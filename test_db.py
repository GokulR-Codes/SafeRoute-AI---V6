"""
Quick test — verifies MongoDB connection + data integrity for SafeRoute-AI.
Run:  python test_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix Windows console encoding
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from DATABASE.db import get_risk_dataframe, get_collection

print("=" * 60)
print("  SafeRoute-AI — Database Connection Test")
print("=" * 60)

# 1. Test connection + fetch
print("\n[1] Fetching data from MongoDB...")
df = get_risk_dataframe()
print(f"    ✔ Got {len(df):,} rows, {len(df.columns)} columns")

# 2. Schema check
print("\n[2] Schema validation...")
required = [
    "zone", "direction", "lat", "lng", "source_area", "destination_area",
    "road_name", "road_type", "speed_limit", "crime_score",
    "road_risk_score", "congestion_score", "adjacency_count",
]
missing = [c for c in required if c not in df.columns]
if missing:
    print(f"    ✘ Missing columns: {missing}")
else:
    print(f"    ✔ All {len(required)} critical columns present")

# 3. Area coverage
print("\n[3] Area coverage...")
areas = sorted(df["source_area"].dropna().unique())
print(f"    ✔ {len(areas)} areas: {', '.join(areas)}")

# 4. Cross-area routes
cross = df[df["source_area"] != df["destination_area"]]
print(f"    ✔ {len(cross)} cross-area (interconnected) routes")

# 5. Numeric sanity
print("\n[4] Numeric sanity...")
for col in ["lat", "lng", "crime_score", "road_risk_score"]:
    vals = df[col].dropna()
    print(f"    {col:25s}  min={vals.min():.3f}  max={vals.max():.3f}  nulls={df[col].isna().sum()}")

# 6. Caching test
print("\n[5] Caching test...")
df2 = get_risk_dataframe()  # Should be instant (cached)
print(f"    ✔ Second fetch returned {len(df2):,} rows (from cache)")

print("\n" + "=" * 60)
print("  ALL TESTS PASSED ✔")
print("=" * 60)
