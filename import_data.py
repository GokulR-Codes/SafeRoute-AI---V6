"""
import_data.py — Push the 6-area interconnected risk CSVs into MongoDB Atlas.

Usage:
    python import_data.py

Requirements:
    1. A .env file at the repo root with  MONGO_URI=<your Atlas connection string>
    2. pip install pymongo python-dotenv

The script:
    • Drops the old collection (clean slate) so you can re-run safely.
    • Imports only the combined interconnected dataset (ALL_6_AREAS_INTERCONNECTED.csv).
    • Casts all numeric fields to float, builds GeoJSON Point for geo queries.
    • Creates 2dsphere + secondary indexes for fast engine lookups.
"""

import csv
import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pymongo import MongoClient, GEOSPHERE

# ─── Load MONGO_URI from .env ────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _DOTENV = Path(__file__).resolve().parent / ".env"
    if _DOTENV.exists():
        load_dotenv(dotenv_path=_DOTENV)
except ImportError:
    pass

MONGO_URI = os.getenv("MONGO_URI", "")
if not MONGO_URI:
    print("❌ MONGO_URI is not set.  Add it to your .env file.")
    sys.exit(1)

DB_NAME = "SAFEROUTE_AI"
COLLECTION_NAME = "RiskData6Areas"

# ─── Files to Import ─────────────────────────────────────────────────────────
# Use ONLY the combined interconnected file (contains all 6 areas + cross-area
# routes).  This avoids duplicating rows that exist in individual area files.
FILES_TO_IMPORT = [
    "SafeRoute_6Areas_Interconnected/ALL_6_AREAS_INTERCONNECTED.csv",
]

# All fields that need to be stored as numbers in MongoDB
NUMERIC_FIELDS = [
    "speed_limit", "traffic_signal_density", "intersection_density",
    "commercial_density", "nightlife_density", "hospital_density",
    "police_station_distance", "cctv_density_estimate", "lighting_score",
    "crime_score", "activity_score", "event_frequency", "infrastructure_score",
    "connectivity_score", "isolated_area_score", "road_risk_score",
    "travel_time_estimate", "congestion_score", "flood_risk",
    "weather_exposure_score", "poi_density", "time_risk", "adjacency_count",
]


def safe_float(val):
    """Helper to safely convert strings to floats, handling empty CSV cells."""
    if not val or val.strip() == "":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def import_csv(file_path, collection):
    results = []

    with open(file_path, mode="r", encoding="utf-8-sig") as file:
        # DictReader automatically uses the first row as dictionary keys
        reader = csv.DictReader(file)

        for row in reader:
            # 1. Start with the base string data
            doc = dict(row)

            # 2. Extract and cast lat/lng
            lat = safe_float(row.get("lat"))
            lng = safe_float(row.get("lng"))

            doc["lat"] = lat
            doc["lng"] = lng

            # 3. Construct GeoJSON location object (Longitude first, then Latitude)
            if lat is not None and lng is not None:
                doc["location"] = {
                    "type": "Point",
                    "coordinates": [lng, lat],
                }

            # 4. Explicitly cast all other numeric fields
            for field_name in NUMERIC_FIELDS:
                if field_name in row:
                    doc[field_name] = safe_float(row[field_name])

            results.append(doc)

    # Bulk insert into MongoDB
    if results:
        try:
            collection.insert_many(results)
            print(f"✅ Successfully imported {len(results)} rows from {file_path}")
        except Exception as e:
            print(f"❌ Error inserting {file_path}: {e}")
    else:
        print(f"⚠️ No data found in {file_path}")


def run_import():
    try:
        print("━" * 60)
        print("  SafeRoute-AI — MongoDB Data Importer")
        print("  Target: 6 Areas Interconnected Dataset")
        print("━" * 60)

        print("\nConnecting to MongoDB Atlas...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
        # Verify connection
        client.admin.command("ping")
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        print("Connected! ✔\n")

        # Drop old data for a clean import (safe to re-run)
        existing = collection.count_documents({})
        if existing > 0:
            print(f"  ⚠ Dropping {existing:,} existing documents in '{COLLECTION_NAME}'...")
            collection.drop()
            collection = db[COLLECTION_NAME]  # re-acquire after drop
            print("  Dropped. Starting fresh.\n")

        # Create indexes
        print("Creating indexes...")
        collection.create_index([("location", GEOSPHERE)], background=True)
        collection.create_index("source_area", background=True)
        collection.create_index("destination_area", background=True)
        collection.create_index("zone", background=True)
        print("Indexes created ✔\n")

        # Import files
        for file_name in FILES_TO_IMPORT:
            if os.path.exists(file_name):
                import_csv(file_name, collection)
            else:
                print(f"⚠️ File not found: {file_name}, skipping...")

        # Summary
        final_count = collection.count_documents({})
        print(f"\n🎉 Import complete!  {final_count:,} documents in '{COLLECTION_NAME}'")
        print(f"   Database: {DB_NAME}")
        print(f"   Free tier usage: ~{final_count * 260 / 1024:.0f} KB  (Atlas M0 limit: 512 MB)")

    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        sys.exit(1)
    finally:
        if "client" in locals():
            client.close()


if __name__ == "__main__":
    run_import()