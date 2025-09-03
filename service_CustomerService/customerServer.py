import asyncio

import sys
import os
import threading

import uuid

import json

from fastapi import Request,  Response
from fastapi.responses import JSONResponse

import requests
import pickle
import time


from customerAgent import customerAgent

class CustomerServerData:
    def __init__(self):
        self.http_host = "127.0.0.1"
        self.http_port = 5000
        
        # Customer server specific configurations
        self.service_url_mapping_file = "ServiceURLMapping.json"
        self.session_timeout = 3600  # 1 hour
        self.max_concurrent_sessions = 100
        self.credential_validation_enabled = True

class CustomerServerService():
    def __init__(self, data_class=None):
        self.data = data_class or CustomerServerData()
        self.httpServer = HTTPServer(self.data.http_host, self.data.http_port)

        self.sessionCreationRequests = {}
        self.sessionStatus = {}
        self.customerAgentList = {}

        self.CateringRequestLock = threading.Lock()

    async def getServiceURL(self, serviceName):
        servicePortMapping = json.load(open(self.data.service_url_mapping_file))
        return servicePortMapping[serviceName]

    async def ConfigureHttpRoutes(self):

        async def handleSessionCreationRequest(data):
            email = data["EMAIL"]
            mainData = data["DATA"]
            if email not in self.sessionStatus.keys():
                self.sessionCreationRequests[email] = mainData
                self.sessionStatus[email] = "PENDING"
                responseToSend = {"MESSAGE": "SESSION_CREATION_REQUEST_ACCEPTED"}
                return JSONResponse(content=responseToSend , status_code=200)
            else:
                responseToSend = {"MESSAGE": "SESSION_ALREADY_RUNNING"}
                return JSONResponse(content=responseToSend , status_code=400)

        @self.httpServer.app.post("/requestSessionCreation")
        async def createSession(request: Request):
            print("Session Creation Request Received")

            content_type = request.headers.get("content-type")
            data = None

            if(content_type == 'application/json'):
                data = await request.json()
            elif(content_type == 'application/bytes'):
                data= await request.body()
                data = pickle.loads(data)

            personaType = data["PERSONA_TYPE"]
            email = data["EMAIL"]
            password = data["PASSWORD"]

            if email != "paarthsaxena2005@gmail.com":
                return JSONResponse(content={"MESSAGE": "INVALID_EMAIL_OR_PASSWORD"} , status_code=401)

            messageToSend = {"EMAIL": email , "PASSWORD": password, "TYPE": personaType}
            messageInJson = json.dumps(messageToSend)

            # credentialServerServiceURL = await self.getServiceURL("CREDENTIAL_SERVER")
            # response = requests.get(f"http://{credentialServerServiceURL}/check_node?message={messageInJson}")

            response = 200

            # if response.status_code == 200:
            if response == 200:
                # responseData = response.json()
                responseData = {"MESSAGE": "REGISTERED"}
                if(responseData["MESSAGE"] == "REGISTERED"):
                    return await handleSessionCreationRequest(data)
                else:
                    return JSONResponse(content={"MESSAGE": "INVALID_EMAIL_OR_PASSWORD"} , status_code=401)
            else:
                return JSONResponse(content={"MESSAGE": "SESSION_CREATION_FAILED"} , status_code=500)

    async def initializeCustomerSession(self, customerEmail):
        print(f"Session Inititalizing for the Customer : {customerEmail}")
        newCustomerAgent = customerAgent()
        self.customerAgentList[customerEmail] = newCustomerAgent
        messageToSend = {"META_DATA" : {"EMAIL" : customerEmail} , "SESSION_DATA": self.sessionCreationRequests[customerEmail]}

        await newCustomerAgent.InitializeSession(messageToSend)

    async def startService(self):
        await self.ConfigureHttpRoutes()
        await self.httpServer.run_app()

class Service:
    def __init__(self, customerServerService=None):
        self.customerServerService = customerServerService

    async def startService(self):
        print("Starting Customer Server Service...")
        await self.customerServerService.startService()

async def start_service():
    dataClass = CustomerServerData()
    customerServerService = CustomerServerService(dataClass)
    service = Service(customerServerService)
    await service.startService()

if __name__ == "__main__":
    asyncio.run(start_service())