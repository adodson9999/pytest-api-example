import json
from concurrent.futures import ThreadPoolExecutor, as_completed


def load_json(path: str):
    """
    Purpose:  Low-level helper that reads and parses a single JSON file from disk.

    Why we do it this way:
    - Separates file I/O + JSON parsing from higher-level logic → makes the code
      more testable (can mock this function) and reusable.
    - Uses with open() context manager → ensures file is properly closed even
      on exceptions or early returns.
    - Calls json.load() directly → simplest and most efficient way to parse JSON
      from file handle.
    - No error handling inside → lets caller (load_all_data) deal with FileNotFoundError,
      JSONDecodeError, etc. → keeps function pure and small.
    - Type-hinted path: str and implicit return type Dict → clear contract.

    Returns: the deserialized Python object (usually dict or list) from the JSON file

    Raises: FileNotFoundError, PermissionError, JSONDecodeError, etc.
    """
    with open(path, "r") as file:
        return json.load(file)


# 10 follow-up questions & short answers for load_json

# 1. Why not use json.loads() with file.read()?
#    → json.load() is more memory-efficient for large files (streams instead of reading all at once)

# 2. Should we add encoding="utf-8" to open()?
#    → Good practice — add open(path, "r", encoding="utf-8") to avoid platform-dependent defaults

# 3. Why no try/except for JSONDecodeError inside the function?
#    → Keeps helper simple; caller (load_all_data) can handle or let pytest crash with clear traceback

# 4. What if file is very large (hundreds of MB)?
#    → json.load() may consume a lot of memory — can switch to ijson for streaming if needed later

# 5. Can we add validation that result is dict/list?
#    → Possible — but overkill for helper; validation belongs in tests or higher-level code

# 6. Why not return None on failure instead of raising?
#    → Raising is better — makes bugs visible early rather than silent None propagation

# 7. Should we support YAML or TOML too in the future?
#    → Easy — rename to load_data and add format param; current name is fine for JSON-only

# 8. What if path is relative vs absolute?
#    → Works fine as long as cwd is correct; can use pathlib.Path for more robustness

# 9. Why no timeout or size limit on file read?
#    → json.load() doesn't support timeouts — add if malicious/large files become concern

# 10. Can we cache loaded files (e.g. @lru_cache)?
#     → No — data may change between test runs; better to reload fresh each time


def load_all_data():
    """
    Purpose:  Loads all predefined JSON fixture files in parallel and returns them
              as a tuple in a fixed order (pets, events, inventory, vendors, trainers,
              customers, vets).

    Why we do it this way:
    - Uses ThreadPoolExecutor → parallel loading reduces total time significantly
      when many files exist or disk I/O is slow (common on CI runners or large datasets)
    - max_workers = len(paths) → uses all available threads for maximum parallelism
      (safe because JSON parsing is CPU-bound and I/O is short)
    - future_map dictionary → maps each future back to its resource key → easy result collection
    - as_completed() → processes futures as they finish (no fixed order needed)
    - Results collected into dict then unpacked into fixed-order tuple → deterministic
      return value regardless of completion order
    - Hardcoded paths and order → matches the exact needs of tests that unpack the tuple
    - No error suppression → if any file is missing/invalid, test suite fails early with
      clear exception (good for CI visibility)
    - Returns tuple instead of dict → matches legacy/unpacked usage in tests (pets, events, …)

    Returns: tuple of loaded data in order: (pets, events, inventory, vendors, trainers, customers, vets)

    Raises: FileNotFoundError, JSONDecodeError, etc. if any file is missing or malformed
    """
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


# 10 follow-up questions & short answers for load_all_data

# 1. Why parallel loading instead of sequential for loop?
#    → Faster startup — especially noticeable when many files or slow disk/network mounts

# 2. Why max_workers = len(paths) instead of cpu_count() or a fixed number?
#    → I/O-bound task (file read) — more workers = better throughput; len(paths) is small and safe

# 3. What if one file fails — does the whole function crash?
#    → Yes — fut.result() re-raises exception → good, fails fast with clear traceback

# 4. Should we add try/except around fut.result() to continue on failure?
#    → No — silent partial load is dangerous; better to fail suite if fixture is broken

# 5. Why return tuple instead of dict like results?
#    → Matches existing test code that unpacks as pets, events, … = load_all_data()

# 6. Can we make paths configurable (e.g. via env var or pytest fixture)?
#    → Yes — useful for different environments; current hardcode is fine for monorepo

# 7. Why no validation that each loaded item is list[dict]?
#    → Belongs in tests or separate validation function — keeps loader dumb

# 8. What if files are very large — memory concern?
#    → Possible OOM — can switch to streaming (ijson) or load lazily per resource later

# 9. Should we cache the loaded data across test runs?
#    → No — data might change; pytest fixtures usually reload fixtures per session/module

# 10. Can we add logging (e.g. print("Loaded", key)) or timing?
#     → Helpful for debug — add print(f"Loaded {key} from {paths[key]}") inside loop