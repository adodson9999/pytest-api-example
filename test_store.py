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
    """
    Purpose:  Creates a fresh pet + corresponding pet-order before each test that uses it
    Why:      Guarantees isolation — no test modifies shared data → avoids order-dependent flakiness
              UUID in name prevents name collision when many tests run in parallel / repeatedly
    """
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

    # 10 follow-up questions & short answers:
    # 1. Why not use a global / session-scoped fixture? → Risk of state pollution between tests
    # 2. Why modulo 1e9 on uuid? → Shorter number, still collision-resistant for test purposes
    # 3. Should we also delete pet/order in teardown? → Optional — many prefer DB reset per suite
    # 4. Why allow 200 or 201? → API might return 200 on creation — more flexible
    # 5. Can we make pet type parametrizable? → Yes — add param to fixture if needed later
    # 6. Why not use factory-boy / model-bakery? → Simpler to keep raw dicts for small API
    # 7. What if /pets/ endpoint changes schema? → Test fails loudly — good signal
    # 8. Is uuid4().int safe? → Yes — positive, very large, negligible collision risk
    # 9. Should we validate full pet/order schema here? → Better in separate schema tests
    # 10. Can this fixture be used for DELETE tests too? → Yes — just ignore status checks

def test_patch_order_by_id(order_test_data):
    """
    Purpose:  Happy-path test: update pet order status to "sold" → verify pet status also updated
    Why:      Core business rule of pet store — ordering pet should mark it sold
    """
    order_id = order_test_data["order"]["id"]
    pet_id = order_test_data["pet_id"]
    response = api_helpers.make_request("PATCH", f"/store/order/{order_id}", json={"status": "sold"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Body: {response.text}"
    data = response.json()
    assert data.get("message") == "Order and pet status updated successfully"
    pet_resp = api_helpers.make_request("GET", f"/pets/{pet_id}")
    assert pet_resp.status_code == 200
    assert pet_resp.json().get("status") == "sold"

    # 10 follow-up questions & short answers:
    # 1. Why not check full response schema? → Can be added later with jsonschema
    # 2. Should we also verify order status changed? → Yes — missing in current test
    # 3. What if PATCH is idempotent? → Test still passes — good
    # 4. Why GET pet instead of trusting message? → Independent verification → stronger test
    # 5. Can we parametrize status? → Yes — good candidate for @pytest.mark.parametrize
    # 6. What if pet was already sold? → API should handle → maybe add separate test
    # 7. Should we capture original pet status first? → Yes — for delta assertion
    # 8. Why no timeout on requests? → api_helpers probably has default
    # 9. Can we use hamcrest for message? → Yes — assert_that(data["message"], equal_to(...))
    # 10. Should we test concurrent PATCH? → Advanced — needs separate stress suite

def test_patch_order_by_id_invalid_status_400(order_test_data):
    """
    Purpose:  Negative test: try invalid status value → expect 400 validation error
    Why:      Ensures API enforces enum-like constraint on status field
    """
    order_id = order_test_data["order"]["id"] # ✅ correct
    resp = api_helpers.make_request("PATCH", f"/store/order/{order_id}", json={"status": "nope"})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}. Body: {resp.text}"

    # 10 follow-up questions & short answers:
    # 1. Should we check error message contains "invalid"? → Yes — stronger test
    # 2. Why not parametrize many bad statuses? → Good idea — list of ["pendingg", "", None,...]
    # 3. What if API returns 422 instead? → Update expectation or make flexible
    # 4. Should we also try null / missing status? → Separate test — different semantics
    # 5. Can status be case-sensitive? → Probably — add uppercase/lowercase variants
    # 6. Why no payload schema validation here? → Could add with jsonschema
    # 7. Is 400 enough or need 422? → Depends on API convention (400 common)
    # 8. Should we test empty json {} ? → Yes — separate test case
    # 9. What if order is already sold? → Different test — focus here on bad input
    # 10. Can we snapshot error response? → Yes — with pytest-snapshot or inline

def test_patch_order_by_id_not_found_404():
    """
    Purpose:  Negative test: try to PATCH non-existent order ID
    Why:      Verifies proper 404 behavior on resource not found
    """
    resp = api_helpers.make_request("PATCH", "/store/order/not-a-real-id", json={"status": "sold"})
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}. Body: {resp.text}"

    # 10 follow-up questions & short answers:
    # 1. Why string "not-a-real-id"? → Forces type coercion / parsing error path
    # 2. Should we also try negative int / 0? → Yes — add parametrized cases
    # 3. What error message should we check? → Optional — e.g. contains "not found"
    # 4. Is UUID format required? → If yes → test wrong format separately
    # 5. Should we try very large number? → Possible overflow test
    # 6. What if DB returns 500 instead? → Test would fail — good signal
    # 7. Can we use real deleted order ID? → Risky — needs cleanup logic
    # 8. Why no auth check here? → Separate security tests
    # 9. Should response have JSON body? → Usually yes — can assert structure
    # 10. Is 404 vs 400 correct here? → 404 = not found, 400 = bad request

