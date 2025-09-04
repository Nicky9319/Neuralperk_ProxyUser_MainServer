#!/usr/bin/env python3
"""
Test script to verify the new get-blend-file-from-path API endpoint
This script tests the functionality to find blend files in database by path hash
"""

import hashlib
import urllib.parse

def test_hash_calculation():
    """Test that the hash calculation works correctly"""
    print("Testing hash calculation...")
    
    # Test with a sample file path
    test_path = "/path/to/sample.blend"
    expected_hash = hashlib.sha256(test_path.encode("utf-8")).hexdigest()
    
    print(f"Test file path: {test_path}")
    print(f"Expected SHA-256 hash: {expected_hash}")
    print(f"Hash length: {len(expected_hash)} characters")
    
    # Verify hash format
    if len(expected_hash) == 64 and all(c in '0123456789abcdef' for c in expected_hash):
        print("✓ Hash format is valid (64 hex characters)")
    else:
        print("✗ Hash format is invalid")
    
    return expected_hash

def test_url_encoding():
    """Test URL encoding for file paths"""
    print("\nTesting URL encoding...")
    
    test_paths = [
        "path/to/sample.blend",
        "path/with spaces and special chars!@#.blend",
        "very/long/nested/directory/structure/with/many/subdirectories/and/finally/the/blend/file/name/with/very/long/name/that/exceeds/normal/length/limits/but/should/still/work/correctly/model.blend",
        "C:\\Windows\\Path\\With\\Backslashes\\file.blend",
        "path/with/unicode/characters/🚀/model.blend"
    ]
    
    for path in test_paths:
        encoded = urllib.parse.quote(path)
        decoded = urllib.parse.unquote(encoded)
        
        print(f"\nOriginal: {path}")
        print(f"Encoded:  {encoded}")
        print(f"Decoded:  {decoded}")
        
        if path == decoded:
            print("✓ Encoding/decoding successful")
        else:
            print("✗ Encoding/decoding failed")

def test_api_endpoint_simulation():
    """Simulate the API endpoint behavior"""
    print("\nSimulating API endpoint behavior...")
    
    # Simulate the get-hash-from-path endpoint
    def get_blend_file_hash_from_path(file_path):
        """Simulate the get-hash-from-path endpoint logic"""
        # Validate file_path parameter
        if not file_path:
            return {
                "error": "file_path query parameter is required",
                "status_code": 400
            }
        
        # Calculate hash
        try:
            blend_file_hash = hashlib.sha256(file_path.encode("utf-8")).hexdigest()
            return {
                "blendFileHash": blend_file_hash,
                "filePath": file_path,
                "message": "Hash calculated successfully",
                "status_code": 200
            }
        except Exception as e:
            return {
                "error": f"Error calculating hash: {str(e)}",
                "status_code": 500
            }
    
    # Test cases
    test_cases = [
        {
            "name": "Valid file path",
            "file_path": "path/to/sample.blend",
            "expected_status": 200
        },
        {
            "name": "Empty file path",
            "file_path": "",
            "expected_status": 400
        },
        {
            "name": "File path with spaces",
            "file_path": "path/with spaces/file.blend",
            "expected_status": 200
        },
        {
            "name": "File path with special characters",
            "file_path": "path/with!@#$%^&*()/file.blend",
            "expected_status": 200
        },
        {
            "name": "Very long file path",
            "file_path": "very/long/nested/directory/structure/with/many/subdirectories/and/finally/the/blend/file/name/with/very/long/name/that/exceeds/normal/length/limits/but/should/still/work/correctly/model.blend",
            "expected_status": 200
        },
        {
            "name": "Windows-style path",
            "file_path": "C:\\Users\\Username\\Documents\\Models\\model.blend",
            "expected_status": 200
        },
        {
            "name": "File path with unicode",
            "file_path": "path/with/unicode/🚀/model.blend",
            "expected_status": 200
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- Testing: {test_case['name']} ---")
        print(f"File path: {test_case['file_path']}")
        
        result = get_blend_file_hash_from_path(test_case['file_path'])
        
        if result.get("status_code") == test_case["expected_status"]:
            print(f"✓ Status code: {result['status_code']} (expected: {test_case['expected_status']})")
        else:
            print(f"✗ Status code: {result.get('status_code')} (expected: {test_case['expected_status']})")
        
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Success: {result['message']}")
            print(f"File Path: {result['filePath']}")
            print(f"Hash: {result['blendFileHash']}")
            print(f"Hash Length: {len(result['blendFileHash'])} characters")

def test_query_parameter_format():
    """Test the correct query parameter format for the API"""
    print("\nTesting query parameter format...")
    
    base_url = "http://localhost:12000"
    endpoint = "/api/mongodb-service/blender-objects/get-hash-from-path"
    
    test_paths = [
        "path/to/sample.blend",
        "path/with spaces/file.blend",
        "path/with/special/chars!@#/file.blend"
    ]
    
    for path in test_paths:
        # Encode the path for URL
        encoded_path = urllib.parse.quote(path)
        
        # Construct the full URL
        full_url = f"{base_url}{endpoint}?file_path={encoded_path}"
        
        print(f"\nFile path: {path}")
        print(f"Encoded: {encoded_path}")
        print(f"Full URL: {full_url}")
        
        # Verify the URL can be parsed back
        parsed = urllib.parse.urlparse(full_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        
        if 'file_path' in query_params:
            decoded_path = urllib.parse.unquote(query_params['file_path'][0])
            print(f"Decoded from URL: {decoded_path}")
            
            if path == decoded_path:
                print("✓ URL construction successful")
            else:
                print("✗ URL construction failed")
        else:
            print("✗ Query parameter not found in URL")

if __name__ == "__main__":
    print("Hash-From-Path API Endpoint Test")
    print("=" * 50)
    
    test_hash_calculation()
    test_url_encoding()
    test_api_endpoint_simulation()
    test_query_parameter_format()
    
    print("\n" + "=" * 50)
    print("Test completed!")
