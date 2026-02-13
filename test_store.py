from jsonschema import validate
import pytest
import api_helpers
from hamcrest import assert_that, contains_string, is_
import uuid


'''
TODO: Finish this test by...
1) Creating a function to test the PATCH request /store/order/{order_id}
2) *Optional* Consider using @pytest.fixture to create unique test data for each run
2) *Optional* Consider creating an 'Order' model in schemas.py and validating it in the test
3) Validate the response codes and values
4) Validate the response message "Order and pet status updated successfully"
'''

# Optional fixture: creates a unique pet + order for each test run
@pytest.fixture
def order_test_data():
    new_name = f"TestPet-{uuid.uuid4().int % 1_000_000_000}"
    pet_payload = {"name": new_name, "type": "dog", "status": "available"}

    pet_resp = api_helpers.make_request("POST", "/pets/", json=pet_payload)
    assert pet_resp.status_code in (200, 201), (
        f"Failed to create pet. Status: {pet_resp.status_code}. Body: {pet_resp.text}"
    )

    created_pet = pet_resp.json()
    pet_id = created_pet["id"]

    order_payload = {"inven_id": pet_id}
    order_resp = api_helpers.make_request("POST", "/store/order/pet", json=order_payload)
    assert order_resp.status_code in (200, 201), (
        f"Failed to create order. Status: {order_resp.status_code}. Body: {order_resp.text}"
    )

    order_json = order_resp.json()
    return {
        "order": order_json,
        "pet_id": pet_id,
    }


def test_patch_order_by_id(order_test_data):
    order_id = order_test_data["order"]["id"]
    pet_id = order_test_data["pet_id"]

    response = api_helpers.make_request("PATCH", f"/store/order/{order_id}", json={"status": "sold"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Body: {response.text}"

    data = response.json()
    assert data.get("message") == "Order and pet status updated successfully"

    pet_resp = api_helpers.make_request("GET", f"/pets/{pet_id}")
    assert pet_resp.status_code == 200
    assert pet_resp.json().get("status") == "sold"
def test_patch_order_by_id_invalid_status_400(order_test_data):
    order_id = order_test_data["order"]["id"]   # ✅ correct
    resp = api_helpers.make_request("PATCH", f"/store/order/{order_id}", json={"status": "nope"})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}. Body: {resp.text}"
    
def test_patch_order_by_id_not_found_404():
    resp = api_helpers.make_request("PATCH", "/store/order/not-a-real-id", json={"status": "sold"})
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}. Body: {resp.text}"



import pytest
import uuid
import api_helpers

PET_STATUS = ["available", "pending", "sold"]  # keep aligned with your API


# -----------------------------
# Helpers / Fixtures
# -----------------------------
def _post_json(path: str, payload: dict):
    return api_helpers.make_request("POST", path, json=payload)


def _patch_json(path: str, payload: dict):
    return api_helpers.make_request("PATCH", path, json=payload)


def _get_json(path: str):
    return api_helpers.make_request("GET", path)


def _create_inventory_item(initial_stock: int = 10):
    """
    Creates an inventory item via /inventory/ POST (server assigns id).
    Returns {"id": int, "inventory": int}
    """
    resp = _post_json("/inventory/", {"inventory": initial_stock})
    assert resp.status_code in (200, 201), f"Failed to create inventory. {resp.status_code}: {resp.text}"
    return resp.json()


def _create_pet_available():
    """
    Creates a Pet via /pets/ POST (server assigns id).
    Returns pet dict that includes id.
    """
    payload = {
        "name": f"TestPet-{uuid.uuid4().hex[:8]}",
        "type": "dog",
        "status": "available",
    }
    resp = _post_json("/pets/", payload)
    assert resp.status_code in (200, 201), f"Failed to create pet. {resp.status_code}: {resp.text}"
    return resp.json()


@pytest.fixture
def inv_item():
    return _create_inventory_item(initial_stock=10)


@pytest.fixture
def pet_item():
    return _create_pet_available()


@pytest.fixture
def inv_order(inv_item):
    """
    Places an inventory order (store/order) for amount 1 by default.
    Returns created order json.
    """
    payload = {"inven_id": inv_item["id"], "amount_purchase": 1}
    resp = _post_json("/store/order", payload)
    assert resp.status_code in (200, 201), f"Failed to create inv order. {resp.status_code}: {resp.text}"
    return resp.json()


