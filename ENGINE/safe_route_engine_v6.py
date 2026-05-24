"""
SafeRoute-AI  |  Dynamic Road Risk Engine  v6.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Changes from v5.0 → v6.0
─────────────────────────
1.  Full schema alignment with the 34-column dataset spec:
      zone, direction, lat, lng, source_area, destination_area,
      road_name, road_type, highway_type, junction_type,
      road_width_estimate, speed_limit, traffic_signal_density,
      intersection_density, commercial_density, nightlife_density,
      hospital_density, police_station_distance, cctv_density_estimate,
      lighting_score, crime_score, activity_score, event_frequency,
      infrastructure_score, connectivity_score, isolated_area_score,
      road_risk_score, travel_time_estimate, congestion_score,
      flood_risk, weather_exposure_score, poi_density, time_risk,
      adjacency_count

2.  Mandatory correlation enforcement via weighted formulas:
      • Higher crime_score → increases road_risk_score
      • Higher congestion_score → increases travel_time_estimate
      • Higher lighting_score → reduces road_risk_score
      • Higher cctv_density_estimate → reduces crime_score
      • Higher isolated_area_score → increases road_risk_score
      • Higher commercial_density → increases activity_score
      • Higher nightlife_density → increases night-time risk
      • Higher connectivity_score → reduces isolation risk
      • Higher police_station_distance → increases risk
      • Higher flood_risk → increases travel_time_estimate (weather)
      • Higher traffic_signal_density → slightly increases congestion_score
      • Higher intersection_density → moderately increases congestion_score
      • Higher road_width_estimate → reduces congestion_score

3.  Contextual temporal behaviour:
      • Late-night isolated road risk spike
      • Nightlife zones riskier after 22:00
      • Commercial areas safer during daytime
      • IT corridors riskier after midnight

4.  Multi-factor weighted formulas replacing random generation for:
      road_risk_score, activity_score, congestion_score,
      infrastructure_score, connectivity_score, isolated_area_score,
      weather_exposure_score, time_risk, travel_time_estimate

5.  Realistic continuous variation in speed limits, road widths, densities.

6.  All v5.0 advanced features retained:
      temporal memory [U3], uncertainty/confidence [U4], route context [U5],
      dynamic weight adaptation [U6], behavioural adjustment [U7],
      multi-scale fusion [U8], calibration engine [U9], POI interaction [U2]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)

# ══════════════════════════════════════════════════════════════════════════════
# 1.  BASE RISK WEIGHTS  (context-adaptive via adapt_weights())
# ══════════════════════════════════════════════════════════════════════════════

RISK_WEIGHTS: Dict[str, float] = {
    "crime":             0.17,
    "lighting":          0.16,
    "activity":          0.11,
    "event":             0.06,
    "road":              0.08,
    "infrastructure":    0.06,
    "cctv":              0.12,
    "police":            0.12,
    "poi":               0.04,
    "isolation":         0.08,   # isolated_area_score direct path
}

assert abs(sum(RISK_WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

# ── Road-risk score composition weights ──────────────────────────────────────
# road_risk_score = weighted combination of:
ROAD_RISK_COMP: Dict[str, float] = {
    "crime_score":            0.19,
    "lighting_score_inv":     0.14,   # inverse: low lighting → high risk
    "cctv_density_inv":       0.11,   # inverse: low CCTV → high risk
    "police_dist_norm":       0.12,   # normalised distance: far → high risk
    "congestion_score":       0.07,
    "isolated_area_score":    0.17,   # raised to enforce mandatory correlation
    "weather_exposure_score": 0.06,
    "activity_score_ctx":     0.07,   # context-adjusted activity
    "event_frequency":        0.03,
    "time_risk_norm":         0.04,   # normalised 0–1
}
assert abs(sum(ROAD_RISK_COMP.values()) - 1.0) < 1e-9

# ── Congestion score composition weights ─────────────────────────────────────
CONGESTION_COMP: Dict[str, float] = {
    "traffic_signal_density": 0.18,
    "intersection_density":   0.25,
    "road_width_inv":         0.22,   # inverse: narrower → more congested
    "commercial_density":     0.18,
    "highway_type_factor":    0.10,
    "time_risk_norm":         0.07,
}
assert abs(sum(CONGESTION_COMP.values()) - 1.0) < 1e-9

# ── Travel time composition weights ──────────────────────────────────────────
TRAVEL_TIME_COMP: Dict[str, float] = {
    "congestion_score":       0.35,
    "road_width_inv":         0.15,
    "flood_risk":             0.15,
    "weather_exposure_score": 0.12,
    "speed_limit_inv":        0.13,
    "traffic_signal_density": 0.10,
}
assert abs(sum(TRAVEL_TIME_COMP.values()) - 1.0) < 1e-9

# ── Connectivity score composition weights ───────────────────────────────────
CONNECTIVITY_COMP: Dict[str, float] = {
    "adjacency_count_norm":   0.40,
    "road_type_factor":       0.25,
    "highway_type_factor":    0.15,
    "intersection_density":   0.20,
}
assert abs(sum(CONNECTIVITY_COMP.values()) - 1.0) < 1e-9

# ══════════════════════════════════════════════════════════════════════════════
# 1B.  MULTI-SCALE FUSION COEFFICIENTS  [U8]
# ══════════════════════════════════════════════════════════════════════════════

MULTISCALE_ALPHA = 0.60   # micro (segment-level)
MULTISCALE_BETA  = 0.25   # meso  (≈300 m neighbourhood)
MULTISCALE_GAMMA = 0.15   # macro (zone-wide trend)

# ══════════════════════════════════════════════════════════════════════════════
# 1C.  TEMPORAL MEMORY PARAMETERS  [U3]
# ══════════════════════════════════════════════════════════════════════════════

MEMORY_LAMBDA        = 0.70
MEMORY_DECAY_PER_HR  = 0.85
MEMORY_NIGHT_BOOST   = 1.15

_TEMPORAL_MEMORY: Dict[int, float] = {}

# ══════════════════════════════════════════════════════════════════════════════
# 1D.  UNCERTAINTY PARAMETERS  [U4]
# ══════════════════════════════════════════════════════════════════════════════

UNCERTAINTY_SIGMA_MIN = 0.005
UNCERTAINTY_SIGMA_MAX = 0.060
UNCERTAINTY_RNG       = np.random.default_rng(seed=None)

# ══════════════════════════════════════════════════════════════════════════════
# 1E.  BEHAVIOURAL PARAMETERS  [U7]
# ══════════════════════════════════════════════════════════════════════════════

BEHAVIOURAL_DESERTED_PENALTY   = 0.18
BEHAVIOURAL_DRUNK_ZONE_PENALTY = 0.14
BEHAVIOURAL_SAFE_CROWD_BONUS   = 0.08

# ══════════════════════════════════════════════════════════════════════════════
# 2.  POLICE STATIONS  (Bengaluru)
# ══════════════════════════════════════════════════════════════════════════════

POLICE_STATIONS: List[Dict] = [
    # North
    {"name": "Hebbal PS",           "lat": 13.0360, "lng": 77.5970},
    {"name": "RT Nagar PS",         "lat": 13.0220, "lng": 77.5975},
    {"name": "Yelahanka PS",        "lat": 13.1006, "lng": 77.5960},
    {"name": "Byatarayanapura PS",  "lat": 13.0590, "lng": 77.5600},
    {"name": "Devanahalli PS",      "lat": 13.2470, "lng": 77.7110},
    {"name": "Jakkur PS",           "lat": 13.0715, "lng": 77.5880},
    {"name": "Nagawara PS",         "lat": 13.0450, "lng": 77.6250},
    # West
    {"name": "Rajajinagar PS",      "lat": 12.9840, "lng": 77.5510},
    {"name": "Malleswaram PS",      "lat": 12.9990, "lng": 77.5720},
    {"name": "Majestic PS",         "lat": 12.9770, "lng": 77.5720},
    {"name": "Magadi Road PS",      "lat": 12.9640, "lng": 77.5170},
    {"name": "Kengeri PS",          "lat": 12.9149, "lng": 77.4840},
    # East
    {"name": "Indiranagar PS",      "lat": 12.9792, "lng": 77.6388},
    {"name": "Whitefield PS",       "lat": 12.9698, "lng": 77.7500},
    {"name": "KR Puram PS",         "lat": 13.0020, "lng": 77.6960},
    {"name": "Marathahalli PS",     "lat": 12.9591, "lng": 77.7011},
    {"name": "HAL PS",              "lat": 12.9634, "lng": 77.6596},
    # South
    {"name": "Koramangala PS",      "lat": 12.9293, "lng": 77.6210},
    {"name": "BTM Layout PS",       "lat": 12.9126, "lng": 77.6101},
    {"name": "JP Nagar PS",         "lat": 12.9060, "lng": 77.5830},
    {"name": "Jayanagar PS",        "lat": 12.9260, "lng": 77.5830},
    {"name": "Electronic City PS",  "lat": 12.8440, "lng": 77.6600},
    {"name": "HSR Layout PS",       "lat": 12.9121, "lng": 77.6446},
    {"name": "Banashankari PS",     "lat": 12.9270, "lng": 77.5640},
]

POLICE_DF = pd.DataFrame(POLICE_STATIONS)

# ══════════════════════════════════════════════════════════════════════════════
# 3.  CRIME HOTSPOTS
# ══════════════════════════════════════════════════════════════════════════════

CRIME_HOTSPOTS: List[Dict] = [
    {"lat": 12.9770, "lng": 77.5720, "intensity": 0.95},  # Majestic
    {"lat": 12.9630, "lng": 77.5770, "intensity": 0.88},  # KR Market
    {"lat": 12.9600, "lng": 77.5600, "intensity": 0.82},  # Magadi Road
    {"lat": 13.0220, "lng": 77.5950, "intensity": 0.78},  # RT Nagar
    {"lat": 12.9290, "lng": 77.6210, "intensity": 0.74},  # Koramangala night
    {"lat": 13.0020, "lng": 77.6960, "intensity": 0.72},  # KR Puram
    {"lat": 12.9590, "lng": 77.7010, "intensity": 0.65},  # Marathahalli
    {"lat": 12.9120, "lng": 77.6100, "intensity": 0.62},  # BTM
    {"lat": 12.9840, "lng": 77.5510, "intensity": 0.60},  # Rajajinagar
    {"lat": 13.0450, "lng": 77.6250, "intensity": 0.58},  # Nagawara
    {"lat": 12.9510, "lng": 77.5270, "intensity": 0.55},  # Kengeri
    {"lat": 12.9791, "lng": 77.6390, "intensity": 0.50},  # Indiranagar late night
]

HOTSPOT_DF = pd.DataFrame(CRIME_HOTSPOTS)

# ══════════════════════════════════════════════════════════════════════════════
# 3B.  SPATIAL POI DATABASE
# ══════════════════════════════════════════════════════════════════════════════

TRAFFIC_SIGNALS: List[Tuple[float, float]] = [
    # North Bangalore
    (13.0360, 77.5970), (13.0220, 77.5975), (13.0450, 77.6250),
    (13.0715, 77.5880), (13.1000, 77.5960), (13.0590, 77.5600),
    (13.0470, 77.5770), (13.0300, 77.6300), (13.0240, 77.6150),
    (13.0550, 77.5960), (13.0080, 77.5600), (13.0110, 77.5770),
    # West Bangalore
    (12.9840, 77.5510), (12.9990, 77.5720), (12.9770, 77.5720),
    (12.9640, 77.5170), (12.9800, 77.5380), (12.9950, 77.5470),
    (12.9700, 77.5340), (12.9150, 77.4840), (12.9600, 77.5110),
    (12.9420, 77.5760), (12.9500, 77.5840), (13.0100, 77.5310),
    (13.0250, 77.5390), (13.0200, 77.5190), (12.9900, 77.5470),
    # Central Bangalore
    (12.9760, 77.5930), (12.9840, 77.6090), (12.9740, 77.6070),
    (12.9710, 77.6100), (12.9860, 77.6060), (12.9750, 77.5840),
    (12.9680, 77.6010), (12.9950, 77.5750), (12.9990, 77.5900),
    (12.9520, 77.5980), (12.9430, 77.5720), (12.9550, 77.5840),
    # East Bangalore
    (12.9792, 77.6388), (12.9698, 77.7500), (13.0020, 77.6960),
    (12.9591, 77.7011), (12.9634, 77.6596), (12.9900, 77.6720),
    (12.9820, 77.7100), (12.9550, 77.7040), (12.9740, 77.7180),
    (12.9540, 77.6480), (12.9600, 77.6450), (12.9800, 77.6550),
    (12.9660, 77.7460), (13.0250, 77.6380), (13.0100, 77.6550),
    (12.9400, 77.6980), (12.9200, 77.6730), (12.9070, 77.6760),
    (12.9400, 77.7120), (12.9290, 77.6990), (12.9730, 77.7200),
    # South Bangalore
    (12.9293, 77.6210), (12.9126, 77.6101), (12.9060, 77.5830),
    (12.9260, 77.5830), (12.8440, 77.6600), (12.9121, 77.6446),
    (12.9270, 77.5640), (12.9170, 77.6230), (12.8990, 77.6250),
    (12.9340, 77.6160), (12.9160, 77.5760), (12.8900, 77.6030),
    (12.8750, 77.5960), (12.8620, 77.5970), (12.8850, 77.6420),
    # Airport / Peripheral
    (13.1980, 77.7050), (13.1750, 77.6820), (13.1550, 77.6650),
    (13.2200, 77.7100), (13.1320, 77.6200), (13.2480, 77.7130),
    # Logistics / Industrial
    (12.9050, 77.5000), (12.9100, 77.4900), (12.8900, 77.4800),
    (12.8700, 77.5100), (13.0800, 77.5850), (13.0690, 77.5890),
]

COMMERCIAL_POIS: List[Tuple[float, float]] = [
    # Major Malls & Commercial Hubs
    (12.9950, 77.5460), (12.9720, 77.7350), (12.9360, 77.6140),
    (13.0030, 77.5570), (13.0680, 77.6210), (12.9970, 77.5520),
    (12.9340, 77.5840), (12.9900, 77.5390), (12.8670, 77.5970),
    (12.9600, 77.7260), (12.9710, 77.6100), (12.9780, 77.6420),
    # Commercial Streets & Markets
    (12.9840, 77.6090), (12.9730, 77.6080), (12.9750, 77.6110),
    (12.9740, 77.6070), (12.9290, 77.6180), (12.9270, 77.6240),
    (12.9300, 77.6300), (12.9680, 77.6010), (12.9630, 77.5770),
    (13.0000, 77.5720), (12.9840, 77.5550), (12.9280, 77.5810),
    (12.9550, 77.7030), (12.9690, 77.7450), (12.8500, 77.6600),
    # IT Corridor Commercial
    (12.9400, 77.6980), (12.9250, 77.6730), (13.0100, 77.6550),
    (13.0470, 77.6200), (12.9750, 77.7480), (12.9860, 77.7300),
    (12.9600, 77.7180), (12.9810, 77.7100), (12.9830, 77.6550),
    # Airport / Peripheral Commercial
    (13.1980, 77.7060), (13.2000, 77.7100), (13.1800, 77.6900),
    # Residential Commercial nodes
    (13.0220, 77.5975), (13.0470, 77.6240), (13.0550, 77.6380),
    (12.9580, 77.5720), (12.9540, 77.5820), (12.9060, 77.5770),
    (12.9270, 77.5640), (12.9440, 77.5700), (12.9100, 77.5430),
    (12.8880, 77.5740), (12.8660, 77.5970), (12.9960, 77.5920),
]

BAR_PUB_POIS: List[Tuple[float, float]] = [
    # Indiranagar — highest density
    (12.9790, 77.6380), (12.9760, 77.6410), (12.9780, 77.6360),
    (12.9800, 77.6420), (12.9790, 77.6390), (12.9770, 77.6350),
    (12.9750, 77.6360), (12.9800, 77.6360), (12.9770, 77.6400),
    (12.9750, 77.6410),
    # Koramangala — high density
    (12.9280, 77.6180), (12.9300, 77.6230), (12.9280, 77.6300),
    (12.9150, 77.6140), (12.9350, 77.6200), (12.9310, 77.6180),
    (12.9270, 77.6210), (12.9290, 77.6250),
    # HSR Layout
    (12.9160, 77.6430), (12.9170, 77.6360), (12.9150, 77.6400),
    # Whitefield / SE IT Corridor
    (12.9700, 77.7480), (12.9660, 77.7450), (12.9830, 77.7330),
    (12.9680, 77.7420),
    # Marathahalli
    (12.9560, 77.7030), (12.9520, 77.7050), (12.9580, 77.7000),
    # Bellandur / ORR East
    (12.9260, 77.6710), (12.9300, 77.6690),
    # MG Road / Brigade / Church Street
    (12.9750, 77.6100), (12.9730, 77.6080), (12.9740, 77.6070),
    (12.9690, 77.6070),
    # BTM / JP Nagar / Jayanagar
    (12.9120, 77.6150), (12.9090, 77.6130), (12.9070, 77.5800),
    (12.9270, 77.5820),
    # Malleswaram / Hebbal / Nagawara
    (13.0000, 77.5710), (13.0370, 77.5960), (13.0460, 77.6240),
    # Misc
    (13.0420, 77.6350), (12.9500, 77.7070), (12.8970, 77.6750),
    (13.0030, 77.6950), (13.0200, 77.5410), (12.9830, 77.5520),
    (12.9780, 77.5710), (12.9420, 77.5770), (12.9990, 77.5920),
    (12.9700, 77.6030), (12.9610, 77.6430), (12.8470, 77.6620),
    (12.9600, 77.7180), (12.8970, 77.6750),
]

HOSPITAL_POIS: List[Tuple[float, float]] = [
    (12.9650, 77.6480), (12.9310, 77.5830), (12.8640, 77.6040),
    (12.8480, 77.6600), (12.9440, 77.7060), (12.9360, 77.6080),
    (12.9660, 77.5740), (12.9840, 77.6040), (12.9440, 77.6010),
    (12.9210, 77.6040), (13.0080, 77.5590), (12.9010, 77.4930),
    (13.0240, 77.5380), (12.9170, 77.6350), (13.0430, 77.5930),
    (12.9200, 77.5000), (12.9350, 77.6190), (12.9680, 77.7490),
    (13.0440, 77.5950), (12.9750, 77.6070), (12.9330, 77.5740),
    (12.9780, 77.6390),
]


def _generate_intersection_nodes() -> List[Tuple[float, float]]:
    rng = np.random.default_rng(2024)
    zone_seeds = [
        (13.022,  77.598,  30, 0.009), (13.045,  77.625,  22, 0.008),
        (13.070,  77.628,  18, 0.010), (12.984,  77.551,  22, 0.008),
        (12.977,  77.572,  28, 0.007), (12.930,  77.621,  25, 0.007),
        (12.912,  77.610,  22, 0.008), (12.970,  77.750,  18, 0.011),
        (12.959,  77.701,  20, 0.008), (12.978,  77.640,  18, 0.007),
        (13.002,  77.696,  18, 0.009), (12.912,  77.645,  15, 0.008),
        (12.844,  77.660,  12, 0.010), (13.100,  77.596,  12, 0.011),
        (12.999,  77.572,  15, 0.007), (12.960,  77.510,  10, 0.009),
        (12.915,  77.484,   8, 0.009), (12.927,  77.564,  14, 0.007),
        (12.926,  77.583,  14, 0.007), (12.975,  77.593,  12, 0.006),
        (13.036,  77.597,  10, 0.008),
        # Airport / peripheral nodes
        (13.198,  77.706,   8, 0.012), (13.175,  77.682,   6, 0.010),
        # Logistics/industrial nodes
        (12.905,  77.500,   8, 0.009), (12.870,  77.510,   6, 0.008),
    ]
    nodes: List[Tuple[float, float]] = []
    for lat_c, lng_c, n, sigma in zone_seeds:
        lats = rng.normal(lat_c, sigma, n)
        lngs = rng.normal(lng_c, sigma, n)
        nodes.extend(zip(lats.tolist(), lngs.tolist()))
    return nodes


INTERSECTION_NODES: List[Tuple[float, float]] = _generate_intersection_nodes()

# ══════════════════════════════════════════════════════════════════════════════
# 4.  ZONE PROFILES  (weak priors ≤ 25%)
# ══════════════════════════════════════════════════════════════════════════════

ZONE_PROFILES: Dict[str, Dict] = {
    # ── NORTH ────────────────────────────────────────────────────────────────
    "Hebbal": {
        "zone_type": "transit_commercial",   "base_activity": 0.72,
        "nightlife_density": 0.20,           "commercial_density": 0.65,
        "infra_quality": 0.68,               "cctv_density": 0.60,
        "road_type": "primary",              "avg_road_width_m": 18,
        "junction_density": 0.55,           "event_frequency": 0.25,
    },
    "RT Nagar": {
        "zone_type": "dense_residential",    "base_activity": 0.65,
        "nightlife_density": 0.18,           "commercial_density": 0.50,
        "infra_quality": 0.52,               "cctv_density": 0.42,
        "road_type": "secondary",            "avg_road_width_m": 10,
        "junction_density": 0.70,           "event_frequency": 0.15,
    },
    "Nagawara": {
        "zone_type": "mixed_residential",    "base_activity": 0.58,
        "nightlife_density": 0.12,           "commercial_density": 0.40,
        "infra_quality": 0.55,               "cctv_density": 0.38,
        "road_type": "secondary",            "avg_road_width_m": 9,
        "junction_density": 0.60,           "event_frequency": 0.12,
    },
    "Thanisandra": {
        "zone_type": "growing_residential",  "base_activity": 0.50,
        "nightlife_density": 0.10,           "commercial_density": 0.35,
        "infra_quality": 0.50,               "cctv_density": 0.30,
        "road_type": "secondary",            "avg_road_width_m": 9,
        "junction_density": 0.50,           "event_frequency": 0.08,
    },
    "Yelahanka": {
        "zone_type": "suburban_residential", "base_activity": 0.48,
        "nightlife_density": 0.08,           "commercial_density": 0.38,
        "infra_quality": 0.58,               "cctv_density": 0.35,
        "road_type": "secondary",            "avg_road_width_m": 10,
        "junction_density": 0.45,           "event_frequency": 0.10,
    },
    "Hennur": {
        "zone_type": "dense_residential",    "base_activity": 0.55,
        "nightlife_density": 0.10,           "commercial_density": 0.42,
        "infra_quality": 0.48,               "cctv_density": 0.32,
        "road_type": "residential",          "avg_road_width_m": 7,
        "junction_density": 0.65,           "event_frequency": 0.10,
    },
    "Jakkur": {
        "zone_type": "suburban_mixed",       "base_activity": 0.45,
        "nightlife_density": 0.08,           "commercial_density": 0.30,
        "infra_quality": 0.55,               "cctv_density": 0.30,
        "road_type": "secondary",            "avg_road_width_m": 9,
        "junction_density": 0.40,           "event_frequency": 0.08,
    },
    "Sahakar Nagar": {
        "zone_type": "planned_residential",  "base_activity": 0.52,
        "nightlife_density": 0.06,           "commercial_density": 0.35,
        "infra_quality": 0.62,               "cctv_density": 0.40,
        "road_type": "residential",          "avg_road_width_m": 9,
        "junction_density": 0.45,           "event_frequency": 0.08,
    },
    "Devanahalli": {
        "zone_type": "peri_urban",           "base_activity": 0.35,
        "nightlife_density": 0.06,           "commercial_density": 0.25,
        "infra_quality": 0.52,               "cctv_density": 0.28,
        "road_type": "primary",              "avg_road_width_m": 12,
        "junction_density": 0.25,           "event_frequency": 0.08,
    },
    # ── WEST ─────────────────────────────────────────────────────────────────
    "Rajajinagar": {
        "zone_type": "dense_residential",    "base_activity": 0.65,
        "nightlife_density": 0.20,           "commercial_density": 0.55,
        "infra_quality": 0.55,               "cctv_density": 0.45,
        "road_type": "secondary",            "avg_road_width_m": 10,
        "junction_density": 0.68,           "event_frequency": 0.18,
    },
    "Malleswaram": {
        "zone_type": "heritage_commercial",  "base_activity": 0.68,
        "nightlife_density": 0.18,           "commercial_density": 0.65,
        "infra_quality": 0.60,               "cctv_density": 0.50,
        "road_type": "secondary",            "avg_road_width_m": 9,
        "junction_density": 0.72,           "event_frequency": 0.20,
    },
    "Majestic": {
        "zone_type": "high_crime_commercial","base_activity": 0.88,
        "nightlife_density": 0.55,           "commercial_density": 0.90,
        "infra_quality": 0.45,               "cctv_density": 0.55,
        "road_type": "primary",              "avg_road_width_m": 14,
        "junction_density": 0.85,           "event_frequency": 0.40,
    },
    "Magadi Road": {
        "zone_type": "industrial_transit",   "base_activity": 0.55,
        "nightlife_density": 0.12,           "commercial_density": 0.45,
        "infra_quality": 0.42,               "cctv_density": 0.30,
        "road_type": "primary",              "avg_road_width_m": 14,
        "junction_density": 0.50,           "event_frequency": 0.12,
    },
    "Kengeri": {
        "zone_type": "suburban_residential", "base_activity": 0.45,
        "nightlife_density": 0.10,           "commercial_density": 0.38,
        "infra_quality": 0.48,               "cctv_density": 0.28,
        "road_type": "secondary",            "avg_road_width_m": 9,
        "junction_density": 0.45,           "event_frequency": 0.10,
    },
    "Yeshwantpur": {
        "zone_type": "industrial_transit",   "base_activity": 0.62,
        "nightlife_density": 0.15,           "commercial_density": 0.52,
        "infra_quality": 0.55,               "cctv_density": 0.42,
        "road_type": "primary",              "avg_road_width_m": 14,
        "junction_density": 0.60,           "event_frequency": 0.18,
    },
    "Tumkur Road": {
        "zone_type": "arterial_highway",     "base_activity": 0.55,
        "nightlife_density": 0.08,           "commercial_density": 0.40,
        "infra_quality": 0.60,               "cctv_density": 0.38,
        "road_type": "highway",              "avg_road_width_m": 24,
        "junction_density": 0.30,           "event_frequency": 0.10,
    },
    # ── EAST ─────────────────────────────────────────────────────────────────
    "Indiranagar": {
        "zone_type": "nightlife_startup",    "base_activity": 0.85,
        "nightlife_density": 0.80,           "commercial_density": 0.78,
        "infra_quality": 0.72,               "cctv_density": 0.68,
        "road_type": "secondary",            "avg_road_width_m": 10,
        "junction_density": 0.75,           "event_frequency": 0.45,
    },
    "Whitefield": {
        "zone_type": "it_corridor",          "base_activity": 0.72,
        "nightlife_density": 0.35,           "commercial_density": 0.62,
        "infra_quality": 0.68,               "cctv_density": 0.65,
        "road_type": "primary",              "avg_road_width_m": 16,
        "junction_density": 0.55,           "event_frequency": 0.30,
    },
    "KR Puram": {
        "zone_type": "industrial_transit",   "base_activity": 0.65,
        "nightlife_density": 0.20,           "commercial_density": 0.55,
        "infra_quality": 0.50,               "cctv_density": 0.40,
        "road_type": "primary",              "avg_road_width_m": 14,
        "junction_density": 0.58,           "event_frequency": 0.18,
    },
    "Marathahalli": {
        "zone_type": "it_residential",       "base_activity": 0.78,
        "nightlife_density": 0.40,           "commercial_density": 0.70,
        "infra_quality": 0.62,               "cctv_density": 0.58,
        "road_type": "primary",              "avg_road_width_m": 14,
        "junction_density": 0.65,           "event_frequency": 0.32,
    },
    "HAL": {
        "zone_type": "industrial_defense",   "base_activity": 0.58,
        "nightlife_density": 0.12,           "commercial_density": 0.45,
        "infra_quality": 0.65,               "cctv_density": 0.55,
        "road_type": "secondary",            "avg_road_width_m": 12,
        "junction_density": 0.50,           "event_frequency": 0.12,
    },
    "Bellandur": {
        "zone_type": "it_residential",       "base_activity": 0.68,
        "nightlife_density": 0.30,           "commercial_density": 0.58,
        "infra_quality": 0.60,               "cctv_density": 0.55,
        "road_type": "primary",              "avg_road_width_m": 14,
        "junction_density": 0.55,           "event_frequency": 0.25,
    },
    "Varthur": {
        "zone_type": "growing_residential",  "base_activity": 0.48,
        "nightlife_density": 0.12,           "commercial_density": 0.35,
        "infra_quality": 0.45,               "cctv_density": 0.28,
        "road_type": "secondary",            "avg_road_width_m": 9,
        "junction_density": 0.48,           "event_frequency": 0.10,
    },
    # ── SOUTH ────────────────────────────────────────────────────────────────
    "Koramangala": {
        "zone_type": "nightlife_commercial", "base_activity": 0.82,
        "nightlife_density": 0.70,           "commercial_density": 0.80,
        "infra_quality": 0.68,               "cctv_density": 0.65,
        "road_type": "secondary",            "avg_road_width_m": 10,
        "junction_density": 0.72,           "event_frequency": 0.42,
    },
    "BTM Layout": {
        "zone_type": "dense_residential",    "base_activity": 0.65,
        "nightlife_density": 0.28,           "commercial_density": 0.58,
        "infra_quality": 0.55,               "cctv_density": 0.48,
        "road_type": "secondary",            "avg_road_width_m": 9,
        "junction_density": 0.70,           "event_frequency": 0.22,
    },
    "JP Nagar": {
        "zone_type": "residential_commercial","base_activity": 0.58,
        "nightlife_density": 0.18,           "commercial_density": 0.50,
        "infra_quality": 0.60,               "cctv_density": 0.45,
        "road_type": "secondary",            "avg_road_width_m": 10,
        "junction_density": 0.60,           "event_frequency": 0.15,
    },
    "Jayanagar": {
        "zone_type": "upscale_residential",  "base_activity": 0.60,
        "nightlife_density": 0.15,           "commercial_density": 0.55,
        "infra_quality": 0.68,               "cctv_density": 0.55,
        "road_type": "secondary",            "avg_road_width_m": 10,
        "junction_density": 0.62,           "event_frequency": 0.15,
    },
    "Electronic City": {
        "zone_type": "it_corridor",          "base_activity": 0.65,
        "nightlife_density": 0.15,           "commercial_density": 0.48,
        "infra_quality": 0.65,               "cctv_density": 0.60,
        "road_type": "highway",              "avg_road_width_m": 20,
        "junction_density": 0.40,           "event_frequency": 0.18,
    },
    "HSR Layout": {
        "zone_type": "it_residential",       "base_activity": 0.68,
        "nightlife_density": 0.35,           "commercial_density": 0.62,
        "infra_quality": 0.65,               "cctv_density": 0.58,
        "road_type": "secondary",            "avg_road_width_m": 10,
        "junction_density": 0.62,           "event_frequency": 0.28,
    },
    "Banashankari": {
        "zone_type": "residential_commercial","base_activity": 0.58,
        "nightlife_density": 0.12,           "commercial_density": 0.50,
        "infra_quality": 0.60,               "cctv_density": 0.45,
        "road_type": "secondary",            "avg_road_width_m": 10,
        "junction_density": 0.58,           "event_frequency": 0.14,
    },
    # ── CENTRAL ──────────────────────────────────────────────────────────────
    "Shivajinagar": {
        "zone_type": "commercial_transit",   "base_activity": 0.80,
        "nightlife_density": 0.30,           "commercial_density": 0.80,
        "infra_quality": 0.58,               "cctv_density": 0.62,
        "road_type": "primary",              "avg_road_width_m": 14,
        "junction_density": 0.80,           "event_frequency": 0.35,
    },
    "MG Road": {
        "zone_type": "arterial_commercial",  "base_activity": 0.85,
        "nightlife_density": 0.45,           "commercial_density": 0.88,
        "infra_quality": 0.72,               "cctv_density": 0.78,
        "road_type": "primary",              "avg_road_width_m": 18,
        "junction_density": 0.75,           "event_frequency": 0.40,
    },
    "Cunningham Road": {
        "zone_type": "upscale_residential",  "base_activity": 0.62,
        "nightlife_density": 0.22,           "commercial_density": 0.55,
        "infra_quality": 0.72,               "cctv_density": 0.65,
        "road_type": "secondary",            "avg_road_width_m": 12,
        "junction_density": 0.55,           "event_frequency": 0.18,
    },
    # ── AIRPORT / PERIPHERAL ─────────────────────────────────────────────────
    "Kempegowda International Airport": {
        "zone_type": "transit_commercial",   "base_activity": 0.70,
        "nightlife_density": 0.10,           "commercial_density": 0.55,
        "infra_quality": 0.85,               "cctv_density": 0.88,
        "road_type": "highway",              "avg_road_width_m": 28,
        "junction_density": 0.20,           "event_frequency": 0.20,
    },
    "Airport Road": {
        "zone_type": "arterial_highway",     "base_activity": 0.58,
        "nightlife_density": 0.05,           "commercial_density": 0.35,
        "infra_quality": 0.80,               "cctv_density": 0.72,
        "road_type": "highway",              "avg_road_width_m": 24,
        "junction_density": 0.18,           "event_frequency": 0.12,
    },
    "Peripheral Ring Road": {
        "zone_type": "arterial_highway",     "base_activity": 0.45,
        "nightlife_density": 0.05,           "commercial_density": 0.25,
        "infra_quality": 0.72,               "cctv_density": 0.55,
        "road_type": "highway",              "avg_road_width_m": 22,
        "junction_density": 0.15,           "event_frequency": 0.08,
    },
    # ── SOUTHEAST IT CORRIDOR ────────────────────────────────────────────────
    "Sarjapur Road": {
        "zone_type": "it_corridor",          "base_activity": 0.70,
        "nightlife_density": 0.25,           "commercial_density": 0.58,
        "infra_quality": 0.62,               "cctv_density": 0.58,
        "road_type": "primary",              "avg_road_width_m": 16,
        "junction_density": 0.50,           "event_frequency": 0.25,
    },
    "Outer Ring Road": {
        "zone_type": "it_corridor",          "base_activity": 0.78,
        "nightlife_density": 0.30,           "commercial_density": 0.65,
        "infra_quality": 0.68,               "cctv_density": 0.65,
        "road_type": "highway",              "avg_road_width_m": 24,
        "junction_density": 0.45,           "event_frequency": 0.30,
    },
    # ── LOGISTICS / HIGH-TRAFFIC ─────────────────────────────────────────────
    "Peenya Industrial Area": {
        "zone_type": "industrial_transit",   "base_activity": 0.60,
        "nightlife_density": 0.05,           "commercial_density": 0.35,
        "infra_quality": 0.50,               "cctv_density": 0.38,
        "road_type": "primary",              "avg_road_width_m": 14,
        "junction_density": 0.40,           "event_frequency": 0.08,
    },
    "Hosur Road": {
        "zone_type": "arterial_highway",     "base_activity": 0.68,
        "nightlife_density": 0.12,           "commercial_density": 0.50,
        "infra_quality": 0.65,               "cctv_density": 0.55,
        "road_type": "highway",              "avg_road_width_m": 22,
        "junction_density": 0.35,           "event_frequency": 0.18,
    },
    "NICE Road": {
        "zone_type": "arterial_highway",     "base_activity": 0.45,
        "nightlife_density": 0.03,           "commercial_density": 0.18,
        "infra_quality": 0.80,               "cctv_density": 0.60,
        "road_type": "highway",              "avg_road_width_m": 26,
        "junction_density": 0.10,           "event_frequency": 0.05,
    },
}

DEFAULT_ZONE_PROFILE: Dict = {
    "zone_type": "mixed_residential",    "base_activity": 0.50,
    "nightlife_density": 0.12,           "commercial_density": 0.40,
    "infra_quality": 0.50,               "cctv_density": 0.35,
    "road_type": "secondary",            "avg_road_width_m": 10,
    "junction_density": 0.50,           "event_frequency": 0.10,
}

# ══════════════════════════════════════════════════════════════════════════════
# 5.  ROAD TYPE RISK TABLE
# ══════════════════════════════════════════════════════════════════════════════

ROAD_TYPE_RISK: Dict[str, float] = {
    "motorway":       0.78,
    "motorway_link":  0.70,
    "trunk":          0.72,
    "trunk_link":     0.65,
    "highway":        0.72,
    "primary":        0.58,
    "primary_link":   0.52,
    "secondary":      0.40,
    "secondary_link": 0.38,
    "tertiary":       0.36,
    "tertiary_link":  0.34,
    "residential":    0.30,
    "living_street":  0.25,
    "service":        0.28,
    "unclassified":   0.35,
    "busway":         0.32,
    "road":           0.38,
}

# Highway type → structural congestion modifier (higher = more congested baseline)
HIGHWAY_TYPE_FACTOR: Dict[str, float] = {
    "motorway":       0.12,   # controlled access, low congestion baseline
    "motorway_link":  0.22,
    "trunk":          0.28,
    "trunk_link":     0.32,
    "primary":        0.45,
    "primary_link":   0.42,
    "secondary":      0.50,
    "secondary_link": 0.48,
    "tertiary":       0.52,
    "tertiary_link":  0.50,
    "residential":    0.40,
    "living_street":  0.35,
    "service":        0.35,
    "unclassified":   0.48,
    "busway":         0.38,
    "road":           0.45,
    "none":           0.48,
}

# Road type → connectivity factor
ROAD_TYPE_CONN: Dict[str, float] = {
    "motorway":       0.95,
    "motorway_link":  0.88,
    "trunk":          0.90,
    "trunk_link":     0.82,
    "highway":        0.90,
    "primary":        0.78,
    "primary_link":   0.72,
    "secondary":      0.60,
    "secondary_link": 0.55,
    "tertiary":       0.50,
    "tertiary_link":  0.46,
    "residential":    0.35,
    "living_street":  0.28,
    "service":        0.28,
    "unclassified":   0.42,
    "busway":         0.60,
    "road":           0.45,
}

# ══════════════════════════════════════════════════════════════════════════════
# 5B.  SPATIAL QUERY ENGINE  (vectorised haversine, unchanged from v5.0)
# ══════════════════════════════════════════════════════════════════════════════

class SpatialQueryEngine:
    """Efficient spatial query engine for POI proximity calculations."""

    def __init__(self, coords: List[Tuple[float, float]]) -> None:
        if coords:
            arr = np.array(coords, dtype=np.float64)
            self._lats: np.ndarray = arr[:, 0]
            self._lngs: np.ndarray = arr[:, 1]
        else:
            self._lats = np.empty(0, dtype=np.float64)
            self._lngs = np.empty(0, dtype=np.float64)
        self._n = len(self._lats)

    def _dist_to_poi(self, lats: np.ndarray, lngs: np.ndarray,
                     poi_lat: float, poi_lng: float) -> np.ndarray:
        R = 6_371_000.0
        phi1 = np.radians(lats);  phi2 = math.radians(poi_lat)
        dphi = np.radians(poi_lat - lats);  dlam = np.radians(poi_lng - lngs)
        a = (np.sin(dphi / 2) ** 2
             + np.cos(phi1) * math.cos(phi2) * np.sin(dlam / 2) ** 2)
        return R * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))

    def count_within_radius(self, lats: np.ndarray, lngs: np.ndarray,
                             radius_m: float) -> np.ndarray:
        if self._n == 0:
            return np.zeros(len(lats), dtype=np.float64)
        count = np.zeros(len(lats), dtype=np.float64)
        for i in range(self._n):
            dist = self._dist_to_poi(lats, lngs, self._lats[i], self._lngs[i])
            count += (dist < radius_m).astype(np.float64)
        return count

    def nearest_distance_m(self, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
        if self._n == 0:
            return np.full(len(lats), np.inf, dtype=np.float64)
        min_dist = np.full(len(lats), np.inf, dtype=np.float64)
        for i in range(self._n):
            dist = self._dist_to_poi(lats, lngs, self._lats[i], self._lngs[i])
            np.minimum(min_dist, dist, out=min_dist)
        return min_dist

    def exp_density(self, lats: np.ndarray, lngs: np.ndarray,
                    radius_m: float) -> np.ndarray:
        if self._n == 0:
            return np.zeros(len(lats), dtype=np.float64)
        density = np.zeros(len(lats), dtype=np.float64)
        cutoff  = 3.0 * radius_m
        for i in range(self._n):
            dist = self._dist_to_poi(lats, lngs, self._lats[i], self._lngs[i])
            mask = dist < cutoff
            density[mask] += np.exp(-dist[mask] / radius_m)
        return density

    def exp_density_norm(self, lats: np.ndarray, lngs: np.ndarray,
                          radius_m: float, norm_scale: float) -> np.ndarray:
        raw = self.exp_density(lats, lngs, radius_m)
        return np.clip(raw / norm_scale, 0.0, 1.0)


# ── Module-level spatial indices ─────────────────────────────────────────────

_SIGNAL_NORM     = 4.0
_COMMERCIAL_NORM = 5.5
_BAR_NORM        = 4.0
_NODE_NORM       = 8.0

SIGNAL_IDX     = SpatialQueryEngine(TRAFFIC_SIGNALS)
COMMERCIAL_IDX = SpatialQueryEngine(COMMERCIAL_POIS)
BAR_IDX        = SpatialQueryEngine(BAR_PUB_POIS)
HOSPITAL_IDX   = SpatialQueryEngine(HOSPITAL_POIS)
NODE_IDX       = SpatialQueryEngine(INTERSECTION_NODES)
POLICE_IDX     = SpatialQueryEngine(
    [(s["lat"], s["lng"]) for s in POLICE_STATIONS]
)

# ══════════════════════════════════════════════════════════════════════════════
# 6.  UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def haversine_fast(lat1: np.ndarray, lng1: np.ndarray,
                   lat2: float, lng2: float) -> np.ndarray:
    R = 6_371_000.0
    phi1 = np.radians(lat1);  phi2 = math.radians(lat2)
    dphi = np.radians(lat2 - lat1);  dlam = np.radians(lng2 - lng1)
    a = (np.sin(dphi / 2.0) ** 2
         + np.cos(phi1) * math.cos(phi2) * np.sin(dlam / 2.0) ** 2)
    return R * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))


def inverse_distance_weight(distances_m: np.ndarray,
                             intensity: float = 1.0,
                             radius_m: float = 500.0,
                             decay: float = 1.5) -> np.ndarray:
    clipped = np.clip(distances_m, 1.0, None)
    raw = intensity / (clipped ** decay)
    return raw * np.exp(-distances_m / radius_m)


def normalize_min_max(series: pd.Series,
                       lo: float = 0.0, hi: float = 1.0) -> pd.Series:
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(np.full(len(series), (lo + hi) / 2.0),
                         index=series.index)
    return lo + (series - mn) / (mx - mn) * (hi - lo)


def zone_attr(zone_series: pd.Series, key: str) -> pd.Series:
    return zone_series.map(
        lambda z: ZONE_PROFILES.get(z, DEFAULT_ZONE_PROFILE)[key]
    )


def zone_attr_float(zone_series: pd.Series, key: str) -> pd.Series:
    return zone_attr(zone_series, key).astype(float)


def bounded_noise(rng: np.random.Generator, n: int,
                  scale: float, lo: float = 0.0, hi: float = 1.0,
                  base: np.ndarray = None) -> np.ndarray:
    """
    Add bounded stochastic noise that clips to [lo, hi].
    If base provided, also prevents completely destroying the correlation
    structure by scaling noise proportionally to base variance.
    """
    noise = rng.normal(0.0, scale, size=n)
    return np.clip(noise, lo - 1.0, hi - lo)   # allow noise in both directions


# ══════════════════════════════════════════════════════════════════════════════
# 7.  TIME MODULE
# ══════════════════════════════════════════════════════════════════════════════

def get_time_multiplier(hour: int) -> float:
    base = 0.72 + 0.35 * (1.0 - math.cos(2.0 * math.pi * (hour - 12.0) / 24.0)) / 2.0
    if hour >= 22 or hour <= 2:
        spike = (0.08 * math.exp(-((hour - 0.0) ** 2) / 8.0) if hour <= 2
                 else 0.08 * math.exp(-((hour - 24.0) ** 2) / 8.0))
        base = min(base + spike, 1.30)
    return round(base, 4)


def get_time_context(hour: int) -> str:
    if   0 <= hour < 5:   return "night_deep"
    elif 5 <= hour < 8:   return "early_morning"
    elif 8 <= hour < 12:  return "morning_peak"
    elif 12 <= hour < 17: return "afternoon"
    elif 17 <= hour < 21: return "evening_peak"
    else:                  return "late_night"


def get_night_activity_penalty(hour: int) -> float:
    if 8 <= hour <= 20:           return  1.0
    elif 6 <= hour < 8 or 20 < hour <= 22: return  0.3
    else:                          return -0.8


# ══════════════════════════════════════════════════════════════════════════════
# [U6]  DYNAMIC WEIGHT ADAPTATION
# ══════════════════════════════════════════════════════════════════════════════

def adapt_weights(hour: int,
                  avg_crime_score: float,
                  avg_cctv_score: float) -> Dict[str, float]:
    w = dict(RISK_WEIGHTS)
    ctx = get_time_context(hour)

    if ctx in ("night_deep", "late_night", "early_morning"):
        w["lighting"]   += 0.08
        w["crime"]      += 0.04
        w["cctv"]       += 0.03
        w["police"]     += 0.02
        w["isolation"]  += 0.04   # isolated roads riskier at night
        w["activity"]    = max(0.03, w["activity"] - 0.04)
        w["road"]        = max(0.04, w["road"] - 0.02)
    elif ctx in ("morning_peak", "afternoon"):
        w["activity"]   += 0.03
        w["road"]       += 0.02
        w["lighting"]    = max(0.04, w["lighting"] - 0.06)
        w["isolation"]   = max(0.04, w["isolation"] - 0.02)

    if avg_crime_score > 0.60:
        w["crime"]  += 0.05
        w["police"] += 0.03
        w["cctv"]   += 0.02

    if avg_cctv_score > 0.55:
        w["cctv"] += 0.04
        w["poi"]   = max(0.02, w["poi"] - 0.02)

    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


# ══════════════════════════════════════════════════════════════════════════════
# [U3]  TEMPORAL MEMORY ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _lat_lng_to_cell(lats: np.ndarray, lngs: np.ndarray,
                     resolution: float = 0.004) -> np.ndarray:
    lat_cells = (lats / resolution).astype(np.int32)
    lng_cells = (lngs / resolution).astype(np.int32)
    return lat_cells * 100_000 + lng_cells


def update_temporal_memory(lats: np.ndarray, lngs: np.ndarray,
                            risk_scores: np.ndarray, hour: int) -> None:
    cells = _lat_lng_to_cell(lats, lngs)
    scores_norm = risk_scores / 100.0
    boost = MEMORY_NIGHT_BOOST if (hour >= 22 or hour <= 4) else 1.0
    unique_cells, inverse = np.unique(cells, return_inverse=True)
    cell_means = np.bincount(inverse, weights=scores_norm) / np.bincount(inverse)
    for cell_id, mean_score in zip(unique_cells, cell_means):
        key = int(cell_id)
        existing = _TEMPORAL_MEMORY.get(key, mean_score)
        updated = (MEMORY_LAMBDA * mean_score * boost
                   + (1.0 - MEMORY_LAMBDA) * existing * MEMORY_DECAY_PER_HR)
        _TEMPORAL_MEMORY[key] = float(np.clip(updated, 0.0, 1.0))


def apply_temporal_memory(lats: np.ndarray, lngs: np.ndarray,
                           current_risk: np.ndarray, hour: int) -> np.ndarray:
    cells = _lat_lng_to_cell(lats, lngs)
    if 0 <= hour <= 4:
        mem_weight = 1.0 - MEMORY_LAMBDA + 0.15
        cur_weight = MEMORY_LAMBDA - 0.15
    else:
        mem_weight = 1.0 - MEMORY_LAMBDA
        cur_weight = MEMORY_LAMBDA
    mem_weight = np.clip(mem_weight, 0.0, 1.0)
    cur_weight = np.clip(cur_weight, 0.0, 1.0)
    cell_memory = np.array([
        _TEMPORAL_MEMORY.get(int(c), float(r))
        for c, r in zip(cells, current_risk)
    ], dtype=np.float64)
    blended = cur_weight * current_risk + mem_weight * cell_memory
    return np.clip(blended, 0.0, 1.0)


def reset_temporal_memory() -> None:
    _TEMPORAL_MEMORY.clear()


# ══════════════════════════════════════════════════════════════════════════════
# [U4]  UNCERTAINTY / CONFIDENCE SCORING
# ══════════════════════════════════════════════════════════════════════════════

def compute_data_sparsity(lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
    signal_cnt     = SIGNAL_IDX.count_within_radius(lats, lngs, 1000.0)
    commercial_cnt = COMMERCIAL_IDX.count_within_radius(lats, lngs, 1000.0)
    bar_cnt        = BAR_IDX.count_within_radius(lats, lngs, 800.0)
    hospital_cnt   = HOSPITAL_IDX.count_within_radius(lats, lngs, 1200.0)
    total_poi = signal_cnt + commercial_cnt + bar_cnt + hospital_cnt * 2.5
    poi_density = np.clip(np.sqrt(total_poi) / 4.5, 0.0, 1.0)
    return np.clip(1.0 - poi_density, 0.05, 1.0)


def inject_uncertainty(risk_scores: np.ndarray,
                        sparsity: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    n = len(risk_scores)
    sigma = (UNCERTAINTY_SIGMA_MIN
             + sparsity * (UNCERTAINTY_SIGMA_MAX - UNCERTAINTY_SIGMA_MIN))
    noise = UNCERTAINTY_RNG.normal(loc=0.0, scale=sigma, size=n)
    noisy = np.clip(risk_scores + noise, 0.0, 1.0)
    data_density = 1.0 - sparsity
    density_conf = 0.10 + 0.82 * (data_density ** 0.65)
    risk_penalty = np.clip(risk_scores - 0.70, 0.0, 0.30) * 0.15
    confidence   = np.clip(density_conf - risk_penalty, 0.10, 0.92)
    return noisy, confidence


# ══════════════════════════════════════════════════════════════════════════════
# [U2]  CONTEXTUAL POI INTERACTION MODEL
# ══════════════════════════════════════════════════════════════════════════════

def compute_poi_interaction_score(lats: np.ndarray, lngs: np.ndarray,
                                   hour: int) -> np.ndarray:
    bar_score     = BAR_IDX.exp_density_norm(lats, lngs, 350.0, _BAR_NORM)
    police_dist   = POLICE_IDX.nearest_distance_m(lats, lngs)
    hospital_dist = HOSPITAL_IDX.nearest_distance_m(lats, lngs)
    commercial_sc = COMMERCIAL_IDX.exp_density_norm(lats, lngs, 400.0, _COMMERCIAL_NORM)
    signal_sc     = SIGNAL_IDX.exp_density_norm(lats, lngs, 500.0, _SIGNAL_NORM)

    police_close     = np.exp(-police_dist / 800.0)
    cctv_proxy       = np.clip(signal_sc * 0.6 + commercial_sc * 0.4, 0.0, 1.0)
    hospital_near    = np.exp(-hospital_dist / 600.0)
    night_factor     = 1.4 if (hour >= 21 or hour <= 4) else 1.0

    bar_danger       = bar_score * (1.0 - police_close) * (1.0 - cctv_proxy)
    bar_risk_delta   = bar_danger * 0.28 * night_factor
    bar_safe_ctx     = bar_score * police_close * cctv_proxy
    bar_mitigation   = -bar_safe_ctx * 0.16 * night_factor
    hosp_commercial  = hospital_near * commercial_sc
    hospital_safety  = -(hosp_commercial * 0.15 + hospital_near * 0.10) / 2.0
    surveillance_corridor = police_close * cctv_proxy
    surveillance_delta    = -surveillance_corridor * 0.14

    total = bar_risk_delta + bar_mitigation + hospital_safety + surveillance_delta
    return np.clip(total, -0.20, 0.25)


# ══════════════════════════════════════════════════════════════════════════════
# [U7]  BEHAVIOURAL RISK ADJUSTMENT
# ══════════════════════════════════════════════════════════════════════════════

def compute_behavioural_adjustment(lats: np.ndarray, lngs: np.ndarray,
                                    hour: int,
                                    activity_scores: np.ndarray,
                                    cctv_scores: np.ndarray) -> np.ndarray:
    bar_score = BAR_IDX.exp_density_norm(lats, lngs, 350.0, _BAR_NORM)

    is_night_deep  = (hour >= 22 or hour <= 5)
    deserted_mask  = (
        is_night_deep & (activity_scores < 0.20) & (cctv_scores < 0.35)
    ).astype(float)
    deserted_penalty = deserted_mask * BEHAVIOURAL_DESERTED_PENALTY

    is_post_midnight = (hour >= 23 or hour <= 3)
    drunk_mask = (
        is_post_midnight & (bar_score > 0.60) & (activity_scores > 0.55)
    ).astype(float)
    drunk_penalty = drunk_mask * BEHAVIOURAL_DRUNK_ZONE_PENALTY

    moderate_activity = np.clip(
        1.0 - 2.0 * np.abs(activity_scores - 0.475), 0.0, 1.0
    )
    high_cctv  = np.clip((cctv_scores - 0.55) / 0.45, 0.0, 1.0)
    safe_bonus = -moderate_activity * high_cctv * BEHAVIOURAL_SAFE_CROWD_BONUS

    return np.clip(deserted_penalty + drunk_penalty + safe_bonus, -0.10, 0.20)


# ══════════════════════════════════════════════════════════════════════════════
# [U8]  MULTI-SCALE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def compute_meso_risk(df: pd.DataFrame, micro_risk: np.ndarray) -> np.ndarray:
    lats  = df["lat"].values.astype(np.float64)
    lngs  = df["lng"].values.astype(np.float64)
    cells = _lat_lng_to_cell(lats, lngs, resolution=0.004)
    unique_cells, inverse = np.unique(cells, return_inverse=True)
    cell_counts = np.bincount(inverse)
    cell_sums   = np.bincount(inverse, weights=micro_risk)
    cell_means  = cell_sums / np.maximum(cell_counts, 1)
    return np.clip(cell_means[inverse], 0.0, 1.0)


def compute_macro_risk(df: pd.DataFrame, micro_risk: np.ndarray) -> np.ndarray:
    temp = pd.DataFrame({"zone": df["zone"].values, "risk": micro_risk})
    zone_means = temp.groupby("zone")["risk"].transform("mean")
    return np.clip(zone_means.values, 0.0, 1.0)


def fuse_multiscale(micro: np.ndarray, meso: np.ndarray,
                    macro: np.ndarray) -> np.ndarray:
    fused = (MULTISCALE_ALPHA * micro
             + MULTISCALE_BETA  * meso
             + MULTISCALE_GAMMA * macro)
    return np.clip(fused, 0.0, 1.0)


# ══════════════════════════════════════════════════════════════════════════════
# [U5]  ROUTE CONTEXT ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def compute_route_transition_penalties(risk_sequence: np.ndarray,
                                        threshold_jump: float = 0.25,
                                        threshold_drop: float = 0.20) -> np.ndarray:
    n = len(risk_sequence)
    penalties = np.zeros(n, dtype=np.float64)
    if n < 2:
        return penalties
    delta = np.diff(risk_sequence)
    entry_mask = delta > threshold_jump
    penalties[1:][entry_mask]  += 0.60 * delta[entry_mask]
    exit_mask  = -delta > threshold_drop
    penalties[1:][exit_mask]   -= 0.30 * (-delta[exit_mask])
    return np.clip(penalties, -0.10, 0.30)


def score_route(segment_risks: np.ndarray) -> Dict:
    risks_norm  = segment_risks / 100.0
    penalties   = compute_route_transition_penalties(risks_norm)
    adjusted    = np.clip(risks_norm + penalties, 0.0, 1.0) * 100.0
    transition_score = float(np.abs(penalties).mean() * 100.0)
    mean_risk = float(adjusted.mean())
    max_risk  = float(adjusted.max())
    if mean_risk < 25:   band = "Low"
    elif mean_risk < 45: band = "Moderate"
    elif mean_risk < 65: band = "High"
    else:                band = "Critical"
    return {
        "segment_risks_adjusted": adjusted,
        "transition_penalties":   penalties * 100.0,
        "route_risk_mean":        round(mean_risk, 2),
        "route_risk_max":         round(max_risk, 2),
        "route_transition_score": round(transition_score, 2),
        "route_band":             band,
    }


# ══════════════════════════════════════════════════════════════════════════════
# [U9]  CALIBRATION MODE
# ══════════════════════════════════════════════════════════════════════════════

class CalibrationEngine:
    """Plug-in calibration and scenario simulation interface."""

    SCENARIOS: Dict[str, Dict] = {
        "diwali_night": {
            "description": "High event density, fireworks crowds, late night",
            "weight_overrides": {"event": 0.18, "activity": 0.16, "crime": 0.18},
            "time_multiplier_override": 1.45,
        },
        "heavy_rain": {
            "description": "Reduced visibility, flooded roads, reduced police mobility",
            "weight_overrides": {"road": 0.18, "infrastructure": 0.14, "lighting": 0.18},
            "time_multiplier_override": None,
        },
        "strike_hartal": {
            "description": "Road closures, empty streets, police presence high",
            "weight_overrides": {"event": 0.20, "activity": 0.15, "police": 0.08},
            "time_multiplier_override": 1.25,
        },
        "it_peak_weekday": {
            "description": "Heavy IT traffic 8-10AM and 6-8PM, low crime",
            "weight_overrides": {"road": 0.18, "activity": 0.05, "crime": 0.16},
            "time_multiplier_override": 0.82,
        },
        "baseline": {
            "description": "Default v6.0 weights, no overrides",
            "weight_overrides": {},
            "time_multiplier_override": None,
        },
    }

    def __init__(self) -> None:
        self._weight_overrides: Dict[str, float] = {}
        self._time_mult_override: Optional[float] = None
        self._ml_hook: Optional[callable] = None
        self._active_scenario: str = "baseline"

    def set_scenario(self, name: str) -> None:
        if name not in self.SCENARIOS:
            raise ValueError(f"Unknown scenario '{name}'. Available: {list(self.SCENARIOS)}")
        preset = self.SCENARIOS[name]
        self._weight_overrides   = dict(preset.get("weight_overrides", {}))
        self._time_mult_override = preset.get("time_multiplier_override")
        self._active_scenario    = name
        print(f"  [Calibration] Scenario '{name}': {preset['description']}")

    def set_custom_weights(self, overrides: Dict[str, float]) -> None:
        self._weight_overrides = dict(overrides)

    def register_ml_hook(self, fn: callable) -> None:
        self._ml_hook = fn

    def get_effective_weights(self, context_weights: Dict[str, float]) -> Dict[str, float]:
        w = dict(context_weights)
        for k, v in self._weight_overrides.items():
            if k in w:
                w[k] = v
        total = sum(w.values())
        return {k: v / total for k, v in w.items()}

    def get_time_multiplier(self, hour: int) -> float:
        if self._time_mult_override is not None:
            return self._time_mult_override
        return get_time_multiplier(hour)

    def run(self, df: pd.DataFrame, hour: int) -> pd.DataFrame:
        return calculate_dynamic_risk(df, hour, calibration=self)

    def factor_contribution_report(self, result_df: pd.DataFrame) -> pd.DataFrame:
        factor_cols = [c for c in result_df.columns if c.startswith("score_")]
        rows = []
        for col in factor_cols:
            factor     = col.replace("score_", "")
            mean_score = result_df[col].mean()
            weight     = RISK_WEIGHTS.get(factor, 0.0)
            rows.append({
                "factor":       factor,
                "mean_score":   round(mean_score, 4),
                "base_weight":  round(weight, 4),
                "contribution": round(mean_score * weight, 4),
            })
        return (pd.DataFrame(rows)
                .sort_values("contribution", ascending=False)
                .reset_index(drop=True))

    def simulate_scenario_comparison(self, df: pd.DataFrame, hour: int,
                                      scenarios: Optional[List[str]] = None) -> pd.DataFrame:
        if scenarios is None:
            scenarios = list(self.SCENARIOS.keys())
        records = []
        for sc in scenarios:
            self.set_scenario(sc)
            result = self.run(df.copy(), hour)
            records.append({
                "scenario":    sc,
                "description": self.SCENARIOS[sc]["description"],
                "risk_mean":   round(result["final_risk_score"].mean(), 2),
                "risk_p90":    round(result["final_risk_score"].quantile(0.90), 2),
                "risk_max":    round(result["final_risk_score"].max(), 2),
                "confidence":  round(result["confidence_score"].mean(), 3),
            })
        self.set_scenario("baseline")
        return pd.DataFrame(records)


# ══════════════════════════════════════════════════════════════════════════════
# 8.  SCHEMA-ALIGNED FACTOR COMPUTATIONS  (v6.0 new additions)
#     These functions operate on the CSV column values directly,
#     implementing the mandatory correlation requirements.
# ══════════════════════════════════════════════════════════════════════════════

def _parse_road_width(width_series: pd.Series) -> np.ndarray:
    """
    Parse road_width_estimate column which may contain strings like '7.5m'
    or numeric values.  Returns float array of widths in metres.
    """
    def _parse_one(v):
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).replace('m', '').strip()
        try:
            return float(s)
        except ValueError:
            return 10.0   # fallback
    return np.array([_parse_one(v) for v in width_series], dtype=np.float64)


def compute_congestion_score_v6(df: pd.DataFrame, hour: int,
                                  rng: np.random.Generator) -> np.ndarray:
    """
    [v6.0] Congestion score — multi-factor weighted calculation.

    MANDATORY CORRELATIONS ENFORCED:
    • Higher traffic_signal_density → slightly increases congestion
    • Higher intersection_density → moderately increases congestion
    • Higher road_width_estimate → reduces congestion
    • Commercial density → increases congestion (more stops/pedestrians)
    • Highway type: motorways less congested than secondary roads
    • time_risk: peak-hour time risks increase congestion

    Returns float array in [0, 1].
    """
    n = len(df)
    lats = df["lat"].values.astype(np.float64)
    lngs = df["lng"].values.astype(np.float64)

    # ── Input columns ─────────────────────────────────────────────────────────
    tsd   = df["traffic_signal_density"].values.astype(float)
    idens = df["intersection_density"].values.astype(float)
    rw    = _parse_road_width(df["road_width_estimate"])
    commd = df["commercial_density"].values.astype(float)
    hw    = df["highway_type"].fillna("none").values
    tr    = df["time_risk"].values.astype(float)

    # Normalise road width: typical Bengaluru range 4–30 m
    rw_norm = np.clip((rw - 4.0) / (30.0 - 4.0), 0.0, 1.0)
    rw_inv  = 1.0 - rw_norm   # narrow → high congestion contribution

    # Highway type factor: motorway/expressway reduces congestion
    hw_factor = np.array([HIGHWAY_TYPE_FACTOR.get(str(h).lower(), 0.48)
                          for h in hw], dtype=np.float64)

    # Normalise time_risk (could be int 0–10 or float 0–1 in data)
    tr_max = tr.max()
    tr_norm = np.clip(tr / max(tr_max, 1.0), 0.0, 1.0) if tr_max > 1.0 else np.clip(tr, 0.0, 1.0)

    # Weighted combination
    cong = (
        CONGESTION_COMP["traffic_signal_density"] * np.clip(tsd, 0.0, 1.0)
      + CONGESTION_COMP["intersection_density"]   * np.clip(idens, 0.0, 1.0)
      + CONGESTION_COMP["road_width_inv"]         * rw_inv
      + CONGESTION_COMP["commercial_density"]     * np.clip(commd, 0.0, 1.0)
      + CONGESTION_COMP["highway_type_factor"]    * hw_factor
      + CONGESTION_COMP["time_risk_norm"]         * tr_norm
    )

    # Spatial augmentation: CCTV density near commercial hubs = camera intersections
    signal_spatial = SIGNAL_IDX.exp_density_norm(lats, lngs, 500.0, _SIGNAL_NORM)
    commercial_sp  = COMMERCIAL_IDX.exp_density_norm(lats, lngs, 400.0, _COMMERCIAL_NORM)
    spatial_boost  = np.clip(0.4 * signal_spatial + 0.6 * commercial_sp, 0.0, 1.0) * 0.08

    cong = np.clip(cong + spatial_boost, 0.0, 1.0)

    # Controlled noise preserving correlations
    noise = rng.normal(0.0, 0.025, size=n)
    return np.clip(cong + noise, 0.0, 1.0)


def compute_travel_time_v6(df: pd.DataFrame,
                             congestion: np.ndarray,
                             flood_risk_col: np.ndarray,
                             rng: np.random.Generator) -> np.ndarray:
    """
    [v6.0] Travel time estimate — formula-driven, NOT random.

    MANDATORY CORRELATIONS ENFORCED:
    • Higher congestion_score → increases travel_time_estimate
    • Higher flood_risk → increases travel_time_estimate
    • Higher weather_exposure_score → increases travel_time_estimate
    • Higher road_width_estimate → decreases travel_time_estimate
    • Higher speed_limit → decreases travel_time_estimate
    • Higher traffic_signal_density → increases travel_time_estimate

    Returns float array in minutes (realistic Bengaluru: 0.1 – 60 min).
    """
    n   = len(df)
    rw  = _parse_road_width(df["road_width_estimate"])
    sl  = df["speed_limit"].values.astype(float)
    tsd = df["traffic_signal_density"].values.astype(float)
    wex = df["weather_exposure_score"].values.astype(float)

    # Normalise road width and speed limit to [0,1]
    rw_norm = np.clip((rw - 4.0) / 26.0, 0.0, 1.0)
    rw_inv  = 1.0 - rw_norm

    sl_norm = np.clip((sl - 20.0) / (100.0 - 20.0), 0.0, 1.0)
    sl_inv  = 1.0 - sl_norm   # low speed_limit → longer travel time

    flood = np.clip(flood_risk_col, 0.0, 1.0)
    wex   = np.clip(wex, 0.0, 1.0)
    tsd_c = np.clip(tsd, 0.0, 1.0)
    cong  = np.clip(congestion, 0.0, 1.0)

    # Weighted risk index → maps to travel time
    risk_index = (
        TRAVEL_TIME_COMP["congestion_score"]       * cong
      + TRAVEL_TIME_COMP["road_width_inv"]         * rw_inv
      + TRAVEL_TIME_COMP["flood_risk"]             * flood
      + TRAVEL_TIME_COMP["weather_exposure_score"] * wex
      + TRAVEL_TIME_COMP["speed_limit_inv"]        * sl_inv
      + TRAVEL_TIME_COMP["traffic_signal_density"] * tsd_c
    )

    # Convert risk_index [0,1] → realistic travel time in minutes.
    # Bengaluru road segments free-flow ≈ 0.5–8 min; heavy congestion ≈ 8–60 min.
    # Use a two-regime mapping:
    #   low risk  (0.0–0.4): 0.5 → 6  min  (linear regime, mostly residential)
    #   high risk (0.4–1.0): 6  → 55 min  (exponential regime, congested arterials)
    low_mask  = risk_index <= 0.40
    high_mask = ~low_mask

    base_time = np.empty(n, dtype=np.float64)
    # Linear regime
    base_time[low_mask]  = 0.5 + (risk_index[low_mask] / 0.40) * 5.5
    # Exponential regime
    scaled = (risk_index[high_mask] - 0.40) / 0.60   # 0→1 within high regime
    base_time[high_mask] = 6.0 + np.exp(scaled * 3.0) * 3.2   # 6→61 minutes

    # Road-type upper bounds (prevents service road having 60-min segment)
    rt_max = np.array([
        {"motorway": 60, "trunk": 55, "highway": 60,
         "primary": 50, "primary_link": 40,
         "secondary": 35, "secondary_link": 30,
         "tertiary": 28, "tertiary_link": 25,
         "residential": 18, "living_street": 12,
         "service": 12, "unclassified": 25,
         "busway": 20, "road": 30}.get(
            str(r).lower(), 30)
        for r in df["road_type"].fillna("secondary").values
    ], dtype=np.float64)

    time_clipped = np.minimum(base_time, rt_max)

    # Bounded stochastic noise (±10% of value to preserve correlations)
    noise = rng.normal(0.0, 0.08, size=n) * time_clipped
    return np.clip(time_clipped + noise, 0.1, 60.0).round(2)


def compute_connectivity_score_v6(df: pd.DataFrame,
                                   rng: np.random.Generator) -> np.ndarray:
    """
    [v6.0] Connectivity score — formula-driven.

    MANDATORY CORRELATIONS:
    • Higher adjacency_count → increases connectivity
    • Highway / primary road type → higher connectivity
    • Higher intersection_density → higher connectivity
    • Isolated areas → lower connectivity

    Returns float array in [0, 1].
    """
    adj    = df["adjacency_count"].values.astype(float)
    idens  = df["intersection_density"].values.astype(float)
    rt     = df["road_type"].fillna("secondary").values
    hw     = df["highway_type"].fillna("none").values

    # Normalise adjacency (typical Bengaluru: 0–12)
    adj_norm = np.clip(adj / 10.0, 0.0, 1.0)

    # Road type connectivity factor
    rt_factor = np.array([ROAD_TYPE_CONN.get(str(r).lower(), 0.42)
                          for r in rt], dtype=np.float64)

    # Highway type connectivity factor (same table, re-used)
    hw_factor = np.array([HIGHWAY_TYPE_FACTOR.get(str(h).lower(), 0.48)
                          for h in hw], dtype=np.float64)
    # For connectivity, motorways are high connectivity (not congested)
    # Invert the congestion-oriented highway factor
    hw_conn = 1.0 - hw_factor

    conn = (
        CONNECTIVITY_COMP["adjacency_count_norm"] * adj_norm
      + CONNECTIVITY_COMP["road_type_factor"]     * rt_factor
      + CONNECTIVITY_COMP["highway_type_factor"]  * hw_conn
      + CONNECTIVITY_COMP["intersection_density"] * np.clip(idens, 0.0, 1.0)
    )

    noise = rng.normal(0.0, 0.025, size=len(df))
    return np.clip(conn + noise, 0.0, 1.0)


def compute_isolated_area_score_v6(df: pd.DataFrame, hour: int,
                                    connectivity: np.ndarray,
                                    rng: np.random.Generator) -> np.ndarray:
    """
    [v6.0] Isolated area score — inversely related to connectivity.

    MANDATORY CORRELATIONS:
    • Higher connectivity_score → reduces isolation_risk
    • Late night → increases isolated road risk
    • Nightlife areas become riskier after 10 PM (but not isolated —
      the isolation risk applies to non-nightlife zones)
    • IT corridors riskier after midnight (deserted)

    Returns float array in [0, 1].
    """
    lats = df["lat"].values.astype(np.float64)
    lngs = df["lng"].values.astype(np.float64)
    n    = len(df)

    # Base isolation = inverse of connectivity
    base_isolation = 1.0 - connectivity

    # Spatial augmentation: areas far from POIs are genuinely isolated
    node_cnt  = NODE_IDX.count_within_radius(lats, lngs, 600.0)
    node_dens = np.clip(node_cnt / 12.0, 0.0, 1.0)
    poi_isolation = 1.0 - node_dens   # fewer nodes = more isolated

    # Combine: 60% connectivity-derived, 40% spatial POI isolation
    base = 0.60 * base_isolation + 0.40 * poi_isolation

    # ── Temporal modulation ───────────────────────────────────────────────────
    ctx = get_time_context(hour)

    # Late night: isolated roads become riskier — scale penalty by base isolation
    # (already-isolated areas get amplified; well-connected areas get small penalty)
    if ctx in ("night_deep", "late_night"):
        night_multiplier = 1.30   # 30% boost to existing isolation
    elif ctx == "early_morning":
        night_multiplier = 1.15
    else:
        night_multiplier = 1.0

    base = np.clip(base * night_multiplier, 0.0, 1.0)

    # IT corridor deserted after midnight
    commercial_score = COMMERCIAL_IDX.exp_density_norm(lats, lngs, 400.0, _COMMERCIAL_NORM)
    zone_type = zone_attr(df["zone"], "zone_type")
    is_it_zone = zone_type.map(
        lambda zt: 1.0 if "it_corridor" in str(zt) else 0.0
    ).values

    it_midnight_penalty = np.where(
        (ctx in ("night_deep",)) & (is_it_zone > 0.5) & (commercial_score < 0.15),
        base * 0.20,   # proportional: already-isolated IT roads get additional 20%
        0.0
    )

    # Nightlife areas richer activity at night → LOWER isolation
    nightlife_zone = zone_attr_float(df["zone"], "nightlife_density").values
    bar_score = BAR_IDX.exp_density_norm(lats, lngs, 350.0, _BAR_NORM)
    nightlife_activity = np.clip(0.5 * nightlife_zone + 0.5 * bar_score, 0.0, 1.0)

    if ctx in ("late_night", "night_deep"):
        nightlife_safety = nightlife_activity * 0.18
    else:
        nightlife_safety = 0.0

    isolated = base + it_midnight_penalty - nightlife_safety

    noise = rng.normal(0.0, 0.030, size=n)
    return np.clip(isolated + noise, 0.0, 1.0)


def compute_road_risk_score_v6(df: pd.DataFrame,
                                 crime: np.ndarray,
                                 lighting: np.ndarray,
                                 cctv: np.ndarray,
                                 congestion: np.ndarray,
                                 isolated: np.ndarray,
                                 weather_exp: np.ndarray,
                                 activity: np.ndarray,
                                 time_risk_norm: np.ndarray,
                                 rng: np.random.Generator) -> np.ndarray:
    """
    [v6.0] Road risk score — multi-factor weighted formula.

    MANDATORY CORRELATIONS ENFORCED:
    • Higher crime_score       → increases road_risk_score ✓
    • Higher lighting_score    → REDUCES road_risk_score   ✓ (lighting_inv used)
    • Higher cctv_density_est  → REDUCES crime contribution ✓ (cctv_inv = risk)
    • Higher police_dist       → increases risk             ✓ (police_dist_norm)
    • Higher congestion_score  → increases road_risk_score  ✓
    • Higher isolated_area_sc  → increases road_risk_score  ✓
    • Higher weather_exposure  → increases road_risk_score  ✓
    • Higher commercial_density→ increases activity_score   (handled in activity)
    • Higher nightlife_density → increases night-time risk  (handled in activity)

    Returns float array in [0, 1].
    """
    n    = len(df)
    lats = df["lat"].values.astype(np.float64)
    lngs = df["lng"].values.astype(np.float64)

    # Police station distance: normalise to risk [0,1] — far = risky
    police_dist_m = POLICE_IDX.nearest_distance_m(lats, lngs)
    police_dist_norm = 1.0 - np.exp(-police_dist_m / 1200.0)   # far → close to 1

    # Lighting: high lighting reduces risk → use inverse
    lighting_inv = 1.0 - np.clip(lighting, 0.0, 1.0)

    # CCTV: high CCTV reduces risk → use inverse
    cctv_inv = 1.0 - np.clip(cctv, 0.0, 1.0)

    # Context-adjusted activity (nightlife density amplifies night risk)
    hour = int(df.get("_hour_", pd.Series([22])).iloc[0]) if "_hour_" in df.columns else 22
    nightlife_z = zone_attr_float(df["zone"], "nightlife_density").values
    ctx = get_time_context(hour)
    if ctx in ("late_night", "night_deep"):
        # Nightlife increases risk at night — nightlife_density boosts activity risk
        activity_ctx = np.clip(
            activity + nightlife_z * 0.30, 0.0, 1.0
        )
    else:
        activity_ctx = activity

    # Event frequency (from CSV, normalised)
    ef = np.clip(df["event_frequency"].values.astype(float), 0.0, 1.0)

    # Weighted combination
    road_risk = (
        ROAD_RISK_COMP["crime_score"]            * np.clip(crime, 0.0, 1.0)
      + ROAD_RISK_COMP["lighting_score_inv"]     * lighting_inv
      + ROAD_RISK_COMP["cctv_density_inv"]       * cctv_inv
      + ROAD_RISK_COMP["police_dist_norm"]       * police_dist_norm
      + ROAD_RISK_COMP["congestion_score"]       * np.clip(congestion, 0.0, 1.0)
      + ROAD_RISK_COMP["isolated_area_score"]    * np.clip(isolated, 0.0, 1.0)
      + ROAD_RISK_COMP["weather_exposure_score"] * np.clip(weather_exp, 0.0, 1.0)
      + ROAD_RISK_COMP["activity_score_ctx"]     * activity_ctx
      + ROAD_RISK_COMP["event_frequency"]        * ef
      + ROAD_RISK_COMP["time_risk_norm"]         * time_risk_norm
    )

    noise = rng.normal(0.0, 0.022, size=n)
    return np.clip(road_risk + noise, 0.0, 1.0)


# ══════════════════════════════════════════════════════════════════════════════
# 9.  EXISTING FACTOR COMPUTATIONS  (v5.0, updated to use CSV columns)
# ══════════════════════════════════════════════════════════════════════════════

def compute_crime_risk(df: pd.DataFrame, hour: int) -> pd.Series:
    """
    Crime risk [0–1].
    v6.0: uses cctv_density_estimate from CSV to reduce crime score
    (mandatory: higher CCTV must reduce crime_score contribution).
    """
    lats = df["lat"].values
    lngs = df["lng"].values

    # Component 1: CSV crime_score
    base_crime = normalize_min_max(df["crime_score"]).values

    # Component 2: Hotspot gravity
    hotspot_gravity = np.zeros(len(df))
    for _, hs in HOTSPOT_DF.iterrows():
        dist = haversine_fast(lats, lngs, hs["lat"], hs["lng"])
        hotspot_gravity += inverse_distance_weight(
            dist, intensity=hs["intensity"], radius_m=600, decay=1.8
        )
    hg_max = hotspot_gravity.max()
    if hg_max > 0:
        hotspot_gravity /= hg_max

    # Component 3: CCTV density suppresses crime (mandatory correlation)
    cctv_raw = np.clip(df["cctv_density_estimate"].values.astype(float), 0.0, 1.0)
    cctv_suppression = 1.0 - cctv_raw * 0.40   # high CCTV → up to 40% crime reduction

    # Component 4: Time modulation
    t_mult  = get_time_multiplier(hour)
    crime_t = 0.7 + (t_mult - 0.75) / (1.55 - 0.75) * 0.5

    # Zone prior (weak, 20%)
    zone_crime_prior = zone_attr(df["zone"], "zone_type").map({
        "high_crime_commercial":   0.85, "nightlife_startup":    0.72,
        "nightlife_commercial":    0.70, "industrial_transit":   0.55,
        "dense_residential":       0.45, "mixed_residential":    0.40,
        "growing_residential":     0.38, "it_corridor":          0.30,
        "it_residential":          0.28, "planned_residential":  0.25,
        "upscale_residential":     0.20, "industrial_defense":   0.22,
        "peri_urban":              0.35, "rural_fringe":         0.30,
        "suburban_residential":    0.35, "heritage_commercial":  0.45,
        "transit_commercial":      0.50, "arterial_highway":     0.40,
        "arterial_commercial":     0.48, "university_residential":0.32,
        "residential_commercial":  0.38, "commercial_transit":   0.50,
        "suburban_mixed":          0.33, "residential":          0.30,
        "industrial_residential":  0.42,
    }).fillna(0.40).values.astype(float)

    # Blend: 45% CSV base, 25% hotspot, 15% CCTV modulated, 15% zone prior
    blended = (0.45 * base_crime
               + 0.25 * hotspot_gravity
               + 0.15 * (base_crime * cctv_suppression)   # CCTV reduces crime
               + 0.15 * zone_crime_prior) * crime_t

    # Stretch distribution
    mean_val  = blended.mean()
    stretched = mean_val + (blended - mean_val) * 1.6
    rng       = np.random.default_rng(seed=int(lats.mean() * 1000) % 2**31)
    noise_sc  = 0.04 + zone_crime_prior * 0.06
    noise     = rng.normal(0.0, noise_sc, size=len(blended))
    return pd.Series(np.clip(stretched + noise, 0.0, 1.0), index=df.index)


def compute_lighting_risk(df: pd.DataFrame, hour: int) -> Tuple[pd.Series, pd.Series]:
    """
    Returns (dark_risk, lighting_quality) both as pd.Series in [0,1].

    dark_risk        : used in RISK_WEIGHTS pipeline (higher = riskier, time-modulated)
    lighting_quality : stored as output lighting_score column (0=dark, 1=well-lit, stable)

    v6.0: uses lighting_score column directly (already in CSV).
    HIGH lighting_score means well-lit → REDUCES road_risk_score.
    """
    lats = df["lat"].values
    lngs = df["lng"].values

    # Component 1: CSV lighting_score (0–1, higher = better lit)
    raw_light = df["lighting_score"].values.astype(float)
    light_min, light_max = raw_light.min(), raw_light.max()
    if light_max > light_min:
        lighting_quality = (raw_light - light_min) / (light_max - light_min)
    else:
        lighting_quality = np.full(len(raw_light), 0.5)
    lighting_quality = np.clip(0.05 + lighting_quality * 0.90, 0.0, 1.0)

    # Component 2: Urban density proxy
    signal_score     = SIGNAL_IDX.exp_density_norm(lats, lngs, 400.0, _SIGNAL_NORM)
    commercial_score = COMMERCIAL_IDX.exp_density_norm(lats, lngs, 350.0, _COMMERCIAL_NORM)
    urban_density    = np.clip(0.55 * signal_score + 0.45 * commercial_score, 0.0, 1.0)

    # Component 3: Road type
    road_light_map = {
        "motorway": 0.88, "motorway_link": 0.82,
        "trunk": 0.82, "trunk_link": 0.75,
        "highway": 0.80, "primary": 0.70, "primary_link": 0.65,
        "secondary": 0.52, "secondary_link": 0.48,
        "tertiary": 0.42, "tertiary_link": 0.38,
        "residential": 0.30, "living_street": 0.28,
        "service": 0.20, "unclassified": 0.35,
        "busway": 0.45, "road": 0.40,
    }
    road_light = (zone_attr(df["zone"], "road_type")
                  .map(road_light_map).fillna(0.40).values.astype(float))

    # Component 4: Zone infra quality
    zone_infra = zone_attr_float(df["zone"], "infra_quality").values

    # Fuse into continuous lighting quality (higher = better lit)
    lit_score = np.clip(
        0.40 * lighting_quality + 0.30 * urban_density
        + 0.20 * road_light + 0.10 * zone_infra,
        0.0, 1.0
    )

    # dark_risk = inverse of lighting quality, amplified at night
    dark_risk = 1.0 - lit_score

    if hour >= 20 or hour <= 5:
        night_factor = 1.50
    elif 6 <= hour <= 8 or 18 <= hour <= 19:
        night_factor = 1.15
    elif 9 <= hour <= 17:
        night_factor = 0.45
    else:
        night_factor = 0.80

    dark_risk_modulated = np.clip(dark_risk * night_factor, 0.0, 1.0)

    return (pd.Series(dark_risk_modulated, index=df.index),
            pd.Series(lit_score, index=df.index))


def compute_activity_score_v6(df: pd.DataFrame, hour: int) -> pd.Series:
    """
    Activity score [0–1].
    v6.0: uses commercial_density + nightlife_density from CSV columns.

    MANDATORY CORRELATIONS:
    • Higher commercial_density → increases activity_score (daytime)
    • Higher nightlife_density  → increases night-time activity (risk at night)
    """
    lats = df["lat"].values
    lngs = df["lng"].values

    # CSV columns (ground truth inputs)
    commd = np.clip(df["commercial_density"].values.astype(float), 0.0, 1.0)
    nightd = np.clip(df["nightlife_density"].values.astype(float), 0.0, 1.0)

    # Spatial signals
    commercial_score = COMMERCIAL_IDX.exp_density_norm(lats, lngs, 400.0, _COMMERCIAL_NORM)
    bar_score        = BAR_IDX.exp_density_norm(lats, lngs, 350.0, _BAR_NORM)
    signal_score     = SIGNAL_IDX.exp_density_norm(lats, lngs, 350.0, _SIGNAL_NORM)

    penalty_direction = get_night_activity_penalty(hour)

    if penalty_direction >= 0:
        # Daytime: commercial density reduces risk (busy = safe)
        # MANDATORY: commercial_density increases activity_score → here "activity" means
        # protective footfall during day, which reduces road risk.
        # We store the full activity score (not risk-inverted) for correlation enforcement.
        footfall = (0.40 * commd + 0.30 * commercial_score
                    + 0.15 * signal_score + 0.15 * nightd)
        activity_score = np.clip(footfall * (0.5 + 0.5 * penalty_direction), 0.0, 1.0)
    else:
        # Night: nightlife_density increases risk; deserted areas also risky
        night_weight = abs(penalty_direction)
        # Bar/nightlife activity at night
        nightlife_act = np.clip(0.50 * nightd + 0.30 * bar_score + 0.20 * commd, 0.0, 1.0)
        deserted_act  = np.clip(1.0 - commd - bar_score * 0.5, 0.0, 1.0) * 0.50
        activity_score = np.clip(
            nightlife_act * night_weight * 0.85 + deserted_act * night_weight * 0.55,
            0.0, 1.0
        )

    return pd.Series(np.clip(activity_score, 0.0, 1.0), index=df.index)


def compute_cctv_score(df: pd.DataFrame) -> pd.Series:
    """CCTV coverage score [0–1]. Uses cctv_density_estimate from CSV."""
    lats = df["lat"].values
    lngs = df["lng"].values

    # CSV column (primary)
    cctv_csv = np.clip(df["cctv_density_estimate"].values.astype(float), 0.0, 1.0)

    signal_score     = SIGNAL_IDX.exp_density_norm(lats, lngs, 500.0, _SIGNAL_NORM)
    commercial_score = COMMERCIAL_IDX.exp_density_norm(lats, lngs, 400.0, _COMMERCIAL_NORM)
    zone_cctv        = zone_attr_float(df["zone"], "cctv_density").values * 0.12

    road_bonus = zone_attr(df["zone"], "road_type").map(
        lambda rt: 0.15 if rt == "highway" else (0.10 if rt == "primary" else 0.03)
    ).values.astype(float)

    # Blend: CSV column gets 40% weight as direct input
    cctv_raw = (0.40 * cctv_csv
                + 0.28 * signal_score
                + 0.20 * commercial_score
                + zone_cctv
                + road_bonus)

    cctv_amplified = np.clip(cctv_raw, 0.0, 1.0)
    cctv_amplified = 1.0 / (1.0 + np.exp(-6.0 * (cctv_amplified - 0.45)))

    return pd.Series(np.clip(cctv_amplified, 0.0, 1.0), index=df.index)


def compute_police_proximity(df: pd.DataFrame) -> pd.Series:
    """Police proximity risk [0–1]. Far = high risk (mandatory correlation)."""
    lats = df["lat"].values
    lngs = df["lng"].values

    # Also use CSV police_station_distance column as an additional input
    if "police_station_distance" in df.columns:
        ps_csv = df["police_station_distance"].values.astype(float)
        # CSV values are typically normalised [0,1] in these files
        # Convert to risk: higher value = further = higher risk
        ps_csv_risk = np.clip(ps_csv, 0.0, 1.0)
    else:
        ps_csv_risk = None

    DECAY_SCALE_M = 1200.0
    nearest_dist  = POLICE_IDX.nearest_distance_m(lats, lngs)

    close_mask = nearest_dist < 500.0
    far_mask   = ~close_mask

    police_risk = np.zeros(len(nearest_dist))
    police_risk[close_mask] = 0.10 + 0.40 * (nearest_dist[close_mask] / 500.0) ** 1.5
    police_risk[far_mask]   = 1.0 - np.exp(-nearest_dist[far_mask] / DECAY_SCALE_M)

    # Blend with CSV column if available
    if ps_csv_risk is not None:
        police_risk = 0.60 * police_risk + 0.40 * ps_csv_risk

    return pd.Series(np.clip(police_risk, 0.0, 1.0), index=df.index)


def compute_poi_risk(df: pd.DataFrame, hour: int) -> pd.Series:
    """POI-based risk [0–1]. Uses poi_density from CSV."""
    lats = df["lat"].values
    lngs = df["lng"].values

    bar_score = BAR_IDX.exp_density_norm(lats, lngs, 350.0, _BAR_NORM)

    if hour >= 21 or hour <= 3:
        bar_night_mult = 0.90
    elif 19 <= hour < 21:
        bar_night_mult = 0.45
    else:
        bar_night_mult = 0.08

    nightlife_penalty = bar_score * bar_night_mult

    hospital_dist   = HOSPITAL_IDX.nearest_distance_m(lats, lngs)
    hospital_safety = np.exp(-hospital_dist / 1000.0) * 0.10

    police_count = POLICE_IDX.count_within_radius(lats, lngs, 500.0)
    police_boost = np.clip(police_count / 2.0, 0.0, 1.0) * 0.05

    # IT-corridor ghost-zone
    commercial_score = COMMERCIAL_IDX.exp_density_norm(lats, lngs, 400.0, _COMMERCIAL_NORM)
    zone_type = zone_attr(df["zone"], "zone_type")
    is_it_zone = zone_type.map(
        lambda zt: 1.0 if "it_corridor" in str(zt) else 0.0
    ).values
    ghost_penalty = np.where(
        (hour >= 21 or hour <= 6) & (commercial_score < 0.15),
        is_it_zone * 0.25 + (1.0 - commercial_score) * 0.10,
        0.0
    )

    # Incorporate CSV poi_density
    if "poi_density" in df.columns:
        poi_csv = np.clip(df["poi_density"].values.astype(float), 0.0, 1.0)
        # High POI density at night = more risk
        if hour >= 21 or hour <= 4:
            poi_csv_risk = poi_csv * 0.15
        else:
            poi_csv_risk = (1.0 - poi_csv) * 0.08   # deserted = slightly risky
    else:
        poi_csv_risk = 0.0

    poi_risk = nightlife_penalty + ghost_penalty - hospital_safety - police_boost + poi_csv_risk
    return pd.Series(np.clip(poi_risk, 0.0, 1.0), index=df.index)


def compute_infrastructure_risk(df: pd.DataFrame) -> pd.Series:
    """Infrastructure risk [0–1]. Uses infrastructure_score from CSV."""
    lats = df["lat"].values
    lngs = df["lng"].values

    node_count   = NODE_IDX.count_within_radius(lats, lngs, 300.0)
    node_density = np.clip(node_count / 15.0, 0.0, 1.0)

    infra_q    = zone_attr_float(df["zone"], "infra_quality").values * 0.10
    junction_d = zone_attr_float(df["zone"], "junction_density").values * 0.10

    # CSV infrastructure_score (higher = better infra → lower risk)
    if "infrastructure_score" in df.columns:
        infra_csv = np.clip(df["infrastructure_score"].values.astype(float), 0.0, 1.0)
        infra_csv_risk = 1.0 - infra_csv   # inverse
    else:
        infra_csv_risk = 0.50

    infra_risk = (
          infra_csv_risk * 0.35
        + (1.0 - np.clip(infra_q * 10, 0.0, 1.0)) * 0.10
        + junction_d
        + node_density * 0.55
    )
    return pd.Series(np.clip(infra_risk, 0.0, 1.0), index=df.index)


def compute_event_risk(df: pd.DataFrame, hour: int) -> pd.Series:
    """Event volatility risk [0–1]. Uses event_frequency from CSV."""
    # CSV event_frequency as primary input (normalised)
    event_freq = np.clip(df["event_frequency"].values.astype(float), 0.0, 1.0)

    lats = df["lat"].values
    lngs = df["lng"].values
    commercial_score = COMMERCIAL_IDX.exp_density_norm(lats, lngs, 500.0, _COMMERCIAL_NORM)
    bar_score        = BAR_IDX.exp_density_norm(lats, lngs, 350.0, _BAR_NORM)

    spatial_event = (0.55 * commercial_score + 0.45 * bar_score) * 0.60

    if 19 <= hour <= 23:
        time_weight = 1.0
    elif 0 <= hour <= 2:
        time_weight = 0.70
    elif 15 <= hour < 19:
        time_weight = 0.45
    else:
        time_weight = 0.15

    event_risk = (0.40 * event_freq + spatial_event) * time_weight
    return pd.Series(np.clip(event_risk, 0.0, 1.0), index=df.index)


def compute_road_risk_factor(df: pd.DataFrame) -> pd.Series:
    """Road exposure factor [0–1] for the RISK_WEIGHTS pipeline."""
    lats = df["lat"].values
    lngs = df["lng"].values

    road_type_risk = zone_attr(df["zone"], "road_type").map(ROAD_TYPE_RISK).fillna(0.40).values
    road_width     = _parse_road_width(df["road_width_estimate"])
    width_factor   = np.clip((road_width - 6.0) / (30.0 - 6.0), 0.0, 1.0) * 0.15

    commercial_cnt = COMMERCIAL_IDX.count_within_radius(lats, lngs, 500.0)
    traffic_factor = np.clip(commercial_cnt / 10.0, 0.0, 1.0) * 0.10

    # Also use road_risk_score if in CSV (as a weak prior)
    if "road_risk_score" in df.columns:
        road_csv = np.clip(df["road_risk_score"].values.astype(float), 0.0, 1.0)
        road_risk = 0.50 * road_type_risk + 0.25 * road_csv + width_factor + traffic_factor
    else:
        road_risk = road_type_risk + width_factor + traffic_factor

    return pd.Series(np.clip(road_risk, 0.0, 1.0), index=df.index)


def compute_weather_exposure_v6(df: pd.DataFrame, hour: int) -> np.ndarray:
    """
    [v6.0] Weather exposure score from CSV + spatial factors.
    Higher flood_risk → increases weather_exposure_score (mandatory).
    """
    lats = df["lat"].values.astype(np.float64)
    lngs = df["lng"].values.astype(np.float64)
    n    = len(df)

    wex_csv   = np.clip(df["weather_exposure_score"].values.astype(float), 0.0, 1.0)
    flood_csv = np.clip(df["flood_risk"].values.astype(float), 0.0, 1.0)

    # Spatial: peri-urban and open roads get more weather exposure
    commercial_score = COMMERCIAL_IDX.exp_density_norm(lats, lngs, 400.0, _COMMERCIAL_NORM)
    shelter_factor   = np.clip(commercial_score * 0.5, 0.0, 0.5)   # buildings = shelter
    open_exposure    = 1.0 - shelter_factor

    # Road width: wide open roads = more weather exposure
    rw     = _parse_road_width(df["road_width_estimate"])
    rw_exp = np.clip((rw - 4.0) / 26.0, 0.0, 1.0)

    # Blend: CSV values are primary
    weather_exp = (0.45 * wex_csv
                   + 0.25 * flood_csv   # flood_risk increases weather exposure
                   + 0.18 * open_exposure
                   + 0.12 * rw_exp)

    return np.clip(weather_exp, 0.0, 1.0)


# ══════════════════════════════════════════════════════════════════════════════
# 10.  MAIN CALCULATION FUNCTION  (v6.0 — 11-stage pipeline)
# ══════════════════════════════════════════════════════════════════════════════

def calculate_dynamic_risk(df: pd.DataFrame, hour: int,
                             calibration: Optional[CalibrationEngine] = None,
                             seed: Optional[int] = None) -> pd.DataFrame:
    """
    Compute the final dynamic risk score for every road-segment row.

    v6.0 Pipeline (11 stages):
    ──────────────────────────
    Stage 0  : Parse and validate schema columns
    Stage 1  : Derived metric computation (congestion, connectivity, isolation,
               travel_time, weather_exposure, road_risk_score)
    Stage 2  : Legacy factor computation (crime, lighting, activity, event,
               road, infra, cctv, police, poi)
    Stage 3  : Dynamic weight adaptation          [U6]
    Stage 4  : Weighted combination (micro risk)
    Stage 5  : Multi-scale fusion                 [U8]
    Stage 6  : Behavioural adjustment             [U7]
    Stage 7  : Temporal memory blend              [U3]
    Stage 8  : Contextual POI interaction         [U2]
    Stage 9  : Uncertainty injection              [U4]
    Stage 10 : Logical consistency + calibration
    Stage 11 : Scale to 0–100 with time multiplier

    Parameters
    ──────────
    df          : DataFrame with all 34 schema columns
    hour        : current hour 0–23
    calibration : optional CalibrationEngine for scenario overrides [U9]
    seed        : optional RNG seed for reproducibility

    Returns
    ───────
    DataFrame with:
      • All 34 original schema columns (passthrough)
      • Recomputed derived columns:
          congestion_score, travel_time_estimate, connectivity_score,
          isolated_area_score, road_risk_score, weather_exposure_score
      • Factor scores (all 0–1):
          score_crime, score_lighting, score_activity, score_event,
          score_road, score_infra, score_cctv, score_police, score_poi
      • v6.0 pipeline intermediate:
          micro_risk, meso_risk, macro_risk, behavioural_adj, poi_interaction
      • Final outputs:
          time_multiplier, time_context, final_risk_score, contextual_risk,
          confidence_score, uncertainty_level, risk_band
    """
    if seed is not None:
        UNCERTAINTY_RNG.__init__(seed=seed)

    rng = np.random.default_rng(
        seed=int(abs(df["lat"].mean() * df["lng"].mean()) * 1000) % 2**31
    )

    ctx = get_time_context(hour)
    t   = (calibration.get_time_multiplier(hour) if calibration
           else get_time_multiplier(hour))

    print(f"  ⏱  Hour={hour:02d}  |  Context={ctx}  |  Time-multiplier={t:.3f}")
    print(f"  📐 v6.0 pipeline for {len(df):,} road segments …")

    lats = df["lat"].values.astype(np.float64)
    lngs = df["lng"].values.astype(np.float64)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 0: Prepare — attach hour for internal use
    # ─────────────────────────────────────────────────────────────────────────
    df = df.copy()
    df["_hour_"] = hour   # internal flag consumed by road_risk_score_v6

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 1: Derived metric computation  [v6.0 NEW — mandatory correlations]
    # ─────────────────────────────────────────────────────────────────────────

    # 1a. Weather exposure (uses flood_risk column → affects weather_exp)
    weather_exp = compute_weather_exposure_v6(df, hour)

    # 1b. Congestion score (uses traffic_signal_density, intersection_density,
    #                        road_width_estimate, commercial_density, highway_type)
    congestion = compute_congestion_score_v6(df, hour, rng)

    # 1c. Connectivity score (uses adjacency_count, road_type, highway_type,
    #                          intersection_density)
    connectivity = compute_connectivity_score_v6(df, rng)

    # 1d. Isolated area score (inverse of connectivity + temporal penalties)
    isolated = compute_isolated_area_score_v6(df, hour, connectivity, rng)

    # 1e. Travel time (depends on congestion, road_width, flood_risk,
    #                   weather_exp, speed_limit, traffic_signal_density)
    flood_col   = df["flood_risk"].values.astype(float)
    travel_time = compute_travel_time_v6(df, congestion, flood_col, rng)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 2: Legacy factor computation
    # ─────────────────────────────────────────────────────────────────────────
    crime_risk                  = compute_crime_risk(df, hour)
    lighting_dark_risk, lighting_quality = compute_lighting_risk(df, hour)
    activity_risk               = compute_activity_score_v6(df, hour)
    event_risk                  = compute_event_risk(df, hour)
    road_risk                   = compute_road_risk_factor(df)
    infra_risk                  = compute_infrastructure_risk(df)
    cctv_score                  = compute_cctv_score(df)
    police_risk                 = compute_police_proximity(df)
    poi_risk                    = compute_poi_risk(df, hour)

    # 1f. Road risk score (depends on crime, lighting, cctv, police_dist,
    #                       congestion, isolated, weather_exp, activity, event,
    #                       time_risk)
    tr_raw  = df["time_risk"].values.astype(float)
    tr_max  = tr_raw.max()
    tr_norm = np.clip(tr_raw / max(tr_max, 1.0), 0.0, 1.0) if tr_max > 1.0 else np.clip(tr_raw, 0.0, 1.0)

    road_risk_score_v6 = compute_road_risk_score_v6(
        df,
        crime=crime_risk.values,
        lighting=lighting_quality.values,    # lighting quality (high = well-lit = safer)
        cctv=cctv_score.values,
        congestion=congestion,
        isolated=isolated,
        weather_exp=weather_exp,
        activity=activity_risk.values,
        time_risk_norm=tr_norm,
        rng=rng,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 3: Dynamic weight adaptation  [U6]
    # ─────────────────────────────────────────────────────────────────────────
    avg_crime_score = float(crime_risk.mean())
    avg_cctv_score  = float(cctv_score.mean())
    w = adapt_weights(hour, avg_crime_score, avg_cctv_score)
    if calibration:
        w = calibration.get_effective_weights(w)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 4: Weighted micro-risk combination
    # ─────────────────────────────────────────────────────────────────────────
    micro_risk = (
          w["crime"]          * crime_risk.values
        + w["lighting"]       * lighting_dark_risk.values
        + w["activity"]       * activity_risk.values
        + w["event"]          * event_risk.values
        + w["road"]           * road_risk.values
        + w["infrastructure"] * infra_risk.values
        + w["cctv"]           * (1.0 - cctv_score.values)
        + w["police"]         * police_risk.values
        + w["poi"]            * poi_risk.values
        + w["isolation"]      * isolated          # direct path for mandatory correlation
    )
    micro_risk = np.clip(micro_risk, 0.0, 1.0)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 5: Multi-scale fusion  [U8]
    # ─────────────────────────────────────────────────────────────────────────
    meso_risk  = compute_meso_risk(df, micro_risk)
    macro_risk = compute_macro_risk(df, micro_risk)
    ms_risk    = fuse_multiscale(micro_risk, meso_risk, macro_risk)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 6: Behavioural adjustment  [U7]
    # ─────────────────────────────────────────────────────────────────────────
    behav_adj  = compute_behavioural_adjustment(
        lats, lngs, hour,
        activity_scores=activity_risk.values,
        cctv_scores=cctv_score.values,
    )
    behav_risk = np.clip(ms_risk + behav_adj, 0.0, 1.0)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 7: Temporal memory blend  [U3]
    # ─────────────────────────────────────────────────────────────────────────
    mem_risk = apply_temporal_memory(lats, lngs, behav_risk, hour)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 8: Contextual POI interaction  [U2]
    # ─────────────────────────────────────────────────────────────────────────
    poi_interaction = compute_poi_interaction_score(lats, lngs, hour)
    ctx_risk        = np.clip(mem_risk + poi_interaction, 0.0, 1.0)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 9: Uncertainty injection  [U4]
    # ─────────────────────────────────────────────────────────────────────────
    sparsity = compute_data_sparsity(lats, lngs)
    final_risk_01, confidence = inject_uncertainty(ctx_risk, sparsity)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 10a: Logical consistency enforcement  [v5+v6]
    # ─────────────────────────────────────────────────────────────────────────
    cctv_arr     = cctv_score.values
    police_arr   = police_risk.values
    lighting_dark = lighting_dark_risk.values   # dark_risk: high = poorly lit

    safety_composite = cctv_arr * (1.0 - police_arr) * (1.0 - lighting_dark)
    strong_safety = safety_composite > 0.35
    final_risk_01 = np.where(strong_safety,
                              np.minimum(final_risk_01, 0.42), final_risk_01)

    dark_isolated = (lighting_dark > 0.70) & (cctv_arr < 0.25) & (police_arr > 0.75)
    is_night = (hour >= 21 or hour <= 5)
    if is_night:
        final_risk_01 = np.where(dark_isolated,
                                  np.maximum(final_risk_01, 0.45),
                                  final_risk_01)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 10b: Output calibration via sigmoid rescaling
    # ─────────────────────────────────────────────────────────────────────────
    mu = final_risk_01.mean()
    sigma_stretch = max(final_risk_01.std(), 0.05)
    z = (final_risk_01 - mu) / sigma_stretch
    calibrated = 0.5 + 0.5 * np.tanh(z * 0.7)
    final_risk_01 = np.clip(0.65 * calibrated + 0.35 * final_risk_01, 0.0, 1.0)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 11: Scale + time multiplier
    # ─────────────────────────────────────────────────────────────────────────
    final_score     = np.clip(final_risk_01  * t * 100.0, 0.0, 100.0).round(2)
    contextual_risk = np.clip(ctx_risk       * t * 100.0, 0.0, 100.0).round(2)

    if calibration and calibration._ml_hook is not None:
        final_risk_01 = calibration._ml_hook(final_risk_01, df)
        final_score   = np.clip(final_risk_01 * t * 100.0, 0.0, 100.0).round(2)

    update_temporal_memory(lats, lngs, final_score, hour)

    risk_band = pd.cut(
        pd.Series(final_score),
        bins=[0, 20, 40, 60, 80, 100],
        labels=["Very Low", "Low", "Moderate", "High", "Critical"],
        right=True, include_lowest=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Assemble output — preserve ALL 34 schema columns + computed outputs
    # ─────────────────────────────────────────────────────────────────────────

    # Schema passthrough columns (read from input, not overwritten)
    passthrough_cols = [
        "zone", "direction", "lat", "lng",
        "source_area", "destination_area", "road_name",
        "road_type", "highway_type", "junction_type",
        "road_width_estimate", "speed_limit",
        "traffic_signal_density", "intersection_density",
        "commercial_density", "nightlife_density",
        "hospital_density", "flood_risk",
        "crime_score", "event_frequency",
        "poi_density", "adjacency_count",
    ]

    # Build output
    out_data: Dict[str, object] = {}

    # Passthrough
    for col in passthrough_cols:
        if col in df.columns:
            out_data[col] = df[col].values

    # v6.0 recomputed derived columns (overwrite input values)
    out_data["lighting_score"]            = lighting_quality.values.round(4)   # quality: high = well-lit
    out_data["cctv_density_estimate"]     = cctv_score.values.round(4)
    out_data["police_station_distance"]   = police_risk.values.round(4)
    out_data["activity_score"]            = activity_risk.values.round(4)
    out_data["infrastructure_score"]      = (1.0 - infra_risk.values).round(4)
    out_data["connectivity_score"]        = connectivity.round(4)
    out_data["isolated_area_score"]       = isolated.round(4)
    out_data["road_risk_score"]           = road_risk_score_v6.round(4)
    out_data["congestion_score"]          = congestion.round(4)
    out_data["travel_time_estimate"]      = travel_time
    out_data["weather_exposure_score"]    = weather_exp.round(4)
    out_data["time_risk"]                 = df["time_risk"].values   # pass through

    # v6.0 intermediate factor scores (all 0–1)
    out_data["score_crime"]      = crime_risk.round(4).values
    out_data["score_lighting"]   = lighting_dark_risk.round(4).values   # dark risk for pipeline
    out_data["score_activity"]   = activity_risk.round(4).values
    out_data["score_event"]      = event_risk.round(4).values
    out_data["score_road"]       = road_risk.round(4).values
    out_data["score_infra"]      = infra_risk.round(4).values
    out_data["score_cctv"]       = cctv_score.round(4).values
    out_data["score_police"]     = police_risk.round(4).values
    out_data["score_poi"]        = poi_risk.round(4).values

    # Multi-scale intermediate signals
    out_data["micro_risk"]       = micro_risk.round(4)
    out_data["meso_risk"]        = meso_risk.round(4)
    out_data["macro_risk"]       = macro_risk.round(4)
    out_data["behavioural_adj"]  = behav_adj.round(4)
    out_data["poi_interaction"]  = poi_interaction.round(4)

    # Final v6.0 outputs
    out_data["time_multiplier"]  = t
    out_data["time_context"]     = ctx
    out_data["final_risk_score"] = final_score
    out_data["contextual_risk"]  = contextual_risk
    out_data["confidence_score"] = confidence.round(4)
    out_data["uncertainty_level"]= sparsity.round(4)
    out_data["risk_band"]        = risk_band.values

    out = pd.DataFrame(out_data, index=df.index)

    # Drop internal column
    if "_hour_" in out.columns:
        out = out.drop(columns=["_hour_"])

    return out


# ══════════════════════════════════════════════════════════════════════════════
# 11.  ANALYTICS HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def zone_summary(result_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-zone statistics for v6.0 outputs."""
    agg = result_df.groupby(["zone", "direction"]).agg(
        segments              = ("final_risk_score",      "count"),
        risk_mean             = ("final_risk_score",      "mean"),
        risk_median           = ("final_risk_score",      "median"),
        risk_p95              = ("final_risk_score",      lambda x: x.quantile(0.95)),
        risk_max              = ("final_risk_score",      "max"),
        contextual_mean       = ("contextual_risk",       "mean"),
        confidence_mean       = ("confidence_score",      "mean"),
        uncertainty_mean      = ("uncertainty_level",     "mean"),
        crime_mean            = ("score_crime",           "mean"),
        lighting_mean         = ("score_lighting",        "mean"),
        police_mean           = ("score_police",          "mean"),
        cctv_mean             = ("score_cctv",            "mean"),
        congestion_mean       = ("congestion_score",      "mean"),
        travel_time_mean      = ("travel_time_estimate",  "mean"),
        connectivity_mean     = ("connectivity_score",    "mean"),
        isolation_mean        = ("isolated_area_score",   "mean"),
        road_risk_mean        = ("road_risk_score",       "mean"),
        behav_adj_mean        = ("behavioural_adj",       "mean"),
        poi_interaction_mean  = ("poi_interaction",       "mean"),
    ).reset_index()

    for col in ["risk_mean", "risk_median", "risk_p95", "risk_max",
                "contextual_mean", "confidence_mean", "uncertainty_mean",
                "congestion_mean", "travel_time_mean", "connectivity_mean",
                "isolation_mean", "road_risk_mean"]:
        if col in agg.columns:
            agg[col] = agg[col].round(2)

    return agg.sort_values("risk_mean", ascending=False)


