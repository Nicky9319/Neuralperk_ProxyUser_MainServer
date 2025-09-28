#!/usr/bin/env python3
"""
Test script for the get-rendered-frames endpoint in Customer Service
This script tests the functionality of retrieving rendered frames with pagination
"""

import asyncio
import aiohttp
import json
import os
from pathlib import Path

class RenderedFramesTester:
    def __init__(self, base_url="http://localhost:11000", auth_token=None):
        self.base_url = base_url
        self.auth_token = auth_token
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def get_headers(self):
        """Get headers with authentication token"""
        headers = {
            "Content-Type": "application/json"
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    async def test_get_rendered_frames(self, object_id, start_frame=0, pagination_size=20):
        """
        Test the get-rendered-frames endpoint
        
        Args:
            object_id: The object ID to get frames for
            start_frame: Starting frame index (default: 0)
            pagination_size: Number of frames to return (default: 20)
        """
        url = f"{self.base_url}/api/customer-service/get-rendered-frames/{object_id}"
        params = {
            "start_frame": start_frame,
            "pagination_size": pagination_size
        }
        
        print(f"Testing get-rendered-frames endpoint...")
        print(f"URL: {url}")
        print(f"Object ID: {object_id}")
        print(f"Start Frame: {start_frame}")
        print(f"Pagination Size: {pagination_size}")
        print(f"Auth Token: {'***' if self.auth_token else 'None'}")
        print("-" * 50)
        
        try:
            async with self.session.get(
                url, 
                params=params, 
                headers=self.get_headers()
            ) as response:
                print(f"Response Status: {response.status}")
                print(f"Response Headers:")
                for key, value in response.headers.items():
                    print(f"  {key}: {value}")
                print("-" * 50)
                
                if response.status == 200:
                    # Read the response content
                    content = await response.read()
                    
                    # Try to decode as text to get the metadata
                    try:
                        # The response starts with JSON metadata, then binary image data
                        content_str = content.decode('utf-8')
                        
                        # Find the first newline to separate metadata from binary data
                        newline_pos = content_str.find('\n')
                        if newline_pos != -1:
                            metadata_json = content_str[:newline_pos]
                            binary_data = content[newline_pos + 1:]
                            
                            # Parse metadata
                            metadata = json.loads(metadata_json)
                            print("Metadata:")
                            print(json.dumps(metadata, indent=2))
                            print("-" * 50)
                            
                            # Try to extract individual frames from the binary data
                            await self.extract_frames_from_binary(binary_data, object_id, start_frame, pagination_size)
                            
                        else:
                            print("No newline found in response, treating as pure binary")
                            # Try to extract individual frames from the binary data
                            await self.extract_frames_from_binary(content, object_id, start_frame, pagination_size)
                            
                    except UnicodeDecodeError:
                        # If it's not valid UTF-8, treat as pure binary
                        # Try to extract individual frames from the binary data
                        await self.extract_frames_from_binary(content, object_id, start_frame, pagination_size)
                        
                else:
                    # Handle error responses
                    error_text = await response.text()
                    print(f"Error Response: {error_text}")
                    
        except Exception as e:
            print(f"Error making request: {str(e)}")
    
    async def extract_frames_from_binary(self, binary_data, object_id, start_frame, pagination_size):
        """
        Extract individual frames from the binary response data
        """
        try:
            # Create output directory for frames with the specified naming format
            output_dir = f"{start_frame}_{pagination_size}"
            os.makedirs(output_dir, exist_ok=True)
            print(f"Created output directory: {output_dir}")
            
            print(f"Binary data size: {len(binary_data)} bytes")
            print(f"First 200 bytes (hex): {binary_data[:200].hex()}")
            print(f"First 200 bytes (as string, errors='ignore'): {binary_data[:200].decode('utf-8', errors='ignore')}")
            
            # Look for frame separators in binary data
            frame_start_marker = b"---FRAME_"
            frame_end_marker = b"---END_FRAME_"
            
            frames = []
            start_pos = 0
            
            # Find all frame markers
            frame_markers = []
            pos = 0
            while True:
                marker_pos = binary_data.find(frame_start_marker, pos)
                if marker_pos == -1:
                    break
                frame_markers.append(marker_pos)
                pos = marker_pos + 1
            
            print(f"Found {len(frame_markers)} frame start markers at positions: {frame_markers}")
            
            for i, frame_start in enumerate(frame_markers):
                try:
                    # Find the frame number
                    frame_num_start = frame_start + len(frame_start_marker)
                    frame_num_end = binary_data.find(b"---", frame_num_start)
                    if frame_num_end == -1:
                        print(f"Could not find frame number end marker for frame {i}")
                        continue
                    
                    # Extract frame number as string
                    frame_number_bytes = binary_data[frame_num_start:frame_num_end]
                    frame_number = frame_number_bytes.decode('utf-8')
                    print(f"Processing frame {frame_number}")
                    
                    # Find the end marker for this frame
                    frame_end_marker_with_number = frame_end_marker + frame_number_bytes
                    frame_end = binary_data.find(frame_end_marker_with_number, frame_num_end)
                    if frame_end == -1:
                        print(f"Could not find end marker for frame {frame_number}")
                        continue
                    
                    # Extract the frame data (between the markers)
                    frame_data_start = frame_num_end + 3  # Skip the "---"
                    frame_data_end = frame_end
                    
                    # Extract the actual binary image data
                    frame_data_binary = binary_data[frame_data_start:frame_data_end]
                    
                    print(f"Frame {frame_number} data size: {len(frame_data_binary)} bytes")
                    print(f"Frame {frame_number} data starts with: {frame_data_binary[:20].hex()}")
                    
                    # Check if this looks like PNG data (PNG files start with specific bytes)
                    # PNG header can be: \x89PNG\r\n\x1a\n or \n\x89PNG\r\n\x1a\n (with newline)
                    if frame_data_binary.startswith(b'\x89PNG\r\n\x1a\n'):
                        print(f"Frame {frame_number} appears to be valid PNG data")
                    elif frame_data_binary.startswith(b'\n\x89PNG\r\n\x1a\n'):
                        print(f"Frame {frame_number} has PNG data with leading newline, adjusting")
                        frame_data_binary = frame_data_binary[1:]  # Remove the leading newline
                    else:
                        print(f"Frame {frame_number} does not appear to be PNG data")
                        # Try to find PNG header within the data
                        png_start = frame_data_binary.find(b'\x89PNG\r\n\x1a\n')
                        if png_start != -1:
                            print(f"Found PNG header at position {png_start}, adjusting data")
                            frame_data_binary = frame_data_binary[png_start:]
                        else:
                            print(f"No PNG header found in frame {frame_number} data")
                    
                    # Save individual frame with proper naming
                    # Convert frame_number to int for zero-padding
                    frame_number_int = int(frame_number)
                    frame_filename = f"frame_{frame_number_int:04d}.png"  # Zero-padded frame number
                    frame_path = os.path.join(output_dir, frame_filename)
                    
                    with open(frame_path, 'wb') as f:
                        f.write(frame_data_binary)
                    
                    frames.append({
                        "frame_number": frame_number,
                        "filename": frame_filename,
                        "path": frame_path,
                        "size": len(frame_data_binary)
                    })
                    
                    print(f"Extracted frame {frame_number}: {frame_path} ({len(frame_data_binary)} bytes)")
                    
                except Exception as frame_error:
                    print(f"Error processing frame {i}: {str(frame_error)}")
                    continue
            
            print(f"Total frames extracted: {len(frames)}")
            print(f"All frames saved in directory: {output_dir}")
            
            # List all files in the output directory
            if os.path.exists(output_dir):
                files = os.listdir(output_dir)
                print(f"Files in {output_dir}: {sorted(files)}")
                
                # Check if files are valid PNG files
                for file in files:
                    file_path = os.path.join(output_dir, file)
                    try:
                        with open(file_path, 'rb') as f:
                            header = f.read(8)
                            if header == b'\x89PNG\r\n\x1a\n':
                                print(f"✓ {file} is a valid PNG file")
                            else:
                                print(f"✗ {file} is NOT a valid PNG file (header: {header.hex()})")
                    except Exception as e:
                        print(f"Error checking {file}: {str(e)}")
            
        except Exception as e:
            print(f"Error extracting frames: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def test_health_check(self):
        """Test the health check endpoint"""
        url = f"{self.base_url}/api/customer-service/"
        
        print("Testing health check endpoint...")
        print(f"URL: {url}")
        print("-" * 50)
        
        try:
            async with self.session.post(url, headers=self.get_headers()) as response:
                print(f"Response Status: {response.status}")
                response_text = await response.text()
                print(f"Response: {response_text}")
                
        except Exception as e:
            print(f"Error making health check request: {str(e)}")

async def main():
    """Main test function"""
    print("Rendered Frames API Tester")
    print("=" * 50)
    
    # Configuration
    BASE_URL = "http://143.110.186.158:11000"
    
    # You need to provide a valid auth token
    # Replace this with your actual customer ID/token
    AUTH_TOKEN = "392b1d5e-7edd-4386-856c-b16f1353988b"
    
    if not AUTH_TOKEN:
        print("No auth token provided. Some endpoints may not work.")
        AUTH_TOKEN = None
    
    # Test object ID - replace with a valid object ID from your system
    OBJECT_ID = "ef33729b-9d09-45ed-92d5-c3ee8580a5cb"
    
    if not OBJECT_ID:
        print("No object ID provided. Using default test ID.")
        OBJECT_ID = "test-object-id"
    
    async with RenderedFramesTester(BASE_URL, AUTH_TOKEN) as tester:
        # Test 1: Health check
        print("\n1. Testing Health Check")
        print("=" * 30)
        await tester.test_health_check()
        

        # Test 2: Get rendered frames with custom pagination
        print("\n2. Testing Get Rendered Frames (Custom Pagination)")
        print("=" * 50)
        await tester.test_get_rendered_frames(OBJECT_ID, start_frame=0, pagination_size=5)
        
        # Test 3: Get rendered frames with offset
        print("\n3. Testing Get Rendered Frames (With Offset)")
        print("=" * 50)
        await tester.test_get_rendered_frames(OBJECT_ID, start_frame=10, pagination_size=10)

if __name__ == "__main__":
    asyncio.run(main())
