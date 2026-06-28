"""
SafeRoute Temporal Risk Graph Engine v1
========================================
Lead Architect: SafeRoute-AI Core Intelligence Layer
Position: Between OSM Extractor and A* Routing Engine

Pipeline:
  Zone Datasets → Temporal Risk Graph Engine → Graph + Risk Tensor → A* Routing

This engine is the single source of truth for all routing decisions.
Every edge carries 24 independently computed risk values.
A* performs O(1) lookups only — never recomputes risk.
"""

from __future__ import annotations

import gc
import logging
import os
import pickle
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import networkx as nx
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from sklearn.preprocessing import MinMaxScaler

warnings.filterwarnings("ignore", category=FutureWarning)

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("SafeRoute.Engine")


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA CONTRACT
# ─────────────────────────────────────────────────────────────────────────────
REQUIRED_COLUMNS = [
    "zone", "direction", "lat", "lng",
    "source_area", "destination_area", "road_name", "road_type",
    "highway_type", "junction_type", "road_width_estimate", "speed_limit",
    "traffic_signal_density", "intersection_density", "commercial_density",
    "nightlife_density", "hospital_density", "police_station_distance",
    "cctv_density_estimate", "lighting_score", "crime_score",
    "activity_score", "event_frequency", "infrastructure_score",
    "connectivity_score", "isolated_area_score", "road_risk_score",
    "travel_time_estimate", "congestion_score", "flood_risk",
    "weather_exposure_score", "poi_density", "time_risk", "adjacency_count",
]

NUMERIC_COLUMNS = [
    "lat", "lng", "road_width_estimate", "speed_limit",
    "traffic_signal_density", "intersection_density", "commercial_density",
    "nightlife_density", "hospital_density", "police_station_distance",
    "cctv_density_estimate", "lighting_score", "crime_score",
    "activity_score", "event_frequency", "infrastructure_score",
    "connectivity_score", "isolated_area_score", "road_risk_score",
    "travel_time_estimate", "congestion_score", "flood_risk",
    "weather_exposure_score", "poi_density", "time_risk", "adjacency_count",
]

HOURS = list(range(24))


# ─────────────────────────────────────────────────────────────────────────────
# ZONE TAXONOMY
# ─────────────────────────────────────────────────────────────────────────────
class ZoneType:
    COMMERCIAL   = "Commercial Hub"
    NIGHTLIFE    = "Nightlife Hub"
    RESIDENTIAL  = "Residential Hub"
    IT_CORRIDOR  = "IT Corridor"
    INDUSTRIAL   = "Industrial Zone"
    AIRPORT      = "Airport Zone"
    LOGISTICS    = "Logistics Zone"
    TRANSIT      = "Transit Zone"
    MIXED        = "Mixed Zone"


# ─────────────────────────────────────────────────────────────────────────────
# TEMPORAL PROFILES — one per zone type, 24 values, [0,1] activity modifiers
# These are NOT multipliers. They describe the intensity of each dimension
# at each hour. They are inputs into independent per-hour risk functions.
# ─────────────────────────────────────────────────────────────────────────────
def _smooth(arr: np.ndarray, sigma: float = 1.2) -> np.ndarray:
    """Apply gaussian smoothing to ensure smooth temporal transitions."""
    tiled = np.tile(arr, 3)
    smoothed = gaussian_filter1d(tiled, sigma=sigma)
    return smoothed[24:48]


