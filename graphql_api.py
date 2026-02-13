from ariadne import QueryType, MutationType, make_executable_schema, graphql_sync
from flask import request, jsonify
import logging
import time
import uuid
import os
import logging
from logging.handlers import RotatingFileHandler

# ----------------------------
# In-memory data stores (wired via init_graphql)
# ----------------------------
pets_data = []
orders_data = []
customers_data = []
inventory_data = []
vets_data = []
trainers_data = []
vendors_data = []
events_data = []

# ----------------------------
# GraphQL Playground (GET /graphql)
# ----------------------------
PLAYGROUND_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>GraphQL Playground</title>
    <style>
        body { height: 100vh; margin: 0; font-family: Arial, sans-serif; background-color: #1a1a1a; color: #fff; }
        #container { display: flex; height: 100vh; }
        #query-panel { flex: 1; display: flex; flex-direction: column; padding: 20px; background-color: #1e1e1e; }
        #response-panel { flex: 1; display: flex; flex-direction: column; padding: 20px; background-color: #252525; }
        textarea { flex: 1; background-color: #2d2d2d; color: #d4d4d4; border: 1px solid #3e3e3e; padding: 10px;
                   font-family: 'Courier New', monospace; font-size: 14px; resize: none; }
        button { margin-top: 10px; padding: 10px 20px; background-color: #e10098; color: white; border: none; cursor: pointer;
                 font-size: 16px; border-radius: 4px; }
        button:hover { background-color: #c1007a; }
        pre { flex: 1; background-color: #2d2d2d; color: #d4d4d4; border: 1px solid #3e3e3e; padding: 10px; overflow: auto;
              font-family: 'Courier New', monospace; font-size: 14px; }
        h2 { margin-top: 0; color: #e10098; }
        .example { font-size: 12px; color: #888; margin-top: 10px; }
    </style>
</head>
<body>
    <div id="container">
        <div id="query-panel">
            <h2>Query</h2>
            <textarea id="query" placeholder="Enter your GraphQL query here...">query {
  pets {
    id
    name
    type
    status
    order_id
  }
}</textarea>
            <button onclick="executeQuery()">Execute Query</button>
            <div class="example">
                <strong>Example Mutation:</strong><br>
                mutation {<br>
                &nbsp;&nbsp;createPet(name: "Buddy", type: "dog", status: "available") {<br>
                &nbsp;&nbsp;&nbsp;&nbsp;id name type status order_id<br>
                &nbsp;&nbsp;}<br>
                }<br><br>
                <strong>Example Order:</strong><br>
                mutation {<br>
                &nbsp;&nbsp;createOrder(inven_id: 1, amount_purchase: 1, status: "placed") {<br>
                &nbsp;&nbsp;&nbsp;&nbsp;id inven_id amount_purchase status<br>
                &nbsp;&nbsp;}<br>
                }
            </div>
        </div>
        <div id="response-panel">
            <h2>Response</h2>
            <pre id="response">Click "Execute Query" to see results</pre>
        </div>
    </div>

    <script>
        async function executeQuery() {
            const query = document.getElementById('query').value;
            const responseElement = document.getElementById('response');
            try {
                responseElement.textContent = 'Loading...';
                const response = await fetch('/graphql', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query })
                });
                const result = await response.json();
                responseElement.textContent = JSON.stringify(result, null, 2);
            } catch (error) {
                responseElement.textContent = 'Error: ' + error.message;
            }
        }

        document.getElementById('query').addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') executeQuery();
        });
    </script>
