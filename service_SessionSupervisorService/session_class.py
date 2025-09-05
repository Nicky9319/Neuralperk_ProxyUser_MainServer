import uuid

import json 
import subprocess
import os
import socket
import sys

import pickle

import httpx

from typing import Literal

import aio_pika
from fastapi.responses import JSONResponse

from session_supervisor_class import sessionSupervisorClass



# =========================
# Session Class Definition
# =========================

class sessionClass:
    # -------------------------
    # Initialization Section
    # -------------------------
    def __init__(self, customer_id = None, object_id = None):
        self.session_status : Literal["queued", "rendering", "completed", "failed" , None] = None
        self.customer_id = customer_id
        self.object_id = object_id

        self.session_id = str(uuid.uuid4())
        self.sessionRoutingKey = f"SESSION_SUPERVISOR_{self.session_id}"

        self.session_supervisor_instance = sessionSupervisorClass(customer_id=self.customer_id, object_id=self.object_id, session_id=self.session_id)


        self.http_client = httpx.AsyncClient(timeout=30.0)

        self.user_manager_service_url = os.getenv("USER_MANAGER_SERVICE", "").strip()
        if not self.user_manager_service_url or not (self.user_manager_service_url.startswith("http://") or self.user_manager_service_url.startswith("https://")):
            self.user_manager_service_url = "http://127.0.0.1:7000"
        else:
            self.user_manager_service_url = self.user_manager_service_url

    # -------------------------
    # Workload Management Section
    # -------------------------
    async def start_workload(self):
        if self.customer_id is None or self.object_id is None:
            return JSONResponse(content={"message": "Customer ID or Object ID is missing"}, status_code=400)
        
        self.session_status = "running"

  
        # Register this session supervisor with the user manager
        user_manager_new_session_url = f"{self.user_manager_service_url}/api/user-manager/session-supervisor/new-session"
        # For now, request 1 user (can be parameterized)
        user_count = 1
        response = await self.http_client.post(
            user_manager_new_session_url,
            data={
                "user_count": user_count,
                "session_supervisor_id": self.session_id
            }
        )

        print("Response from user manager after registering session supervisor:")
        print(response.content)

        await self.session_supervisor_instance.initialization()
        await self.session_supervisor_instance.start_workload()

        return JSONResponse(content={"message": "Workload started"}, status_code=200)


    async def stop_and_delete_workload(self, customer_id):
        return JSONResponse(content={"message": "Workload stopped and deleted"}, status_code=200)

    # -------------------------
    # Session Status Section
    # -------------------------
    async def get_session_status(self):
        # Returns the current session status
        return self.session_status

    async def set_session_status(self, session_status):
        # Sets the session status
        self.session_status = session_status

    # -------------------------
    # Customer ID Section
    # -------------------------
    async def get_customer_id(self):
        # Returns the customer ID associated with the session
        return self.customer_id

    async def set_customer_id(self, customer_id):
        # Sets the customer ID for the session
        self.customer_id = customer_id

    # -------------------------
    # Object ID Section
    # -------------------------
    async def get_object_id(self):
        # Returns the object ID associated with the session
        return self.object_id

    async def set_object_id(self, object_id):
        # Sets the object ID for the session
        self.object_id = object_id