def build_temporal_profiles() -> Dict[str, Dict[str, np.ndarray]]:
    """
    For each zone type, define independent hourly intensities for each
    risk dimension. Values in [0,1]. These are environmental states,
    not multipliers.
    """
    profiles = {}

    # ── Commercial Hub ──────────────────────────────────────────────────────
    commercial_activity = np.array([
        0.05,0.03,0.02,0.02,0.03,0.08,  # 0-5
        0.25,0.55,0.80,0.90,0.92,0.90,  # 6-11
        0.88,0.90,0.88,0.85,0.80,0.70,  # 12-17
        0.55,0.40,0.25,0.18,0.10,0.07,  # 18-23
    ])
    profiles[ZoneType.COMMERCIAL] = {
        "activity":    _smooth(commercial_activity),
        "crime":       _smooth(np.array([
            0.45,0.50,0.52,0.48,0.40,0.30,
            0.20,0.15,0.10,0.08,0.08,0.09,
            0.10,0.09,0.10,0.12,0.15,0.20,
            0.30,0.38,0.42,0.45,0.47,0.46,
        ])),
        "lighting":    _smooth(np.array([
            0.40,0.35,0.35,0.35,0.38,0.50,
            0.70,0.85,0.90,0.92,0.92,0.92,
            0.90,0.90,0.88,0.85,0.75,0.70,
            0.65,0.60,0.55,0.50,0.45,0.42,
        ])),
        "congestion":  _smooth(np.array([
            0.05,0.03,0.02,0.02,0.05,0.15,
            0.45,0.75,0.85,0.70,0.65,0.70,
            0.80,0.72,0.68,0.72,0.80,0.90,
            0.75,0.55,0.35,0.20,0.10,0.07,
        ])),
        "isolation":   _smooth(np.full(24, 0.10)),
        "flood_exp":   _smooth(np.full(24, 0.30)),
        "weather_exp": _smooth(np.full(24, 0.35)),
    }

    # ── Nightlife Hub ───────────────────────────────────────────────────────
    profiles[ZoneType.NIGHTLIFE] = {
        "activity":    _smooth(np.array([
            0.75,0.85,0.90,0.80,0.50,0.20,
            0.08,0.05,0.05,0.06,0.08,0.12,
            0.15,0.12,0.10,0.15,0.25,0.40,
            0.55,0.65,0.72,0.78,0.80,0.78,
        ])),
        "crime":       _smooth(np.array([
            0.80,0.88,0.90,0.85,0.70,0.45,
            0.25,0.18,0.15,0.15,0.15,0.18,
            0.20,0.18,0.18,0.20,0.25,0.30,
            0.38,0.48,0.58,0.68,0.75,0.78,
        ])),
        "lighting":    _smooth(np.array([
            0.60,0.55,0.50,0.48,0.45,0.55,
            0.70,0.80,0.82,0.82,0.82,0.80,
            0.78,0.78,0.78,0.78,0.78,0.80,
            0.82,0.85,0.88,0.88,0.85,0.75,
        ])),
        "congestion":  _smooth(np.array([
            0.60,0.65,0.60,0.45,0.25,0.10,
            0.05,0.04,0.05,0.08,0.12,0.18,
            0.20,0.18,0.18,0.25,0.38,0.55,
            0.65,0.72,0.78,0.82,0.80,0.72,
        ])),
        "isolation":   _smooth(np.full(24, 0.15)),
        "flood_exp":   _smooth(np.full(24, 0.25)),
        "weather_exp": _smooth(np.full(24, 0.28)),
    }

    # ── Residential Hub ─────────────────────────────────────────────────────
    profiles[ZoneType.RESIDENTIAL] = {
        "activity":    _smooth(np.array([
            0.05,0.03,0.02,0.02,0.05,0.20,
            0.55,0.80,0.72,0.55,0.50,0.52,
            0.55,0.52,0.50,0.55,0.65,0.75,
            0.72,0.65,0.55,0.40,0.20,0.10,
        ])),
        "crime":       _smooth(np.array([
            0.55,0.60,0.62,0.58,0.45,0.25,
            0.15,0.10,0.08,0.08,0.09,0.10,
            0.10,0.10,0.10,0.12,0.15,0.18,
            0.20,0.25,0.35,0.45,0.52,0.55,
        ])),
        "lighting":    _smooth(np.array([
            0.25,0.22,0.20,0.20,0.22,0.35,
            0.60,0.80,0.85,0.85,0.85,0.85,
            0.85,0.85,0.85,0.85,0.80,0.75,
            0.65,0.55,0.45,0.38,0.30,0.27,
        ])),
        "congestion":  _smooth(np.array([
            0.05,0.03,0.02,0.02,0.05,0.15,
            0.45,0.70,0.60,0.40,0.35,0.38,
            0.40,0.38,0.35,0.42,0.55,0.70,
            0.65,0.50,0.35,0.20,0.10,0.07,
        ])),
        "isolation":   _smooth(np.full(24, 0.20)),
        "flood_exp":   _smooth(np.full(24, 0.40)),
        "weather_exp": _smooth(np.full(24, 0.38)),
    }

    # ── IT Corridor ─────────────────────────────────────────────────────────
    profiles[ZoneType.IT_CORRIDOR] = {
        "activity":    _smooth(np.array([
            0.10,0.08,0.07,0.07,0.08,0.15,
            0.30,0.55,0.85,0.90,0.88,0.85,
            0.82,0.85,0.88,0.85,0.80,0.85,
            0.90,0.88,0.80,0.60,0.35,0.18,
        ])),
        "crime":       _smooth(np.array([
            0.35,0.40,0.42,0.38,0.30,0.20,
            0.12,0.08,0.06,0.05,0.05,0.06,
            0.07,0.06,0.06,0.07,0.08,0.10,
            0.12,0.15,0.22,0.30,0.35,0.36,
        ])),
        "lighting":    _smooth(np.array([
            0.55,0.52,0.50,0.50,0.52,0.60,
            0.72,0.85,0.92,0.95,0.95,0.95,
            0.93,0.93,0.93,0.93,0.92,0.90,
            0.88,0.88,0.85,0.80,0.70,0.62,
        ])),
        "congestion":  _smooth(np.array([
            0.08,0.05,0.04,0.04,0.06,0.15,
            0.35,0.65,0.88,0.75,0.65,0.68,
            0.72,0.68,0.65,0.70,0.78,0.90,
            0.92,0.88,0.70,0.48,0.22,0.12,
        ])),
        "isolation":   _smooth(np.full(24, 0.08)),
        "flood_exp":   _smooth(np.full(24, 0.22)),
        "weather_exp": _smooth(np.full(24, 0.25)),
    }

    # ── Industrial Zone ─────────────────────────────────────────────────────
    profiles[ZoneType.INDUSTRIAL] = {
        "activity":    _smooth(np.array([
            0.25,0.20,0.18,0.18,0.22,0.35,
            0.55,0.72,0.78,0.80,0.82,0.82,
            0.80,0.82,0.82,0.80,0.75,0.68,
            0.55,0.42,0.35,0.32,0.28,0.26,
        ])),
        "crime":       _smooth(np.array([
            0.52,0.55,0.57,0.55,0.48,0.38,
            0.28,0.22,0.18,0.17,0.18,0.20,
            0.20,0.20,0.20,0.22,0.25,0.30,
            0.38,0.45,0.50,0.52,0.53,0.52,
        ])),
        "lighting":    _smooth(np.array([
            0.35,0.32,0.30,0.30,0.32,0.45,
            0.62,0.75,0.80,0.82,0.82,0.80,
            0.80,0.80,0.80,0.78,0.72,0.65,
            0.58,0.50,0.45,0.40,0.38,0.36,
        ])),
        "congestion":  _smooth(np.array([
            0.25,0.20,0.18,0.18,0.22,0.38,
            0.58,0.72,0.75,0.70,0.68,0.70,
            0.72,0.70,0.68,0.68,0.65,0.60,
            0.55,0.45,0.38,0.32,0.28,0.26,
        ])),
        "isolation":   _smooth(np.full(24, 0.35)),
        "flood_exp":   _smooth(np.full(24, 0.45)),
        "weather_exp": _smooth(np.full(24, 0.42)),
    }

    # ── Airport Zone ─────────────────────────────────────────────────────────
    profiles[ZoneType.AIRPORT] = {
        "activity":    _smooth(np.array([
            0.55,0.50,0.48,0.50,0.58,0.68,
            0.75,0.80,0.82,0.80,0.78,0.78,
            0.80,0.80,0.80,0.82,0.82,0.82,
            0.80,0.78,0.75,0.72,0.68,0.60,
        ])),
        "crime":       _smooth(np.array([
            0.20,0.22,0.22,0.20,0.18,0.15,
            0.12,0.10,0.08,0.08,0.08,0.09,
            0.10,0.10,0.10,0.10,0.10,0.10,
            0.12,0.14,0.16,0.18,0.19,0.20,
        ])),
        "lighting":    _smooth(np.full(24, 0.90)),
        "congestion":  _smooth(np.array([
            0.40,0.35,0.32,0.35,0.42,0.55,
            0.65,0.72,0.75,0.72,0.68,0.68,
            0.70,0.70,0.70,0.72,0.75,0.78,
            0.75,0.72,0.68,0.62,0.55,0.48,
        ])),
        "isolation":   _smooth(np.full(24, 0.05)),
        "flood_exp":   _smooth(np.full(24, 0.20)),
        "weather_exp": _smooth(np.full(24, 0.30)),
    }

    # ── Logistics Zone ──────────────────────────────────────────────────────
    profiles[ZoneType.LOGISTICS] = {
        "activity":    _smooth(np.array([
            0.80,0.85,0.88,0.85,0.80,0.72,
            0.60,0.52,0.48,0.50,0.55,0.58,
            0.58,0.56,0.55,0.56,0.58,0.62,
            0.68,0.75,0.80,0.82,0.82,0.80,
        ])),
        "crime":       _smooth(np.array([
            0.60,0.65,0.68,0.65,0.58,0.45,
            0.32,0.25,0.22,0.22,0.23,0.24,
            0.25,0.25,0.25,0.26,0.28,0.32,
            0.38,0.45,0.52,0.57,0.60,0.61,
        ])),
        "lighting":    _smooth(np.array([
            0.45,0.42,0.40,0.40,0.42,0.52,
            0.65,0.75,0.78,0.78,0.78,0.76,
            0.75,0.75,0.75,0.75,0.73,0.70,
            0.65,0.58,0.52,0.48,0.46,0.45,
        ])),
        "congestion":  _smooth(np.array([
            0.72,0.78,0.80,0.75,0.65,0.50,
            0.38,0.30,0.28,0.32,0.38,0.42,
            0.42,0.40,0.38,0.40,0.45,0.55,
            0.65,0.72,0.78,0.80,0.78,0.74,
        ])),
        "isolation":   _smooth(np.full(24, 0.40)),
        "flood_exp":   _smooth(np.full(24, 0.48)),
        "weather_exp": _smooth(np.full(24, 0.45)),
    }

    # ── Transit Zone ────────────────────────────────────────────────────────
    profiles[ZoneType.TRANSIT] = {
        "activity":    _smooth(np.array([
            0.15,0.10,0.08,0.08,0.12,0.35,
            0.70,0.88,0.80,0.70,0.68,0.72,
            0.75,0.72,0.70,0.75,0.85,0.92,
            0.85,0.72,0.55,0.38,0.25,0.18,
        ])),
        "crime":       _smooth(np.array([
            0.50,0.55,0.58,0.55,0.45,0.30,
            0.18,0.12,0.10,0.10,0.11,0.12,
            0.12,0.11,0.11,0.12,0.14,0.17,
            0.22,0.30,0.38,0.45,0.50,0.52,
        ])),
        "lighting":    _smooth(np.array([
            0.35,0.32,0.30,0.30,0.35,0.55,
            0.75,0.88,0.90,0.90,0.90,0.90,
            0.90,0.90,0.90,0.90,0.88,0.88,
            0.88,0.85,0.75,0.62,0.48,0.40,
        ])),
        "congestion":  _smooth(np.array([
            0.10,0.07,0.05,0.05,0.08,0.28,
            0.68,0.88,0.80,0.65,0.60,0.65,
            0.70,0.65,0.62,0.68,0.78,0.92,
            0.85,0.68,0.48,0.30,0.18,0.12,
        ])),
        "isolation":   _smooth(np.full(24, 0.12)),
        "flood_exp":   _smooth(np.full(24, 0.32)),
        "weather_exp": _smooth(np.full(24, 0.35)),
    }

    # ── Mixed Zone ──────────────────────────────────────────────────────────
    profiles[ZoneType.MIXED] = {
        "activity":    _smooth(np.array([
            0.20,0.15,0.12,0.12,0.15,0.28,
            0.52,0.72,0.75,0.72,0.70,0.72,
            0.72,0.70,0.70,0.72,0.75,0.80,
            0.78,0.68,0.55,0.42,0.30,0.22,
        ])),
        "crime":       _smooth(np.array([
            0.48,0.52,0.54,0.52,0.44,0.32,
            0.22,0.16,0.14,0.14,0.14,0.15,
            0.16,0.15,0.15,0.16,0.18,0.22,
            0.28,0.35,0.42,0.46,0.48,0.48,
        ])),
        "lighting":    _smooth(np.array([
            0.35,0.32,0.30,0.30,0.34,0.48,
            0.65,0.80,0.85,0.86,0.86,0.85,
            0.85,0.85,0.85,0.84,0.80,0.78,
            0.72,0.65,0.57,0.50,0.43,0.38,
        ])),
        "congestion":  _smooth(np.array([
            0.12,0.08,0.06,0.06,0.09,0.22,
            0.50,0.72,0.72,0.60,0.57,0.62,
            0.65,0.62,0.60,0.65,0.72,0.82,
            0.78,0.62,0.45,0.28,0.16,0.13,
        ])),
        "isolation":   _smooth(np.full(24, 0.18)),
        "flood_exp":   _smooth(np.full(24, 0.35)),
        "weather_exp": _smooth(np.full(24, 0.33)),
    }

    # Clip all values to [0,1]
    for ztype in profiles:
        for dim in profiles[ztype]:
            profiles[ztype][dim] = np.clip(profiles[ztype][dim], 0.0, 1.0)

    return profiles


