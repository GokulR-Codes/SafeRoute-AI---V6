"""
SafeRoute-AI | MongoDB Schema Setup (Python / PyMongo)
=======================================================
Creates all collections with JSON Schema validators and indexes.

Usage:
    python db_schemas.py                          # uses MONGO_URI from .env
    python db_schemas.py --uri "mongodb+srv://..." # override URI
    python db_schemas.py --drop                   # drop & recreate collections

Collections:
    1.  RiskSegments           - road-segment risk records (zone CSVs)
    2.  GraphNodes             - graph routing nodes
    3.  GraphEdges             - directed graph edges
    4.  HourlyEdgeWeights      - per-edge, per-hour dynamic risk weights
    5.  ZoneSummary            - per-zone aggregated statistics
    6.  CityHourlyProfile      - city-wide hourly risk statistics
    7.  ZoneHourlyRisk         - per zone-type hourly risk sweep
    8.  TopRiskSegments        - pre-computed high-risk hotspot segments
    9.  FactorContributions    - risk factor weight/contribution breakdown
   10.  HourlyRiskSweep        - city-wide hourly sweep summary
   11.  CorrelationValidation  - correlation check audit log
   12.  IncidentLayer          - live/injected incidents on edges
   13.  RouteCache             - cached route results (TTL: 1h)
   14.  PoliceStations         - reference POI: police stations
   15.  Hospitals              - reference POI: hospitals
   16.  SafeHavens             - snapped safe-haven graph nodes
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List

try:
    from pymongo import MongoClient, GEOSPHERE, ASCENDING, DESCENDING
    from pymongo.errors import CollectionInvalid, BulkWriteError
except ImportError:
    print("pymongo not found – run:  pip install pymongo")
    sys.exit(1)

try:
    from ENGINE.config import MONGO_URI
except Exception:
    import os
    MONGO_URI = os.getenv("MONGO_URI", "")

DB_NAME = "SAFEROUTE_AI"

# ─────────────────────────────────────────────────────────────────────────────
# Schema helpers
# ─────────────────────────────────────────────────────────────────────────────

_RISK_ZONE_ENUM = [
    "CENTRAL BANGALORE", "NORTH BANGALORE", "SOUTH BANGALORE",
    "EAST BANGALORE", "WEST BANGALORE",
    "SOUTHEAST / IT CORRIDOR", "AIRPORT / PERIPHERAL",
    "LOGISTICS / HIGH-TRAFFIC",
]

_ROAD_TYPE_ENUM = [
    "motorway", "motorway_link", "trunk", "trunk_link", "highway",
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "residential", "living_street",
    "service", "unclassified", "busway", "road",
    "connector", "arterial_connector", "healed_connector",
]

_RISK_BAND_ENUM = ["Low", "Moderate", "High", "Critical"]

_ROUTING_PROFILE_ENUM = [
    "default", "women", "fastest", "balanced",
    "FASTEST", "SAFEST", "BALANCED", "WOMEN_SAFE", "EMERGENCY",
]

_INCIDENT_TYPE_ENUM = [
    "Accident", "Flood", "Crime", "Road Closure",
    "Construction", "Event", "crime_spike", "road_closure",
    "accident", "flood", "event", "construction",
]

_HAVEN_TYPE_ENUM = [
    "police_station", "hospital", "metro_station",
    "bus_station", "public_area", "cctv_dense_zone",
]

# Reusable sub-schemas
_GEOJSON_POINT = {
    "bsonType": ["object", "null"],
    "description": "GeoJSON Point — {type:'Point', coordinates:[lng, lat]}",
    "properties": {
        "type":        {"bsonType": "string", "enum": ["Point"]},
        "coordinates": {"bsonType": "array",  "minItems": 2, "maxItems": 2,
                        "items": {"bsonType": "double"}},
    },
}

_ROUTE_METRICS_SCHEMA = {
    "bsonType": ["object", "null"],
    "properties": {
        "total_distance_km":          {"bsonType": ["double", "null"]},
        "total_travel_time_min":      {"bsonType": ["double", "null"]},
        "average_risk":               {"bsonType": ["double", "null"]},
        "maximum_risk":               {"bsonType": ["double", "null"]},
        "average_congestion":         {"bsonType": ["double", "null"]},
        "weather_exposure":           {"bsonType": ["double", "null"]},
        "node_count":                 {"bsonType": ["int", "null"]},
        "edge_count":                 {"bsonType": ["int", "null"]},
        "average_lighting_dark_risk": {"bsonType": ["double", "null"]},
        "average_isolation":          {"bsonType": ["double", "null"]},
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Collection definitions
# ─────────────────────────────────────────────────────────────────────────────

COLLECTIONS: Dict[str, Dict[str, Any]] = {

    # ── 1. RiskSegments ──────────────────────────────────────────────────────
    "RiskSegments": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["zone", "lat", "lng", "road_risk_score"],
                "properties": {
                    "zone":             {"bsonType": "string", "enum": _RISK_ZONE_ENUM},
                    "direction":        {"bsonType": ["string", "null"]},
                    "lat":              {"bsonType": ["double", "null"]},
                    "lng":              {"bsonType": ["double", "null"]},
                    "location":         _GEOJSON_POINT,
                    "source_area":      {"bsonType": ["string", "null"]},
                    "destination_area": {"bsonType": ["string", "null"]},
                    "road_name":        {"bsonType": ["string", "null"]},
                    "road_type":        {"bsonType": ["string", "null"],
                                         "enum": _ROAD_TYPE_ENUM + [None]},
                    "highway_type":     {"bsonType": ["string", "null"]},
                    "junction_type":    {"bsonType": ["string", "null"]},
                    "road_width_estimate": {"bsonType": ["string", "null"]},
                    # Traffic
                    "speed_limit":            {"bsonType": ["double", "null"]},
                    "traffic_signal_density": {"bsonType": ["double", "null"]},
                    "intersection_density":   {"bsonType": ["double", "null"]},
                    "adjacency_count":        {"bsonType": ["double", "int", "null"]},
                    # Density
                    "commercial_density": {"bsonType": ["double", "null"]},
                    "nightlife_density":  {"bsonType": ["double", "null"]},
                    "hospital_density":   {"bsonType": ["double", "null"]},
                    "poi_density":        {"bsonType": ["double", "null"]},
                    # Safety infra
                    "police_station_distance": {"bsonType": ["double", "null"]},
                    "cctv_density_estimate":   {"bsonType": ["double", "null"]},
                    "lighting_score":          {"bsonType": ["double", "null"]},
                    # Risk scores
                    "crime_score":          {"bsonType": ["double", "null"]},
                    "activity_score":       {"bsonType": ["double", "null"]},
                    "event_frequency":      {"bsonType": ["double", "null"]},
                    "infrastructure_score": {"bsonType": ["double", "null"]},
                    "connectivity_score":   {"bsonType": ["double", "null"]},
                    "isolated_area_score":  {"bsonType": ["double", "null"]},
                    "road_risk_score":      {"bsonType": ["double", "null"]},
                    # Environmental
                    "flood_risk":             {"bsonType": ["double", "null"]},
                    "weather_exposure_score": {"bsonType": ["double", "null"]},
                    "time_risk":              {"bsonType": ["double", "null"]},
                    # Travel
                    "travel_time_estimate": {"bsonType": ["double", "null"]},
                    "congestion_score":     {"bsonType": ["double", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("location", GEOSPHERE)], {}),
            ([("zone", ASCENDING), ("road_risk_score", DESCENDING)], {}),
            ([("source_area", ASCENDING), ("destination_area", ASCENDING)], {}),
            ([("crime_score", DESCENDING)], {}),
            ([("isolated_area_score", DESCENDING)], {}),
        ],
    },

    # ── 2. GraphNodes ────────────────────────────────────────────────────────
    "GraphNodes": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["node_id", "lat", "lng"],
                "properties": {
                    "node_id":           {"bsonType": ["int", "long"]},
                    "lat":               {"bsonType": "double"},
                    "lng":               {"bsonType": "double"},
                    "location":          _GEOJSON_POINT,
                    "zone":              {"bsonType": ["string", "null"]},
                    "source_area":       {"bsonType": ["string", "null"]},
                    "adjacency_count":   {"bsonType": ["int", "null"]},
                    "connectivity_score":{"bsonType": ["double", "null"]},
                    "is_dead_end":       {"bsonType": ["bool", "null"]},
                    "is_merged":         {"bsonType": ["bool", "null"]},
                    "merged_into":       {"bsonType": ["int", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("node_id", ASCENDING)], {"unique": True}),
            ([("location", GEOSPHERE)], {}),
            ([("zone", ASCENDING)], {}),
            ([("source_area", ASCENDING)], {}),
        ],
    },

    # ── 3. GraphEdges ────────────────────────────────────────────────────────
    "GraphEdges": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["edge_id", "u", "v"],
                "properties": {
                    "edge_id":            {"bsonType": "string"},
                    "u":                  {"bsonType": ["int", "long"]},
                    "v":                  {"bsonType": ["int", "long"]},
                    "source_node":        {"bsonType": ["int", "long", "null"]},
                    "destination_node":   {"bsonType": ["int", "long", "null"]},
                    "lat":                {"bsonType": ["double", "null"]},
                    "lng":                {"bsonType": ["double", "null"]},
                    "road_name":          {"bsonType": ["string", "null"]},
                    "road_type":          {"bsonType": ["string", "null"]},
                    "highway_type":       {"bsonType": ["string", "null"]},
                    "direction":          {"bsonType": ["string", "null"]},
                    "zone":               {"bsonType": ["string", "null"]},
                    "zone_type":          {"bsonType": ["string", "null"]},
                    "source_area":        {"bsonType": ["string", "null"]},
                    "destination_area":   {"bsonType": ["string", "null"]},
                    # Static geometry (v8 Phase 1)
                    "static_distance_km":      {"bsonType": ["double", "null"]},
                    "static_travel_time_min":  {"bsonType": ["double", "null"]},
                    "bearing":                 {"bsonType": ["double", "null"]},
                    "geometry_length":         {"bsonType": ["double", "null"]},
                    "road_curvature":          {"bsonType": ["double", "null"]},
                    "geometry_polyline":       {"bsonType": ["string", "null"]},
                    # Elevation (v8 Phase 3)
                    "elevation_m":    {"bsonType": ["double", "null"]},
                    "slope_percent":  {"bsonType": ["double", "null"]},
                    "bridge_flag":    {"bsonType": ["int", "bool", "null"]},
                    "flyover_flag":   {"bsonType": ["int", "bool", "null"]},
                    "underpass_flag": {"bsonType": ["int", "bool", "null"]},
                    # Capacity (v8 Phase 4)
                    "lane_count":            {"bsonType": ["int", "null"]},
                    "capacity_score":        {"bsonType": ["double", "null"]},
                    "road_importance_score": {"bsonType": ["double", "null"]},
                    "capacity_weight":       {"bsonType": ["double", "null"]},
                    # Turn penalty (v8 Phase 2)
                    "turn_penalty": {"bsonType": ["double", "null"]},
                    # Risk features (from edge CSV)
                    "road_risk_score":       {"bsonType": ["double", "null"]},
                    "crime_score":           {"bsonType": ["double", "null"]},
                    "lighting_score":        {"bsonType": ["double", "null"]},
                    "isolated_area_score":   {"bsonType": ["double", "null"]},
                    "congestion_score":      {"bsonType": ["double", "null"]},
                    "flood_risk":            {"bsonType": ["double", "null"]},
                    "weather_exposure_score":{"bsonType": ["double", "null"]},
                    "static_component":      {"bsonType": ["double", "null"]},
                    "graph_component":       {"bsonType": ["double", "null"]},
                    "edge_source":           {"bsonType": ["string", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("edge_id", ASCENDING)], {"unique": True}),
            ([("u", ASCENDING), ("v", ASCENDING)], {}),
            ([("source_node", ASCENDING), ("destination_node", ASCENDING)], {}),
            ([("zone", ASCENDING)], {}),
            ([("road_type", ASCENDING)], {}),
            ([("road_risk_score", DESCENDING)], {}),
        ],
    },

    # ── 4. HourlyEdgeWeights ─────────────────────────────────────────────────
    "HourlyEdgeWeights": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["edge_id", "hour"],
                "properties": {
                    "edge_id": {"bsonType": "string"},
                    "hour":    {"bsonType": "int", "minimum": 0, "maximum": 23},
                    "final_edge_weight":      {"bsonType": ["double", "null"]},
                    "final_risk_score":       {"bsonType": ["double", "null"]},
                    "congestion_score":       {"bsonType": ["double", "null"]},
                    "time_risk":              {"bsonType": ["double", "null"]},
                    "weather_exposure_score": {"bsonType": ["double", "null"]},
                    "dynamic_risk_score":     {"bsonType": ["double", "null"]},
                    "lighting_dark_risk":     {"bsonType": ["double", "null"]},
                    "isolated_area_score":    {"bsonType": ["double", "null"]},
                    "crime_score":            {"bsonType": ["double", "null"]},
                    # Raw 24-col CSV format (alternative storage)
                    **{f"hour_{h:02d}": {"bsonType": ["double", "null"]}
                       for h in range(24)},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("edge_id", ASCENDING), ("hour", ASCENDING)], {"unique": True}),
            ([("hour", ASCENDING), ("final_risk_score", DESCENDING)], {}),
        ],
    },

    # ── 5. ZoneSummary ───────────────────────────────────────────────────────
    "ZoneSummary": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["zone"],
                "properties": {
                    "zone":              {"bsonType": "string"},
                    "direction":         {"bsonType": ["string", "null"]},
                    "segments":          {"bsonType": ["int", "null"]},
                    "risk_mean":         {"bsonType": ["double", "null"]},
                    "risk_median":       {"bsonType": ["double", "null"]},
                    "risk_p95":          {"bsonType": ["double", "null"]},
                    "risk_max":          {"bsonType": ["double", "null"]},
                    "contextual_mean":   {"bsonType": ["double", "null"]},
                    "confidence_mean":   {"bsonType": ["double", "null"]},
                    "uncertainty_mean":  {"bsonType": ["double", "null"]},
                    "crime_mean":        {"bsonType": ["double", "null"]},
                    "lighting_mean":     {"bsonType": ["double", "null"]},
                    "police_mean":       {"bsonType": ["double", "null"]},
                    "cctv_mean":         {"bsonType": ["double", "null"]},
                    "congestion_mean":   {"bsonType": ["double", "null"]},
                    "travel_time_mean":  {"bsonType": ["double", "null"]},
                    "connectivity_mean": {"bsonType": ["double", "null"]},
                    "isolation_mean":    {"bsonType": ["double", "null"]},
                    "road_risk_mean":    {"bsonType": ["double", "null"]},
                    "behav_adj_mean":    {"bsonType": ["double", "null"]},
                    "poi_interaction_mean": {"bsonType": ["double", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("zone", ASCENDING), ("direction", ASCENDING)], {"unique": True}),
            ([("risk_mean", DESCENDING)], {}),
        ],
    },

    # ── 6. CityHourlyProfile ─────────────────────────────────────────────────
    "CityHourlyProfile": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["hour"],
                "properties": {
                    "hour":      {"bsonType": "int", "minimum": 0, "maximum": 23},
                    "mean_risk": {"bsonType": ["double", "null"]},
                    "p25_risk":  {"bsonType": ["double", "null"]},
                    "p75_risk":  {"bsonType": ["double", "null"]},
                    "max_risk":  {"bsonType": ["double", "null"]},
                    "min_risk":  {"bsonType": ["double", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("hour", ASCENDING)], {"unique": True}),
        ],
    },

    # ── 7. ZoneHourlyRisk ────────────────────────────────────────────────────
    "ZoneHourlyRisk": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["zone_type"],
                "properties": {
                    "zone_type": {"bsonType": "string"},
                    **{f"hour_{h:02d}": {"bsonType": ["double", "null"]}
                       for h in range(24)},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("zone_type", ASCENDING)], {"unique": True}),
        ],
    },

    # ── 8. TopRiskSegments ───────────────────────────────────────────────────
    "TopRiskSegments": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["zone", "lat", "lng", "final_risk_score"],
                "properties": {
                    "zone":              {"bsonType": "string"},
                    "lat":               {"bsonType": "double"},
                    "lng":               {"bsonType": "double"},
                    "location":          _GEOJSON_POINT,
                    "final_risk_score":  {"bsonType": "double"},
                    "contextual_risk":   {"bsonType": ["double", "null"]},
                    "confidence_score":  {"bsonType": ["double", "null"]},
                    "uncertainty_level": {"bsonType": ["double", "null"]},
                    "risk_band":         {"bsonType": ["string", "null"],
                                          "enum": _RISK_BAND_ENUM + [None]},
                    "road_risk_score":   {"bsonType": ["double", "null"]},
                    "congestion_score":  {"bsonType": ["double", "null"]},
                    "travel_time_estimate": {"bsonType": ["double", "null"]},
                    "score_crime":       {"bsonType": ["double", "null"]},
                    "score_lighting":    {"bsonType": ["double", "null"]},
                    "score_police":      {"bsonType": ["double", "null"]},
                    "isolated_area_score": {"bsonType": ["double", "null"]},
                    "connectivity_score":  {"bsonType": ["double", "null"]},
                    "behavioural_adj":   {"bsonType": ["double", "null"]},
                    "poi_interaction":   {"bsonType": ["double", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("location", GEOSPHERE)], {}),
            ([("final_risk_score", DESCENDING)], {}),
            ([("zone", ASCENDING), ("final_risk_score", DESCENDING)], {}),
        ],
    },

    # ── 9. FactorContributions ───────────────────────────────────────────────
    "FactorContributions": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["factor"],
                "properties": {
                    "factor":       {"bsonType": "string"},
                    "mean_score":   {"bsonType": ["double", "null"]},
                    "base_weight":  {"bsonType": ["double", "null"]},
                    "contribution": {"bsonType": ["double", "null"]},
                    "snapshot_ts":  {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("factor", ASCENDING)], {"unique": True}),
        ],
    },

    # ── 10. HourlyRiskSweep ──────────────────────────────────────────────────
    "HourlyRiskSweep": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["hour"],
                "properties": {
                    "hour":           {"bsonType": "int", "minimum": 0, "maximum": 23},
                    "time_context":   {"bsonType": ["string", "null"]},
                    "risk_mean":      {"bsonType": ["double", "null"]},
                    "risk_std":       {"bsonType": ["double", "null"]},
                    "risk_p90":       {"bsonType": ["double", "null"]},
                    "risk_max":       {"bsonType": ["double", "null"]},
                    "contextual_mean":   {"bsonType": ["double", "null"]},
                    "congestion_mean":   {"bsonType": ["double", "null"]},
                    "travel_time_mean":  {"bsonType": ["double", "null"]},
                    "connectivity_mean": {"bsonType": ["double", "null"]},
                    "isolation_mean":    {"bsonType": ["double", "null"]},
                    "confidence_mean":   {"bsonType": ["double", "null"]},
                    "uncertainty_mean":  {"bsonType": ["double", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("hour", ASCENDING)], {"unique": True}),
        ],
    },

    # ── 11. CorrelationValidation ────────────────────────────────────────────
    "CorrelationValidation": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["check", "col_a", "col_b"],
                "properties": {
                    "check":     {"bsonType": "string"},
                    "col_a":     {"bsonType": "string"},
                    "col_b":     {"bsonType": "string"},
                    "pearson_r": {"bsonType": ["double", "null"]},
                    "expected":  {"bsonType": ["string", "null"]},
                    "status":    {"bsonType": ["string", "null"],
                                  "enum": ["PASS", "FAIL", None]},
                    "run_ts":    {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("check", ASCENDING)], {}),
            ([("status", ASCENDING)], {}),
        ],
    },

    # ── 12. IncidentLayer ────────────────────────────────────────────────────
    "IncidentLayer": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["edge_id", "type"],
                "properties": {
                    "edge_id":        {"bsonType": "string"},
                    "type":           {"bsonType": "string",
                                       "enum": _INCIDENT_TYPE_ENUM},
                    "severity":       {"bsonType": ["double", "null"]},
                    "hazard_penalty": {"bsonType": ["double", "null"]},
                    "description":    {"bsonType": ["string", "null"]},
                    "active":         {"bsonType": ["bool", "int", "null"]},
                    "reported_hour":  {"bsonType": ["int", "null"]},
                    "reported_at":    {"bsonType": ["date", "null"]},
                    "expires_at":     {"bsonType": ["date", "null"]},
                    "lat":            {"bsonType": ["double", "null"]},
                    "lng":            {"bsonType": ["double", "null"]},
                    "location":       _GEOJSON_POINT,
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("edge_id", ASCENDING)], {}),
            ([("location", GEOSPHERE)], {}),
            ([("active", ASCENDING), ("type", ASCENDING)], {}),
            ([("expires_at", ASCENDING)], {"expireAfterSeconds": 0,
                                            "name": "incident_ttl"}),
        ],
    },

    # ── 13. RouteCache ───────────────────────────────────────────────────────
    "RouteCache": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["source_node", "destination_node", "profile"],
                "properties": {
                    "source_node":      {"bsonType": ["int", "long"]},
                    "destination_node": {"bsonType": ["int", "long"]},
                    "hour":             {"bsonType": ["int", "null"]},
                    "profile":          {"bsonType": "string",
                                         "enum": _ROUTING_PROFILE_ENUM},
                    "path":             {"bsonType": ["array", "null"]},
                    "edge_path":        {"bsonType": ["array", "null"]},
                    "cost":             {"bsonType": ["double", "null"]},
                    "metrics":          _ROUTE_METRICS_SCHEMA,
                    "coordinates":      {"bsonType": ["array", "null"]},
                    "explanation":      {"bsonType": ["object", "null"]},
                    "confidence_score": {"bsonType": ["int", "null"]},
                    "created_at":       {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("source_node", ASCENDING), ("destination_node", ASCENDING),
              ("hour", ASCENDING), ("profile", ASCENDING)], {"unique": True}),
            ([("created_at", ASCENDING)],
             {"expireAfterSeconds": 3600, "name": "route_cache_ttl_1h"}),
        ],
    },

    # ── 14. PoliceStations ───────────────────────────────────────────────────
    "PoliceStations": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name", "lat", "lng"],
                "properties": {
                    "name":            {"bsonType": "string"},
                    "lat":             {"bsonType": "double"},
                    "lng":             {"bsonType": "double"},
                    "location":        _GEOJSON_POINT,
                    "nearest_node_id": {"bsonType": ["int", "null"]},
                    "zone":            {"bsonType": ["string", "null"]},
                    "active":          {"bsonType": ["bool", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("location", GEOSPHERE)], {}),
            ([("name", ASCENDING)], {"unique": True}),
        ],
    },

    # ── 15. Hospitals ────────────────────────────────────────────────────────
    "Hospitals": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["name", "lat", "lng"],
                "properties": {
                    "name":            {"bsonType": "string"},
                    "lat":             {"bsonType": "double"},
                    "lng":             {"bsonType": "double"},
                    "location":        _GEOJSON_POINT,
                    "nearest_node_id": {"bsonType": ["int", "null"]},
                    "zone":            {"bsonType": ["string", "null"]},
                    "active":          {"bsonType": ["bool", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("location", GEOSPHERE)], {}),
            ([("name", ASCENDING)], {"unique": True}),
        ],
    },

    # ── 16. SafeHavens ───────────────────────────────────────────────────────
    "SafeHavens": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["haven_type", "node_id"],
                "properties": {
                    "haven_type":      {"bsonType": "string",
                                        "enum": _HAVEN_TYPE_ENUM},
                    "node_id":         {"bsonType": ["int", "long"]},
                    "poi_name":        {"bsonType": ["string", "null"]},
                    "lat":             {"bsonType": ["double", "null"]},
                    "lng":             {"bsonType": ["double", "null"]},
                    "location":        _GEOJSON_POINT,
                    "snap_distance_m": {"bsonType": ["double", "null"]},
                    "created_at":      {"bsonType": ["date", "null"]},
                },
            }
        },
        "validationAction": "warn",
        "indexes": [
            ([("haven_type", ASCENDING), ("node_id", ASCENDING)], {"unique": True}),
            ([("location", GEOSPHERE)], {}),
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Seed data
# ─────────────────────────────────────────────────────────────────────────────

POLICE_STATIONS_SEED: List[Dict] = [
    {"name": "Hebbal PS",          "lat": 13.0360, "lng": 77.5970, "zone": "North Bangalore"},
    {"name": "RT Nagar PS",        "lat": 13.0220, "lng": 77.5975, "zone": "North Bangalore"},
    {"name": "Yelahanka PS",       "lat": 13.1006, "lng": 77.5960, "zone": "North Bangalore"},
    {"name": "Byatarayanapura PS", "lat": 13.0590, "lng": 77.5600, "zone": "North Bangalore"},
    {"name": "Devanahalli PS",     "lat": 13.2470, "lng": 77.7110, "zone": "Airport / Peripheral"},
    {"name": "Jakkur PS",          "lat": 13.0715, "lng": 77.5880, "zone": "North Bangalore"},
    {"name": "Nagawara PS",        "lat": 13.0450, "lng": 77.6250, "zone": "North Bangalore"},
    {"name": "Rajajinagar PS",     "lat": 12.9840, "lng": 77.5510, "zone": "West Bangalore"},
    {"name": "Malleswaram PS",     "lat": 12.9990, "lng": 77.5720, "zone": "West Bangalore"},
    {"name": "Majestic PS",        "lat": 12.9770, "lng": 77.5720, "zone": "West Bangalore"},
    {"name": "Magadi Road PS",     "lat": 12.9640, "lng": 77.5170, "zone": "West Bangalore"},
    {"name": "Kengeri PS",         "lat": 12.9149, "lng": 77.4840, "zone": "West Bangalore"},
    {"name": "Indiranagar PS",     "lat": 12.9792, "lng": 77.6388, "zone": "East Bangalore"},
    {"name": "Whitefield PS",      "lat": 12.9698, "lng": 77.7500, "zone": "East Bangalore"},
    {"name": "KR Puram PS",        "lat": 13.0020, "lng": 77.6960, "zone": "East Bangalore"},
    {"name": "Marathahalli PS",    "lat": 12.9591, "lng": 77.7011, "zone": "East Bangalore"},
    {"name": "HAL PS",             "lat": 12.9634, "lng": 77.6596, "zone": "East Bangalore"},
    {"name": "Koramangala PS",     "lat": 12.9293, "lng": 77.6210, "zone": "South Bangalore"},
    {"name": "BTM Layout PS",      "lat": 12.9126, "lng": 77.6101, "zone": "South Bangalore"},
    {"name": "JP Nagar PS",        "lat": 12.9060, "lng": 77.5830, "zone": "South Bangalore"},
    {"name": "Jayanagar PS",       "lat": 12.9260, "lng": 77.5830, "zone": "South Bangalore"},
    {"name": "Electronic City PS", "lat": 12.8440, "lng": 77.6600, "zone": "South Bangalore"},
    {"name": "HSR Layout PS",      "lat": 12.9121, "lng": 77.6446, "zone": "South Bangalore"},
    {"name": "Banashankari PS",    "lat": 12.9270, "lng": 77.5640, "zone": "South Bangalore"},
]

HOSPITALS_SEED: List[Dict] = [
    {"name": "Manipal Hospital",      "lat": 12.9592, "lng": 77.6474},
    {"name": "Fortis Bannerghatta",   "lat": 12.8929, "lng": 77.5971},
    {"name": "Apollo Jayanagar",      "lat": 12.9257, "lng": 77.5832},
    {"name": "Narayana Hrudayalaya",  "lat": 12.8414, "lng": 77.6601},
    {"name": "St Johns Hospital",     "lat": 12.9452, "lng": 77.6153},
    {"name": "Victoria Hospital",     "lat": 12.9640, "lng": 77.5730},
    {"name": "Bowring Hospital",      "lat": 12.9787, "lng": 77.6133},
    {"name": "Sakra World Hospital",  "lat": 12.9582, "lng": 77.7091},
    {"name": "Columbia Asia Hebbal",  "lat": 13.0360, "lng": 77.5978},
    {"name": "Aster CMI Hebbal",      "lat": 13.0430, "lng": 77.5890},
    {"name": "Sparsh Hospital",       "lat": 13.0220, "lng": 77.5960},
    {"name": "NIMHANS",               "lat": 12.9442, "lng": 77.5955},
    {"name": "KIMS Hospital",         "lat": 12.9330, "lng": 77.5790},
    {"name": "Bangalore Baptist",     "lat": 13.0254, "lng": 77.5963},
    {"name": "Msrit Medical Centre",  "lat": 13.0213, "lng": 77.5637},
]


def _add_geojson(docs: List[Dict]) -> List[Dict]:
    """Inject GeoJSON Point and active flag into POI seed docs."""
    for doc in docs:
        doc["location"] = {
            "type": "Point",
            "coordinates": [doc["lng"], doc["lat"]],
        }
        doc.setdefault("active", True)
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Setup function
# ─────────────────────────────────────────────────────────────────────────────

def setup_database(uri: str, drop: bool = False) -> None:
    print(f"\n{'='*63}")
    print("  SafeRoute-AI  |  MongoDB Schema Setup")
    print(f"  Database: {DB_NAME}")
    print(f"{'='*63}")

    client = MongoClient(uri)
    db = client[DB_NAME]

    existing = set(db.list_collection_names())

    for coll_name, spec in COLLECTIONS.items():
        options = {k: v for k, v in spec.items() if k != "indexes"}
        indexes: List = spec.get("indexes", [])

        if drop and coll_name in existing:
            db[coll_name].drop()
            print(f"  🗑  Dropped: {coll_name}")
            existing.discard(coll_name)

        if coll_name not in existing:
            db.create_collection(coll_name, **options)
            print(f"  ✅  Created: {coll_name}")
        else:
            # Update validator on existing collection
            db.command("collMod", coll_name,
                       validator=options.get("validator", {}),
                       validationAction=options.get("validationAction", "warn"))
            print(f"  🔄  Updated validator: {coll_name}")

        coll = db[coll_name]
        for index_keys, index_opts in indexes:
            try:
                coll.create_index(index_keys, **index_opts)
            except Exception as e:
                print(f"    ⚠  Index on {coll_name} {index_keys}: {e}")

    # ── Seed reference data ───────────────────────────────────────────────────
    for coll_name, seed_docs in [
        ("PoliceStations", _add_geojson(POLICE_STATIONS_SEED)),
        ("Hospitals",      _add_geojson(HOSPITALS_SEED)),
    ]:
        coll = db[coll_name]
        if coll.count_documents({}) == 0:
            try:
                coll.insert_many(seed_docs, ordered=False)
                print(f"  🌱  Seeded {len(seed_docs)} docs → {coll_name}")
            except BulkWriteError as bwe:
                print(f"  ⚠  Seed partial error {coll_name}: {bwe.details}")
        else:
            print(f"  ℹ   {coll_name} already seeded ({coll.count_documents({})} docs)")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─'*63}")
    print(f"  {'Collection':<32} {'Documents':>10}")
    print(f"{'─'*63}")
    for coll_name in sorted(db.list_collection_names()):
        cnt = db[coll_name].count_documents({})
        print(f"  {coll_name:<32} {cnt:>10,}")
    print(f"{'='*63}\n")

    client.close()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SafeRoute-AI MongoDB schema setup")
    parser.add_argument("--uri",  default=MONGO_URI,
                        help="MongoDB connection URI (default: MONGO_URI env var)")
    parser.add_argument("--drop", action="store_true",
                        help="Drop and recreate all collections (destructive!)")
    args = parser.parse_args()

    if not args.uri:
        print("ERROR: MONGO_URI not set. Provide --uri or set MONGO_URI in .env")
        sys.exit(1)

    setup_database(args.uri, drop=args.drop)
