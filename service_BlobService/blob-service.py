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
            endpoint_url="http://localhost:3000",
            aws_access_key_id="admin",
            aws_secret_access_key="password",
            config=Config(signature_version="s3v4"),
            region_name="us-east-1"
        )

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
            print(f"Retrieving blend file from bucket: {bucket}")
            print(f"Key: {key}")
            
            # Add .blend extension if not present in key
            if not key.endswith(".blend"):
                key = f"{key}.blend"
            
            # Retrieve from blob storage
            data = await self.retrieveBlendFileFromBlobStorage(bucket, key)
            
            if isinstance(data, dict) and "error" in data:
                return JSONResponse(content={"error": data["error"]}, status_code=404)
            
            # Return blend file with appropriate media type
            return Response(content=data, media_type="application/octet-stream")

    async def uploadImageToBlobStorage(self, image: UploadFile, bucket: str, key: str):
        print(image)
        try:
            contents = await image.read()
            self.client.put_object(Bucket=bucket, Key=key, Body=contents)
            return {"filename": image.filename}
        except Exception as e:
            return {"error": str(e)}
        
    async def retrieveImageFromBlobStorage(self, bucket: str, key: str):
        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            data = response['Body'].read()
            print(type(data))
            return data
        except Exception as e:
            return {"error": str(e)}

    async def uploadBlendFileToBlobStorage(self, blend_file: UploadFile, bucket: str, key: str):
        print(blend_file)
        try:
            contents = await blend_file.read()
            self.client.put_object(Bucket=bucket, Key=key, Body=contents)
            return {"filename": blend_file.filename}
        except Exception as e:
            return {"error": str(e)}
        
    async def retrieveBlendFileFromBlobStorage(self, bucket: str, key: str):
        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            data = response['Body'].read()
            print(type(data))
            return data
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
    httpServerHost = "0.0.0.0"

    httpServerPrivilegedIpAddress = ["127.0.0.1"]

    http_server = HTTP_SERVER(httpServerHost=httpServerHost, httpServerPort=httpServerPort, httpServerPrivilegedIpAddress=httpServerPrivilegedIpAddress, data_class_instance=dataClass)

    service = Service(http_server)
    await service.startService()

if __name__ == "__main__":
    asyncio.run(start_service())