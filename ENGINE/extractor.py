"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          SafeRoute-AI  |  OSM Extractor  v6.1  (patched)                   ║
║          Target City   : Bengaluru, Karnataka, India                        ║
║          Fixes applied :                                                    ║
║            [1] _get_hw()      — NaN highway tag crashes                    ║
║            [2] _junction_type() — float-in-dict crashes                    ║
║            [3] node_data store — NaN values stripped at source             ║
╚══════════════════════════════════════════════════════════════════════════════╝

USAGE
─────
    python extractor.py                          # all zones, daytime (09:00)
    python extractor.py --hour 22                # night-time time_risk
    python extractor.py --zones north central    # specific zones only
    python extractor.py --resume                 # skip already-done CSVs
    python extractor.py --validate-only          # QA on existing CSVs
    python extractor.py --output-dir /tmp/data   # custom output path

DEPENDENCIES  (auto-installed on first run)
───────────────────────────────────────────
    osmnx, geopandas, shapely, pandas, numpy, scipy, scikit-learn, requests
"""

from __future__ import annotations

# ── stdlib ────────────────────────────────────────────────────────────────────
import argparse
import logging
import math
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

warnings.filterwarnings("ignore")

# ── Auto-install dependencies ─────────────────────────────────────────────────
REQUIRED_PACKAGES = [
    "osmnx>=1.9.0", "geopandas>=0.14.0", "shapely>=2.0.0",
    "pandas>=2.0.0", "numpy>=1.26.0", "scipy>=1.12.0",
    "scikit-learn>=1.4.0", "requests>=2.31.0",
]

def _install_dependencies() -> None:
    print("  [Setup] Checking / installing dependencies …")
    for pkg in REQUIRED_PACKAGES:
        pkg_name = pkg.split(">=")[0].split("==")[0]
        try:
            __import__(pkg_name.replace("-", "_"))
        except ImportError:
            print(f"  [Setup] Installing {pkg} …")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pkg, "-q"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    print("  [Setup] All dependencies satisfied.\n")

_install_dependencies()

# ── Third-party ───────────────────────────────────────────────────────────────
import geopandas as gpd            # noqa: E402
import numpy as np                 # noqa: E402
import osmnx as ox                 # noqa: E402
import pandas as pd                # noqa: E402
import requests                    # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
from shapely.geometry import LineString, Point  # noqa: E402
from sklearn.preprocessing import MinMaxScaler  # noqa: E402

# ══════════════════════════════════════════════════════════════════════════════
# 1.  LOGGING
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("saferoute_extractor")

# ══════════════════════════════════════════════════════════════════════════════
# 2.  OUTPUT PATH & ZONE → FILE MAPPING
# ══════════════════════════════════════════════════════════════════════════════

OUTPUT_DIR = Path(r"D:\Project\SafeRoute AI - v6\ENGINE\datasets")

ZONE_FILE_MAP: Dict[str, str] = {
    "north":      "north_bangalore_risk.csv",
    "northeast":  "northeast_bangalore_risk.csv",
    "east":       "east_bangalore_risk.csv",
    "southeast":  "southeast_bangalore_risk.csv",
    "central":    "central_bangalore_risk.csv",
    "south":      "south_bangalore_risk.csv",
    "southwest":  "southwest_bangalore_risk.csv",
    "west":       "west_bangalore_risk.csv",
    "northwest":  "northwest_bangalore_risk.csv",
    "it_belt":    "southeast_it_corridor_risk.csv",
    "airport":    "airport_peripheral_risk.csv",
    "peripheral": "logistics_hightraffic_risk.csv",
    "industrial": "logistics_hightraffic_risk.csv",
}

# ══════════════════════════════════════════════════════════════════════════════
# 3.  AREA REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

def get_zone_areas() -> Dict[str, List[str]]:
    return {
        "north": [
            "Hebbal, Bengaluru", "Yelahanka, Bengaluru", "Jakkur, Bengaluru",
            "Thanisandra, Bengaluru", "Nagawara, Bengaluru", "Hennur, Bengaluru",
            "Kogilu, Bengaluru", "Vidyaranyapura, Bengaluru", "Sahakara Nagar, Bengaluru",
            "Kodigehalli, Bengaluru", "RT Nagar, Bengaluru", "Ganganagar, Bengaluru",
            "Sanjay Nagar, Bengaluru", "New BEL Road, Bengaluru", "Dollars Colony, Bengaluru",
            "Kempapura, Bengaluru", "Byatarayanapura, Bengaluru", "Bagalur, Bengaluru",
            "Chikkajala, Bengaluru", "Devanahalli, Bengaluru", "Bettahalasur, Bengaluru",
            "Airport Road, Bengaluru", "Allalasandra, Bengaluru",
            "Attur Layout, Bengaluru", "Judicial Layout, Bengaluru",
        ],
        "northeast": [
            "Kalyan Nagar, Bengaluru", "HRBR Layout, Bengaluru", "Banaswadi, Bengaluru",
            "Horamavu, Bengaluru", "Ramamurthy Nagar, Bengaluru", "Kasturi Nagar, Bengaluru",
            "Kammanahalli, Bengaluru", "TC Palya, Bengaluru", "Kalkere, Bengaluru",
            "Byrathi, Bengaluru", "Narayanapura, Bengaluru", "NRI Layout, Bengaluru",
            "HBR Layout, Bengaluru", "Lingarajapuram, Bengaluru",
        ],
        "east": [
            "Indiranagar, Bengaluru", "HAL, Bengaluru", "Domlur, Bengaluru",
            "CV Raman Nagar, Bengaluru", "Baiyappanahalli, Bengaluru",
            "Mahadevapura, Bengaluru", "Hoodi, Bengaluru", "KR Puram, Bengaluru",
            "Brookefield, Bengaluru", "Whitefield, Bengaluru", "Kadugodi, Bengaluru",
            "Varthur, Bengaluru", "Bellandur, Bengaluru", "Marathahalli, Bengaluru",
            "Doddanekkundi, Bengaluru", "Kundalahalli, Bengaluru", "AECS Layout, Bengaluru",
            "Thubarahalli, Bengaluru", "Channasandra, Bengaluru", "Seegehalli, Bengaluru",
            "Nallurhalli, Bengaluru", "Battarahalli, Bengaluru",
        ],
        "southeast": [
            "HSR Layout, Bengaluru", "Agara, Bengaluru", "Sarjapur Road, Bengaluru",
            "Kaikondrahalli, Bengaluru", "Kasavanahalli, Bengaluru", "Haralur, Bengaluru",
            "Ambalipura, Bengaluru", "Carmelaram, Bengaluru", "Doddakannelli, Bengaluru",
            "Electronic City Phase 1, Bengaluru", "Electronic City Phase 2, Bengaluru",
            "Neeladri Nagar, Bengaluru", "Singasandra, Bengaluru", "Begur, Bengaluru",
            "Bommanahalli, Bengaluru", "Hongasandra, Bengaluru", "Kudlu, Bengaluru",
            "Parappana Agrahara, Bengaluru",
        ],
        "central": [
            "MG Road, Bengaluru", "Brigade Road, Bengaluru", "Richmond Town, Bengaluru",
            "Richmond Circle, Bengaluru", "Residency Road, Bengaluru",
            "Cubbon Park, Bengaluru", "Vasanth Nagar, Bengaluru", "Shivajinagar, Bengaluru",
            "Infantry Road, Bengaluru", "Cunningham Road, Bengaluru",
            "Race Course Road, Bengaluru", "Seshadripuram, Bengaluru",
            "Palace Road, Bengaluru", "High Grounds, Bengaluru",
            "Gandhinagar, Bengaluru", "Majestic, Bengaluru",
            "Cottonpet, Bengaluru", "Chamarajpet, Bengaluru",
        ],
        "south": [
            "Jayanagar, Bengaluru", "JP Nagar, Bengaluru", "Banashankari, Bengaluru",
            "Basavanagudi, Bengaluru", "Uttarahalli, Bengaluru",
            "Padmanabhanagar, Bengaluru", "Kumaraswamy Layout, Bengaluru",
            "ISRO Layout, Bengaluru", "Anjanapura, Bengaluru",
            "Kanakapura Road, Bengaluru", "Konanakunte, Bengaluru",
            "Yelachenahalli, Bengaluru", "Vajarahalli, Bengaluru",
            "Talaghattapura, Bengaluru", "Arekere, Bengaluru",
            "Bilekahalli, Bengaluru", "Hulimavu, Bengaluru", "Gottigere, Bengaluru",
            "Kalena Agrahara, Bengaluru", "Doddakallasandra, Bengaluru",
            "Subramanyapura, Bengaluru",
        ],
        "southwest": [
            "Kengeri, Bengaluru", "Rajarajeshwari Nagar, Bengaluru",
            "BEML Layout, Bengaluru", "Nagarbhavi, Bengaluru", "Ullal, Bengaluru",
            "Gnana Bharathi, Bengaluru", "Mallathahalli, Bengaluru",
            "Jnanabharathi, Bengaluru", "Chandra Layout, Bengaluru",
            "Deepanjali Nagar, Bengaluru", "Mysore Road, Bengaluru",
        ],
        "west": [
            "Vijayanagar, Bengaluru", "Attiguppe, Bengaluru",
            "Basaveshwaranagar, Bengaluru", "Mahalakshmi Layout, Bengaluru",
            "Rajajinagar, Bengaluru", "Malleswaram, Bengaluru",
            "Yeshwanthpur, Bengaluru", "Peenya, Bengaluru",
            "Nandini Layout, Bengaluru", "Kurubarahalli, Bengaluru",
            "Kamakshipalya, Bengaluru", "Magadi Road, Bengaluru",
            "Sunkadakatte, Bengaluru", "Herohalli, Bengaluru",
            "Andrahalli, Bengaluru",
        ],
        "northwest": [
            "Dasarahalli, Bengaluru", "Jalahalli, Bengaluru",
            "Jalahalli West, Bengaluru", "Chokkasandra, Bengaluru",
            "T Dasarahalli, Bengaluru", "Hesaraghatta, Bengaluru",
            "Soladevanahalli, Bengaluru", "Abbigere, Bengaluru",
            "Chikkabanavara, Bengaluru", "Bagalagunte, Bengaluru",
            "Nelamangala, Bengaluru",
        ],
        "it_belt": [
            "Whitefield, Bengaluru", "Outer Ring Road, Bengaluru",
            "Bellandur, Bengaluru", "Marathahalli, Bengaluru",
            "Mahadevapura, Bengaluru", "HSR Layout, Bengaluru",
            "Sarjapur Road, Bengaluru", "Electronic City, Bengaluru",
            "Brookefield, Bengaluru", "KR Puram, Bengaluru", "Hoodi, Bengaluru",
        ],
        "airport": [
            "Hebbal, Bengaluru", "Jakkur, Bengaluru", "Yelahanka, Bengaluru",
            "Bagalur, Bengaluru", "Chikkajala, Bengaluru", "Bettahalasur, Bengaluru",
            "Devanahalli, Bengaluru", "Aerospace Park, Bengaluru",
            "KIADB Tech Park, Bengaluru",
        ],
        "peripheral": [
            "Devanahalli, Bengaluru", "Hoskote, Bengaluru",
            "Budigere Cross, Bengaluru", "Varthur, Bengaluru",
            "Gunjur, Bengaluru", "Sarjapur, Bengaluru", "Anekal, Bengaluru",
            "Jigani, Bengaluru", "Attibele, Bengaluru", "Chandapura, Bengaluru",
            "Nelamangala, Bengaluru", "Hesaraghatta, Bengaluru", "Bagalur, Bengaluru",
        ],
        "industrial": [
            "Peenya, Bengaluru", "Bommasandra, Bengaluru", "Jigani, Bengaluru",
            "Electronic City, Bengaluru", "Whitefield, Bengaluru",
            "Rajajinagar, Bengaluru",
        ],
    }

# ══════════════════════════════════════════════════════════════════════════════
# 4.  OVERPASS HELPERS
# ══════════════════════════════════════════════════════════════════════════════

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

_OVERPASS_DELAY = 2.5

def _overpass_query(query: str, retries: int = 4) -> dict:
    """Execute an Overpass QL query, rotating endpoints on failure."""
    for attempt in range(retries):
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        try:
            r = requests.post(
                endpoint,
                data={"data": query},
                timeout=120,
                headers={"User-Agent": "SafeRoute-AI-OSM-Agent/6.1"},
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            wait = _OVERPASS_DELAY * (2 ** attempt)
            log.warning(
                "Overpass attempt %d failed (%s) — retrying in %.0fs",
                attempt + 1, exc, wait,
            )
            time.sleep(wait)
    raise RuntimeError(f"Overpass query failed after {retries} attempts")


def fetch_pois_in_bbox(
    bbox: Tuple[float, float, float, float],
    tag_filter: str,
) -> List[Tuple[float, float]]:
    """Return list of (lat, lng) for OSM nodes/ways matching tag_filter in bbox."""
    s, w, n, e = bbox
    q = f"""
    [out:json][timeout:60];
    (
      node[{tag_filter}]({s},{w},{n},{e});
      way[{tag_filter}]({s},{w},{n},{e});
    );
    out center;
    """
    data = _overpass_query(q)
    coords = []
    for el in data.get("elements", []):
        if el["type"] == "node":
            coords.append((el["lat"], el.get("lon", el.get("lng", 0.0))))
        elif el.get("center"):
            coords.append((el["center"]["lat"], el["center"]["lon"]))
    return coords

# ══════════════════════════════════════════════════════════════════════════════
# 5.  ROAD-NETWORK CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

HIGHWAY_TYPES_WANTED = [
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link",
    "secondary", "secondary_link",
    "tertiary", "tertiary_link",
    "residential", "living_street",
    "service", "unclassified", "busway",
]

ROAD_TYPE_MAP: Dict[str, str] = {
    "motorway": "highway",      "motorway_link": "highway",
    "trunk": "highway",         "trunk_link": "highway",
    "primary": "primary",       "primary_link": "primary",
    "secondary": "secondary",   "secondary_link": "secondary",
    "tertiary": "tertiary",     "tertiary_link": "tertiary",
    "residential": "residential","living_street": "residential",
    "service": "service",
    "unclassified": "unclassified",
    "busway": "secondary",
}

SPEED_DEFAULTS: Dict[str, float] = {
    "motorway": 80, "motorway_link": 60, "trunk": 80, "trunk_link": 60,
    "primary": 60,  "primary_link": 50,
    "secondary": 50,"secondary_link": 40,
    "tertiary": 40, "tertiary_link": 30,
    "residential": 30,"living_street": 20,
    "service": 20,  "unclassified": 30, "busway": 40,
}

WIDTH_BY_LANES: Dict[int, str] = {1: "4m", 2: "7m", 3: "10m", 4: "12m", 6: "18m"}

LIT_MAP: Dict[str, float] = {
    "yes": 0.85, "24/7": 1.0, "no": 0.10, "auto": 0.60,
    "limited": 0.45, "interval": 0.55,
}

ROAD_TYPE_LIGHT: Dict[str, float] = {
    "motorway": 0.80, "motorway_link": 0.75, "trunk": 0.80, "trunk_link": 0.75,
    "highway": 0.80, "primary": 0.65, "primary_link": 0.60,
    "secondary": 0.50, "secondary_link": 0.45,
    "tertiary": 0.38, "tertiary_link": 0.34,
    "residential": 0.28, "living_street": 0.25,
    "service": 0.18, "unclassified": 0.32, "busway": 0.42,
}

ROAD_TYPE_QUALITY: Dict[str, float] = {
    "motorway": 0.90, "trunk": 0.85, "highway": 0.88,
    "primary": 0.75, "primary_link": 0.70,
    "secondary": 0.60, "secondary_link": 0.55,
    "tertiary": 0.50, "tertiary_link": 0.46,
    "residential": 0.35, "living_street": 0.28,
    "service": 0.25, "unclassified": 0.38, "busway": 0.40,
}

ROAD_TYPE_CONN: Dict[str, float] = {
    "motorway": 0.95, "trunk": 0.90, "highway": 0.90,
    "primary": 0.78, "primary_link": 0.72,
    "secondary": 0.60, "secondary_link": 0.55,
    "tertiary": 0.50, "tertiary_link": 0.46,
    "residential": 0.35, "living_street": 0.28,
    "service": 0.28, "unclassified": 0.42, "busway": 0.55,
}

ROAD_TYPE_RISK: Dict[str, float] = {
    "motorway": 0.78, "trunk": 0.72, "highway": 0.72,
    "primary": 0.58, "primary_link": 0.52,
    "secondary": 0.40, "secondary_link": 0.38,
    "tertiary": 0.36, "tertiary_link": 0.34,
    "residential": 0.30, "living_street": 0.25,
    "service": 0.28, "unclassified": 0.35, "busway": 0.32,
}

# ══════════════════════════════════════════════════════════════════════════════
# 6.  ROAD ATTRIBUTE PARSERS
# ══════════════════════════════════════════════════════════════════════════════

def _parse_speed(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, list):
        val = val[0]
    s = str(val).replace("mph", "").replace("km/h", "").replace("kmh", "").strip()
    try:
        v = float(s)
        if "mph" in str(val):
            v *= 1.60934
        return v
    except ValueError:
        return 0.0


def _parse_width(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, list):
        val = val[0]
    s = str(val).replace("m", "").replace("'", "").strip()
    try:
        v = float(s)
        return v if 1 < v < 60 else None
    except ValueError:
        return None


def _parse_lanes(val) -> int:
    if val is None:
        return 2
    if isinstance(val, list):
        val = val[0]
    try:
        return max(1, int(float(str(val))))
    except ValueError:
        return 2


def _width_estimate(width_m: Optional[float], lanes: int) -> str:
    if width_m is not None and 1 < width_m < 60:
        return f"{width_m:.1f}m"
    for lane_count in sorted(WIDTH_BY_LANES.keys(), reverse=True):
        if lanes >= lane_count:
            return WIDTH_BY_LANES[lane_count]
    return "4m"


# ── FIX 1: _get_hw — guard against NaN float values ──────────────────────────
def _get_hw(val) -> str:
    """
    Safely parse the OSM 'highway' tag to a lowercase string.

    BUG FIXED: In v6.0, when val was NaN (a float), the check `if val`
    evaluated to True for non-zero floats, so str(nan).lower() = 'nan'
    slipped through.  Worse, the `in` membership check on a raw float
    raised 'argument of type float is not iterable'.  We now explicitly
    detect NaN/None before calling str().
    """
    if isinstance(val, list):
        if not val:                          # FIX 5: empty list → unclassified
            return "unclassified"
        val = val[0]
    if val is None:
        return "unclassified"
    if isinstance(val, float):              # catches NaN, inf, etc.
        return "unclassified"              # floats are never valid highway tags
    s = str(val).strip().lower()
    if not s or s == "nan":                 # FIX 5: never return "nan"
        return "unclassified"
    return s


# ── FIX 2: _junction_type — guard against non-dict / NaN values ───────────────
def _junction_type(node_tags) -> str:
    """
    Classify the junction type from an OSM node's tag dict.

    BUG FIXED: In v6.0, node_tags could arrive as a float (NaN) when a
    node row had no tag columns.  The check `"crossing" in node_tags`
    then raised 'argument of type float is not iterable'.  We now
    validate that node_tags is an actual dict, and coerce every tag value
    we read to str before comparison.
    """
    if not isinstance(node_tags, dict):
        return "none"

    hw = node_tags.get("highway", "")
    if not isinstance(hw, str):
        hw = "" if (isinstance(hw, float) and math.isnan(hw)) else str(hw)

    jn = node_tags.get("junction", "")
    if not isinstance(jn, str):
        jn = "" if (isinstance(jn, float) and math.isnan(jn)) else str(jn)

    if hw == "traffic_signals" or "traffic_signal" in jn:
        return "traffic_signals"
    if jn == "roundabout" or node_tags.get("oneway", "") == "roundabout":
        return "roundabout"
    if hw == "crossing" or "crossing" in node_tags:
        return "crossing"
    return "none"

# ══════════════════════════════════════════════════════════════════════════════
# 7.  SPATIAL DENSITY ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class DensityEngine:
    """Vectorised spatial density via cKDTree (lat/lng → approx metres)."""

    def __init__(self, coords: List[Tuple[float, float]]) -> None:
        if coords:
            arr = np.array(coords, dtype=np.float64)
            self._xy = np.column_stack([
                arr[:, 0] * 111320.0,
                arr[:, 1] * 111320.0 * np.cos(np.radians(arr[:, 0].mean())),
            ])
            self._tree = cKDTree(self._xy)
            self._n = len(coords)
        else:
            self._n = 0
            self._tree = None

    def count_within(self, lats: np.ndarray, lngs: np.ndarray, radius_m: float) -> np.ndarray:
        if self._n == 0:
            return np.zeros(len(lats))
        lat_mean = lats.mean()
        xy = np.column_stack([
            lats * 111320.0,
            lngs * 111320.0 * np.cos(np.radians(lat_mean)),
        ])
        return np.array(
            [len(self._tree.query_ball_point(p, radius_m)) for p in xy], dtype=float
        )

    def nearest_dist_m(self, lats: np.ndarray, lngs: np.ndarray) -> np.ndarray:
        if self._n == 0:
            return np.full(len(lats), 99999.0)
        lat_mean = lats.mean()
        xy = np.column_stack([
            lats * 111320.0,
            lngs * 111320.0 * np.cos(np.radians(lat_mean)),
        ])
        dists, _ = self._tree.query(xy, k=1)
        return dists


def _normalize(arr: np.ndarray, lo: float = 0.0, hi: float = 1.0) -> np.ndarray:
    mn, mx = arr.min(), arr.max()
    if mx == mn:
        return np.full(len(arr), (lo + hi) / 2.0)
    return lo + (arr - mn) / (mx - mn) * (hi - lo)


def _clip01(arr: np.ndarray) -> np.ndarray:
    return np.clip(arr, 0.0, 1.0)

# ══════════════════════════════════════════════════════════════════════════════
# 8.  BASELINES
# ══════════════════════════════════════════════════════════════════════════════

CRIME_BASELINES: Dict[str, float] = {
    "majestic": 0.85, "kr market": 0.80, "magadi road": 0.78,
    "cottonpet": 0.76, "gandhinagar": 0.74,
    "rt nagar": 0.68, "koramangala": 0.70, "kr puram": 0.72,
    "indiranagar": 0.65, "marathahalli": 0.60, "shivajinagar": 0.62,
    "rajajinagar": 0.58, "nagawara": 0.58, "banaswadi": 0.55,
    "horamavu": 0.52, "lingarajapuram": 0.55, "malleswaram": 0.50,
    "peenya": 0.52, "yeshwanthpur": 0.50, "kammanahalli": 0.50,
    "btm layout": 0.55, "hsr layout": 0.42, "bellandur": 0.40,
    "mahadevapura": 0.42, "hebbal": 0.45, "byatarayanapura": 0.48,
    "jalahalli": 0.45, "dasarahalli": 0.48,
    "whitefield": 0.35, "jayanagar": 0.28, "jp nagar": 0.30,
    "electronic city": 0.32, "banashankari": 0.30, "basavanagudi": 0.28,
    "yelahanka": 0.35, "devanahalli": 0.25, "kengeri": 0.38,
}

FLOOD_BASELINES: Dict[str, float] = {
    "bellandur": 0.80, "varthur": 0.75, "koramangala": 0.65,
    "hebbal": 0.60, "nagawara": 0.55, "hrbr layout": 0.50,
    "horamavu": 0.55, "battarahalli": 0.50, "doddanekkundi": 0.45,
    "bommanahalli": 0.45, "hongasandra": 0.42, "kalkere": 0.50,
    "whitefield": 0.35, "marathahalli": 0.40,
    "electronic city": 0.30, "devanahalli": 0.18, "yelahanka": 0.22,
}

EVENT_BASELINES: Dict[str, float] = {
    "mg road": 0.45, "brigade road": 0.45, "koramangala": 0.42,
    "indiranagar": 0.45, "majestic": 0.40, "shivajinagar": 0.38,
    "whitefield": 0.30, "marathahalli": 0.30,
    "hsr layout": 0.28, "jayanagar": 0.20,
    "yelahanka": 0.12, "devanahalli": 0.10,
}

def _crime_baseline(zone_name: str) -> float:
    z = zone_name.lower()
    for k, v in CRIME_BASELINES.items():
        if k in z:
            return v
    return 0.45

def _flood_baseline(zone_name: str) -> float:
    z = zone_name.lower()
    for k, v in FLOOD_BASELINES.items():
        if k in z:
            return v
    return 0.15

def _event_baseline(zone_name: str) -> float:
    z = zone_name.lower()
    for k, v in EVENT_BASELINES.items():
        if k in z:
            return v
    return 0.12

# ══════════════════════════════════════════════════════════════════════════════
# 9.  TIME-RISK ENCODER
# ══════════════════════════════════════════════════════════════════════════════

def _time_risk(hour: int, nightlife_density: float) -> float:
    if 8 <= hour < 10:         base = 0.70
    elif 17 <= hour < 20:      base = 0.80
    elif 22 <= hour or hour < 5: base = 0.65
    elif 12 <= hour < 17:      base = 0.40
    else:                      base = 0.50
    return float(np.clip(base + nightlife_density * 0.10, 0.0, 1.0))

def _direction_label(zone_key: str) -> str:
    MAP = {
        "north": "north", "northeast": "north", "northwest": "north",
        "east": "east",   "southeast": "east",
        "south": "south", "southwest": "south",
        "west": "west",   "central": "central",
        "it_belt": "east", "airport": "north",
        "peripheral": "peripheral", "industrial": "west",
    }
    return MAP.get(zone_key, zone_key)

# ══════════════════════════════════════════════════════════════════════════════
# 10.  CORE ZONE EXTRACTOR
# ══════════════════════════════════════════════════════════════════════════════

def extract_zone(
    zone_key: str,
    areas: List[str],
    hour: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Extract all road segments for a zone and compute all 34 schema columns.
    Returns a DataFrame; empty DataFrame if no edges could be fetched.
    """
    log.info("━" * 60)
    log.info("ZONE: %s  |  %d locality groups  |  hour=%02d",
             zone_key.upper(), len(areas), hour)
    log.info("━" * 60)

    direction = _direction_label(zone_key)

    # ── osmnx settings ────────────────────────────────────────────────────────
    ox.settings.log_console = False
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(Path.home() / ".cache" / "osmnx_saferoute")
    useful_tags = list(set(
        ox.settings.useful_tags_way + ["lit", "width", "lanes", "maxspeed", "junction"]
    ))
    ox.settings.useful_tags_way = useful_tags
    ox.settings.useful_tags_node = list(set(
        ox.settings.useful_tags_node + ["highway", "junction", "crossing"]
    ))

    all_edges: List[pd.DataFrame] = []
    all_node_data: Dict[int, dict] = {}

    _overpass_idx = 0  # rotating index for graph fetches

    for area_name in areas:
        log.info("  Fetching road network: %s", area_name)

        # FIX 2: rotate Overpass endpoint before every graph fetch
        ox.settings.overpass_url = OVERPASS_ENDPOINTS[_overpass_idx % len(OVERPASS_ENDPOINTS)]
        _overpass_idx += 1

        G = None
        _POLYGON_TRIGGERS = ("did not geocode", "Polygon", "MultiPolygon", "graph nodes")

        # --- attempt 1: graph_from_place ---
        try:
            G = ox.graph_from_place(
                area_name,
                network_type="drive",
                retain_all=False,
                simplify=True,
            )
        except Exception as exc:
            exc_str = str(exc)
            needs_retry = any(t in exc_str for t in _POLYGON_TRIGGERS)
            if needs_retry:
                log.warning("  ⚠ graph_from_place polygon failure for '%s': %s — trying graph_from_address", area_name, exc)
                # FIX 2: rotate endpoint on timeout/polygon retry
                ox.settings.overpass_url = OVERPASS_ENDPOINTS[_overpass_idx % len(OVERPASS_ENDPOINTS)]
                _overpass_idx += 1
                # --- attempt 2: graph_from_address with full name ---
                try:
                    G = ox.graph_from_address(area_name, dist=1500, network_type="drive", simplify=True)
                except Exception as exc2:
                    log.warning("  ⚠ graph_from_address failed for '%s': %s — trying locality fallback", area_name, exc2)
                    locality = area_name.split(",")[0].strip()
                    fallback_name = f"{locality}, Bengaluru, Karnataka, India"
                    ox.settings.overpass_url = OVERPASS_ENDPOINTS[_overpass_idx % len(OVERPASS_ENDPOINTS)]
                    _overpass_idx += 1
                    # --- attempt 3: locality fallback ---
                    try:
                        G = ox.graph_from_address(fallback_name, dist=1500, network_type="drive", simplify=True)
                    except Exception as exc3:
                        log.warning("  ⚠ All retries failed for '%s': %s — skipping", area_name, exc3)
                        time.sleep(_OVERPASS_DELAY)
                        continue
            else:
                log.warning("  ⚠ Could not fetch '%s': %s — skipping", area_name, exc)
                time.sleep(_OVERPASS_DELAY)
                continue

        if G is None:
            log.warning("  ⚠ Graph is None for '%s' — skipping", area_name)
            time.sleep(_OVERPASS_DELAY)
            continue

        nodes_gdf, edges_gdf = ox.graph_to_gdfs(G, nodes=True, edges=True)
        edges_gdf = edges_gdf.reset_index()

        # ── FIX 3: strip NaN values when storing node tags ────────────────────
        # In v6.0, row.to_dict() preserved NaN float values for empty tag
        # columns.  Later, _junction_type() received these NaNs and the
        # `"crossing" in node_tags` membership check failed with
        # "argument of type float is not iterable".
        for nid, row in nodes_gdf.iterrows():
            all_node_data[nid] = {
                k: v for k, v in row.to_dict().items()
                if v is not None
                and not (isinstance(v, float) and math.isnan(v))
                and v != ""
            }

        edges_gdf["_locality"] = area_name.split(",")[0].strip()
        edges_gdf["_area_name"] = area_name
        all_edges.append(edges_gdf)
        log.info("    → %d edges", len(edges_gdf))
        time.sleep(_OVERPASS_DELAY)

    if not all_edges:
        log.error("No edges fetched for zone %s — returning empty DataFrame", zone_key)
        return pd.DataFrame()

    edges = pd.concat(all_edges, ignore_index=True)
    log.info("  Total edges before dedup: %d", len(edges))

    # ── Deduplicate on osmid ──────────────────────────────────────────────────
    if "osmid" in edges.columns:
        edges = edges.drop_duplicates(subset="osmid")
    log.info("  Edges after dedup: %d", len(edges))

    # ── Midpoints ─────────────────────────────────────────────────────────────
    def _midpoint(geom):
        if geom is None:
            return (0.0, 0.0)
        pt = geom.interpolate(0.5, normalized=True)
        return (pt.y, pt.x)

    midpoints = edges["geometry"].apply(_midpoint)
    edges["lat"] = midpoints.apply(lambda x: x[0]).astype(np.float32)
    edges["lng"] = midpoints.apply(lambda x: x[1]).astype(np.float32)

    # ── Bengaluru bbox filter ─────────────────────────────────────────────────
    mask = (
        (edges["lat"] >= 12.70) & (edges["lat"] <= 13.35) &
        (edges["lng"] >= 77.35) & (edges["lng"] <= 77.85)
    )
    edges = edges[mask].copy()
    log.info("  Edges within Bengaluru bbox: %d", len(edges))

    if len(edges) == 0:
        return pd.DataFrame()

    lats = edges["lat"].values.astype(np.float64)
    lngs = edges["lng"].values.astype(np.float64)
    n = len(edges)

    # ── Highway tag (uses patched _get_hw) ───────────────────────────────────
    edges["_hw"] = edges["highway"].apply(_get_hw)
    edges = edges[edges["_hw"].isin(HIGHWAY_TYPES_WANTED)].copy()
    n = len(edges)
    if n == 0:
        return pd.DataFrame()

    lats    = edges["lat"].values.astype(np.float64)
    lngs    = edges["lng"].values.astype(np.float64)
    hw_arr  = edges["_hw"].values

    # ── Categorical columns ───────────────────────────────────────────────────
    road_type      = np.array([ROAD_TYPE_MAP.get(h, "unclassified") for h in hw_arr])
    highway_type   = hw_arr.copy()
    zone_col       = edges["_locality"].values
    direction_col  = np.full(n, direction, dtype=object)
    source_area    = zone_col.copy()
    destination_area = zone_col.copy()
    road_name = edges["name"].fillna("Unnamed Road").apply(
        lambda v: v[0] if isinstance(v, list) else str(v)
    ).values

    # ── Speed, lanes, width ───────────────────────────────────────────────────
    raw_speed = edges["maxspeed"].apply(_parse_speed) if "maxspeed" in edges.columns else pd.Series([0.0] * n)
    raw_lanes = edges["lanes"].apply(_parse_lanes)   if "lanes"    in edges.columns else pd.Series([2]   * n)
    raw_width = edges["width"].apply(_parse_width)   if "width"    in edges.columns else pd.Series([None] * n)

    speed_limit = np.array([
        sp if sp >= 10 else SPEED_DEFAULTS.get(hw_arr[i], 40.0)
        for i, sp in enumerate(raw_speed.values)
    ], dtype=np.float32)

    road_width_estimate = np.array([
        _width_estimate(raw_width.iloc[i], int(raw_lanes.iloc[i]))
        for i in range(n)
    ], dtype=object)

    # ── Junction type (uses patched _junction_type) ───────────────────────────
    junction_type_arr = []
    for _, row in edges.iterrows():
        v_node = row.get("v", None)
        if v_node is None:
            tags = {}
        elif isinstance(v_node, float) and math.isnan(v_node):
            tags = {}
        else:
            tags = all_node_data.get(int(v_node), {})
        junction_type_arr.append(_junction_type(tags))
    junction_type_arr = np.array(junction_type_arr, dtype=object)

    # ── Adjacency count ───────────────────────────────────────────────────────
    v_nodes = edges["v"].values if "v" in edges.columns else np.zeros(n, dtype=int)
    node_degree = pd.Series(v_nodes).value_counts().to_dict()
    adjacency_count = np.clip(
        np.array([node_degree.get(v, 1) for v in v_nodes], dtype=np.int16),
        0, 30,
    )

    # ── Overpass POI fetches ──────────────────────────────────────────────────
    bbox = (lats.min() - 0.01, lngs.min() - 0.01,
            lats.max() + 0.01, lngs.max() + 0.01)

    log.info("  Fetching traffic signals …")
    signals = fetch_pois_in_bbox(bbox, 'highway="traffic_signals"')
    time.sleep(_OVERPASS_DELAY)

    log.info("  Fetching commercial POIs …")
    commercial = fetch_pois_in_bbox(bbox, '"shop"~"."')
    commercial += fetch_pois_in_bbox(
        bbox, '"amenity"~"restaurant|cafe|fast_food|bank|supermarket|marketplace|fuel|atm"'
    )
    time.sleep(_OVERPASS_DELAY)

    log.info("  Fetching nightlife POIs …")
    nightlife = fetch_pois_in_bbox(bbox, '"amenity"~"bar|pub|nightclub"')
    time.sleep(_OVERPASS_DELAY)

    log.info("  Fetching hospital POIs …")
    hospitals = fetch_pois_in_bbox(bbox, '"amenity"~"hospital|clinic|doctors|pharmacy"')
    time.sleep(_OVERPASS_DELAY)

    log.info("  Fetching police stations …")
    police = fetch_pois_in_bbox(bbox, '"amenity"="police"')
    time.sleep(_OVERPASS_DELAY)

    log.info("  Fetching all POIs …")
    all_pois  = fetch_pois_in_bbox(bbox, '"amenity"~"."')
    all_pois += fetch_pois_in_bbox(bbox, '"shop"~"."')
    time.sleep(_OVERPASS_DELAY)

    log.info(
        "  Fetched: signals=%d  commercial=%d  nightlife=%d  "
        "hospitals=%d  police=%d  all_pois=%d",
        len(signals), len(commercial), len(nightlife),
        len(hospitals), len(police), len(all_pois),
    )

    # ── Spatial density calculations ──────────────────────────────────────────
    sig_eng  = DensityEngine(signals)
    com_eng  = DensityEngine(commercial)
    nl_eng   = DensityEngine(nightlife)
    hosp_eng = DensityEngine(hospitals)
    pol_eng  = DensityEngine(police)
    poi_eng  = DensityEngine(list(set(all_pois)))

    sig_cnt  = sig_eng.count_within(lats, lngs, 500.0)
    com_cnt  = com_eng.count_within(lats, lngs, 400.0)
    nl_cnt   = nl_eng.count_within(lats, lngs, 350.0)
    hosp_cnt = hosp_eng.count_within(lats, lngs, 1200.0)
    poi_cnt  = poi_eng.count_within(lats, lngs, 400.0)
    inter_cnt = sig_cnt * 0.4 + adjacency_count.astype(float) * 0.8

    traffic_signal_density = _clip01(_normalize(sig_cnt))
    commercial_density     = _clip01(_normalize(com_cnt))
    nightlife_density      = _clip01(_normalize(nl_cnt))
    hospital_density       = _clip01(_normalize(hosp_cnt))
    intersection_density   = _clip01(_normalize(inter_cnt))
    poi_density            = _clip01(_normalize(poi_cnt))

    pol_dist_m = pol_eng.nearest_dist_m(lats, lngs)
    police_station_distance = _clip01(1.0 - np.exp(-pol_dist_m / 1200.0))

    # ── CCTV proxy ────────────────────────────────────────────────────────────
    is_major = np.array([1.0 if rt in ("highway", "primary") else 0.0 for rt in road_type])
    cctv_density_estimate = _clip01(
        0.55 * traffic_signal_density
        + 0.30 * commercial_density
        + 0.15 * is_major
    )

    # ── Lighting ──────────────────────────────────────────────────────────────
    lit_raw = (
        edges["lit"].fillna("").apply(lambda v: v[0] if isinstance(v, list) else str(v)).values
        if "lit" in edges.columns else np.full(n, "")
    )
    osm_lit    = np.array([LIT_MAP.get(str(v).lower(), -1.0) for v in lit_raw])
    road_light = np.array([ROAD_TYPE_LIGHT.get(h, 0.32) for h in hw_arr])
    urban_proxy = _clip01(0.6 * traffic_signal_density + 0.4 * commercial_density)
    lighting_score = _clip01(np.where(
        osm_lit >= 0,
        0.50 * osm_lit + 0.30 * urban_proxy + 0.20 * road_light,
        0.50 * road_light + 0.30 * urban_proxy + 0.20 * road_light,
    ))

    # ── Crime ─────────────────────────────────────────────────────────────────
    crime_base  = np.array([_crime_baseline(z) for z in zone_col], dtype=float)
    crime_score = _clip01(crime_base + rng.normal(0.0, 0.04, size=n))

    # ── Activity ──────────────────────────────────────────────────────────────
    activity_score = _clip01(
        0.45 * commercial_density + 0.30 * poi_density
        + 0.15 * traffic_signal_density + 0.10 * nightlife_density
    )

    # ── Event frequency ───────────────────────────────────────────────────────
    ev_base = np.array([_event_baseline(z) for z in zone_col], dtype=float)
    event_frequency = _clip01(ev_base + rng.normal(0.0, 0.03, size=n))

    # ── Infrastructure ────────────────────────────────────────────────────────
    rt_quality = np.array([ROAD_TYPE_QUALITY.get(h, 0.38) for h in hw_arr])
    infrastructure_score = _clip01(
        0.40 * (1.0 - _clip01(intersection_density))
        + 0.30 * rt_quality
        + 0.30 * (1.0 - crime_score)
    )

    # ── Connectivity ──────────────────────────────────────────────────────────
    adj_norm = _clip01(adjacency_count.astype(float) / 10.0)
    rt_conn  = np.array([ROAD_TYPE_CONN.get(h, 0.42) for h in hw_arr])
    connectivity_score = _clip01(
        0.40 * adj_norm + 0.35 * rt_conn + 0.25 * intersection_density
    )

    # ── Isolation ─────────────────────────────────────────────────────────────
    isolated_area_score = _clip01(
        1.0 - connectivity_score + rng.normal(0.0, 0.03, size=n)
    )

    # ── Road risk ─────────────────────────────────────────────────────────────
    rt_risk = np.array([ROAD_TYPE_RISK.get(h, 0.38) for h in hw_arr])
    road_risk_score = _clip01(
        0.30 * crime_score
        + 0.20 * (1.0 - lighting_score)
        + 0.15 * (1.0 - cctv_density_estimate)
        + 0.15 * isolated_area_score
        + 0.20 * rt_risk
    )

    # ── Flood & weather ───────────────────────────────────────────────────────
    flood_base = np.array([_flood_baseline(z) for z in zone_col], dtype=float)
    flood_risk = _clip01(flood_base + rng.normal(0.0, 0.05, size=n))

    rw_m = np.array([
        float(str(w).replace("m", "")) if w else 10.0
        for w in road_width_estimate
    ], dtype=float)
    rw_norm = _clip01((rw_m - 4.0) / 26.0)
    weather_exposure_score = _clip01(
        0.40 * flood_risk + 0.35 * (1.0 - commercial_density) + 0.25 * rw_norm
    )

    # ── Congestion ────────────────────────────────────────────────────────────
    congestion_score = _clip01(
        0.30 * traffic_signal_density + 0.25 * intersection_density
        + 0.25 * commercial_density + 0.20 * (1.0 - rw_norm)
    )

    # ── Travel time ───────────────────────────────────────────────────────────
    edge_len_m  = edges["length"].values.astype(float) if "length" in edges.columns else np.full(n, 100.0)
    free_flow   = np.clip((edge_len_m / 1000.0 / np.maximum(speed_limit, 10.0)) * 60.0, 0.05, 60.0)
    travel_time_estimate = np.clip(
        free_flow * (1.0 + congestion_score * 0.80), 0.1, 60.0
    ).astype(np.float32)

    # ── Time risk ─────────────────────────────────────────────────────────────
    time_risk_arr = np.array(
        [_time_risk(hour, float(nightlife_density[i])) for i in range(n)],
        dtype=np.float32,
    )

    # ── Assemble DataFrame ────────────────────────────────────────────────────
    df = pd.DataFrame({
        "zone":                    zone_col,
        "direction":               direction_col,
        "lat":                     edges["lat"].values.astype(np.float32),
        "lng":                     edges["lng"].values.astype(np.float32),
        "source_area":             source_area,
        "destination_area":        destination_area,
        "road_name":               road_name,
        "road_type":               road_type,
        "highway_type":            highway_type,
        "junction_type":           junction_type_arr,
        "road_width_estimate":     road_width_estimate,
        "speed_limit":             speed_limit,
        "traffic_signal_density":  traffic_signal_density.astype(np.float32),
        "intersection_density":    intersection_density.astype(np.float32),
        "commercial_density":      commercial_density.astype(np.float32),
        "nightlife_density":       nightlife_density.astype(np.float32),
        "hospital_density":        hospital_density.astype(np.float32),
        "police_station_distance": police_station_distance.astype(np.float32),
        "cctv_density_estimate":   cctv_density_estimate.astype(np.float32),
        "lighting_score":          lighting_score.astype(np.float32),
        "crime_score":             crime_score.astype(np.float32),
        "activity_score":          activity_score.astype(np.float32),
        "event_frequency":         event_frequency.astype(np.float32),
        "infrastructure_score":    infrastructure_score.astype(np.float32),
        "connectivity_score":      connectivity_score.astype(np.float32),
        "isolated_area_score":     isolated_area_score.astype(np.float32),
        "road_risk_score":         road_risk_score.astype(np.float32),
        "travel_time_estimate":    travel_time_estimate,
        "congestion_score":        congestion_score.astype(np.float32),
        "flood_risk":              flood_risk.astype(np.float32),
        "weather_exposure_score":  weather_exposure_score.astype(np.float32),
        "poi_density":             poi_density.astype(np.float32),
        "time_risk":               time_risk_arr,
        "adjacency_count":         adjacency_count,
    })

    df = df.dropna(subset=["lat", "lng"]).reset_index(drop=True)
    log.info("  ✔ Zone %s: %d road segments extracted", zone_key.upper(), len(df))
    return df

