import json
import os
from pymongo import MongoClient
from pymongo.server_api import ServerApi

def populate_test_data():
    """Populate MongoDB database with test data for development and testing"""
    
    # Load the dummy data files
    current_dir = os.path.dirname(__file__)
    
    # Load customers data
    customers_file = os.path.join(current_dir, "dummy_data", "customers.json")
    if os.path.exists(customers_file):
        with open(customers_file, 'r') as f:
            customers_data = json.load(f)
    else:
        # Create sample customers if file doesn't exist
        customers_data = [
            {
                "customerId": "cust001",
                "email": "customer1@example.com",
                "password": "password123"
            },
            {
                "customerId": "cust002", 
                "email": "customer2@example.com",
                "password": "password456"
            },
            {
                "customerId": "cust003",
                "email": "customer3@example.com", 
                "password": "password789"
            }
        ]
    
    # Load blender objects data
    blender_objects_file = os.path.join(current_dir, "dummy_data", "blenderObjects.json")
    with open(blender_objects_file, 'r') as f:
        blender_objects_data = json.load(f)
    
    # Create sample sessions data
    sessions_data = [
        {
            "sessionId": "sess001",
            "customerId": "cust001",
            "blenderObjectId": "obj001",
            "status": "completed"
        },
        {
            "sessionId": "sess002",
            "customerId": "cust002",
            "blenderObjectId": "obj002", 
            "status": "rendering"
        },
        {
            "sessionId": "sess003",
            "customerId": "cust003",
            "blenderObjectId": "obj003",
            "status": "queued"
        }
    ]
    
    # Connect to MongoDB
    client = MongoClient('mongodb://localhost:27017/', server_api=ServerApi('1'))
    db = client["neuralperk"]
    
    print("Populating MongoDB database with test data...")
    
    # Clear existing data
    db.customers.delete_many({})
    db.blenderObjects.delete_many({})
    db.sessions.delete_many({})
    
    # Insert customers
    if customers_data:
        result = db.customers.insert_many(customers_data)
        print(f"Inserted {len(result.inserted_ids)} customers")
    
    # Insert blender objects
    if blender_objects_data:
        result = db.blenderObjects.insert_many(blender_objects_data)
        print(f"Inserted {len(result.inserted_ids)} blender objects")
    
    # Insert sessions
    if sessions_data:
        result = db.sessions.insert_many(sessions_data)
        print(f"Inserted {len(result.inserted_ids)} sessions")
    
    print("Database population completed successfully!")
    
    # Display summary
    print(f"\nDatabase Summary:")
    print(f"Customers: {db.customers.count_documents({})}")
    print(f"Blender Objects: {db.blenderObjects.count_documents({})}")
    print(f"Sessions: {db.sessions.count_documents({})}")
    
    # Show sample data
    print(f"\nSample Customers:")
    for customer in db.customers.find().limit(3):
        print(f"  - {customer['customerId']}: {customer['email']}")
    
    print(f"\nSample Blender Objects:")
    for obj in db.blenderObjects.find().limit(3):
        print(f"  - {obj['objectId']}: {obj['customerId']} ({len(obj.get('renderedImages', []))} images)")
    
    print(f"\nSample Sessions:")
    for session in db.sessions.find().limit(3):
        print(f"  - {session['sessionId']}: {session['status']}")

if __name__ == "__main__":
    populate_test_data()
