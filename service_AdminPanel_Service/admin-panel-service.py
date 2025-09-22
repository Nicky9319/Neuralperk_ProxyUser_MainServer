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


    # ----------------------------
    # API Calls Section
    # ----------------------------

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
        
        @self.app.post("/api/admin-panel-service/")
        async def adminPanelServiceRoot(request: Request):
            """
            Admin Panel Service Health Check Endpoint
            
            This endpoint provides a simple health check to verify that the Admin Panel Service
            is running and accessible.
            
            Returns:
                JSONResponse: A simple status message confirming the service is active
                
            Example Response:
                {
                    "message": "Admin Panel Service is active"
                }
            """
            print("Admin Panel Service Root Endpoint Hit")
            return JSONResponse(content={"message": "Admin Panel Service is active"}, status_code=200)
         

        # ----------------------------
        # Session Supervisor API Calls
        # ----------------------------

        @self.app.get("/api/admin-panel-service/get-all-session-supervisor-information")
        async def getAllSessionSupervisorInformation(request: Request):
            """
            Get information about all active session supervisors.
            
            This endpoint retrieves comprehensive information about all active
            session supervisors from the Session Supervisor Service. It provides
            an overview of all running rendering sessions, their status, and
            associated metadata.
            
            Args:
                request (Request): FastAPI request object
                
            Returns:
                JSONResponse: Response containing list of all session supervisor information
                
            Status Codes:
                200: Information retrieved successfully
                500: Error communicating with Session Supervisor Service
                
            Example Response:
                [
                    {
                        "object_id": "object-123",
                        "session_routing_key": "SESSION_SUPERVISOR_abc-123",
                        "session_id": "session-456",
                        "number_of_users": 3,
                        "session_status": "running"
                    },
                    {
                        "object_id": "object-789",
                        "session_routing_key": "SESSION_SUPERVISOR_def-456",
                        "session_id": "session-789",
                        "number_of_users": 2,
                        "session_status": "completed"
                    }
                ]
            """
            try:
                response = await self.http_client.get(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-all-supervisor-information"
                )
                
                if response.status_code == 200:
                    return JSONResponse(content=response.json(), status_code=200)
                else:
                    return JSONResponse(
                        content={"message": "Failed to retrieve session supervisor information"}, 
                        status_code=response.status_code
                    )
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error communicating with Session Supervisor Service: {str(e)}"}, 
                    status_code=500
                )
    
        @self.app.get("/api/admin-panel-service/get-session-supervisor-overview/{customer_id}")
        async def getSessionSupervisorOverview(customer_id: str):
            """
            Get detailed overview information for a specific session supervisor.
            
            This endpoint retrieves comprehensive information about a specific
            session supervisor identified by customer_id. It provides details
            about the session status, user assignments, and other session metadata.
            
            Args:
                customer_id (str): Unique identifier for the customer/session supervisor
                                 Provided as path parameter
                
            Returns:
                JSONResponse: Response containing session supervisor overview information
                
            Status Codes:
                200: Overview retrieved successfully
                404: No active session found for customer
                500: Error communicating with Session Supervisor Service
                
            Example Response:
                {
                    "object_id": "object-123",
                    "session_routing_key": "SESSION_SUPERVISOR_abc-123",
                    "session_id": "session-456",
                    "number_of_users": 3,
                    "session_status": "running"
                }
            """
            try:
                response = await self.http_client.get(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-session-supervisor-overview/{customer_id}"
                )
                
                if response.status_code == 200:
                    return JSONResponse(content=response.json(), status_code=200)
                else:
                    return JSONResponse(
                        content={"message": f"Failed to retrieve session supervisor overview for customer_id: {customer_id}"}, 
                        status_code=response.status_code
                    )
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error communicating with Session Supervisor Service: {str(e)}"}, 
                    status_code=500
                )
    
        @self.app.get("/api/admin-panel-service/get-session-supervisor-user-count/{customer_id}")
        async def getSessionSupervisorUserCount(customer_id: str):
            """
            Get the current number of users assigned to a session supervisor.
            
            This endpoint retrieves the current user count for a specific session
            supervisor identified by customer_id. It provides information about
            how many users are currently assigned to handle the rendering workload.
            
            Args:
                customer_id (str): Unique identifier for the customer/session supervisor
                                 Provided as path parameter
                
            Returns:
                JSONResponse: Response containing user count information
                
            Status Codes:
                200: User count retrieved successfully
                404: No active session found for customer
                500: Error communicating with Session Supervisor Service
                
            Example Response:
                {
                    "customer_id": "customer-123",
                    "user_count": 3,
                    "message": "User count retrieved successfully"
                }
            """
            try:
                response = await self.http_client.get(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-user-count/{customer_id}"
                )
                
                if response.status_code == 200:
                    return JSONResponse(content=response.json(), status_code=200)
                else:
                    return JSONResponse(
                        content={"message": f"Failed to retrieve user count for customer_id: {customer_id}"}, 
                        status_code=response.status_code
                    )
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error communicating with Session Supervisor Service: {str(e)}"}, 
                    status_code=500
                )
    
        @self.app.put("/api/admin-panel-service/set-session-supervisor-user-count/{customer_id}/{user_count}")
        async def setSessionSupervisorUserCount(customer_id: str, user_count: int):
            """
            Set the number of users assigned to a session supervisor.
            
            This endpoint allows administrators to dynamically adjust the number
            of users assigned to a specific session supervisor. This can be used
            to scale up or down the rendering capacity based on workload demands
            or system resources.
            
            Args:
                customer_id (str): Unique identifier for the customer/session supervisor
                                 Provided as path parameter
                user_count (int): Desired number of users to assign
                                Provided as path parameter
                
            Returns:
                JSONResponse: Response containing the result of the user count update
                
            Status Codes:
                200: User count updated successfully
                404: No active session found for customer
                500: Error communicating with Session Supervisor Service
                
            Example Response:
                {
                    "customer_id": "customer-123",
                    "user_count": 5,
                    "message": "User count updated successfully"
                }
            """
            try:
                response = await self.http_client.post(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/set-user-count/{customer_id}/{user_count}"
                )
                
                if response.status_code == 200:
                    return JSONResponse(content=response.json(), status_code=200)
                else:
                    return JSONResponse(
                        content={"message": f"Failed to set user count for customer_id: {customer_id}"}, 
                        status_code=response.status_code
                    )
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error communicating with Session Supervisor Service: {str(e)}"}, 
                    status_code=500
                )

        # ----------------------------
        # User Manager API Calls
        # ----------------------------

        @self.app.get("/api/admin-panel-service/get-user-manager-overview")
        async def getUserManagerOverview(request: Request):
            """
            Get comprehensive overview of User Manager service state.
            
            This endpoint retrieves detailed information about the current state
            of the User Manager service, including user mappings, session
            supervisor information, demand queue status, and active sessions.
            
            Args:
                request (Request): FastAPI request object
                
            Returns:
                JSONResponse: Response containing User Manager overview information
                
            Status Codes:
                200: Overview retrieved successfully
                500: Error communicating with User Manager Service
                
            Example Response:
                {
                    "userToSupervisorIdMapping": {
                        "user-123": "supervisor-456",
                        "user-789": "supervisor-456"
                    },
                    "supervisorToRoutingKeyMapping": {
                        "supervisor-456": "SESSION_SUPERVISOR_456"
                    },
                    "user_demand_queue": [
                        {
                            "user_count": 3,
                            "session_supervisor_id": "supervisor-789"
                        }
                    ],
                    "activeSessions": ["supervisor-456", "supervisor-789"],
                    "idle_users": ["user-111", "user-222"]
                }
            """
            try:
                response = await self.http_client.get(
                    f"{self.user_manager_service_url}/api/user-manager/get-overview"
                )
                
                if response.status_code == 200:
                    return JSONResponse(content=response.json(), status_code=200)
                else:
                    return JSONResponse(
                        content={"message": "Failed to retrieve User Manager overview"}, 
                        status_code=response.status_code
                    )
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error communicating with User Manager Service: {str(e)}"}, 
                    status_code=500
                )

        # ----------------------------
        # System Overview API Calls
        # ----------------------------

        @self.app.get("/api/admin-panel-service/get-system-overview")
        async def getSystemOverview(request: Request):
            """
            Get comprehensive system overview combining all services.
            
            This endpoint provides a complete overview of the entire system by
            combining information from both the User Manager and Session Supervisor
            services. It gives administrators a unified view of the system state.
            
            Args:
                request (Request): FastAPI request object
                
            Returns:
                JSONResponse: Response containing comprehensive system overview
                
            Status Codes:
                200: System overview retrieved successfully
                500: Error communicating with services
                
            Example Response:
                {
                    "user_manager": {
                        "userToSupervisorIdMapping": {...},
                        "supervisorToRoutingKeyMapping": {...},
                        "user_demand_queue": [...],
                        "activeSessions": [...],
                        "idle_users": [...]
                    },
                    "session_supervisors": [
                        {
                            "object_id": "object-123",
                            "session_routing_key": "SESSION_SUPERVISOR_abc-123",
                            "session_id": "session-456",
                            "number_of_users": 3,
                            "session_status": "running"
                        }
                    ],
                    "system_summary": {
                        "total_active_sessions": 2,
                        "total_idle_users": 5,
                        "total_demand_requests": 1
                    }
                }
            """
            try:
                # Get User Manager overview
                user_manager_response = await self.http_client.get(
                    f"{self.user_manager_service_url}/api/user-manager/get-overview"
                )
                
                # Get Session Supervisor information
                session_supervisor_response = await self.http_client.get(
                    f"{self.session_supervisor_service_url}/api/session-supervisor-service/get-all-supervisor-information"
                )
                
                user_manager_data = user_manager_response.json() if user_manager_response.status_code == 200 else {}
                session_supervisor_data = session_supervisor_response.json() if session_supervisor_response.status_code == 200 else []
                
                # Calculate system summary
                system_summary = {
                    "total_active_sessions": len(user_manager_data.get("activeSessions", [])),
                    "total_idle_users": len(user_manager_data.get("idle_users", [])),
                    "total_demand_requests": len(user_manager_data.get("user_demand_queue", [])),
                    "total_session_supervisors": len(session_supervisor_data)
                }
                
                system_overview = {
                    "user_manager": user_manager_data,
                    "session_supervisors": session_supervisor_data,
                    "system_summary": system_summary
                }
                
                return JSONResponse(content=system_overview, status_code=200)
                
            except Exception as e:
                return JSONResponse(
                    content={"message": f"Error retrieving system overview: {str(e)}"}, 
                    status_code=500
                )

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
    httpServerPort = 15000
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