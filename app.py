import uuid
from flask import Flask, request, jsonify
from flask_restx import Api, Resource, Namespace
from models import Models
from load_data import load_all_data
from flask_restx import abort
from flask import request
from flask_restx import Resource, abort
import uuid  
from graphql_api import init_graphql
from dataclasses import dataclass
from typing import Callable, Any, Optional
from dataclasses import dataclass
from typing import Any, Callable, Optional
from flask import request
from flask_restx import Resource


app = Flask(__name__)
api = Api(app, version='1.0', title='Petstore API',
          description='A simple Petstore API')


# Enums
PET_STATUS = ['available', 'sold', 'pending']
PET_TYPE = ["dog", "cat", "bird", "rabbit"]

models = Models(api, PET_TYPE, PET_STATUS)

# Namespaces
namespaces_config = {
    "pets": "Pets info",
    "store": "Store operations",
    "customer": "Customers info",
    "inventory": "Inventory info",
    "vet": "Vet info",
    "vendor": "Vendor info",
    "event": "Event info",
    "trainers": "Trainer info"
}

namespaces = {}

for name, description in namespaces_config.items():
    ns = Namespace(name, description=description)
    namespaces[name] = ns
    api.add_namespace(ns)
    
pet_ns = namespaces["pets"]
store_ns = namespaces["store"]
customer_ns = namespaces["customer"]
inventory_ns = namespaces["inventory"]
vet_ns = namespaces["vet"]
vendor_ns = namespaces["vendor"]
event_ns = namespaces["event"]
trainer_ns = namespaces["trainers"]

# In-memory data storage
pets, events, inventory, vendors, trainers, customers, vets = load_all_data()


orders = {}

for pet in pets:
    order_id = pet.get("order_id")

    if isinstance(order_id, int) and order_id != 0:
        orders[order_id] = {
            "id": int(order_id),
            "pet_id": pet["id"], 
        }

'''
Pet Namespace
'''
# only needed if you still use uuid elsewhere (not used for ids below)


class BaseListResource(Resource):
    """
    Base behavior:
    - GET: return ITEMS
    - POST: append payload; server generates sequential id if missing
    """
    ITEMS = None          # list[dict]
    LABEL = "Item"        # e.g. "Pet"
    ID_FIELD = "id"       # default id key


@dataclass
class SharedTarget:
    items: list[dict]
    build: Callable[[dict], dict]
    # Prevent duplicates if you re-post same thing or client supplies same id
    # Example: dedupe_key=lambda created: ("inven_id", created["id"])
    dedupe_key: Optional[Callable[[dict], tuple[str, Any]]] = None


class BaseGetResource(Resource):
    ITEMS = None
    LABEL = "Item"
    ID_FIELD = "id"

    def get_one(self, item_id: int):
        obj = next((x for x in self.ITEMS if x.get(self.ID_FIELD) == item_id), None)
        if obj is None:
            abort(404, f"{self.LABEL} with ID {item_id} not found")
        return obj


def _generate_next_id(existing_ids: set[int]) -> int:
    return next(i for i in range(1, len(existing_ids) + 2) if i not in existing_ids)


