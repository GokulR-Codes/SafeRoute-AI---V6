"""
SafeRoute-AI v6.0  |  A* Safe Route Finder
============================================================================
Builds a directed graph from road segment CSVs and finds the path with the
lowest cumulative risk between two areas using the A* search algorithm.

Usage (standalone):
    python astar_router.py

Usage (as module):
    from astar_router import load_graph_from_datasets, print_route
    graph = load_graph_from_datasets("datasets/")
    result = graph.find_safest_path("Hebbal", "Koramangala")
    print_route(result)

Graph construction:
    Nodes  - unique area names from source_area / destination_area columns
    Edges  - road segments; weight = road_risk_score (0-100, lower = safer)
    Coords - centroid of lat/lng values per area (used for heuristic)

A* cost model:
    g(n)   - cumulative road_risk_score along the path so far
    h(n)   - admissible lower bound: min_edge_risk * estimated remaining hops
             (estimated hops = haversine distance / avg segment distance)
    f(n)   = g(n) + h(n)
============================================================================
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ==============================================================================
# HAVERSINE DISTANCE
# ==============================================================================

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance in metres between two (lat, lng) points."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2.0 * R * math.asin(math.sqrt(max(a, 0.0)))


# ==============================================================================
# GRAPH
# ==============================================================================

class SafeRouteGraph:
    """
    Directed weighted graph of Bangalore road segments.

    Builds from one or more *_risk.csv files (raw data or engine output).
    Multiple segments sharing the same source->destination pair are collapsed
    to the single lowest-risk edge so the graph is a simple directed graph.
    """

    def __init__(self, csv_paths: List[str], risk_column: str = "road_risk_score"):
        self.risk_column = risk_column
        self._build(csv_paths)

    # -- construction ----------------------------------------------------------

    def _build(self, csv_paths: List[str]) -> None:
        frames = []
        for p in csv_paths:
            df = pd.read_csv(p, low_memory=False)
            if self.risk_column not in df.columns:
                raise ValueError(f"Column '{self.risk_column}' not found in {p}")
            frames.append(df)

        data = pd.concat(frames, ignore_index=True)

        required = {"source_area", "destination_area", "lat", "lng", self.risk_column}
        missing = required - set(data.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        data = data.dropna(subset=["source_area", "destination_area", self.risk_column])
        data["source_area"] = data["source_area"].astype(str).str.strip()
        data["destination_area"] = data["destination_area"].astype(str).str.strip()

        # -- node coordinates: centroid of all segment lats/lngs per area ------
        src_coords = (
            data.groupby("source_area")[["lat", "lng"]]
            .mean()
            .rename_axis("area")
        )
        dst_only = data[~data["destination_area"].isin(src_coords.index)]
        dst_coords = (
            dst_only.groupby("destination_area")[["lat", "lng"]]
            .mean()
            .rename_axis("area")
        )
        all_coords = pd.concat([src_coords, dst_coords])
        all_coords = all_coords[~all_coords.index.duplicated(keep="first")]
        self.node_coords: Dict[str, Tuple[float, float]] = {
            area: (float(row["lat"]), float(row["lng"]))
            for area, row in all_coords.iterrows()
        }

        # -- edges: keep minimum-risk segment per source->destination pair ------
        idx_min = (
            data.groupby(["source_area", "destination_area"])[self.risk_column]
            .idxmin()
        )
        best = data.loc[idx_min.values].copy()

        self.adj: Dict[str, List[Dict]] = defaultdict(list)
        for _, row in best.iterrows():
            src = row["source_area"]
            dst = row["destination_area"]
            if src == dst:
                continue
            self.adj[src].append({
                "destination": dst,
                "risk":        float(row[self.risk_column]),
                "road_name":   str(row.get("road_name", "")),
                "zone":        str(row.get("zone", "")),
                "road_type":   str(row.get("road_type", "")),
                "lat":         float(row["lat"]),
                "lng":         float(row["lng"]),
            })

        # -- heuristic calibration stats ---------------------------------------
        all_risks = best[self.risk_column].values
        self._min_risk: float = float(all_risks.min()) if len(all_risks) else 0.0

        dists = []
        for _, row in best.iterrows():
            src, dst = row["source_area"], row["destination_area"]
            if src in self.node_coords and dst in self.node_coords:
                lat1, lon1 = self.node_coords[src]
                lat2, lon2 = self.node_coords[dst]
                d = haversine_m(lat1, lon1, lat2, lon2)
                if d > 10.0:
                    dists.append(d)
        self._avg_dist: float = float(np.mean(dists)) if dists else 500.0

    # -- properties ------------------------------------------------------------

    @property
    def nodes(self) -> List[str]:
        return list(self.node_coords.keys())

    @property
    def edge_count(self) -> int:
        return sum(len(v) for v in self.adj.values())

    # -- heuristic -------------------------------------------------------------

    def _heuristic(self, node: str, goal: str) -> float:
        """
        Admissible lower bound on remaining risk.

        h(n) = min_edge_risk × ceil(haversine(n, goal) / avg_segment_dist)

        Since the actual path must traverse at least that many segments, and
        each segment costs at least min_edge_risk, this never overestimates.
        """
        if node == goal:
            return 0.0
        if node not in self.node_coords or goal not in self.node_coords:
            return 0.0
        lat1, lon1 = self.node_coords[node]
        lat2, lon2 = self.node_coords[goal]
        dist = haversine_m(lat1, lon1, lat2, lon2)
        estimated_hops = math.ceil(dist / self._avg_dist)
        return self._min_risk * estimated_hops

    # -- A* search -------------------------------------------------------------

    def find_safest_path(self, start: str, goal: str) -> Optional[Dict]:
        """
        A* search for the minimum cumulative-risk path from start to goal.

        Parameters
        ----------
        start : source area name (must exist in graph nodes)
        goal  : destination area name (must exist in graph nodes)

        Returns
        -------
        dict with keys:
            path       - ordered list of area names [start, ..., goal]
            edges      - list of edge dicts for each traversed segment
            total_risk - sum of road_risk_score along the path
            mean_risk  - average risk per segment
            segments   - number of segments
            risk_band  - Low / Moderate / High / Critical
        Returns None if no path exists between start and goal.
        """
        if start not in self.node_coords:
            raise KeyError(f"Start area not found: '{start}'")
        if goal not in self.node_coords:
            raise KeyError(f"Goal area not found: '{goal}'")
        if start == goal:
            return {
                "path": [start],
                "edges": [],
                "total_risk": 0.0,
                "mean_risk": 0.0,
                "segments": 0,
                "risk_band": "Low",
            }

        # heap: (f_score, tie_breaker, g_score, node, path, edge_list)
        counter = 0
        heap: list = [(self._heuristic(start, goal), counter, 0.0, start, [start], [])]
        best_g: Dict[str, float] = {}

        while heap:
            f, _, g, node, path, edge_list = heapq.heappop(heap)

            if node == goal:
                mean = g / max(len(edge_list), 1)
                return {
                    "path":       path,
                    "edges":      edge_list,
                    "total_risk": round(g, 2),
                    "mean_risk":  round(mean, 2),
                    "segments":   len(edge_list),
                    "risk_band":  _risk_band(mean),
                }

            if node in best_g and best_g[node] <= g:
                continue
            best_g[node] = g

            for edge in self.adj.get(node, []):
                nbr = edge["destination"]
                new_g = g + edge["risk"]
                if nbr in best_g and best_g[nbr] <= new_g:
                    continue
                h = self._heuristic(nbr, goal)
                counter += 1
                heapq.heappush(heap, (
                    new_g + h,
                    counter,
                    new_g,
                    nbr,
                    path + [nbr],
                    edge_list + [edge],
                ))

        return None  # no path found

    # -- reachability helpers --------------------------------------------------

    def reachable_from(self, start: str) -> List[str]:
        """Return all area names reachable from start via BFS."""
        if start not in self.node_coords:
            raise KeyError(f"Area not found: '{start}'")
        visited: set = set()
        queue = [start]
        while queue:
            node = queue.pop()
            if node in visited:
                continue
            visited.add(node)
            for edge in self.adj.get(node, []):
                if edge["destination"] not in visited:
                    queue.append(edge["destination"])
        visited.discard(start)
        return sorted(visited)

    def connected_components(self) -> List[List[str]]:
        """Return all connected components as lists of area names, largest first."""
        from collections import deque
        all_nodes = set(self.adj.keys())
        for edges in self.adj.values():
            for e in edges:
                all_nodes.add(e["destination"])
        seen: set = set()
        components: List[List[str]] = []
        for start in all_nodes:
            if start in seen:
                continue
            comp: set = set()
            q: deque = deque([start])
            while q:
                n = q.popleft()
                if n in comp:
                    continue
                comp.add(n)
                for edge in self.adj.get(n, []):
                    if edge["destination"] not in comp:
                        q.append(edge["destination"])
            seen |= comp
            components.append(sorted(comp))
        components.sort(key=len, reverse=True)
        return components

    # -- multi-path comparison -------------------------------------------------

    def compare_routes(
        self, start: str, goal: str, alternatives: int = 3
    ) -> List[Dict]:
        """
        Find up to `alternatives` distinct routes and return them ranked by
        total risk (lowest first). Uses repeated A* with temporary edge removal
        to force path diversity (Yen's K-shortest paths approach on risk cost).
        """
        found: List[Dict] = []
        blocked: set = set()

        for _ in range(alternatives):
            # Temporarily remove edges used by already-found paths
            saved: Dict[str, List] = {}
            for key in blocked:
                src, dst = key
                if src in self.adj:
                    saved[key] = [e for e in self.adj[src] if e["destination"] == dst]
                    self.adj[src] = [e for e in self.adj[src] if e["destination"] != dst]

            result = self.find_safest_path(start, goal)

            # Restore removed edges
            for key, edges in saved.items():
                src, _ = key
                self.adj[src].extend(edges)

            if result is None:
                break

            found.append(result)
            # Block the highest-risk edge in this path for next iteration
            if result["edges"]:
                worst = max(result["edges"], key=lambda e: e["risk"])
                src_node = result["path"][result["edges"].index(worst)]
                blocked.add((src_node, worst["destination"]))

        return found


# ==============================================================================
# RISK BAND
# ==============================================================================

def _risk_band(mean_risk: float) -> str:
    if mean_risk < 25:   return "Low"
    elif mean_risk < 45: return "Moderate"
    elif mean_risk < 65: return "High"
    else:                return "Critical"


# ==============================================================================
# LOADERS
# ==============================================================================

def load_graph_from_datasets(datasets_dir: str) -> SafeRouteGraph:
    """Load all *_risk.csv zone files from the ENGINE/datasets/ folder."""
    d = Path(datasets_dir)
    csvs = sorted(d.glob("*_risk.csv"))
    if not csvs:
        raise FileNotFoundError(f"No *_risk.csv files found in: {datasets_dir}")
    return SafeRouteGraph([str(p) for p in csvs])


def load_graph_from_engine_output(output_csv: str) -> SafeRouteGraph:
    """Load from the engine's saferoute_v6_risk_scores.csv output file."""
    return SafeRouteGraph([output_csv])


# ==============================================================================
# RESULT PRINTER
# ==============================================================================

def print_route(result: Optional[Dict], label: str = "") -> None:
    """Pretty-print a route result dict."""
    bar = "-" * 58
    if result is None:
        print(f"\n{bar}")
        print("  No path found between the specified areas.")
        print(f"{bar}\n")
        return

    title = f"  A* SAFEST ROUTE{' -- ' + label if label else ''}"
    print(f"\n{bar}")
    print(title)
    print(bar)
    print(f"  Risk Band    : {result['risk_band']}")
    print(f"  Total Risk   : {result['total_risk']:.1f}")
    print(f"  Mean / Seg   : {result['mean_risk']:.1f}")
    print(f"  Segments     : {result['segments']}")
    print(f"\n  PATH  ({len(result['path'])} nodes):")
    for i, area in enumerate(result["path"]):
        if i == 0:
            tag = "  START ->"
        elif i == len(result["path"]) - 1:
            tag = "  GOAL  : "
        else:
            tag = f"  [{i:>2}]    "
        print(f"{tag} {area}")
    if result["edges"]:
        print(f"\n  {'#':<4} {'Road Name':<32} {'Zone':<18} {'Type':<12} {'Risk':>6}")
        print(f"  {'-'*4} {'-'*32} {'-'*18} {'-'*12} {'-'*6}")
        for i, e in enumerate(result["edges"], 1):
            road = e.get("road_name", "-")[:32]
            zone = e.get("zone", "-")[:18]
            rtype = e.get("road_type", "-")[:12]
            print(f"  {i:<4} {road:<32} {zone:<18} {rtype:<12} {e['risk']:>6.1f}")
    print(f"{bar}\n")


# ==============================================================================
# DEMO  (python astar_router.py)
# ==============================================================================

if __name__ == "__main__":
    datasets_dir = Path(__file__).parent / "datasets"

    print("\n" + "=" * 58)
    print("         SafeRoute-AI v6.0  |  A* Router Demo")
    print("=" * 58)

    print(f"\nLoading datasets from: {datasets_dir}")
    graph = load_graph_from_datasets(str(datasets_dir))

    print(f"Graph ready  -  {len(graph.nodes)} nodes,  {graph.edge_count} edges")
    print(f"Min edge risk: {graph._min_risk:.2f}   Avg segment dist: {graph._avg_dist:.0f} m")

    # Show connected components
    components = graph.connected_components()
    print(f"\nConnected components: {len(components)}")
    print(f"Largest component ({len(components[0])} areas):")
    for n in components[0]:
        lat, lng = graph.node_coords[n]
        print(f"  * {n:<40} ({lat:.4f}, {lng:.4f})")

    # -- Demo query: find a start node with the most reachable destinations ----
    print("\nFinding best demo start (most reachable destinations)...")
    best_start, best_reachable = "", []
    for candidate in sorted(graph.adj.keys()):
        r = graph.reachable_from(candidate)
        if len(r) > len(best_reachable):
            best_start, best_reachable = candidate, r

    if best_reachable:
        start_area = best_start
        goal_area  = best_reachable[-1]  # farthest alphabetically

        print(f"\n  Best start  : '{start_area}'  ({len(best_reachable)} reachable areas)")
        print(f"  Destinations: {', '.join(best_reachable[:8])}{'...' if len(best_reachable) > 8 else ''}")

        print(f"\nQuery: '{start_area}'  ->  '{goal_area}'")
        result = graph.find_safest_path(start_area, goal_area)
        print_route(result, label=f"{start_area} -> {goal_area}")

        # Show all reachable areas from the best start
        print(f"All areas reachable from '{start_area}':")
        for r in best_reachable:
            print(f"  * {r}")
    else:
        print("\nNo routable inter-area paths found in the dataset.")
