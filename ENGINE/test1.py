
"""
SafeRoute-AI v6.0
RUN FILE / EXECUTION SCRIPT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Compatible with:
    safe_route_engine_v6.py

Project Structure:
------------------

SafeRoute-AI/
│
├── safe_route_engine_v6.py
├── test.py
│
├── datasets/
│   ├── airport_peripheral_risk.csv
│   ├── central_bangalore_risk.csv
│   ├── east_bangalore_risk.csv
│   ├── logistics_hightraffic_risk.csv
│   ├── north_bangalore_risk.csv
│   ├── south_bangalore_risk.csv
│   ├── southeast_it_corridor_risk.csv
│   └── west_bangalore_risk.csv
│
└── outputs/

Run Command:
-------------
python test.py
"""

from pathlib import Path
import traceback
import sys

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IMPORT ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

try:
    from safe_route_engine_v6 import main

except ImportError as e:

    print("\n❌ ENGINE IMPORT FAILED")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print("\nPossible Reasons:")
    print("1. Engine filename is incorrect")
    print("2. File not in same folder")
    print("3. Python environment issue")

    print("\nExpected engine file:")
    print("   safe_route_engine_v6.py")

    print("\nOriginal Error:")
    print(e)

    sys.exit(1)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PROJECT PATHS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BASE_DIR = Path(__file__).parent.resolve()

DATASET_DIR = BASE_DIR / "datasets"
OUTPUT_DIR = BASE_DIR / "outputs"

# Auto-create output directory
OUTPUT_DIR.mkdir(exist_ok=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REQUIRED DATASETS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REQUIRED_DATASETS = [

    "airport_peripheral_risk.csv",
    "central_bangalore_risk.csv",
    "east_bangalore_risk.csv",
    "logistics_hightraffic_risk.csv",
    "north_bangalore_risk.csv",
    "south_bangalore_risk.csv",
    "southeast_it_corridor_risk.csv",
    "west_bangalore_risk.csv",
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATASET VALIDATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("          SafeRoute-AI v6.0")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

print("\n📂 Checking datasets...\n")

missing_files = []

for file in REQUIRED_DATASETS:

    file_path = DATASET_DIR / file

    if file_path.exists():

        print(f"✅ Found Dataset : {file}")

    else:

        print(f"❌ Missing Dataset : {file}")
        missing_files.append(file)

# Stop if any files missing
if missing_files:

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("❌ DATASET VALIDATION FAILED")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print("\nMissing Files:\n")

    for m in missing_files:
        print(f"   • {m}")

    print("\nPlace all CSV files inside:")
    print(f"   {DATASET_DIR}")

    sys.exit(1)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ENGINE SETTINGS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Simulation Hour
# 0–23
# Example:
# 08 = morning
# 18 = evening
# 22 = late night

SIMULATION_HOUR = 22

# Available Scenarios:
#
# baseline
# heavy_rain
# diwali_night
# strike_hartal
# it_peak_weekday

SCENARIO = "baseline"

# Processing chunk size
CHUNK_SIZE = 100000

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# START EXECUTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n🚀 STARTING SAFEROUTE-AI ENGINE")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

print(f"\n🕒 Simulation Hour : {SIMULATION_HOUR}:00")
print(f"🌦 Scenario         : {SCENARIO}")
print(f"📂 Dataset Folder   : {DATASET_DIR}")
print(f"📁 Output Folder    : {OUTPUT_DIR}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXECUTE ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

try:

    main(
        data_dir=str(DATASET_DIR),
        output_dir=str(OUTPUT_DIR),
        hour=SIMULATION_HOUR,
        chunk_size=CHUNK_SIZE,
        scenario=SCENARIO,
    )

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ EXECUTION COMPLETED SUCCESSFULLY")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print("\n📁 OUTPUT FILES GENERATED:\n")

    generated_outputs = [

        "saferoute_v6_risk_scores.csv",
        "saferoute_v6_zone_summary.csv",
        "saferoute_v6_top_risk_segments.csv",
        "saferoute_v6_hourly_sweep.csv",
        "saferoute_v6_factor_contributions.csv",
        "saferoute_v6_heatmap_confident.csv",
        "saferoute_v6_correlation_validation.csv",
    ]

    for output in generated_outputs:

        output_path = OUTPUT_DIR / output

        if output_path.exists():
            print(f"   ✔ {output}")
        else:
            print(f"   ⚠ Missing Expected Output : {output}")

    print("\n🎯 SafeRoute-AI analysis completed successfully.")

except Exception as e:

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("❌ EXECUTION FAILED")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    print("\nERROR:")
    print(e)

    print("\nFULL TRACEBACK:\n")
    traceback.print_exc()

    sys.exit(1)
