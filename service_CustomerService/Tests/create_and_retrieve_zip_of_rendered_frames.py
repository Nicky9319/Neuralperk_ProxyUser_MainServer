#!/usr/bin/env python3
"""
Test script for creating and retrieving zip files of rendered frames

This script demonstrates:
1. Making an API call to create a zip file of rendered frames
2. Printing the creation results
3. Making another API call to retrieve the actual zip file
4. Using tqdm to show download progress
"""

import requests
import os
import json
from tqdm import tqdm
import time
from urllib.parse import urlparse

SERVER_IP_ADDRESS = "127.0.0.1"
SERVER_IP_ADDRESS = "143.110.186.158"

# Configuration
BASE_URL = f"http://{SERVER_IP_ADDRESS}:11000"  # Customer service URL
OUTPUT_DIR = "./downloaded_frames"

# Test data - replace these with actual values
TEST_CUSTOMER_ID = "392b1d5e-7edd-4386-856c-b16f1353988b"
TEST_OBJECT_ID = "0ca73243-52d8-41a9-8555-bb925fe683dd"
TEST_ACCESS_TOKEN = "392b1d5e-7edd-4386-856c-b16f1353988b"
EXPIRATION_SECONDS = 3600  # 1 hour

def create_output_directory():
    """Create output directory if it doesn't exist"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"✓ Created output directory: {OUTPUT_DIR}")

def create_zip_file(object_id: str, access_token: str, expiration_secs: int = 3600):
    """
    Step 1: Create zip file of rendered frames
    
    Args:
        customer_id: Customer ID
        object_id: Object ID to create zip for
        access_token: Bearer token for authentication
        expiration_secs: Expiration time for signed URL in seconds
        
    Returns:
        dict: API response containing zip creation details
    """
    print("=" * 60)
    print("🚀 STEP 1: Creating zip file of rendered frames")
    print("=" * 60)
    
    url = f"{BASE_URL}/api/customer-service/create-and-retrieve-zip-file-of-rendered-frames/{object_id}/{expiration_secs}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    print(f"📡 Making API call to: {url}")
    print(f"🔐 Using access token: {access_token[:20]}..." if len(access_token) > 20 else access_token)
    print(f"⏰ Expiration: {expiration_secs} seconds")
    
    try:
        response = requests.get(url, headers=headers, timeout=60)
        
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            print("✅ SUCCESS: Zip file creation completed!")
            print(f"📦 Zip Key: {response_data.get('zipKey', 'N/A')}")
            print(f"🪣 Bucket: {response_data.get('bucket', 'N/A')}")
            print(f"📊 Total Frames: {response_data.get('totalFrames', 'N/A')}")
            print(f"📏 Zip Size: {response_data.get('zipSizeHuman', 'N/A')}")
            print(f"♻️ Previously Existed: {response_data.get('zipExistsPreviously', False)}")
            print(f"🔗 Signed URL: {response_data.get('signedUrl', 'N/A')[:80]}...")
            
            return response_data
        else:
            print(f"❌ ERROR: {response.status_code}")
            print(f"📝 Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse JSON response: {str(e)}")
        return None

def download_zip_file_with_progress(signed_url: str, output_filename: str):
    """
    Step 2: Download the zip file using the signed URL with progress bar
    
    Args:
        signed_url: Signed URL to download the zip file
        output_filename: Local filename to save the zip file
        
    Returns:
        bool: True if download successful, False otherwise
    """
    print("\n" + "=" * 60)
    print("📥 STEP 2: Downloading zip file with progress bar")
    print("=" * 60)
    
    try:
        # Get file size first for progress bar
        print("🔍 Getting file size for progress tracking...")
        head_response = requests.head(signed_url, timeout=30)
        
        if head_response.status_code != 200:
            print(f"❌ Failed to get file info: {head_response.status_code}")
            return False
            
        file_size = int(head_response.headers.get('content-length', 0))
        print(f"📏 File size: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")
        
        # Download with progress bar
        print(f"📥 Downloading to: {output_filename}")
        
        with requests.get(signed_url, stream=True, timeout=60) as response:
            response.raise_for_status()
            
            # Initialize progress bar
            progress_bar = tqdm(
                total=file_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc="Downloading",
                ncols=80
            )
            
            with open(output_filename, 'wb') as file:
                downloaded = 0
                start_time = time.time()
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        downloaded += len(chunk)
                        progress_bar.update(len(chunk))
                        
                        # Update progress bar description with speed
                        elapsed_time = time.time() - start_time
                        if elapsed_time > 0:
                            speed = downloaded / elapsed_time
                            progress_bar.set_description(f"Downloading ({speed/1024/1024:.1f} MB/s)")
            
            progress_bar.close()
            
        final_size = os.path.getsize(output_filename)
        print(f"✅ Download completed!")
        print(f"📁 Saved to: {output_filename}")
        print(f"📊 Final size: {final_size:,} bytes ({final_size / (1024*1024):.2f} MB)")
        
        # Verify file size matches
        if file_size > 0 and final_size != file_size:
            print(f"⚠️  WARNING: Downloaded size ({final_size}) doesn't match expected size ({file_size})")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Download failed: {str(e)}")
        return False
    except IOError as e:
        print(f"❌ File I/O error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during download: {str(e)}")
        return False



def main():
    """Main function to orchestrate the zip creation and download process"""
    print("🎬 Starting Rendered Frames Zip Creation and Download Test")
    print(f"🎯 Target Object ID: {TEST_OBJECT_ID}")
    
    # Create output directory
    create_output_directory()
    
    # Step 1: Create zip file
    zip_data = create_zip_file(
        object_id=TEST_OBJECT_ID,
        access_token=TEST_ACCESS_TOKEN,
        expiration_secs=EXPIRATION_SECONDS
    )
    
    if not zip_data:
        print("❌ Failed to create zip file. Exiting.")
        return
    
    # Print detailed results
    print("\n" + "📋 ZIP CREATION RESULTS:")
    print(json.dumps(zip_data, indent=2))
    
    # Extract information for download
    signed_url = zip_data.get('signedUrl')
    zip_key = zip_data.get('zipKey')
    
    if not signed_url:
        print("❌ No signed URL received. Cannot download.")
        return
    
    # Generate output filename
    timestamp = int(time.time())
    output_filename = os.path.join(OUTPUT_DIR, f"frames_{TEST_OBJECT_ID}_{timestamp}.zip")
    
    # Step 2: Download using signed URL
    success = download_zip_file_with_progress(signed_url, output_filename)
    
    if success:
        print("\n🎉 COMPLETE: Zip file created and downloaded successfully!")
    else:
        print("\n❌ FAILED: Could not download the zip file.")
        print("💡 Note: All file operations go through the Customer Service API.")

if __name__ == "__main__":
    # You can modify these values for testing
    print("⚙️  Configuration:")
    print(f"   - Customer Service: {BASE_URL}")
    print(f"   - Output Directory: {OUTPUT_DIR}")
    print(f"   - Test Object ID: {TEST_OBJECT_ID}")
    print(f"   - Access Token: {TEST_ACCESS_TOKEN[:20]}..." if len(TEST_ACCESS_TOKEN) > 20 else TEST_ACCESS_TOKEN)
    print()
    
    # Prompt user to confirm or modify values
    response = input("Proceed with these settings? (y/n/modify): ").lower().strip()
    
    if response == 'n':
        print("👋 Exiting...")
        exit(0)
    elif response == 'modify':
        print("\n📝 Enter new values (press Enter to keep current value):")
        
        new_object_id = input(f"Object ID [{TEST_OBJECT_ID}]: ").strip()
        if new_object_id:
            TEST_OBJECT_ID = new_object_id
            
        new_token = input(f"Access Token [{TEST_ACCESS_TOKEN}]: ").strip()
        if new_token:
            TEST_ACCESS_TOKEN = new_token
            
        new_expiration = input(f"Expiration seconds [{EXPIRATION_SECONDS}]: ").strip()
        if new_expiration and new_expiration.isdigit():
            EXPIRATION_SECONDS = int(new_expiration)
    
    main()
