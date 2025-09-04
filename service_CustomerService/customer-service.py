import asyncio

from fastapi import FastAPI, Response, Request, HTTPException, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from fastapi.responses import JSONResponse

import uvicorn
import httpx
import json
from datetime import datetime
import uuid
import hashlib
import secrets

import asyncio
import aio_pika

from customerAgent import customerAgent


import sys
import os

from dotenv import load_dotenv
load_dotenv()

# Security scheme for token validation
security = HTTPBearer(auto_error=False)

class HTTP_SERVER():
    def __init__(self, httpServerHost, httpServerPort, httpServerPrivilegedIpAddress=["127.0.0.1"], data_class_instance=None):
        self.app = FastAPI()
        self.host = httpServerHost
        self.port = httpServerPort

        self.privilegedIpAddress = httpServerPrivilegedIpAddress        #<HTTP_SERVER_CORS_ADDITION_START>
        self.app.add_middleware(CORSMiddleware, allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"],)
        #<HTTP_SERVER_CORS_ADDITION_END>
        
        self.data_class = data_class_instance  # Reference to the Data class instance
        
        # Get MongoDB service URL from environment
        env_url = os.getenv("MONGODB_SERVICE", "").strip()
        if not env_url or not (env_url.startswith("http://") or env_url.startswith("https://")):
            self.mongodb_service_url = "http://127.0.0.1:12000"
        else:
            self.mongodb_service_url = env_url
        
        # Get Auth service URL from environment
        auth_env_url = os.getenv("AUTH_SERVICE", "").strip()
        if not auth_env_url or not (auth_env_url.startswith("http://") or auth_env_url.startswith("https://")):
            self.auth_service_url = "http://127.0.0.1:10000"
        else:
            self.auth_service_url = auth_env_url
        
        # Get Blob service URL from environment
        blob_env_url = os.getenv("BLOB_SERVICE", "").strip()
        if not blob_env_url or not (blob_env_url.startswith("http://") or blob_env_url.startswith("https://")):
            self.blob_service_url = "http://127.0.0.1:13000"
        else:
            self.blob_service_url = blob_env_url
        
        # Get Session Supervisor service URL from environment
        session_supervisor_env_url = os.getenv("SESSION_SUPERVISOR_SERVICE", "").strip()
        if not session_supervisor_env_url or not (session_supervisor_env_url.startswith("http://") or session_supervisor_env_url.startswith("https://")):
            self.session_supervisor_service_url = "http://127.0.0.1:7500"
        else:
            self.session_supervisor_service_url = session_supervisor_env_url
        
        # HTTP client for making requests to MongoDB service and Auth service
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def authenticate_token(self, credentials: HTTPAuthorizationCredentials = Depends(security)):
        """
        Middleware function to authenticate the access token (customerId)
        This function will be called before any protected endpoint
        """
        print("Authenticating token... is being processed...")
        if not credentials:
            raise HTTPException(
                status_code=401, 
                detail="Access token required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        

        access_token = credentials.credentials
        print(access_token)
        
        try:
            # Call auth service to validate the customer ID
            response = await self.http_client.post(
                f"{self.auth_service_url}/api/auth-service/authenticate_customer_id",
                json={"customerId": access_token}
            )
            
            if response.status_code == 200:
                auth_result = response.json()
                if auth_result.get("authenticated"):
                    # Token is valid, return the customer ID for use in endpoints
                    return access_token
                else:
                    raise HTTPException(
                        status_code=401, 
                        detail="Invalid access token",
                        headers={"WWW-Authenticate": "Bearer"}
                    )
            else:
                # Auth service error
                raise HTTPException(
                    status_code=503, 
                    detail="Authentication service unavailable"
                )
                
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503, 
                detail=f"Authentication service unavailable: {str(e)}"
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Authentication error: {str(e)}"
            )

    async def getCustomerIdFromAuthorizationHeader(self, access_token: HTTPAuthorizationCredentials = Depends(security)):
        try:
            if not access_token:
                raise HTTPException(
                    status_code=401,
                    detail="Access token missing or invalid",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            return access_token.credentials
        except HTTPException as http_exc:
            raise http_exc
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error extracting access token: {str(e)}"
            )
        

    async def configure_routes(self):

        # @self.app.post("/api/customer-service/test-auth")
        # async def testAuth(
        #     request: Request, 
        #     access_token: str = Depends(self.authenticate_token)
        # ):
        #     print(f"Test Auth endpoint hit for customer: {access_token}")
        #     return JSONResponse(content={
        #         "message": "Authentication successful", 
        #         "customer_id": access_token,
        #         "status": "authorized",
        #         "timestamp": datetime.now().isoformat()
        #     }, status_code=200)
        
        @self.app.post("/api/customer-service/")
        async def handleSessionCreationRequest(request: Request):
            print("Customer Service Root Endpoint Hit")
            return JSONResponse(content={"message": "Customer Service is active"}, status_code=200)
            
        @self.app.post("/api/customer-service/upload-blend-file")
        async def uploadBlendFile(
            blend_file_name: str = Form(...),
            blend_file: UploadFile = File(...),
            # customer_id: str = Form(...),
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader)
        ):
            print(f"Upload blend file endpoint hit for customer: {customer_id}")
            print(f"Blend file name: {blend_file_name}")
            print(f"Blend file size: {blend_file.size} bytes")
            print(f"access token: {access_token}")
            print(f"customer id from authorization header: {customer_id}")
            
            try:
                # Step 1: Create empty blender object in MongoDB
                print("Creating empty blender object in MongoDB...")
                mongo_response = await self.http_client.post(
                    f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/add",
                    json={
                        "customerId": customer_id,
                        "blendFileName": blend_file_name
                    }
                )
                
                if mongo_response.status_code != 201:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to create blender object: {mongo_response.text}"
                    )
                
                mongo_result = mongo_response.json()
                object_id = mongo_result["objectId"]
                print(f"Created blender object with ID: {object_id}")
                
                # Step 2: Store blend file in blob storage
                print("Storing blend file in blob storage...")
                
                # Prepare form data for blob service
                # Using the blend-files bucket with the naming convention: customer_id/object_id/blend_file_name
                
                # Store in blob storage
                # Ensure .blend extension is included in the key for consistency
                if not blend_file_name.endswith('.blend'):
                    blob_key = f"{customer_id}/{object_id}/{blend_file_name}.blend"
                else:
                    blob_key = f"{customer_id}/{object_id}/{blend_file_name}"
                
                blob_response = await self.http_client.post(
                    f"{self.blob_service_url}/api/blob-service/store-blend",
                    data={
                        "bucket": "blend-files",
                        "key": blob_key
                    },
                    files={"blend_file": (blend_file_name, await blend_file.read(), "application/octet-stream")}
                )
                
                if blob_response.status_code != 200:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to store blend file in blob storage: {blob_response.text}"
                    )
                
                blob_result = blob_response.json()
                print(f"Blend file stored successfully: {blob_result}")
                
                # Step 3: Update MongoDB object with blend file path
                print("Updating MongoDB object with blend file path...")
                # Ensure .blend extension is included in the path for easier retrieval
                if not blend_file_name.endswith('.blend'):
                    blend_file_path = f"{customer_id}/{object_id}/{blend_file_name}.blend"
                else:
                    blend_file_path = f"{customer_id}/{object_id}/{blend_file_name}"
                
                update_response = await self.http_client.put(
                    f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/update-blend-file",
                    json={
                        "objectId": object_id,
                        "customerId": customer_id,
                        "blendFilePath": blend_file_path
                    }
                )
                
                if update_response.status_code != 200:
                    print(f"Warning: Failed to update blend file path: {update_response.text}")
                    # Continue anyway as the file is stored
                
                # Return success response
                return JSONResponse(content={
                    "message": "Blend file uploaded successfully",
                    "customer_id": customer_id,
                    "object_id": object_id,
                    "file_name": blend_file_name,
                    "file_size_bytes": blend_file.size,
                    "upload_timestamp": datetime.now().isoformat(),
                    "status": "uploaded"
                }, status_code=200)
                
            except HTTPException:
                raise
            except Exception as e:
                print(f"Error uploading blend file: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload blend file: {str(e)}"
                )

        @self.app.post("/api/customer-service/start-workload")
        async def startWorkload(
            request: Request, 
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader),
            object_id: str = Form(...)
        ):
            try:
                print(f"Redirecting start-workload request to session supervisor service for customer: {customer_id}")
                
                # Forward the request to session supervisor service with form data
                response = await self.http_client.post(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/start-workload",
                    data={
                        "customer_id": customer_id,
                        "object_id": object_id
                    }
                )
                
                # Return the response directly to the client
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code
                )
                
            except httpx.RequestError as e:
                print(f"Error connecting to session supervisor service: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail="Session supervisor service unavailable"
                )
            except HTTPException:
                raise
            except Exception as e:
                import traceback
                print(f"Error in startWorkload: {traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

        @self.app.post("/api/customer-service/get-workload-status")
        async def getWorkloadStatus(
            request: Request, 
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader)
        ):
            try:
                print(f"Redirecting get-workload-status request to session supervisor service for customer: {customer_id}")
                
                # Forward the request to session supervisor service with form data
                response = await self.http_client.post(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-workload-status",
                    data={"customer_id": customer_id}
                )
                
                # Return the response directly to the client
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code
                )
                
            except httpx.RequestError as e:
                print(f"Error connecting to session supervisor service: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail="Session supervisor service unavailable"
                )
            except HTTPException:
                raise
            except Exception as e:
                import traceback
                print(f"Error in getWorkloadStatus: {traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

        @self.app.post("/api/customer-service/stop-and-delete-workload")
        async def getWorkloadResults(
            request: Request, 
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader)
        ):
            try:
                print(f"Redirecting stop-and-delete-workload request to session supervisor service for customer: {customer_id}")
                
                # Forward the request to session supervisor service with form data
                response = await self.http_client.post(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/stop-and-delete-workload",
                    data={"customer_id": customer_id}
                )
                
                # Return the response directly to the client
                return JSONResponse(
                    content=response.json(),
                    status_code=response.status_code
                )
                
            except httpx.RequestError as e:
                print(f"Error connecting to session supervisor service: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail="Session supervisor service unavailable"
                )
            except HTTPException:
                raise
            except Exception as e:
                import traceback
                print(f"Error in stopAndDeleteWorkload: {traceback.format_exc()}")
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
                
        @self.app.get("/api/customer-service/get-blend-file/{object_id}")
        async def getBlendFile(
            object_id: str,
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader)
        ):
            print(f"Get blend file endpoint hit for customer: {customer_id}")
            print(f"Requested object ID: {object_id}")
            
            try:
                # Step 1: Get the blend file path from MongoDB
                print("Retrieving blend file path from MongoDB...")
                mongo_response = await self.http_client.get(
                    f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/get-blend-file-name/{object_id}",
                    params={"customer_id": access_token}
                )
                
                if mongo_response.status_code != 200:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Blend file not found: {mongo_response.text}"
                    )
                
                mongo_result = mongo_response.json()
                print(mongo_result)
                blend_file_path = mongo_result.get("blendFilePath")
                
                if not blend_file_path:
                    raise HTTPException(
                        status_code=404,
                        detail="Blend file path not found in database"
                    )
                
                print(f"Found blend file path: {blend_file_path}")
                
                # Step 2: Extract bucket and key from the path
                # Path format: customer_id/object_id/filename.blend
                path_parts = blend_file_path.split('/')
                if len(path_parts) != 3:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Invalid blend file path format: {blend_file_path}"
                    )
                
                bucket = "blend-files"  # Fixed bucket for blend files
                key = blend_file_path
                
                print(f"Retrieving from bucket: {bucket}, key: {key}")
                
                # Step 3: Proxy the response directly from blob service to client
                print(f"Proxying blend file from blob service...")
                
                # Create a streaming response that proxies the blob service
                async def proxy_blend_file():
                    try:
                        async with httpx.AsyncClient() as proxy_client:
                            async with proxy_client.stream(
                                "GET",
                                f"{self.blob_service_url}/api/blob-service/retrieve-blend",
                                params={
                                    "bucket": bucket,
                                    "key": key
                                }
                            ) as response:
                                if response.status_code != 200:
                                    # If blob service fails, we need to handle it differently
                                    error_content = await response.aread()
                                    raise HTTPException(
                                        status_code=response.status_code,
                                        detail=f"Blob service error: {error_content.decode()}"
                                    )
                                
                                # Stream the response directly to the client
                                async for chunk in response.aiter_bytes():
                                    yield chunk
                                
                    except Exception as e:
                        print(f"Error in proxy stream: {str(e)}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to proxy blend file: {str(e)}"
                        )
                
                # Return streaming response with proper headers
                file_name = path_parts[2]  # filename.blend
                print(f"Proxying blend file: {file_name}")
                
                return StreamingResponse(
                    proxy_blend_file(),
                    media_type="application/octet-stream",
                    headers={
                        "Content-Disposition": f"attachment; filename=\"{file_name}\"",
                        "Cache-Control": "no-cache"
                    }
                )
                
            except HTTPException:
                raise
            except Exception as e:
                print(f"Error retrieving blend file: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to retrieve blend file: {str(e)}"
                )
    
        @self.app.get("/api/customer-service/get-rendered-video")
        async def getRenderedVideo(
            request: Request, 
            customer_id: str = Depends(self.authenticate_token)
        ):
            print(f"Get rendered video endpoint hit for customer: {customer_id}")
            # TODO: Implement actual business logic
            return JSONResponse(content={"message": "Get rendered video endpoint", "customer_id": customer_id}, status_code=200)
        
        @self.app.post("/api/customer-service/get-rendered-images")
        async def getRenderedImages(
            request: Request, 
            customer_id: str = Depends(self.authenticate_token)
        ):
            print(f"Get rendered images endpoint hit for customer: {customer_id}")
            # TODO: Implement actual business logic
            return JSONResponse(content={"message": "Get rendered images endpoint", "customer_id": customer_id}, status_code=200)
        


    async def run_app(self):
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()

