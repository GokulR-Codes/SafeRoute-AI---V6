"""
Engine output validator for the SafeRoute Temporal Risk Graph Engine.

Checks structural integrity, value ranges, and consistency across the
graph, risk tensor, and edge DataFrame produced by a single engine run.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx
import numpy as np
import pandas as pd

log = logging.getLogger("SafeRoute.Validator")

HOURS = list(range(24))

REQUIRED_EDGE_DF_COLS = [
    "edge_id", "u", "v", "zone", "road_name",
    "zone_type", "static_component", "graph_component",
]

REQUIRED_OUTPUT_FILES = [
    "graph_nodes.csv",
    "graph_edges.csv",
    "hourly_edge_weights.csv",
    "risk_tensor.pkl",
    "temporal_graph.pkl",
    "zone_hourly_risk.csv",
    "city_hourly_profile.csv",
]


class EngineValidator:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)

    def run(
        self,
        G: nx.DiGraph,
        risk_tensor: Dict[str, np.ndarray],
        edge_df: pd.DataFrame,
    ) -> Tuple[str, bool]:
        checks: List[Tuple[str, bool, str]] = []

        checks += self._check_graph(G)
        checks += self._check_tensor(risk_tensor)
        checks += self._check_edge_df(edge_df)
        checks += self._check_consistency(G, risk_tensor, edge_df)
        checks += self._check_outputs()

        passed = all(ok for _, ok, _ in checks)
        report = self._format_report(checks, passed)

        n_pass = sum(1 for _, ok, _ in checks if ok)
        n_fail = len(checks) - n_pass
        log.info(f"Validation: {n_pass} passed, {n_fail} failed — {'PASS' if passed else 'FAIL'}")
        return report, passed

    def _check_graph(self, G: nx.DiGraph) -> List[Tuple[str, bool, str]]:
        results = []

        results.append((
            "Graph is non-empty",
            G.number_of_nodes() > 0 and G.number_of_edges() > 0,
            f"{G.number_of_nodes()} nodes, {G.number_of_edges()} edges",
        ))

        missing_coords = 0
        for n, data in G.nodes(data=True):
            if "lat" not in data or "lng" not in data:
                missing_coords += 1
        results.append((
            "All nodes have lat/lng",
            missing_coords == 0,
            f"{missing_coords} nodes missing coordinates" if missing_coords else "OK",
        ))

        missing_profile = 0
        for u, v, data in G.edges(data=True):
            if "risk_profile" not in data:
                missing_profile += 1
        results.append((
            "All edges have risk_profile",
            missing_profile == 0,
            f"{missing_profile} edges missing risk_profile" if missing_profile else "OK",
        ))

        return results

    def _check_tensor(self, risk_tensor: Dict[str, np.ndarray]) -> List[Tuple[str, bool, str]]:
        results = []

        results.append((
            "Risk tensor is non-empty",
            len(risk_tensor) > 0,
            f"{len(risk_tensor)} edges in tensor",
        ))

        bad_shape = 0
        out_of_range = 0
        has_nan = 0
        for eid, arr in risk_tensor.items():
            if arr.shape != (24,):
                bad_shape += 1
            if np.any(np.isnan(arr)):
                has_nan += 1
            if np.any(arr < 0) or np.any(arr > 100):
                out_of_range += 1

        results.append((
            "Tensor arrays have shape (24,)",
            bad_shape == 0,
            f"{bad_shape} edges with wrong shape" if bad_shape else "OK",
        ))
        results.append((
            "No NaN values in tensor",
            has_nan == 0,
            f"{has_nan} edges contain NaN" if has_nan else "OK",
        ))
        results.append((
            "Risk values in [0, 100]",
            out_of_range == 0,
            f"{out_of_range} edges out of range" if out_of_range else "OK",
        ))

        all_vals = np.concatenate(list(risk_tensor.values()))
        results.append((
            "Risk values are not all identical",
            np.std(all_vals) > 0.01,
            f"std={np.std(all_vals):.4f}, mean={np.mean(all_vals):.2f}",
        ))

        return results

    def _check_edge_df(self, edge_df: pd.DataFrame) -> List[Tuple[str, bool, str]]:
        results = []

        missing = [c for c in REQUIRED_EDGE_DF_COLS if c not in edge_df.columns]
        results.append((
            "Edge DataFrame has required columns",
            len(missing) == 0,
            f"missing: {missing}" if missing else "OK",
        ))

        dup_count = edge_df["edge_id"].duplicated().sum() if "edge_id" in edge_df.columns else 0
        results.append((
            "No duplicate edge_ids",
            dup_count == 0,
            f"{dup_count} duplicates" if dup_count else "OK",
        ))

        return results

    def _check_consistency(
        self,
        G: nx.DiGraph,
        risk_tensor: Dict[str, np.ndarray],
        edge_df: pd.DataFrame,
    ) -> List[Tuple[str, bool, str]]:
        results = []

        tensor_ids = set(risk_tensor.keys())
        df_ids = set(edge_df["edge_id"]) if "edge_id" in edge_df.columns else set()

        results.append((
            "Tensor edge_ids match DataFrame edge_ids",
            tensor_ids == df_ids,
            f"tensor_only={len(tensor_ids - df_ids)}, df_only={len(df_ids - tensor_ids)}"
            if tensor_ids != df_ids else "OK",
        ))

        graph_edges = G.number_of_edges()
        tensor_edges = len(risk_tensor)
        ratio = tensor_edges / graph_edges if graph_edges else 0
        results.append((
            "Tensor covers >90% of graph edges",
            ratio > 0.9,
            f"{tensor_edges}/{graph_edges} ({ratio:.1%})",
        ))

        mismatch = 0
        sample_checked = 0
        for u, v, data in G.edges(data=True):
            eid = data.get("edge_id")
            profile = data.get("risk_profile", {})
            if eid and eid in risk_tensor and profile:
                sample_checked += 1
                arr = risk_tensor[eid]
                if abs(profile.get(0, -1) - float(arr[0])) > 0.01:
                    mismatch += 1
                if sample_checked >= 1000:
                    break
        results.append((
            "Graph risk_profile matches tensor (sampled)",
            mismatch == 0,
            f"{mismatch}/{sample_checked} mismatched" if mismatch else f"OK ({sample_checked} checked)",
        ))

        return results

    def _check_outputs(self) -> List[Tuple[str, bool, str]]:
        results = []
        for fname in REQUIRED_OUTPUT_FILES:
            path = self.output_dir / fname
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            results.append((
                f"Output exists: {fname}",
                exists and size > 0,
                f"{size:,} bytes" if exists else "NOT FOUND",
            ))
        return results

    @staticmethod
    def _format_report(checks: List[Tuple[str, bool, str]], passed: bool) -> str:
        lines = [
            "=" * 60,
            "SafeRoute Engine — Validation Report",
            "=" * 60,
            "",
        ]
        for name, ok, detail in checks:
            icon = "PASS" if ok else "FAIL"
            lines.append(f"  [{icon}] {name}")
            lines.append(f"         {detail}")
        lines.append("")
        lines.append("=" * 60)
        lines.append(f"Result: {'ALL CHECKS PASSED' if passed else 'SOME CHECKS FAILED'}")
        lines.append("=" * 60)
        return "\n".join(lines)
