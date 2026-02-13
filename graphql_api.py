from ariadne import QueryType, MutationType, make_executable_schema, graphql_sync
from flask import request, jsonify

# Data stores
pets_data = []
orders_data = []

# Simpler GraphQL Playground HTML that actually works
PLAYGROUND_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>GraphQL Playground</title>
    <style>
        body {
            height: 100vh;
            margin: 0;
            font-family: Arial, sans-serif;
            background-color: #1a1a1a;
            color: #fff;
        }
        #container {
            display: flex;
            height: 100vh;
        }
        #query-panel {
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 20px;
            background-color: #1e1e1e;
        }
        #response-panel {
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 20px;
            background-color: #252525;
        }
        textarea {
            flex: 1;
            background-color: #2d2d2d;
            color: #d4d4d4;
            border: 1px solid #3e3e3e;
            padding: 10px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            resize: none;
        }
        button {
            margin-top: 10px;
            padding: 10px 20px;
            background-color: #e10098;
            color: white;
            border: none;
            cursor: pointer;
            font-size: 16px;
            border-radius: 4px;
        }
        button:hover {
            background-color: #c1007a;
        }
        pre {
            flex: 1;
            background-color: #2d2d2d;
            color: #d4d4d4;
            border: 1px solid #3e3e3e;
            padding: 10px;
            overflow: auto;
            font-family: 'Courier New', monospace;
            font-size: 14px;
        }
        h2 {
            margin-top: 0;
            color: #e10098;
        }
        .example {
            font-size: 12px;
            color: #888;
            margin-top: 10px;
        }
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
    orderId
  }
}</textarea>
            <button onclick="executeQuery()">Execute Query</button>
            <div class="example">
                <strong>Example Mutation:</strong><br>
                mutation {<br>
                &nbsp;&nbsp;createPet(name: "Buddy", type: "dog", status: "available") {<br>
                &nbsp;&nbsp;&nbsp;&nbsp;id name type status<br>
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
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ query: query })
                });
                
                const result = await response.json();
                responseElement.textContent = JSON.stringify(result, null, 2);
            } catch (error) {
                responseElement.textContent = 'Error: ' + error.message;
            }
        }
        
        // Allow Ctrl+Enter to execute
        document.getElementById('query').addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                executeQuery();
            }
        });
    </script>
</body>
</html>
"""

# Define GraphQL schema matching your actual model
type_defs = """
    type Pet {
        id: Int!
        name: String!
        type: String!
        status: String
        orderId: Int
    }
    
    type Order {
        id: Int!
        petId: Int!
        quantity: Int!
        shipDate: String
        status: String!
        complete: Boolean
    }
    
    type Query {
        pet(id: Int!): Pet
        pets(status: String, type: String): [Pet!]!
        order(id: Int!): Order
        orders: [Order!]!
    }
    
    type Mutation {
        createPet(name: String!, type: String!, status: String): Pet!
        updatePet(id: Int!, name: String, type: String, status: String): Pet
        deletePet(id: Int!): DeleteResult!
        createOrder(petId: Int!, quantity: Int!, status: String): Order!
    }
    
    type DeleteResult {
        success: Boolean!
    }
"""

# Initialize resolvers
query = QueryType()
mutation = MutationType()

# Query resolvers
@query.field("pet")
def resolve_pet(_, info, id):
    pet = next((pet for pet in pets_data if pet.get("id") == id), None)
    if pet:
        # Map order_id to orderId for GraphQL response
        return {
            **pet,
            "orderId": pet.get("order_id", 0)
        }
    return None

@query.field("pets")
def resolve_pets(_, info, status=None, type=None):
    filtered_pets = pets_data
    
    if status:
        filtered_pets = [pet for pet in filtered_pets if pet.get("status") == status]
    if type:
        filtered_pets = [pet for pet in filtered_pets if pet.get("type") == type]
    
    # Map order_id to orderId for GraphQL response
    return [
        {
            **pet,
            "orderId": pet.get("order_id", 0)
        }
        for pet in filtered_pets
    ]

@query.field("order")
def resolve_order(_, info, id):
    order = next((order for order in orders_data if order.get("id") == id), None)
    if order:
        # Map pet_id to petId for GraphQL response
        return {
            **order,
            "petId": order.get("pet_id") or order.get("petId")
        }
    return None

@query.field("orders")
def resolve_orders(_, info):
    # Map pet_id to petId for GraphQL response
    return [
        {
            **order,
            "petId": order.get("pet_id") or order.get("petId")
        }
        for order in orders_data
    ]

# Mutation resolvers
@mutation.field("createPet")
def resolve_create_pet(_, info, name, type, status="available"):
    new_id = max([p.get("id", 0) for p in pets_data], default=0) + 1
    new_pet = {
        "id": new_id,
        "name": name,
        "type": type,
        "status": status,
        "order_id": 0
    }
    pets_data.append(new_pet)
    
    # Return with orderId mapped for GraphQL
    return {
        **new_pet,
        "orderId": new_pet.get("order_id", 0)
    }

@mutation.field("updatePet")
def resolve_update_pet(_, info, id, name=None, type=None, status=None):
    pet = next((p for p in pets_data if p.get("id") == id), None)
    if not pet:
        return None
    
    if name is not None:
        pet["name"] = name
    if type is not None:
        pet["type"] = type
    if status is not None:
        pet["status"] = status
    
    # Return with orderId mapped for GraphQL
    return {
        **pet,
        "orderId": pet.get("order_id", 0)
    }

@mutation.field("deletePet")
def resolve_delete_pet(_, info, id):
    global pets_data
    initial_length = len(pets_data)
    pets_data = [p for p in pets_data if p.get("id") != id]
    return {"success": len(pets_data) < initial_length}

@mutation.field("createOrder")
def resolve_create_order(_, info, petId, quantity, status="placed"):
    new_id = max([o.get("id", 0) for o in orders_data], default=0) + 1
    new_order = {
        "id": new_id,
        "pet_id": petId,
        "quantity": quantity,
        "status": status,
        "complete": False
    }
    orders_data.append(new_order)
    
    # Return with petId mapped for GraphQL
    return {
        **new_order,
        "petId": new_order.get("pet_id")
    }

# Create executable schema
schema = make_executable_schema(type_defs, query, mutation)

def init_graphql(app, pets_store, orders_store):
    """Initialize GraphQL with the Flask app and data stores"""
    global pets_data, orders_data
    pets_data = pets_store
    orders_data = orders_store
    
    @app.route("/graphql", methods=["GET"])
    def graphql_playground():
        """Serve GraphQL Playground"""
        return PLAYGROUND_HTML, 200
    
    @app.route("/graphql", methods=["POST"])
    def graphql_server():
        """Handle GraphQL requests"""
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        success, result = graphql_sync(
            schema,
            data,
            context_value=request,
            debug=app.debug
        )
        status_code = 200 if success else 400
        return jsonify(result), status_code