@pytest.fixture
def pet_order(pet_item):
    """
    Places a pet order (store/order/pet).
    Returns created order json (with id, inven_id, status).
    """
    payload = {"inven_id": pet_item["id"]}
    resp = _post_json("/store/order/pet", payload)
    assert resp.status_code in (200, 201), f"Failed to create pet order. {resp.status_code}: {resp.text}"
    return resp.json()


# -----------------------------
# 1) /store/order payload validation tests (inventory orders)
# -----------------------------

def test_store_order_requires_inven_id_400():
    resp = _post_json("/store/order", {"amount_purchase": 1})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}. Body: {resp.text}"


def test_store_order_requires_amount_purchase_400(inv_item):
    resp = _post_json("/store/order", {"inven_id": inv_item["id"]})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}. Body: {resp.text}"


@pytest.mark.parametrize("amount", [0, -1, -999])
def test_store_order_amount_purchase_must_be_positive_int_400(inv_item, amount):
    resp = _post_json("/store/order", {"inven_id": inv_item["id"], "amount_purchase": amount})
    assert resp.status_code == 400, f"Expected 400 for amount={amount}, got {resp.status_code}. Body: {resp.text}"


@pytest.mark.parametrize("amount", ["1", 1.5, True, None, [], {}])
def test_store_order_amount_purchase_type_validation_400(inv_item, amount):
    resp = _post_json("/store/order", {"inven_id": inv_item["id"], "amount_purchase": amount})
    assert resp.status_code == 400, f"Expected 400 for amount={amount}, got {resp.status_code}. Body: {resp.text}"


@pytest.mark.parametrize("bad_inven_id", [0, -1, 999999999])
def test_store_order_inventory_not_found_404(bad_inven_id):
    resp = _post_json("/store/order", {"inven_id": bad_inven_id, "amount_purchase": 1})
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}. Body: {resp.text}"


def test_store_order_not_enough_inventory_400():
    inv = _create_inventory_item(initial_stock=1)
    resp = _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": 2})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}. Body: {resp.text}"


# -----------------------------
# 2) /store/order success + inventory decrement tests
# -----------------------------

def test_store_order_success_201(inv_item):
    payload = {"inven_id": inv_item["id"], "amount_purchase": 1}
    resp = _post_json("/store/order", payload)
    assert resp.status_code in (200, 201), f"Expected 201/200, got {resp.status_code}. Body: {resp.text}"
    data = resp.json()
    assert isinstance(data, dict)
    assert data.get("inven_id") == inv_item["id"]
    assert data.get("amount_purchase") == 1
    assert isinstance(data.get("id"), int), f"Order id should be int. Got: {data.get('id')}"


def test_store_order_decrements_inventory(inv_item):
    before = _get_json(f"/inventory/{inv_item['id']}")
    assert before.status_code == 200, f"Expected 200, got {before.status_code}. Body: {before.text}"
    before_stock = before.json().get("inventory")

    resp = _post_json("/store/order", {"inven_id": inv_item["id"], "amount_purchase": 3})
    assert resp.status_code in (200, 201), f"Expected 201/200, got {resp.status_code}. Body: {resp.text}"

    after = _get_json(f"/inventory/{inv_item['id']}")
    assert after.status_code == 200, f"Expected 200, got {after.status_code}. Body: {after.text}"
    after_stock = after.json().get("inventory")

    assert after_stock == before_stock - 3, f"Expected stock {before_stock-3}, got {after_stock}"


@pytest.mark.parametrize("amount", [1, 2, 5])
def test_store_order_decrements_inventory_param(inv_item, amount):
    before = _get_json(f"/inventory/{inv_item['id']}").json()["inventory"]
    resp = _post_json("/store/order", {"inven_id": inv_item["id"], "amount_purchase": amount})
    assert resp.status_code in (200, 201), f"Create order failed. {resp.status_code}: {resp.text}"
    after = _get_json(f"/inventory/{inv_item['id']}").json()["inventory"]
    assert after == before - amount


def test_store_order_multiple_orders_reduce_inventory_correctly():
    inv = _create_inventory_item(initial_stock=10)
    _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": 2})
    _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": 3})
    final = _get_json(f"/inventory/{inv['id']}").json()["inventory"]
    assert final == 5, f"Expected final stock 5, got {final}"


# -----------------------------
# 3) /store/order ID assignment (first available key)
# -----------------------------

def test_store_order_id_is_int(inv_item):
    resp = _post_json("/store/order", {"inven_id": inv_item["id"], "amount_purchase": 1})
    assert resp.status_code in (200, 201)
    assert isinstance(resp.json().get("id"), int)


