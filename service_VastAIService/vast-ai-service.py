import asyncio
import subprocess
import time

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

# Get VastAI API key from environment variable
VASTAI_API_KEY = os.getenv("VASTAI_API_KEY", "")


class HTTP_SERVER():
    def __init__(self, httpServerHost, httpServerPort, httpServerPrivilegedIpAddress=["127.0.0.1"], data_class_instance=None):
        self.app = FastAPI()
        self.host = httpServerHost
        self.port = httpServerPort

        self.privilegedIpAddress = httpServerPrivilegedIpAddress        #<HTTP_SERVER_CORS_ADDITION_START>
        # self.app.add_middleware(CORSMiddleware, allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"],)
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

    async def configure_routes(self):

        @self.app.get("/api/vastai-service/")
        async def root():
            """Root endpoint to check if Auth Service is active"""
            return JSONResponse(content={"message": "Vast AI Service is Active"}, status_code=200)

        @self.app.get("/api/vastai-service/instance/list-of-instances")
        async def list_instances(request: Request):
            """
                This method returns the list of all instances currently active in the system
            """
            try:
                # Use the VastAIHelper instance from data_class
                instances = self.data_class.vastai_helper.list_instances()
                
                # Format the response with essential information
                formatted_instances = []
                for instance in instances:
                    formatted_instances.append({
                        "instance_id": instance.get("id"),
                        "status": instance.get("actual_status"),
                        "gpu_name": instance.get("gpu_name"),
                        "created_at": instance.get("created_timestamp"),
                        "machine_id": instance.get("machine_id")
                    })
                
                return JSONResponse(content={
                    "success": True,
                    "instances": formatted_instances
                }, status_code=200)
            except Exception as e:
                return JSONResponse(content={
                    "success": False, 
                    "error": f"Failed to retrieve instances: {str(e)}"
                }, status_code=500)
            
        @self.app.get("/api/vastai-service/instance/information/{instance_id}")
        async def get_instance_info(request: Request, instance_id: str):
            """
                This method returns the following information about the instance
                1. Instance ID
                2. Instance Up Time
                3. Instance Status
                4. Instance Cost till now
                5. Instance Logs
            """
            try:
                # Use the VastAIHelper instance from data_class
                instance_info = self.data_class.vastai_helper.get_instance_info(instance_id)
                
                if not instance_info:
                    return JSONResponse(content={
                        "success": False,
                        "error": f"Instance {instance_id} not found or error retrieving information"
                    }, status_code=404)
                
                return JSONResponse(content={
                    "success": True,
                    "instance": {
                        "instance_id": instance_info["instance_id"],
                        "uptime_hours": instance_info["uptime_hours"],
                        "status": instance_info["status"],
                        "total_cost": instance_info["total_cost"],
                        "hourly_rate": instance_info["dph_total"],
                        "gpu_info": f"{instance_info['gpu_name']} ({instance_info['gpu_ram']}GB)",
                        "machine_id": instance_info["machine_id"],
                        "logs": instance_info["logs"]
                    }
                }, status_code=200)
            except Exception as e:
                return JSONResponse(content={
                    "success": False,
                    "error": f"Failed to retrieve instance information: {str(e)}"
                }, status_code=500)
    async def run_app(self):
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()


class VastAIHelper:
    def __init__(self, api_key=None):
        self.api_key = api_key
    
    def run_command(self, command: str, check: bool = True, silent: bool = False):
        """Run a command and return the result"""
        try:
            # Add API key to command if available
            if self.api_key and "--api-key" not in command:
                command = f"{command} --api-key {self.api_key}"
                
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if check and result.returncode != 0:
                if not silent:
                    print(f"Command failed: {result.stderr}")
                raise subprocess.CalledProcessError(result.returncode, command, result.stderr)
            return result
        except Exception as e:
            if not silent:
                print(f"Error running command: {e}")
            if check:
                raise
            return None
    
    def list_instances(self):
        """Get list of all running instances"""
        cmd = f"vastai show instances --raw"
        
        try:
            result = self.run_command(cmd)
            instances = json.loads(result.stdout)
            return instances
        except Exception as e:
            print(f"Error listing instances: {e}")
            return []

    def get_instance_info(self, instance_id: str):
        """Get detailed information about a specific instance"""
        try:
            # Get instance details including cost and runtime stats
            result = self.run_command(f"vastai show instance {instance_id} --raw", check=False)
            if result.returncode != 0:
                return None
            
            stats = json.loads(result.stdout)
            
            # Calculate relevant metrics
            start_date = stats.get('start_date')
            current_time = time.time()
            
            # Calculate uptime if start_date is available
            uptime_hours = 0
            if start_date:
                uptime_seconds = current_time - start_date
                uptime_hours = uptime_seconds / 3600
            
            # Calculate total cost from hourly rate and uptime
            dph_total = stats.get('dph_total', 0)
            total_cost = float(dph_total) * uptime_hours if dph_total and uptime_hours else 0
            
            # Get logs
            logs_result = self.run_command(f"vastai logs {instance_id} --tail 20", check=False)
            logs = logs_result.stdout.strip() if logs_result and logs_result.returncode == 0 else "No logs available"
            
            return {
                "instance_id": instance_id,
                "uptime_hours": round(uptime_hours, 2) if uptime_hours else 0,
                "total_cost": round(total_cost, 4),
                "dph_total": dph_total,
                "status": stats.get('actual_status') or 'unknown',
                "gpu_name": stats.get('gpu_name') or 'Unknown',
                "gpu_ram": stats.get('gpu_ram') or 0,
                "machine_id": stats.get('machine_id', 'N/A'),
                "logs": logs
            }
        except Exception as e:
            print(f"Error getting instance info: {e}")
            return None

class Data():
    def __init__(self):
        self.value = None
        # Create VastAIHelper instance
        self.vastai_helper = VastAIHelper(api_key=VASTAI_API_KEY)

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


    httpServerPort = 6000

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