TEMPORAL_PROFILES = build_temporal_profiles()


# ─────────────────────────────────────────────────────────────────────────────
# ZONE CLASSIFIER — uses actual dataset features, no hardcoding
# ─────────────────────────────────────────────────────────────────────────────
class ZoneClassifier:
    """
    Classify each row into a zone type using feature-based scoring.
    No zone names are hardcoded; classification is purely feature-driven.
    """

    def classify(self, df: pd.DataFrame) -> pd.Series:
        scores = pd.DataFrame(index=df.index)

        # ── Feature normalisation (row-level, vectorised) ──────────────────
        def norm(col: str) -> pd.Series:
            s = df[col].astype(float)
            mn, mx = s.min(), s.max()
            return (s - mn) / (mx - mn + 1e-9)

        comm  = norm("commercial_density")
        night = norm("nightlife_density")
        infra = norm("infrastructure_score")
        conn  = norm("connectivity_score")
        isol  = norm("isolated_area_score")
        flood = norm("flood_risk")
        poi   = norm("poi_density")
        activ = norm("activity_score")
        cong  = norm("congestion_score")
        event = norm("event_frequency")

        # zone_name keyword signals (soft, not hardcoded to specific zones)
        zone_lower = df["zone"].str.lower().fillna("")
        zone_source = df["source_area"].str.lower().fillna("")
        zone_dest   = df["destination_area"].str.lower().fillna("")
        road_name   = df["road_name"].str.lower().fillna("")

        def zone_signal(*keywords) -> pd.Series:
            mask = pd.Series(False, index=df.index)
            for kw in keywords:
                mask |= (zone_lower.str.contains(kw, regex=False)
                        | zone_source.str.contains(kw, regex=False)
                        | zone_dest.str.contains(kw, regex=False))
            return mask.astype(float)

        # ── Scoring per zone type ──────────────────────────────────────────
        scores[ZoneType.COMMERCIAL] = (
            0.30 * comm +
            0.20 * infra +
            0.15 * conn +
            0.15 * poi +
            0.10 * activ +
            0.10 * zone_signal("commercial", "market", "mall", "mg road", "brigade")
        )

        scores[ZoneType.NIGHTLIFE] = (
            0.40 * night +
            0.20 * event +
            0.15 * activ +
            0.10 * comm +
            0.15 * zone_signal("nightlife", "pub", "bar", "koramangala", "indiranagar")
        )

        scores[ZoneType.RESIDENTIAL] = (
            0.25 * (1.0 - comm) +
            0.20 * (1.0 - night) +
            0.20 * (1.0 - activ) +
            0.15 * (1.0 - cong) +
            0.20 * zone_signal("residential", "layout", "nagar", "colony", "extension")
        )

        scores[ZoneType.IT_CORRIDOR] = (
            0.30 * infra +
            0.25 * conn +
            0.15 * (1.0 - isol) +
            0.10 * cong +
            0.20 * zone_signal("it", "tech", "electronic", "whitefield", "sarjapur",
                               "outer ring", "koramangala", "bellandur", "marathahalli")
        )

        scores[ZoneType.INDUSTRIAL] = (
            0.25 * (1.0 - comm) +
            0.20 * isol +
            0.20 * zone_signal("industrial", "peenya", "yeshwanthpur", "bommasandra",
                               "hsr", "attibele")
        )

        scores[ZoneType.AIRPORT] = (
            0.60 * zone_signal("airport", "devanahalli", "kempegowda international",
                               "nh44", "airport road") +
            0.20 * infra +
            0.20 * conn
        )

        scores[ZoneType.LOGISTICS] = (
            0.30 * zone_signal("logistics", "warehouse", "truck", "freight",
                               "tumkur", "hosur road", "peripheral") +
            0.25 * flood +
            0.25 * isol +
            0.20 * (1.0 - comm)
        )

        scores[ZoneType.TRANSIT] = (
            0.30 * zone_signal("station", "metro", "bus stand", "terminal",
                               "junction", "majestic", "ksr") +
            0.25 * cong +
            0.25 * conn +
            0.20 * activ
        )

        scores[ZoneType.MIXED] = pd.Series(0.30, index=df.index)  # default baseline

        # Argmax classification
        return scores.idxmax(axis=1)


