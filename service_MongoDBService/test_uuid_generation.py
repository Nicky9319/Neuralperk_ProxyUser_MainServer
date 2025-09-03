#!/usr/bin/env python3
"""
Test script to verify UUID generation in MongoDB Service
This script tests the generate_uuid method and simulates the ID generation logic
"""

import uuid
import json

def generate_uuid():
    """Generate a unique UUID string - same as in the service"""
    return str(uuid.uuid4())

def test_uuid_generation():
    """Test that UUIDs are generated correctly and are unique"""
    print("Testing UUID generation...")
    
    # Generate multiple UUIDs
    uuids = []
    for i in range(5):
        new_uuid = generate_uuid()
        uuids.append(new_uuid)
        print(f"Generated UUID {i+1}: {new_uuid}")
    
    # Check uniqueness
    unique_uuids = set(uuids)
    if len(uuids) == len(unique_uuids):
        print("✓ All UUIDs are unique")
    else:
        print("✗ Duplicate UUIDs found!")
    
    # Check format (should be 36 characters with hyphens)
    for i, uuid_str in enumerate(uuids):
        if len(uuid_str) == 36 and uuid_str.count('-') == 4:
            print(f"✓ UUID {i+1} has correct format")
        else:
            print(f"✗ UUID {i+1} has incorrect format")
    
    # Test UUID validation
    try:
        uuid.UUID(uuids[0])
        print("✓ Generated UUID is valid")
    except ValueError:
        print("✗ Generated UUID is invalid")

def test_api_request_simulation():
    """Simulate API requests to show how IDs would be generated"""
    print("\nSimulating API requests...")
    
    # Simulate adding a customer
    customer_data = {
        "email": "test@example.com",
        "password": "testpass123"
    }
    
    # Generate customer ID
    customer_id = generate_uuid()
    print(f"Customer data: {json.dumps(customer_data, indent=2)}")
    print(f"Generated customerId: {customer_id}")
    
    # Simulate adding a blender object
    blender_object_data = {
        "customerId": customer_id,
        "blendFileName": "test_model.blend"
    }
    
    # Generate object ID
    object_id = generate_uuid()
    print(f"\nBlender object data: {json.dumps(blender_object_data, indent=2)}")
    print(f"Generated objectId: {object_id}")
    
    # Simulate adding a session
    session_data = {
        "customerId": customer_id,
        "blenderObjectId": object_id,
        "status": "queued"
    }
    
    # Generate session ID
    session_id = generate_uuid()
    print(f"\nSession data: {json.dumps(session_data, indent=2)}")
    print(f"Generated sessionId: {session_id}")
    
    # Show final document structures
    print("\nFinal document structures:")
    
    customer_doc = {
        "customerId": customer_id,
        "email": customer_data["email"],
        "password": customer_data["password"]
    }
    print(f"Customer document: {json.dumps(customer_doc, indent=2)}")
    
    object_doc = {
        "objectId": object_id,
        "customerId": customer_id,
        "blendFileName": blender_object_data["blendFileName"]
    }
    print(f"Blender object document: {json.dumps(object_doc, indent=2)}")
    
    session_doc = {
        "sessionId": session_id,
        "customerId": customer_id,
        "blenderObjectId": object_id,
        "status": session_data["status"]
    }
    print(f"Session document: {json.dumps(session_doc, indent=2)}")

if __name__ == "__main__":
    print("MongoDB Service UUID Generation Test")
    print("=" * 40)
    
    test_uuid_generation()
    test_api_request_simulation()
    
    print("\n" + "=" * 40)
    print("Test completed!")