class Data():
    def __init__(self):
        self.customerAgentMapping = {}

class Service():
    def __init__(self, httpServer = None):
        self.httpServer = httpServer

    async def startService(self):
        await self.httpServer.configure_routes()
        await self.httpServer.run_app()

        
async def start_service():
    dataClass = Data()

    #<HTTP_SERVER_INSTANCE_INTIALIZATION_START>

    #<HTTP_SERVER_PORT_START>
    httpServerPort = 11000
    #<HTTP_SERVER_PORT_END>

    #<HTTP_SERVER_HOST_START>
    httpServerHost = "0.0.0.0"
    #<HTTP_SERVER_HOST_END>

    #<HTTP_SERVER_PRIVILEGED_IP_ADDRESS_START>
    httpServerPrivilegedIpAddress = ["127.0.0.1"]
    #<HTTP_SERVER_PRIVILEGED_IP_ADDRESS_END>

    http_server = HTTP_SERVER(httpServerHost=httpServerHost, httpServerPort=httpServerPort, httpServerPrivilegedIpAddress=httpServerPrivilegedIpAddress, data_class_instance=dataClass)
    #<HTTP_SERVER_INSTANCE_INTIALIZATION_END>

    service = Service(http_server)
    await service.startService()

if __name__ == "__main__":
    asyncio.run(start_service())