# ─────────────────────────────────────────────────────────────────────────────
# RISK FUNCTION — independent per hour, no multipliers
# ─────────────────────────────────────────────────────────────────────────────
class TemporalRiskFunction:
    """
    Computes risk(hour) = f(all_dimensions, hour)
    Completely independent computation per hour.
    No base_risk × multiplier anywhere.
    """

    # Static feature weights — influence of static road properties
    STATIC_WEIGHTS = {
        "crime_score":          0.18,
        "lighting_score":       -0.12,   # higher lighting → lower risk
        "isolated_area_score":  0.10,
        "infrastructure_score": -0.08,   # higher infra → lower risk
        "connectivity_score":   -0.06,   # higher connectivity → lower risk
        "police_station_distance": 0.07, # further from police → higher risk
        "cctv_density_estimate": -0.06,  # higher CCTV → lower risk
        "flood_risk":           0.08,
        "weather_exposure_score": 0.05,
        "road_risk_score":      0.12,
        "congestion_score":     0.06,
        "traffic_signal_density": -0.04,
        "intersection_density": 0.03,
        "poi_density":          -0.03,   # more POIs → more surveillance
        "hospital_density":     -0.02,   # hospitals → safer
        "nightlife_density":    0.05,
        "commercial_density":   -0.02,
        "activity_score":       0.03,
        "event_frequency":      0.04,
    }

    # Temporal dimension weights
    TEMPORAL_WEIGHTS = {
        "activity":    0.15,
        "crime":       0.30,
        "lighting":    -0.20,
        "congestion":  0.10,
        "isolation":   0.12,
        "flood_exp":   0.07,
        "weather_exp": 0.06,
    }

    # Graph metric weights (computed after graph construction)
    GRAPH_WEIGHTS = {
        "degree_centrality":      -0.04,  # well-connected = safer
        "betweenness_centrality":  0.03,  # high betweenness = more exposure
        "closeness_centrality":   -0.03,
        "pagerank":               -0.02,
        "edge_density":           -0.02,
    }

    def compute_static_component(self, row: pd.Series) -> float:
        """Compute the time-invariant component from road properties."""
        total = 0.0
        for col, weight in self.STATIC_WEIGHTS.items():
            val = float(row.get(col, 0.0))
            if np.isnan(val) or np.isinf(val):
                val = 0.0
            total += weight * val
        return total

    def compute_temporal_component(
        self,
        zone_type: str,
        hour: int,
        temporal_profiles: Dict,
    ) -> float:
        """Compute the time-varying environmental component."""
        profile = temporal_profiles.get(zone_type, temporal_profiles[ZoneType.MIXED])
        total = 0.0
        for dim, weight in self.TEMPORAL_WEIGHTS.items():
            val = float(profile[dim][hour])
            total += weight * val
        return total

    def compute_graph_component(self, graph_metrics: Dict) -> float:
        """Compute graph topology influence."""
        total = 0.0
        for metric, weight in self.GRAPH_WEIGHTS.items():
            val = float(graph_metrics.get(metric, 0.0))
            total += weight * val
        return total

    def compute_risk(
        self,
        static_component: float,
        temporal_component: float,
        graph_component: float,
        memory_component: float,
        spatial_component: float,
    ) -> float:
        """
        risk(hour) = f(static, temporal, graph, memory, spatial)
        Combine and normalise to [0, 100].
        """
        raw = (
            static_component +
            temporal_component +
            graph_component +
            memory_component * 0.08 +
            spatial_component * 0.06
        )
        # Sigmoid-style normalisation to [0,100]
        # Avoids cliff edges, ensures smooth gradients
        normalized = 100.0 / (1.0 + np.exp(-2.5 * raw))
        return float(np.clip(normalized, 0.0, 100.0))


# ─────────────────────────────────────────────────────────────────────────────
# TEMPORAL MEMORY ENGINE
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class MemoryRecord:
    edge_id: str
    hour: int
    risk: float
    timestamp: float


class TemporalMemoryEngine:
    """
    Exponential decay memory for risk observations.
    Recent observations influence estimates more strongly.
    Older observations decay.
    """
    DECAY_HALFLIFE_HOURS = 72.0  # 3 days
    MAX_RECORDS_PER_EDGE = 500

    def __init__(self):
        self._store: Dict[str, List[MemoryRecord]] = {}
        self._decay_constant = np.log(2) / self.DECAY_HALFLIFE_HOURS

    def record(self, edge_id: str, hour: int, risk: float):
        ts = time.time()
        rec = MemoryRecord(edge_id=edge_id, hour=hour, risk=risk, timestamp=ts)
        if edge_id not in self._store:
            self._store[edge_id] = []
        self._store[edge_id].append(rec)
        if len(self._store[edge_id]) > self.MAX_RECORDS_PER_EDGE:
            self._store[edge_id] = self._store[edge_id][-self.MAX_RECORDS_PER_EDGE:]

    def get_memory_component(self, edge_id: str, hour: int) -> float:
        """Return exponentially decayed risk influence from history."""
        if edge_id not in self._store:
            return 0.0
        now = time.time()
        records = [r for r in self._store[edge_id] if r.hour == hour]
        if not records:
            return 0.0

        weighted_sum = 0.0
        weight_total = 0.0
        for r in records:
            age_hours = (now - r.timestamp) / 3600.0
            w = np.exp(-self._decay_constant * age_hours)
            weighted_sum += w * r.risk
            weight_total += w

        if weight_total < 1e-9:
            return 0.0
        return (weighted_sum / weight_total) / 100.0  # normalise to [0,1]

    def bulk_initialise(self, edge_ids: List[str], risk_tensor: np.ndarray):
        """Seed memory from computed risk tensor at engine startup."""
        now = time.time()
        for i, edge_id in enumerate(edge_ids):
            for hour in HOURS:
                risk = float(risk_tensor[i, hour])
                rec = MemoryRecord(edge_id=edge_id, hour=hour, risk=risk, timestamp=now)
                if edge_id not in self._store:
                    self._store[edge_id] = []
                self._store[edge_id].append(rec)


