import json
from concurrent.futures import ThreadPoolExecutor, as_completed

def load_json(path: str):
    with open(path, "r") as file:
        return json.load(file)

def load_all_data():
    paths = {
        "pets": "data/pet.json",
        "events": "data/events.json",
        "inventory": "data/inventory.json",
        "vendors": "data/vendors.json",
        "trainers": "data/trainers.json",
        "customers": "data/customers.json",
        "vets": "data/vet.json"
    }

    results = {}
    with ThreadPoolExecutor(max_workers=len(paths)) as executor:
        future_map = {executor.submit(load_json, p): key for key, p in paths.items()}

        for fut in as_completed(future_map):
            key = future_map[fut]
            results[key] = fut.result()  # raises if file missing / invalid JSON

    return (
        results["pets"],
        results["events"],
        results["inventory"],
        results["vendors"],
        results["trainers"],
        results["customers"], 
        results["vets"]
    )