#!/usr/bin/env python3
"""
Export the running GraphQL schema (via introspection) into SDL and write it to:
  graphql_contract/schema.graphql

Usage:
  # Start your server first (example):
  # python app.py

  python scripts/export_graphql_schema.py

Optional env vars:
  GRAPHQL_URL=http://127.0.0.1:5001/graphql
  OUTPUT_PATH=graphql_contract/schema.graphql
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from graphql import build_client_schema, get_introspection_query, print_schema


def fetch_introspection(graphql_url: str) -> dict:
    """Fetch GraphQL introspection result JSON from a running server."""
    query = get_introspection_query(descriptions=True)
    payload = {"query": query}

    resp = requests.post(graphql_url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
    resp.raise_for_status()

    data = resp.json()

    # Standard GraphQL response shape: {"data": {...}} or {"errors": [...]}
    if "errors" in data and data["errors"]:
        raise RuntimeError(f"GraphQL introspection returned errors: {data['errors']}")

    if "data" not in data or "__schema" not in data["data"]:
        raise RuntimeError(
            "Introspection response missing expected fields. "
            f"Got keys: {list(data.keys())}. Full response: {data}"
        )

    return data["data"]


def introspection_to_sdl(introspection_data: dict) -> str:
    """Convert introspection JSON (data portion) -> SDL string."""
    schema = build_client_schema(introspection_data)
    sdl = print_schema(schema)
    return sdl.strip() + "\n"


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    graphql_url = os.getenv("GRAPHQL_URL", "http://127.0.0.1:5001/graphql")
    output_path = Path(os.getenv("OUTPUT_PATH", "graphql_contract/schema.graphql"))

    try:
        introspection_data = fetch_introspection(graphql_url)
        sdl = introspection_to_sdl(introspection_data)
        write_file(output_path, sdl)

        print(f"✅ Exported schema SDL from {graphql_url}")
        print(f"✅ Wrote: {output_path}")
        return 0

    except requests.RequestException as e:
        print(f"❌ HTTP error calling GraphQL endpoint at {graphql_url}: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"❌ Failed to export schema: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())




"""
GraphQL Schema Export Tool (Middleware Contract Snapshot)

Why this exists:

STRATA acts as a GraphQL middleware layer and serves as an API/data highway
between multiple backend domains and consuming applications.

In a middleware platform, the GraphQL schema is a public contract.
If it changes unexpectedly, downstream applications or QA teams can break.

This script:
1. Calls the running GraphQL server via introspection.
2. Converts the schema to SDL.
3. Writes a committed snapshot (schema.graphql).

The committed SDL file acts as a contract snapshot.
CI will fail if the schema changes without updating this snapshot.

This prevents silent breaking changes and enforces intentional contract evolution.

— Demonstrates:
  • Deep understanding of GraphQL middleware contracts
  • Production API governance mindset
  • Senior-level SDET tooling design
"""



