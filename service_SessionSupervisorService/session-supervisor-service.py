import asyncio

from fastapi import FastAPI, Response, Request, HTTPException, Depends, File, Form, UploadFile, Query
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

# from customerAgent import customerAgent
from session_class import sessionClass

import sys
import os
import traceback

from dotenv import load_dotenv
load_dotenv()

class HTTP_SERVER():
    """
    HTTP Server class for the Session Supervisor Service.
    
    This class manages the FastAPI web server that provides REST API endpoints
    for controlling and monitoring rendering sessions. It handles session creation,
    workload management, progress tracking, and session cleanup.
    
    The server integrates with multiple services:
    - MongoDB Service: For data persistence
    - Auth Service: For authentication (if needed)
    - Blob Service: For file storage operations
    
    Attributes:
        app (FastAPI): The FastAPI application instance
        host (str): Server host address
        port (int): Server port number
        privilegedIpAddress (list): List of privileged IP addresses
        data_class (Data): Reference to the data management class
        mongodb_service_url (str): URL for MongoDB service
        auth_service_url (str): URL for authentication service
        blob_service_url (str): URL for blob storage service
        http_client (httpx.AsyncClient): HTTP client for service communication
    """
    
    def __init__(self, httpServerHost, httpServerPort, httpServerPrivilegedIpAddress=["127.0.0.1"], data_class_instance=None):
        """
        Initialize the HTTP Server for Session Supervisor Service.
        
        Sets up the FastAPI application with CORS middleware and configures
        connections to external services (MongoDB, Auth, Blob) based on
        environment variables.
        
        Args:
            httpServerHost (str): Host address for the HTTP server (e.g., "0.0.0.0")
            httpServerPort (int): Port number for the HTTP server (e.g., 7500)
            httpServerPrivilegedIpAddress (list): List of privileged IP addresses
                                                 Defaults to ["127.0.0.1"]
            data_class_instance (Data): Instance of the Data class for session management
                                      Defaults to None
                                      
        Environment Variables:
            MONGODB_SERVICE: URL for MongoDB service (defaults to http://127.0.0.1:12000)
            AUTH_SERVICE: URL for authentication service (defaults to http://127.0.0.1:10000)
            BLOB_SERVICE: URL for blob storage service (defaults to http://127.0.0.1:13000)
            
        Example:
            server = HTTP_SERVER(
                httpServerHost="0.0.0.0",
                httpServerPort=7500,
                data_class_instance=data_class
            )
        """
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

        # Get User Manager service URL from environment (needed for cleanup calls)
        user_manager_env_url = os.getenv("USER_MANAGER_SERVICE", "").strip()
        if not user_manager_env_url or not (user_manager_env_url.startswith("http://") or user_manager_env_url.startswith("https://")):
            self.user_manager_service_url = "http://127.0.0.1:7000"
        else:
            self.user_manager_service_url = user_manager_env_url
        
        # HTTP client for making requests to MongoDB service and Auth service
        self.http_client = httpx.AsyncClient(timeout=30.0)


    async def workload_completed_callback(self, customer_id: str):
        """
        Callback function to remove completed workload sessions.
        
        This method is called when a rendering workload is completed or needs
        to be cleaned up. It removes the customer's session from the active
        sessions mapping, freeing up resources and allowing new workloads
        to be started for that customer.
        
        Args:
            customer_id (str): Unique identifier of the customer whose
                             workload session should be removed
                             
        Example:
            await server.workload_completed_callback("customer-123")
        """
        print("Workload is Completed for the customer id : ", customer_id)

        # Attempt to update the blender object state to 'video-ready' in MongoDB
        session = None
        object_id = None
        try:
            session = self.data_class.customerSessionsMapping.get(customer_id)
            object_id = getattr(session, "object_id", None) if session else None
            if object_id:
                payload = {
                    "objectId": object_id,
                    "customerId": customer_id,
                    "objectState": "video-ready"
                }
                try:
                    resp = await self.http_client.put(
                        f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/change-state",
                        json=payload
                    )
                    if resp.status_code == 200:
                        print(f"Updated object state to 'video-ready' for object {object_id}")
                    else:
                        print(f"Warning: Failed to update object state. Status: {resp.status_code}, Response: {resp.text}")
                except Exception as e:
                    print(f"Error calling MongoDB service to update object state: {e}")
            else:
                print(f"No object_id available for customer {customer_id}; skipping DB update")
        except Exception as e:
            print(f"Unexpected error while attempting DB update in workload_completed_callback: {e}")

        # Also clean up the User Manager routing/session mapping similar to customer-service
        try:
            # Get the session supervisor information directly (no HTTP call to self)
            overview = await self.get_session_supervisor_information(customer_id)
        except Exception as e:
            overview = None
            print(f"Warning: Error fetching session supervisor overview for User Manager cleanup: {e}")

        try:
            if overview and not overview.get("error"):
                try:
                    session_supervisor_id = overview.get("session_id")
                    print(f"Cleaning up User Manager session for session_supervisor_id from session supervisor: {session_supervisor_id}")
                    if session_supervisor_id:
                        cleanup_resp = await self.http_client.request(
                            "DELETE",
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
                            print(f"User Manager cleanup successful for session_supervisor_id: {session_supervisor_id}")
                    else:
                        print("Warning: session_id not found in session supervisor overview; skipping User Manager cleanup")
                except Exception as e:
                    print(f"Warning: Error during User Manager cleanup processing: {e}")
            else:
                print(f"Warning: No session supervisor overview available for customer {customer_id}; skipping User Manager cleanup")
        except Exception as e:
            print(f"Warning: Error during User Manager cleanup: {str(e)}")

        # Ensure the session is stopped/cleaned and removed from the in-memory mapping.
        # This mirrors the stop-and-delete endpoint behavior and guarantees the
        # session mapping is cleared even if stop/cleanup throws.
        if customer_id in self.data_class.customerSessionsMapping:
            try:
                try:
                    response = await self.data_class.customerSessionsMapping[customer_id].stop_and_delete_workload()
                    # response is typically a JSONResponse; log status
                    status_code = getattr(response, 'status_code', None)
                    print(f"workload_completed_callback: stop_and_delete_workload status: {status_code}")
                except Exception as e:
                    # Log but continue to remove mapping to avoid stale entries
                    print(f"Error while stopping/cleaning session for {customer_id}: {e}")
            finally:
                # Always attempt to remove the session from the mapping so the
                # server is free to accept new workloads for this customer.
                try:
                    del self.data_class.customerSessionsMapping[customer_id]
                    print(f"Session removed from mapping for customer_id: {customer_id}")
                except KeyError:
                    print(f"Session for {customer_id} already removed from mapping")
                except Exception as e:
                    print(f"Unexpected error removing session from mapping for {customer_id}: {e}")
   
    async def configure_routes(self):
        """
        Configure all API routes and endpoints for the Session Supervisor Service.
        
        This method sets up all the REST API endpoints that clients can use to:
        - Check service health
        - Start new rendering workloads
        - Monitor workload status and progress
        - Stop and delete workloads
        
        The endpoints are configured with proper request/response handling,
        error management, and status codes.
        
        API Endpoints:
            POST /api/session-supervisor-service/ - Service health check
            POST /api/session-supervisor-service/start-workload - Start new workload
            GET /api/session-supervisor-service/get-workload-status - Get workload status
            POST /api/session-supervisor-service/stop-and-delete-workload - Stop workload
            GET /api/session-supervisor-service/get-workload-progress - Get progress
            
        Example:
            await server.configure_routes()
        """

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
        
        @self.app.post("/api/session-supervisor-service/")
        async def sessionSupervisorServiceRoot(request: Request):
            """
            Service health check endpoint.
            
            This endpoint provides a simple health check to verify that the
            Session Supervisor Service is running and responsive. It returns
            a basic status message confirming the service is active.
            
            Args:
                request (Request): FastAPI request object
                
            Returns:
                JSONResponse: Response containing service status message
                
            Status Codes:
                200: Service is active and responding
                
            Example Response:
                {
                    "message": "Session Supervisor Service is active"
                }
            """
            print("Session Supervisor Service Root Endpoint Hit")
            return JSONResponse(content={"message": "Session Supervisor Service is active"}, status_code=200)

        @self.app.post("/api/session-supervisor-service/start-workload")
        async def startWorkload(
            customer_id: str = Form(...),
            object_id: str = Form(...)
        ):
            """
            Start a new rendering workload for a customer's 3D object.
            
            This endpoint creates a new rendering session for the specified customer
            and object. It checks if the customer already has an active workload
            and prevents multiple concurrent workloads per customer.
            
            The endpoint creates a new session supervisor that will:
            1. Download the blend file from blob storage
            2. Determine the frame range to render
            3. Request users from the User Manager
            4. Distribute frames among available users
            5. Monitor rendering progress
            
            Args:
                customer_id (str): Unique identifier for the customer
                                 Provided as form data
                object_id (str): Unique identifier for the 3D object to render
                               Provided as form data
                               
            Returns:
                JSONResponse: Response containing workload start status
                
            Status Codes:
                200: Workload started successfully
                400: Customer already has an active workload
                500: Internal server error during workload creation
                
            Example Request:
                POST /api/session-supervisor-service/start-workload
                Content-Type: application/x-www-form-urlencoded
                
                customer_id=customer-123&object_id=object-456
                
            Example Response (Success):
                {
                    "message": "Workload started"
                }
                
            Example Response (Error):
                {
                    "message": "One workload already running. Your Access Plan doesnt allow to run another workload"
                }
            """
            try:
                if customer_id in self.data_class.customerSessionsMapping.keys():
                    return JSONResponse(content={"message": "One workload already running. Your Access Plan doesnt allow to run another workload"}, status_code=400)

                new_session = sessionClass(customer_id=customer_id, object_id=object_id, workload_completed_callback=self.workload_completed_callback)
                self.data_class.customerSessionsMapping[customer_id] = new_session
                response = await new_session.start_workload()
                # JSONResponse does not have a .content attribute; to print the response body, access .body and decode it
                print(response.body.decode())

                if response.status_code == 200:
                    return JSONResponse(content={"message": "Workload started"}, status_code=response.status_code)
                else:
                    return JSONResponse(content={"message": "Failed to start workload"}, status_code=response.status_code)
            except Exception as e:
                import traceback
                print(f"Error in startWorkload: {traceback.format_exc()}")
                return JSONResponse(content={"message": "Internal server error", "details": str(e)}, status_code=500)
            

        @self.app.get("/api/session-supervisor-service/get-workload-status")
        async def getWorkloadStatus(
            customer_id: str = Query(...),
        ):
            """
            Get the current status of a customer's rendering workload.
            
            This endpoint retrieves the current status of an active rendering
            session for the specified customer. It provides information about
            the workload state, completion status, and other session details.
            
            Args:
                customer_id (str): Unique identifier for the customer
                                 Provided as query parameter
                                 
            Returns:
                JSONResponse: Response containing workload status information
                
            Status Codes:
                200: Status retrieved successfully
                404: No active workload found for customer
                
            Example Request:
                GET /api/session-supervisor-service/get-workload-status?customer_id=customer-123
                
            Example Response:
                {
                    "message": "Workload status",
                    "status": {
                        "workload_status": "running",
                        "total_frames": 250,
                        "completed_frames": 125,
                        "completion_percentage": 50.0
                    }
                }
            """
            session_status = await self.data_class.customerSessionsMapping[customer_id].get_session_status()
            return JSONResponse(content={"message": "Workload status", "status": session_status}, status_code=200)

        @self.app.post("/api/session-supervisor-service/stop-and-delete-workload")
        async def getWorkloadResults(
                customer_id: str = Form(...),
            ):
                """
                Stop and delete an active rendering workload for a customer.
                
                This endpoint terminates an active rendering session and performs
                cleanup operations. It stops all rendering work, releases users
                back to the User Manager, and removes the session from memory.
                
                The endpoint performs the following actions:
                1. Stops all rendering work for the session
                2. Releases all assigned users
                3. Cleans up session resources
                4. Removes the session from active sessions mapping
                
                Args:
                customer_id (str): Unique identifier for the customer
                            Provided as form data
                            
                Returns:
                JSONResponse: Response containing stop/delete operation status
                
                Status Codes:
                200: Workload stopped and deleted successfully
                404: No active workload found for customer
                500: Error during workload termination
                
                Example Request:
                POST /api/session-supervisor-service/stop-and-delete-workload
                Content-Type: application/x-www-form-urlencoded
                
                customer_id=customer-123
                
                Example Response (Success):
                {
                    "message": "Workload stopped and deleted"
                }
                
                Example Response (Error):
                {
                    "message": "Failed to stop and delete workload"
                }
                """
                print(f"[stop-and-delete-workload] Endpoint hit for customer_id: {customer_id}")
                if customer_id not in self.data_class.customerSessionsMapping:
                    print(f"[stop-and-delete-workload] No active workload found for customer_id: {customer_id}")
                    return JSONResponse(content={"message": "No active workload found for customer"}, status_code=404)
                try:
                    print(f"[stop-and-delete-workload] Stopping and deleting workload for customer_id: {customer_id}")
                    response = await self.data_class.customerSessionsMapping[customer_id].stop_and_delete_workload()
                    print(f"[stop-and-delete-workload] Workload stop response: {response}")
                    del self.data_class.customerSessionsMapping[customer_id]
                    print(f"[stop-and-delete-workload] Session removed from mapping for customer_id: {customer_id}")
                    if response.status_code == 200:
                        print(f"[stop-and-delete-workload] Workload stopped and deleted successfully for customer_id: {customer_id}")
                        return JSONResponse(content={"message": "Workload stopped and deleted"}, status_code=response.status_code)
                    else:
                        print(f"[stop-and-delete-workload] Failed to stop and delete workload for customer_id: {customer_id}, status_code: {response.status_code}")
                        return JSONResponse(content={"message": "Failed to stop and delete workload"}, status_code=response.status_code)
                except Exception as e:
                    print(f"[stop-and-delete-workload] Error for customer_id: {customer_id}: {traceback.format_exc()}")
                    return JSONResponse(content={"message": "Internal server error", "details": str(e)}, status_code=500)


        @self.app.get("/api/session-supervisor-service/get-workload-progress")
        async def getWorkloadProgress(
            customer_id: str = Query(...),
        ):
            """
            Get detailed progress information for a customer's rendering workload.
            
            This endpoint provides comprehensive progress information about an
            active rendering session, including frame completion statistics,
            user assignments, and detailed rendering progress.
            
            Args:
                customer_id (str): Unique identifier for the customer
                                 Provided as query parameter
                                 
            Returns:
                JSONResponse: Response containing detailed progress information
                
            Status Codes:
                200: Progress information retrieved successfully
                404: No active workload found for customer
                
            Example Request:
                GET /api/session-supervisor-service/get-workload-progress?customer_id=customer-123
                
            Example Response:
                {
                    "total_frames": 250,
                    "completed_frames": 125,
                    "remaining_frames": 125,
                    "progress_percentage": 50.0,
                    "workload_status": "running",
                    "active_users": 3,
                    "frame_mapping": {
                        "1": "user-123",
                        "2": "user-123",
                        "3": "user-456"
                    }
                }
            """
            response = await self.data_class.customerSessionsMapping[customer_id].get_session_progress()
            return JSONResponse(content=response, status_code=200)

        # -------------------------
        # Admin Panel Controls
        # -------------------------


        @self.app.get("/api/session-supervisor-service/get-all-supervisor-information")
        async def getAllSupervisorInformation(request: Request):
            response_list = []
            for customer_id in self.data_class.customerSessionsMapping.keys():
                print(f"Session Information retrieving for Customer ID: {customer_id}")
                response = await self.get_session_supervisor_information(customer_id)
                response_list.append(response)
            return JSONResponse(content=response_list, status_code=200)
            
        @self.app.get("/api/session-supervisor-service/get-session-supervisor-overview/{customer_id}")
        async def getSessionSupervisorOverview(customer_id: str):
            response = await self.get_session_supervisor_information(customer_id)          
            return JSONResponse(content=response, status_code=200)

        @self.app.get("/api/session-supervisor-service/get-user-count/{customer_id}")
        async def getUserCount(
            customer_id: str
        ):
            """
            Get the number of users assigned to a session supervisor.

            This endpoint retrieves the current number of users assigned to a
            session supervisor. It provides information about the current user
            count for the session supervisor.
            """
            try:
                if customer_id not in self.data_class.customerSessionsMapping:
                    return JSONResponse(content={"message": f"No active session for customer_id: {customer_id}"}, status_code=404)
                response = await self.data_class.customerSessionsMapping[customer_id].get_number_of_users()
                return JSONResponse(content=response, status_code=200)
            except Exception as e:
                return JSONResponse(content={"message": f"Error retrieving user count: {str(e)}"}, status_code=500)

        @self.app.post("/api/session-supervisor-service/set-user-count/{customer_id}/{user_count}")
        async def setUserCount(
            customer_id: str,
            user_count: int
        ):
            """
            Set the number of users assigned to a session supervisor.

            This endpoint sets the number of users assigned to a session supervisor.
            It updates the user count for the session supervisor.
            """
            print(f"[setUserCount] Endpoint hit for customer_id: {customer_id}, user_count: {user_count}")
            try:
                if customer_id not in self.data_class.customerSessionsMapping:
                    print(f"[setUserCount] No active session for customer_id: {customer_id}")
                    return JSONResponse(content={"message": f"No active session for customer_id: {customer_id}"}, status_code=404)
                print(f"[setUserCount] Setting user count for customer_id: {customer_id} to {user_count}")
                response = await self.data_class.customerSessionsMapping[customer_id].set_user_count(user_count)
                print(f"[setUserCount] Response: {response}")
                return JSONResponse(content=response, status_code=200)
            except Exception as e:
                print(f"[setUserCount] Error setting user count for customer_id: {customer_id}: {str(e)}")
                return JSONResponse(content={"message": f"Error setting user count: {str(e)}"}, status_code=500)

    async def get_session_supervisor_information(self, customer_id: str):
        """
        Retrieve session supervisor information for a given customer_id, with error handling.

        Args:
            customer_id (str): The customer ID whose session supervisor info is requested.

        Returns:
            dict: Information about the session supervisor, or an error message.
        """
        try:
            if customer_id not in self.data_class.customerSessionsMapping:
                return {
                    "error": f"No active session for customer_id: {customer_id}"
                }
            supervisor = self.data_class.customerSessionsMapping[customer_id]
            return {
                "customer_id": customer_id,
                "object_id": getattr(supervisor, "object_id", None),
                "session_routing_key": getattr(supervisor, "sessionRoutingKey", None),
                "session_id": getattr(supervisor, "session_id", None),
                "number_of_users": await supervisor.get_number_of_users() if hasattr(supervisor, "get_number_of_users") else None,
                "session_status": getattr(supervisor, "session_status", None),
            }
        except Exception as e:
            print("Error in get_session_supervisor_information: ", e)
            return {
                "error": f"Error retrieving session supervisor information: {str(e)}"
            }


    async def run_app(self):
        """
        Start the FastAPI application server.
        
        This method configures and starts the uvicorn ASGI server to serve
        the FastAPI application. It sets up the server with the configured
        host and port, then starts serving HTTP requests.
        
        The server will run indefinitely until stopped, handling all incoming
        HTTP requests to the configured endpoints.
        
        Example:
            await server.run_app()
        """
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()

class Data():
    """
    Data management class for the Session Supervisor Service.
    
    This class manages the in-memory storage of active rendering sessions.
    It maintains a mapping between customer IDs and their active session
    supervisor instances, allowing the service to track and manage multiple
    concurrent rendering workloads.
    
    Attributes:
        customerSessionsMapping (dict): Dictionary mapping customer IDs to
                                      their active session supervisor instances
                                      Format: {customer_id: session_supervisor_instance}
    """
    
    def __init__(self):
        """
        Initialize the Data class with empty session mapping.
        
        Creates a new Data instance with an empty dictionary to store
        customer session mappings. This dictionary will be populated
        as customers start new rendering workloads.
        
        Example:
            data_class = Data()
            # data_class.customerSessionsMapping is now an empty dict {}
        """
        self.customerSessionsMapping = {}

class Service():
    """
    Main service class that orchestrates the Session Supervisor Service.
    
    This class acts as the main coordinator for the Session Supervisor Service,
    managing the HTTP server lifecycle and ensuring proper initialization
    and startup of all service components.
    
    Attributes:
        httpServer (HTTP_SERVER): Instance of the HTTP server class
    """
    
    def __init__(self, httpServer = None):
        """
        Initialize the Service with an HTTP server instance.
        
        Args:
            httpServer (HTTP_SERVER): HTTP server instance to manage
                                   Defaults to None
                                   
        Example:
            service = Service(http_server)
        """
        self.httpServer = httpServer

    async def startService(self):
        """
        Start the Session Supervisor Service.
        
        This method initializes and starts the service by:
        1. Configuring all API routes and endpoints
        2. Starting the HTTP server to handle requests
        
        The service will run indefinitely until stopped, serving HTTP requests
        and managing rendering sessions.
        
        Example:
            await service.startService()
        """
        await self.httpServer.configure_routes()
        await self.httpServer.run_app()

        
async def start_service():
    """
    Main entry point for starting the Session Supervisor Service.
    
    This function initializes and starts the complete Session Supervisor Service
    by creating all necessary components and starting the HTTP server. It sets up:
    1. Data management class for session tracking
    2. HTTP server with configured host, port, and settings
    3. Main service orchestrator
    4. Starts the service to handle requests
    
    The service runs on the following default configuration:
    - Host: 0.0.0.0 (accepts connections from any IP)
    - Port: 7500
    - Privileged IPs: 127.0.0.1 (localhost)
    
    The service will run indefinitely until manually stopped.
    
    Example:
        # Run the service
        await start_service()
        
    Note:
        This function is typically called from the main execution block
        or by a process manager/supervisor.
    """
    dataClass = Data()

    #<HTTP_SERVER_INSTANCE_INTIALIZATION_START>

    #<HTTP_SERVER_PORT_START>
    httpServerPort = 7500
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
    """
    Main execution block for the Session Supervisor Service.
    
    This block runs when the script is executed directly (not imported as a module).
    It starts the Session Supervisor Service using asyncio to handle the async
    nature of the FastAPI application and message queue operations.
    
    The service will start and run indefinitely, handling HTTP requests and
    managing rendering sessions until manually stopped (Ctrl+C).
    
    Usage:
        python session-supervisor-service.py
        
    Note:
        This is the standard entry point for running the service as a standalone
        application. For production deployments, consider using a process manager
        like systemd, supervisor, or Docker.
    """
    asyncio.run(start_service())