import pytest
import uuid
import api_helpers

PET_STATUS = ["available", "pending", "sold"] # keep aligned with your API

# -----------------------------
# Helpers / Fixtures
# -----------------------------

def _post_json(path: str, payload: dict):
    """
    Purpose:  Tiny wrapper — POST json payload and return response
    Why:      Reduces repetition, improves readability in many tests
    """
    return api_helpers.make_request("POST", path, json=payload)

    # 10 follow-up questions & short answers:
    # 1. Why not general _request(method, path, **kwargs)? → Simpler for now
    # 2. Should it handle non-JSON? → No — all these tests are JSON
    # 3. Can we add timeout param? → Yes — pass through to make_request
    # 4. Why no assert on status here? → Intentional — caller decides
    # 5. Should we log payload on failure? → api_helpers hopefully does
    # 6. Can we make it async later? → Easy — change to async def + await
    # 7. Why dict type hint? → Clear contract — we always send JSON-like
    # 8. Should it return json() ? → No — sometimes we want raw response
    # 9. Can we add headers support? → Yes — extend signature
    # 10. Is this better than direct call? → Yes — DRY + easier refactor

def _patch_json(path: str, payload: dict):
    """
    Purpose:  Wrapper for PATCH requests — same reasoning as _post_json
    Why:      Consistency + less typing in PATCH-heavy tests
    """
    return api_helpers.make_request("PATCH", path, json=payload)

    # 10 follow-up questions & short answers: (similar to _post_json)
    # 1–10 mirror _post_json answers — just replace POST with PATCH

def _get_json(path: str):
    """
    Purpose:  Wrapper for simple GET requests
    Why:      Same — reduces boilerplate when we only need GET
    """
    return api_helpers.make_request("GET", path)

    # 10 follow-up questions & short answers:
    # 1. Why no json= param? → GET usually doesn't send body
    # 2. Should it accept params=? → Yes — good future extension
    # 3–10 similar to above wrappers

def _create_inventory_item(initial_stock: int = 10):
    """
    Purpose:  Helper — creates one inventory item with given stock
    Why:      Reusable building block for inventory-order tests
    """
    resp = _post_json("/inventory/", {"inventory": initial_stock})
    assert resp.status_code in (200, 201), f"Failed to create inventory. {resp.status_code}: {resp.text}"
    return resp.json()

    # 10 follow-up questions & short answers:
    # 1. Why default 10? → Enough for most test cases without waste
    # 2. Should we allow name/description? → Add optional params later
    # 3. Why not fixture? → Used directly in some places — flexibility
    # 4. What if stock=0 allowed? → Test separately
    # 5. Should return typed model? → Optional — pydantic later
    # 6. Can we add cleanup? → Usually DB reset handles it
    # 7. Why assert here instead of caller? → Fail fast + clear message
    # 8. Should we check inventory == initial_stock? → Yes — good addition
    # 9. What if /inventory/ requires auth? → Add in api_helpers
    # 10. Can we parametrize stock? → Yes — in calling tests