def register_list_resource(ns, api, *, items, model, label, id_param=None, shared: list[SharedTarget] | None = None):
    """
    Registers:
      GET   /
      POST  /
      GET   /<int:id>

    Optional:
      shared: list of SharedTarget() to also write to other resource lists on POST.
    """
    id_param = id_param or f"{label.lower()}_id"
    shared = shared or []

    @ns.route('/')
    class _ListResource(BaseListResource):
        ITEMS = items
        LABEL = label

        @ns.doc(f'list_{label.lower()}s')
        @ns.marshal_list_with(model)
        def get(self):
            return self.ITEMS

        @ns.doc(f'create_{label.lower()}')
        @ns.expect(model)
        @ns.marshal_with(model, code=201)
        def post(self):
            payload = api.payload or {}

            existing_ids = {
                x.get(self.ID_FIELD)
                for x in self.ITEMS
                if isinstance(x.get(self.ID_FIELD), int)
            }

            incoming_id = payload.get(self.ID_FIELD)

            if incoming_id is None:
                payload[self.ID_FIELD] = _generate_next_id(existing_ids)
            else:
                if not isinstance(incoming_id, int):
                    api.abort(400, f"{self.LABEL} '{self.ID_FIELD}' must be an integer")
                if incoming_id in existing_ids:
                    api.abort(409, f"{self.LABEL} with ID {incoming_id} already exists")

            # Create the primary object
            self.ITEMS.append(payload)

            # ✅ Shared writes (e.g., also create inventory record)
            for target in shared:
                shared_obj = target.build(payload)

                if target.dedupe_key:
                    key_field, key_value = target.dedupe_key(payload)
                    if any(x.get(key_field) == key_value for x in target.items):
                        # already exists -> skip (or api.abort(409) if you prefer)
                        continue

                target.items.append(shared_obj)

            return payload, 201

    @ns.route(f'/<int:{id_param}>')
    @ns.response(404, f'{label} not found')
    @ns.param(id_param, f'The {label.lower()} identifier')
    class _GetResource(BaseGetResource):
        ITEMS = items
        LABEL = label

        @ns.doc(f'get_{label.lower()}')
        @ns.marshal_with(model)
        def get(self, **kwargs):
            item_id = kwargs[id_param]
            return self.get_one(item_id)

# Pets
register_list_resource(
    pet_ns,
    api,
    items=pets,
    model=models.pet_model,
    label="Pet",
    id_param="pet_id",
    shared=[
        SharedTarget(
            items=inventory,
            build=lambda pet: {
                # choose your inventory schema
                "id": pet["id"],          # inventory row id (same as pet id)
                "pet_id": pet["id"],    # what orders reference
                "inventory": 1            # quantity/stock
            },
            dedupe_key=lambda pet: ("inven_id", pet["id"]),
        )
    ],
)


# Customers
register_list_resource(
    customer_ns,
    api,
    items=customers,
    model=models.customer_model,
    label="Customer",
    id_param="customer_id"
)

# Inventory
register_list_resource(
    inventory_ns,
    api,
    items=inventory,
    model=models.inventory_model,
    label="Inventory",
    id_param="inventory_id"
)

# Vets
register_list_resource(
    vet_ns,
    api,
    items=vets,
    model=models.vet_model,
    label="Vet",
    id_param="vet_id"
)

# Vendors
register_list_resource(
    vendor_ns,
    api,
    items=vendors,
    model=models.vendor_model,
    label="Vendor",
    id_param="vendor_id"
)

# Events
register_list_resource(
    event_ns,
    api,
    items=events,
    model=models.events_model,   # adjust if your name is models.event_model
    label="Event",
    id_param="event_id"
)

# Trainers
register_list_resource(
    trainer_ns,
    api,
    items=trainers,
    model=models.trainer_model,
    label="Trainer",
    id_param="trainer_id"
)

@pet_ns.route('/<string:pet_name>')
@pet_ns.response(404, 'Pet not found')
@pet_ns.param('pet_id', 'The pet identifier by name')
class Pet(Resource):
    @pet_ns.doc('get_name')
    @pet_ns.marshal_with(models.pet_model)
    def get(self, pet_name):
        """Fetch a pet by name"""
        pet = next((pet for pet in pets if pet['name'] == pet_name), None)
        if pet is not None:
            return pet
        api.abort(404, f"Pet with name {pet_name} not found")

@store_ns.route('/order/<int:pet_name>')
@pet_ns.response(404, 'Order not found')
@pet_ns.param('pet_id', 'The pet identifier by name')
class Order(Resource):
    @pet_ns.doc('get_name')
    @pet_ns.marshal_with(models.pet_model)
    def get(self, pet_name):
        """Fetch a pet by name"""
        pet = next((pet for pet in pets if pet['name'] == pet_name), None)
        if pet is not None:
            return pet
        api.abort(404, f"Pet with name {pet_name} not found")


@pet_ns.route('/findByStatus')
@pet_ns.param('status', 'The status of the pets to find')
class PetFindByStatus(Resource):
    @pet_ns.doc('find_pets_by_status')
    @pet_ns.marshal_list_with(models.pet_model)
    def get(self):
        """Find pets by status"""
        status = request.args.get('status')
        if status not in PET_STATUS:
            api.abort(400, 'Invalid pet status {status}')
        if status:
            filtered_pets = [pet for pet in pets if pet['status'] == status]
            return filtered_pets
        
