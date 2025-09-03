import asyncio
from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import json
from datetime import datetime
import uuid

import asyncio
import aio_pika


import sys
import os

# Import necessary MongoDB modules
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import DuplicateKeyError



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

        # MongoDB connection setup
        self.mongo_client = MongoClient('mongodb://localhost:27017/', server_api=ServerApi('1'))
        self.db = self.mongo_client["neuralperk"]  # Database name from MongoSchema.json
        
        # Collections based on schema
        self.customers_collection = self.db["customers"]
        self.blender_objects_collection = self.db["blenderObjects"]
        self.sessions_collection = self.db["sessions"]


    def parse_date_time(self,field):
        if isinstance(field, dict) and "$date" in field:
            return datetime.fromisoformat(field["$date"].replace("Z", "+00:00"))
        return field

       
    async def configure_routes(self):
        # ========================================
        # ROOT ENDPOINT
        # ========================================
        @self.app.get("/api/mongodb-service/")
        async def root():
            """Root endpoint to check if MongoDB Service is active"""
            return JSONResponse(content={"message": "MongoDB Service is Active"}, status_code=200)
        
        # ========================================
        # CUSTOMER MANAGEMENT ENDPOINTS
        # ========================================
        
        @self.app.post("/api/mongodb-service/customers/add")
        async def add_customer(request: Request):
            """Add a new customer to the database
            Required fields: customerId, email, password
            Returns: Success message with customer details
            """
            try:
                body = await request.json()
                
                # Validate required fields
                required_fields = ["customerId", "email", "password"]
                for field in required_fields:
                    if field not in body:
                        raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
                
                # Check if customer already exists
                existing_customer = self.customers_collection.find_one({"customerId": body["customerId"]})
                if existing_customer:
                    raise HTTPException(status_code=409, detail="Customer with this ID already exists")
                
                # Create customer document
                customer_doc = {
                    "customerId": body["customerId"],
                    "email": body["email"],
                    "password": body["password"]
                }
                
                result = self.customers_collection.insert_one(customer_doc)
                
                return JSONResponse(
                    content={
                        "message": "Customer added successfully",
                        "customerId": body["customerId"],
                        "email": body["email"]
                    },
                    status_code=201
                )
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.get("/api/mongodb-service/customers/check/{customer_id}")
        async def check_customer_exists(customer_id: str):
            """Check if a customer exists in the database
            Parameters: customer_id (path parameter)
            Returns: Customer exists status and basic info if found
            """
            try:
                customer = self.customers_collection.find_one({"customerId": customer_id})
                
                if customer:
                    return JSONResponse(
                        content={
                            "exists": True,
                            "customerId": customer["customerId"],
                            "email": customer["email"]
                        },
                        status_code=200
                    )
                else:
                    return JSONResponse(
                        content={
                            "exists": False,
                            "message": "Customer not found"
                        },
                        status_code=404
                    )
                    
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        # ========================================
        # BLENDER OBJECT MANAGEMENT ENDPOINTS
        # ========================================
        
        @self.app.post("/api/mongodb-service/blender-objects/add")
        async def add_blender_object(request: Request):
            """Add a new blender object to the database
            Required fields: objectId, customerId
            Optional fields: blendFilePath, renderedVideoPath
            Returns: Success message with object details
            """
            try:
                body = await request.json()
                
                # Validate required fields
                required_fields = ["objectId", "customerId"]
                for field in required_fields:
                    if field not in body:
                        raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
                
                # Check if customer exists
                customer = self.customers_collection.find_one({"customerId": body["customerId"]})
                if not customer:
                    raise HTTPException(status_code=404, detail="Customer not found")
                
                # Check if object already exists
                existing_object = self.blender_objects_collection.find_one({"objectId": body["objectId"]})
                if existing_object:
                    raise HTTPException(status_code=409, detail="Object with this ID already exists")
                
                # Create blender object document
                object_doc = {
                    "objectId": body["objectId"],
                    "blendFilePath": body.get("blendFilePath", None),
                    "renderedVideoPath": body.get("renderedVideoPath", None),
                    "customerId": body["customerId"]
                }
                
                result = self.blender_objects_collection.insert_one(object_doc)
                
                return JSONResponse(
                    content={
                        "message": "Blender object added successfully",
                        "objectId": body["objectId"],
                        "customerId": body["customerId"]
                    },
                    status_code=201
                )
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.put("/api/mongodb-service/blender-objects/update-blend-file")
        async def update_blend_file_path(request: Request):
            """Update the blend file path for a blender object
            Required fields: objectId, customerId, blendFilePath
            Returns: Success message with updated object details
            """
            try:
                body = await request.json()
                
                # Validate required fields
                required_fields = ["objectId", "customerId", "blendFilePath"]
                for field in required_fields:
                    if field not in body:
                        raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
                
                # Check if customer exists
                customer = self.customers_collection.find_one({"customerId": body["customerId"]})
                if not customer:
                    raise HTTPException(status_code=404, detail="Customer not found")
                
                # Update the blend file path
                result = self.blender_objects_collection.update_one(
                    {"objectId": body["objectId"], "customerId": body["customerId"]},
                    {"$set": {"blendFilePath": body["blendFilePath"]}}
                )
                
                if result.matched_count == 0:
                    raise HTTPException(status_code=404, detail="Blender object not found")
                
                return JSONResponse(
                    content={
                        "message": "Blend file path updated successfully",
                        "objectId": body["objectId"],
                        "blendFilePath": body["blendFilePath"]
                    },
                    status_code=200
                )
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.put("/api/mongodb-service/blender-objects/update-video-file")
        async def update_video_file_path(request: Request):
            """Update the rendered video path for a blender object
            Required fields: objectId, customerId, renderedVideoPath
            Returns: Success message with updated object details
            """
            try:
                body = await request.json()
                
                # Validate required fields
                required_fields = ["objectId", "customerId", "renderedVideoPath"]
                for field in required_fields:
                    if field not in body:
                        raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
                
                # Check if customer exists
                customer = self.customers_collection.find_one({"customerId": body["customerId"]})
                if not customer:
                    raise HTTPException(status_code=404, detail="Customer not found")
                
                # Update the video file path
                result = self.blender_objects_collection.update_one(
                    {"objectId": body["objectId"], "customerId": body["customerId"]},
                    {"$set": {"renderedVideoPath": body["renderedVideoPath"]}}
                )
                
                if result.matched_count == 0:
                    raise HTTPException(status_code=404, detail="Blender object not found")
                
                return JSONResponse(
                    content={
                        "message": "Video file path updated successfully",
                        "objectId": body["objectId"],
                        "renderedVideoPath": body["renderedVideoPath"]
                    },
                    status_code=200
                )
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        # ========================================
        # SESSION MANAGEMENT ENDPOINTS
        # ========================================
        
        @self.app.post("/api/mongodb-service/sessions/add")
        async def add_session(request: Request):
            """Add a new session to the database
            Required fields: sessionId, customerId, blenderObjectId
            Optional fields: status (defaults to 'queued')
            Returns: Success message with session details
            """
            try:
                body = await request.json()
                
                # Validate required fields
                required_fields = ["sessionId", "customerId", "blenderObjectId"]
                for field in required_fields:
                    if field not in body:
                        raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
                
                # Check if customer exists
                customer = self.customers_collection.find_one({"customerId": body["customerId"]})
                if not customer:
                    raise HTTPException(status_code=404, detail="Customer not found")
                
                # Check if blender object exists
                blender_object = self.blender_objects_collection.find_one({"objectId": body["blenderObjectId"]})
                if not blender_object:
                    raise HTTPException(status_code=404, detail="Blender object not found")
                
                # Check if session already exists
                existing_session = self.sessions_collection.find_one({"sessionId": body["sessionId"]})
                if existing_session:
                    raise HTTPException(status_code=409, detail="Session with this ID already exists")
                
                # Create session document with default status 'queued'
                session_doc = {
                    "sessionId": body["sessionId"],
                    "customerId": body["customerId"],
                    "blenderObjectId": body["blenderObjectId"],
                    "status": body.get("status", "queued")
                }
                
                result = self.sessions_collection.insert_one(session_doc)
                
                return JSONResponse(
                    content={
                        "message": "Session added successfully",
                        "sessionId": body["sessionId"],
                        "status": session_doc["status"]
                    },
                    status_code=201
                )
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        
        @self.app.put("/api/mongodb-service/sessions/update-status")
        async def update_session_status(request: Request):
            """Update the status of a session
            Required fields: sessionId, status
            Returns: Success message with updated session details
            """
            try:
                body = await request.json()
                
                # Validate required fields
                required_fields = ["sessionId", "status"]
                for field in required_fields:
                    if field not in body:
                        raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
                
                # Update the session status
                result = self.sessions_collection.update_one(
                    {"sessionId": body["sessionId"]},
                    {"$set": {"status": body["status"]}}
                )
                
                if result.matched_count == 0:
                    raise HTTPException(status_code=404, detail="Session not found")
                
                return JSONResponse(
                    content={
                        "message": "Session status updated successfully",
                        "sessionId": body["sessionId"],
                        "status": body["status"]
                    },
                    status_code=200
                )
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
     
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

    httpServerPort = 15000
    httpServerHost = "127.0.0.1"
    httpServerPrivilegedIpAddress = ["127.0.0.1"]
    
    http_server = HTTP_SERVER(httpServerHost=httpServerHost, httpServerPort=httpServerPort, httpServerPrivilegedIpAddress=httpServerPrivilegedIpAddress, data_class_instance=dataClass)


    service = Service(http_server)
    await service.startService()

if __name__ == "__main__":
    asyncio.run(start_service())