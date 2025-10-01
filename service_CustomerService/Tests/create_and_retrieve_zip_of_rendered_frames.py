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


t1 = time.time()

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TEST_ACCESS_TOKEN}"
}

zip_signed_url_response = requests.get(f"{BASE_URL}/api/customer-service/create-and-retrieve-zip-file-of-rendered-frames/{TEST_OBJECT_ID}/{EXPIRATION_SECONDS}" , headers=headers).json()
print(zip_signed_url_response)

t2 = time.time()

print("Total time to create the zip folder itself and retrieve the signed url is : ")
print(t2 - t1)