# Store Namespace
@store_ns.route('/order')
class OrderResource(Resource):
    @store_ns.doc('place_order')
    @store_ns.expect(models.order_model)
    @store_ns.marshal_with(models.order_model, code=201)
    def post(self):
        """Place a new order and reduce inventory"""
        order_data = api.payload

        inven_id = order_data.get("inven_id")
        amount_purchase = order_data.get("amount_purchase")

        # Validate payload basics
        if inven_id is None:
            api.abort(400, "inven_id is required")

        if amount_purchase is None:
            api.abort(400, "amount_purchase is required")

        # ✅ FIXED VALIDATION (reject bool explicitly)
        if type(amount_purchase) is not int or amount_purchase <= 0:
            api.abort(400, "amount_purchase must be a positive integer")

        # Find the inventory item by id
        inv_item = next((i for i in inventory if i.get("id") == inven_id), None)
        if inv_item is None:
            api.abort(404, f"Inventory item with ID {inven_id} not found")

        # Ensure enough stock
        current_stock = inv_item.get("inventory", 0)
        if current_stock < amount_purchase:
            api.abort(
                400,
                f"Not enough inventory for item ID {inven_id}. "
                f"Available: {current_stock}, requested: {amount_purchase}"
            )

        # Update inventory (decrement)
        inv_item["inventory"] = current_stock - amount_purchase

        # Create and store the order (first available id)
        order_id = next(i for i in range(1, len(orders) + 2) if i not in orders)
        order_data["id"] = order_id

        orders[order_id] = order_data

        return order_data, 201

    
@store_ns.route('/order/pet')
class OrderPetResource(Resource):
    @store_ns.doc('place_order')
    @store_ns.expect(models.order_model)
    @store_ns.marshal_with(models.order_model, code=201)
    def post(self):
        order_data = api.payload or {}
        pet_id = order_data.get("inven_id")

        pet = next((p for p in pets if p.get("id") == pet_id), None)
        if pet is None:
            api.abort(404, f"No pet found with ID {pet_id}")

        if pet.get("status") != "available":
            api.abort(400, f"Pet with ID {pet_id} is not available for order")

        # Update pet status to pending
        pet["status"] = "pending"

        # Create sequential order id (int key)
        order_id = max(orders.keys(), default=0) + 1

        # Store order in consistent shape
        created_order = {
            "id": int(order_id),
            "inven_id": int(pet_id),
            "status": "pending",
        }
        orders[order_id] = created_order

        # Keep pet synced
        pet["order_id"] = int(order_id)

        return created_order, 201




@store_ns.route('/order/<string:order_id>')
@store_ns.response(404, 'Order not found')
@store_ns.response(400, 'Invalid status')
@store_ns.param('order_id', 'The order identifier')
class OrderUpdateResource(Resource):
    @store_ns.doc('update_order')
    @store_ns.expect(models.order_update_model)
    def patch(self, order_id):
        """Update an existing order"""

        # ✅ Your orders dict uses int keys, so convert
        try:
            order_id_int = int(order_id)
        except ValueError:
            api.abort(404, "Order not found")

        if order_id_int not in orders:
            api.abort(404, "Order not found")

        update_data = request.json or {}
        new_status = update_data.get("status")

        if not new_status:
            api.abort(400, "Missing required field: status")

        if new_status not in PET_STATUS:
            api.abort(400, f"Invalid status '{new_status}'. Valid statuses are {', '.join(PET_STATUS)}")

        order = orders[order_id_int]
        pet_id = order["inven_id"]

        pet = next((p for p in pets if p["id"] == pet_id), None)
        if pet is None:
            api.abort(404, f"No pet found with ID {pet_id}")

        pet["status"] = new_status

        # ✅ Optional consistency rule:
        # If an order is set back to "available", treat it like "order canceled"
        if new_status == "available":
            pet["order_id"] = 0
            del orders[order_id_int]  # remove the order record entirely

        return {"message": "Order and pet status updated successfully"}, 200

