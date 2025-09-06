import asyncio
from fastapi import FastAPI, Response, Request, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from fastapi.responses import JSONResponse
import asyncio
import aio_pika
import sys
import os
import boto3
from botocore.client import Config


class HTTP_SERVER():
    def __init__(self, httpServerHost, httpServerPort, httpServerPrivilegedIpAddress=["127.0.0.1"], data_class_instance=None):
        self.app = FastAPI()
        self.host = httpServerHost
        self.port = httpServerPort

        self.privilegedIpAddress = httpServerPrivilegedIpAddress
        #<HTTP_SERVER_CORS_ADDITION_START>
        self.app.add_middleware(CORSMiddleware, allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"],)
        #<HTTP_SERVER_CORS_ADDITION_END>
        
        self.data_class = data_class_instance  # Reference to the Data class instance
        
        # Initialize S3 client
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

    def initialize_default_buckets(self):
        """Initialize default buckets if they don't exist"""
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
        """Ensure a bucket exists, create it if it doesn't"""
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

    async def configure_routes(self):

        @self.app.get("/api/blob-service/")
        async def root():
            return JSONResponse(content={"message": "Blob Service is active"}, status_code=200)

        # 1. Store image with bucket and key
        @self.app.post("/api/blob-service/store-image")
        async def storeImage(
            image: UploadFile = Form(...),
            bucket: str = Form(...),
            key: str = Form(...),
            type: str = Form(default="png")
        ):
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

        # 2. Retrieve image with bucket and key
        @self.app.get("/api/blob-service/retrieve-image")
        async def retrieveImage(
            bucket: str,
            key: str,
            type: str = "png"
        ):
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

        # 3. Store blend file
        @self.app.post("/api/blob-service/store-blend")
        async def storeBlend(
            blend_file: UploadFile = Form(...),
            bucket: str = Form(...),
            key: str = Form(...)
        ):
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

        # 4. Retrieve blend file
        @self.app.get("/api/blob-service/retrieve-blend")
        async def retrieveBlend(
            bucket: str,
            key: str
        ):
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
        
        # 5. List buckets
        @self.app.get("/api/blob-service/list-buckets")
        async def listBuckets():
            """List all available buckets"""
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
        
        # 6. Create bucket
        @self.app.post("/api/blob-service/create-bucket")
        async def createBucket(bucket_name: str = Form(...)):
            """Create a new bucket"""
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

        # 7. Store file in temp bucket
        @self.app.post("/api/blob-service/store-temp")
        async def storeTemp(
            file: UploadFile = Form(...),
            key: str = Form(...)
        ):
            """Store any file in the temp bucket with the given key (including extension)"""
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

        # 8. Retrieve file from temp bucket
        @self.app.get("/api/blob-service/retrieve-temp")
        async def retrieveTemp(key: str):
            """Retrieve file from temp bucket using the key"""
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

        # 9. Delete file from temp bucket
        @self.app.delete("/api/blob-service/delete-temp")
        async def deleteTemp(key: str):
            """Delete file from temp bucket using the key"""
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

    async def uploadImageToBlobStorage(self, image: UploadFile, bucket: str, key: str):
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

    async def uploadBlendFileToBlobStorage(self, blend_file: UploadFile, bucket: str, key: str):
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

    # Temp bucket helper methods
    async def uploadFileToTempBucket(self, file: UploadFile, key: str):
        """Upload any file to the temp bucket with the given key"""
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
        """Retrieve any file from the temp bucket using the key"""
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
        """Delete any file from the temp bucket using the key"""
        try:
            # Ensure temp bucket exists
            bucket_created = await self.ensure_bucket_exists("temp")
            if not bucket_created:
                return {"error": "Failed to create temp bucket"}
            
            self.client.delete_object(Bucket="temp", Key=key)
            return {"message": f"File '{key}' deleted successfully from temp bucket"}
        except Exception as e:
            return {"error": str(e)}

    async def run_app(self):
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


class Data():
    def __init__(self):
        self.uploadedImages = {}
        self.imageMetadata = {}
        self.storageStats = {}

    def get_value(self):
        pass

    def set_value(self, value):
        pass


class Service():
    def __init__(self, httpServer=None):
        self.httpServer = httpServer

    async def startService(self):
        await self.httpServer.configure_routes()
        await self.httpServer.run_app()


async def start_service():
    dataClass = Data()

    httpServerPort = 13000
    httpServerHost = "127.0.0.1"

    httpServerPrivilegedIpAddress = ["127.0.0.1"]

    http_server = HTTP_SERVER(httpServerHost=httpServerHost, httpServerPort=httpServerPort, httpServerPrivilegedIpAddress=httpServerPrivilegedIpAddress, data_class_instance=dataClass)

    service = Service(http_server)
    await service.startService()

if __name__ == "__main__":
    asyncio.run(start_service())