# ══════════════════════════════════════════════════════════════════════════════
# 11.  QUALITY ASSURANCE
# ══════════════════════════════════════════════════════════════════════════════

SCHEMA_COLS = [
    "zone", "direction", "lat", "lng", "source_area", "destination_area",
    "road_name", "road_type", "highway_type", "junction_type",
    "road_width_estimate", "speed_limit",
    "traffic_signal_density", "intersection_density",
    "commercial_density", "nightlife_density",
    "hospital_density", "police_station_distance",
    "cctv_density_estimate", "lighting_score",
    "crime_score", "activity_score", "event_frequency",
    "infrastructure_score", "connectivity_score",
    "isolated_area_score", "road_risk_score",
    "travel_time_estimate", "congestion_score",
    "flood_risk", "weather_exposure_score",
    "poi_density", "time_risk", "adjacency_count",
]

def validate_csv(df: pd.DataFrame, zone_key: str) -> List[str]:
    warns: List[str] = []
    n = len(df)
    min_rows = 500 if zone_key in ("airport", "industrial") else 2000
    if n < min_rows:
        warns.append(f"⚠ Row count {n} < minimum {min_rows}")
    for col in ["zone", "direction", "lat", "lng", "road_type", "highway_type", "speed_limit"]:
        if col in df.columns and df[col].isna().any():
            warns.append(f"⚠ NaN in mandatory column: {col}")
    if df["lat"].min() < 12.70 or df["lat"].max() > 13.35:
        warns.append("⚠ lat out of Bengaluru bbox")
    if df["lng"].min() < 77.35 or df["lng"].max() > 77.85:
        warns.append("⚠ lng out of Bengaluru bbox")
    score_cols = [c for c in df.columns if any(
        c.endswith(s) for s in ("_density", "_score", "_risk", "_frequency", "time_risk")
    ) and c not in ("speed_limit", "travel_time_estimate", "adjacency_count", "road_width_estimate")]
    for col in score_cols:
        if col in df.columns and (df[col].min() < -0.001 or df[col].max() > 1.001):
            warns.append(f"⚠ {col} out of [0,1]: min={df[col].min():.3f} max={df[col].max():.3f}")
    return warns