</body>
</html>
"""

# ----------------------------
# Helpers
# ----------------------------
def _next_id(store: list[dict]) -> int:
    """1-based incremental id (max+1)."""
    return max([x.get("id", 0) for x in store], default=0) + 1

def _find_by_id(store: list[dict], item_id: int) -> dict | None:
    return next((x for x in store if x.get("id") == item_id), None)

def _delete_by_id(store: list[dict], item_id: int) -> bool:
    before = len(store)
    store[:] = [x for x in store if x.get("id") != item_id]
    return len(store) < before

def _ensure_inventory_for_pet(pet_id: int):
    """
    Shared behavior:
    when a new Pet is created, also upsert inventory record with inventory=1 and pet_id=<pet_id>.
    (If one already exists for the pet_id, do nothing.)
    """
    existing = next((i for i in inventory_data if i.get("pet_id") == pet_id), None)
    if existing is None:
        inventory_data.append({
            "id": _next_id(inventory_data),
            "inventory": 1,
            "pet_id": pet_id
        })

# ----------------------------
# GraphQL schema (matches your RESTX model field names)
# ----------------------------
type_defs = """
    type Pet {
        id: Int!
        name: String!
        type: String!
        status: String
        order_id: Int
    }

    type Order {
        id: Int!
        inven_id: Int!
        amount_purchase: Int!
        status: String
    }

    type Customer {
        id: Int!
        name: String!
        date: String!
        purchase: Int!
        email: String!
    }

    type Inventory {
        id: Int!
        inventory: Int
        pet_id: Int
    }

    type Vet {
        id: Int!
        name: String!
        contact_form: String!
        contact_info: Int!
    }

    type Trainer {
        id: Int!
        name: String!
        contact_form: String!
        contact_info: Int!
    }

    type Vendor {
        id: Int!
        name: String!
        contact_form: String!
        contact_info: String!
        point_of_contact: String!
        product: Int!
    }

    type Event {
        id: Int!
        name: String!
        date: String!
        location: Int!
    }

    type DeleteResult {
        success: Boolean!
    }

    type Query {
        # Pets
        pet(id: Int!): Pet
        pets(status: String, type: String): [Pet!]!

        # Orders
        order(id: Int!): Order
        orders(status: String): [Order!]!

        # Customers
        customer(id: Int!): Customer
        customers: [Customer!]!

        # Inventory
        inventoryItem(id: Int!): Inventory
        inventory(pet_id: Int): [Inventory!]!

        # Vets
        vet(id: Int!): Vet
        vets: [Vet!]!

        # Trainers
        trainer(id: Int!): Trainer
        trainers: [Trainer!]!

        # Vendors
        vendor(id: Int!): Vendor
        vendors: [Vendor!]!

        # Events
        event(id: Int!): Event
        events: [Event!]!
    }

    type Mutation {
        # Pets
        createPet(name: String!, type: String!, status: String): Pet!
        updatePet(id: Int!, name: String, type: String, status: String, order_id: Int): Pet
        deletePet(id: Int!): DeleteResult!

        # Orders
        createOrder(inven_id: Int!, amount_purchase: Int!, status: String): Order!
        updateOrder(id: Int!, status: String): Order
        deleteOrder(id: Int!): DeleteResult!

        # Customers
        createCustomer(name: String!, date: String!, purchase: Int!, email: String!): Customer!
        updateCustomer(id: Int!, name: String, date: String, purchase: Int, email: String): Customer
        deleteCustomer(id: Int!): DeleteResult!

        # Inventory
        createInventory(inventory: Int, pet_id: Int): Inventory!
        updateInventory(id: Int!, inventory: Int, pet_id: Int): Inventory
        deleteInventory(id: Int!): DeleteResult!

        # Vets
        createVet(name: String!, contact_form: String!, contact_info: Int!): Vet!
        updateVet(id: Int!, name: String, contact_form: String, contact_info: Int): Vet
        deleteVet(id: Int!): DeleteResult!

        # Trainers
        createTrainer(name: String!, contact_form: String!, contact_info: Int!): Trainer!
        updateTrainer(id: Int!, name: String, contact_form: String, contact_info: Int): Trainer
        deleteTrainer(id: Int!): DeleteResult!

        # Vendors
        createVendor(name: String!, contact_form: String!, contact_info: String!, point_of_contact: String!, product: Int!): Vendor!
        updateVendor(id: Int!, name: String, contact_form: String, contact_info: String, point_of_contact: String, product: Int): Vendor
        deleteVendor(id: Int!): DeleteResult!

        # Events
        createEvent(name: String!, date: String!, location: Int!): Event!
        updateEvent(id: Int!, name: String, date: String, location: Int): Event
        deleteEvent(id: Int!): DeleteResult!
    }
