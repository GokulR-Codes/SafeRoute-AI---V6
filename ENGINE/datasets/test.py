import pandas as pd
import numpy as np
import glob
import os
from scipy.stats import pearsonr
from scipy.stats import entropy
from sklearn.ensemble import IsolationForest

# =========================================================
# DATA FOLDER
# =========================================================

folder_path = r"D:\Project\SafeRoute Ai Test\data"

csv_files = glob.glob(os.path.join(folder_path, "*.csv"))

print("\n===================================================")
print("SAFE ROUTE AI - DATA LEGITIMACY ANALYZER")
print("===================================================")

# =========================================================
# METRIC EXPECTATIONS
# =========================================================

expected_positive_correlations = [

    ("crime_score", "road_risk_score"),
    ("isolated_area_score", "road_risk_score"),
    ("congestion_score", "travel_time_estimate"),
    ("commercial_density", "activity_score"),
    ("nightlife_density", "activity_score")

]

expected_negative_correlations = [

    ("lighting_score", "road_risk_score"),
    ("cctv_density_estimate", "crime_score"),
    ("hospital_density", "travel_time_estimate")

]

# =========================================================
# ANALYZE EACH FILE
# =========================================================

for file in csv_files:

    print("\n===================================================")
    print(f"ANALYZING : {os.path.basename(file)}")
    print("===================================================")

    try:

        df = pd.read_csv(file)

        numeric_df = df.select_dtypes(include=np.number)

        # =================================================
        # 1. RANDOMNESS TEST
        # =================================================

        print("\n[1] RANDOMNESS ANALYSIS")

        for col in numeric_df.columns:

            unique_ratio = len(df[col].unique()) / len(df)

            if unique_ratio < 0.01:
                print(f"⚠ {col} may be repetitive/artificial")

            elif unique_ratio > 0.95:
                print(f"⚠ {col} may be overly random/generated")

        # =================================================
        # 2. DISTRIBUTION LEGITIMACY
        # =================================================

        print("\n[2] DISTRIBUTION LEGITIMACY")

        for col in numeric_df.columns:

            skewness = df[col].skew()

            if abs(skewness) > 5:
                print(f"⚠ {col} has unnatural distribution")

        # =================================================
        # 3. CORRELATION VALIDATION
        # =================================================

        print("\n[3] REAL-WORLD CORRELATION VALIDATION")

        for a, b in expected_positive_correlations:

            if a in df.columns and b in df.columns:

                corr, _ = pearsonr(df[a], df[b])

                print(f"{a} ↔ {b} = {round(corr,3)}")

                if corr < 0.2:
                    print("⚠ Weak real-world relationship")

        for a, b in expected_negative_correlations:

            if a in df.columns and b in df.columns:

                corr, _ = pearsonr(df[a], df[b])

                print(f"{a} ↔ {b} = {round(corr,3)}")

                if corr > -0.1:
                    print("⚠ Unrealistic negative relationship")

        # =================================================
        # 4. GEOGRAPHIC VALIDATION
        # =================================================

        print("\n[4] BANGALORE GEO VALIDATION")

        bangalore_lat_min = 12.70
        bangalore_lat_max = 13.25

        bangalore_lng_min = 77.35
        bangalore_lng_max = 77.90

        invalid_geo = df[
            (df['lat'] < bangalore_lat_min) |
            (df['lat'] > bangalore_lat_max) |
            (df['lng'] < bangalore_lng_min) |
            (df['lng'] > bangalore_lng_max)
        ]

        print(f"Invalid Bangalore Coordinates: {len(invalid_geo)}")

        # =================================================
        # 5. SYNTHETIC DATA DETECTION
        # =================================================

        print("\n[5] SYNTHETIC DATA DETECTION")

        for col in numeric_df.columns:

            std = df[col].std()
            mean = df[col].mean()

            if mean != 0:

                cv = std / mean

                if cv < 0.03:
                    print(f"⚠ {col} values too uniform")

        # =================================================
        # 6. ENTROPY ANALYSIS
        # =================================================

        print("\n[6] ENTROPY ANALYSIS")

        for col in numeric_df.columns:

            values = df[col].value_counts(normalize=True)

            ent = entropy(values)

            if ent < 1:
                print(f"⚠ {col} low entropy (possibly fabricated)")

        # =================================================
        # 7. ML-BASED LEGITIMACY TEST
        # =================================================

        print("\n[7] ML LEGITIMACY ANALYSIS")

        model = IsolationForest(
            contamination=0.02,
            random_state=42
        )

        predictions = model.fit_predict(
            numeric_df.fillna(0)
        )

        anomalies = (predictions == -1).sum()

        print(f"Suspicious Rows Detected: {anomalies}")

        # =================================================
        # 8. TRAFFIC REALISM
        # =================================================

        print("\n[8] TRAFFIC REALISM CHECK")

        unrealistic_speed = df[
            (df['speed_limit'] > 140)
        ]

        unrealistic_travel = df[
            (df['travel_time_estimate'] < 1)
        ]

        print(f"Unrealistic Speed Limits: {len(unrealistic_speed)}")
        print(f"Unrealistic Travel Times: {len(unrealistic_travel)}")

        # =================================================
        # 9. RISK SCORE CONSISTENCY
        # =================================================

        print("\n[9] RISK CONSISTENCY ANALYSIS")

        suspicious_risk = df[
            (df['crime_score'] > 8) &
            (df['road_risk_score'] < 3)
        ]

        print(f"Inconsistent Risk Rows: {len(suspicious_risk)}")

        # =================================================
        # 10. FINAL LEGITIMACY SCORE
        # =================================================

        print("\n[10] FINAL LEGITIMACY SCORE")

        legitimacy_score = 100

        legitimacy_score -= anomalies * 0.2
        legitimacy_score -= len(invalid_geo) * 0.3
        legitimacy_score -= len(suspicious_risk) * 0.2

        legitimacy_score = max(0, round(legitimacy_score, 2))

        print(f"\nLEGITIMACY SCORE : {legitimacy_score}/100")

        if legitimacy_score >= 90:
            print("DATA QUALITY : HIGHLY REALISTIC")

        elif legitimacy_score >= 75:
            print("DATA QUALITY : MOSTLY LEGITIMATE")

        elif legitimacy_score >= 50:
            print("DATA QUALITY : PARTIALLY SYNTHETIC")

        else:
            print("DATA QUALITY : SUSPICIOUS / FABRICATED")

    except Exception as e:

        print(f"\nERROR : {str(e)}")

print("\n===================================================")
print("LEGITIMACY ANALYSIS COMPLETED")
print("===================================================")
