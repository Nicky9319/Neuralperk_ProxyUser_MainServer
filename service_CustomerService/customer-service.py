import asyncio

from fastapi import FastAPI, Response, Request, HTTPException, Depends
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
        
        # HTTP client for making requests to MongoDB service and Auth service
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def authenticate_token(self, credentials: HTTPAuthorizationCredentials = Depends(security)):
        """
        Middleware function to authenticate the access token (customerId)
        This function will be called before any protected endpoint
        """
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
            request: Request, 
            customer_id: str = Depends(self.authenticate_token)
        ):
            print(f"Upload blend file endpoint hit for customer: {customer_id}")
            # TODO: Implement actual business logic
            return JSONResponse(content={"message": "Upload blend file endpoint", "customer_id": customer_id}, status_code=200)

        @self.app.post("/api/customer-service/start-workload")
        async def startWorkload(
            request: Request, 
            customer_id: str = Depends(self.authenticate_token)
        ):
            print(f"Start workload endpoint hit for customer: {customer_id}")
            # TODO: Implement actual business logic
            return JSONResponse(content={"message": "Start workload endpoint", "customer_id": customer_id}, status_code=200)

        @self.app.post("/api/customer-service/get-workload-status")
        async def getWorkloadStatus(
            request: Request, 
            customer_id: str = Depends(self.authenticate_token)
        ):
            print(f"Get workload status endpoint hit for customer: {customer_id}")
            # TODO: Implement actual business logic
            return JSONResponse(content={"message": "Get workload status endpoint", "customer_id": customer_id}, status_code=200)

        @self.app.post("/api/customer-service/stop-and-delete-workload")
        async def getWorkloadResults(
            request: Request, 
            customer_id: str = Depends(self.authenticate_token)
        ):
            print(f"Stop and delete workload endpoint hit for customer: {customer_id}")
            # TODO: Implement actual business logic
            return JSONResponse(content={"message": "Stop and delete workload endpoint", "customer_id": customer_id}, status_code=200)
            
        @self.app.post("/api/customer-service/get-blend-file")
        async def getBlendFile(
            request: Request, 
            customer_id: str = Depends(self.authenticate_token)
        ):
            print(f"Get blend file endpoint hit for customer: {customer_id}")
            # TODO: Implement actual business logic
            return JSONResponse(content={"message": "Get blend file endpoint", "customer_id": customer_id}, status_code=200)
    
        @self.app.post("/api/customer-service/get-rendered-video")
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
        self.value = None

    def get_value(self):
        return self.value

    def set_value(self, value):
        self.value = value

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