"""

query = QueryType()
mutation = MutationType()

# ----------------------------
# Query resolvers
# ----------------------------
@query.field("pet")
def resolve_pet(_, info, id):
    return _find_by_id(pets_data, id)

@query.field("pets")
def resolve_pets(_, info, status=None, type=None):
    items = pets_data
    if status is not None:
        items = [p for p in items if p.get("status") == status]
    if type is not None:
        items = [p for p in items if p.get("type") == type]
    return items

@query.field("order")
def resolve_order(_, info, id):
    return _find_by_id(orders_data, id)

@query.field("orders")
def resolve_orders(_, info, status=None):
    items = orders_data
    if status is not None:
        items = [o for o in items if o.get("status") == status]
    return items

@query.field("customer")
def resolve_customer(_, info, id):
    return _find_by_id(customers_data, id)

@query.field("customers")
def resolve_customers(_, info):
    return customers_data

@query.field("inventoryItem")
def resolve_inventory_item(_, info, id):
    return _find_by_id(inventory_data, id)

@query.field("inventory")
def resolve_inventory(_, info, pet_id=None):
    items = inventory_data
    if pet_id is not None:
        items = [i for i in items if i.get("pet_id") == pet_id]
    return items

@query.field("vet")
def resolve_vet(_, info, id):
    return _find_by_id(vets_data, id)

@query.field("vets")
def resolve_vets(_, info):
    return vets_data

@query.field("trainer")
def resolve_trainer(_, info, id):
    return _find_by_id(trainers_data, id)

@query.field("trainers")
def resolve_trainers(_, info):
    return trainers_data

@query.field("vendor")
def resolve_vendor(_, info, id):
    return _find_by_id(vendors_data, id)

@query.field("vendors")
def resolve_vendors(_, info):
    return vendors_data

@query.field("event")
def resolve_event(_, info, id):
    return _find_by_id(events_data, id)

@query.field("events")
def resolve_events(_, info):
    return events_data

# ----------------------------
# Mutation resolvers
# ----------------------------
@mutation.field("createPet")
def resolve_create_pet(_, info, name, type, status="available"):
    new_pet = {
        "id": _next_id(pets_data),
        "name": name,
        "type": type,
        "status": status,
        "order_id": 0,
    }
    pets_data.append(new_pet)

    # ✅ shared behavior: also update inventory with inventory=1 for this pet
    _ensure_inventory_for_pet(new_pet["id"])

    return new_pet

@mutation.field("updatePet")
def resolve_update_pet(_, info, id, name=None, type=None, status=None, order_id=None):
    pet = _find_by_id(pets_data, id)
    if not pet:
        return None
    if name is not None:
        pet["name"] = name
    if type is not None:
        pet["type"] = type
    if status is not None:
        pet["status"] = status
    if order_id is not None:
        pet["order_id"] = order_id
    return pet

@mutation.field("deletePet")
def resolve_delete_pet(_, info, id):
    return {"success": _delete_by_id(pets_data, id)}

@mutation.field("createOrder")
def resolve_create_order(_, info, inven_id, amount_purchase, status="placed"):
    new_order = {
        "id": _next_id(orders_data),
        "inven_id": inven_id,
        "amount_purchase": amount_purchase,
        "status": status,
    }
    orders_data.append(new_order)
    return new_order

@mutation.field("updateOrder")
def resolve_update_order(_, info, id, status=None):
    order = _find_by_id(orders_data, id)
    if not order:
        return None
    if status is not None:
        order["status"] = status
    return order

@mutation.field("deleteOrder")
def resolve_delete_order(_, info, id):
    return {"success": _delete_by_id(orders_data, id)}

@mutation.field("createCustomer")
def resolve_create_customer(_, info, name, date, purchase, email):
    new_customer = {
        "id": _next_id(customers_data),
        "name": name,
        "date": date,
        "purchase": purchase,
        "email": email,
    }
    customers_data.append(new_customer)
    return new_customer

@mutation.field("updateCustomer")
def resolve_update_customer(_, info, id, name=None, date=None, purchase=None, email=None):
    c = _find_by_id(customers_data, id)
    if not c:
        return None
    if name is not None:
        c["name"] = name
    if date is not None:
        c["date"] = date
    if purchase is not None:
        c["purchase"] = purchase
    if email is not None:
        c["email"] = email
    return c

@mutation.field("deleteCustomer")
def resolve_delete_customer(_, info, id):
    return {"success": _delete_by_id(customers_data, id)}

@mutation.field("createInventory")
def resolve_create_inventory(_, info, inventory=None, pet_id=None):
    new_item = {
        "id": _next_id(inventory_data),
        "inventory": inventory,
        "pet_id": pet_id,
    }
    inventory_data.append(new_item)
    return new_item

@mutation.field("updateInventory")
def resolve_update_inventory(_, info, id, inventory=None, pet_id=None):
    inv = _find_by_id(inventory_data, id)
    if not inv:
        return None
    if inventory is not None:
        inv["inventory"] = inventory
    if pet_id is not None:
        inv["pet_id"] = pet_id
    return inv

@mutation.field("deleteInventory")
def resolve_delete_inventory(_, info, id):
    return {"success": _delete_by_id(inventory_data, id)}

@mutation.field("createVet")
def resolve_create_vet(_, info, name, contact_form, contact_info):
    new_vet = {
        "id": _next_id(vets_data),
        "name": name,
        "contact_form": contact_form,
        "contact_info": contact_info,
    }
    vets_data.append(new_vet)
    return new_vet

@mutation.field("updateVet")
def resolve_update_vet(_, info, id, name=None, contact_form=None, contact_info=None):
    v = _find_by_id(vets_data, id)
    if not v:
        return None
    if name is not None:
        v["name"] = name
    if contact_form is not None:
        v["contact_form"] = contact_form
    if contact_info is not None:
        v["contact_info"] = contact_info
    return v

@mutation.field("deleteVet")
def resolve_delete_vet(_, info, id):
    return {"success": _delete_by_id(vets_data, id)}

@mutation.field("createTrainer")
def resolve_create_trainer(_, info, name, contact_form, contact_info):
    new_trainer = {
        "id": _next_id(trainers_data),
        "name": name,
        "contact_form": contact_form,
        "contact_info": contact_info,
    }
    trainers_data.append(new_trainer)
    return new_trainer

@mutation.field("updateTrainer")
def resolve_update_trainer(_, info, id, name=None, contact_form=None, contact_info=None):
    t = _find_by_id(trainers_data, id)
    if not t:
        return None
    if name is not None:
        t["name"] = name
    if contact_form is not None:
        t["contact_form"] = contact_form
    if contact_info is not None:
        t["contact_info"] = contact_info
    return t

@mutation.field("deleteTrainer")
def resolve_delete_trainer(_, info, id):
    return {"success": _delete_by_id(trainers_data, id)}

@mutation.field("createVendor")
def resolve_create_vendor(_, info, name, contact_form, contact_info, point_of_contact, product):
    new_vendor = {
        "id": _next_id(vendors_data),
        "name": name,
        "contact_form": contact_form,
        "contact_info": contact_info,
        "point_of_contact": point_of_contact,
        "product": product,
    }
    vendors_data.append(new_vendor)
    return new_vendor

@mutation.field("updateVendor")
def resolve_update_vendor(
    _, info, id, name=None, contact_form=None, contact_info=None, point_of_contact=None, product=None
):
    v = _find_by_id(vendors_data, id)
    if not v:
        return None
    if name is not None:
        v["name"] = name
    if contact_form is not None:
        v["contact_form"] = contact_form
    if contact_info is not None:
        v["contact_info"] = contact_info
    if point_of_contact is not None:
        v["point_of_contact"] = point_of_contact
    if product is not None:
        v["product"] = product
    return v

@mutation.field("deleteVendor")
def resolve_delete_vendor(_, info, id):
    return {"success": _delete_by_id(vendors_data, id)}

@mutation.field("createEvent")
def resolve_create_event(_, info, name, date, location):
    new_event = {
        "id": _next_id(events_data),
        "name": name,
        "date": date,
        "location": location,
    }
    events_data.append(new_event)
    return new_event

@mutation.field("updateEvent")
def resolve_update_event(_, info, id, name=None, date=None, location=None):
    e = _find_by_id(events_data, id)
    if not e:
        return None
    if name is not None:
        e["name"] = name
    if date is not None:
        e["date"] = date
    if location is not None:
        e["location"] = location
    return e

@mutation.field("deleteEvent")
def resolve_delete_event(_, info, id):
    return {"success": _delete_by_id(events_data, id)}


def setup_graphql_logging(app):
    logger = logging.getLogger("graphql")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if app reloads
    if logger.handlers:
        return

    if os.getenv("FLASK_ENV") == "testing":
        handler = RotatingFileHandler("logs/graphql_test.log", maxBytes=2_000_000, backupCount=2)
    else:
        handler = logging.StreamHandler()

    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ----------------------------
# Executable schema
# ----------------------------
schema = make_executable_schema(type_defs, query, mutation)

# ----------------------------
# init_graphql (updated signature and wiring)
# ----------------------------

# graphql_server.py (or wherever your init_graphql lives)
# ✅ Full init_graphql with ALL observability changes:
# - request_id generation + propagation (X-Request-Id / X-Correlation-Id / uuid)
# - JSON line logging to a file during testing (and stdout in non-testing)
# - Robust log path (env override GRAPHQL_LOG_PATH; defaults to logs/graphql_test.log)
# - Ensures logs/ dir exists
# - Avoids duplicate handlers
# - Logs request summary + error summary events
# - Echoes X-Request-Id in response headers

import json
import logging
import os
import time
import uuid
from pathlib import Path
from logging.handlers import RotatingFileHandler

from flask import request, jsonify
from ariadne import graphql_sync

# assumes schema and PLAYGROUND_HTML are in scope
# from .schema import schema, PLAYGROUND_HTML


import json
import logging
import os
import time
import uuid
from pathlib import Path
from logging.handlers import RotatingFileHandler

from flask import request, jsonify
from ariadne import graphql_sync

# assumes schema + PLAYGROUND_HTML are defined in this module
# from .graphql_schema import schema, PLAYGROUND_HTML


def init_graphql(app, pets_store, orders_store, events, inventory, vendors, trainers, customers, vets):
    """
    Initialize GraphQL with the Flask app and data stores.

    ✅ Observability/Logging (STRATA-style) additions:
      - request_id correlation (X-Request-Id / X-Correlation-Id / uuid)
      - JSON-lines logging (machine-parseable)
      - request summary event:   event=graphql_request
      - error summary event:     event=graphql_error (when result.errors exists)
      - invalid request event:   event=graphql_request_invalid (no body)
      - duration_ms, operation_name, operation_type
      - response header X-Request-Id echoed back to caller

    ✅ Separate-process friendly:
      - Writes to a log file in testing mode so pytest (running in another process)
        can validate logs by reading the file.

    Environment:
      - FLASK_ENV=testing                 -> enables file logging
      - GRAPHQL_LOG_PATH=logs/graphql_test.log  -> override log file path (default shown)
    """

    # ----------------------------
    # Wire stores into module globals (your existing behavior)
    # ----------------------------
    global pets_data, orders_data, events_data, inventory_data, vendors_data, trainers_data, customers_data, vets_data
    pets_data = pets_store
    orders_data = orders_store
    events_data = events
    inventory_data = inventory
    vendors_data = vendors
    trainers_data = trainers
    customers_data = customers
    vets_data = vets

    # ----------------------------
    # Logging setup (robust + repeatable)
    #   IMPORTANT: we always clear handlers to avoid "already had handlers"
    #   which otherwise prevents file logging from being attached.
    # ----------------------------
    logger = logging.getLogger("graphql")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # don't duplicate logs through root logger

    env = (os.getenv("FLASK_ENV") or "").lower().strip()
    log_path_str = os.getenv("GRAPHQL_LOG_PATH", "logs/graphql_test.log")

    # Use CWD so both server and tests refer to the same relative path
    log_path = (Path(os.getcwd()) / log_path_str).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Clear any existing handlers to guarantee current config applies
    for h in list(logger.handlers):
        logger.removeHandler(h)

    if env == "testing":
        file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=2_000_000,
            backupCount=2,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter("%(message)s"))  # JSON lines only
        logger.addHandler(file_handler)
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(stream_handler)

    # One-time marker to prove logging is wired
    logger.info(json.dumps({
        "event": "logger_ready",
        "env": env or "unknown",
        "log_path": str(log_path) if env == "testing" else None,
    }))

    # ----------------------------
    # Helpers
    # ----------------------------
    def _get_request_id() -> str:
        return (
            request.headers.get("X-Request-Id")
            or request.headers.get("X-Correlation-Id")
            or str(uuid.uuid4())
        )

    def _infer_operation_type(query_text: str | None) -> str:
        if not query_text:
            return "unknown"
        q = query_text.lstrip()
        if q.startswith("mutation"):
            return "mutation"
        if q.startswith("query"):
            return "query"
        # anonymous query often omits "query" keyword
        return "query"

    # ----------------------------
    # Routes
    # ----------------------------
    @app.route("/graphql", methods=["GET"])
    def graphql_playground():
        return PLAYGROUND_HTML, 200

    @app.route("/graphql", methods=["POST"])
    def graphql_server():
        started = time.perf_counter()
        request_id = _get_request_id()

        data = request.get_json(silent=True)
        if not data:
            logger.warning(json.dumps({
                "event": "graphql_request_invalid",
                "request_id": request_id,
                "reason": "no_data",
                "path": request.path,
                "method": request.method,
            }))
            resp = jsonify({"error": "No data provided"})
            resp.headers["X-Request-Id"] = request_id
            return resp, 400

        query_text = data.get("query")
        operation_name = data.get("operationName") or "anonymous"
        operation_type = _infer_operation_type(query_text)

        success, result = graphql_sync(
            schema,
            data,
            context_value={"request": request, "request_id": request_id},
            debug=app.debug
        )

        duration_ms = int((time.perf_counter() - started) * 1000)

        # Always log request summary (even if it errors)
        logger.info(json.dumps({
            "event": "graphql_request",
            "request_id": request_id,
            "operation_name": operation_name,
            "operation_type": operation_type,
            "duration_ms": duration_ms,
            "status": "success" if success else "failed",
        }))

        # If GraphQL returned errors, log a structured error event too
        errors = (result or {}).get("errors") or []
        if errors:
            messages = []
            for e in errors:
                if isinstance(e, dict):
                    messages.append(e.get("message"))
                else:
                    messages.append(str(e))

            logger.error(json.dumps({
                "event": "graphql_error",
                "request_id": request_id,
                "operation_name": operation_name,
                "operation_type": operation_type,
                "duration_ms": duration_ms,
                "errors": [m for m in messages if m],
            }))

        resp = jsonify(result)
        resp.headers["X-Request-Id"] = request_id
        return resp, (200 if success else 400)