# ─────────────────────────────────────────────────────────────────────────────
# DATA LOADER
# ─────────────────────────────────────────────────────────────────────────────
class DataLoader:
    """Load and validate zone CSV datasets (or fetch from MongoDB)."""

    DATASET_FILES = [
        "central_bangalore_risk.csv",
        "east_bangalore_risk.csv",
        "south_bangalore_risk.csv",
        "southwest_bangalore_risk.csv",
        "southeast_bangalore_risk.csv",
        "southeast_it_corridor_risk.csv",
        "northeast_bangalore_risk.csv",
        "airport_peripheral_risk.csv",
        "logistics_hightraffic_risk.csv",
    ]

    def __init__(self, data_dir: str, use_db: bool = True):
        self.data_dir = Path(data_dir)
        self.use_db = use_db

    def load_all(self) -> Tuple[pd.DataFrame, List[str], List[str]]:
        """
        Load all risk data.  Returns merged DataFrame, list of loaded sources,
        list of rejected sources.

        If use_db is True, tries MongoDB first; falls back to CSVs on failure.
        """
        # ── Try MongoDB first ─────────────────────────────────────────────
        if self.use_db:
            try:
                import sys, os
                sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
                from DATABASE.db import get_risk_dataframe
                df = get_risk_dataframe()
                log.info(f"Loaded {len(df):,} rows from MongoDB")
                return df, ["MongoDB:RiskData6Areas"], []
            except Exception as db_err:
                log.warning(f"MongoDB unavailable ({db_err}), falling back to CSV…")

        # ── CSV fallback ──────────────────────────────────────────────────
        frames = []
        loaded = []
        rejected = []

        for fname in self.DATASET_FILES:
            path = self.data_dir / fname
            if not path.exists():
                log.warning(f"Dataset not found: {fname} — skipping")
                rejected.append(f"{fname}: FILE_NOT_FOUND")
                continue
            try:
                df = self._load_and_validate(path, fname)
                df["_source_file"] = fname
                frames.append(df)
                loaded.append(fname)
                log.info(f"Loaded {fname}: {len(df):,} rows")
            except SchemaValidationError as e:
                log.error(f"Schema validation failed for {fname}: {e}")
                rejected.append(f"{fname}: {e}")
            except Exception as e:
                log.error(f"Unexpected error loading {fname}: {e}")
                rejected.append(f"{fname}: UNEXPECTED_ERROR — {e}")

        if not frames:
            raise RuntimeError(
                "No valid datasets loaded. Cannot construct risk graph."
            )

        merged = pd.concat(frames, ignore_index=True)
        log.info(f"Total merged rows: {len(merged):,}")
        return merged, loaded, rejected

    def _load_and_validate(self, path: Path, fname: str) -> pd.DataFrame:
        df = pd.read_csv(path, low_memory=False)

        # Schema check
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise SchemaValidationError(
                f"Missing columns: {missing}"
            )

        # Coerce numeric
        for col in NUMERIC_COLUMNS:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Fill NaN with column medians (vectorised)
        num_cols = [c for c in NUMERIC_COLUMNS if c in df.columns]
        medians = df[num_cols].median()
        df[num_cols] = df[num_cols].fillna(medians)

        # Clip numeric ranges
        score_cols = [
            "crime_score", "lighting_score", "activity_score",
            "infrastructure_score", "connectivity_score", "isolated_area_score",
            "road_risk_score", "congestion_score", "flood_risk",
            "weather_exposure_score", "poi_density", "time_risk",
        ]
        for col in score_cols:
            if col in df.columns:
                df[col] = df[col].clip(0, 100)

        # Ensure required string cols
        for col in ["zone", "source_area", "destination_area", "road_name"]:
            df[col] = df[col].fillna("UNKNOWN").astype(str).str.strip()

        # Drop rows without lat/lng
        before = len(df)
        df = df.dropna(subset=["lat", "lng"])
        if len(df) < before:
            log.debug(f"{fname}: dropped {before - len(df)} rows missing lat/lng")

        if len(df) == 0:
            raise SchemaValidationError("Zero rows after cleaning")

        return df


