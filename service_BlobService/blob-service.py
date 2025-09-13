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
            default_buckets = ["blend-files", "rendered-videos", "rendered-frames", "temp"]
            
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