import csv
import os
from pymongo import MongoClient, GEOSPHERE

# Replace with your MongoDB Atlas URI
MONGO_URI = "mongodb+srv://1jb23cs163_admin:algUuOHtPdLc9nzM@cluster0.hc4wd.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "SAFEROUTE_AI"
COLLECTION_NAME = "RiskDataBengaluru"

# List of your CSV files
FILES_TO_IMPORT = [
    'ENGINE/datasets/central_bangalore_risk.csv',
    'ENGINE/datasets/airport_peripheral_risk.csv',
    'ENGINE/datasets/east_bangalore_risk.csv',
    'ENGINE/datasets/logistics_hightraffic_risk.csv',
    'ENGINE/datasets/north_bangalore_risk.csv',
    'ENGINE/datasets/west_bangalore_risk.csv',
    'ENGINE/datasets/southeast_it_corridor_risk.csv',
    'ENGINE/datasets/south_bangalore_risk.csv',
    'ENGINE/datasets/graph_edges.csv',
    'ENGINE/datasets/graph_nodes.csv',
    'ENGINE/datasets/hourly_edge_weights.csv'
]

# All fields that need to be stored as numbers in MongoDB
NUMERIC_FIELDS = [
    'speed_limit', 'traffic_signal_density', 'intersection_density', 
    'commercial_density', 'nightlife_density', 'hospital_density', 
    'police_station_distance', 'cctv_density_estimate', 'lighting_score', 
    'crime_score', 'activity_score', 'event_frequency', 'infrastructure_score', 
    'connectivity_score', 'isolated_area_score', 'road_risk_score', 
    'travel_time_estimate', 'congestion_score', 'flood_risk', 
    'weather_exposure_score', 'poi_density', 'time_risk', 'adjacency_count'
]

def safe_float(val):
    """Helper to safely convert strings to floats, handling empty CSV cells."""
    if not val or val.strip() == '':
        return None
    try:
        return float(val)
    except ValueError:
        return None

def import_csv(file_path, collection):
    results = []
    
    with open(file_path, mode='r', encoding='utf-8-sig') as file:
        # DictReader automatically uses the first row as dictionary keys
        reader = csv.DictReader(file)
        
        for row in reader:
            # 1. Start with the base string data
            doc = dict(row)
            
            # 2. Extract and cast lat/lng
            lat = safe_float(row.get('lat'))
            lng = safe_float(row.get('lng'))
            
            doc['lat'] = lat
            doc['lng'] = lng
            
            # 3. Construct GeoJSON location object (Longitude first, then Latitude)
            if lat is not None and lng is not None:
                doc['location'] = {
                    "type": "Point",
                    "coordinates": [lng, lat]
                }
            
            # 4. Explicitly cast all other numeric fields
            for field in NUMERIC_FIELDS:
                if field in row:
                    doc[field] = safe_float(row[field])
            
            results.append(doc)
            
    # Bulk insert into MongoDB
    if results:
        try:
            collection.insert_many(results)
            print(f"✅ Successfully imported {len(results)} rows from {file_path}")
        except Exception as e:
            print(f"❌ Error inserting {file_path}: {e}")
    else:
        print(f"⚠️ No data found in {file_path}")

def run_import():
    try:
        print("Connecting to MongoDB Atlas...")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        print("Connected!")
        
        # Create the 2dsphere index for spatial queries
        print("Creating 2dsphere index on 'location'...")
        collection.create_index([("location", GEOSPHERE)])

        # Loop through and import all files
        for file_name in FILES_TO_IMPORT:
            if os.path.exists(file_name):
                import_csv(file_name, collection)
            else:
                print(f"⚠️ File not found: {file_name}, skipping...")

        print("🎉 All datasets imported successfully!")
        
    except Exception as e:
        print(f"Fatal Error: {e}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    run_import()