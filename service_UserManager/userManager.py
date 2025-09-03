import asyncio

import sys
import os
import threading

import json
import pickle

from fastapi import Request,  Response
from fastapi.responses import JSONResponse

# Embedded HTTPServer class
class HTTPServer:
    def __init__(self, host="127.0.0.1", port=54545):
        self.app = FastAPI()
        self.host = host
        self.port = port

    async def run_app(self):
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()

# Embedded MessageQueue class
class MessageQueue:
    def __init__(self, ConnectionURL="amqp://guest:guest@localhost/", ExchangeName="/"):
        self.ExchangeName = ExchangeName
        self.ConnectionURL = ConnectionURL
        self.Connection = None
        self.Channel = None
        self.QueueList = []
        self.QueueToCallbackMapping = {}  
        self.DeclaredExchanges = {}

    async def InitializeConnection(self):
        self.Connection = await aio_pika.connect_robust(self.ConnectionURL)
        self.Channel = await self.Connection.channel()
        await self.Channel.declare_exchange(self.ExchangeName, aio_pika.ExchangeType.DIRECT)

    async def BoundQueueToExchange(self):
        for queues in self.QueueList:
            await queues.bind(self.ExchangeName , routing_key=queues.name)
        
    async def AddNewQueue(self, QueueName,**queueParams):
        queue = await self.Channel.declare_queue(QueueName, **queueParams)
        self.QueueList.append(queue)
    
    async def MapQueueToCallback(self, QueueName, Callback):
        self.QueueToCallbackMapping[QueueName] = Callback

    async def AddQueueAndMapToCallback(self, QueueName, Callback,**queueParams):
        await self.AddNewQueue(QueueName,**queueParams)
        await self.MapQueueToCallback(QueueName, Callback)

    async def StartListeningToQueue(self):
        for queue in self.QueueList:
            await queue.consume(self.QueueToCallbackMapping[queue.name])

    async def PublishMessage(self, exchangeName , routingKey, message, headers=None):
        exchange = None
        if exchangeName not in self.DeclaredExchanges.keys():
            exchange = await self.Channel.declare_exchange(exchangeName)
            self.DeclaredExchanges[exchangeName] = exchange
        else:
            exchange = self.DeclaredExchanges[exchangeName]
        
        messageToSend = None
        if headers and "DATA_FORMAT" in headers:
            if headers["DATA_FORMAT"] == "BYTES":
                messageToSend = message
            else:
                messageToSend = message.encode()
        else:
            messageToSend = message.encode()
    
        try:
            await exchange.publish(
                aio_pika.Message(body=messageToSend, headers=headers),
                routing_key=routingKey
            )
        except Exception as e:
            print(f"Failed to publish message: {e}")

        return True

    async def CloseConnection(self):
        await self.Connection.close()

class UserManagerData:
    def __init__(self):
        self.connection_url = "amqp://guest:guest@localhost/"
        self.exchange_name = "USER_MANAGER_EXCHANGE"
        self.http_host = "127.0.0.1"
        self.http_port = 20000
        
        # User management specific configurations
        self.max_users_per_session = 10
        self.user_session_timeout = 3600  # 1 hour
        self.supervisor_routing_prefix = "SSE_"

