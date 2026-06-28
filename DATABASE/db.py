"""
DATABASE.db — Reusable MongoDB connection & data-fetch layer for SafeRoute-AI.

Usage:
    from DATABASE.db import get_risk_dataframe, get_collection

    # Fetch all risk data as a Pandas DataFrame (cached in-memory)
    df = get_risk_dataframe()

    # Direct collection access for custom queries
    col = get_collection("RiskData6Areas")
    docs = list(col.find({"source_area": "Indiranagar"}))

Environment:
    Requires MONGO_URI in .env (or as an OS environment variable).
    Free tier: MongoDB Atlas M0 Sandbox (512 MB).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
from pymongo import MongoClient, GEOSPHERE

# ─── Logging ──────────────────────────────────────────────────────────────────
log = logging.getLogger("SafeRoute.DB")

# ─── Config ───────────────────────────────────────────────────────────────────
try:
    from ENGINE.config import MONGO_URI
except ImportError:
    # Fallback: load directly from environment / .env
    try:
        from dotenv import load_dotenv
        _DOTENV = Path(__file__).resolve().parents[1] / ".env"
        if _DOTENV.exists():
            load_dotenv(dotenv_path=_DOTENV)
    except ImportError:
        pass
    MONGO_URI = os.getenv("MONGO_URI", "")

# ─── Constants ────────────────────────────────────────────────────────────────
DB_NAME = "SAFEROUTE_AI"
RISK_COLLECTION = "RiskData6Areas"

# Columns that must be stored / returned as numbers
NUMERIC_FIELDS = [
    "speed_limit", "traffic_signal_density", "intersection_density",
    "commercial_density", "nightlife_density", "hospital_density",
    "police_station_distance", "cctv_density_estimate", "lighting_score",
    "crime_score", "activity_score", "event_frequency", "infrastructure_score",
    "connectivity_score", "isolated_area_score", "road_risk_score",
    "travel_time_estimate", "congestion_score", "flood_risk",
    "weather_exposure_score", "poi_density", "time_risk", "adjacency_count",
]


# ─── Connection ───────────────────────────────────────────────────────────────

_client: Optional[MongoClient] = None


def _get_client() -> MongoClient:
    """Return a singleton MongoClient (lazy-initialised)."""
    global _client
    if _client is None:
        if not MONGO_URI:
            raise EnvironmentError(
                "MONGO_URI is not set. Add it to your .env file or export it."
            )
        log.info("Connecting to MongoDB Atlas …")
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10_000)
        # Force a connection check
        _client.admin.command("ping")
        log.info("MongoDB connection OK ✔")
    return _client


def get_collection(name: str = RISK_COLLECTION):
    """Return a pymongo Collection handle."""
    return _get_client()[DB_NAME][name]


# ─── Data Fetch ───────────────────────────────────────────────────────────────

_cached_df: Optional[pd.DataFrame] = None


def get_risk_dataframe(force_reload: bool = False) -> pd.DataFrame:
    """
    Fetch all risk data from MongoDB and return as a Pandas DataFrame.

    The result is cached in-memory after the first call.  Pass
    ``force_reload=True`` to re-query.

    Returns
    -------
    pd.DataFrame
        DataFrame with all 34 schema columns, numeric fields properly typed.
    """
    global _cached_df
    if _cached_df is not None and not force_reload:
        return _cached_df.copy()

    col = get_collection(RISK_COLLECTION)
    cursor = col.find({}, {"_id": 0, "location": 0})  # exclude Mongo internals & GeoJSON duplicate
    docs = list(cursor)

    if not docs:
        raise RuntimeError(
            f"Collection '{RISK_COLLECTION}' in database '{DB_NAME}' is empty. "
            "Run import_data.py first to populate it."
        )

    df = pd.DataFrame(docs)

    # Coerce numeric columns
    for col_name in NUMERIC_FIELDS:
        if col_name in df.columns:
            df[col_name] = pd.to_numeric(df[col_name], errors="coerce")

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")

    log.info(f"Loaded {len(df):,} risk rows from MongoDB ({RISK_COLLECTION})")
    _cached_df = df
    return _cached_df.copy()


# ─── Index Setup ──────────────────────────────────────────────────────────────

def ensure_indexes():
    """Create recommended indexes on the risk collection."""
    col = get_collection(RISK_COLLECTION)
    col.create_index([("location", GEOSPHERE)], background=True)
    col.create_index("source_area", background=True)
    col.create_index("destination_area", background=True)
    col.create_index("zone", background=True)
    log.info("MongoDB indexes ensured ✔")
