# =============================================================================
# BLOB SERVICE - FILE STORAGE AND RETRIEVAL SERVICE
# =============================================================================
# This service provides APIs for storing, retrieving, and managing files
# in blob storage (S3-compatible MinIO). It handles images, blend files,
# temporary files, and rendered content.
# =============================================================================

# =============================================================================
# IMPORTS AND DEPENDENCIES
# =============================================================================

# Standard library imports
import asyncio
import sys
import os
import collections
import collections.abc

# FastAPI and web framework imports
from fastapi import FastAPI, Response, Request, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# AWS S3/MinIO client imports
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from io import BytesIO
import io
import zipstream

# Message queue imports (for future use)
import aio_pika

# Fix for Python 3.10+ compatibility with collections.Callable
collections.Callable = collections.abc.Callable

# Print status of monkey patch
print("collections.Callable patched:",
      hasattr(collections, "Callable"),
      collections.Callable is collections.abc.Callable)


# =============================================================================
# HTTP SERVER CLASS - MAIN SERVER CONFIGURATION
# =============================================================================

class HTTP_SERVER():
    """
    Main HTTP server class that handles FastAPI configuration, S3/MinIO client setup,
    and route configuration for the blob service.
    """
    
    def __init__(self, httpServerHost, httpServerPort, httpServerPrivilegedIpAddress=["127.0.0.1"], data_class_instance=None):
        """
        Initialize the HTTP server with FastAPI app, CORS middleware, and S3 client.
        
        Args:
            httpServerHost (str): Host address for the server
            httpServerPort (int): Port number for the server
            httpServerPrivilegedIpAddress (list): List of privileged IP addresses
            data_class_instance: Reference to the Data class instance
        """
        # FastAPI application setup
        self.app = FastAPI()
        self.host = httpServerHost
        self.port = httpServerPort
        self.privilegedIpAddress = httpServerPrivilegedIpAddress
        
        # CORS middleware configuration
        #<HTTP_SERVER_CORS_ADDITION_START>
        self.app.add_middleware(CORSMiddleware, allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"],)
        #<HTTP_SERVER_CORS_ADDITION_END>
        
        # Data class reference
        self.data_class = data_class_instance
        
        # S3/MinIO client initialization
        self.client = boto3.client(
            "s3",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="admin",
            aws_secret_access_key="password",
            config=Config(signature_version="s3v4"),
            region_name="us-east-1"
        )
        
        # Initialize default buckets
        self.initialize_default_buckets()

    # =============================================================================
    # BUCKET MANAGEMENT METHODS
    # =============================================================================
    
    def initialize_default_buckets(self):
        """
        Initialize default buckets if they don't exist.
        Creates standard buckets for different file types.
        """
        try:
            # List of default buckets to create
            default_buckets = ["blend-files", "rendered-videos", "rendered-frames", "frames-zip", "temp"]
            
            for bucket_name in default_buckets:
                try:
                    # Check if bucket exists
                    self.client.head_bucket(Bucket=bucket_name)
                    print(f"Bucket '{bucket_name}' already exists")
                except Exception:
                    # Bucket doesn't exist, create it
                    self.client.create_bucket(Bucket=bucket_name)
                    print(f"Created bucket '{bucket_name}' successfully")
                    
        except Exception as e:
            print(f"Warning: Could not initialize default buckets: {str(e)}")

    async def ensure_bucket_exists(self, bucket: str):
        """
        Ensure a bucket exists, create it if it doesn't.
        
        Args:
            bucket (str): Name of the bucket to check/create
            
        Returns:
            bool: True if bucket exists or was created successfully, False otherwise
        """
        try:
            # Check if bucket exists
            self.client.head_bucket(Bucket=bucket)
            return True
        except Exception:
            try:
                # Bucket doesn't exist, create it
                self.client.create_bucket(Bucket=bucket)
                print(f"Created bucket '{bucket}' on demand")
                return True
            except Exception as e:
                print(f"Error creating bucket '{bucket}': {str(e)}")
                return False

    # =============================================================================
    # API ROUTES CONFIGURATION
    # =============================================================================
    
    async def configure_routes(self):
        """
        Configure all API routes for the blob service.
        Routes are organized by functionality: health check, image operations,
        blend file operations, bucket management, and temp file operations.
        """
        
        # =============================================================================
        # HEALTH CHECK AND STATUS ROUTES
        # =============================================================================
        
        @self.app.get("/api/blob-service/")
        async def root():
            """Health check endpoint to verify service is running"""
            return JSONResponse(content={"message": "Blob Service is active"}, status_code=200)

        # =============================================================================
        # IMAGE OPERATIONS ROUTES
        # =============================================================================
        
        @self.app.post("/api/blob-service/store-image")
        async def storeImage(
            image: UploadFile = Form(...),
            bucket: str = Form(...),
            key: str = Form(...),
            type: str = Form(default="png")
        ):
            """
            Store an image file in the specified bucket with the given key.
            
            Args:
                image: Uploaded image file
                bucket: Target bucket name
                key: File key/name
                type: Image type/extension (default: png)
            
            Returns:
                JSON response with success/error status
            """
            print(f"Storing image: {image.filename}")
            print(f"Bucket: {bucket}")
            print(f"Key: {key}")
            print(f"Type: {type}")
            
            # Add file extension if not present in key
            if not key.endswith(f".{type}"):
                key = f"{key}.{type}"
            
            # Upload to blob storage
            result = await self.uploadImageToBlobStorage(image, bucket, key)
            
            if "error" in result:
                return JSONResponse(content={"error": result["error"]}, status_code=500)
        
            return JSONResponse(content={
                "message": "Image stored successfully",
                "filename": image.filename,
                "bucket": bucket,
                "key": key,
                "type": type
            }, status_code=200)

        @self.app.get("/api/blob-service/retrieve-image")
        async def retrieveImage(
            bucket: str,
            key: str,
            type: str = "png"
        ):
            """
            Retrieve an image file from the specified bucket and key.
            
            Args:
                bucket: Source bucket name
                key: File key/name
                type: Image type/extension (default: png)
            
            Returns:
                Image file with appropriate media type or error response
            """
            print(f"Retrieving image from bucket: {bucket}")
            print(f"Key: {key}")
            print(f"Type: {type}")
            
            # Add file extension if not present in key
            if not key.endswith(f".{type}"):
                key = f"{key}.{type}"
            
            # Retrieve from blob storage
            data = await self.retrieveImageFromBlobStorage(bucket, key)
            
            if isinstance(data, dict) and "error" in data:
                return JSONResponse(content={"error": data["error"]}, status_code=404)
            
            # Return image with appropriate media type
            media_type = f"image/{type}"
            return Response(content=data, media_type=media_type)
        
    
        # =============================================================================
        # LIGHT-WEIGHT OBJECT EXISTENCE ROUTE
        # =============================================================================
        @self.app.get("/api/blob-service/object-exists")
        async def objectExists(bucket: str, key: str):
            """Lightweight existence check for an object.
            Returns exists flag and basic metadata if present.
            """
            try:
                await self.ensure_bucket_exists(bucket)
                import botocore
                try:
                    head = self.client.head_object(Bucket=bucket, Key=key)
                    return JSONResponse(content={
                        "bucket": bucket,
                        "key": key,
                        "exists": True,
                        "size_bytes": head.get("ContentLength"),
                        "etag": (head.get("ETag") or '').strip('"')
                    }, status_code=200)
                except botocore.exceptions.ClientError as ce:
                    code = ce.response.get("Error", {}).get("Code")
                    http_status = ce.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                    if code in ("404", "NoSuchKey") or http_status == 404:
                        return JSONResponse(content={
                            "bucket": bucket,
                            "key": key,
                            "exists": False,
                            "size_bytes": None,
                            "etag": None
                        }, status_code=200)
                    return JSONResponse(content={"error": str(ce)}, status_code=500)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=500)

        # =============================================================================
        # GENERIC OBJECT / PREFIX METADATA ROUTE
        # =============================================================================
        @self.app.get("/api/blob-service/object-metadata")
        async def objectMetadata(
            bucket: str,
            key: str,
            aggregate_prefix: bool = False
        ):
            """Retrieve rich metadata for a specific object, or optionally aggregate for a prefix.

            Query Parameters:
                bucket (str): Bucket name
                key (str): Object key OR prefix path (if aggregate_prefix=True)
                aggregate_prefix (bool): When true and the exact object does not exist, treat key as a prefix
                                          and return aggregate statistics for all objects under it.

            Returns JSON with fields:
                bucket, key, exists, is_prefix, size_bytes, human_readable_size,
                etag, content_type, last_modified, storage_class,
                total_size_bytes, object_count, human_readable_total_size (when aggregated)
            """

            def _human(size):
                if size is None:
                    return None
                if size < 1024:
                    return f"{size} B"
                if size < 1024**2:
                    return f"{size/1024:.2f} KB"
                if size < 1024**3:
                    return f"{size/1024**2:.2f} MB"
                return f"{size/1024**3:.2f} GB"

            # Attempt a HEAD for exact object
            try:
                head = self.client.head_object(Bucket=bucket, Key=key)
                size_bytes = head.get("ContentLength")
                return JSONResponse(content={
                    "bucket": bucket,
                    "key": key,
                    "exists": True,
                    "is_prefix": False,
                    "size_bytes": size_bytes,
                    "human_readable_size": _human(size_bytes),
                    "etag": (head.get("ETag") or '').strip('"'),
                    "content_type": head.get("ContentType"),
                    "last_modified": head.get("LastModified").isoformat() if head.get("LastModified") else None,
                    "storage_class": head.get("StorageClass"),
                    "total_size_bytes": None,
                    "object_count": None,
                    "human_readable_total_size": None
                }, status_code=200)
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code in ("404", "NoSuchKey", "NotFound") and aggregate_prefix:
                    # Treat as prefix aggregation
                    prefix = key if key.endswith('/') else key + '/'
                    paginator = self.client.get_paginator('list_objects_v2')
                    total_size = 0
                    count = 0
                    last_modified = None
                    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                        for obj in page.get('Contents', []):
                            if obj.get('Key') == prefix:
                                continue
                            total_size += obj.get('Size', 0)
                            count += 1
                            lm = obj.get('LastModified')
                            if lm and (last_modified is None or lm > last_modified):
                                last_modified = lm
                    return JSONResponse(content={
                        "bucket": bucket,
                        "key": key,
                        "exists": count > 0,
                        "is_prefix": True,
                        "size_bytes": None,
                        "human_readable_size": None,
                        "etag": None,
                        "content_type": None,
                        "last_modified": last_modified.isoformat() if last_modified else None,
                        "storage_class": None,
                        "total_size_bytes": total_size if count else None,
                        "object_count": count if count else None,
                        "human_readable_total_size": _human(total_size) if count else None
                    }, status_code=200)
                elif error_code in ("404", "NoSuchKey", "NotFound"):
                    return JSONResponse(content={
                        "bucket": bucket,
                        "key": key,
                        "exists": False,
                        "is_prefix": False,
                        "size_bytes": None,
                        "human_readable_size": None,
                        "etag": None,
                        "content_type": None,
                        "last_modified": None,
                        "storage_class": None,
                        "total_size_bytes": None,
                        "object_count": None,
                        "human_readable_total_size": None
                    }, status_code=200)
                else:
                    return JSONResponse(content={
                        "error": "Failed to retrieve object metadata",
                        "details": str(e),
                        "bucket": bucket,
                        "key": key
                    }, status_code=500)
            except Exception as e:
                return JSONResponse(content={
                    "error": "Unexpected error while retrieving object metadata",
                    "details": str(e),
                    "bucket": bucket,
                    "key": key
                }, status_code=500)

        # =============================================================================
        # BLEND FILE OPERATIONS ROUTES
        # =============================================================================
        
        @self.app.post("/api/blob-service/store-blend")
        async def storeBlend(
            blend_file: UploadFile = Form(...),
            bucket: str = Form(...),
            key: str = Form(...)
        ):
            """
            Store a Blender (.blend) file in the specified bucket.
            
            Args:
                blend_file: Uploaded blend file
                bucket: Target bucket name
                key: File key/name
            
            Returns:
                JSON response with success/error status
            """
            print(f"Storing blend file: {blend_file.filename}")
            print(f"Bucket: {bucket}")
            print(f"Key: {key}")
            
            # Add .blend extension if not present in key
            if not key.endswith(".blend"):
                key = f"{key}.blend"
            
            # Upload to blob storage
            result = await self.uploadBlendFileToBlobStorage(blend_file, bucket, key)
            
            if "error" in result:
                return JSONResponse(content={"error": result["error"]}, status_code=500)
            
            return JSONResponse(content={
                "message": "Blend file stored successfully",
                "filename": blend_file.filename,
                "bucket": bucket,
                "key": key
            }, status_code=200)

        @self.app.get("/api/blob-service/retrieve-blend")
        async def retrieveBlend(
            bucket: str,
            key: str
        ):
            """
            Retrieve a Blender (.blend) file from the specified bucket.
            
            Args:
                bucket: Source bucket name
                key: File key/name
            
            Returns:
                Blend file with appropriate media type or error response
            """
            try:
                print(f"[INFO] Retrieving blend file from bucket: {bucket}")
                print(f"[INFO] Key: {key}")
                
                # Add .blend extension if not present in key
                if not key.endswith(".blend"):
                    key = f"{key}.blend"
                    print(f"[DEBUG] Appended .blend extension to key. New key: {key}")
                
                # Retrieve from blob storage
                data = await self.retrieveBlendFileFromBlobStorage(bucket, key)
                
                if isinstance(data, dict) and "error" in data:
                    print(f"[ERROR] Error retrieving blend file: {data['error']}")
                    return JSONResponse(content={"error": data["error"]}, status_code=404)
                
                # Return blend file with appropriate media type
                print(f"[INFO] Successfully retrieved blend file: {key} from bucket: {bucket}")
                return Response(content=data, media_type="application/octet-stream")
            except Exception as e:
                import traceback
                print(f"[ERROR] Exception occurred while retrieving blend file: {traceback.format_exc()}")
                return JSONResponse(
                    content={"error": f"Failed to retrieve blend file: {str(e)}"},
                    status_code=500
                )

        @self.app.get("/api/blob-service/retrieve-blend-metadata")
        async def retrieveBlendMetadata(
            bucket: str,
            key: str
        ):
            """
            Retrieve metadata for a Blender (.blend) file without downloading the file.
            
            Args:
                bucket: Source bucket name
                key: File key/name
            
            Returns:
                JSON response with file metadata or error response
            """
            try:
                print(f"[INFO] Retrieving blend file metadata from bucket: {bucket}")
                print(f"[INFO] Key: {key}")
                
                # Add .blend extension if not present in key
                if not key.endswith(".blend"):
                    key = f"{key}.blend"
                    print(f"[DEBUG] Appended .blend extension to key. New key: {key}")
                
                # Retrieve metadata from blob storage
                metadata = await self.retrieveBlendFileMetadataFromBlobStorage(bucket, key)
                
                if isinstance(metadata, dict) and "error" in metadata:
                    print(f"[ERROR] Error retrieving blend file metadata: {metadata['error']}")
                    return JSONResponse(content={"error": metadata["error"]}, status_code=404)
                
                # Return metadata as JSON
                print(f"[INFO] Successfully retrieved blend file metadata: {key} from bucket: {bucket}")
                return JSONResponse(content=metadata, status_code=200)
            except Exception as e:
                import traceback
                print(f"[ERROR] Exception occurred while retrieving blend file metadata: {traceback.format_exc()}")
                return JSONResponse(
                    content={"error": f"Failed to retrieve blend file metadata: {str(e)}"},
                    status_code=500
                )
        
        # =============================================================================
        # BUCKET MANAGEMENT ROUTES
        # =============================================================================
        
        @self.app.get("/api/blob-service/list-buckets")
        async def listBuckets():
            """
            List all available buckets in the storage system.
            
            Returns:
                JSON response with list of bucket names and count
            """
            try:
                response = self.client.list_buckets()
                buckets = [bucket['Name'] for bucket in response['Buckets']]
                return JSONResponse(content={
                    "buckets": buckets,
                    "count": len(buckets),
                    "message": "Buckets retrieved successfully"
                }, status_code=200)
            except Exception as e:
                return JSONResponse(content={
                    "error": f"Failed to list buckets: {str(e)}"
                }, status_code=500)
        
        @self.app.post("/api/blob-service/create-bucket")
        async def createBucket(bucket_name: str = Form(...)):
            """
            Create a new bucket in the storage system.
            
            Args:
                bucket_name: Name of the bucket to create
            
            Returns:
                JSON response with success/error status
            """
            try:
                bucket_created = await self.ensure_bucket_exists(bucket_name)
                if bucket_created:
                    return JSONResponse(content={
                        "message": f"Bucket '{bucket_name}' created successfully or already exists",
                        "bucket_name": bucket_name
                    }, status_code=200)
                else:
                    return JSONResponse(content={
                        "error": f"Failed to create bucket '{bucket_name}'"
                    }, status_code=500)
            except Exception as e:
                return JSONResponse(content={
                    "error": f"Failed to create bucket: {str(e)}"
                }, status_code=500)

        # =============================================================================
        # TEMPORARY FILE OPERATIONS ROUTES
        # =============================================================================
        
        @self.app.post("/api/blob-service/store-temp")
        async def storeTemp(
            file: UploadFile = Form(...),
            key: str = Form(...)
        ):
            """
            Store any file in the temp bucket with the given key.
            
            Args:
                file: Uploaded file
                key: File key/name (including extension)
            
            Returns:
                JSON response with success/error status
            """
            print(f"Storing file in temp bucket: {file.filename}")
            print(f"Key: {key}")
            
            # Upload to temp bucket
            result = await self.uploadFileToTempBucket(file, key)
            
            if "error" in result:
                return JSONResponse(content={"error": result["error"]}, status_code=500)
            
            return JSONResponse(content={
                "message": "File stored successfully in temp bucket",
                "filename": file.filename,
                "key": key,
                "bucket": "temp"
            }, status_code=200)

        @self.app.get("/api/blob-service/retrieve-temp")
        async def retrieveTemp(key: str):
            """
            Retrieve file from temp bucket using the key.
            
            Args:
                key: File key/name
            
            Returns:
                File with appropriate media type or error response
            """
            print(f"Retrieving file from temp bucket")
            print(f"Key: {key}")
            
            # Retrieve from temp bucket
            data = await self.retrieveFileFromTempBucket(key)
            
            if isinstance(data, dict) and "error" in data:
                return JSONResponse(content={"error": data["error"]}, status_code=404)
            
            # Determine media type based on file extension
            media_type = "application/octet-stream"  # Default
            if key.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                media_type = "image/" + key.split('.')[-1].lower()
            elif key.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                media_type = "video/" + key.split('.')[-1].lower()
            elif key.lower().endswith(('.pdf')):
                media_type = "application/pdf"
            elif key.lower().endswith(('.txt')):
                media_type = "text/plain"
            elif key.lower().endswith(('.json')):
                media_type = "application/json"
            
            return Response(content=data, media_type=media_type)

        @self.app.delete("/api/blob-service/delete-temp")
        async def deleteTemp(key: str):
            """
            Delete file from temp bucket using the key.
            
            Args:
                key: File key/name to delete
            
            Returns:
                JSON response with success/error status
            """
            print(f"Deleting file from temp bucket")
            print(f"Key: {key}")
            
            # Delete from temp bucket
            result = await self.deleteFileFromTempBucket(key)
            
            if "error" in result:
                return JSONResponse(content={"error": result["error"]}, status_code=500)
            
            return JSONResponse(content={
                "message": "File deleted successfully from temp bucket",
                "key": key,
                "bucket": "temp"
            }, status_code=200)

        # =============================================================================
        # SIGNED URL OPERATIONS ROUTES
        # =============================================================================
        
        @self.app.get("/api/blob-service/generate-signed-url")
        async def generateSignedUrl(
            bucket: str,
            key: str,
            expiration: int = 3600
        ):
            """
            Generate a signed URL for accessing a file in blob storage.
            
            Args:
                bucket: Source bucket name
                key: File key/name
                expiration: URL expiration time in seconds (default: 3600 = 1 hour)
            
            Returns:
                JSON response with signed URL or error response
            """
            try:
                print(f"[INFO] Generating signed URL for bucket: {bucket}, key: {key}")
                print(f"[INFO] Expiration: {expiration} seconds")
                
                # Generate signed URL
                signed_url = await self.generateSignedUrlForBlobStorage(bucket, key, expiration)
                
                if isinstance(signed_url, dict) and "error" in signed_url:
                    print(f"[ERROR] Error generating signed URL: {signed_url['error']}")
                    return JSONResponse(content={"error": signed_url["error"]}, status_code=500)
                
                print(f"[INFO] Successfully generated signed URL for: {key} in bucket: {bucket}")
                return JSONResponse(content={
                    "signed_url": signed_url,
                    "bucket": bucket,
                    "key": key,
                    "expiration_seconds": expiration,
                    "message": "Signed URL generated successfully"
                }, status_code=200)
            except Exception as e:
                import traceback
                print(f"[ERROR] Exception occurred while generating signed URL: {traceback.format_exc()}")
                return JSONResponse(
                    content={"error": f"Failed to generate signed URL: {str(e)}"},
                    status_code=500
                )

        # =============================================================================
        # FRAMES ZIP OPERATIONS ROUTES
        # =============================================================================
        @self.app.post("/api/blob-service/store-frames-zip")
        async def storeFramesZip(
            file: UploadFile = Form(...),
            key: str = Form(...)
        ):
            """
            Store a ZIP file containing rendered frames for a particular blend object.

            Args:
                file: Uploaded zip file (should be .zip)
                key: Desired storage key (without or with .zip extension)

            Returns:
                JSON response with success or error status.
            """
            print(f"Storing frames zip file upload received: {file.filename}")
            print(f"Provided key/prefix: '{key}'")

            # Validate uploaded file extension
            if not file.filename.lower().endswith('.zip'):
                return JSONResponse(content={"error": "Uploaded file must be a .zip archive"}, status_code=400)

            # Normalize key so the stored object is ALWAYS named 'frames.zip'
            prefix = (key or '').strip()
            if prefix in ('', '.', '/'):  # no meaningful prefix
                final_key = 'frames.zip'
            else:
                # Remove leading slashes
                while prefix.startswith('/'):
                    prefix = prefix[1:]
                # If user supplied a file name, replace it with frames.zip
                if prefix.endswith('/'):
                    final_key = f"{prefix}frames.zip"
                else:
                    # Decide if last segment looks like a file name (has a dot)
                    if '.' in prefix.split('/')[-1]:
                        # Replace last segment with frames.zip
                        parts = prefix.split('/')[:-1]
                        if parts:
                            final_key = '/'.join(parts) + '/frames.zip'
                        else:
                            final_key = 'frames.zip'
                    else:
                        # Treat as folder path
                        final_key = f"{prefix}/frames.zip"

            print(f"Normalized storage key: {final_key}")

            result = await self.uploadFramesZipToBlobStorage(file, final_key)
            if "error" in result:
                return JSONResponse(content={"error": result["error"]}, status_code=500)

            return JSONResponse(content={
                "message": "Frames zip stored successfully",
                "filename": file.filename,
                "key": final_key,
                "bucket": "frames-zip"
            }, status_code=200)

        @self.app.get("/api/blob-service/retrieve-frames-zip")
        async def retrieveFramesZip(key: str):
            """
            Retrieve a ZIP archive of frames by key from the frames-zip bucket.

            Args:
                key: Storage key (with or without .zip extension)

            Returns:
                Streaming response / file bytes
            """
            print(f"Retrieving frames zip with supplied key/prefix: {key}")

            supplied = key.strip()
            if supplied in ('', '.', '/'):  # default
                final_key = 'frames.zip'
            else:
                if supplied.endswith('/'):
                    final_key = f"{supplied}frames.zip"
                else:
                    # If last segment has a dot and isn't frames.zip, replace with frames.zip
                    last = supplied.split('/')[-1]
                    if last.lower() == 'frames.zip':
                        final_key = supplied
                    elif '.' in last:  # treat as file name to replace
                        parts = supplied.split('/')[:-1]
                        if parts:
                            final_key = '/'.join(parts) + '/frames.zip'
                        else:
                            final_key = 'frames.zip'
                    else:
                        final_key = f"{supplied}/frames.zip"

            print(f"Resolved retrieval key: {final_key}")

            data = await self.retrieveFramesZipFromBlobStorage(final_key)
            if isinstance(data, dict) and "error" in data:
                return JSONResponse(content={"error": data["error"]}, status_code=404)

            headers = {
                "Content-Disposition": f"attachment; filename=\"frames.zip\""
            }
            return Response(content=data, media_type="application/zip", headers=headers)

        @self.app.post("/api/blob-service/store-rendered-images-as-zip")
        async def api_store_rendered_images_zip(
            bucket: str = Form(...),
            prefix: str = Form(...),
        ):
            """
            API endpoint to zip all images under a prefix in a bucket and upload to zip_bucket/zip_key.
            If zip_key is not provided, it will be prefix+'.zip' in the zip_bucket.
            """
            try:
                result = await self.store_rendered_images_to_zip(bucket, prefix)
                return JSONResponse(content=result, status_code=200)
            except Exception as e:
                return JSONResponse(content={"error": str(e)}, status_code=500)
        

        # =============================================================================
        # DELETE OPERATIONS ROUTES
        # =============================================================================
        
        @self.app.delete("/api/blob-service/delete-key")
        async def deleteKey(
            bucket: str,
            key: str
        ):
            """
            Delete a key (file or folder) from the specified bucket.
            If the key is a folder, all objects within that folder will be deleted.
            
            Args:
                bucket: Source bucket name
                key: File key/name or folder path to delete
            
            Returns:
                JSON response with success/error status and deletion summary
            """
            try:
                print(f"[INFO] Deleting key from bucket: {bucket}")
                print(f"[INFO] Key: {key}")
                
                # Delete from blob storage
                result = await self.deleteKeyFromBlobStorage(bucket, key)
                
                if "error" in result:
                    print(f"[ERROR] Error deleting key: {result['error']}")
                    return JSONResponse(content={"error": result["error"]}, status_code=500)
                
                print(f"[INFO] Successfully deleted key: {key} from bucket: {bucket}")
                return JSONResponse(content={
                    "message": "Key deleted successfully",
                    "bucket": bucket,
                    "key": key,
                    "deleted_objects": result.get("deleted_objects", []),
                    "total_deleted": result.get("total_deleted", 0)
                }, status_code=200)
            except Exception as e:
                import traceback
                print(f"[ERROR] Exception occurred while deleting key: {traceback.format_exc()}")
                return JSONResponse(
                    content={"error": f"Failed to delete key: {str(e)}"},
                    status_code=500
                )


    # =============================================================================
    # BLOB STORAGE OPERATION METHODS
    # =============================================================================
    
    # =============================================================================
    # IMAGE STORAGE OPERATIONS
    # =============================================================================
    
    async def uploadImageToBlobStorage(self, image: UploadFile, bucket: str, key: str):
        """
        Upload an image file to blob storage.
        
        Args:
            image: Uploaded image file
            bucket: Target bucket name
            key: File key/name
            
        Returns:
            dict: Success response with filename or error response
        """
        print(image)
        try:
            # Ensure bucket exists before uploading
            bucket_created = await self.ensure_bucket_exists(bucket)
            if not bucket_created:
                return {"error": f"Failed to create bucket '{bucket}'"}
            
            contents = await image.read()
            self.client.put_object(Bucket=bucket, Key=key, Body=contents)
            return {"filename": image.filename}
        except Exception as e:
            return {"error": str(e)}
        
    async def retrieveImageFromBlobStorage(self, bucket: str, key: str):
        """
        Retrieve an image file from blob storage.

        Args:
            bucket: Source bucket name
            key: File key/name

        Returns:
            bytes: Image data or dict with error
        """
        try:
            # Ensure bucket exists before retrieving
            bucket_created = await self.ensure_bucket_exists(bucket)
            if not bucket_created:
                return {"error": f"Failed to create bucket '{bucket}'"}
            
            response = self.client.get_object(Bucket=bucket, Key=key)
            data = response['Body'].read()
            print(type(data))
            return data
        except Exception as e:
            return {"error": str(e)}

    # =============================================================================
    # BLEND FILE STORAGE OPERATIONS
    # =============================================================================
    
    async def uploadBlendFileToBlobStorage(self, blend_file: UploadFile, bucket: str, key: str):
        """
        Upload a Blender (.blend) file to blob storage.
        
        Args:
            blend_file: Uploaded blend file
            bucket: Target bucket name
            key: File key/name
            
        Returns:
            dict: Success response with filename or error response
        """
        print(blend_file)
        try:
            # Ensure bucket exists before uploading
            bucket_created = await self.ensure_bucket_exists(bucket)
            if not bucket_created:
                return {"error": f"Failed to create bucket '{bucket}'"}
            
            contents = await blend_file.read()
            self.client.put_object(Bucket=bucket, Key=key, Body=contents)
            return {"filename": blend_file.filename}
        except Exception as e:
            return {"error": str(e)}
        
    async def retrieveBlendFileFromBlobStorage(self, bucket: str, key: str):
        """
        Retrieve a Blender (.blend) file from blob storage.
        
        Args:
            bucket: Source bucket name
            key: File key/name
            
        Returns:
            bytes: Blend file data or dict with error
        """
        try:
            print(f"[INFO] Attempting to retrieve blend file from bucket: {bucket}, key: {key}")
            # Ensure bucket exists before retrieving
            bucket_created = await self.ensure_bucket_exists(bucket)
            if not bucket_created:
                print(f"[ERROR] Failed to create or access bucket: {bucket}")
                return {"error": f"Failed to create bucket '{bucket}'"}
            
            print(f"[INFO] Bucket '{bucket}' exists. Proceeding to get object with key '{key}'")
            response = self.client.get_object(Bucket=bucket, Key=key)
            data = response['Body'].read()
            print(f"[INFO] Successfully retrieved blend file. Data type: {type(data)}")
            return data
        except Exception as e:
            print(f"[ERROR] Exception occurred while retrieving blend file from bucket '{bucket}', key '{key}': {str(e)}")
            return {"error": str(e)}

    async def retrieveBlendFileMetadataFromBlobStorage(self, bucket: str, key: str):
        """
        Retrieve metadata for a Blender (.blend) file without downloading the file content.
        
        Args:
            bucket: Source bucket name
            key: File key/name
            
        Returns:
            dict: File metadata including size, timestamps, etc. or error response
        """
        try:
            print(f"[INFO] Attempting to retrieve blend file metadata from bucket: {bucket}, key: {key}")
            # Ensure bucket exists before retrieving
            bucket_created = await self.ensure_bucket_exists(bucket)
            if not bucket_created:
                print(f"[ERROR] Failed to create or access bucket: {bucket}")
                return {"error": f"Failed to create bucket '{bucket}'"}
            
            print(f"[INFO] Bucket '{bucket}' exists. Proceeding to get object metadata with key '{key}'")
            
            # Get object metadata using head_object (doesn't download the file content)
            response = self.client.head_object(Bucket=bucket, Key=key)
            
            # Extract relevant metadata
            metadata = {
                "bucket": bucket,
                "key": key,
                "filename": key.split('/')[-1],  # Get filename from key
                "size_bytes": response.get('ContentLength', 0),
                "last_modified": response.get('LastModified', '').isoformat() if response.get('LastModified') else None,
                "content_type": response.get('ContentType', 'application/octet-stream'),
                "etag": response.get('ETag', '').strip('"'),  # Remove quotes from ETag
                "storage_class": response.get('StorageClass', 'STANDARD'),
                "metadata": response.get('Metadata', {}),
                "server_side_encryption": response.get('ServerSideEncryption'),
                "version_id": response.get('VersionId'),
                "exists": True
            }
            
            # Calculate human-readable file size
            size_bytes = metadata["size_bytes"]
            if size_bytes < 1024:
                metadata["size_human"] = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                metadata["size_human"] = f"{size_bytes / 1024:.2f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                metadata["size_human"] = f"{size_bytes / (1024 * 1024):.2f} MB"
            else:
                metadata["size_human"] = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
            
            print(f"[INFO] Successfully retrieved blend file metadata. Size: {metadata['size_human']}")
            return metadata
        except Exception as e:
            print(f"[ERROR] Exception occurred while retrieving blend file metadata from bucket '{bucket}', key '{key}': {str(e)}")
            return {"error": str(e)}

    # =============================================================================
    # TEMPORARY FILE STORAGE OPERATIONS
    # =============================================================================
    
    async def uploadFileToTempBucket(self, file: UploadFile, key: str):
        """
        Upload any file to the temp bucket with the given key.
        
        Args:
            file: Uploaded file
            key: File key/name
            
        Returns:
            dict: Success response with filename and key or error response
        """
        try:
            # Ensure temp bucket exists
            bucket_created = await self.ensure_bucket_exists("temp")
            if not bucket_created:
                return {"error": "Failed to create temp bucket"}
            
            contents = await file.read()
            self.client.put_object(Bucket="temp", Key=key, Body=contents)
            return {"filename": file.filename, "key": key}
        except Exception as e:
            return {"error": str(e)}
    
    async def retrieveFileFromTempBucket(self, key: str):
        """
        Retrieve any file from the temp bucket using the key.
        
        Args:
            key: File key/name
            
        Returns:
            bytes: File data or dict with error
        """
        try:
            # Ensure temp bucket exists
            bucket_created = await self.ensure_bucket_exists("temp")
            if not bucket_created:
                return {"error": "Failed to create temp bucket"}
            
            response = self.client.get_object(Bucket="temp", Key=key)
            data = response['Body'].read()
            return data
        except Exception as e:
            return {"error": str(e)}
    
    async def deleteFileFromTempBucket(self, key: str):
        """
        Delete any file from the temp bucket using the key.
        
        Args:
            key: File key/name to delete
            
        Returns:
            dict: Success message or error response
        """
        try:
            # Ensure temp bucket exists
            bucket_created = await self.ensure_bucket_exists("temp")
            if not bucket_created:
                return {"error": "Failed to create temp bucket"}
            
            self.client.delete_object(Bucket="temp", Key=key)
            return {"message": f"File '{key}' deleted successfully from temp bucket"}
        except Exception as e:
            return {"error": str(e)}

    # =============================================================================
    # FRAMES ZIP STORAGE OPERATIONS
    # =============================================================================
    async def uploadFramesZipToBlobStorage(self, file: UploadFile, key: str):
        """
        Upload a frames zip archive to the frames-zip bucket.

        Args:
            file: Uploaded .zip file
            key: Storage key (should end with .zip)

        Returns:
            dict: Success response with filename/key or error
        """
        try:
            bucket_created = await self.ensure_bucket_exists("frames-zip")
            if not bucket_created:
                return {"error": "Failed to create frames-zip bucket"}
            contents = await file.read()
            self.client.put_object(Bucket="frames-zip", Key=key, Body=contents, ContentType="application/zip")
            return {"filename": file.filename, "key": key}
        except Exception as e:
            return {"error": str(e)}

    async def retrieveFramesZipFromBlobStorage(self, key: str):
        """
        Retrieve a frames zip archive from the frames-zip bucket.

        Args:
            key: Storage key (expects .zip)

        Returns:
            bytes or dict with error
        """
        try:
            bucket_created = await self.ensure_bucket_exists("frames-zip")
            if not bucket_created:
                return {"error": "Failed to create frames-zip bucket"}
            response = self.client.get_object(Bucket="frames-zip", Key=key)
            return response['Body'].read()
        except Exception as e:
            return {"error": str(e)}
    async def store_rendered_images_to_zip(self, bucket: str, prefix: str):
        try:
            zipStreamingObj = zipstream.ZipFile(mode="w", compression=zipstream.ZIP_DEFLATED)
        except Exception as e:
            raise Exception(f"Failed to initialize zip stream: {str(e)}")

        try:
            object_keys = await self.listObjectsWithPrefix(bucket, prefix)
            if isinstance(object_keys, dict) and "error" in object_keys:
                raise Exception(object_keys["error"])
            if not object_keys:
                raise Exception("No images found for the given prefix.")
        except Exception as e:
            raise Exception(f"Failed to list objects with prefix '{prefix}' in bucket '{bucket}': {str(e)}")

        try:
            for objs in object_keys:
                try:
                    response = self.client.get_object(Bucket=bucket, Key=objs)
                    body_stream = response["Body"].iter_chunks(chunk_size=8192)
                    zipStreamingObj.write_iter(objs.split("/")[-1], body_stream)
                except Exception as e:
                    raise Exception(f"Failed to retrieve or add object '{objs}' to zip: {str(e)}")
        except Exception as e:
            raise Exception(f"Error during zip creation for prefix '{prefix}': {str(e)}")

        print("storing the zip now...")

        try:
            # Inline generator->file-like wrapper
            class _GenReader(io.RawIOBase):
                def __init__(self, gen):
                    self._iter = iter(gen)
                    self._buffer = b""

                def readable(self):
                    return True

                def readinto(self, b):
                    while not self._buffer:
                        try:
                            self._buffer = next(self._iter)
                        except StopIteration:
                            return 0  # EOF
                    n = min(len(b), len(self._buffer))
                    b[:n] = self._buffer[:n]
                    self._buffer = self._buffer[n:]
                    return n

            stream_wrapper = io.BufferedReader(_GenReader(zipStreamingObj))

            # Ensure frames-zip bucket exists
            bucket_created = await self.ensure_bucket_exists("frames-zip")
            if not bucket_created:
                raise Exception("Failed to create or access frames-zip bucket")

            # Upload streaming zip to S3/MinIO
            self.client.upload_fileobj(
                Fileobj=stream_wrapper,
                Bucket="frames-zip",
                Key=f"{prefix.strip('/')}/frames.zip",
                ExtraArgs={"ContentType": "application/zip"}
            )
        except Exception as e:
            raise Exception(f"Failed to upload zip file for prefix '{prefix}': {str(e)}")

        print(f"✅ Stored {prefix.strip('/')}.zip in frames-zip bucket")
        
        return {
            "bucket": "frames-zip",
            "key": f"{prefix.strip('/')}/frames.zip",
        }
    # =============================================================================
    # SIGNED URL OPERATIONS
    # =============================================================================
    
    async def generateSignedUrlForBlobStorage(self, bucket: str, key: str, expiration: int = 3600):
        """
        Generate a signed URL for accessing a file in blob storage.
        
        Args:
            bucket: Source bucket name
            key: File key/name
            expiration: URL expiration time in seconds (default: 3600 = 1 hour)
            
        Returns:
            str: Signed URL or dict with error
        """
        try:
            print(f"[INFO] Attempting to generate signed URL for bucket: {bucket}, key: {key}")
            print(f"[INFO] Expiration time: {expiration} seconds")
            
            # Ensure bucket exists before generating signed URL
            bucket_created = await self.ensure_bucket_exists(bucket)
            if not bucket_created:
                print(f"[ERROR] Failed to create or access bucket: {bucket}")
                return {"error": f"Failed to create bucket '{bucket}'"}
            
            print(f"[INFO] Bucket '{bucket}' exists. Proceeding to generate signed URL for key '{key}'")
            
            # Generate presigned URL using boto3
            signed_url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            
            print(f"[INFO] Successfully generated signed URL. URL length: {len(signed_url)} characters")
            return signed_url
        except Exception as e:
            print(f"[ERROR] Exception occurred while generating signed URL for bucket '{bucket}', key '{key}': {str(e)}")
            return {"error": str(e)}

    # =============================================================================
    # DELETE OPERATIONS
    # =============================================================================
    
    async def listObjectsWithPrefix(self, bucket: str, prefix: str):
        """
        List all objects in a bucket that start with the given prefix.
        
        Args:
            bucket: Source bucket name
            prefix: Prefix to filter objects
            
        Returns:
            list: List of object keys or dict with error
        """
        try:
            print(f"[INFO] Listing objects with prefix '{prefix}' in bucket '{bucket}'")
            
            # Ensure bucket exists
            bucket_created = await self.ensure_bucket_exists(bucket)
            if not bucket_created:
                print(f"[ERROR] Failed to create or access bucket: {bucket}")
                return {"error": f"Failed to create bucket '{bucket}'"}
            
            # List objects with the given prefix
            paginator = self.client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix)
            
            objects = []
            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects.append(obj['Key'])
            
            print(f"[INFO] Found {len(objects)} objects with prefix '{prefix}'")
            return objects
        except Exception as e:
            print(f"[ERROR] Exception occurred while listing objects with prefix '{prefix}' in bucket '{bucket}': {str(e)}")
            return {"error": str(e)}
    
    async def deleteKeyFromBlobStorage(self, bucket: str, key: str):
        """
        Delete a key (file or folder) from blob storage.
        If the key is a folder, all objects within that folder will be deleted.
        
        Args:
            bucket: Source bucket name
            key: File key/name or folder path to delete
            
        Returns:
            dict: Success response with deletion summary or error response
        """
        try:
            print(f"[INFO] Attempting to delete key '{key}' from bucket '{bucket}'")
            
            # Ensure bucket exists
            bucket_created = await self.ensure_bucket_exists(bucket)
            if not bucket_created:
                print(f"[ERROR] Failed to create or access bucket: {bucket}")
                return {"error": f"Failed to create bucket '{bucket}'"}
            
            deleted_objects = []
            total_deleted = 0
            
            # Check if the key ends with '/' to determine if it's a folder
            if key.endswith('/'):
                # It's a folder - delete all objects with this prefix
                print(f"[INFO] Key '{key}' appears to be a folder. Listing all objects with this prefix.")
                
                # List all objects with this prefix
                objects_result = await self.listObjectsWithPrefix(bucket, key)
                
                if isinstance(objects_result, dict) and "error" in objects_result:
                    return objects_result
                
                objects_to_delete = objects_result
                
                if not objects_to_delete:
                    print(f"[WARNING] No objects found with prefix '{key}'")
                    return {
                        "message": f"No objects found with prefix '{key}'",
                        "deleted_objects": [],
                        "total_deleted": 0
                    }
                
                print(f"[INFO] Found {len(objects_to_delete)} objects to delete")
                
                # Delete all objects with this prefix
                for obj_key in objects_to_delete:
                    try:
                        self.client.delete_object(Bucket=bucket, Key=obj_key)
                        deleted_objects.append(obj_key)
                        total_deleted += 1
                        print(f"[INFO] Deleted object: {obj_key}")
                    except Exception as e:
                        print(f"[ERROR] Failed to delete object '{obj_key}': {str(e)}")
                        # Continue with other objects even if one fails
                
            else:
                # It's a single file - try to delete it directly
                print(f"[INFO] Key '{key}' appears to be a single file. Attempting direct deletion.")
                
                try:
                    # First check if the object exists
                    self.client.head_object(Bucket=bucket, Key=key)
                    
                    # Delete the object
                    self.client.delete_object(Bucket=bucket, Key=key)
                    deleted_objects.append(key)
                    total_deleted = 1
                    print(f"[INFO] Successfully deleted file: {key}")
                    
                except Exception as e:
                    # If direct deletion fails, check if it might be a folder without trailing slash
                    print(f"[WARNING] Direct deletion failed for '{key}': {str(e)}")
                    print(f"[INFO] Checking if '{key}' might be a folder without trailing slash...")
                    
                    # Try to list objects with this key as prefix
                    folder_prefix = key + '/'
                    objects_result = await self.listObjectsWithPrefix(bucket, folder_prefix)
                    
                    if isinstance(objects_result, dict) and "error" in objects_result:
                        return objects_result
                    
                    objects_to_delete = objects_result
                    
                    if objects_to_delete:
                        print(f"[INFO] Found {len(objects_to_delete)} objects with prefix '{folder_prefix}'. Deleting them.")
                        
                        # Delete all objects with this prefix
                        for obj_key in objects_to_delete:
                            try:
                                self.client.delete_object(Bucket=bucket, Key=obj_key)
                                deleted_objects.append(obj_key)
                                total_deleted += 1
                                print(f"[INFO] Deleted object: {obj_key}")
                            except Exception as e:
                                print(f"[ERROR] Failed to delete object '{obj_key}': {str(e)}")
                    else:
                        # No objects found, return error
                        return {"error": f"Object '{key}' not found in bucket '{bucket}'"}
            
            print(f"[INFO] Deletion completed. Total objects deleted: {total_deleted}")
            return {
                "message": f"Successfully deleted {total_deleted} object(s)",
                "deleted_objects": deleted_objects,
                "total_deleted": total_deleted
            }
            
        except Exception as e:
            print(f"[ERROR] Exception occurred while deleting key '{key}' from bucket '{bucket}': {str(e)}")
            return {"error": str(e)}

    # =============================================================================
    # SERVER LIFECYCLE METHODS
    # =============================================================================
    
    async def run_app(self):
        """
        Start the FastAPI server with uvicorn.
        
        Returns:
            None
        """
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