def _create_pet_available():
    """
    Purpose:  Creates one available pet (dog) with unique name
    Why:      Most common prerequisite for pet-order tests
    """
    payload = {
        "name": f"TestPet-{uuid.uuid4().hex[:8]}",
        "type": "dog",
        "status": "available",
    }
    resp = _post_json("/pets/", payload)
    assert resp.status_code in (200, 201), f"Failed to create pet. {resp.status_code}: {resp.text}"
    return resp.json()

    # 10 follow-up questions & short answers:
    # 1. Why hex[:8] instead of int? → Shorter, still unique enough
    # 2. Why hardcode "dog"? → Simplest — can parametrize later
    # 3. Should status be param? → Yes — for pending/sold tests
    # 4. Why not use order_test_data fixture? → This is lower-level building block
    # 5–10 similar to order_test_data reasoning

# Fixtures below use the helpers above

@pytest.fixture
def inv_item():
    return _create_inventory_item(initial_stock=10)

    # 10 follow-up questions & short answers:
    # 1. Why not parametrize stock? → Can create stock_5, stock_50 fixtures
    # 2. Scope? → Default=function — good for isolation
    # 3–10 similar to _create_inventory_item

@pytest.fixture
def pet_item():
    return _create_pet_available()

    # similar Q&A as above

@pytest.fixture
def inv_order(inv_item):
    """
    Purpose:  Creates a completed inventory purchase order (amount=1)
    Why:      Ready-made order for GET/PATCH/DELETE tests on store/order
    """
    payload = {"inven_id": inv_item["id"], "amount_purchase": 1}
    resp = _post_json("/store/order", payload)
    assert resp.status_code in (200, 201), f"Failed to create inv order. {resp.status_code}: {resp.text}"
    return resp.json()

    # 10 follow-up questions & short answers:
    # 1. Why amount=1 always? → Simplest successful case
    # 2. Should we have inv_order_5? → Yes — for amount tests
    # 3. Can we add status check? → Yes — e.g. "completed"
    # 4–10 similar to previous creation fixtures

@pytest.fixture
def pet_order(pet_item):
    """
    Purpose:  Creates a pet order (links to existing pet)
    Why:      Most common order type in pet-store domain
    """
    payload = {"inven_id": pet_item["id"]}
    resp = _post_json("/store/order/pet", payload)
    assert resp.status_code in (200, 201), f"Failed to create pet order. {resp.status_code}: {resp.text}"
    return resp.json()

    # similar Q&A as inv_order

# -----------------------------
# 1) /store/order payload validation tests (inventory orders)
# -----------------------------

def test_store_order_requires_inven_id_400():
    """
    Purpose:  Negative — POST /store/order without inven_id
    Why:      Required field validation
    """
    resp = _post_json("/store/order", {"amount_purchase": 1})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}. Body: {resp.text}"

    # 10 follow-up questions & short answers: (typical required-field negative test)

def test_store_order_requires_amount_purchase_400(inv_item):
    """
    Purpose:  Negative — missing amount_purchase
    Why:      Required field
    """
    resp = _post_json("/store/order", {"inven_id": inv_item["id"]})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}. Body: {resp.text}"

    # similar Q&A

@pytest.mark.parametrize("amount", [0, -1, -999])
def test_store_order_amount_purchase_must_be_positive_int_400(inv_item, amount):
    """
    Purpose:  Negative — amount_purchase ≤ 0 not allowed
    Why:      Business rule — can't buy zero or negative items
    """
    resp = _post_json("/store/order", {"inven_id": inv_item["id"], "amount_purchase": amount})
    assert resp.status_code == 400, f"Expected 400 for amount={amount}, got {resp.status_code}. Body: {resp.text}"

    # 10 follow-up questions & short answers:
    # 1. Why not include -0? → Same as 0 in python
    # 2. Should we check error message? → Yes — "must be positive"
    # 3. What about very large int? → Separate overflow test
    # 4–10 typical boundary / validation questions

