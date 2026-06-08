from pymongo import MongoClient
from ENGINE.config import MONGO_URI

# MONGO_URI is loaded from environment (.env or system env). Do not commit credentials.
client = MongoClient(MONGO_URI)
db = client["SAFEROUTE_AI"]
collection = db["RiskDataBengaluru"]

print("Analyzing City-Wide Traffic Risk...")

# This is an Aggregation Pipeline - MongoDB's most powerful feature
pipeline = [
    {
        "$group": {
            "_id": "$zone", # Group the data by the 'zone' column
            "average_risk": {"$avg": "$road_risk_score"}, # Calculate average risk
            "total_roads": {"$sum": 1} # Count how many roads are in each zone
        }
    },
    {
        "$sort": {"average_risk": -1} # Sort from highest risk to lowest risk
    }
]

results = collection.aggregate(pipeline)

print("\n--- Risk Report by Zone ---")
for zone_data in results:
    print(f"Zone: {zone_data['_id']}")
    print(f"  Average Risk Score: {zone_data['average_risk']:.3f}")
    print(f"  Total Roads Tracked: {zone_data['total_roads']}\n")

client.close()