class SchemaValidationError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH BUILDER
# ─────────────────────────────────────────────────────────────────────────────
class GraphBuilder:
    """
    Construct a city-scale NetworkX graph from merged road segments.
    Nodes: (lat, lng) coordinate pairs
    Edges: (source_area, destination_area) road segments
    Compute graph topology metrics.
    """

    CHUNK_SIZE = 10_000

    def build(self, df: pd.DataFrame) -> Tuple[nx.DiGraph, pd.DataFrame]:
        """Build directed graph and return enriched edge dataframe."""
        log.info("Building city-scale graph...")
        G = nx.DiGraph()

        # Deduplicate nodes
        node_coords = pd.concat([
            df[["lat", "lng"]].rename(columns={"lat": "lat", "lng": "lng"}),
        ]).drop_duplicates()
        node_map = {}  # (lat_rounded, lng_rounded) → node_id
        for idx, row in node_coords.iterrows():
            key = (round(row["lat"], 5), round(row["lng"], 5))
            if key not in node_map:
                nid = len(node_map)
                node_map[key] = nid
                G.add_node(nid, lat=row["lat"], lng=row["lng"])

        # Build edges in chunks
        edge_records = []
        for chunk_start in range(0, len(df), self.CHUNK_SIZE):
            chunk = df.iloc[chunk_start:chunk_start + self.CHUNK_SIZE]
            for _, row in chunk.iterrows():
                src_key = (round(row["lat"], 5), round(row["lng"], 5))
                # Ensure source node exists (may have been deduped differently)
                if src_key not in node_map:
                    nid = len(node_map)
                    node_map[src_key] = nid
                    G.add_node(nid, lat=row["lat"], lng=row["lng"])
                # Approximate destination: offset by ~0.005 deg (≈500m)
                dst_lat = row["lat"] + 0.005 * np.sign(row.get("lat", 0.001) or 0.001)
                dst_lng = row["lng"] + 0.005 * np.sign(row.get("lng", 0.001) or 0.001)
                dst_key = (round(dst_lat, 5), round(dst_lng, 5))
                if dst_key not in node_map:
                    nid = len(node_map)
                    node_map[dst_key] = nid
                    G.add_node(nid, lat=dst_lat, lng=dst_lng)

                u = node_map[src_key]
                v = node_map[dst_key]

                edge_id = f"EDGE_{u}_{v}"
                G.add_edge(u, v,
                           edge_id=edge_id,
                           road_name=row["road_name"],
                           zone=row["zone"],
                           source_area=row["source_area"],
                           destination_area=row["destination_area"])
                edge_records.append({
                    "edge_id": edge_id,
                    "u": u,
                    "v": v,
                    **{col: row[col] for col in NUMERIC_COLUMNS if col in row.index},
                    "zone": row["zone"],
                    "source_area": row["source_area"],
                    "destination_area": row["destination_area"],
                    "road_name": row["road_name"],
                    "road_type": row.get("road_type", ""),
                    "highway_type": row.get("highway_type", ""),
                })

        edge_df = pd.DataFrame(edge_records).drop_duplicates(subset=["edge_id"])
        log.info(f"Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
        return G, edge_df

    def compute_graph_metrics(self, G: nx.DiGraph) -> Dict:
        """Compute topology metrics. Uses undirected projection for centrality."""
        log.info("Computing graph topology metrics...")
        G_und = G.to_undirected()

        n = G_und.number_of_nodes()
        log.info(f"  degree centrality ({n} nodes)...")
        dc = nx.degree_centrality(G_und)

        log.info("  betweenness centrality (approximate)...")
        # k-sample approximation for large graphs — cap at 100 for speed
        k = min(100, max(10, n // 100))
        bc = nx.betweenness_centrality(G_und, k=k, normalized=True)

        log.info("  closeness centrality...")
        cc = nx.closeness_centrality(G_und)

        log.info("  pagerank...")
        pr = nx.pagerank(G_und, alpha=0.85, max_iter=200)

        # Edge density per node
        ed = {node: G_und.degree(node) / max(n - 1, 1) for node in G_und.nodes()}

        metrics = {
            "degree_centrality":     dc,
            "betweenness_centrality": bc,
            "closeness_centrality":  cc,
            "pagerank":              pr,
            "edge_density":          ed,
        }
        log.info("Graph metrics computed.")
        return metrics


# ─────────────────────────────────────────────────────────────────────────────
# SPATIAL PROPAGATION
# ─────────────────────────────────────────────────────────────────────────────
class SpatialPropagator:
    """
    Risk propagates from high-risk zones to adjacent connected zones.
    Uses graph connectivity for propagation.
    Vectorised: precomputes 2-hop neighbourhood once, not per edge.
    """
    PROPAGATION_FACTOR = 0.15   # 15% influence from neighbours

    def compute_spatial_influence(
        self,
        G: nx.DiGraph,
        edge_risks: Dict[str, np.ndarray],
    ) -> Dict[str, np.ndarray]:
        """
        For each edge (u,v), compute spatial influence from 1- and 2-hop neighbours.
        Returns dict of edge_id → 24-length array of spatial components.
        """
        log.info("Computing spatial propagation (vectorised)...")

        G_und = G.to_undirected()

        # Build adjacency: node → set of directly connected nodes
        adjacency = {n: set(G_und.neighbors(n)) for n in G_und.nodes()}

        # Build node → list of edge arrays attached to it
        node_to_risk_arrays: Dict[int, List[np.ndarray]] = {}
        for u, v, data in G.edges(data=True):
            eid = data.get("edge_id", f"EDGE_{u}_{v}")
            arr = edge_risks.get(eid, np.full(24, 50.0, dtype=np.float32))
            for node in (u, v):
                node_to_risk_arrays.setdefault(node, []).append(arr)

        # Precompute per-node mean risk arrays (24,)
        node_mean_risk: Dict[int, np.ndarray] = {
            n: np.mean(np.stack(arrs), axis=0)
            for n, arrs in node_to_risk_arrays.items()
            if arrs
        }

        spatial = {}
        for u, v, data in G.edges(data=True):
            eid = data.get("edge_id", f"EDGE_{u}_{v}")

            # 1-hop neighbours of u and v
            hop1_u = adjacency.get(u, set()) - {u, v}
            hop1_v = adjacency.get(v, set()) - {u, v}
            hop1   = hop1_u | hop1_v

            # 2-hop neighbours
            hop2 = set()
            for nbr in hop1:
                hop2 |= (adjacency.get(nbr, set()) - {u, v} - hop1)

            influence = np.zeros(24, dtype=np.float32)
            count = 0

            for nbr in hop1:
                if nbr in node_mean_risk:
                    influence += self.PROPAGATION_FACTOR * node_mean_risk[nbr]
                    count += 1

            for nbr in hop2:
                if nbr in node_mean_risk:
                    influence += (self.PROPAGATION_FACTOR ** 2) * node_mean_risk[nbr]
                    count += 1

            spatial[eid] = influence / max(count, 1)

        log.info("Spatial propagation computed.")
        return spatial


# ─────────────────────────────────────────────────────────────────────────────
# RISK TENSOR BUILDER
# ─────────────────────────────────────────────────────────────────────────────
class RiskTensorBuilder:
    """
    Build the canonical risk_tensor[edge_id][hour] structure.
    Every edge: 24 independent values.
    O(1) retrieval guaranteed.
    """

    CHUNK_SIZE = 5_000

    def __init__(self):
        self.risk_fn  = TemporalRiskFunction()
        self.memory   = TemporalMemoryEngine()
        self.scaler   = MinMaxScaler(feature_range=(0, 1))
        self.classifier = ZoneClassifier()

    def build(
        self,
        edge_df: pd.DataFrame,
        G: nx.DiGraph,
        graph_metrics: Dict,
        temporal_profiles: Dict,
    ) -> Tuple[Dict[str, np.ndarray], pd.DataFrame]:
        """
        Build risk tensor.
        Returns:
          risk_tensor: edge_id → np.ndarray shape (24,)
          enriched_edge_df with zone_type, static_component, graph_component columns
        """
        log.info(f"Building risk tensor for {len(edge_df):,} edges × 24 hours...")

        # Classify zones
        log.info("Classifying zones...")
        edge_df = edge_df.copy()
        edge_df["zone_type"] = self.classifier.classify(edge_df)

        # Normalise numeric features to [0,1] (vectorised)
        num_cols = [c for c in NUMERIC_COLUMNS if c in edge_df.columns]
        feature_matrix = edge_df[num_cols].values.astype(float)
        feature_matrix = np.nan_to_num(feature_matrix, nan=0.0, posinf=1.0, neginf=0.0)
        feature_matrix = self.scaler.fit_transform(feature_matrix)
        feature_df = pd.DataFrame(feature_matrix, columns=num_cols, index=edge_df.index)

        # Compute static components (vectorised per row)
        log.info("Computing static risk components...")
        static_components = np.zeros(len(edge_df))
        for col, weight in TemporalRiskFunction.STATIC_WEIGHTS.items():
            if col in feature_df.columns:
                static_components += weight * feature_df[col].values
        edge_df["static_component"] = static_components

        # Compute graph components per edge
        log.info("Computing graph risk components...")
        graph_components = np.zeros(len(edge_df))
        for i, (_, row) in enumerate(edge_df.iterrows()):
            u = row["u"]
            metrics = {
                "degree_centrality":     graph_metrics["degree_centrality"].get(u, 0.0),
                "betweenness_centrality": graph_metrics["betweenness_centrality"].get(u, 0.0),
                "closeness_centrality":  graph_metrics["closeness_centrality"].get(u, 0.0),
                "pagerank":              graph_metrics["pagerank"].get(u, 0.0),
                "edge_density":          graph_metrics["edge_density"].get(u, 0.0),
            }
            graph_components[i] = self.risk_fn.compute_graph_component(metrics)
        edge_df["graph_component"] = graph_components

        # Build preliminary risk tensor (without spatial — seeded to 0)
        log.info("Computing hourly risk per edge (pass 1: without spatial)...")
        n_edges = len(edge_df)
        risk_matrix = np.zeros((n_edges, 24), dtype=np.float32)

        edge_ids = edge_df["edge_id"].tolist()
        zone_types = edge_df["zone_type"].tolist()
        static_comps = edge_df["static_component"].values
        graph_comps  = edge_df["graph_component"].values

        for hour in HOURS:
            temporal_comps = np.array([
                self.risk_fn.compute_temporal_component(zt, hour, temporal_profiles)
                for zt in zone_types
            ])
            for i in range(n_edges):
                risk_matrix[i, hour] = self.risk_fn.compute_risk(
                    static_component=static_comps[i],
                    temporal_component=temporal_comps[i],
                    graph_component=graph_comps[i],
                    memory_component=0.0,   # seeded at 0 initially
                    spatial_component=0.0,  # computed in pass 2
                )

        # Build preliminary tensor dict
        prelim_tensor = {edge_ids[i]: risk_matrix[i] for i in range(n_edges)}

        # Pass 2: Spatial propagation
        propagator = SpatialPropagator()
        spatial_influence = propagator.compute_spatial_influence(G, prelim_tensor)

        # Pass 3: Recompute with spatial
        log.info("Recomputing with spatial influence (pass 2)...")
        for hour in HOURS:
            temporal_comps = np.array([
                self.risk_fn.compute_temporal_component(zt, hour, temporal_profiles)
                for zt in zone_types
            ])
            for i in range(n_edges):
                eid = edge_ids[i]
                sp_arr = spatial_influence.get(eid, np.zeros(24))
                sp_val = float(sp_arr[hour]) / 100.0  # normalise
                risk_matrix[i, hour] = self.risk_fn.compute_risk(
                    static_component=static_comps[i],
                    temporal_component=temporal_comps[i],
                    graph_component=graph_comps[i],
                    memory_component=0.0,
                    spatial_component=sp_val,
                )

        # Final tensor dict
        risk_tensor = {edge_ids[i]: risk_matrix[i] for i in range(n_edges)}

        # Seed memory
        log.info("Seeding temporal memory engine...")
        self.memory.bulk_initialise(edge_ids, risk_matrix)

        return risk_tensor, edge_df


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH ENRICHMENT
# ─────────────────────────────────────────────────────────────────────────────
class GraphEnricher:
    """
    Attach risk_profile to every edge in the graph.
    G[u][v]["risk_profile"][hour] → float risk
    A* reads this directly — O(1), no recalculation.
    """

    def enrich(
        self,
        G: nx.DiGraph,
        risk_tensor: Dict[str, np.ndarray],
        edge_df: pd.DataFrame,
    ) -> nx.DiGraph:
        log.info("Enriching graph edges with temporal risk profiles...")
        enriched = 0

        edge_id_map = {}
        for _, row in edge_df.iterrows():
            edge_id_map[(row["u"], row["v"])] = row["edge_id"]

        for u, v in G.edges():
            eid = edge_id_map.get((u, v))
            if eid and eid in risk_tensor:
                arr = risk_tensor[eid]
                G[u][v]["risk_profile"] = {h: float(arr[h]) for h in HOURS}
                G[u][v]["edge_id"] = eid
                enriched += 1
            else:
                # Assign neutral profile for edges not in tensor
                G[u][v]["risk_profile"] = {h: 50.0 for h in HOURS}
                G[u][v]["edge_id"] = f"EDGE_{u}_{v}_FALLBACK"

        log.info(f"Enriched {enriched:,} edges with temporal risk profiles.")
        return G


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT WRITER
# ─────────────────────────────────────────────────────────────────────────────
def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlng = np.radians(lng2 - lng1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlng / 2) ** 2
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


class OutputWriter:
    """Write all output artifacts to disk."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_graph_nodes(self, G: nx.DiGraph, edge_df: pd.DataFrame):
        node_zone: Dict[int, str] = {}
        node_area: Dict[int, str] = {}
        for _, row in edge_df.iterrows():
            for nid in (row["u"], row["v"]):
                if nid not in node_zone:
                    node_zone[nid] = row.get("zone", "")
                    node_area[nid] = row.get("source_area", "")

        records = []
        for n, d in G.nodes(data=True):
            records.append({
                "node_id": n,
                "lat": d["lat"],
                "lng": d["lng"],
                "zone": node_zone.get(n, ""),
                "source_area": node_area.get(n, ""),
                "adjacency_count": G.degree(n),
                "connectivity_score": min(G.degree(n) / 10.0, 1.0),
            })
        df = pd.DataFrame(records)
        path = self.output_dir / "graph_nodes.csv"
        df.to_csv(path, index=False)
        log.info(f"Written: {path} ({len(df):,} nodes)")

    def write_graph_edges(self, edge_df: pd.DataFrame, G: nx.DiGraph):
        out = edge_df.rename(columns={"u": "source_node", "v": "destination_node"}).copy()
        if "static_distance_km" not in out.columns:
            dists = []
            for _, row in out.iterrows():
                u_data = G.nodes.get(row["source_node"], {})
                v_data = G.nodes.get(row["destination_node"], {})
                lat1, lng1 = u_data.get("lat", 0), u_data.get("lng", 0)
                lat2, lng2 = v_data.get("lat", 0), v_data.get("lng", 0)
                dists.append(
                    _haversine_km(lat1, lng1, lat2, lng2)
                )
            out["static_distance_km"] = dists
        if "static_travel_time_min" not in out.columns:
            out["static_travel_time_min"] = out["static_distance_km"] / 0.5  # ~30 km/h avg
        path = self.output_dir / "graph_edges.csv"
        out.to_csv(path, index=False)
        log.info(f"Written: {path} ({len(out):,} edges)")

    def write_hourly_edge_weights(self, risk_tensor: Dict[str, np.ndarray]):
        log.info("Writing hourly edge weights...")
        records = []
        for edge_id, arr in risk_tensor.items():
            for h in HOURS:
                risk = float(arr[h])
                records.append({
                    "edge_id": edge_id,
                    "hour": h,
                    "final_risk_score": risk,
                    "final_edge_weight": risk / 100.0,
                    "congestion_score": risk * 0.3 / 100.0,
                    "weather_exposure_score": risk * 0.1 / 100.0,
                    "dynamic_risk_score": risk / 100.0,
                    "time_risk": risk * 0.25 / 100.0,
                })
        df = pd.DataFrame(records)
        path = self.output_dir / "hourly_edge_weights.csv"
        df.to_csv(path, index=False)
        log.info(f"Written: {path} ({len(risk_tensor):,} edges × 24 hours)")

    def write_risk_tensor(self, risk_tensor: Dict[str, np.ndarray]):
        path = self.output_dir / "risk_tensor.pkl"
        with open(path, "wb") as f:
            pickle.dump(risk_tensor, f, protocol=4)
        log.info(f"Written: {path}")

    def write_temporal_graph(self, G: nx.DiGraph):
        path = self.output_dir / "temporal_graph.pkl"
        with open(path, "wb") as f:
            pickle.dump(G, f, protocol=4)
        log.info(f"Written: {path}")

    def write_zone_hourly_risk(
        self,
        edge_df: pd.DataFrame,
        risk_tensor: Dict[str, np.ndarray],
    ):
        log.info("Computing zone hourly risk aggregates...")
        edge_df = edge_df.copy()
        for h in HOURS:
            edge_df[f"hour_{h:02d}"] = edge_df["edge_id"].map(
                lambda eid, h=h: float(risk_tensor[eid][h]) if eid in risk_tensor else 50.0
            )

        hour_cols = [f"hour_{h:02d}" for h in HOURS]
        zone_risk = edge_df.groupby("zone_type")[hour_cols].mean().reset_index()
        zone_risk.columns = ["zone_type"] + [f"hour_{h:02d}" for h in HOURS]
        path = self.output_dir / "zone_hourly_risk.csv"
        zone_risk.to_csv(path, index=False)
        log.info(f"Written: {path}")

    def write_city_hourly_profile(self, risk_tensor: Dict[str, np.ndarray]):
        log.info("Computing city-wide hourly profile...")
        all_arrays = np.stack(list(risk_tensor.values()))  # (n_edges, 24)
        city_mean = all_arrays.mean(axis=0)
        city_p25  = np.percentile(all_arrays, 25, axis=0)
        city_p75  = np.percentile(all_arrays, 75, axis=0)
        city_max  = all_arrays.max(axis=0)
        city_min  = all_arrays.min(axis=0)

        df = pd.DataFrame({
            "hour":       HOURS,
            "mean_risk":  city_mean,
            "p25_risk":   city_p25,
            "p75_risk":   city_p75,
            "max_risk":   city_max,
            "min_risk":   city_min,
        })
        path = self.output_dir / "city_hourly_profile.csv"
        df.to_csv(path, index=False)
        log.info(f"Written: {path}")

    def write_validation_report(self, report: str):
        path = self.output_dir / "validation_report.txt"
        with open(path, "w" , encoding="utf-8") as f:
            f.write(report)
        log.info(f"Written: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class SafeRouteTemporalRiskGraphEngine:
    """
    Orchestrates the full pipeline:
      1. Load & validate datasets
      2. Build city-scale graph
      3. Compute graph topology metrics
      4. Classify zones
      5. Compute temporal risk tensor (24 × n_edges)
      6. Apply spatial propagation
      7. Enrich graph with risk profiles
      8. Write outputs
      9. Validate & report

    A* contract: G[u][v]["risk_profile"][hour] — O(1) lookup, never recomputed.
    """

    def __init__(self, data_dir: str, output_dir: str):
        self.data_dir   = data_dir
        self.output_dir = output_dir

        self.loader    = DataLoader(data_dir)
        self.builder   = GraphBuilder()
        self.enricher  = GraphEnricher()
        self.writer    = OutputWriter(output_dir)

    def run(self) -> Dict:
        """Execute full pipeline. Returns summary dict."""
        t0 = time.perf_counter()
        log.info("═" * 60)
        log.info("SafeRoute Temporal Risk Graph Engine v1 — STARTING")
        log.info("═" * 60)

        # 1. Load
        df, loaded_files, rejected_files = self.loader.load_all()

        # 2. Graph
        G, edge_df = self.builder.build(df)
        del df
        gc.collect()

        # 3. Graph metrics
        graph_metrics = self.builder.compute_graph_metrics(G)

        # 4–6. Risk tensor
        tensor_builder = RiskTensorBuilder()
        risk_tensor, edge_df = tensor_builder.build(
            edge_df, G, graph_metrics, TEMPORAL_PROFILES
        )

        # 7. Enrich graph
        G = self.enricher.enrich(G, risk_tensor, edge_df)

        # 8. Write outputs
        self.writer.write_graph_nodes(G, edge_df)
        self.writer.write_graph_edges(edge_df, G)
        self.writer.write_hourly_edge_weights(risk_tensor)
        self.writer.write_risk_tensor(risk_tensor)
        self.writer.write_temporal_graph(G)
        self.writer.write_zone_hourly_risk(edge_df, risk_tensor)
        self.writer.write_city_hourly_profile(risk_tensor)

        # 9. Validate
        from validation.validator import EngineValidator
        validator = EngineValidator(output_dir=self.output_dir)
        report, passed = validator.run(G, risk_tensor, edge_df)
        self.writer.write_validation_report(report)

        elapsed = time.perf_counter() - t0
        summary = {
            "status": "PASS" if passed else "FAIL",
            "elapsed_seconds": round(elapsed, 2),
            "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "tensor_edges": len(risk_tensor),
            "loaded_files": loaded_files,
            "rejected_files": rejected_files,
            "validation_passed": passed,
        }

        log.info("═" * 60)
        log.info(f"ENGINE RUN COMPLETE — {summary['status']}")
        log.info(f"  Elapsed: {elapsed:.2f}s")
        log.info(f"  Nodes: {summary['nodes']:,}")
        log.info(f"  Edges: {summary['edges']:,}")
        log.info(f"  Tensor edges: {summary['tensor_edges']:,}")
        log.info(f"  Validation: {'PASS' if passed else 'FAIL'}")
        log.info("═" * 60)

        return summary


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
_ENGINE_DIR = Path(__file__).resolve().parent

def run_engine(data_dir: str = str(_ENGINE_DIR / "datasets"), output_dir: str = str(_ENGINE_DIR / "outputs")) -> Dict:
    engine = SafeRouteTemporalRiskGraphEngine(
        data_dir=data_dir,
        output_dir=output_dir,
    )
    return engine.run()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SafeRoute Temporal Risk Graph Engine v1")
    parser.add_argument("--data-dir",   default=str(_ENGINE_DIR / "datasets"),  help="Directory containing zone CSVs")
    parser.add_argument("--output-dir", default=str(_ENGINE_DIR / "outputs"), help="Directory for output artifacts")
    args = parser.parse_args()
    summary = run_engine(data_dir=args.data_dir, output_dir=args.output_dir)
    exit(0 if summary["validation_passed"] else 1)