@pytest.mark.parametrize("amount", ["1", 1.5, True, None, [], {}])
def test_store_order_amount_purchase_type_validation_400(inv_item, amount):
    """
    Purpose:  Negative — amount_purchase wrong type
    Why:      Schema / type enforcement
    """
    resp = _post_json("/store/order", {"inven_id": inv_item["id"], "amount_purchase": amount})
    assert resp.status_code == 400, f"Expected 400 for amount={amount}, got {resp.status_code}. Body: {resp.text}"

    # similar Q&A

@pytest.mark.parametrize("bad_inven_id", [0, -1, 999999999])
def test_store_order_inventory_not_found_404(bad_inven_id):
    """
    Purpose:  Negative — inven_id that doesn't exist
    Why:      Resource lookup failure
    """
    resp = _post_json("/store/order", {"inven_id": bad_inven_id, "amount_purchase": 1})
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}. Body: {resp.text}"

    # similar Q&A to not-found tests

def test_store_order_not_enough_inventory_400():
    """
    Purpose:  Negative business rule — can't buy more than available
    Why:      Inventory protection / optimistic locking
    """
    inv = _create_inventory_item(initial_stock=1)
    resp = _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": 2})
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}. Body: {resp.text}"

    # 10 follow-up questions & short answers:
    # 1. Should we check inventory unchanged? → Yes — strong invariant
    # 2. What if concurrent orders? → Race condition / locking test
    # 3. Should error say "not enough"? → Nice to assert message
    # 4–10 typical stock validation questions

# -----------------------------
# 2) /store/order success + inventory decrement tests
# -----------------------------

def test_store_order_success_201(inv_item):
    """
    Purpose:  Happy path — create inventory order + check response shape
    Why:      Basic correctness + contract verification
    """
    payload = {"inven_id": inv_item["id"], "amount_purchase": 1}
    resp = _post_json("/store/order", payload)
    assert resp.status_code in (200, 201), f"Expected 201/200, got {resp.status_code}. Body: {resp.text}"
    data = resp.json()
    assert isinstance(data, dict)
    assert data.get("inven_id") == inv_item["id"]
    assert data.get("amount_purchase") == 1
    assert isinstance(data.get("id"), int), f"Order id should be int. Got: {data.get('id')}"

    # 10 follow-up questions & short answers:
    # 1. Why not check status / created_at? → Add if present
    # 2. Should we GET order after? → Yes — persistence check
    # 3. Should we verify inventory decremented? → Critical — missing here
    # 4. Why allow 200 or 201? → API inconsistency tolerance
    # 5. Can we use jsonschema here? → Yes — better than manual asserts
    # 6. Should we check order in list endpoint? → Separate list test
    # 7. What if amount_purchase=5? → Parametrized test
    # 8. Is id always positive? → Probably — add >=1 assert
    # 9. Should we snapshot response? → Good for regression
    # 10. Can we add auth / role check? → Security suite

