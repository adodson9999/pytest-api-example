import pytest
import requests
from typing import Dict, Any
import json

class GraphQLClient:
    """Client for making GraphQL requests"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.endpoint = f"{base_url}/graphql"
    
    def execute(self, query: str, variables: Dict[str, Any] = None) -> Dict:
        """Execute a GraphQL query"""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        headers = {'Content-Type': 'application/json'}
        
        print(f"\n=== GraphQL Request ===")
        print(f"URL: {self.endpoint}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(self.endpoint, json=payload, headers=headers)
        
        print(f"\n=== GraphQL Response ===")
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Raw Response Text: {response.text[:500]}")  # First 500 chars
        
        # Better error handling
        try:
            result = response.json()
            print(f"Parsed JSON: {json.dumps(result, indent=2)}")
            return result
        except requests.exceptions.JSONDecodeError as e:
            print(f"\n!!! JSON Decode Error !!!")
            print(f"Error: {e}")
            print(f"Full Response Text: {response.text}")
            raise

@pytest.fixture(scope="module")
def graphql_client():
    """Fixture to provide GraphQL client"""
    return GraphQLClient("http://localhost:5001")

@pytest.fixture(scope="module")
def setup_test_pet(graphql_client):
    """Fixture to create a test pet for queries"""
    mutation = """
    mutation CreatePet($name: String!, $type: String!, $status: String!) {
        createPet(name: $name, type: $type, status: $status) {
            id
            name
            type
            status
        }
    }
    """
    variables = {
        "name": "Test Dog",
        "type": "dog",
        "status": "available"
    }
    
    result = graphql_client.execute(mutation, variables)
    return result["data"]["createPet"]

class TestGraphQLPetQueries:
    """Test suite for GraphQL pet queries"""
    
    def test_create_pet_mutation_graphql(self, graphql_client):
        """Test creating a pet using GraphQL mutation"""
        mutation = """
        mutation CreatePet($name: String!, $type: String!, $status: String!) {
            createPet(name: $name, type: $type, status: $status) {
                id
                name
                type
                status
            }
        }
        """
        variables = {
            "name": "GraphQL Dog",
            "type": "dog",
            "status": "available"
        }
        
        result = graphql_client.execute(mutation, variables)
        
        # Assert no errors
        assert "errors" not in result, f"GraphQL errors: {result.get('errors')}"
        assert "data" in result
        assert result["data"]["createPet"]["name"] == "GraphQL Dog"
        assert result["data"]["createPet"]["id"] is not None
        assert result["data"]["createPet"]["type"] == "dog"
        assert result["data"]["createPet"]["status"] == "available"
    
    def test_get_pet_by_id_graphql(self, graphql_client, setup_test_pet):
        """Test retrieving a pet by ID using GraphQL"""
        pet_id = setup_test_pet["id"]
        
        query = """
        query GetPet($petId: Int!) {
            pet(id: $petId) {
                id
                name
                type
                status
            }
        }
        """
        variables = {"petId": pet_id}
        
        result = graphql_client.execute(query, variables)
        
        # Assert no errors
        assert "errors" not in result, f"GraphQL errors: {result.get('errors')}"
        assert "data" in result
        assert result["data"]["pet"]["id"] == pet_id
        assert result["data"]["pet"]["name"] is not None
    
    def test_list_pets_graphql(self, graphql_client, setup_test_pet):
        """Test listing all pets using GraphQL"""
        query = """
        query ListPets {
            pets {
                id
                name
                status
                type
            }
        }
        """
        
        result = graphql_client.execute(query)
        
        assert "errors" not in result, f"GraphQL errors: {result.get('errors')}"
        assert "data" in result
        assert isinstance(result["data"]["pets"], list)
        assert len(result["data"]["pets"]) > 0
        
        # Verify structure of first pet
        first_pet = result["data"]["pets"][0]
        assert "id" in first_pet
        assert "name" in first_pet
        assert "status" in first_pet