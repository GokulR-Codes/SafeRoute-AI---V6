from pymongo import MongoClient

# Connect to your Atlas cluster
MONGO_URI = "mongodb+srv://1jb23cs163_admin:algUuOHtPdLc9nzM@cluster0.hc4wd.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client["SAFEROUTE_AI"]
collection = db["RiskDataBengaluru"]

print("🔍 Searching for documents with a missing or 'None' zone...\n")

# Query: Find documents where 'zone' is None OR an empty string
query = {"zone": {"$in": [None, ""]}}

# We use .limit(5) so it doesn't spam your terminal if there are hundreds of blank rows
results = list(collection.find(query).limit(5))

if len(results) == 0:
    print("✅ No empty zones found! Your database is clean.")
else:
    print(f"⚠️ Found {collection.count_documents(query)} rows with missing zones. Here is a sample of 5:\n")
    
    for i, doc in enumerate(results, 1):
        print(f"--- Ghost Row {i} ---")
        # Print a few key fields to see if they hold actual data or are completely blank
        print(f"  Zone: {doc.get('zone')}")
        print(f"  Road Name: {doc.get('road_name')}")
        print(f"  Latitude: {doc.get('lat')}")
        print(f"  Longitude: {doc.get('lng')}")
        print(f"  Risk Score: {doc.get('road_risk_score')}")
        print("-" * 25 + "\n")

client.close()