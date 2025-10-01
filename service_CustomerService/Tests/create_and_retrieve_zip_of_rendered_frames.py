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
from urllib.parse import quote

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


t1 = time.time()

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TEST_ACCESS_TOKEN}"
}

zip_creation_response = requests.get(
    f"{BASE_URL}/api/customer-service/create-and-retrieve-zip-file-of-rendered-frames/{TEST_OBJECT_ID}/{EXPIRATION_SECONDS}",
    headers=headers
)

if zip_creation_response.status_code != 200:
    print("Failed to create / retrieve zip:", zip_creation_response.status_code, zip_creation_response.text)
    exit(1)

zip_data = zip_creation_response.json()
print(json.dumps(zip_data, indent=2))

t2 = time.time()

print("Total time to create the zip folder itself and retrieve the signed url is : ")
print(t2 - t1)


# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Extract proxy path returned by the service
proxy_path = zip_data.get("zipProxyPath") or zip_data.get("signedUrl") or zip_data.get("signed_url")
if not proxy_path:
    print("No proxy path present in response; cannot download.")
    exit(1)

# The proxy_path already contains query params (signed URL path + signature). We need to URL-encode only the path portion up to '?' for embedding
if '?' in proxy_path:
    path_part, query_part = proxy_path.split('?', 1)
    encoded_path = quote(path_part, safe='/')  # keep slashes
    final_download_url = f"{BASE_URL}/api/customer-service/get-zip-from-signed-url/{encoded_path}?{query_part}"
else:
    encoded_path = quote(proxy_path, safe='/')
    final_download_url = f"{BASE_URL}/api/customer-service/get-zip-from-signed-url/{encoded_path}"

print("Downloading zip via proxy endpoint:")
print(final_download_url)

download_start = time.time()
response = requests.get(final_download_url, stream=True)

if response.status_code != 200:
    print("Download failed:", response.status_code, response.text[:500])
    exit(1)

file_size = int(response.headers.get('content-length', 0))
human_size = f"{file_size/1024/1024:.2f} MB" if file_size else "Unknown size"
print(f"Reported size: {human_size}")

timestamp = int(time.time())
zip_filename = os.path.join(OUTPUT_DIR, f"frames_{TEST_OBJECT_ID}_{timestamp}.zip")

progress = tqdm(total=file_size if file_size else None, unit='B', unit_scale=True, unit_divisor=1024, desc='Downloading ZIP', ncols=80)

bytes_downloaded = 0
with open(zip_filename, 'wb') as f:
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            f.write(chunk)
            bytes_downloaded += len(chunk)
            progress.update(len(chunk))

progress.close()
download_end = time.time()

print(f"Saved zip to: {zip_filename}")
print(f"Downloaded {bytes_downloaded/1024/1024:.2f} MB in {download_end - download_start:.2f} seconds")
if file_size and bytes_downloaded != file_size:
    print(f"Warning: Downloaded size {bytes_downloaded} differs from content-length {file_size}")