class UserManagerService:
    def __init__(self, data_class=None):
        self.data = data_class or UserManagerData()
        self.messageQueue = MessageQueue(self.data.connection_url, self.data.exchange_name)
        self.apiServer = HTTPServer(self.data.http_host, self.data.http_port)

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
                responseMsg = JSONResponse(content=json.dumps(responseToSend), media_type="application/json")
            else:
                responseToSend = {"LIST_USER_ID" : self.users[:userCount], "NOTICE" : "SUFFICIENT"}
                for users in self.users[:userCount]:
                    self.userToSupervisorIdMapping[users] = supervisorID
                self.users = self.users[userCount:]
                responseMsg = JSONResponse(content=json.dumps(responseToSend), media_type="application/json")
        elif msgType == "GET_USERS":
            responseToSend = {"LIST_USER_ID" : self.users, "NOTICE" : "SUFFICIENT"}
            responseMsg = JSONResponse(content=json.dumps(responseToSend), media_type="application/json")
        else:
            print("Unknown Message Type")
            print("Received Message: ", supervisorMessage)
            responseMsg = {"STATUS" : "FAILED" , "ERROR" : "Unknown message type"}

        if response:
            return responseMsg

    async def handleUserServerMessages(self, userServerMessage, headers=None):
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

    async def callbackCustomerServerMessages(self, message):
        DecodedMessage = message.body.decode()
        DecodedMessage = json.loads(DecodedMessage)

        asyncio.create_task(self.handleCustomerServerMessages(DecodedMessage))

    async def handleCustomerServerMessages(self, customerServerMessage):
        msgType = customerServerMessage['TYPE']
        msgData = customerServerMessage['DATA']
        responseMsg = None
        if msgType == "NEW_SESSION":
            userCount = msgData["USER_COUNT"]
            if userCount == "ALL":
                if len(self.users) == 0:
                    responseToSend = {"LIST_USER_ID" : [], "NOTICE" : "NOT_SUFFICIENT"}
                    responseMsg = {"STATUS" : "SUCCESS" , "DATA" : responseToSend}
                else:
                    responseToSend = {"LIST_USER_ID" : self.users, "NOTICE" : "SUFFICIENT"}
                    for users in self.users[:]:
                        self.userToSupervisorIdMapping[users] = msgData["SESSION_SUPERVISOR_ID"]
                    self.users = []
                    responseMsg = {"STATUS" : "SUCCESS" , "DATA" : responseToSend}
            elif len(self.users) < userCount:
                responseToSend = {"LIST_USER_ID" : self.users, "NOTICE" : "NOT_SUFFICIENT"}
                responseMsg = {"STATUS" : "SUCCESS" , "DATA" : responseToSend}
            else:
                responseToSend = {"LIST_USER_ID" : self.users[:userCount], "NOTICE" : "SUFFICIENT"}
                for users in self.users[:userCount]:
                    self.userToSupervisorIdMapping[users] = msgData["SESSION_SUPERVISOR_ID"]
                self.users = self.users[userCount:]
                responseMsg = {"STATUS" : "SUCCESS" , "DATA" : responseToSend}
        elif msgType == "GET_USERS":
            responseToSend = {"LIST_USER_ID" : self.users, "NOTICE" : "SUFFICIENT"}
            responseMsg = {"STATUS" : "SUCCESS" , "DATA" : responseToSend}
        else:
            print("Unknown Message Type")
            print("Received Message: ", customerServerMessage)
            responseMsg = {"STATUS" : "FAILED" , "ERROR" : "Unknown message type"}

        if response:
            return responseMsg

    async def callbackSupervisorMessages(self, message):
        DecodedMessage = message.body.decode()
        DecodedMessage = json.loads(DecodedMessage)

        asyncio.create_task(self.handleSupervisorMessages(DecodedMessage, message.headers))

    
    async def startService(self):
        await self.messageQueue.InitializeConnection()
        await self.messageQueue.AddQueueAndMapToCallback("UME_USER_SERVER", self.callbackUserServerMessages, auto_delete = True)
        await self.messageQueue.AddQueueAndMapToCallback("UME_CUSTOMER_SERVER", self.callbackCustomerServerMessages, auto_delete = True)
        await self.messageQueue.AddQueueAndMapToCallback("UME_SESSION_SUPERVISOR", self.callbackSupervisorMessages, auto_delete = True)
        await self.messageQueue.BoundQueueToExchange()
        await self.messageQueue.StartListeningToQueue()

        await self.ConfigureApiRoutes()
        await self.apiServer.run_app()

class Service:
    def __init__(self, userManagerService=None):
        self.userManagerService = userManagerService

    async def startService(self):
        print("Starting User Manager Service...")
        await self.userManagerService.startService()

async def start_service():
    dataClass = UserManagerData()
    userManagerService = UserManagerService(dataClass)
    service = Service(userManagerService)
    await service.startService()


if __name__ == "__main__":
    print("Starting User Manager Service")
    asyncio.run(start_service())

