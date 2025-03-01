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

sys.path.append(os.path.join(os.path.dirname(__file__), "../ServiceTemplates/Basic"))

from HTTP_SERVER import HTTPServer
from customerAgent import customerAgent

class CustomerServerService():
    def __init__(self,httpServerHost, httpServerPort):
        self.httpServer = HTTPServer(httpServerHost, httpServerPort)

        self.sessionCreationRequests = {}
        self.sessionStatus = {}
        self.customerAgentList = {}

        self.CateringRequestLock = threading.Lock()


    async def getServiceURL(self, serviceName):
        servicePortMapping = json.load(open("ServiceURLMapping.json"))
        return servicePortMapping[serviceName]

    async def ConfigureHttpRoutes(self):

        async def handleSessionCreationRequest(data):
            email = data["EMAIL"]
            mainData = data["DATA"]
            if email not in self.sessionStatus.keys():
                self.sessionCreationRequests[email] = mainData
                self.sessionStatus[email] = "PENDING"
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

            messageToSend = {"EMAIL": email , "PASSWORD": password, "TYPE": personaType}
            messageInJson = json.dumps(messageToSend)

            credentialServerServiceURL = await self.getServiceURL("CREDENTIAL_SERVER")
            response = requests.get(f"http://{credentialServerServiceURL}/check_node?message={messageInJson}")

            if response.status_code == 200:
                responseData = response.json()
                if(responseData["MESSAGE"] == "REGISTERED"):
                    return await handleSessionCreationRequest(data)
                else:
                    return JSONResponse(content={"MESSAGE": "INVALID_EMAIL_OR_PASSWORD"} , status_code=401)
            else:
                return JSONResponse(content={"MESSAGE": "SESSION_CREATION_FAILED"} , status_code=500)

            

        async def initializeCustomerSession(customerEmail):
            print(f"Session Inititalizing for the Customer : {customerEmail}")
            newCustomerAgent = customerAgent()
            self.customerAgentList[customerEmail] = newCustomerAgent
            messageToSend = {"META_DATA" : {"EMAIL" : customerEmail} , "SESSION_DATA": self.sessionCreationRequests[customerEmail]}

            await newCustomerAgent.InitializeSession(messageToSend)
            return True
            
        @self.httpServer.app.post("/initializeSession")
        async def initializeSessionCallback(request: Request):
            print("Initialize Session Called")
            data = await request.json()
            email = data["EMAIL"]
            if email in self.sessionCreationRequests.keys():
                if await initializeCustomerSession(email):
                    print(f"Session Initialized for the Customer : {email}")
                    print(len(self.customerAgentList))

                    del self.sessionCreationRequests[email]
                    self.sessionStatus[email] = "RUNNING"
                    print(f"Session Status for the Customer {email} : {self.sessionStatus[email]}")

                    return JSONResponse(content={"MESSAGE": "SESSION_INITIALIZED"} , status_code=200)
                else:
                    print(f"Session Creation Failed for Customer : {email}")
                    return JSONResponse(content={"MESSAGE": "SESSION_CREATION_FAILED"} , status_code=500)
            else:
                print(f"No Session Pending for the Customer : {email}")
                return JSONResponse(content={"MESSAGE": "NO_SESSION_PENDING"} , status_code=404)



        @self.httpServer.app.put("/handleSessionRequests")
        async def handleSessionRequestsCallback(request: Request):
            pass
            


        @self.httpServer.app.get("/serverRunning")
        async def serverRunningCallback(request: Request):
            print("Server Running Check Called ")
            responseToSend = {"MESSAGE": "SERVER_RUNNING"}
            return JSONResponse(content=responseToSend , status_code=200)



        @self.httpServer.app.get("/sessionSTATUS")
        async def sessionStatusCallback(request: Request):
            print("Session Status Check Called ")
            message = request.query_params.get("message")
            data = json.loads(message)

            personalType = data["PERSONA_TYPE"]
            email = data["EMAIL"]
            if personalType == "CUSTOMERS":
                if email in self.sessionStatus.keys():
                    responseToSend = {"MESSAGE": self.sessionStatus[email]}
                    return JSONResponse(content=responseToSend , status_code=200)
                else:
                    responseToSend = {"MESSAGE": "IDLE"}
                    return JSONResponse(content=responseToSend , status_code=200)
            else:
                responseToSend = {"MESSAGE": "INVALID_REQUEST"}
                return JSONResponse(content=responseToSend , status_code=400)
          
            

    async def startService(self):

        await self.ConfigureHttpRoutes()
        await self.httpServer.run_app()



async def start_service():
    service = CustomerServerService("0.0.0.0" , 5500)
    await service.startService()

if __name__ == "__main__":
    print("Starting Customer Server Service")
    asyncio.run(start_service())