@app.route('/health')
def health_check():
    """Health check endpoint for CI/CD monitoring"""
    return jsonify({
        "status": "healthy",
        "service": "pet-store-api",
        "version": "1.0.0"
    }), 200





# Reuse your existing SharedTarget + _generate_next_id if you want shared behavior in bulk creates
# (I'm not changing your SharedTarget implementation here)

def _existing_ids(items: list[dict], id_field: str = "id") -> set[int]:
    return {
        x.get(id_field)
        for x in items
        if isinstance(x.get(id_field), int)
    }

def _next_id(items: list[dict], id_field: str = "id") -> int:
    existing = _existing_ids(items, id_field)
    return next(i for i in range(1, len(existing) + 2) if i not in existing)

def _matches_search(item: dict, q: str, fields: list[str]) -> bool:
    ql = q.lower()
    for f in fields:
        v = item.get(f)
        if v is None:
            continue
        if ql in str(v).lower():
            return True
    return False

def register_common_extras(
    ns,
    api,
    *,
    items: list[dict],
    model,
    label: str,
    id_param: str,
    id_field: str = "id",
    searchable_fields: Optional[list[str]] = None,
    filterable_fields: Optional[list[str]] = None,
):
    """
    Adds standardized "extra" endpoints to a resource namespace.
    This is the scalability piece: one function, many resources.

    Endpoints added:
      GET    /count
      GET    /ids
      GET    /exists/<int:id>
      GET    /search?q=...
      GET    /filter?... (exact match using query params)
      POST   /bulk
      POST   /bulk/delete
      PATCH  /bulk/patch
    """
    searchable_fields = searchable_fields or []
    filterable_fields = filterable_fields or []

    # ---------- COUNT ----------
    @ns.route("/count")
    class _Count(Resource):
        @ns.doc(f"{label.lower()}_count")
        def get(self):
            return {"count": len(items)}, 200

    # ---------- IDS ----------
    @ns.route("/ids")
    class _Ids(Resource):
        @ns.doc(f"{label.lower()}_ids")
        def get(self):
            ids = [x.get(id_field) for x in items if isinstance(x.get(id_field), int)]
            return {"ids": ids}, 200

    # ---------- EXISTS ----------
    @ns.route(f"/exists/<int:{id_param}>")
    class _Exists(Resource):
        @ns.doc(f"{label.lower()}_exists")
        def get(self, **kwargs):
            item_id = kwargs[id_param]
            exists = any(x.get(id_field) == item_id for x in items)
            return {"exists": exists, id_field: item_id}, 200

    # ---------- SEARCH ----------
    @ns.route("/search")
    class _Search(Resource):
        @ns.doc(f"{label.lower()}_search")
        def get(self):
            q = (request.args.get("q") or "").strip()
            if not q:
                api.abort(400, "Missing required query param: q")
            if not searchable_fields:
                api.abort(400, f"{label} search is not configured (no searchable_fields)")
            results = [x for x in items if _matches_search(x, q, searchable_fields)]
            return results, 200

    # ---------- FILTER (exact match from querystring) ----------
    @ns.route("/filter")
    class _Filter(Resource):
        @ns.doc(f"{label.lower()}_filter")
        def get(self):
            if not filterable_fields:
                api.abort(400, f"{label} filter is not configured (no filterable_fields)")

            params = dict(request.args)
            allowed = {k: v for k, v in params.items() if k in filterable_fields}
            if not allowed:
                api.abort(400, f"Provide at least one filter param from: {', '.join(filterable_fields)}")

            def ok(item: dict) -> bool:
                for k, v in allowed.items():
                    if str(item.get(k)) != str(v):
                        return False
                return True

            return [x for x in items if ok(x)], 200

    # ---------- BULK CREATE ----------
    @ns.route("/bulk")
    class _BulkCreate(Resource):
        @ns.doc(f"{label.lower()}_bulk_create")
        @ns.expect([model])
        def post(self):
            payload = api.payload
            if not isinstance(payload, list):
                api.abort(400, "Expected a JSON array of objects")

            created = []
            existing = _existing_ids(items, id_field)

            for obj in payload:
                if not isinstance(obj, dict):
                    api.abort(400, "Each item in array must be an object")

                incoming_id = obj.get(id_field)
                if incoming_id is None:
                    obj[id_field] = next(i for i in range(1, len(existing) + 2) if i not in existing)
                else:
                    if not isinstance(incoming_id, int):
                        api.abort(400, f"{label} '{id_field}' must be an integer")
                    if incoming_id in existing:
                        api.abort(409, f"{label} with ID {incoming_id} already exists")

                existing.add(obj[id_field])
                items.append(obj)
                created.append(obj)

            return {"created": created, "count": len(created)}, 201

    # ---------- BULK DELETE ----------
    @ns.route("/bulk/delete")
    class _BulkDelete(Resource):
        @ns.doc(f"{label.lower()}_bulk_delete")
        def post(self):
            payload = api.payload or {}
            ids = payload.get("ids")
            if not isinstance(ids, list) or not all(isinstance(x, int) for x in ids):
                api.abort(400, "Body must be: { 'ids': [int, int, ...] }")

            before = len(items)
            items[:] = [x for x in items if x.get(id_field) not in set(ids)]
            deleted = before - len(items)
            return {"deleted": deleted, "requested": len(ids)}, 200

    # ---------- BULK PATCH ----------
    @ns.route("/bulk/patch")
    class _BulkPatch(Resource):
        @ns.doc(f"{label.lower()}_bulk_patch")
        def patch(self):
            """
            Body:
              {
                "ids": [1,2,3],
                "set": {"status": "available"}
              }
            """
            payload = api.payload or {}
            ids = payload.get("ids")
            changes = payload.get("set")

            if not isinstance(ids, list) or not all(isinstance(x, int) for x in ids):
                api.abort(400, "Body must include 'ids': [int, ...]")
            if not isinstance(changes, dict) or not changes:
                api.abort(400, "Body must include 'set': { ... }")

            ids_set = set(ids)
            updated = 0

            for obj in items:
                if obj.get(id_field) in ids_set:
                    obj.update(changes)
                    updated += 1

            return {"updated": updated, "requested": len(ids)}, 200