def test_store_order_decrements_inventory(inv_item):
    """
    Purpose:  Verifies that placing an inventory order reduces stock by the purchased amount
    Why:      Core invariant of any inventory system — buying something must decrease available quantity
              This is the non-parametrized baseline version (fixed amount=3)
    """
    before = _get_json(f"/inventory/{inv_item['id']}")
    assert before.status_code == 200, f"Expected 200, got {before.status_code}. Body: {before.text}"
    before_stock = before.json().get("inventory")
    resp = _post_json("/store/order", {"inven_id": inv_item["id"], "amount_purchase": 3})
    assert resp.status_code in (200, 201), f"Expected 201/200, got {resp.status_code}. Body: {resp.text}"
    after = _get_json(f"/inventory/{inv_item['id']}")
    assert after.status_code == 200, f"Expected 200, got {after.status_code}. Body: {after.text}"
    after_stock = after.json().get("inventory")
    assert after_stock == before_stock - 3, f"Expected stock {before_stock-3}, got {after_stock}"

    # 10 follow-up questions & answers
    # 1. Why fetch inventory twice instead of trusting the order response? → Independent source of truth, catches race conditions / bugs
    # 2. Why hardcode amount=3 instead of 1? → Makes arithmetic difference more obvious during debugging
    # 3. Should we also check the order response contains amount_purchase=3? → Yes — good addition for contract testing
    # 4. What if concurrent orders happen? → This test is serial — concurrency needs separate stress/locking tests
    # 5. Why allow 200 or 201? → Defensive — API might evolve to return 200 on success
    # 6. Should we assert inventory never goes negative here? → Covered indirectly — separate overbuy test exists
    # 7. Can we snapshot before/after delta? → Possible with pytest-snapshot, but current assert is clearer
    # 8. Why not use hamcrest for comparison? → Simple int subtract — overkill
    # 9. What happens if inventory endpoint is slow? → Test becomes slow — could add timeout in api_helpers
    # 10. Should we verify order id is returned and positive? → Yes — belongs in success shape test


@pytest.mark.parametrize("amount", [1, 2, 5])
def test_store_order_decrements_inventory_param(inv_item, amount):
    """
    Purpose:  Same business rule as above, but parametrized for different purchase quantities
    Why:      More coverage with less duplication — proves decrement logic is correct for various (small) amounts
    """
    before = _get_json(f"/inventory/{inv_item['id']}").json()["inventory"]
    resp = _post_json("/store/order", {"inven_id": inv_item["id"], "amount_purchase": amount})
    assert resp.status_code in (200, 201), f"Create order failed. {resp.status_code}: {resp.text}"
    after = _get_json(f"/inventory/{inv_item['id']}").json()["inventory"]
    assert after == before - amount

    # 10 follow-up questions & answers
    # 1. Why only small amounts (1,2,5)? → Faster + enough to prove linear decrement
    # 2. Why not include 0? → 0 is invalid input — covered in earlier validation tests
    # 3. Should we add amount=10 or larger? → Yes — if stock fixture allows it safely
    # 4. Why inline .json()["inventory"] instead of helper? → Readability for this simple case
    # 5. What if amount > initial stock? → Should fail order — covered in overbuy test
    # 6. Can we combine with status check on order? → Yes — extend assertion
    # 7. Is fixture scope correct? → function scope → fresh stock each param run
    # 8. Should we log before/after values on failure? → pytest shows them anyway
    # 9. Why no explicit order shape validation here? → Focus is solely on stock side-effect
    # 10. Better to use one big parametrized test or separate functions? → Parametrized is DRY and scales better


def test_store_order_multiple_orders_reduce_inventory_correctly():
    """
    Purpose:  Checks cumulative effect — multiple orders against same inventory item
    Why:      Ensures no over-subtraction or state reset bug when orders are sequential
    """
    inv = _create_inventory_item(initial_stock=10)
    _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": 2})
    _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": 3})
    final = _get_json(f"/inventory/{inv['id']}").json()["inventory"]
    assert final == 5, f"Expected final stock 5, got {final}"

    # 10 follow-up questions & answers
    # 1. Why not capture responses of the orders? → Not needed for this invariant
    # 2. Should we assert no negative stock ever? → Implicit — API should reject overbuy
    # 3. Why hardcode 2+3=5 instead of variables? → Easier to read and debug
    # 4. Can this become flaky with parallel execution? → No — single test, sequential calls
    # 5. Should we check order IDs are different? → Belongs in ID uniqueness test
    # 6. What if API has optimistic locking? → Test passes if locking works
    # 7. Better to loop instead of two calls? → Two calls are clearer for small N
    # 8. Should we verify inventory after each order? → Yes — stronger test (delta check)
    # 9. Why not use parametrized cumulative amounts? → Possible but more complex
    # 10. Does this test transactionality? → Indirectly — assumes atomic decrement


