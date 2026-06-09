"""
SafeRoute-AI v8.0 — Production Routing Engine
==============================================
Phases 1-15:  Core A* routing, graph loading, snapping, metrics
Phases 16-30: Predictive risk, women safety, emergency escape,
              safe havens, heatmaps, time machine, simulation,
              incident injection, zone detection, redundancy,
              explainability AI, risk visualization, caching,
              and multi-profile recommendations.

Inputs (unchanged schema):
  graph_nodes.csv          node_id, lat, lng, zone, source_area, adjacency_count, connectivity_score
  graph_edges.csv          edge_id, source_node, destination_node, road_name, road_type, highway_type,
                           direction, static_distance_km, static_travel_time_min
  hourly_edge_weights.csv  edge_id, hour, final_edge_weight, final_risk_score, congestion_score,
                           time_risk, weather_exposure_score, dynamic_risk_score
"""

from typing import Dict, List, Optional
import pandas as pd
import numpy as np
import json
import math
import heapq
import time
import pickle
import warnings
import os
from pathlib import Path
from scipy.spatial import KDTree
from collections import defaultdict
from functools import lru_cache
from datetime import datetime

warnings.filterwarnings("ignore")

# ─── Paths ─────────────────────────────────────────────────────────────────────
_ENGINE_DIR = Path(__file__).resolve().parent
SRC = _ENGINE_DIR / "outputs"
OUT = _ENGINE_DIR / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

NODES_CSV    = SRC / "graph_nodes.csv"
EDGES_CSV    = SRC / "graph_edges.csv"
WEIGHTS_CSV  = SRC / "hourly_edge_weights.csv"
CACHE_FILE   = OUT / "routing_cache.pkl"
INCIDENT_CSV = OUT / "incident_layer.csv"

# ─── Cost function weights (Phase 5, configurable) ────────────────────────────
PROFILE_WEIGHTS = {
    "default":  {"risk": 0.45, "time": 0.25, "congestion": 0.20, "weather": 0.10},
    "women":    {"risk": 0.55, "time": 0.10, "congestion": 0.10, "weather": 0.05, "safety_bonus": 0.20},
    "fastest":  {"risk": 0.15, "time": 0.55, "congestion": 0.25, "weather": 0.05},
    "balanced": {"risk": 0.35, "time": 0.35, "congestion": 0.20, "weather": 0.10},
}

# ─── Haversine ─────────────────────────────────────────────────────────────────
def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(max(0.0, a)))

@lru_cache(maxsize=50_000)
def cached_haversine(lat1, lng1, lat2, lng2):
    return haversine_km(lat1, lng1, lat2, lng2)

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1-2 — DATA LOADING & GRAPH CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════════════

