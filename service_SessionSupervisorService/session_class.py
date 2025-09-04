import uuid

import json 
import subprocess
import os
import socket
import sys

import pickle

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
        self.session_status = None
        self.customer_id = customer_id
        self.object_id = object_id

        self.session_id = str(uuid.uuid4())
        self.sessionRoutingKey = f"{self.session_id}"

    # -------------------------
    # Workload Management Section
    # -------------------------
    async def start_workload(self):
        if self.customer_id is None or self.object_id is None:
            return JSONResponse(content={"message": "Customer ID or Object ID is missing"}, status_code=400)
        
        self.session_status = "running"

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