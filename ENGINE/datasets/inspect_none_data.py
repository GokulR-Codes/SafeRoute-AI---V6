import argparse
import sys
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

try:
    from ENGINE.config import MONGO_URI
except Exception:
    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from ENGINE.config import MONGO_URI

DB_NAME = "SAFEROUTE_AI"
COLLECTION_NAME = "RiskDataBengaluru"
DISPLAY_FIELDS = ["zone", "road_name", "lat", "lng", "road_risk_score"]


def connect(uri: str, timeout_ms: int = 5000) -> MongoClient:
    if not uri or "your_" in uri or "example" in uri.lower():
        print(
            "ERROR: MONGO_URI is still a placeholder.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Replace the value with your real MongoDB connection string\n"
        )
        sys.exit(1)

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
        client.admin.command("ping")
        return client
    except (ConnectionFailure, ServerSelectionTimeoutError) as exc:
        print(f"ERROR: Could not connect to MongoDB: {exc}")
        sys.exit(1)


def inspect_field(collection, field: str, sample: int) -> None:
    query = {"$or": [{field: None}, {field: ""}, {field: {"$exists": False}}]}
    total = collection.count_documents(query)

    if total == 0:
        print(f"  No documents with missing '{field}'. Database is clean for this field.")
        return

    print(f"  {total} document(s) with missing '{field}'. Sample (up to {sample}):\n")
    for i, doc in enumerate(collection.find(query).limit(sample), 1):
        print(f"    [{i}] _id={doc.get('_id')}")
        for f in DISPLAY_FIELDS:
            print(f"        {f}: {doc.get(f)}")
        print()


def summary(collection) -> None:
    total = collection.estimated_document_count()
    print(f"  Total documents (approx): {total}")

    for field in DISPLAY_FIELDS:
        missing = collection.count_documents(
            {"$or": [{field: None}, {field: ""}, {field: {"$exists": False}}]}
        )
        if missing:
            pct = missing / total * 100 if total else 0
            print(f"  Missing '{field}': {missing} ({pct:.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect missing data in RiskDataBengaluru")
    parser.add_argument("-f", "--field", default="zone", help="Field to inspect (default: zone)")
    parser.add_argument("-n", "--sample", type=int, default=5, help="Number of sample docs to show")
    parser.add_argument("--summary", action="store_true", help="Show missing-data summary for all key fields")
    args = parser.parse_args()

    client = connect(MONGO_URI)
    collection = client[DB_NAME][COLLECTION_NAME]

    print(f"\n--- Inspecting '{COLLECTION_NAME}' in '{DB_NAME}' ---\n")

    if args.summary:
        print("[Summary]")
        summary(collection)
        print()

    print(f"[Field: {args.field}]")
    inspect_field(collection, args.field, args.sample)

    client.close()
    print("Done.")


if __name__ == "__main__":
    main()