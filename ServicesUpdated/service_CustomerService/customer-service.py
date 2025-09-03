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
        env_url = os.getenv("MONGO_DB_SERVICE", "").strip()
        if not env_url or not (env_url.startswith("http://") or env_url.startswith("https://")):
            self.mongodb_service_url = "http://127.0.0.1:5757"
        else:
            self.mongodb_service_url = env_url

    async def configure_routes(self):
        

        @self.httpServer.app.post("/requestSessionCreation")
        async def handleSessionCreationRequest(request: Request):
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



class Data():
    def __init__(self):
        self.sessionCreationRequests = {}
        self.sessionStatus = {}
        self.customerAgentList = {}

        self.CateringRequestLock = asyncio.Lock()

    def get_value(self):
        pass

    def set_value(self, value):
        pass


class Service():
    def __init__(self, httpServer = None):
        self.httpServer = httpServer

    async def startService(self):
        await self.httpServer.configure_routes()
        await self.httpServer.run_app()



async def start_service():
    dataClass = Data()

    httpServerPort = 12000
    httpServerHost = "0.0.0.0"

    httpServerPrivilegedIpAddress = ["127.0.0.1"]

    http_server = HTTP_SERVER(httpServerHost=httpServerHost, httpServerPort=httpServerPort, httpServerPrivilegedIpAddress=httpServerPrivilegedIpAddress, data_class_instance=dataClass)

    service = Service(http_server)
    await service.startService()

if __name__ == "__main__":
    asyncio.run(start_service())