# PETS extras
register_common_extras(
    pet_ns, api,
    items=pets,
    model=models.pet_model,
    label="Pet",
    id_param="pet_id",
    searchable_fields=["name", "type", "status"],
    filterable_fields=["name", "type", "status", "order_id"],
)

# CUSTOMERS extras
register_common_extras(
    customer_ns, api,
    items=customers,
    model=models.customer_model,
    label="Customer",
    id_param="customer_id",
    searchable_fields=["name", "email", "date"],
    filterable_fields=["name", "email", "date", "purchase"],
)

# INVENTORY extras
register_common_extras(
    inventory_ns, api,
    items=inventory,
    model=models.inventory_model,
    label="Inventory",
    id_param="inventory_id",
    searchable_fields=["pet_id"],
    filterable_fields=["pet_id", "inventory"],
)

# VETS extras
register_common_extras(
    vet_ns, api,
    items=vets,
    model=models.vet_model,
    label="Vet",
    id_param="vet_id",
    searchable_fields=["name", "contact_form"],
    filterable_fields=["name", "contact_form", "contact_info"],
)

# TRAINERS extras
register_common_extras(
    trainer_ns, api,
    items=trainers,
    model=models.trainer_model,
    label="Trainer",
    id_param="trainer_id",
    searchable_fields=["name", "contact_form"],
    filterable_fields=["name", "contact_form", "contact_info"],
)

# VENDORS extras
register_common_extras(
    vendor_ns, api,
    items=vendors,
    model=models.vendor_model,
    label="Vendor",
    id_param="vendor_id",
    searchable_fields=["name", "contact_form", "point_of_contact", "contact_info"],
    filterable_fields=["name", "contact_form", "point_of_contact", "product"],
)

# EVENTS extras
register_common_extras(
    event_ns, api,
    items=events,
    model=models.events_model,
    label="Event",
    id_param="event_id",
    searchable_fields=["name", "date"],
    filterable_fields=["name", "date", "location"],
)


init_graphql(app, pets, orders, events, inventory, vendors, trainers, customers, vets)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