def fill_missing(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include=[np.floating]).columns:
        if df[col].isna().any():
            med = df[col].median()
            df[col] = df[col].fillna(med if not np.isnan(med) else 0.5)
    str_defaults = {
        "road_type": "secondary", "highway_type": "secondary",
        "junction_type": "none",  "road_name": "Unnamed Road",
    }
    for col in ["zone", "direction", "source_area", "destination_area",
                "road_name", "road_type", "highway_type", "junction_type"]:
        if col in df.columns and df[col].isna().any():
            df[col] = df[col].fillna(str_defaults.get(col, "unknown"))
    if "road_width_estimate" in df.columns:
        df["road_width_estimate"] = df["road_width_estimate"].fillna("10m")
    if "adjacency_count" in df.columns:
        df["adjacency_count"] = df["adjacency_count"].fillna(4).astype(np.int16)
    if "speed_limit" in df.columns:
        df["speed_limit"] = df["speed_limit"].fillna(40.0).astype(np.float32)
    return df

# ══════════════════════════════════════════════════════════════════════════════
# 12.  ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

def run(
    zones_to_run: Optional[List[str]] = None,
    hour: int = 9,
    resume: bool = False,
    validate_only: bool = False,
    output_dir: Optional[Path] = None,
    seed: int = 42,
) -> None:
    out = output_dir or OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    log.info("Output directory: %s", out)

    zone_areas   = get_zone_areas()
    all_keys     = list(zone_areas.keys())
    keys_to_run  = zones_to_run if zones_to_run else all_keys

    for k in keys_to_run:
        if k not in zone_areas:
            log.error("Unknown zone '%s'. Valid: %s", k, all_keys)
            sys.exit(1)

    if validate_only:
        for zone_key in keys_to_run:
            csv_path = out / ZONE_FILE_MAP.get(zone_key, f"{zone_key}_bangalore_risk.csv")
            if not csv_path.exists():
                print(f"  ✗ {csv_path.name} — NOT FOUND")
                continue
            df   = pd.read_csv(csv_path, low_memory=False)
            warns = validate_csv(df, zone_key)
            status = "✔ PASS" if not warns else f"⚠ {len(warns)} warnings"
            print(f"  {status:15s} {csv_path.name:50s} ({len(df):,} rows)")
            for w in warns:
                print(f"             {w}")
        return

    rng = np.random.default_rng(seed)
    total_rows = 0

    print("\n" + "━" * 70)
    print("  SafeRoute-AI Extractor v6.1")
    print(f"  Zones : {keys_to_run}")
    print(f"  Hour  : {hour:02d}:00")
    print(f"  Output: {out}")
    print("━" * 70 + "\n")

    for zone_key in keys_to_run:
        csv_name = ZONE_FILE_MAP.get(zone_key, f"{zone_key}_bangalore_risk.csv")
        csv_path = out / csv_name

        if resume and csv_path.exists():
            log.info("  ⏭  Skipping %s (--resume)", csv_name)
            continue

        log.info("\n  Processing zone: %s  (%d areas)", zone_key, len(zone_areas[zone_key]))

        try:
            df = extract_zone(zone_key, zone_areas[zone_key], hour, rng)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            log.error("  ✗ Zone %s failed: %s", zone_key, exc)
            continue

        if df.empty:
            log.warning("  ⚠ Zone %s returned empty DataFrame", zone_key)
            continue

        df = fill_missing(df)

        warns = validate_csv(df, zone_key)
        if warns:
            for w in warns:
                log.warning("  %s", w)
        else:
            log.info("  ✔ All QA checks passed for zone %s", zone_key)

        # Enforce column order; add any missing columns with safe defaults
        for col in SCHEMA_COLS:
            if col not in df.columns:
                df[col] = (
                    0.5 if col not in (
                        "zone", "direction", "road_name", "road_type",
                        "highway_type", "junction_type", "road_width_estimate",
                        "source_area", "destination_area",
                    )
                    else "unknown"
                )
        df = df[SCHEMA_COLS]

        df.to_csv(csv_path, index=False, encoding="utf-8")
        total_rows += len(df)
        log.info("  💾 Saved: %s  (%d rows)", csv_path, len(df))

    print("\n" + "━" * 70)
    print(f"  ✅  Done!  {total_rows:,} total road segments written to {out}")
    print("━" * 70 + "\n")