def test_store_order_creates_unique_ids_for_two_orders():
    inv = _create_inventory_item(initial_stock=10)
    r1 = _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": 1})
    r2 = _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": 1})
    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201)
    assert r1.json()["id"] != r2.json()["id"]


# -----------------------------
# 4) /store/order/pet validation tests
# -----------------------------

def test_store_order_pet_not_found_404():
    resp = _post_json("/store/order/pet", {"inven_id": 999999999})
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}. Body: {resp.text}"


def test_store_order_pet_missing_inven_id_400_or_404():
    # Depending on your API behavior, missing inven_id may become 404 "No pet found with ID None"
    resp = _post_json("/store/order/pet", {})
    assert resp.status_code in (400, 404), f"Expected 400/404, got {resp.status_code}. Body: {resp.text}"


def test_store_order_pet_requires_available_status(pet_item):
    # Make pet sold then attempt order -> should 400
    pet_id = pet_item["id"]
    # If you don't have a pet PATCH, you can create an order then set to sold via store patch later,
    # but simplest: order once to set pending, then try ordering again.
    first = _post_json("/store/order/pet", {"inven_id": pet_id})
    assert first.status_code in (200, 201)

    second = _post_json("/store/order/pet", {"inven_id": pet_id})
    assert second.status_code == 400, f"Expected 400, got {second.status_code}. Body: {second.text}"


# -----------------------------
# 5) /store/order/pet success + sync tests
# -----------------------------

def test_store_order_pet_success_sets_pet_pending(pet_item):
    pet_id = pet_item["id"]
    resp = _post_json("/store/order/pet", {"inven_id": pet_id})
    assert resp.status_code in (200, 201), f"Expected 201/200, got {resp.status_code}. Body: {resp.text}"

    pet_get = _get_json(f"/pets/{pet_id}")
    assert pet_get.status_code == 200
    assert pet_get.json().get("status") == "pending"


def test_store_order_pet_returns_pending_status(pet_item):
    pet_id = pet_item["id"]
    resp = _post_json("/store/order/pet", {"inven_id": pet_id})
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data.get("status") == "pending"
    assert data.get("inven_id") == pet_id


def test_store_order_pet_sets_pet_order_id_nonzero(pet_item):
    pet_id = pet_item["id"]
    order = _post_json("/store/order/pet", {"inven_id": pet_id}).json()

    pet_get = _get_json(f"/pets/{pet_id}").json()
    assert pet_get.get("order_id") == order.get("id"), f"Expected pet.order_id to equal order.id"


def test_store_order_pet_order_id_increments():
    p1 = _create_pet_available()
    p2 = _create_pet_available()
    o1 = _post_json("/store/order/pet", {"inven_id": p1["id"]}).json()
    o2 = _post_json("/store/order/pet", {"inven_id": p2["id"]}).json()
    assert o2["id"] == o1["id"] + 1


# -----------------------------
# 6) PATCH /store/order/<id> validation tests
# -----------------------------

def test_patch_order_not_found_404():
    resp = _patch_json("/store/order/999999999", {"status": "sold"})
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}. Body: {resp.text}"


@pytest.mark.parametrize("bad_id", ["abc", "not-a-number", "12x"])
def test_patch_order_non_numeric_id_404(bad_id):
    resp = _patch_json(f"/store/order/{bad_id}", {"status": "sold"})
    assert resp.status_code == 404, f"Expected 404 for id={bad_id}, got {resp.status_code}. Body: {resp.text}"


def test_patch_order_missing_status_400(pet_order):
    oid = pet_order["id"]
    resp = _patch_json(f"/store/order/{oid}", {})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}. Body: {resp.text}"


@pytest.mark.parametrize("bad_status", ["nope", "DONE", "", None, 123])
def test_patch_order_invalid_status_400(pet_order, bad_status):
    oid = pet_order["id"]
    resp = _patch_json(f"/store/order/{oid}", {"status": bad_status})
    assert resp.status_code == 400, f"Expected 400 for status={bad_status}, got {resp.status_code}. Body: {resp.text}"


# -----------------------------
# 7) PATCH /store/order/<id> success + sync tests
# -----------------------------

@pytest.mark.parametrize("new_status", ["sold", "pending"])
def test_patch_order_updates_pet_status(pet_order, new_status):
    oid = pet_order["id"]
    pet_id = pet_order["inven_id"]

    resp = _patch_json(f"/store/order/{oid}", {"status": new_status})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}. Body: {resp.text}"
    assert resp.json().get("message") == "Order and pet status updated successfully"

    pet_get = _get_json(f"/pets/{pet_id}")
    assert pet_get.status_code == 200
    assert pet_get.json().get("status") == new_status


