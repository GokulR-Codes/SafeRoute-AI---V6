"""
test_routes.py — End-to-end route testing with MongoDB-backed data.
Tests the A* router, graph construction, and cross-area routing.

Run:  python test_routes.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix Windows console encoding
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ENGINE.astar_router import SafeRouteGraph


def print_route(result, start, goal):
    """Pretty-print a route result."""
    if result is None:
        print(f"    NO PATH from {start} -> {goal}")
        return

    path_str = " -> ".join(result["path"])
    print(f"    Route : {path_str}")
    print(f"    Risk  : {result['total_risk']:.3f} total | {result['mean_risk']:.3f} avg | Band: {result['risk_band']}")
    print(f"    Hops  : {result['segments']} segments")

    if result["edges"]:
        print(f"    Roads :")
        for i, e in enumerate(result["edges"], 1):
            road = e.get("road_name", "unnamed") or "unnamed road"
            rtype = e.get("road_type", "?")
            risk = e.get("risk", 0)
            print(f"      {i}. {road} ({rtype}) — risk: {risk:.3f}")


def main():
    print("=" * 65)
    print("  SafeRoute-AI — End-to-End Route Testing (MongoDB)")
    print("=" * 65)

    # Build graph from MongoDB (no CSV paths needed)
    print("\n[1] Building graph from MongoDB...")
    graph = SafeRouteGraph(use_db=True)
    print(f"    Nodes : {len(graph.nodes)}")
    print(f"    Edges : {graph.edge_count}")
    print(f"    Areas : {', '.join(sorted(graph.nodes))}")

    # Reachability check
    print("\n[2] Reachability check...")
    components = graph.connected_components()
    print(f"    Connected components: {len(components)}")
    for i, comp in enumerate(components):
        print(f"    Component {i+1}: {', '.join(comp)} ({len(comp)} areas)")

    # Test routes
    test_routes = [
        ("Indiranagar", "Koramangala"),
        ("BTM Layout", "Mahadevapura"),
        ("HSR Layout", "Silk Board"),
        ("Koramangala", "BTM Layout"),
        ("Silk Board", "Indiranagar"),
        ("Mahadevapura", "HSR Layout"),
    ]

    print(f"\n[3] Testing {len(test_routes)} routes...")
    print("-" * 65)

    passed = 0
    for start, goal in test_routes:
        print(f"\n  >> {start} -> {goal}")
        try:
            result = graph.find_safest_path(start, goal)
            if result is not None:
                print_route(result, start, goal)
                passed += 1
            else:
                print(f"    !! No path found (graph may be disconnected)")
        except Exception as e:
            print(f"    !! ERROR: {e}")

    # Summary
    print("\n" + "=" * 65)
    print(f"  RESULTS: {passed}/{len(test_routes)} routes found successfully")

    if passed == len(test_routes):
        print("  STATUS : ALL ROUTES WORKING ✔")
    elif passed > 0:
        print("  STATUS : PARTIAL (some routes missing)")
    else:
        print("  STATUS : FAILED (no routes working)")

    print("=" * 65)


if __name__ == "__main__":
    main()
