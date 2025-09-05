import asyncio

from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

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
        
        # HTTP client for making requests to MongoDB service
        self.http_client = httpx.AsyncClient(timeout=30.0)

    def hash_password(self, password: str) -> str:
        """Hash a password using SHA-256 with salt"""
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{hashed}"
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        try:
            salt, hash_value = hashed_password.split(":")
            computed_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return computed_hash == hash_value
        except:
            return False

    async def configure_routes(self):

        @self.app.get("/api/auth-service/")
        async def root():
            """Root endpoint to check if Auth Service is active"""
            return JSONResponse(content={"message": "Auth Service is Active"}, status_code=200)

        @self.app.post("/api/auth-service/register")
        async def register(request: Request):
            """Register a new user
            Required fields: email, password
            Returns: Success message with user details including auto-generated customerId
            """
            try:
                body = await request.json()
                
                # Validate required fields
                required_fields = ["email", "password"]
                for field in required_fields:
                    if field not in body:
                        raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
                
                # Validate username format (basic validation)
                email = body["email"]
                if len(email) < 3:
                    raise HTTPException(status_code=400, detail="Username must be at least 3 characters long")
                
                # Validate password strength (basic validation)
                password = body["password"]
                if len(password) < 6:
                    raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
                
                # Hash the password
                hashed_password = self.hash_password(password)
                
                # Prepare user data for MongoDB service (using username as email)
                user_data = {
                    "email": email,  # Using username as email for MongoDB service
                    "password": hashed_password
                }
                
                # Call MongoDB service to add user
                try:
                    response = await self.http_client.post(
                        f"{self.mongodb_service_url}/api/mongodb-service/customers/add",
                        json=user_data
                    )
                    
                    if response.status_code == 201:
                        # Registration successful - get the generated customer ID from response
                        response_data = response.json()
                        generated_customer_id = response_data.get("customerId")
                        
                        return JSONResponse(
                            content={
                                "message": "User registered successfully",
                                "customerId": generated_customer_id
                            },
                            status_code=201
                        )
                    elif response.status_code == 409:
                        raise HTTPException(status_code=409, detail="User with this username already exists")
                    else:
                        # Forward the error from MongoDB service
                        error_detail = response.json().get("detail", "Registration failed")
                        raise HTTPException(status_code=response.status_code, detail=error_detail)
                        
                except httpx.RequestError as e:
                    raise HTTPException(status_code=503, detail=f"MongoDB service unavailable: {str(e)}")
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

        @self.app.post("/api/auth-service/authenticate_customer_id")
        async def authenticate_customer_id(request: Request):
            """Authenticate a customer ID
            Required fields: customerId
            Returns: Boolean indicating if customer ID exists
            """
            try:
                body = await request.json()
                
                # Validate required fields
                required_fields = ["customerId"]
                for field in required_fields:
                    if field not in body:
                        raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
                
                customer_id = body["customerId"]
                
                # Check if customer exists using MongoDB service
                try:
                    response = await self.http_client.get(
                        f"{self.mongodb_service_url}/api/mongodb-service/customers/check/{customer_id}"
                    )
                    
                    if response.status_code == 200:
                        user_data = response.json()
                        if user_data.get("exists"):
                            # Customer ID is valid
                            return JSONResponse(
                                content={
                                    "authenticated": True,
                                    "message": "Customer ID is valid"
                                },
                                status_code=200
                            )
                        else:
                            # Customer ID is invalid
                            return JSONResponse(
                                content={
                                    "authenticated": False,
                                    "message": "Customer ID is invalid"
                                },
                                status_code=200
                            )
                    else:
                        # Customer ID is invalid
                        return JSONResponse(
                            content={
                                "authenticated": False,
                                "message": "Customer ID is invalid"
                            },
                            status_code=200
                        )
                        
                except httpx.RequestError as e:
                    raise HTTPException(status_code=503, detail=f"MongoDB service unavailable: {str(e)}")
                
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

        @self.app.post("/api/auth-service/login")
        async def login(request: Request):
            """Login user with username and password
            Required fields: username, password
            Returns: Access token and refresh token
            """
            try:
                body = await request.json()
                
                # Validate required fields
                required_fields = ["username", "password"]
                for field in required_fields:
                    if field not in body:
                        raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
                
                username = body["username"]
                password = body["password"]
                
                # Find user by username (stored as email in MongoDB) using MongoDB service
                try:
                    response = await self.http_client.get(
                        f"{self.mongodb_service_url}/api/mongodb-service/customers/find-by-email/{username}"
                    )
                    
                    if response.status_code == 200:
                        user_data = response.json()
                        if user_data.get("exists"):
                            # User found, now verify password
                            stored_password = user_data.get("password")
                            customer_id = user_data.get("customerId")
                            
                            # Verify the password
                            if self.verify_password(password, stored_password):
                                # Password is correct, return access token and refresh token
                                return JSONResponse(
                                    content={
                                        "message": "Login successful",
                                        "accessToken": customer_id,
                                        "refreshToken": ""
                                    },
                                    status_code=200
                                )
                            else:
                                raise HTTPException(status_code=401, detail="Invalid username or password")
                        else:
                            raise HTTPException(status_code=401, detail="Invalid username or password")
                    else:
                        raise HTTPException(status_code=401, detail="Invalid username or password")
                        
                except httpx.RequestError as e:
                    raise HTTPException(status_code=503, detail=f"MongoDB service unavailable: {str(e)}")
                
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

    #<HTTP_SERVER_INSTANCE_INTIALIZATION_START>

    #<HTTP_SERVER_PORT_START>
    httpServerPort = 10000
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