# =============================================================================
# HELPER CLASSES
# =============================================================================

class Data():
    """
    Data class for storing service state and metadata.
    Currently contains placeholders for image metadata and storage statistics.
    """
    def __init__(self):
        """Initialize data storage containers"""
        self.uploadedImages = {}
        self.imageMetadata = {}
        self.storageStats = {}

    def get_value(self):
        """Get value from data storage (placeholder implementation)"""
        pass

    def set_value(self, value):
        """Set value in data storage (placeholder implementation)"""
        pass


class Service():
    """
    Main service class that orchestrates the HTTP server and service lifecycle.
    """
    def __init__(self, httpServer=None):
        """
        Initialize the service with an HTTP server instance.
        
        Args:
            httpServer: HTTP_SERVER instance
        """
        self.httpServer = httpServer

    async def startService(self):
        """
        Start the service by configuring routes and running the HTTP server.
        
        Returns:
            None
        """
        await self.httpServer.configure_routes()
        await self.httpServer.run_app()


# =============================================================================
# SERVICE STARTUP AND MAIN EXECUTION
# =============================================================================

async def start_service():
    """
    Initialize and start the blob service.
    
    This function sets up the data class, HTTP server configuration,
    and starts the service.
    
    Returns:
        None
    """
    # Initialize data storage
    dataClass = Data()

    # Server configuration
    httpServerPort = 13000
    httpServerHost = "127.0.0.1"
    httpServerPrivilegedIpAddress = ["127.0.0.1"]

    # Create HTTP server instance
    http_server = HTTP_SERVER(
        httpServerHost=httpServerHost, 
        httpServerPort=httpServerPort, 
        httpServerPrivilegedIpAddress=httpServerPrivilegedIpAddress, 
        data_class_instance=dataClass
    )

    # Create and start service
    service = Service(http_server)
    await service.startService()


if __name__ == "__main__":
    """
    Main entry point for the blob service.
    Starts the service using asyncio event loop.
    """
    asyncio.run(start_service())