# -----------------------------
# 3) /store/order ID assignment (first available key)
# -----------------------------

def test_store_order_id_is_int(inv_item):
    """
    Purpose:  Basic contract — order creation returns integer ID
    Why:      Prevents string IDs, UUIDs or missing ID breaking downstream consumers
    """
    resp = _post_json("/store/order", {"inven_id": inv_item["id"], "amount_purchase": 1})
    assert resp.status_code in (200, 201)
    assert isinstance(resp.json().get("id"), int)

    # 10 follow-up questions & answers
    # 1. Why not assert id > 0? → Good addition — prevents zero/negative IDs
    # 2. Should we check uniqueness here? → No — separate test exists
    # 3. What if id is float 1.0? → isinstance(int) fails → good catch
    # 4. Why get("id") instead of ["id"]? → Safer against KeyError
    # 5. Can id be very large? → Later test can check upper bound if needed
    # 6. Should we test pet orders return int id too? → Yes — duplicate or parametrize
    # 7. Better to use schema validation? → Yes — jsonschema would cover this + more
    # 8. Why no full response shape check? → Keep test focused
    # 9. What if API returns "id": "1"? → Fails correctly
    # 10. Should id be auto-incrementing? → Separate monotonic test exists


def test_store_order_creates_unique_ids_for_two_orders():
    """
    Purpose:  Ensures two consecutive orders get different IDs
    Why:      Basic uniqueness — critical for any resource identifier
    """
    inv = _create_inventory_item(initial_stock=10)
    r1 = _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": 1})
    r2 = _post_json("/store/order", {"inven_id": inv["id"], "amount_purchase": 1})
    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201)
    assert r1.json()["id"] != r2.json()["id"]

    # 10 follow-up questions & answers
    # 1. Why only two orders? → Minimal proof — enough for most bugs
    # 2. Should we check r2.id > r1.id? → Yes — if monotonic, add in separate test
    # 3. What if DB rolls back one? → Rare — would require transaction test
    # 4. Better name: test_order_ids_are_unique? → Yes — clearer
    # 5. Should we test pet orders uniqueness too? → Duplicate or parametrize
    # 6. Can we make it 10 orders in loop? → Overkill for this purpose
    # 7. Why not use set() of ids? → Two is simple enough
    # 8. What if API reuses IDs on failure? → Test would fail — good
    # 9. Should we GET /orders to verify both exist? → Separate list endpoint test
    # 10. Is sequential ID enough or need UUID? → Depends on API design


# -----------------------------
# 4) /store/order/pet validation tests
# -----------------------------

def test_store_order_pet_not_found_404():
    """
    Purpose:  Attempt to order non-existent pet → expect 404
    Why:      Proper resource-not-found behavior
    """
    resp = _post_json("/store/order/pet", {"inven_id": 999999999})
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}. Body: {resp.text}"

    # 10 follow-up questions & answers
    # 1. Why 999999999 specifically? → Very unlikely to exist accidentally
    # 2. Should we try negative / zero / string? → Separate negative tests exist
    # 3. Should we check error message? → Nice to have — "Pet not found"
    # 4. What if pet exists but deleted? → Depends on soft-delete — usually 404
    # 5. Is 404 correct vs 400? → 404 = resource missing, 400 = bad input
    # 6. Can we use real deleted pet ID? → Risky without cleanup
    # 7. Should response be JSON? → Usually yes — can add structure check
    # 8. Why no payload validation here? → Focus is on lookup failure
    # 9. Better to parametrize bad IDs? → Yes — see later non-numeric test
    # 10. What if auth required? → Separate security tests


