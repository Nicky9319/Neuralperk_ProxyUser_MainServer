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
        
        self.blob_storage_base_url = "http://localhost:9000"
        
        # Get Session Supervisor service URL from environment
        session_supervisor_env_url = os.getenv("SESSION_SUPERVISOR_SERVICE", "").strip()
        if not session_supervisor_env_url or not (session_supervisor_env_url.startswith("http://") or session_supervisor_env_url.startswith("https://")):
            self.session_supervisor_service_url = "http://127.0.0.1:7500"
        else:
            self.session_supervisor_service_url = session_supervisor_env_url
        
        # Get User Manager service URL from environment
        user_manager_env_url = os.getenv("USER_MANAGER_SERVICE", "").strip()
        if not user_manager_env_url or not (user_manager_env_url.startswith("http://") or user_manager_env_url.startswith("https://")):
            self.user_manager_service_url = "http://127.0.0.1:7000"
        else:
            self.user_manager_service_url = user_manager_env_url
        
        # HTTP client for making requests to MongoDB service and Auth service
        self.http_client = httpx.AsyncClient(timeout=30.0)

    def _format_file_size(self, size_bytes):
        """Format file size in human-readable format"""
        if size_bytes is None:
            return None
        
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

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
            """
            Customer Service Health Check Endpoint
            
            This endpoint provides a simple health check to verify that the Customer Service
            is running and accessible.
            
            Returns:
                JSONResponse: A simple status message confirming the service is active
                
            Example Response:
                {
                    "message": "Customer Service is active"
                }
            """
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
            """
            Upload Blender File Endpoint
            
            This endpoint allows authenticated customers to upload Blender (.blend) files
            for rendering. The file is stored in blob storage and a corresponding record
            is created in the MongoDB database.
            
            Authentication:
                Requires valid Bearer token in Authorization header
                
            Parameters:
                blend_file_name (str, Form): Name of the blend file (e.g., "chair_model.blend")
                blend_file (UploadFile, File): The actual blend file to upload
                access_token (str): Bearer token for authentication (auto-extracted)
                customer_id (str): Customer ID extracted from authorization header
                
            Process:
                1. Creates empty blender object record in MongoDB
                2. Uploads file to blob storage with path: customer_id/object_id/blend_file_name
                3. Updates MongoDB record with file path and hash
                4. Returns object details including generated object_id
                
            Returns:
                JSONResponse: Success message with object details
                
            Example Response:
                {
                    "message": "Blend file uploaded successfully",
                    "objectId": "uuid-generated-object-id",
                    "customerId": "customer-uuid",
                    "blendFileName": "chair_model.blend",
                    "blendFilePath": "customer-uuid/object-id/chair_model.blend",
                    "blendFileHash": "sha256-hash-of-file-path",
                    "fileSize": "2.5 MB"
                }
                
            Raises:
                HTTPException: 401 if authentication fails
                HTTPException: 400 if required fields are missing
                HTTPException: 500 if upload or database operations fail
            """
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
            """
            Start Rendering Workload Endpoint
            
            This endpoint initiates a rendering workload for a specific blender object.
            It coordinates with the Session Supervisor Service to start the rendering
            process and updates the object state in MongoDB.
            
            Authentication:
                Requires valid Bearer token in Authorization header
                
            Parameters:
                object_id (str, Form): The unique identifier of the blender object to render
                access_token (str): Bearer token for authentication (auto-extracted)
                customer_id (str): Customer ID extracted from authorization header
                
            Process:
                1. Forwards request to Session Supervisor Service to start workload
                2. If successful, updates object state to "processing" in MongoDB
                3. Returns the response from Session Supervisor Service
                
            Returns:
                JSONResponse: Response from Session Supervisor Service containing workload details
                
            Example Response:
                {
                    "message": "Workload started successfully",
                    "sessionId": "session-uuid",
                    "objectId": "object-uuid",
                    "customerId": "customer-uuid",
                    "status": "queued"
                }
                
            Raises:
                HTTPException: 401 if authentication fails
                HTTPException: 400 if object_id is missing
                HTTPException: 404 if object not found
                HTTPException: 503 if Session Supervisor Service is unavailable
                HTTPException: 500 if internal server error occurs
            """
            try:
                print(f"Starting workload for customer: {customer_id}, object: {object_id}")
                
                # Step 1: Forward the request to session supervisor service FIRST
                print("Forwarding request to session supervisor service...")
                response = await self.http_client.post(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/start-workload",
                    data={
                        "customer_id": customer_id,
                        "object_id": object_id
                    }
                )

                print("Response when starting workload is: ")
                print(response.json())
                print(f"Response status code: {response.status_code}")
                
                # Step 2: Only update MongoDB if session supervisor service returns 200
                if response.status_code == 200:
                    print("Session supervisor service returned 200. Updating object state to processing in MongoDB...")
                    try:
                        mongo_response = await self.http_client.put(
                            f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/change-state",
                            json={
                                "objectId": object_id,
                                "customerId": customer_id,
                                "objectState": "processing"
                            }
                        )
                        
                        if mongo_response.status_code != 200:
                            print(f"Warning: Failed to update object state to processing: {mongo_response.text}")
                            # Log warning but don't fail the request since workload started successfully
                        else:
                            print("Object state updated to processing successfully")
                            
                    except Exception as mongo_error:
                        print(f"Error updating object state to processing: {str(mongo_error)}")
                        # Log error but don't fail the request since workload started successfully
                else:
                    print(f"Session supervisor service returned non-200 status ({response.status_code}). Skipping MongoDB update.")
                    print("Workload start failed - object state will remain unchanged")
                
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

        @self.app.get("/api/customer-service/get-workload-status")
        async def getWorkloadStatus(
            request: Request, 
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader)
        ):
            """
            Get Workload Status Endpoint
            
            This endpoint retrieves the current status of rendering workloads for the
            authenticated customer. It forwards the request to the Session Supervisor
            Service to get real-time workload information.
            
            Authentication:
                Requires valid Bearer token in Authorization header
                
            Parameters:
                access_token (str): Bearer token for authentication (auto-extracted)
                customer_id (str): Customer ID extracted from authorization header
                
            Returns:
                JSONResponse: Workload status information from Session Supervisor Service
                
            Example Response:
                {
                    "customerId": "customer-uuid",
                    "activeWorkloads": [
                        {
                            "objectId": "object-uuid",
                            "sessionId": "session-uuid",
                            "status": "rendering",
                            "progress": 45.5,
                            "startTime": "2024-01-15T10:30:00Z"
                        }
                    ],
                    "totalActiveWorkloads": 1
                }
                
            Raises:
                HTTPException: 401 if authentication fails
                HTTPException: 503 if Session Supervisor Service is unavailable
                HTTPException: 500 if internal server error occurs
            """
            try:
                print(f"Redirecting get-workload-status request to session supervisor service for customer: {customer_id}")
                
                # Forward the request to session supervisor service with form data
                response = await self.http_client.get(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-workload-status",
                    params={"customer_id": customer_id}
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
        async def stopAndDeleteWorkload(
            object_id: str = Form(None),
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader)
        ):
            """
            Stop and Delete Workload Endpoint
            
            This endpoint stops any active rendering workloads for the authenticated customer
            and resets the object state back to "ready-to-render". It coordinates with both
            the Session Supervisor Service and MongoDB to properly clean up the workload.
            
            Authentication:
                Requires valid Bearer token in Authorization header
                
            Parameters:
                object_id (str, Form, optional): The unique identifier of the blender object
                    to stop rendering for. If not provided, stops all workloads for the customer.
                access_token (str): Bearer token for authentication (auto-extracted)
                customer_id (str): Customer ID extracted from authorization header
                
            Process:
                1. Stops active workloads via Session Supervisor Service
                2. Updates object state to "ready-to-render" in MongoDB
                3. Returns success confirmation
                
            Returns:
                JSONResponse: Success message confirming workload termination
                
            Example Response:
                {
                    "message": "Workload stopped and object state reset successfully",
                    "objectId": "object-uuid",
                    "customerId": "customer-uuid",
                    "objectState": "ready-to-render"
                }
                
            Raises:
                HTTPException: 401 if authentication fails
                HTTPException: 400 if object_id is missing when required
                HTTPException: 404 if object not found
                HTTPException: 503 if Session Supervisor Service is unavailable
                HTTPException: 500 if internal server error occurs
            """
            try:
                # Error handling if object_id is not present in the API request
                if not object_id or object_id.strip() == "":
                    print("Error: object_id is missing in the API request.")
                    raise HTTPException(
                        status_code=400,
                        detail="Missing required field: object_id"
                    )

                print(f"Redirecting stop-and-delete-workload request to session supervisor service for customer: {customer_id}")
                
                # Forward the request to session supervisor service with form data
                response = await self.http_client.post(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/stop-and-delete-workload",
                    data={"customer_id": customer_id}
                )

                # Reset object state in MongoDB regardless of session supervisor response
                mongo_response = await self.http_client.put(
                    f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/change-state",
                    json={
                        "objectId": object_id,
                        "customerId": customer_id,
                        "objectState": "ready-to-render"
                    }
                )
                if mongo_response.status_code != 200:
                    print(f"Warning: Failed to reset object state: {mongo_response.text}")

                # Also clean up the User Manager routing/session mapping
                try:
                    # Get the session supervisor info to obtain the session_supervisor_id
                    overview_resp = await self.http_client.get(
                        f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-session-supervisor-overview/{customer_id}"
                    )
                    if overview_resp.status_code == 200:
                        overview_json = overview_resp.json()
                        session_supervisor_id = overview_json.get("session_id")
                        if session_supervisor_id:
                            cleanup_resp = await self.http_client.delete(
                                f"{self.user_manager_service_url}/api/user-manager/session-supervisor/cleanup-session",
                                data={
                                    "session_supervisor_id": session_supervisor_id
                                }
                            )
                            if cleanup_resp.status_code != 200:
                                try:
                                    err_detail = cleanup_resp.json().get("detail", cleanup_resp.text)
                                except Exception:
                                    err_detail = cleanup_resp.text
                                print(f"Warning: User Manager cleanup failed: {cleanup_resp.status_code} - {err_detail}")
                        else:
                            print("Warning: session_id not found in session supervisor overview; skipping User Manager cleanup")
                    else:
                        print(f"Warning: Failed to get session supervisor overview for cleanup: {overview_resp.status_code} - {overview_resp.text}")
                except Exception as e:
                    print(f"Warning: Error during User Manager cleanup: {str(e)}")
                
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
            """
            Get Blender File Endpoint
            
            This endpoint allows authenticated customers to download their uploaded
            Blender files. It retrieves the file from blob storage and streams it
            back to the client.
            
            Authentication:
                Requires valid Bearer token in Authorization header
                
            Parameters:
                object_id (str): The unique identifier of the blender object
                access_token (str): Bearer token for authentication (auto-extracted)
                customer_id (str): Customer ID extracted from authorization header
                
            Process:
                1. Queries MongoDB to get blend file path and metadata
                2. Retrieves file from blob storage
                3. Streams file content back to client with appropriate headers
                
            Returns:
                StreamingResponse: The blend file content with appropriate headers
                
            Response Headers:
                Content-Type: application/octet-stream
                Content-Disposition: attachment; filename="blend_file_name.blend"
                Content-Length: file size in bytes
                
            Raises:
                HTTPException: 401 if authentication fails
                HTTPException: 404 if object not found or file doesn't exist
                HTTPException: 500 if file retrieval fails
            """
            print(f"Get blend file endpoint hit for customer: {customer_id}")
            print(f"Requested object ID: {object_id}")

            try:
                # Step 1: Query MongoDB service for blend file path using object ID
                try:
                    blend_file_data = await self.http_client.get(
                        f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/get-blend-file-name/{object_id}",
                        params={"customer_id": customer_id},
                        timeout=10.0
                    )
                except Exception as e:
                    print(f"Error contacting MongoDB service: {str(e)}")
                    raise HTTPException(
                        status_code=502,
                        detail=f"Failed to contact MongoDB service: {str(e)}"
                    )

                if blend_file_data.status_code != 200:
                    try:
                        error_detail = blend_file_data.json().get("detail", blend_file_data.text)
                    except Exception:
                        error_detail = blend_file_data.text
                    print(f"MongoDB service returned error: {blend_file_data.status_code} - {error_detail}")
                    raise HTTPException(
                        status_code=blend_file_data.status_code,
                        detail=f"MongoDB service error: {error_detail}"
                    )

                try:
                    blend_file_json = blend_file_data.json()
                except Exception as e:
                    print(f"Failed to parse MongoDB response JSON: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to parse MongoDB service response"
                    )

                blend_file_path = blend_file_json.get("blendFilePath")
                if not blend_file_path:
                    print("blendFilePath not found in MongoDB response")
                    raise HTTPException(
                        status_code=404,
                        detail="Blend file not found for the given object ID"
                    )

                bucket = "blend-files"
                key = blend_file_path

                print(f"Retrieving from bucket: {bucket}, key: {key}")

                # Step 2: Get file metadata (including content length) from blob service
                print(f"Getting blend file metadata from blob service...")
                try:
                    metadata_response = await self.http_client.get(
                        f"{self.blob_service_url}/api/blob-service/retrieve-blend-metadata",
                        params={
                            "bucket": bucket,
                            "key": key
                        },
                        timeout=10.0
                    )
                    
                    content_length = None
                    if metadata_response.status_code == 200:
                        metadata_json = metadata_response.json()
                        content_length = metadata_json.get("size_bytes")
                        print(f"Retrieved file metadata - Content length: {content_length} bytes")
                    else:
                        print(f"Warning: Could not retrieve metadata, status: {metadata_response.status_code}")
                        
                except Exception as e:
                    print(f"Warning: Error retrieving metadata: {str(e)}")
                    content_length = None

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
                                },
                                timeout=30.0
                            ) as response:
                                if response.status_code != 200:
                                    # If blob service fails, we need to handle it differently
                                    try:
                                        error_content = await response.aread()
                                        error_detail = error_content.decode(errors="replace")
                                    except Exception:
                                        error_detail = "Unknown error"
                                    print(f"Blob service returned error: {response.status_code} - {error_detail}")
                                    raise HTTPException(
                                        status_code=response.status_code,
                                        detail=f"Blob service error: {error_detail}"
                                    )

                                # Stream the response directly to the client
                                async for chunk in response.aiter_bytes():
                                    yield chunk

                    except HTTPException:
                        raise
                    except Exception as e:
                        print(f"Error in proxy stream: {str(e)}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to proxy blend file: {str(e)}"
                        )

                # Return streaming response with proper headers
                file_name = os.path.basename(blend_file_path) if blend_file_path else "blendfile.blend"
                print(f"Proxying blend file: {file_name}")

                # Prepare response headers
                response_headers = {
                    "Content-Disposition": f"attachment; filename=\"{file_name}\"",
                    "Cache-Control": "no-cache"
                }
                
                # Add content length if available
                if content_length is not None:
                    response_headers["Content-Length"] = str(content_length)
                    print(f"Added Content-Length header: {content_length} bytes")

                return StreamingResponse(
                    proxy_blend_file(),
                    media_type="application/octet-stream",
                    headers=response_headers
                )
            except HTTPException:
                raise
            except Exception as e:
                print(f"Unexpected error in getBlendFile: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal server error: {str(e)}"
                )

        @self.app.delete("/api/customer-service/delete-blend-file/{object_id}")
        async def deleteBlendFile(
            object_id: str,
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader)
        ):
            """
            Delete Blender Object Endpoint
            
            This endpoint allows authenticated customers to permanently delete their
            blender objects and all associated files. It removes the object from both
            blob storage and the MongoDB database.
            
            Authentication:
                Requires valid Bearer token in Authorization header
                
            Parameters:
                object_id (str): The unique identifier of the blender object to delete
                access_token (str): Bearer token for authentication (auto-extracted)
                customer_id (str): Customer ID extracted from authorization header
                
            Process:
                1. Deletes all associated files from blob storage (blend file, rendered images, video)
                2. Removes the object record from MongoDB database
                3. Returns confirmation of successful deletion
                
            Returns:
                JSONResponse: Success message with deleted object details
                
            Example Response:
                {
                    "message": "Blender object and all associated files deleted successfully",
                    "objectId": "object-uuid",
                    "customerId": "customer-uuid",
                    "blendFileName": "chair_model.blend"
                }
                
            Raises:
                HTTPException: 401 if authentication fails
                HTTPException: 404 if object not found
                HTTPException: 500 if deletion fails
            """
            print(f"Delete blend file endpoint hit for customer: {customer_id}")
            print(f"Requested object ID: {object_id}")
            
            try:
                # Step 1: Delete from blob storage first
                print("Deleting files from blob storage...")
                blob_deletion_results = await self.deleteObjectFilesFromBlobStorage(customer_id, object_id)
                
                # Step 2: Forward the delete request to MongoDB service
                print("Deleting from MongoDB...")
                mongo_response = await self.http_client.delete(
                    f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/delete/{object_id}",
                    params={"customer_id": customer_id}
                )

                if mongo_response.status_code == 200:
                    result = mongo_response.json()
                    print(f"Successfully deleted blender object: {object_id}")
                    return JSONResponse(
                        content={
                            "message": "Blender object and all associated files deleted successfully",
                            "objectId": object_id,
                            "customerId": customer_id,
                            "blendFileName": result.get("blendFileName")
                        },
                        status_code=200
                    )
                else:
                    # Forward the error from MongoDB service
                    error_detail = mongo_response.text
                    print(f"MongoDB service error: {mongo_response.status_code} - {error_detail}")
                    raise HTTPException(
                        status_code=mongo_response.status_code,
                        detail=f"MongoDB service error: {error_detail}"
                    )
                    
            except HTTPException:
                raise
            except Exception as e:
                print(f"Error deleting blend file: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete blend file: {str(e)}"
                )
    
        @self.app.get("/api/customer-service/get-signed-url-for-rendered-video/{object_id}")
        async def getSignedUrlForRenderedVideo(
            object_id: str,
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader)
        ):
            """
            Get Signed URL for Rendered Video Endpoint
            
            This endpoint generates a signed URL that allows temporary access to the
            rendered video file for a specific blender object. The signed URL provides
            secure, time-limited access to the video without requiring authentication
            for the actual file download.
            
            Authentication:
                Requires valid Bearer token in Authorization header
                
            Parameters:
                object_id (str): The unique identifier of the blender object
                access_token (str): Bearer token for authentication (auto-extracted)
                customer_id (str): Customer ID extracted from authorization header
                
            Process:
                1. Retrieves blender object information from MongoDB
                2. Checks if rendered video path exists
                3. Generates signed URL from blob service
                4. Returns the signed URL with expiration information
                
            Returns:
                JSONResponse: Signed URL and metadata for video access
                
            Example Response:
                {
                    "message": "Signed URL generated successfully",
                    "objectId": "object-uuid",
                    "customerId": "customer-uuid",
                    "signedUrl": "https://blob-storage.com/signed-url-with-token",
                    "expiresIn": 3600,
                    "videoPath": "customer-uuid/object-uuid/rendered_video.mp4"
                }
                
            Raises:
                HTTPException: 401 if authentication fails
                HTTPException: 404 if object not found or video doesn't exist
                HTTPException: 500 if signed URL generation fails
            """
            print(f"Get signed URL for rendered video endpoint hit for customer: {customer_id}, object: {object_id}")
            
            try:
                # Step 1: Get blender object information from MongoDB by object ID
                print(f"Retrieving blender object {object_id} from MongoDB...")
                mongo_response = await self.http_client.get(
                    f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/get-by-object-id/{object_id}",
                    params={"customer_id": customer_id}
                )
                
                if mongo_response.status_code != 200:
                    raise HTTPException(
                        status_code=mongo_response.status_code,
                        detail=f"MongoDB service error: {mongo_response.text}"
                    )
                
                mongo_result = mongo_response.json()
                blender_object = mongo_result.get("blenderObject")
                
                if not blender_object:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Blender object with ID {object_id} not found for customer {customer_id}"
                    )
                
                # Check if rendered video path exists
                rendered_video_path = blender_object.get("renderedVideoPath")
                if not rendered_video_path:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No rendered video found for object {object_id}"
                    )
                
                print(f"Found rendered video path: {rendered_video_path}")
                
                # Step 2: Generate signed URL using blob service
                print("Generating signed URL from blob service...")
                blob_response = await self.http_client.get(
                    f"{self.blob_service_url}/api/blob-service/generate-signed-url",
                    params={
                        "bucket": "rendered-videos",
                        "key": rendered_video_path,
                        "expiration": 3600  # 1 minute expiration
                    }
                )
                
                if blob_response.status_code != 200:
                    raise HTTPException(
                        status_code=blob_response.status_code,
                        detail=f"Blob service error: {blob_response.text}"
                    )
                
                blob_result = blob_response.json()
                signed_url = blob_result.get("signed_url")
                
                if not signed_url:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to generate signed URL from blob service"
                    )
                
                print(f"Successfully generated signed URL for object {object_id}")
                
                # Parse the signed URL to extract the path and parameters
                from urllib.parse import urlparse, parse_qs
                parsed_url = urlparse(signed_url)
                
                # Extract the path and query parameters (everything after the domain)
                path_with_params = parsed_url.path
                if parsed_url.query:
                    path_with_params += "?" + parsed_url.query
                
                print(f"Extracted path with params: {path_with_params}")
                
                # Create the proxy URL using customer service endpoint
                print("Signed Url is: ", signed_url)
                proxy_url = f"{path_with_params}"
                print(f"Created proxy URL: {proxy_url}")
                
                # Return the proxy URL instead of direct blob service URL
                return JSONResponse(content={
                    "message": "Signed URL generated successfully",
                    "objectId": object_id,
                    "customerId": customer_id,
                    "signedUrl": proxy_url,
                    "expiration": 3600,
                    "videoPath": rendered_video_path,
                    "timestamp": datetime.now().isoformat()
                }, status_code=200)
                
            except HTTPException:
                raise
            except httpx.RequestError as e:
                print(f"Error connecting to external services: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail="External service unavailable"
                )
            except Exception as e:
                print(f"Error generating signed URL for rendered video: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate signed URL: {str(e)}"
                )

        @self.app.get("/api/customer-service/get-render-video-from-signed-url/{video_path:path}")
        async def getRenderVideoFromSignedUrl(
            video_path: str,
            request: Request,
            download: bool = False
        ):
            """
            Proxy endpoint to stream or download rendered video from blob storage using signed URL
            Parameters: 
                - video_path (path parameter) - the full path from blob service with signed URL params
                - download (query parameter, optional) - if True, forces download; if False, streams for playback
            Returns: Streaming response of the rendered video (streamable or downloadable)
            """
            print(f"Get render video from signed URL endpoint hit")
            print(f"Video path: {video_path}")
            
            try:
                # Reconstruct the full blob service URL
                print(video_path)
                print(self.blob_storage_base_url)
                # Remove leading slash from video_path to avoid double slashes
                clean_video_path = video_path.lstrip('/')
                blob_service_url = f"{self.blob_storage_base_url}/{clean_video_path}"
                
                # Preserve query parameters from the original request
                if request.url.query:
                    blob_service_url += f"?{request.url.query}"
                print(f"Full blob service URL: {blob_service_url}")
                print(f"Query parameters: {request.url.query}")
                
                # Create a streaming response that proxies the blob service
                async def proxy_video_stream():
                    try:
                        print(f"Making API call to blob service with URL: {blob_service_url}")
                        async with httpx.AsyncClient() as proxy_client:
                            async with proxy_client.stream(
                                "GET",
                                blob_service_url,
                                timeout=30.0
                            ) as response:
                                if response.status_code != 200:
                                    try:
                                        error_content = await response.aread()
                                        error_detail = error_content.decode(errors="replace")
                                    except Exception:
                                        error_detail = "Unknown error"
                                    print(f"Blob service returned error: {response.status_code} - {error_detail}")
                                    raise HTTPException(
                                        status_code=response.status_code,
                                        detail=f"Blob service error: {error_detail}"
                                    )

                                # Stream the video directly to the client
                                async for chunk in response.aiter_bytes():
                                    yield chunk

                    except HTTPException:
                        raise
                    except Exception as e:
                        print(f"Error in proxy video stream: {str(e)}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to proxy video stream: {str(e)}"
                        )

                # Return streaming response with proper headers
                video_name = os.path.basename(video_path.split('?')[0]) if video_path else "video.mp4"
                print(f"Proxying video: {video_name}")

                # Prepare response headers
                response_headers = {
                    "Content-Disposition": f"attachment; filename=\"{video_name}\"",
                    "Cache-Control": "no-cache"
                }

                return StreamingResponse(
                    proxy_video_stream(),
                    media_type="video/mp4",
                    headers=response_headers
                )
                
            except HTTPException:
                raise
            except Exception as e:
                print(f"Error retrieving rendered video: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to retrieve rendered video: {str(e)}"
                )
        
        @self.app.get("/api/customer-service/get-rendered-frames/{object_id}")
        async def getRenderedFrames(
            object_id: str,
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader),
            start_frame: int = 0,
            pagination_size: int = 20
        ):
            """
            Get Rendered Frames Endpoint with Pagination
            
            This endpoint retrieves rendered frames for a specific blender object with pagination support.
            The behavior differs based on payment status:
            - Paid plans: Returns sequential frames based on pagination
            - Unpaid plans: Returns 30% of frames distributed evenly, maintaining correct sequence
            
            Authentication:
                Requires valid Bearer token in Authorization header
                
            Parameters:
                object_id (str): The unique identifier of the blender object
                access_token (str): Bearer token for authentication (auto-extracted)
                customer_id (str): Customer ID extracted from authorization header
                start_frame (int, optional): Starting frame index for pagination (default: 0)
                pagination_size (int, optional): Number of frames to return (default: 20)
                
            Process:
                1. Checks payment status for the object
                2. Retrieves all rendered images from MongoDB
                3. Applies pagination logic based on payment status:
                   - Paid: Sequential frames from start_frame
                   - Unpaid: 30% distributed frames, filtered by start_frame
                4. Streams frames with metadata
                
            Returns:
                StreamingResponse: JSON metadata followed by frame images
                
            Response Headers:
                X-Object-ID: Object identifier
                X-Customer-ID: Customer identifier
                X-Payment-Status: "paid" or "unpaid"
                X-Total-Frames: Total number of rendered frames
                X-Frames-Returned: Number of frames in this response
                X-Start-Frame: Starting frame index
                X-Pagination-Size: Requested pagination size
                X-Has-More-Frames: Whether more frames are available
                
            Example Response:
                JSON metadata:
                {
                    "message": "Rendered frames retrieved successfully",
                    "objectId": "object-uuid",
                    "customerId": "customer-uuid",
                    "frames": [...],
                    "totalFrames": 100,
                    "framesReturned": 20,
                    "paymentStatus": "paid",
                    "isPreview": false,
                    "startFrame": 0,
                    "paginationSize": 20,
                    "hasMoreFrames": true
                }
                Followed by frame images with separators.
                
            Raises:
                HTTPException: 401 if authentication fails
                HTTPException: 404 if object not found or no frames available
                HTTPException: 500 if internal server error occurs
            """
            print(f"Get rendered frames endpoint hit for customer: {customer_id}, object: {object_id}")
            print(f"Pagination parameters - start_frame: {start_frame}, pagination_size: {pagination_size}")
            
            try:
                # Step 1: Check if the object is paid for
                print("Checking payment status...")
                payment_response = await self.http_client.get(
                    f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/check-plan/{object_id}"
                )
                
                if payment_response.status_code != 200:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Object not found: {payment_response.text}"
                    )
                
                payment_result = payment_response.json()
                is_paid = payment_result.get("isPaid", False)
                print(f"Payment status: {'paid' if is_paid else 'unpaid'}")
                
                # Step 2: Get all rendered images from MongoDB
                print("Retrieving rendered images from MongoDB...")
                images_response = await self.http_client.get(
                    f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/get-rendered-images/{object_id}",
                    params={"customer_id": customer_id}
                )
                
                if images_response.status_code != 200:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Rendered images not found: {images_response.text}"
                    )
                
                images_result = images_response.json()
                all_rendered_images = images_result.get("renderedImages", [])
                total_frames = len(all_rendered_images)
                
                print(f"Total rendered frames: {total_frames}")
                
                if total_frames == 0:
                    return JSONResponse(content={
                        "message": "No rendered frames available",
                        "objectId": object_id,
                        "customerId": customer_id,
                        "frames": [],
                        "totalFrames": 0,
                        "framesReturned": 0,
                        "paymentStatus": "paid" if is_paid else "unpaid",
                        "startFrame": start_frame,
                        "paginationSize": pagination_size
                    }, status_code=200)
                
                # Step 3: Determine which frames to return based on payment status and pagination
                if is_paid:
                    # If paid, return frames sequentially based on pagination
                    end_frame = min(start_frame + pagination_size, total_frames)
                    frames_to_return = all_rendered_images[start_frame:end_frame]
                    print(f"Customer has paid - returning frames {start_frame} to {end_frame-1} ({len(frames_to_return)} frames)")
                else:
                    # If not paid, calculate which frames should be available (30% distributed)
                    frames_to_return_count = max(1, int(total_frames * 0.3))  # At least 1 frame
                    
                    # Calculate the step size and available frame indices for unpaid plan
                    if frames_to_return_count == 1:
                        # If only 1 frame, return the middle frame
                        available_frame_indices = [total_frames // 2]
                    else:
                        # Calculate step size to get evenly distributed frames
                        step_size = total_frames / frames_to_return_count
                        available_frame_indices = []
                        
                        for i in range(frames_to_return_count):
                            # Calculate index for this frame
                            index = int(i * step_size)
                            # Ensure we don't go out of bounds
                            index = min(index, total_frames - 1)
                            available_frame_indices.append(index)
                    
                    print(f"Available frame indices for unpaid plan: {available_frame_indices}")
                    
                    # Now apply pagination to the available frames
                    # Find which available frames are >= start_frame
                    paginated_available_indices = [
                        idx for idx in available_frame_indices 
                        if idx >= start_frame
                    ][:pagination_size]
                    
                    # Get the actual frame objects for these indices
                    frames_to_return = [
                        all_rendered_images[idx] for idx in paginated_available_indices
                    ]
                    
                    print(f"Customer has not paid - returning {len(frames_to_return)} frames from available frames, starting from frame {start_frame}")
                    print(f"Returned frame indices: {paginated_available_indices}")
                
                # Step 4: Get metadata for each frame (including content length)
                print("Retrieving metadata for rendered frames...")
                frames_metadata = []
                for frame in frames_to_return:
                    frame_number = frame.get("frameNumber")
                    image_file_path = frame.get("imageFilePath")
                    
                    if frame_number is not None and image_file_path:
                        # Get image metadata from blob service
                        try:
                            metadata_response = await self.http_client.get(
                                f"{self.blob_service_url}/api/blob-service/retrieve-blend-metadata",
                                params={
                                    "bucket": "rendered-frames",
                                    "key": image_file_path
                                },
                                timeout=5.0
                            )
                            
                            content_length = None
                            if metadata_response.status_code == 200:
                                metadata_json = metadata_response.json()
                                content_length = metadata_json.get("size_bytes")
                                print(f"Retrieved metadata for frame {frame_number} - Content length: {content_length} bytes")
                            else:
                                print(f"Warning: Could not retrieve metadata for frame {frame_number}, status: {metadata_response.status_code}")
                                
                        except Exception as e:
                            print(f"Warning: Error retrieving metadata for frame {frame_number}: {str(e)}")
                            content_length = None
                        
                        frames_metadata.append({
                            "frameNumber": frame_number,
                            "imageFilePath": image_file_path,
                            "contentLength": content_length,
                            "contentLengthHuman": self._format_file_size(content_length) if content_length else None
                        })
                
                # Step 5: Create streaming response with images
                async def stream_frames_with_images():
                    try:
                        
                        # Create metadata response
                        metadata_response = {
                            "message": "Rendered frames retrieved successfully",
                            "objectId": object_id,
                            "customerId": customer_id,
                            "frames": frames_metadata,
                            "totalFrames": total_frames,
                            "framesReturned": len(frames_metadata),
                            "paymentStatus": "paid" if is_paid else "unpaid",
                            "isPreview": not is_paid,
                            "startFrame": start_frame,
                            "paginationSize": pagination_size,
                            "hasMoreFrames": (start_frame + len(frames_metadata)) < total_frames if is_paid else len(frames_metadata) == pagination_size
                        }
                        
                        # Send metadata as JSON
                        metadata_json = json.dumps(metadata_response) + "\n"
                        yield metadata_json.encode('utf-8')
                        
                        # Then stream each image
                        for frame in frames_to_return:
                            frame_number = frame.get("frameNumber")
                            image_file_path = frame.get("imageFilePath")
                            
                            if frame_number is not None and image_file_path:
                                print(f"Streaming image for frame {frame_number}: {image_file_path}")
                                
                                # Get image from blob storage
                                async with httpx.AsyncClient() as proxy_client:
                                    try:
                                        async with proxy_client.stream(
                                            "GET",
                                            f"{self.blob_service_url}/api/blob-service/retrieve-image",
                                            params={
                                                "bucket": "rendered-frames",
                                                "key": image_file_path,
                                                "type": "png"
                                            }
                                        ) as response:
                                            if response.status_code == 200:
                                                # Send frame separator
                                                frame_header = f"---FRAME_{frame_number}---\n"
                                                yield frame_header.encode('utf-8')
                                                
                                                # Stream the image data
                                                async for chunk in response.aiter_bytes():
                                                    yield chunk
                                                
                                                # Send frame end separator
                                                frame_footer = f"---END_FRAME_{frame_number}---\n"
                                                yield frame_footer.encode('utf-8')
                                            else:
                                                print(f"Failed to retrieve image for frame {frame_number}: {response.status_code}")
                                                error_msg = f"---ERROR_FRAME_{frame_number}: Failed to retrieve image---\n"
                                                yield error_msg.encode('utf-8')
                                    except Exception as e:
                                        print(f"Error streaming image for frame {frame_number}: {str(e)}")
                                        error_msg = f"---ERROR_FRAME_{frame_number}: {str(e)}---\n"
                                        yield error_msg.encode('utf-8')
                        
                    except Exception as e:
                        print(f"Error in stream_frames_with_images: {str(e)}")
                        error_response = json.dumps({"error": f"Failed to stream frames: {str(e)}"})
                        yield error_response.encode('utf-8')
                
                # Return streaming response
                return StreamingResponse(
                    stream_frames_with_images(),
                    media_type="application/octet-stream",
                    headers={
                        "Content-Type": "application/octet-stream",
                        "Cache-Control": "no-cache",
                        "X-Object-ID": object_id,
                        "X-Customer-ID": customer_id,
                        "X-Payment-Status": "paid" if is_paid else "unpaid",
                        "X-Total-Frames": str(total_frames),
                        "X-Frames-Returned": str(len(frames_to_return)),
                        "X-Start-Frame": str(start_frame),
                        "X-Pagination-Size": str(pagination_size),
                        "X-Has-More-Frames": str((start_frame + len(frames_to_return)) < total_frames if is_paid else len(frames_to_return) == pagination_size)
                    }
                )
                
            except HTTPException:
                raise
            except Exception as e:
                print(f"Error retrieving rendered frames: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to retrieve rendered frames: {str(e)}"
                )
        
        @self.app.get("/api/customer-service/get-blender-objects")
        async def getBlenderObjects(
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader)
        ):
            """Get all blender objects associated with the authenticated customer
            Returns: List of blender objects with objectId, blendFileName, and isPaid
            """
            print(f"Get blender objects endpoint hit for customer: {customer_id}")
            
            try:
                # Call MongoDB service to get all blender objects for this customer
                print("Calling MongoDB service to retrieve blender objects...")
                mongo_response = await self.http_client.get(
                    f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/get-by-customer/{customer_id}"
                )
                
                if mongo_response.status_code == 404:
                    # Customer not found - this shouldn't happen since we authenticated
                    raise HTTPException(
                        status_code=404,
                        detail="Customer not found"
                    )
                elif mongo_response.status_code != 200:
                    raise HTTPException(
                        status_code=500,
                        detail=f"MongoDB service error: {mongo_response.text}"
                    )
                
                mongo_result = mongo_response.json()
                print(f"Retrieved {mongo_result.get('totalObjects', 0)} blender objects")
                
                # Return the response directly from MongoDB service
                return JSONResponse(
                    content=mongo_result,
                    status_code=200
                )
                
            except HTTPException:
                raise
            except httpx.RequestError as e:
                print(f"Error connecting to MongoDB service: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB service unavailable"
                )
            except Exception as e:
                print(f"Error retrieving blender objects: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to retrieve blender objects: {str(e)}"
                )

        @self.app.get("/api/customer-service/get-workload-progress")
        async def getWorkloadProgress(
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader)
        ):
            try:
                response = await self.http_client.get(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-workload-progress",
                    params={"customer_id": customer_id}
                )
                if response.status_code == 200:
                    return JSONResponse(
                    content={
                        "message": "Workload progress retrieved",
                        "progress": response.json()
                    },
                    status_code=200
                    )
                else:
                    try:
                        error_detail = response.json().get("detail", response.text)
                    except Exception:
                        error_detail = response.text
                        raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Session supervisor service error: {error_detail}"
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
                print(f"Error retrieving workload progress: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to retrieve workload progress: {str(e)}"
                )

        @self.app.get("/api/customer-service/create-and-retrieve-zip-file-of-rendered-frames/{object_id}/{secs}")
        async def createAndRetrieveZipFileOfRenderedFrames(
            object_id: str,
            secs: int,
            access_token: str = Depends(self.authenticate_token),
            customer_id: str = Depends(self.getCustomerIdFromAuthorizationHeader),
        ):
            """
                flow :
                1. check if the zip file exists in the blob storage and if so directly move to step 3.
                2. if not, make the zip file and then store it in the blob storage
                3. create the signed url for the zip file and return it to the user so that it is able to retrieve the zip folder
            """
            print(f"[ZIP_FRAMES] Request received for customer_id={customer_id} object_id={object_id} secs={secs}")
            # Basic validation
            if secs <= 0:
                raise HTTPException(status_code=400, detail="Expiration seconds must be > 0")
            if secs > 3 * 3600:
                # Cap to 3h to avoid very long-lived URLs (adjust as needed)
                secs = 3 * 3600
            try:
                # Step 0: Validate blender object + ensure it belongs to customer
                print("[ZIP_FRAMES] Fetching blender object from MongoDB service...")
                mongo_response = await self.http_client.get(
                    f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/get-by-object-id/{object_id}",
                    params={"customer_id": customer_id}
                )
                if mongo_response.status_code != 200:
                    raise HTTPException(status_code=mongo_response.status_code, detail=f"MongoDB service error: {mongo_response.text}")
                mongo_json = mongo_response.json()
                blender_object = mongo_json.get("blenderObject")
                if not blender_object:
                    raise HTTPException(status_code=404, detail="Blender object not found")

                rendered_images = blender_object.get("renderedImages", []) or []
                total_frames = len(rendered_images)
                if total_frames == 0:
                    raise HTTPException(status_code=404, detail="No rendered frames available for this object yet")

                prefix = f"{customer_id}/{object_id}"  # matches how frames are stored in rendered-frames bucket
                zip_key = f"{prefix}/frames.zip"
                print(f"[ZIP_FRAMES] Derived prefix={prefix} zip_key={zip_key}")

                # Step 1: Check if zip already exists (light-weight existence endpoint)
                print("[ZIP_FRAMES] Checking if zip already exists in frames-zip bucket (object-exists)...")
                zip_exists = False
                zip_size_bytes = None
                zip_size_human = None
                exists_response = await self.http_client.get(
                    f"{self.blob_service_url}/api/blob-service/object-exists",
                    params={
                        "bucket": "frames-zip",
                        "key": zip_key
                    }
                )
                if exists_response.status_code == 200:
                    exists_json = exists_response.json()
                    if exists_json.get("exists"):
                        zip_exists = True
                        zip_size_bytes = exists_json.get("size_bytes")
                        zip_size_human = self._format_file_size(zip_size_bytes) if zip_size_bytes is not None else None
                        print(f"[ZIP_FRAMES] Zip already exists (size={zip_size_bytes})")
                else:
                    print(f"[ZIP_FRAMES] object-exists check returned {exists_response.status_code}, will attempt creation.")

                # Step 2: If not exists, request blob service to create it
                if not zip_exists:
                    print("[ZIP_FRAMES] Creating frames zip via blob service ...")
                    create_response = await self.http_client.post(
                        f"{self.blob_service_url}/api/blob-service/store-rendered-images-as-zip",
                        data={
                            "bucket": "rendered-frames",
                            "prefix": prefix,
                        }
                    )
                    if create_response.status_code != 200:
                        raise HTTPException(status_code=create_response.status_code, detail=f"Failed to create frames zip: {create_response.text}")
                    create_json = create_response.json()
                    # Use returned key if provided
                    returned_key = create_json.get("key")
                    if returned_key and returned_key != zip_key:
                        print(f"[ZIP_FRAMES] Warning: returned key {returned_key} differs from expected {zip_key}; using returned key.")
                        zip_key = returned_key
                    # Fetch existence again to get size (still light-weight)
                    exists_after_create = await self.http_client.get(
                        f"{self.blob_service_url}/api/blob-service/object-exists",
                        params={
                            "bucket": "frames-zip",
                            "key": zip_key
                        }
                    )
                    if exists_after_create.status_code == 200:
                        after_json = exists_after_create.json()
                        if after_json.get("exists"):
                            zip_size_bytes = after_json.get("size_bytes")
                            zip_size_human = self._format_file_size(zip_size_bytes) if zip_size_bytes is not None else None
                    else:
                        print(f"[ZIP_FRAMES] Could not confirm zip after creation: {exists_after_create.status_code}")

                # Step 3: Generate signed URL
                print("[ZIP_FRAMES] Generating signed URL for frames zip ...")
                signed_url_response = await self.http_client.get(
                    f"{self.blob_service_url}/api/blob-service/generate-signed-url",
                    params={
                        "bucket": "frames-zip",
                        "key": zip_key,
                        "expiration": secs
                    }
                )
                if signed_url_response.status_code != 200:
                    raise HTTPException(status_code=signed_url_response.status_code, detail=f"Failed to generate signed URL: {signed_url_response.text}")
                signed_json = signed_url_response.json()
                signed_url = signed_json.get("signed_url")
                if not signed_url:
                    raise HTTPException(status_code=500, detail="Signed URL missing in blob service response")

                # Parse signed URL and build proxy path similar to rendered video approach
                from urllib.parse import urlparse
                parsed_url = urlparse(signed_url)
                path_with_query = parsed_url.path
                if parsed_url.query:
                    path_with_query += f"?{parsed_url.query}"

                # Construct a customer-service proxied endpoint path for retrieval
                # We'll reuse a new endpoint: /api/customer-service/get-zip-from-signed-url/{zip_path:path}
                # Client will call that with the returned zipProxyPath
                proxy_path = path_with_query.lstrip('/')  # remove leading slash for path parameter

                print(f"[ZIP_FRAMES] Proxied zip path: {proxy_path}")

                return JSONResponse(content={
                    "message": "Frames zip ready",
                    "objectId": object_id,
                    "customerId": customer_id,
                    "zipKey": zip_key,
                    "bucket": "frames-zip",
                    "zipProxyPath": proxy_path,
                    "expiresIn": secs,
                    "zipExistsPreviously": zip_exists,
                    "totalFrames": total_frames,
                    "zipSizeBytes": zip_size_bytes,
                    "zipSizeHuman": zip_size_human
                }, status_code=200)
            except HTTPException:
                raise
            except Exception as e:
                print(f"[ZIP_FRAMES][ERROR] {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to prepare frames zip: {str(e)}")

        @self.app.get("/api/customer-service/get-zip-from-signed-url/{zip_path:path}")
        async def getZipFromSignedUrl(
            zip_path: str,
            request: Request,
            download: bool = False
        ):
            """Proxy endpoint to stream or download the frames zip via the signed URL.
            Similar pattern to get-render-video-from-signed-url.
            zip_path: the path + query component extracted from signed URL (without scheme/host)
            download: if True sets attachment Content-Disposition.
            """
            print(f"[ZIP_PROXY] Zip proxy endpoint hit for path {zip_path}")
            try:
                # Build full blob storage URL
                clean_path = zip_path.lstrip('/')
                blob_url = f"{self.blob_storage_base_url}/{clean_path}"
                if request.url.query:
                    # If additional query parameters are provided by client, append (rare)
                    blob_url += ("&" if "?" in blob_url else "?") + request.url.query
                print(f"[ZIP_PROXY] Full blob URL: {blob_url}")

                async def proxy_zip_stream():
                    try:
                        async with httpx.AsyncClient() as proxy_client:
                            async with proxy_client.stream("GET", blob_url, timeout=60.0) as resp:
                                if resp.status_code != 200:
                                    try:
                                        err_bytes = await resp.aread()
                                        err_detail = err_bytes.decode(errors="replace")
                                    except Exception:
                                        err_detail = "Unknown error"
                                    raise HTTPException(status_code=resp.status_code, detail=f"Blob service error: {err_detail}")
                                async for chunk in resp.aiter_bytes():
                                    yield chunk
                    except HTTPException:
                        raise
                    except Exception as e:
                        print(f"[ZIP_PROXY][ERROR] {str(e)}")
                        raise HTTPException(status_code=500, detail=f"Failed to proxy zip: {str(e)}")

                zip_filename = os.path.basename(zip_path.split('?')[0]) or 'frames.zip'
                disposition = 'attachment' if download else 'inline'
                headers = {
                    'Content-Disposition': f"{disposition}; filename=\"{zip_filename}\"",
                    'Cache-Control': 'no-cache'
                }
                return StreamingResponse(proxy_zip_stream(), media_type='application/zip', headers=headers)
            except HTTPException:
                raise
            except Exception as e:
                print(f"[ZIP_PROXY][ERROR] {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to retrieve zip: {str(e)}")


    async def deleteObjectFilesFromBlobStorage(self, customer_id: str, object_id: str):
        """
        Delete all files associated with an object from blob storage.
        This includes blend files, rendered videos, and rendered frames.
        
        Args:
            customer_id: The customer ID
            object_id: The object ID
            
        Returns:
            dict: Results of deletion operations for each bucket
        """
        try:
            print(f"Deleting files for customer: {customer_id}, object: {object_id}")
            
            # Define the path prefix for this object
            object_path = f"{customer_id}/{object_id}/"
            
            # Define buckets to clean up
            buckets_to_clean = [
                "blend-files",
                "rendered-videos", 
                "rendered-frames"
            ]
            
            deletion_results = {}
            
            for bucket in buckets_to_clean:
                try:
                    print(f"Deleting from bucket: {bucket}, path: {object_path}")
                    
                    # Call blob service to delete the folder
                    blob_response = await self.http_client.delete(
                        f"{self.blob_service_url}/api/blob-service/delete-key",
                        params={
                            "bucket": bucket,
                            "key": object_path
                        }
                    )
                    
                    if blob_response.status_code == 200:
                        result = blob_response.json()
                        deletion_results[bucket] = {
                            "success": True,
                            "deleted_objects": result.get("deleted_objects", []),
                            "total_deleted": result.get("total_deleted", 0)
                        }
                        print(f"Successfully deleted from {bucket}: {result.get('total_deleted', 0)} objects")
                    else:
                        deletion_results[bucket] = {
                            "success": False,
                            "error": f"HTTP {blob_response.status_code}: {blob_response.text}"
                        }
                        print(f"Failed to delete from {bucket}: {blob_response.status_code} - {blob_response.text}")
                        
                except Exception as e:
                    deletion_results[bucket] = {
                        "success": False,
                        "error": str(e)
                    }
                    print(f"Exception while deleting from {bucket}: {str(e)}")
            
            return deletion_results
            
        except Exception as e:
            print(f"Error in deleteObjectFilesFromBlobStorage: {str(e)}")
            return {
                "error": str(e),
                "success": False
            }

    async def run_app(self):
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()

class Data():
    def __init__(self):
        pass

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