def test_patch_order_available_cancels_order_and_resets_pet(pet_order):
    oid = pet_order["id"]
    pet_id = pet_order["inven_id"]

    resp = _patch_json(f"/store/order/{oid}", {"status": "available"})
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}. Body: {resp.text}"

    pet_get = _get_json(f"/pets/{pet_id}").json()
    assert pet_get.get("status") == "available"
    assert pet_get.get("order_id") == 0


# -----------------------------
# 8) Order creation + patch lifecycle tests
# -----------------------------

def test_order_pet_then_patch_to_sold_then_pet_is_sold(pet_item):
    pet_id = pet_item["id"]
    order = _post_json("/store/order/pet", {"inven_id": pet_id}).json()
    oid = order["id"]

    resp = _patch_json(f"/store/order/{oid}", {"status": "sold"})
    assert resp.status_code == 200

    pet_get = _get_json(f"/pets/{pet_id}").json()
    assert pet_get["status"] == "sold"


def test_order_pet_then_patch_to_pending_keeps_pending(pet_item):
    pet_id = pet_item["id"]
    order = _post_json("/store/order/pet", {"inven_id": pet_id}).json()
    oid = order["id"]

    resp = _patch_json(f"/store/order/{oid}", {"status": "pending"})
    assert resp.status_code == 200

    pet_get = _get_json(f"/pets/{pet_id}").json()
    assert pet_get["status"] == "pending"


def test_order_pet_then_cancel_available_allows_reorder(pet_item):
    pet_id = pet_item["id"]
    order = _post_json("/store/order/pet", {"inven_id": pet_id}).json()
    oid = order["id"]

    cancel = _patch_json(f"/store/order/{oid}", {"status": "available"})
    assert cancel.status_code == 200

    reorder = _post_json("/store/order/pet", {"inven_id": pet_id})
    assert reorder.status_code in (200, 201), f"Expected reorder success, got {reorder.status_code}. Body: {reorder.text}"


# -----------------------------
# 9) More inventory order boundary tests
# -----------------------------

@pytest.mark.parametrize("start_stock, buy, expected_left", [
    (1, 1, 0),
    (2, 1, 1),
    (5, 5, 0),
    (10, 7, 3),
])
def test_store_order_inventory_leftover(start_stock, buy, expected_left):
    inv = _create_inventory_item(initial_stock=start_stock)
    resp = _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": buy})
    assert resp.status_code in (200, 201), f"Order failed. {resp.status_code}: {resp.text}"
    left = _get_json(f"/inventory/{inv['id']}").json()["inventory"]
    assert left == expected_left, f"Expected {expected_left}, got {left}"


@pytest.mark.parametrize("start_stock, buy", [
    (0, 1),
    (1, 2),
    (3, 4),
])
def test_store_order_rejects_overbuy(start_stock, buy):
    inv = _create_inventory_item(initial_stock=start_stock)
    resp = _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": buy})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}. Body: {resp.text}"


# -----------------------------
# 10) Bulk-ish tests to reach 50 (param expansions)
# -----------------------------

@pytest.mark.parametrize("n", list(range(1, 11)))
def test_store_order_repeated_small_purchases_reduce_correctly(n):
    inv = _create_inventory_item(initial_stock=20)
    # purchase 1 each time, n times => remaining 20 - n
    for _ in range(n):
        r = _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": 1})
        assert r.status_code in (200, 201), f"Order failed: {r.status_code} {r.text}"
    remaining = _get_json(f"/inventory/{inv['id']}").json()["inventory"]
    assert remaining == 20 - n


@pytest.mark.parametrize("status", PET_STATUS)
def test_patch_order_accepts_valid_statuses(status, pet_order):
    oid = pet_order["id"]
    resp = _patch_json(f"/store/order/{oid}", {"status": status})
    assert resp.status_code == 200, f"Expected 200 for status={status}, got {resp.status_code}. Body: {resp.text}"


@pytest.mark.parametrize("amount", [1, 2, 3, 4, 5, 6, 7, 8])
def test_store_order_various_amounts_success(amount):
    
    inv = _create_inventory_item(initial_stock=50)
    resp = _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": amount})
    assert resp.status_code in (200, 201), f"Expected 201/200, got {resp.status_code}. Body: {resp.text}"