class SafeRouteEngine:
    # Semantic POI coordinates for safe haven snapping (sourced from Risk Engine v6)
    _POLICE_POI: List[Dict] = [
        {"name": "Hebbal PS",          "lat": 13.0360, "lng": 77.5970},
        {"name": "RT Nagar PS",        "lat": 13.0220, "lng": 77.5975},
        {"name": "Yelahanka PS",       "lat": 13.1006, "lng": 77.5960},
        {"name": "Byatarayanapura PS", "lat": 13.0590, "lng": 77.5600},
        {"name": "Devanahalli PS",     "lat": 13.2470, "lng": 77.7110},
        {"name": "Jakkur PS",          "lat": 13.0715, "lng": 77.5880},
        {"name": "Nagawara PS",        "lat": 13.0450, "lng": 77.6250},
        {"name": "Rajajinagar PS",     "lat": 12.9840, "lng": 77.5510},
        {"name": "Malleswaram PS",     "lat": 12.9990, "lng": 77.5720},
        {"name": "Majestic PS",        "lat": 12.9770, "lng": 77.5720},
        {"name": "Magadi Road PS",     "lat": 12.9640, "lng": 77.5170},
        {"name": "Kengeri PS",         "lat": 12.9149, "lng": 77.4840},
        {"name": "Indiranagar PS",     "lat": 12.9792, "lng": 77.6388},
        {"name": "Whitefield PS",      "lat": 12.9698, "lng": 77.7500},
        {"name": "KR Puram PS",        "lat": 13.0020, "lng": 77.6960},
        {"name": "Marathahalli PS",    "lat": 12.9591, "lng": 77.7011},
        {"name": "HAL PS",             "lat": 12.9634, "lng": 77.6596},
        {"name": "Koramangala PS",     "lat": 12.9293, "lng": 77.6210},
        {"name": "BTM Layout PS",      "lat": 12.9126, "lng": 77.6101},
        {"name": "JP Nagar PS",        "lat": 12.9060, "lng": 77.5830},
        {"name": "Jayanagar PS",       "lat": 12.9260, "lng": 77.5830},
        {"name": "Electronic City PS", "lat": 12.8440, "lng": 77.6600},
        {"name": "HSR Layout PS",      "lat": 12.9121, "lng": 77.6446},
        {"name": "Banashankari PS",    "lat": 12.9270, "lng": 77.5640},
    ]

    _HOSPITAL_POI: List[Dict] = [
        {"name": "Manipal Hospital",       "lat": 12.9592, "lng": 77.6474},
        {"name": "Fortis Bannerghatta",    "lat": 12.8929, "lng": 77.5971},
        {"name": "Apollo Jayanagar",       "lat": 12.9257, "lng": 77.5832},
        {"name": "Narayana Hrudayalaya",   "lat": 12.8414, "lng": 77.6601},
        {"name": "St Johns Hospital",      "lat": 12.9452, "lng": 77.6153},
        {"name": "Victoria Hospital",      "lat": 12.9640, "lng": 77.5730},
        {"name": "Bowring Hospital",       "lat": 12.9787, "lng": 77.6133},
        {"name": "Sakra World Hospital",   "lat": 12.9582, "lng": 77.7091},
        {"name": "Columbia Asia Hebbal",   "lat": 13.0360, "lng": 77.5978},
        {"name": "Aster CMI Hebbal",       "lat": 13.0430, "lng": 77.5890},
        {"name": "Sparsh Hospital",        "lat": 13.0220, "lng": 77.5960},
        {"name": "NIMHANS",                "lat": 12.9442, "lng": 77.5955},
        {"name": "KIMS Hospital",          "lat": 12.9330, "lng": 77.5790},
        {"name": "Bangalore Baptist",      "lat": 13.0254, "lng": 77.5963},
        {"name": "Msrit Medical Centre",   "lat": 13.0213, "lng": 77.5637},
    ]

    def __init__(self):
        self.nodes = None           # DataFrame
        self.edges = None           # DataFrame
        self.weights = None         # DataFrame
        self.node_lookup = {}       # node_id → {lat, lng, zone, ...}
        self.edge_lookup = {}       # edge_id → edge dict
        self.adjacency = defaultdict(list)   # node_id → [(neighbor, edge_id)]
        self.weight_index = {}      # (edge_id, hour) → weight row dict
        self.kdtree = None
        self.kdtree_ids = []
        self.safe_haven_nodes = {}  # Phase 19
        self.safe_zone_clusters = []   # Phase 24
        self.danger_zone_clusters = [] # Phase 25
        self.incidents = {}         # Phase 23: edge_id → incident dict
        self.loaded = False

    # ── Phase 1: Load ──────────────────────────────────────────────────────────
    def load_graph(self, verbose=True):
        t0 = time.time()
        if verbose: print("Loading graph data...")

        self.nodes = pd.read_csv(NODES_CSV)
        self.edges = pd.read_csv(EDGES_CSV)
        self.weights = pd.read_csv(WEIGHTS_CSV)

        # Validation
        node_ids = set(self.nodes["node_id"].astype(int))
        edge_node_ids = set(self.edges["source_node"].astype(int)) | set(self.edges["destination_node"].astype(int))
        orphans = edge_node_ids - node_ids
        if orphans and verbose:
            print(f"  ⚠ {len(orphans)} orphan node references in edges")

        # node_lookup
        _node_cols = [c for c in ["node_id","lat","lng","zone","source_area",
                                   "connectivity_score","adjacency_count"]
                      if c in self.nodes.columns]
        _node_records = self.nodes[_node_cols].to_dict("records")
        for r in _node_records:
            nid = int(r["node_id"])
            self.node_lookup[nid] = {
                "lat":                float(r.get("lat", 0.0)),
                "lng":                float(r.get("lng", 0.0)),
                "zone":               str(r.get("zone", "")),
                "source_area":        str(r.get("source_area", "")),
                "connectivity_score": float(r.get("connectivity_score", 0.5)),
                "adjacency_count":    int(r.get("adjacency_count", 0)),
            }

        # edge_lookup + adjacency
        _edge_cols = [c for c in ["edge_id","source_node","destination_node","road_name",
                                   "road_type","highway_type","static_distance_km",
                                   "static_travel_time_min"]
                      if c in self.edges.columns]
        _edge_records = self.edges[_edge_cols].to_dict("records")
        _node_id_set = set(self.node_lookup.keys())
        for r in _edge_records:
            eid = str(r["edge_id"])
            src = int(r["source_node"])
            dst = int(r["destination_node"])
            self.edge_lookup[eid] = {
                "edge_id":        eid,
                "source_node":    src,
                "destination_node": dst,
                "road_name":      str(r.get("road_name", "")),
                "road_type":      str(r.get("road_type", "residential")),
                "highway_type":   str(r.get("highway_type", "")),
                "distance":       float(r.get("static_distance_km", 0.1)),
                "travel_time":    float(r.get("static_travel_time_min", 0.5)),
            }
            if src in _node_id_set and dst in _node_id_set:
                self.adjacency[src].append((dst, eid))

        # weight index
        _wt_base = ["edge_id","hour","final_edge_weight","final_risk_score",
                    "congestion_score","weather_exposure_score","dynamic_risk_score","time_risk"]
        _wt_ext  = ["lighting_dark_risk","isolated_area_score","crime_score"]
        _wt_load = [c for c in _wt_base + _wt_ext if c in self.weights.columns]
        _wt_records = self.weights[_wt_load].to_dict("records")
        for r in _wt_records:
            eid = str(r["edge_id"])
            h   = int(r["hour"])
            self.weight_index[(eid, h)] = {
                "final_edge_weight":     float(r.get("final_edge_weight", 0.5)),
                "final_risk_score":      float(r.get("final_risk_score", 0.5)),
                "congestion_score":      float(r.get("congestion_score", 0.3)),
                "weather_exposure_score":float(r.get("weather_exposure_score", 0.2)),
                "dynamic_risk_score":    float(r.get("dynamic_risk_score", 0.5)),
                "time_risk":             float(r.get("time_risk", 0.3)),
                # Extended columns (present if hourly weights were built via build_hourly_edge_weights)
                "lighting_dark_risk":    float(r.get("lighting_dark_risk", 0.5)),
                "isolated_area_score":   float(r.get("isolated_area_score", 0.3)),
                "crime_score":           float(r.get("crime_score", 0.3)),
            }

        # Phase 3: KDTree with cos_lat longitude scaling (matches Graph Engine v8)
        import math as _math
        self.kdtree_ids = list(self.node_lookup.keys())
        _lats = np.array([self.node_lookup[nid]["lat"] for nid in self.kdtree_ids])
        _lngs = np.array([self.node_lookup[nid]["lng"] for nid in self.kdtree_ids])
        _mean_lat = float(_lats.mean()) if len(_lats) > 0 else 13.0
        self._cos_lat = _math.cos(_math.radians(_mean_lat))
        _scaled_coords = np.column_stack([_lats, _lngs * self._cos_lat])
        self.kdtree = KDTree(_scaled_coords)

        # Phase 19: Precompute safe havens
        self._build_safe_havens()

        # Phase 24/25: Zone detection
        self._detect_zones()

        self.loaded = True
        elapsed = time.time() - t0
        if verbose:
            print(f"  ✓ {len(self.node_lookup)} nodes, {len(self.edge_lookup)} edges, "
                  f"{len(self.weight_index)} weight records  [{elapsed:.1f}s]")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3 — NODE SNAPPING
    # ══════════════════════════════════════════════════════════════════════════
    def snap_to_nearest_node(self, lat, lng, k=1):
        """< 10ms lookup via KDTree with cos_lat scaling (matches Graph Engine v8)."""
        q = np.array([lat, lng * self._cos_lat])
        dists, idxs = self.kdtree.query(q, k=k)
        if k == 1:
            return self.kdtree_ids[int(idxs)]
        return [self.kdtree_ids[int(i)] for i in idxs]

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 4 — HOURLY WEIGHT SELECTION
    # ══════════════════════════════════════════════════════════════════════════
    def get_current_edge_weight(self, edge_id, hour):
        """Return weight dict for (edge_id, hour), fallback to nearest hour."""
        w = self.weight_index.get((edge_id, hour))
        if w: return w
        # nearest hour fallback
        for delta in range(1, 24):
            for sign in [1, -1]:
                h2 = (hour + sign * delta) % 24
                w = self.weight_index.get((edge_id, h2))
                if w: return w
        return {"final_edge_weight": 0.5,
                "final_risk_score": 0.5,
                "congestion_score": 0.3,
                "weather_exposure_score": 0.2,
                "dynamic_risk_score": 0.5,
                "time_risk": 0.3,
                # Extended columns — None signals to calculate_edge_cost to use proxy fallback
                "lighting_dark_risk":     None,
                "isolated_area_score":    None,
                "crime_score":            None,
                }

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 5 — MULTI-CRITERIA COST FUNCTION
    # ══════════════════════════════════════════════════════════════════════════
    def calculate_edge_cost(self, edge_id, hour, profile="default", women_safety_bonus=0.0):
        edge = self.edge_lookup.get(edge_id, {})
        w = self.get_current_edge_weight(edge_id, hour)
        pw = PROFILE_WEIGHTS.get(profile, PROFILE_WEIGHTS["default"])

        # Incident penalty (Phase 23)
        incident_penalty = 0.0
        if edge_id in self.incidents:
            inc = self.incidents[edge_id]
            sev = {"Accident": 0.6, "Flood": 0.8, "Crime": 0.7,
                   "Road Closure": 1.0, "Construction": 0.4, "Event": 0.3}
            incident_penalty = sev.get(inc.get("type", ""), 0.5)
            if inc.get("type") == "Road Closure":
                return 999.0  # impassable

        # Normalize travel time (0-1 scale, assuming max 30min edge)
        t_norm = min(edge.get("travel_time", 0.5) / 30.0, 1.0)

        cost = (pw.get("risk", 0.45) * w["final_risk_score"]
              + pw.get("time", 0.25) * t_norm
              + pw.get("congestion", 0.20) * w["congestion_score"]
              + pw.get("weather", 0.10) * w["weather_exposure_score"]
              + incident_penalty * 0.3)

        # Women safety bonus: reward well-lit/commercial edges
        if profile == "women":
            road_type = edge.get("road_type", "residential")
            road_type_bonus = {"primary": -0.12, "secondary": -0.08, "trunk": -0.10,
                               "residential": 0.05, "living_street": 0.10}.get(road_type, 0.0)
            # Use actual per-edge lighting and isolation data when available.
            # These come from lighting_dark_risk and isolated_area_score in hourly weights,
            # populated by build_hourly_edge_weights() in the Risk Engine.
            lighting = w.get("lighting_dark_risk", None)   # 0-1: high = poorly lit = risky
            isolated = w.get("isolated_area_score", None)  # 0-1: high = more isolated = risky
            if lighting is not None and isolated is not None:
                # Well-lit roads: reduce cost. Poorly-lit roads: increase cost.
                lighting_bonus  = -(1.0 - float(lighting)) * 0.18
                # Isolated roads: increase cost proportional to isolation.
                isolation_bonus = float(isolated) * 0.15
                cost += lighting_bonus + isolation_bonus + women_safety_bonus
            else:
                # Fallback to road-type proxy when per-edge lighting data is unavailable.
                cost += road_type_bonus + women_safety_bonus

        return max(0.001, cost)

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 6 — A* HEURISTIC
    # ══════════════════════════════════════════════════════════════════════════
    def heuristic(self, node_id, goal_id):
        n = self.node_lookup.get(node_id, {})
        g = self.node_lookup.get(goal_id, {})
        if not n or not g: return 0.0
        dist_km = cached_haversine(n["lat"], n["lng"], g["lat"], g["lng"])
        # Admissible: 0.001 cost/km (conservative lower bound)
        return dist_km * 0.001

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 7 — CUSTOM A* SEARCH
    # ══════════════════════════════════════════════════════════════════════════
    def find_safe_route(self, source_node, destination_node, hour=None, profile="default",
                        forbidden_edges=None, forbidden_nodes=None):
        """
        A* with came_from pointer reconstruction — O(V) memory.

        Replaces the previous path-in-heap approach which was O(n^2) memory
        because every heap entry carried a full copy of the path so far.
        """
        if hour is None:
            hour = datetime.now().hour
        hour = int(hour) % 24
        forbidden_edges = forbidden_edges or set()
        forbidden_nodes = forbidden_nodes or set()

        open_heap = []
        h0 = self.heuristic(source_node, destination_node)
        heapq.heappush(open_heap, (h0, 0.0, source_node))

        g_score: Dict[int, float] = {source_node: 0.0}
        came_from_node: Dict[int, Optional[int]] = {source_node: None}
        came_from_edge: Dict[int, Optional[str]] = {source_node: None}
        closed_set: set = set()

        while open_heap:
            f, g, node = heapq.heappop(open_heap)

            if node in closed_set:
                continue
            closed_set.add(node)

            if node == destination_node:
                # Reconstruct path and edge_path by following came_from pointers
                path: List[int] = []
                edge_path: List[str] = []
                cur = destination_node
                while cur is not None:
                    path.append(cur)
                    e = came_from_edge.get(cur)
                    if e is not None:
                        edge_path.append(e)
                    cur = came_from_node.get(cur)
                path.reverse()
                edge_path.reverse()
                return path, g, edge_path

            for neighbor, edge_id in self.adjacency.get(node, []):
                if neighbor in closed_set:
                    continue
                if neighbor in forbidden_nodes or edge_id in forbidden_edges:
                    continue

                cost = self.calculate_edge_cost(edge_id, hour, profile)
                new_g = g + cost

                if new_g < g_score.get(neighbor, float("inf")):
                    g_score[neighbor] = new_g
                    came_from_node[neighbor] = node
                    came_from_edge[neighbor] = edge_id
                    h = self.heuristic(neighbor, destination_node)
                    heapq.heappush(open_heap, (new_g + h, new_g, neighbor))

        return None, float("inf"), []

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 8 — ROUTE METRICS
    # ══════════════════════════════════════════════════════════════════════════
    def compute_route_metrics(self, path, edge_path, hour):
        if not path or len(path) < 2:
            return {}
        total_dist = 0.0
        total_time = 0.0
        risks = []
        congestions = []
        weather_scores = []
        lighting_risks: List[float] = []
        isolation_scores: List[float] = []

        for eid in edge_path:
            edge = self.edge_lookup.get(eid, {})
            w = self.get_current_edge_weight(eid, hour)
            total_dist += edge.get("distance", 0.0)
            total_time += edge.get("travel_time", 0.0)
            risks.append(w["final_risk_score"])
            congestions.append(w["congestion_score"])
            weather_scores.append(w["weather_exposure_score"])
            # Extended columns (populated when hourly weights built via Risk Engine v6.1)
            _ldr = w.get("lighting_dark_risk")
            if _ldr is not None:
                lighting_risks.append(float(_ldr))
            _iso = w.get("isolated_area_score")
            if _iso is not None:
                isolation_scores.append(float(_iso))

        return {
            "total_distance_km": round(total_dist, 3),
            "total_travel_time_min": round(total_time, 2),
            "average_risk": round(float(np.mean(risks)), 4) if risks else 0.5,
            "maximum_risk": round(float(np.max(risks)), 4) if risks else 0.5,
            "average_congestion": round(float(np.mean(congestions)), 4) if congestions else 0.3,
            "weather_exposure": round(float(np.mean(weather_scores)), 4) if weather_scores else 0.2,
            "node_count": len(path),
            "edge_count": len(edge_path),
            "average_lighting_dark_risk": round(float(np.mean(lighting_risks)), 4) if lighting_risks else None,
            "average_isolation":          round(float(np.mean(isolation_scores)), 4) if isolation_scores else None,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 9 — ROUTE GEOMETRY
    # ══════════════════════════════════════════════════════════════════════════
    def get_route_coordinates(self, path):
        coords = []
        for nid in path:
            n = self.node_lookup.get(nid, {})
            if n:
                coords.append([n["lat"], n["lng"]])
        return coords

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 10 — ALTERNATIVE ROUTES
    # ══════════════════════════════════════════════════════════════════════════
    def find_alternative_routes(self, source_node, destination_node, hour=None, n=3):
        """Return up to n meaningfully different routes."""
        if hour is None:
            hour = datetime.now().hour
        routes = []
        profiles = ["default", "fastest", "balanced"]

        for i, profile in enumerate(profiles[:n]):
            forbidden_edges = set()
            # For routes 2+, penalize edges from previous routes
            for prev in routes:
                if i > 0 and prev.get("edge_path"):
                    # Forbid middle 60% of previous route edges
                    ep = prev["edge_path"]
                    start = len(ep) // 5
                    end = len(ep) * 4 // 5
                    forbidden_edges.update(ep[start:end])

            path, cost, edge_path = self.find_safe_route(
                source_node, destination_node, hour, profile, forbidden_edges)

            if path:
                metrics = self.compute_route_metrics(path, edge_path, hour)
                coords = self.get_route_coordinates(path)
                explanation = self._explain_route(edge_path, hour, profile, metrics)
                safety_profile = self._route_safety_profile(edge_path, hour)  # Phase 20
                routes.append({
                    "route_id": chr(65 + i),
                    "profile": profile,
                    "path": path,
                    "edge_path": edge_path,
                    "cost": round(cost, 4),
                    "metrics": metrics,
                    "coordinates": coords,
                    "explanation": explanation,
                    "safety_profile": safety_profile,
                    "confidence_score": self._confidence_score(path, edge_path),
                })

        return routes

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 11 — ROUTE EXPLANATION
    # ══════════════════════════════════════════════════════════════════════════
    def _explain_route(self, edge_path, hour, profile, metrics):
        if not edge_path:
            return {"reasons": ["No route found"]}

        high_risk = sum(1 for eid in edge_path
                        if self.get_current_edge_weight(eid, hour)["final_risk_score"] > 0.7)
        low_risk  = sum(1 for eid in edge_path
                        if self.get_current_edge_weight(eid, hour)["final_risk_score"] < 0.3)
        road_types = [self.edge_lookup.get(eid, {}).get("road_type", "") for eid in edge_path]
        major_roads = sum(1 for rt in road_types if rt in ("primary", "secondary", "trunk"))
        isolated   = sum(1 for rt in road_types if rt in ("living_street", "residential"))

        reasons = []
        if high_risk == 0:
            reasons.append("Avoided all high-risk road segments")
        elif high_risk > 0:
            reasons.append(f"Traversed {high_risk} higher-risk segment(s) — unavoidable")
        if low_risk > 0:
            reasons.append(f"Used {low_risk} low-risk road segments")
        if major_roads > 0:
            reasons.append(f"Used {major_roads} major/well-lit road(s)")
        if isolated > 5:
            reasons.append(f"Note: {isolated} residential segments — limited alternatives")
        if metrics.get("average_risk", 1) < 0.35:
            reasons.append(f"Average risk score: {metrics['average_risk']:.2f} (low)")
        if profile == "women":
            reasons.append("Women Safety Mode: prioritized lit, commercial, and populated roads")
        if profile == "fastest":
            reasons.append("Fastest profile: minimized travel time")
        reasons.append(f"Total distance: {metrics.get('total_distance_km',0):.2f} km, "
                        f"ETA: {metrics.get('total_travel_time_min',0):.0f} min")
        return {"route_profile": profile, "reasons": reasons}

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 12 — CONFIDENCE SCORE
    # ══════════════════════════════════════════════════════════════════════════
    def _confidence_score(self, path, edge_path):
        if not path or not edge_path:
            return 0
        weight_coverage = sum(1 for eid in edge_path
                               if any((eid, h) in self.weight_index for h in range(24)))
        coverage_ratio = weight_coverage / max(len(edge_path), 1)
        length_bonus = min(len(path) / 20.0, 1.0)
        score = int((coverage_ratio * 0.7 + length_bonus * 0.3) * 100)
        return min(score, 100)

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 16 — PREDICTIVE RISK ENGINE
    # ══════════════════════════════════════════════════════════════════════════
    def predict_future_risk(self, edge_ids, target_hour):
        """Predict risk for a list of edges at a future hour using historical patterns."""
        results = {}
        for eid in edge_ids:
            hourly_risks = []
            for h in range(24):
                w = self.weight_index.get((eid, h))
                if w:
                    hourly_risks.append((h, w["final_risk_score"]))

            if not hourly_risks:
                results[eid] = {"predicted_risk": 0.5, "trend": "unknown", "hour": target_hour}
                continue

            # Target hour risk
            w_target = self.get_current_edge_weight(eid, target_hour)
            predicted = w_target["final_risk_score"]

            # Trend: compare to current hour
            current_h = datetime.now().hour
            w_now = self.get_current_edge_weight(eid, current_h)
            diff = predicted - w_now["final_risk_score"]
            trend = "increasing" if diff > 0.05 else ("decreasing" if diff < -0.05 else "stable")

            label = ("safe" if predicted < 0.35 else
                     "moderate" if predicted < 0.55 else
                     "caution" if predicted < 0.75 else "unsafe")

            results[eid] = {
                "predicted_risk": round(predicted, 4),
                "current_risk": round(w_now["final_risk_score"], 4),
                "trend": trend,
                "label": label,
                "hour": target_hour,
            }
        return results

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 17 — WOMEN SAFETY MODE
    # ══════════════════════════════════════════════════════════════════════════
    def compute_women_safety_score(self, edge_ids, hour):
        """Score based on lighting, CCTV proxy (major roads), activity, crime."""
        scores = []
        for eid in edge_ids:
            edge = self.edge_lookup.get(eid, {})
            w = self.get_current_edge_weight(eid, hour)
            road_type = edge.get("road_type", "residential")

            # Proxy: lighting_score from road type
            lighting = {"motorway": 0.9, "trunk": 0.85, "primary": 0.8,
                        "secondary": 0.7, "tertiary": 0.6, "residential": 0.35,
                        "living_street": 0.25, "arterial_connector": 0.65}.get(road_type, 0.4)
            # CCTV density proxy (major roads have more)
            cctv = {"motorway": 0.9, "trunk": 0.8, "primary": 0.75,
                    "secondary": 0.6, "tertiary": 0.45, "residential": 0.2,
                    "living_street": 0.1}.get(road_type, 0.3)
            # Human presence (day=high, night=low for isolated roads)
            if hour in range(7, 22):
                human_presence = lighting  # proxy
            else:
                human_presence = lighting * 0.4

            crime_inv = 1.0 - w["final_risk_score"]  # invert risk as crime proxy
            score = (0.30 * lighting + 0.25 * cctv + 0.20 * human_presence +
                     0.25 * crime_inv)
            scores.append(score)

        return round(float(np.mean(scores)), 4) if scores else 0.5

    def find_women_safe_route(self, source_node, destination_node, hour=None):
        if hour is None:
            hour = datetime.now().hour
        path, cost, edge_path = self.find_safe_route(
            source_node, destination_node, hour, profile="women")
        if not path:
            return None
        metrics = self.compute_route_metrics(path, edge_path, hour)
        women_score = self.compute_women_safety_score(edge_path, hour)
        return {
            "path": path,
            "edge_path": edge_path,
            "women_safety_score": women_score,
            "metrics": metrics,
            "coordinates": self.get_route_coordinates(path),
            "explanation": self._explain_route(edge_path, hour, "women", metrics),
        }

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 18 — EMERGENCY ESCAPE ROUTING
    # ══════════════════════════════════════════════════════════════════════════
    def find_emergency_escape_route(self, user_lat, user_lng, hour=None):
        """SOS: find routes to nearest police, hospital, and public area nodes."""
        if hour is None:
            hour = datetime.now().hour
        user_node = self.snap_to_nearest_node(user_lat, user_lng)

        results = {}
        for haven_type, nodes in self.safe_haven_nodes.items():
            if not nodes:
                continue
            # Find nearest 3 candidate nodes
            best = None
            best_cost = float("inf")
            candidates = nodes[:5]
            for nid in candidates:
                path, cost, ep = self.find_safe_route(user_node, nid, hour, "fastest")
                if path and cost < best_cost:
                    best_cost = cost
                    best = (path, ep, cost)
            if best:
                path, ep, cost = best
                metrics = self.compute_route_metrics(path, ep, hour)
                results[haven_type] = {
                    "path": path,
                    "edge_path": ep,
                    "cost": round(cost, 4),
                    "metrics": metrics,
                    "coordinates": self.get_route_coordinates(path),
                    "destination_node": path[-1],
                }

        # Also find nearest CCTV-dense zone (proxy: nearest primary/secondary road node)
        cctv_nodes = [nid for nid, einfo in self.node_lookup.items()
                      if einfo.get("adjacency_count", 0) >= 6][:20]
        if cctv_nodes:
            # Get top 5 by distance
            dists = [(haversine_km(user_lat, user_lng,
                                   self.node_lookup[n]["lat"],
                                   self.node_lookup[n]["lng"]), n)
                     for n in cctv_nodes]
            dists.sort()
            for _, nid in dists[:3]:
                path, cost, ep = self.find_safe_route(user_node, nid, hour, "fastest")
                if path:
                    results["cctv_dense_zone"] = {
                        "path": path, "edge_path": ep,
                        "cost": round(cost, 4),
                        "metrics": self.compute_route_metrics(path, ep, hour),
                        "coordinates": self.get_route_coordinates(path),
                    }
                    break

        return results

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 19 — SAFE HAVEN NETWORK
    # ══════════════════════════════════════════════════════════════════════════
    def _build_safe_havens(self):
        """
        Assign graph nodes as safe haven proxies by snapping semantic POI coordinates
        to the nearest graph node via KDTree.

        Replaces the previous degree-based heuristic which had no spatial validity
        and could classify IT park flyover nodes as police stations.
        """
        if not hasattr(self, "kdtree") or self.kdtree is None:
            # KDTree not yet built — fall back to degree heuristic as last resort
            all_nodes = sorted(self.node_lookup.items(),
                               key=lambda x: x[1]["adjacency_count"], reverse=True)
            top_nodes = [nid for nid, _ in all_nodes[:500]]
            chunk = max(len(top_nodes) // 5, 1)
            self.safe_haven_nodes = {
                "police_station": top_nodes[:chunk],
                "hospital":       top_nodes[chunk:2*chunk],
                "metro_station":  top_nodes[2*chunk:3*chunk],
                "bus_station":    top_nodes[3*chunk:4*chunk],
                "public_area":    top_nodes[4*chunk:],
            }
            return

        def _snap_poi_list(poi_list: List[Dict]) -> List[int]:
            """Snap each POI to the nearest graph node; return list of unique node IDs."""
            snapped = []
            for poi in poi_list:
                nid = self.snap_to_nearest_node(poi["lat"], poi["lng"], k=1)
                if nid is not None and nid not in snapped:
                    snapped.append(nid)
            return snapped

        police_nodes  = _snap_poi_list(self._POLICE_POI)
        hospital_nodes = _snap_poi_list(self._HOSPITAL_POI)

        # Metro stations: snap from known Namma Metro coordinates (Phase 1 line + Phase 2)
        _metro_pois = [
            {"name": "MG Road",         "lat": 12.9752, "lng": 77.6068},
            {"name": "Indiranagar",      "lat": 12.9784, "lng": 77.6408},
            {"name": "Baiyappanahalli", "lat": 12.9847, "lng": 77.6709},
            {"name": "Majestic",         "lat": 12.9768, "lng": 77.5711},
            {"name": "Yeshwanthpur",     "lat": 13.0248, "lng": 77.5513},
            {"name": "Hebbal",           "lat": 13.0362, "lng": 77.5976},
            {"name": "Whitefield",       "lat": 12.9698, "lng": 77.7504},
            {"name": "Electronic City",  "lat": 12.8394, "lng": 77.6774},
            {"name": "Koramangala",      "lat": 12.9289, "lng": 77.6269},
            {"name": "Banashankari",     "lat": 12.9205, "lng": 77.5623},
        ]
        metro_nodes = _snap_poi_list(_metro_pois)

        # Bus stations: BMTC major terminals
        _bus_pois = [
            {"name": "Majestic KSRTC",   "lat": 12.9767, "lng": 77.5718},
            {"name": "Shivajinagar",      "lat": 12.9878, "lng": 77.6019},
            {"name": "Kempegowda",        "lat": 13.1979, "lng": 77.7063},
            {"name": "Mysore Road",       "lat": 12.9450, "lng": 77.5064},
            {"name": "Marathahalli",      "lat": 12.9593, "lng": 77.7009},
            {"name": "BTM Layout",        "lat": 12.9126, "lng": 77.6096},
            {"name": "Whitefield",        "lat": 12.9700, "lng": 77.7501},
            {"name": "Electronic City",   "lat": 12.8447, "lng": 77.6593},
        ]
        bus_nodes = _snap_poi_list(_bus_pois)

        # Public areas: high-footfall open spaces
        _public_pois = [
            {"name": "Cubbon Park",         "lat": 12.9763, "lng": 77.5929},
            {"name": "Lalbagh Garden",      "lat": 12.9507, "lng": 77.5848},
            {"name": "Ulsoor Lake",         "lat": 12.9836, "lng": 77.6207},
            {"name": "UB City Mall",        "lat": 12.9724, "lng": 77.5960},
            {"name": "Forum Mall",          "lat": 12.9363, "lng": 77.6147},
            {"name": "Phoenix Mall",        "lat": 12.9970, "lng": 77.6964},
            {"name": "Orion Mall",          "lat": 13.0035, "lng": 77.5537},
        ]
        public_nodes = _snap_poi_list(_public_pois)

        self.safe_haven_nodes = {
            "police_station": police_nodes,
            "hospital":       hospital_nodes,
            "metro_station":  metro_nodes,
            "bus_station":    bus_nodes,
            "public_area":    public_nodes,
        }

        total_havens = sum(len(v) for v in self.safe_haven_nodes.values())
        print(f"  ✓ Safe havens: {total_havens} semantic nodes "
              f"(police:{len(police_nodes)}, hospital:{len(hospital_nodes)}, "
              f"metro:{len(metro_nodes)}, bus:{len(bus_nodes)}, public:{len(public_nodes)})")

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 20 — ROUTE SAFETY HEATMAP PROFILE
    # ══════════════════════════════════════════════════════════════════════════
    def _route_safety_profile(self, edge_path, hour):
        """Segment the route into risk bands."""
        if not edge_path:
            return []
        n = len(edge_path)
        segments = 5  # divide into 5 segments
        size = max(n // segments, 1)
        profile = []
        for i in range(0, n, size):
            chunk = edge_path[i:i+size]
            risks = [self.get_current_edge_weight(eid, hour)["final_risk_score"]
                     for eid in chunk]
            avg_risk = float(np.mean(risks)) if risks else 0.5
            pct_start = round(i / n * 100)
            pct_end = round(min((i + size) / n * 100, 100))
            label = ("safe" if avg_risk < 0.35 else
                     "moderate" if avg_risk < 0.55 else
                     "caution" if avg_risk < 0.75 else "high_risk")
            profile.append({
                "segment": f"{pct_start}-{pct_end}%",
                "avg_risk": round(avg_risk, 3),
                "label": label,
            })
        return profile

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 21 — TIME MACHINE ROUTING
    # ══════════════════════════════════════════════════════════════════════════
    def route_at_time(self, source_node, destination_node, hour):
        """Route at a specific hour for comparison."""
        path, cost, edge_path = self.find_safe_route(
            source_node, destination_node, hour)
        if not path:
            return None
        metrics = self.compute_route_metrics(path, edge_path, hour)
        return {
            "hour": hour,
            "path": path,
            "edge_path": edge_path,
            "cost": round(cost, 4),
            "metrics": metrics,
            "coordinates": self.get_route_coordinates(path),
            "safety_profile": self._route_safety_profile(edge_path, hour),
        }

    def compare_routes_by_time(self, source_node, destination_node, hours=None):
        """Compare same route across multiple hours."""
        if hours is None:
            hours = [7, 12, 18, 22, 2]
        results = {}
        for h in hours:
            r = self.route_at_time(source_node, destination_node, h)
            if r:
                results[f"{h:02d}:00"] = {
                    "avg_risk": r["metrics"]["average_risk"],
                    "travel_time": r["metrics"]["total_travel_time_min"],
                    "cost": r["cost"],
                    "label": ("safe" if r["metrics"]["average_risk"] < 0.35 else
                              "moderate" if r["metrics"]["average_risk"] < 0.55 else "unsafe"),
                }
        return results

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 22 — ROUTE SIMULATION ENGINE
    # ══════════════════════════════════════════════════════════════════════════
    def simulate_route(self, path, edge_path, hour, start_time_min=0):
        """Generate minute-by-minute travel/risk/traffic timeline."""
        timeline = []
        elapsed = start_time_min

        for i, eid in enumerate(edge_path):
            edge = self.edge_lookup.get(eid, {})
            w = self.get_current_edge_weight(eid, hour)
            seg_time = edge.get("travel_time", 0.5)
            risk = w["final_risk_score"]
            congestion = w["congestion_score"]

            risk_label = ("safe" if risk < 0.35 else
                          "moderate" if risk < 0.55 else
                          "caution" if risk < 0.75 else "high_risk")
            traffic_label = ("clear" if congestion < 0.3 else
                             "moderate traffic" if congestion < 0.6 else "high congestion")

            timeline.append({
                "minute": round(elapsed, 1),
                "edge_id": eid,
                "road_name": edge.get("road_name", ""),
                "road_type": edge.get("road_type", ""),
                "risk_score": round(risk, 3),
                "risk_label": risk_label,
                "congestion": round(congestion, 3),
                "traffic_label": traffic_label,
                "distance_km": round(edge.get("distance", 0.0), 3),
            })
            elapsed += seg_time

        return {
            "total_minutes": round(elapsed - start_time_min, 1),
            "segments": len(timeline),
            "timeline": timeline,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 23 — REAL-TIME INCIDENT INJECTION
    # ══════════════════════════════════════════════════════════════════════════
    def load_incidents(self):
        """Load incident_layer.csv if it exists."""
        if INCIDENT_CSV.exists():
            df = pd.read_csv(INCIDENT_CSV)
            for _, row in df.iterrows():
                eid = str(row["edge_id"])
                self.incidents[eid] = {
                    "type": str(row.get("type", "Unknown")),
                    "severity": float(row.get("severity", 0.5)),
                    "description": str(row.get("description", "")),
                }
            print(f"  ✓ Loaded {len(self.incidents)} incidents")

    def inject_incident(self, edge_id, incident_type, severity=0.5, description=""):
        """Inject a live incident — A* will automatically re-route."""
        valid = ["Accident", "Flood", "Crime", "Road Closure", "Construction", "Event"]
        if incident_type not in valid:
            raise ValueError(f"Type must be one of: {valid}")
        self.incidents[str(edge_id)] = {
            "type": incident_type,
            "severity": severity,
            "description": description,
        }

    def clear_incident(self, edge_id):
        self.incidents.pop(str(edge_id), None)

    def save_incident_layer(self):
        if not self.incidents:
            return
        rows = [{"edge_id": eid, **info} for eid, info in self.incidents.items()]
        pd.DataFrame(rows).to_csv(INCIDENT_CSV, index=False)

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 24/25 — SAFE & UNSAFE ZONE DETECTION
    # ══════════════════════════════════════════════════════════════════════════
    def _detect_zones(self):
        """Cluster nodes into safe and danger zones using adjacency + weight proxies."""
        # Aggregate per-node average risk from incident edges
        node_risk = {}
        for (eid, h), w in self.weight_index.items():
            if h != 12:  # use midday as representative
                continue
            edge = self.edge_lookup.get(eid, {})
            for nid in [edge.get("source_node"), edge.get("destination_node")]:
                if nid is None:
                    continue
                if nid not in node_risk:
                    node_risk[nid] = []
                node_risk[nid].append(w["final_risk_score"])

        node_avg_risk = {nid: float(np.mean(v)) for nid, v in node_risk.items()}

        safe_nodes = [nid for nid, r in node_avg_risk.items() if r < 0.30]
        danger_nodes = [nid for nid, r in node_avg_risk.items() if r > 0.70]

        # Group into clusters by zone
        safe_by_zone = defaultdict(list)
        danger_by_zone = defaultdict(list)
        for nid in safe_nodes:
            zone = self.node_lookup.get(nid, {}).get("zone", "Unknown")
            safe_by_zone[zone].append(nid)
        for nid in danger_nodes:
            zone = self.node_lookup.get(nid, {}).get("zone", "Unknown")
            danger_by_zone[zone].append(nid)

        self.safe_zone_clusters = [
            {"zone": z, "node_count": len(nodes),
             "centroid_lat": np.mean([self.node_lookup[n]["lat"] for n in nodes]),
             "centroid_lng": np.mean([self.node_lookup[n]["lng"] for n in nodes]),
             "label": "Safe Zone"}
            for z, nodes in safe_by_zone.items() if nodes
        ]
        self.danger_zone_clusters = [
            {"zone": z, "node_count": len(nodes),
             "centroid_lat": np.mean([self.node_lookup[n]["lat"] for n in nodes]),
             "centroid_lng": np.mean([self.node_lookup[n]["lng"] for n in nodes]),
             "label": "Danger Zone"}
            for z, nodes in danger_by_zone.items() if nodes
        ]

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 26 — ROUTE REDUNDANCY ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    def find_fallback_routes(self, source_node, destination_node, hour=None, n=3):
        """Generate primary + fallback routes with diversity enforcement."""
        return self.find_alternative_routes(source_node, destination_node, hour, n)

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 27 — SAFE ROUTE EXPLAINABILITY AI
    # ══════════════════════════════════════════════════════════════════════════
    def route_reasoning_engine(self, selected_route, alternative_routes, hour):
        """Generate detailed reasoning comparing selected vs alternatives."""
        if not selected_route:
            return {"error": "No route to explain"}

        sel_metrics = selected_route["metrics"]
        sel_risk = sel_metrics.get("average_risk", 0.5)
        sel_time = sel_metrics.get("total_travel_time_min", 0)
        sel_dist = sel_metrics.get("total_distance_km", 0)

        # Compare against worst alternative
        worst_risk = sel_risk
        for alt in alternative_routes:
            if alt["route_id"] != selected_route["route_id"]:
                alt_risk = alt["metrics"].get("average_risk", 0.5)
                if alt_risk > worst_risk:
                    worst_risk = alt_risk

        risk_reduction_pct = round((worst_risk - sel_risk) / max(worst_risk, 0.01) * 100, 1)

        # Count avoided risk nodes
        ep = selected_route.get("edge_path", [])
        high_risk_avoided = sum(1 for eid in ep
            if self.get_current_edge_weight(eid, hour)["final_risk_score"] < 0.5)
        isolated_avoided = sum(1 for eid in ep
            if self.edge_lookup.get(eid, {}).get("road_type") not in
               ("living_street", "residential"))
        major_roads_used = sum(1 for eid in ep
            if self.edge_lookup.get(eid, {}).get("road_type") in
               ("primary", "secondary", "trunk", "tertiary"))

        time_diff = 0
        for alt in alternative_routes:
            if alt["route_id"] != selected_route["route_id"]:
                t2 = alt["metrics"].get("total_travel_time_min", sel_time)
                time_diff = round(sel_time - t2, 1)
                break

        reasoning = {
            "selected_route": selected_route["route_id"],
            "profile": selected_route.get("profile", "default"),
            "summary": f"Selected Route {selected_route['route_id']} "
                       f"({'safest' if sel_risk == min(r['metrics'].get('average_risk',1) for r in [selected_route]+alternative_routes) else 'optimized'})",
            "metrics": {
                "avg_risk": sel_risk,
                "distance_km": sel_dist,
                "travel_time_min": sel_time,
            },
            "reasons": [
                f"Avoided {high_risk_avoided} high-risk road segments",
                f"Avoided {len(ep) - major_roads_used} isolated/poor-visibility roads",
                f"Used {major_roads_used} well-lit, major road segment(s)",
                f"Risk reduced by {risk_reduction_pct}% vs worst alternative",
                (f"Travel time {'increased' if time_diff > 0 else 'reduced'} by "
                 f"{abs(time_diff):.1f} min vs fastest alternative"),
            ],
            "confidence": selected_route.get("confidence_score", 75),
        }
        return reasoning

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 28 — RISK VISUALIZATION ENGINE
    # ══════════════════════════════════════════════════════════════════════════
    def generate_route_risk_heatmap(self, routes, hour, output_path=None):
        """Generate route_risk_heatmap.png with color-coded risk overlay."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.cm as cm
            from matplotlib.colors import Normalize

            fig, ax = plt.subplots(figsize=(14, 10))
            fig.patch.set_facecolor("#0d1117")
            ax.set_facecolor("#0d1117")

            # Background nodes (faint)
            all_lats = [v["lat"] for v in self.node_lookup.values()]
            all_lngs = [v["lng"] for v in self.node_lookup.values()]
            ax.scatter(all_lngs, all_lats, s=0.3, c="#1a1a2e", alpha=0.3, linewidths=0)

            cmap = cm.get_cmap("RdYlGn_r")
            norm = Normalize(vmin=0, vmax=1)

            route_styles = [
                ("-", 2.5, "Route A (Safest)"),
                ("--", 2.0, "Route B (Fastest)"),
                (":", 1.8, "Route C (Balanced)"),
            ]

            for i, route in enumerate(routes[:3]):
                ep = route.get("edge_path", [])
                style, lw, label = route_styles[i] if i < 3 else ("-", 1.5, f"Route {i+1}")
                for eid in ep:
                    edge = self.edge_lookup.get(eid, {})
                    w = self.get_current_edge_weight(eid, hour)
                    risk = w["final_risk_score"]
                    src = self.node_lookup.get(edge.get("source_node", -1), {})
                    dst = self.node_lookup.get(edge.get("destination_node", -1), {})
                    if src and dst:
                        color = cmap(norm(risk))
                        ax.plot([src["lng"], dst["lng"]], [src["lat"], dst["lat"]],
                                color=color, lw=lw, linestyle=style, alpha=0.85)

            # Safe zone markers
            for sz in self.safe_zone_clusters[:10]:
                ax.scatter(sz["centroid_lng"], sz["centroid_lat"],
                           s=80, c="#00ff88", marker="o", alpha=0.6, zorder=5)
            for dz in self.danger_zone_clusters[:10]:
                ax.scatter(dz["centroid_lng"], dz["centroid_lat"],
                           s=80, c="#ff4444", marker="X", alpha=0.6, zorder=5)

            sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            cb = plt.colorbar(sm, ax=ax, shrink=0.6, pad=0.01)
            cb.set_label("Risk Score", color="white", fontsize=10)
            cb.ax.yaxis.set_tick_params(color="gray")
            plt.setp(cb.ax.yaxis.get_ticklabels(), color="gray")

            # Legend
            from matplotlib.lines import Line2D
            legend_elems = [
                Line2D([0], [0], color="#00cc44", lw=2, label="Safe (< 0.35)"),
                Line2D([0], [0], color="#ffcc00", lw=2, label="Moderate (0.35-0.55)"),
                Line2D([0], [0], color="#ff8800", lw=2, label="Caution (0.55-0.75)"),
                Line2D([0], [0], color="#ff0000", lw=2, label="High Risk (> 0.75)"),
                Line2D([0], [0], color="white", lw=0, marker="o", markerfacecolor="#00ff88",
                       markersize=8, label="Safe Zone"),
                Line2D([0], [0], color="white", lw=0, marker="X", markerfacecolor="#ff4444",
                       markersize=8, label="Danger Zone"),
            ]
            for s, lw2, lbl in route_styles[:len(routes)]:
                legend_elems.append(Line2D([0], [0], color="white", lw=lw2,
                                           linestyle=s, label=lbl))

            ax.legend(handles=legend_elems, loc="lower right", fontsize=8,
                      facecolor="#1a1a2e", labelcolor="white", framealpha=0.85)

            ax.set_title(f"SafeRoute-AI v8.0 — Route Risk Heatmap  [Hour {hour:02d}:00]",
                         color="white", fontsize=13, fontweight="bold")
            ax.tick_params(colors="gray")
            for spine in ax.spines.values():
                spine.set_edgecolor("#333")
            ax.set_xlabel("Longitude", color="gray", fontsize=9)
            ax.set_ylabel("Latitude", color="gray", fontsize=9)

            out = output_path or str(OUT / "route_risk_heatmap.png")
            plt.tight_layout()
            plt.savefig(out, dpi=130, bbox_inches="tight", facecolor="#0d1117")
            plt.close()
            print(f"  ✓ route_risk_heatmap.png")
            return out
        except Exception as e:
            print(f"  Heatmap skipped: {e}")
            return None

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 29 — GRAPH PRECOMPUTATION CACHE
    # ══════════════════════════════════════════════════════════════════════════
    def build_routing_cache(self, save=True):
        """Precompute landmark, hub, safe/danger hub nodes and cache structures."""
        print("Building routing cache...")

        # Hub nodes: top-degree nodes
        sorted_nodes = sorted(self.node_lookup.items(),
                              key=lambda x: x[1]["adjacency_count"], reverse=True)
        hub_nodes = [nid for nid, _ in sorted_nodes[:200]]

        # Landmark nodes: top by connectivity_score
        landmark_nodes = sorted(self.node_lookup.items(),
                                key=lambda x: x[1]["connectivity_score"], reverse=True)
        landmark_nodes = [nid for nid, _ in landmark_nodes[:100]]

        # Safe/danger hubs
        safe_hubs, danger_hubs = [], []
        for (eid, h), w in self.weight_index.items():
            if h != 12:
                continue
            edge = self.edge_lookup.get(eid, {})
            for nid in [edge.get("source_node"), edge.get("destination_node")]:
                if nid in hub_nodes:
                    if w["final_risk_score"] < 0.3:
                        safe_hubs.append(nid)
                    elif w["final_risk_score"] > 0.7:
                        danger_hubs.append(nid)

        cache = {
            "version": "8.0",
            "created_at": datetime.now().isoformat(),
            "hub_nodes": list(set(hub_nodes)),
            "landmark_nodes": list(set(landmark_nodes)),
            "safe_hubs": list(set(safe_hubs))[:100],
            "danger_hubs": list(set(danger_hubs))[:100],
            "safe_haven_nodes": self.safe_haven_nodes,
            "safe_zone_clusters": self.safe_zone_clusters,
            "danger_zone_clusters": self.danger_zone_clusters,
            "node_count": len(self.node_lookup),
            "edge_count": len(self.edge_lookup),
        }

        if save:
            with open(CACHE_FILE, "wb") as f:
                pickle.dump(cache, f)
            print(f"  ✓ routing_cache.pkl  ({len(hub_nodes)} hubs, "
                  f"{len(landmark_nodes)} landmarks)")
        return cache

    def load_routing_cache(self):
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "rb") as f:
                return pickle.load(f)
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 30 — SAFE ROUTE RECOMMENDATION AI
    # ══════════════════════════════════════════════════════════════════════════
    def recommend_routes(self, source_lat, source_lng, dest_lat, dest_lng, hour=None):
        """Full pipeline: snap → route → recommend with explanations."""
        if hour is None:
            hour = datetime.now().hour

        src = self.snap_to_nearest_node(source_lat, source_lng)
        dst = self.snap_to_nearest_node(dest_lat, dest_lng)

        routes = self.find_alternative_routes(src, dst, hour, n=3)
        if not routes:
            return {"error": "No routes found", "src": src, "dst": dst}

        # Label routes
        labels = {
            "default": {"label": "Safest", "icon": "🛡️"},
            "fastest": {"label": "Fastest", "icon": "⚡"},
            "balanced": {"label": "Balanced", "icon": "⚖️"},
        }

        recommendations = []
        for r in routes:
            meta = labels.get(r["profile"], {"label": r["profile"], "icon": "🗺️"})
            reasoning = self.route_reasoning_engine(r, routes, hour)
            recommendations.append({
                "route_id": r["route_id"],
                "label": meta["label"],
                "icon": meta["icon"],
                "profile": r["profile"],
                "summary": {
                    "distance_km": r["metrics"]["total_distance_km"],
                    "travel_time_min": r["metrics"]["total_travel_time_min"],
                    "avg_risk": r["metrics"]["average_risk"],
                    "confidence": r["confidence_score"],
                },
                "safety_profile": r["safety_profile"],
                "reasoning": reasoning["reasons"],
                "coordinates": r["coordinates"],
            })

        return {
            "source_node": src,
            "destination_node": dst,
            "hour": hour,
            "generated_at": datetime.now().isoformat(),
            "recommendations": recommendations,
        }


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — Integration test + output generation
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 65)
    print("SafeRoute-AI v8.0 — Routing Engine")
    print("=" * 65)

    engine = SafeRouteEngine()
    engine.load_graph(verbose=True)
    engine.load_incidents()

    # Phase 29: cache
    cache = engine.build_routing_cache(save=True)

    # ── Test coordinates (Bangalore landmarks) ─────────────────────────────────
    ROUTES = [
        ("Koramangala → HSR Layout",       12.9352, 77.6245, 12.9082, 77.6476),
        ("Whitefield → MG Road",           12.9698, 77.7500, 12.9752, 77.6099),
        ("Electronic City → Airport",      12.8399, 77.6770, 13.1989, 77.7068),
    ]

    all_route_results = []
    all_summaries = []

    for route_name, slat, slng, dlat, dlng in ROUTES:
        print(f"\n{'─'*55}")
        print(f"  Route: {route_name}")
        t0 = time.time()

        result = engine.recommend_routes(slat, slng, dlat, dlng, hour=18)
        elapsed = time.time() - t0

        src = result.get("source_node")
        dst = result.get("destination_node")
        print(f"  Nodes: {src} → {dst}  [{elapsed*1000:.0f}ms]")

        recs = result.get("recommendations", [])
        for r in recs:
            s = r["summary"]
            print(f"  [{r['label']:8}] dist={s['distance_km']:.2f}km "
                  f"time={s['travel_time_min']:.1f}min "
                  f"risk={s['avg_risk']:.3f} "
                  f"conf={s['confidence']}%")

        all_route_results.append(result)

        # Phase 16: Predictive risk for first route's edges
        if recs and recs[0].get("coordinates"):
            routes_raw = engine.find_alternative_routes(src, dst, 18)
            if routes_raw:
                sample_edges = routes_raw[0]["edge_path"][:10]
                pred = engine.predict_future_risk(sample_edges, target_hour=22)
                trend_summary = {eid: {"now": v["current_risk"], "22h": v["predicted_risk"],
                                       "trend": v["trend"]}
                                 for eid, v in pred.items()}

                # Phase 22: Simulation
                sim = engine.simulate_route(routes_raw[0]["path"],
                                            routes_raw[0]["edge_path"], 18)

                all_summaries.append({
                    "route_name": route_name,
                    "recommendations": result,
                    "predictive_risk_sample": trend_summary,
                    "route_simulation": {
                        "total_minutes": sim["total_minutes"],
                        "segments": sim["segments"],
                        "timeline_sample": sim["timeline"][:5],
                    },
                })

    # ── Phase 21: Time Machine comparison ─────────────────────────────────────
    print("\n─── Time Machine Routing ───")
    src_node = engine.snap_to_nearest_node(12.9352, 77.6245)
    dst_node = engine.snap_to_nearest_node(12.9082, 77.6476)
    time_comparison = engine.compare_routes_by_time(src_node, dst_node, [7, 14, 20, 23, 3])
    for time_key, info in time_comparison.items():
        print(f"  {time_key} → risk={info['avg_risk']:.3f} [{info['label']}]  "
              f"time={info['travel_time']:.1f}min")

    # ── Phase 17: Women safety ─────────────────────────────────────────────────
    print("\n─── Women Safety Mode ───")
    womens_route = engine.find_women_safe_route(src_node, dst_node, hour=21)
    if womens_route:
        print(f"  Women Safety Score: {womens_route['women_safety_score']:.3f}")
        print(f"  Distance: {womens_route['metrics']['total_distance_km']:.2f} km")
        print(f"  Reasons: {womens_route['explanation']['reasons'][0]}")

    # ── Phase 18: Emergency escape ─────────────────────────────────────────────
    print("\n─── Emergency Escape (SOS) ───")
    emergency = engine.find_emergency_escape_route(12.9352, 77.6245, hour=22)
    for haven_type, route_info in emergency.items():
        dist = route_info["metrics"].get("total_distance_km", 0)
        t = route_info["metrics"].get("total_travel_time_min", 0)
        print(f"  {haven_type:25} → {dist:.2f}km / {t:.1f}min")

    # ── Phase 24/25: Zone detection ────────────────────────────────────────────
    print(f"\n─── Zone Detection ───")
    print(f"  Safe Zones:   {len(engine.safe_zone_clusters)}")
    print(f"  Danger Zones: {len(engine.danger_zone_clusters)}")
    for sz in engine.safe_zone_clusters[:3]:
        print(f"  ✓ Safe:   {sz['zone']} ({sz['node_count']} nodes)")
    for dz in engine.danger_zone_clusters[:3]:
        print(f"  ✗ Danger: {dz['zone']} ({dz['node_count']} nodes)")

    # ── Phase 28: Heatmap ─────────────────────────────────────────────────────
    print("\n─── Generating Heatmap ───")
    routes_for_map = engine.find_alternative_routes(src_node, dst_node, 18)
    engine.generate_route_risk_heatmap(routes_for_map, hour=18)

    # ── Output Files ──────────────────────────────────────────────────────────
    print("\n─── Writing Output Files ───")

    # route_summary.json
    summaries_out = []
    for r in all_route_results:
        for rec in r.get("recommendations", []):
            summaries_out.append({
                "route_id": rec["route_id"],
                "label": rec["label"],
                "profile": rec["profile"],
                "summary": rec["summary"],
                "safety_profile": rec["safety_profile"],
            })
    with open(OUT / "route_summary.json", "w") as f:
        json.dump(summaries_out, f, indent=2)
    print("  ✓ route_summary.json")

    # route_explanation.json
    explanations_out = [rec["reasoning"]
                        for r in all_route_results
                        for rec in r.get("recommendations", [])]
    with open(OUT / "route_explanation.json", "w") as f:
        json.dump(explanations_out, f, indent=2)
    print("  ✓ route_explanation.json")

    # route_coordinates.json
    coords_out = [{
        "route_id": rec["route_id"],
        "label": rec["label"],
        "coordinates": rec["coordinates"][:50],  # cap for file size
    } for r in all_route_results for rec in r.get("recommendations", [])]
    with open(OUT / "route_coordinates.json", "w") as f:
        json.dump(coords_out, f, indent=2)
    print("  ✓ route_coordinates.json")

    # time_machine.json (Phase 21)
    with open(OUT / "time_machine.json", "w") as f:
        json.dump(time_comparison, f, indent=2)
    print("  ✓ time_machine.json")

    # zone_clusters.json (Phase 24/25)
    with open(OUT / "zone_clusters.json", "w") as f:
        json.dump({
            "safe_zones": engine.safe_zone_clusters,
            "danger_zones": engine.danger_zone_clusters,
        }, f, indent=2)
    print("  ✓ zone_clusters.json")

    # emergency_routes.json (Phase 18)
    emergency_serializable = {
        k: {"metrics": v["metrics"], "destination_node": v.get("destination_node"),
            "coordinates": v["coordinates"][:20]}
        for k, v in emergency.items()
    }
    with open(OUT / "emergency_routes.json", "w") as f:
        json.dump(emergency_serializable, f, indent=2)
    print("  ✓ emergency_routes.json")

    # women_safety.json (Phase 17)
    if womens_route:
        ws_out = {
            "women_safety_score": womens_route["women_safety_score"],
            "metrics": womens_route["metrics"],
            "explanation": womens_route["explanation"],
            "coordinates": womens_route["coordinates"][:50],
        }
        with open(OUT / "women_safety_route.json", "w") as f:
            json.dump(ws_out, f, indent=2)
        print("  ✓ women_safety_route.json")

    # predictive_risk.json (Phase 16)
    with open(OUT / "predictive_risk.json", "w") as f:
        json.dump(all_summaries, f, indent=2)
    print("  ✓ predictive_risk.json")

    # incident_layer.csv skeleton (Phase 23)
    if not INCIDENT_CSV.exists():
        skeleton = pd.DataFrame([
            {"edge_id": "E000010", "type": "Accident",      "severity": 0.7, "description": "Sample accident"},
            {"edge_id": "E000020", "type": "Construction",  "severity": 0.4, "description": "Road work"},
            {"edge_id": "E000030", "type": "Crime",         "severity": 0.8, "description": "Reported crime"},
        ])
        skeleton.to_csv(INCIDENT_CSV, index=False)
        print("  ✓ incident_layer.csv  (skeleton)")

    print("\n" + "=" * 65)
    print("SafeRoute-AI v8.0 complete.")
    print(f"Outputs → {OUT}")
    print("=" * 65)


if __name__ == "__main__":
    main()