# ══════════════════════════════════════════════════════════════════════════════
# 13.  CLI
# ══════════════════════════════════════════════════════════════════════════════

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SafeRoute-AI Extractor v6.1 — OSM Data Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python extractor.py                            # all zones, 09:00
  python extractor.py --hour 22                  # night-time
  python extractor.py --zones north central      # specific zones
  python extractor.py --resume                   # skip done zones
  python extractor.py --validate-only            # QA only
  python extractor.py --output-dir /tmp/data     # custom output path

Valid zone keys:
  north  northeast  east  southeast  central  south  southwest
  west   northwest  it_belt  airport  peripheral  industrial
""",
    )
    p.add_argument("--zones",       nargs="+", metavar="ZONE")
    p.add_argument("--hour",        type=int, default=9, choices=range(24), metavar="H")
    p.add_argument("--resume",      action="store_true")
    p.add_argument("--validate-only", dest="validate_only", action="store_true")
    p.add_argument("--output-dir",  dest="output_dir", default=None)
    p.add_argument("--seed",        type=int, default=42)
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(
        zones_to_run  = args.zones,
        hour          = args.hour,
        resume        = args.resume,
        validate_only = args.validate_only,
        output_dir    = Path(args.output_dir) if args.output_dir else None,
        seed          = args.seed,
    )
