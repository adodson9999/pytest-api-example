import json
from typing import Any, Dict, Optional

import pytest
import requests


# ----------------------------
# GraphQL client
# ----------------------------
class GraphQLClient:
    """Client for making GraphQL requests"""

    def __init__(self, base_url: str, *, debug: bool = False):
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/graphql"
        self.debug = debug

    def execute(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        headers = {"Content-Type": "application/json"}
        resp = requests.post(self.endpoint, json=payload, headers=headers)

        # Parse JSON with better error message
        try:
            result = resp.json()
        except requests.exceptions.JSONDecodeError as e:
            raise AssertionError(
                f"GraphQL response was not JSON. status={resp.status_code} body={resp.text[:1000]}"
            ) from e

        if self.debug:
            print("\n=== GraphQL Request ===")
            print(f"URL: {self.endpoint}")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print("\n=== GraphQL Response ===")
            print(f"Status Code: {resp.status_code}")
            print(f"Raw Response Text: {resp.text[:1000]}")
            print(f"Parsed JSON: {json.dumps(result, indent=2)}")

        return result


# ----------------------------
# Fixtures
# ----------------------------
@pytest.fixture(scope="session")
def graphql_client():
    # set debug=True temporarily if you want prints
    return GraphQLClient("http://localhost:5001", debug=False)


@pytest.fixture(scope="session")
def gql_schema_fields(graphql_client):
    """Introspect schema once so tests can skip gracefully if fields aren't present."""
    q = """
    query {
      __type(name: "Query") { fields { name } }
      __schema {
        mutationType { fields { name } }
      }
    }
    """
    res = graphql_client.execute(q)
    assert "errors" not in res, f"Schema introspection failed: {res.get('errors')}"
    query_fields = {f["name"] for f in res["data"]["__type"]["fields"]}
    mutation_fields = {f["name"] for f in res["data"]["__schema"]["mutationType"]["fields"]}
    return {"query": query_fields, "mutation": mutation_fields}


def _assert_no_gql_errors(result: Dict[str, Any]):
    assert "errors" not in result, f"GraphQL errors: {result.get('errors')}"
    assert "data" in result, f"Missing data in response: {result}"


def _require_fields(gql_schema_fields, *, query: set[str] = None, mutation: set[str] = None):
    missing = []
    if query:
        for f in query:
            if f not in gql_schema_fields["query"]:
                missing.append(f"Query.{f}")
    if mutation:
        for f in mutation:
            if f not in gql_schema_fields["mutation"]:
                missing.append(f"Mutation.{f}")
    if missing:
        pytest.skip(f"Schema missing fields: {', '.join(missing)}")


# ----------------------------
# Helpers to create data
# ----------------------------
def _create_pet(graphql_client, *, name: str, type_: str = "dog", status: str = "available") -> Dict[str, Any]:
    m = """
    mutation CreatePet($name: String!, $type: String!, $status: String) {
      createPet(name: $name, type: $type, status: $status) {
        id
        name
        type
        status
        order_id
      }
    }
    """
    res = graphql_client.execute(m, {"name": name, "type": type_, "status": status})
    _assert_no_gql_errors(res)
    return res["data"]["createPet"]


def _get_pet(graphql_client, pet_id: int) -> Optional[Dict[str, Any]]:
    q = """
    query GetPet($id: Int!) {
      pet(id: $id) { id name type status order_id }
    }
    """
    res = graphql_client.execute(q, {"id": pet_id})
    _assert_no_gql_errors(res)
    return res["data"]["pet"]


def _list_pets(graphql_client, *, status: Optional[str] = None, type_: Optional[str] = None) -> list[Dict[str, Any]]:
    q = """
    query ListPets($status: String, $type: String) {
      pets(status: $status, type: $type) { id name type status order_id }
    }
    """
    vars_ = {"status": status, "type": type_}
    res = graphql_client.execute(q, vars_)
    _assert_no_gql_errors(res)
    return res["data"]["pets"]


def _get_inventory_by_pet(graphql_client, pet_id: int) -> list[Dict[str, Any]]:
    q = """
    query Inv($pet_id: Int) {
      inventory(pet_id: $pet_id) { id inventory pet_id }
    }
    """
    res = graphql_client.execute(q, {"pet_id": pet_id})
    _assert_no_gql_errors(res)
    return res["data"]["inventory"]


# ----------------------------
# 100 tests (parametrized)
# ----------------------------
class TestGraphQL100:
    """
    100 test cases via parametrization.
    These cover:
      - createPet + get pet + list pets
      - (if present) shared behavior: inventory row created with inventory=1 and pet_id=pet.id
    """

    @pytest.mark.parametrize("i", range(1, 101))
    def test_001_to_100_create_pet_get_pet_list_and_shared_inventory(
        self,
        graphql_client,
        gql_schema_fields,
        i,
    ):
        # Require core pet fields
        _require_fields(gql_schema_fields, query={"pet", "pets"}, mutation={"createPet"})

        # Create unique pet
        pet = _create_pet(graphql_client, name=f"GraphQL Dog {i}", type_="dog", status="available")
        assert isinstance(pet["id"], int)
        assert pet["name"] == f"GraphQL Dog {i}"
        assert pet["type"] == "dog"
        assert pet["status"] == "available"

        # Fetch by id
        fetched = _get_pet(graphql_client, pet["id"])
        assert fetched is not None
        assert fetched["id"] == pet["id"]
        assert fetched["name"] == pet["name"]
        assert fetched["type"] == pet["type"]
        assert fetched["status"] == pet["status"]

        # List pets includes it (not guaranteed ordering, so search)
        all_pets = _list_pets(graphql_client)
        ids = {p["id"] for p in all_pets}
        assert pet["id"] in ids

        # Optional shared behavior: inventory created on createPet
        # If your schema doesn't have inventory yet, skip this part.
        if "inventory" in gql_schema_fields["query"]:
            inv_rows = _get_inventory_by_pet(graphql_client, pet["id"])
            assert len(inv_rows) == 1, f"Expected exactly 1 inventory row for pet_id={pet['id']}, got {inv_rows}"
            assert inv_rows[0]["pet_id"] == pet["id"]
            assert inv_rows[0]["inventory"] == 1
