import asyncio

import sys
import os
import threading

import json
import pickle

from fastapi import Request,  Response
from fastapi.responses import JSONResponse

sys.path.append(os.path.join(os.path.dirname(__file__), "../ServiceTemplates/Basic"))

from HTTP_SERVER import HTTPServer
from MESSAGE_QUEUE import MessageQueue


class UserManagerService:
    def __init__(self, httpServerHost, httpServerPort):
        self.messageQueue = MessageQueue("amqp://guest:guest@localhost/" , "USER_MANAGER_EXCHANGE")
        self.apiServer = HTTPServer(httpServerHost, httpServerPort)

        self.users = []
        self.userToSupervisorIdMapping = {} # Email Address of Customer Linked to the User associated with it
        self.supervisorToRoutingKeyMapping = {} # Supervisor Name to Routing Key Mapping
        
        

    async def ConfigureApiRoutes(self):
        @self.apiServer.app.get('/SessionSupervisor')
        async def handleGetSessionSupervisor():
            pass
        
        @self.apiServer.app.post('/SessionSupervisor/NewSession')
        async def handlePostSessionSupervisor(request : Request):
            data = await request.json()
            print(type(data))
            print(data)
            headers = request.headers

            response = await self.handleSupervisorMessages(data, headers, response=True)
            print("Supervisor API Call fullfileed, Returning Results")
            responseInJson = json.dumps(response)
            return Response(content=responseInJson, media_type="application/json")


        @self.apiServer.app.get('/CustomerServer')
        async def handleGetCustomerServer():
            pass

        @self.apiServer.app.post('/CustomerServer')
        async def handlePostCustomerServer():
            pass

        @self.apiServer.app.get('/UserServer')
        async def handleGetUserServer():
            pass

        @self.apiServer.app.post('/UserServer')
        async def handlePostUserServer():
            pass

    async def sendMessageToSessionSupervisor(self, exchangeName, supervisorRoutingKey, messageToSend, headers=None):
        if headers and "DATA_FORMAT" in headers:
            if headers["DATA_FORMAT"] == "BYTES":
                messageInBytes = pickle.dumps(messageToSend)
                await self.messageQueue.PublishMessage(exchangeName, supervisorRoutingKey, messageInBytes, headers)
                return
            else:
                messageInJson = json.dumps(messageToSend)
                await self.messageQueue.PublishMessage(exchangeName, supervisorRoutingKey, messageInJson, headers)
                return
        else:
            messageInJson = json.dumps(messageToSend)
            await self.messageQueue.PublishMessage(exchangeName, supervisorRoutingKey, messageInJson)


    async def handleSupervisorMessages(self, supervisorMessage, Headers, response=False):
        msgType = supervisorMessage['TYPE']
        msgData = supervisorMessage['DATA']

        supervisorID = Headers["SESSION_SUPERVISOR_ID"]


        responseMsg = None
        if msgType == "NEW_SESSION":
            userCount = msgData["USER_COUNT"]
            if userCount == "ALL":
                if len(self.users) == 0:
                    responseToSend = {"LIST_USER_ID" : [], "NOTICE" : "NOT_SUFFICIENT"}
                    responseMsg = JSONResponse(content=json.dumps(responseToSend), media_type="application/json")
                else:
                    responseToSend = {"LIST_USER_ID" : self.users, "NOTICE" : "SUFFICIENT"}
                    for users in self.users[:]:
                        self.userToSupervisorIdMapping[users] = supervisorID
                    self.users = []
                    responseMsg = JSONResponse(content=json.dumps(responseToSend), media_type="application/json")
            elif len(self.users) < userCount:
                responseToSend = {"LIST_USER_ID" : self.users, "NOTICE" : "NOT_SUFFICIENT"}
                for users in self.users[:]:
                    self.userToSupervisorIdMapping[users] = supervisorID
                self.users = []
                responseMsg = JSONResponse(content=json.dumps(responseToSend), media_type="application/json")
            else:
                responseToSend = {"LIST_USER_ID" : self.users[:userCount], "NOTICE" : "SUFFICIENT"}
                for users in self.users[:userCount]:
                    self.userToSupervisorIdMapping[users] = supervisorID
                self.users = self.users[userCount:]
                responseMsg = JSONResponse(content=json.dumps(responseToSend), media_type="application/json")
        
            if response:
                return responseToSend
        elif msgType == "ADDITIONAL_USERS":
            userCount = msgData["USER_COUNT"]
            if userCount == "ALL":
                if len(self.users) == 0:
                    responseToSend = {"LIST_USER_ID" : [], "NOTICE" : "NOT_SUFFICIENT"}
                    responseMsg = JSONResponse(content=json.dumps(responseToSend), media_type="application/json")
                else:
                    responseToSend = {"LIST_USER_ID" : self.users, "NOTICE" : "SUFFICIENT"}
                    for users in self.users[:]:
                        self.userToSupervisorIdMapping[users] = supervisorID
                    self.users = []
                    responseMsg = JSONResponse(content=json.dumps(responseToSend), media_type="application/json")
            elif len(self.users) < userCount:
                responseToSend = {"LIST_USER_ID" : self.users, "NOTICE" : "NOT_SUFFICIENT"}
                for users in self.users[:]:
                    self.userToSupervisorIdMapping[users] = supervisorID
                self.users = []
                responseMsg = JSONResponse(content=json.dumps(responseToSend), media_type="application/json")
            else:
                responseToSend = {"LIST_USER_ID" : self.users[:userCount], "NOTICE" : "SUFFICIENT"}
                for users in self.users[:userCount]:
                    self.userToSupervisorIdMapping[users] = supervisorID
                self.users = self.users[userCount:]
                responseMsg = JSONResponse(content=json.dumps(responseToSend), media_type="application/json")
        
            if response:
                return responseToSend
        elif msgType == "SEND_MESSAGE_TO_USER":
            exchangeName = "COMMUNICATION_INTERFACE_EXCHANGE"
            routingKey = "CIE_USER_MANAGER"

            mainMessage = msgData
            messageToSend = {"TYPE": "SEND_MESSAGE_TO_USER" , "DATA": mainMessage}
            messageInJson = json.dumps(messageToSend)



            await self.messageQueue.PublishMessage(exchangeName, routingKey, messageInJson)

            responseMsg = {"STATUS" : "SUCCESS"}
        elif msgType == "USER_RELEASED":
            userIds = msgData["LIST_USER_ID"]
            self.users.extend(userIds)
            for users in userIds:
                self.userToSupervisorIdMapping.pop(users)
            
            responseMsg = {"STATUS" : "SUCCESS"}
        elif msgType == "INITIALIZE_SESSION":
            print("Handling Initialization of Session, Request Send from Session Supervisor")
            self.userToSupervisorIdMapping[supervisorID] = []
            self.supervisorToRoutingKeyMapping[supervisorID] = f"SSE_{supervisorID}_UM"
            responseMsg = {"STATUS": "SUCCESS"}
        else:
            print("Unknown Message Type")
            print("Received Message: ", supervisorMessage)
            responseMsg = {"STATUS" : "FAILED" , "ERROR" : "Unknown message type"}

        if response:
            return responseMsg

    async def callbackSupervisorMessages(self, message):
        print("Supervisor Send a Message")

        DecodedMessage = message.body.decode()
        DecodedMessage = json.loads(DecodedMessage)

        Headers = message.headers

        print("UM : Waiting For Lock to Be Released")

        await self.handleSupervisorMessages(DecodedMessage,Headers)

        print("Supervisor Request Handled")
        

    async def handleCustomerServerMessages(self, customerServerMessage, response=False):
        msgType = customerServerMessage['TYPE']
        print(customerServerMessage)

    async def callbackCustomerServerMessages(self , message):
        DecodedMessage = message.body.decode()
        DecodedMessage = json.loads(DecodedMessage)

        await self.handleCustomerServerMessages(DecodedMessage)


    async def handleUserServerMessages(self, userServerMessage, response=False, headers=None):
        msgType = userServerMessage['TYPE']
        msgData = userServerMessage['DATA']
        responseMsg = None
        if msgType == "USER_MESSAGE":
            # userId = msgData["USER_ID"]
            # userMessage = msgData["MESSAGE"]
            # mainMessage = {"USER_ID" : userId , "MESSAGE" : userMessage}

            userId = msgData["USER_ID"]

            supervisorID = self.userToSupervisorIdMapping[userId]
            supervisorRoutingKey = self.supervisorToRoutingKeyMapping[supervisorID]

            exchangeName = "SESSION_SUPERVISOR_EXCHANGE"


            mainMessage = msgData
            messageToSend = {"TYPE" : "USER_MESSAGE" , "DATA" : mainMessage}

            await self.sendMessageToSessionSupervisor(exchangeName, supervisorRoutingKey, messageToSend, headers=headers)
            # await self.messageQueue.PublishMessage(exchangeName, supervisorRoutingKey, messageToSend, headers=headers)
        elif msgType == "NEW_USER":
            self.users.append(msgData["USER_ID"])
            print("New User Added")
            print("Users: ", self.users)
        elif msgType == "REMOVE_USER":
            userId = msgData["USER_ID"]
            if userId in self.users:
                self.users.remove(userId)
            else:
                supervisorID = self.userToSupervisorIdMapping[userId]
                supervisorRoutingKey = self.supervisorToRoutingKeyMapping[supervisorID]

                exchangeName = "SESSION_SUPERVISOR_EXCHANGE"

                mainMessage = {"TYPE" : "USER_DISCONNECT" , "DATA" : msgData}
                messageToSend = {"TYPE" : "USER_MANAGER_MESSAGE" , "DATA" : mainMessage}

                print(msgData.keys())

                await self.sendMessageToSessionSupervisor(exchangeName, supervisorRoutingKey, messageToSend, headers=headers)
                # await self.messageQueue.PublishMessage(exchangeName, supervisorRoutingKey, messageToSend, headers=headers)
            
            print("User Removed")
            print("Users: ", self.users)
        else:
            print("Unknown Message Type")
            print("Received Message: ", userServerMessage)
            responseMsg = {"STATUS" : "FAILED" , "ERROR" : "Unknown message type"}

        if response:
            return responseMsg

    async def callbackUserServerMessages(self, message):

        # DecodedMessage = message.body.decode()
        # DecodedMessage = json.loads(DecodedMessage)

        DecodedMessage = None

        headers = message.headers   
        print(f"User Server Headers Received : {message.headers}")

        if headers and "DATA_FORMAT" in headers:
            if headers["DATA_FORMAT"] == "BYTES":
                print("Bytes")
                DecodedMessage = pickle.loads(message.body)
            else:
                DecodedMessage = message.body.decode()
                DecodedMessage = json.loads(DecodedMessage)
        else:
            DecodedMessage = message.body.decode()
            DecodedMessage = json.loads(DecodedMessage)


        asyncio.create_task(self.handleUserServerMessages(DecodedMessage, headers=headers))
        # await self.handleUserServerMessages(DecodedMessage)



    
    async def startService(self):
        await self.messageQueue.InitializeConnection()
        await self.messageQueue.AddQueueAndMapToCallback("UME_USER_SERVER", self.callbackUserServerMessages, auto_delete = True)
        await self.messageQueue.AddQueueAndMapToCallback("UME_CUSTOMER_SERVER", self.callbackCustomerServerMessages, auto_delete = True)
        await self.messageQueue.AddQueueAndMapToCallback("UME_SESSION_SUPERVISOR", self.callbackSupervisorMessages, auto_delete = True)
        await self.messageQueue.BoundQueueToExchange()
        await self.messageQueue.StartListeningToQueue()

        await self.ConfigureApiRoutes()
        await self.apiServer.run_app()



async def start_service():
    service = UserManagerService('127.0.0.1', 20000)
    await service.startService()


if __name__ == "__main__":
    print("Starting User Manager Service")
    asyncio.run(start_service())

