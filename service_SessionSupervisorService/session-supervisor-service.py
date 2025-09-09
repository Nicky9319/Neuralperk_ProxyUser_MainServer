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
        
        # HTTP client for making requests to MongoDB service and Auth service
        self.http_client = httpx.AsyncClient(timeout=30.0)


    async def workload_removing_callback(self, customer_id: str):
        del self.data_class.customerSessionsMapping[customer_id]
   
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
        
        @self.app.post("/api/session-supervisor-service/")
        async def sessionSupervisorServiceRoot(request: Request):
            print("Session Supervisor Service Root Endpoint Hit")
            return JSONResponse(content={"message": "Session Supervisor Service is active"}, status_code=200)

        @self.app.post("/api/session-supervisor-service/start-workload")
        async def startWorkload(
            customer_id: str = Form(...),
            object_id: str = Form(...)
        ):
            try:
                if customer_id in self.data_class.customerSessionsMapping.keys():
                    return JSONResponse(content={"message": "One workload already running. Your Access Plan doesnt allow to run another workload"}, status_code=400)

                new_session = sessionClass(customer_id=customer_id, object_id=object_id, workload_completed_callback=self.workload_removing_callback)
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
            session_status = await self.data_class.customerSessionsMapping[customer_id].get_session_status()
            return JSONResponse(content={"message": "Workload status", "status": session_status}, status_code=200)

        @self.app.post("/api/session-supervisor-service/stop-and-delete-workload")
        async def getWorkloadResults(
            customer_id: str = Form(...),
        ):
            response = await self.data_class.customerSessionsMapping[customer_id].stop_and_delete_workload()
            if response.status_code == 200:
                return JSONResponse(content={"message": "Workload stopped and deleted"}, status_code=response.status_code)
            else:
                return JSONResponse(content={"message": "Failed to stop and delete workload"}, status_code=response.status_code)
            


    async def run_app(self):
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()

class Data():
    def __init__(self):
        self.customerSessionsMapping = {}

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
    asyncio.run(start_service())