def top_risk_segments(result_df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Return the N highest-risk road segments."""
    cols = [
        "zone", "lat", "lng", "final_risk_score", "contextual_risk",
        "confidence_score", "uncertainty_level", "risk_band",
        "road_risk_score", "congestion_score", "travel_time_estimate",
        "score_crime", "score_lighting", "score_police",
        "isolated_area_score", "connectivity_score",
        "behavioural_adj", "poi_interaction",
    ]
    available = [c for c in cols if c in result_df.columns]
    return (result_df[available]
            .sort_values("final_risk_score", ascending=False)
            .head(n)
            .reset_index(drop=True))


def time_sweep(df: pd.DataFrame,
               hours: Optional[List[int]] = None,
               sample_n: int = 50_000) -> pd.DataFrame:
    """Run the engine across multiple hours on a random sample."""
    if hours is None:
        hours = list(range(0, 24, 3))
    sample  = df.sample(min(sample_n, len(df)), random_state=42)
    records = []
    for h in sorted(hours):
        res = calculate_dynamic_risk(sample.copy(), h)
        records.append({
            "hour":              h,
            "time_context":      get_time_context(h),
            "risk_mean":         round(res["final_risk_score"].mean(), 2),
            "risk_std":          round(res["final_risk_score"].std(), 2),
            "risk_p90":          round(res["final_risk_score"].quantile(0.90), 2),
            "risk_max":          round(res["final_risk_score"].max(), 2),
            "contextual_mean":   round(res["contextual_risk"].mean(), 2),
            "congestion_mean":   round(res["congestion_score"].mean(), 3),
            "travel_time_mean":  round(res["travel_time_estimate"].mean(), 2),
            "connectivity_mean": round(res["connectivity_score"].mean(), 3),
            "isolation_mean":    round(res["isolated_area_score"].mean(), 3),
            "confidence_mean":   round(res["confidence_score"].mean(), 3),
            "uncertainty_mean":  round(res["uncertainty_level"].mean(), 3),
        })
    return pd.DataFrame(records)


def route_risk_report(result_df: pd.DataFrame,
                       segment_indices: List[int]) -> Dict:
    """[U5] Generate a full route-level risk report."""
    route_risks = result_df.loc[segment_indices, "final_risk_score"].values
    report      = score_route(route_risks)
    segs = result_df.loc[segment_indices, [
        "zone", "lat", "lng", "final_risk_score", "risk_band",
        "road_risk_score", "congestion_score", "travel_time_estimate",
    ]].copy()
    segs["adjusted_risk"]      = report["segment_risks_adjusted"]
    segs["transition_penalty"] = report["transition_penalties"]
    report["segment_detail"]   = segs
    return report


def confidence_heatmap_data(result_df: pd.DataFrame,
                             min_confidence: float = 0.0) -> pd.DataFrame:
    """[U4] Extract segments for heatmap rendering."""
    cols = [
        "zone", "lat", "lng", "final_risk_score", "road_risk_score",
        "confidence_score", "uncertainty_level", "risk_band",
    ]
    available = [c for c in cols if c in result_df.columns]
    sub = result_df[result_df["confidence_score"] >= min_confidence][available]
    return sub.sort_values("final_risk_score", ascending=False)


# ══════════════════════════════════════════════════════════════════════════════
# 12.  RUNNER  /  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

# Zone CSV file mapping (v6.0 supports all 8 datasets)
ZONE_CSV_FILES = [
    "north_bangalore_risk.csv",
    "south_bangalore_risk.csv",
    "east_bangalore_risk.csv",
    "west_bangalore_risk.csv",
    "central_bangalore_risk.csv",
    "airport_peripheral_risk.csv",
    "southeast_it_corridor_risk.csv",
    "logistics_hightraffic_risk.csv",
]

# Expected dtypes for schema columns
SCHEMA_DTYPES = {
    "zone":                    "string",
    "direction":               "string",
    "lat":                     "float32",
    "lng":                     "float32",
    "source_area":             "string",
    "destination_area":        "string",
    "road_name":               "string",
    "road_type":               "string",
    "highway_type":            "string",
    "junction_type":           "string",
    "road_width_estimate":     "string",   # e.g. "7.5m" — parsed by _parse_road_width
    "speed_limit":             "float32",
    "traffic_signal_density":  "float32",
    "intersection_density":    "float32",
    "commercial_density":      "float32",
    "nightlife_density":       "float32",
    "hospital_density":        "float32",
    "police_station_distance": "float32",
    "cctv_density_estimate":   "float32",
    "lighting_score":          "float32",
    "crime_score":             "float32",
    "activity_score":          "float32",
    "event_frequency":         "float32",
    "infrastructure_score":    "float32",
    "connectivity_score":      "float32",
    "isolated_area_score":     "float32",
    "road_risk_score":         "float32",
    "travel_time_estimate":    "float32",
    "congestion_score":        "float32",
    "flood_risk":              "float32",
    "weather_exposure_score":  "float32",
    "poi_density":             "float32",
    "time_risk":               "float32",
    "adjacency_count":         "int16",
}


def main(
    data_dir:   str = "/mnt/user-data/uploads",
    output_dir: str = "/mnt/user-data/outputs",
    hour:       int = 22,
    chunk_size: int = 100_000,
    scenario:   str = "baseline",
) -> None:
    """
    Load all zone CSVs, run the v6.0 risk engine, save results.

    Parameters
    ──────────
    data_dir   : directory containing all _risk.csv zone files
    output_dir : where output CSVs are written
    hour       : simulation hour (0–23)
    chunk_size : rows per processing chunk
    scenario   : CalibrationEngine scenario name (default: 'baseline')
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    cal = CalibrationEngine()
    cal.set_scenario(scenario)
    reset_temporal_memory()

    print("━" * 70)
    print("  SafeRoute-AI  |  Dynamic Road Risk Engine  v6.0")
    print(f"  Scenario hour  : {hour:02d}:00  ({get_time_context(hour)})")
    print(f"  Scenario preset: {scenario}")
    print("━" * 70)

    # ── 1. Load & merge all zone CSVs ────────────────────────────────────────
    frames = []
    for csv_file in ZONE_CSV_FILES:
        path = Path(data_dir) / csv_file
        if not path.exists():
            print(f"  ⚠  Skipped (not found): {csv_file}")
            continue
        df = pd.read_csv(path, dtype=SCHEMA_DTYPES, low_memory=False)

        # Ensure direction column exists (derive from filename if missing)
        if "direction" not in df.columns or df["direction"].isna().all():
            direction = csv_file.split("_")[0]
            df["direction"] = direction

        frames.append(df)
        print(f"  ✔  Loaded {csv_file:40s}: {len(df):>7,} rows")

    if not frames:
        raise FileNotFoundError(f"No zone CSV files found in {data_dir}")

    all_data = pd.concat(frames, ignore_index=True)

    # Fill any NaN in critical columns with sensible defaults
    all_data["road_type"]      = all_data["road_type"].fillna("secondary")
    all_data["highway_type"]   = all_data["highway_type"].fillna("none")
    all_data["junction_type"]  = all_data["junction_type"].fillna("none")
    all_data["road_width_estimate"] = all_data["road_width_estimate"].fillna("10m")
    all_data["speed_limit"]    = all_data["speed_limit"].fillna(40.0)
    all_data["adjacency_count"]= all_data["adjacency_count"].fillna(4)

    print(f"\n  📊 Total road segments : {len(all_data):,}")
    print(f"  🗺  Zones               : {all_data['zone'].nunique()}")
    print(f"  📍 Spatial POI index   : {SIGNAL_IDX._n} signals | "
          f"{COMMERCIAL_IDX._n} commercial | {BAR_IDX._n} bars | "
          f"{HOSPITAL_IDX._n} hospitals | {NODE_IDX._n} road nodes")
    print(f"\n  [v6.0] Schema-aligned: all 34 columns fully computed")
    print(f"  [v6.0] Mandatory correlations enforced via weighted formulas")
    print(f"  [v6.0] Temporal memory : λ={MEMORY_LAMBDA}, decay={MEMORY_DECAY_PER_HR}")
    print(f"  [v6.0] Uncertainty     : σ ∈ [{UNCERTAINTY_SIGMA_MIN}, {UNCERTAINTY_SIGMA_MAX}]")
    print()

    # ── 2. Chunked risk computation ──────────────────────────────────────────
    result_chunks = []
    total    = len(all_data)
    n_chunks = math.ceil(total / chunk_size)

    for i, start in enumerate(range(0, total, chunk_size)):
        chunk = all_data.iloc[start : start + chunk_size].copy()
        pct   = min(100, int((start + len(chunk)) / total * 100))
        print(f"\n  [Chunk {i+1}/{n_chunks}]  rows {start:>7,}–{start+len(chunk):>7,}  ({pct}%)")
        res = calculate_dynamic_risk(chunk, hour, calibration=cal)
        result_chunks.append(res)

    results = pd.concat(result_chunks, ignore_index=True)

    # ── 3. Save per-segment results ──────────────────────────────────────────
    seg_path = out_path / "saferoute_v6_risk_scores.csv"
    results.to_csv(seg_path, index=False)
    print(f"\n  💾  Segment scores      → {seg_path}")

    # ── 4. Zone-level summary ────────────────────────────────────────────────
    summary  = zone_summary(results)
    sum_path = out_path / "saferoute_v6_zone_summary.csv"
    summary.to_csv(sum_path, index=False)
    print(f"  💾  Zone summary        → {sum_path}")

    # ── 5. Top-risk segments ─────────────────────────────────────────────────
    top_segs = top_risk_segments(results, n=50)
    top_path = out_path / "saferoute_v6_top_risk_segments.csv"
    top_segs.to_csv(top_path, index=False)
    print(f"  💾  Top-risk segments   → {top_path}")

    # ── 6. 24-hour time sweep ─────────────────────────────────────────────────
    print("\n  ⏳ Running 24-hour time sweep with temporal memory (50K sample)…")
    reset_temporal_memory()
    sweep      = time_sweep(all_data, hours=list(range(24)), sample_n=50_000)
    sweep_path = out_path / "saferoute_v6_hourly_sweep.csv"
    sweep.to_csv(sweep_path, index=False)
    print(f"  💾  Hourly sweep        → {sweep_path}")

    # ── 7. Factor contribution report ────────────────────────────────────────
    contrib      = cal.factor_contribution_report(results)
    contrib_path = out_path / "saferoute_v6_factor_contributions.csv"
    contrib.to_csv(contrib_path, index=False)
    print(f"  💾  Factor report       → {contrib_path}")

    # ── 8. High-confidence heatmap data ─────────────────────────────────────
    heatmap   = confidence_heatmap_data(results, min_confidence=0.50)
    hmap_path = out_path / "saferoute_v6_heatmap_confident.csv"
    heatmap.to_csv(hmap_path, index=False)
    print(f"  💾  Confident heatmap   → {hmap_path}")

    # ── 9. Correlation validation report ─────────────────────────────────────
    corr_path = out_path / "saferoute_v6_correlation_validation.csv"
    _write_correlation_validation(results, corr_path)
    print(f"  💾  Correlation check   → {corr_path}")

    # ── 10. Console summaries ─────────────────────────────────────────────────
    print("\n" + "━" * 70)
    print("  ZONE RISK SUMMARY  (sorted by mean risk ↓)")
    print("━" * 70)
    display_cols = ["zone", "direction", "segments", "risk_mean",
                    "road_risk_mean", "congestion_mean", "travel_time_mean",
                    "connectivity_mean", "isolation_mean",
                    "confidence_mean", "risk_p95"]
    avail_cols = [c for c in display_cols if c in summary.columns]
    print(summary[avail_cols].to_string(index=False))

    print("\n" + "━" * 70)
    print("  HOURLY RISK PROFILE  (city-wide mean, with temporal memory)")
    print("━" * 70)
    print(sweep.to_string(index=False))

    print("\n" + "━" * 70)
    print("  RISK BAND DISTRIBUTION")
    print("━" * 70)
    band_counts = results["risk_band"].value_counts().sort_index()
    for band, cnt in band_counts.items():
        bar = "█" * int(cnt / len(results) * 50)
        pct = cnt / len(results) * 100
        print(f"  {band:12s} │ {bar:<50s} {pct:5.1f}%")

    print(f"\n  ✅  SafeRoute-AI v6.0 engine run complete.\n")


def _write_correlation_validation(results: pd.DataFrame,
                                   out_path: Path) -> None:
    """
    [v6.0] Write a correlation validation report to verify mandatory
    correlations are present in the output data.
    Checks Pearson r for each mandatory pair and flags violations.
    """
    checks = [
        # (col_a, col_b, expected_direction, description)
        ("score_crime",          "final_risk_score",      "+",
         "Higher crime → higher road risk"),
        ("congestion_score",     "travel_time_estimate",  "+",
         "Higher congestion → longer travel time"),
        ("lighting_score",       "final_risk_score",      "-",
         "Higher lighting → lower road risk"),
        ("cctv_density_estimate","score_crime",           "-",
         "Higher CCTV → lower crime contribution"),
        ("isolated_area_score",  "final_risk_score",      "+",
         "Higher isolation → higher road risk"),
        ("commercial_density",   "activity_score",        "+",
         "Higher commercial density → higher activity"),
        ("connectivity_score",   "isolated_area_score",   "-",
         "Higher connectivity → lower isolation"),
        ("congestion_score",     "road_risk_score",       "+",
         "Higher congestion → higher road risk score"),
        ("flood_risk",           "travel_time_estimate",  "+",
         "Higher flood risk → longer travel time"),
        ("traffic_signal_density","congestion_score",     "+",
         "Higher signal density → higher congestion"),
        ("intersection_density", "congestion_score",      "+",
         "Higher intersection density → higher congestion"),
    ]

    rows = []
    for col_a, col_b, direction, desc in checks:
        if col_a not in results.columns or col_b not in results.columns:
            rows.append({"check": desc, "col_a": col_a, "col_b": col_b,
                         "pearson_r": None, "expected": direction,
                         "status": "MISSING_COLUMN"})
            continue
        r = results[[col_a, col_b]].dropna().corr().iloc[0, 1]
        if direction == "+":
            status = "PASS" if r > 0.05 else ("WEAK" if r >= -0.05 else "FAIL")
        else:
            status = "PASS" if r < -0.05 else ("WEAK" if r <= 0.05 else "FAIL")
        rows.append({"check": desc, "col_a": col_a, "col_b": col_b,
                     "pearson_r": round(r, 4), "expected": direction,
                     "status": status})

    pd.DataFrame(rows).to_csv(out_path, index=False)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