def test_store_order_pet_missing_inven_id_400_or_404():
    """
    Purpose:  POST without inven_id → expect validation or lookup failure
    Why:      Required field + graceful handling of null/None ID
    """
    # Depending on your API behavior, missing inven_id may become 404 "No pet found with ID None"
    resp = _post_json("/store/order/pet", {})
    assert resp.status_code in (400, 404), f"Expected 400/404, got {resp.status_code}. Body: {resp.text}"

    # 10 follow-up questions & answers
    # 1. Why allow 400 or 404? → Defensive — API might treat null as not-found
    # 2. Should we check error detail contains "inven_id"? → Stronger test
    # 3. Better to test {"inven_id": None} separately? → Yes — different semantics
    # 4. What about {"inven_id": ""} or false? → Type validation test
    # 5. Why empty dict instead of missing key? → Same in JSON POST
    # 6. Should we assert no side effects? → Hard — pet unchanged implicit
    # 7. Is 422 more RESTful here? → Possible — depends on API
    # 8. Can we use jsonschema for payload? → Yes — future improvement
    # 9. What if extra unknown fields? → Separate test
    # 10. Should this be parametrized with bad payloads? → Yes — good candidate


def test_store_order_pet_requires_available_status(pet_item):
    """
    Purpose:  Try to order pet that is already ordered → should fail
    Why:      Prevents double-booking / overselling pets
    """
    # If you don't have a pet PATCH, you can create an order then set to sold via store patch later,
    # but simplest: order once to set pending, then try ordering again.
    pet_id = pet_item["id"]
    first = _post_json("/store/order/pet", {"inven_id": pet_id})
    assert first.status_code in (200, 201)
    second = _post_json("/store/order/pet", {"inven_id": pet_id})
    assert second.status_code == 400, f"Expected 400, got {second.status_code}. Body: {second.text}"

    # 10 follow-up questions & answers
    # 1. Why set to pending not sold? → Ordering sets pending → re-order should block
    # 2. Should we check error message "already ordered"? → Nice to have
    # 3. What if pet is sold directly? → Separate test if PATCH exists
    # 4. Is 400 correct vs 409 conflict? → 400 common for business rules
    # 5. Should first order set pending? → Yes — verified in success test
    # 6. Can we clean up after? → Usually DB reset
    # 7. Better to use different pets? → No need — same pet is correct scenario
    # 8. What if concurrent orders? → Race condition test needed separately
    # 9. Should we verify pet status after first? → Already in other test
    # 10. Why not parametrize status? → This is specific pending case


# -----------------------------
# 5) /store/order/pet success + sync tests
# -----------------------------

def test_store_order_pet_success_sets_pet_pending(pet_item):
    """
    Purpose:  Ordering pet changes its status to "pending"
    Why:      Important side-effect — pet should be reserved
    """
    pet_id = pet_item["id"]
    resp = _post_json("/store/order/pet", {"inven_id": pet_id})
    assert resp.status_code in (200, 201), f"Expected 201/200, got {resp.status_code}. Body: {resp.text}"
    pet_get = _get_json(f"/pets/{pet_id}")
    assert pet_get.status_code == 200
    assert pet_get.json().get("status") == "pending"

    # 10 follow-up questions & answers
    # 1. Why not check order status too? → Done in separate test
    # 2. Should we capture original status? → Yes — for delta assertion
    # 3. What if pet already pending? → Should fail — covered elsewhere
    # 4. Is "pending" hardcoded ok? → Yes — matches PET_STATUS list
    # 5. Better to use fixture with pending pet? → No — we want fresh available
    # 6. Should we check order_id set? → Separate test
    # 7. Why GET instead of trusting order response? → Source of truth
    # 8. Can status be enum-validated? → Yes — in schema
    # 9. What if race — two orders? → Needs locking test
    # 10. Should we assert no inventory change? → Pets don't use inventory
