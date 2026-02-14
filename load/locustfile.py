import os
import time
import uuid
from typing import Any, Dict, Optional

from locust import HttpUser, task, between


GRAPHQL_PATH = os.getenv("GRAPHQL_PATH", "/graphql")
RUN_ID = os.getenv("LOAD_RUN_ID", str(uuid.uuid4())[:8])  # used in pet names for later filtering
PET_TYPE = os.getenv("LOAD_PET_TYPE", "dog")
PET_STATUS = os.getenv("LOAD_PET_STATUS", "available")


def gql_payload(query: str, variables: Optional[Dict[str, Any]] = None, operation_name: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    if operation_name is not None:
        payload["operationName"] = operation_name
    return payload


class GraphQLLoadUser(HttpUser):
    """
    Locust user simulating STRATA-like GraphQL middleware traffic.
    Mix:
      - read queries (introspection / pets list / inventory by pet_id)
      - write mutations (createPet) to simulate concurrent state changes
    """
    wait_time = between(0.1, 0.6)

    def on_start(self):
        # optional: warm up / verify endpoint
        self._introspect()

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Request-Id": str(uuid.uuid4()),
        }

    def _post_graphql(self, payload: Dict[str, Any], name: str):
        """
        Wraps GraphQL POST and marks failure if:
          - non-200
          - JSON parse fails
          - response contains top-level "errors"
        """
        with self.client.post(
            GRAPHQL_PATH,
            json=payload,
            headers=self._headers(),
            name=name,
            catch_response=True,
        ) as resp:
            if resp.status_code not in (200, 400):
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
                return None

            try:
                data = resp.json()
            except Exception:
                resp.failure(f"Non-JSON response: {resp.text[:200]}")
                return None

            # GraphQL errors should count as failures for load testing
            if isinstance(data, dict) and data.get("errors"):
                resp.failure(f"GraphQL errors: {str(data['errors'])[:200]}")
                return None

            resp.success()
            return data

    # ----------------------------
    # Queries
    # ----------------------------
    def _introspect(self):
        q = 'query IntrospectMe { __type(name: "Query") { fields { name } } }'
        payload = gql_payload(q, operation_name="IntrospectMe")
        return self._post_graphql(payload, name="gql:Introspection")

    @task(35)
    def query_pets(self):
        q = """
        query ListPets {
          pets {
            id
            name
            type
            status
            order_id
          }
        }
        """
        payload = gql_payload(q, operation_name="ListPets")
        self._post_graphql(payload, name="gql:PetsList")

    @task(20)
    def query_inventory_for_recent_pet(self):
        """
        Query inventory for a pet_id we can discover by scanning pets
        and selecting one with our load prefix.
        This avoids relying on shared state between workers.
        """
        # 1) get pets
        q1 = """
        query ListPetsForInv {
          pets {
            id
            name
          }
        }
        """
        data = self._post_graphql(gql_payload(q1, operation_name="ListPetsForInv"), name="gql:PetsListForInv")
        if not data:
            return

        pets = (data.get("data") or {}).get("pets") or []
        # find a load-created pet if possible
        target = next((p for p in pets if isinstance(p, dict) and str(p.get("name", "")).startswith(f"load_{RUN_ID}_")), None)
        if not target:
            # fallback: any pet
            target = next((p for p in pets if isinstance(p, dict) and isinstance(p.get("id"), int)), None)
        if not target:
            return

        pet_id = target.get("id")
        if not isinstance(pet_id, int):
            return

        q2 = """
        query InventoryByPet($pet_id: Int) {
          inventory(pet_id: $pet_id) {
            id
            inventory
            pet_id
          }
        }
        """
        payload = gql_payload(q2, variables={"pet_id": pet_id}, operation_name="InventoryByPet")
        self._post_graphql(payload, name="gql:InventoryByPet")

    @task(15)
    def query_introspection(self):
        self._introspect()

    # ----------------------------
    # Mutations (concurrent writes)
    # ----------------------------
    @task(30)
    def mutation_create_pet(self):
        """
        Concurrent mutation that should also upsert inventory=1 for the new pet_id
        via your shared behavior (_ensure_inventory_for_pet).
        """
        name = f"load_{RUN_ID}_{self.environment.runner.user_count}_{uuid.uuid4().hex[:8]}"
        m = """
        mutation CreatePetOp($name: String!, $type: String!, $status: String) {
          createPet(name: $name, type: $type, status: $status) {
            id
            name
            type
            status
            order_id
          }
        }
        """
        variables = {"name": name, "type": PET_TYPE, "status": PET_STATUS}
        self._post_graphql(gql_payload(m, variables=variables, operation_name="CreatePetOp"), name="gql:CreatePet")




"""How to run

python3 -m locust -f load/locustfile.py \
  --headless \
  -u 25 \
  -r 5 \
  --run-time 30s \
  --host http://127.0.0.1:5001 \
  --csv load/locust_results

"""


"""
Locust load profile for STRATA-style GraphQL middleware traffic.

Why this exists (STRATA context):
- STRATA is an "API/data highway" where GraphQL sits in the middle of many callers.
- Correctness alone isn't enough; middleware must be resilient under concurrency.
- This load test generates a realistic mix of reads + writes against /graphql.

What this test validates:
- Performance under sustained traffic (read-heavy + mutation traffic).
- Error rate stays low (GraphQL "errors" count as failures here).
- Concurrency behavior: multiple users createPet concurrently (write amplification).

Notes:
- We send X-Request-Id to align with observability correlation practices.
"""
