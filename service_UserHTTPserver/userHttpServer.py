import asyncio

import sys
import os
import threading

import socketio
import json
import pickle

import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse


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

class UserHTTPServerData:
    def __init__(self):
        self.connection_url = "amqp://guest:guest@localhost/"
        self.exchange_name = "USER_HTTP_SERVER_EXCHANGE"
        self.http_host = "127.0.0.1"
        self.http_port = 8080
        self.api_host = "127.0.0.1"
        self.api_port = 8081
        
        # User HTTP server specific configurations
        self.buffer_timeout = 300  # 5 minutes
        self.max_buffer_size = 1000
        self.supported_content_types = ["application/json", "application/octet-stream"]

class userHttpServerService:
    def __init__(self, data_class=None):
        self.data = data_class or UserHTTPServerData()
        self.messageQueue = MessageQueue(self.data.connection_url, self.data.exchange_name)
        self.apiServer = HTTPServer(self.data.api_host, self.data.api_port)
        self.httpServer = HTTPServer(self.data.http_host, self.data.http_port)

        self.bufferMsgs = {}

    async def handleUserMessage(self, userMessage, userID):
        msgType = userMessage['TYPE']
        msgData = userMessage['DATA']
        if msgType == "FRAME_RENDERED":
            userId = userID

            # mainMessage = {"MESSAGE" : msgData , "USER_ID" : userId}
            # mainMessage = userMessage
            mainMessage = {"TYPE" : msgType , "DATA" : msgData, "USER_ID" : userId}

            messageToSend = {"TYPE" : "USER_MESSAGE" , "DATA" : mainMessage}
            await self.sendMessageToUserManager(messageToSend, bytes=True)
            return JSONResponse(content={"DATA" : "RECEIVED" , "TIME" : time.time()}, status_code=200)
        elif msgType == "RENDER_COMPLETED":
            userId = userID
            mainMessage = {"MESSAGE" : msgData , "USER_ID" : userId}
            messageToSend = {"TYPE" : "USER_MESSAGE" , "DATA" : mainMessage}
            self.sendMessageToUserManager(messageToSend)
            return JSONResponse(content={"DATA" : "RECEIVED" , "TIME" : time.time()}, status_code=200)
        elif msgType == "TEST":  
            print("Test message Received : " , msgData["TEST"])
            return JSONResponse(content={"DATA" : "RECEIVED" , "TIME" : time.time()}, status_code=200)
        else:
            print("Received Normal Message !!!")
            return JSONResponse(content={"DATA" : "RECEIVED" , "TIME" : time.time()}, status_code=200)

    async def RefineDataFromMetaData(self, bufferMsgData):
        print(bufferMsgData)
        MetaDataType = bufferMsgData["META_DATA"]
        if MetaDataType == "EXTRACT_BLEND_FILE_FROM_PATH":
            def getBlendBinaryFromPath(blendPath):
                print(f"Blender File Path : {bufferMsgData['BINARY_BLEND_FILE']}") 
                
                fileBinary = None
                with open(bufferMsgData["BINARY_BLEND_FILE"] , 'rb') as file:
                    fileBinary =  file.read()
                
                return fileBinary
                
                
            bufferMsgData["BINARY_BLEND_FILE"] = getBlendBinaryFromPath(bufferMsgData["BINARY_BLEND_FILE"])
        else:
            pass

        return bufferMsgData

    async def ConfigureHTTPRoutes(self):
        @self.httpServer.app.get("/")
        async def getDataFromServer(bufferUUID: str):
            if bufferUUID in self.bufferMsgs.keys():
                bufferMsg = self.bufferMsgs[bufferUUID]

                bufferMsgData = bufferMsg["DATA"]

                if type(bufferMsg) == dict and "META_DATA" in bufferMsgData.keys():
                    bufferMsgData = await self.RefineDataFromMetaData(bufferMsgData)

                print("Sending Msg to User")

                del self.bufferMsgs[bufferUUID]
                return Response(content=pickle.dumps(bufferMsg), status_code=200, media_type="application/octet-stream")
            return Response(content=pickle.dumps({"message": "No Buffer Message"}), status_code=400, media_type="application/octet-stream")

        @self.httpServer.app.post("/")
        async def sendDataToServer(request: Request):
            data = None
            if request.headers.get("content-type") == "application/octet-stream":
                data = await request.body()
                data = pickle.loads(data)
            else:
                data = await request.json()

            print("Received Data from User")
            print(data)

            if data["TYPE"] == "FRAME_RENDERED":
                userId = data["USER_ID"]
                response = await self.handleUserMessage(data, userId)
                return response
            elif data["TYPE"] == "RENDER_COMPLETED":
                userId = data["USER_ID"]
                response = await self.handleUserMessage(data, userId)
                return response
            elif data["TYPE"] == "TEST":
                userId = data["USER_ID"]
                response = await self.handleUserMessage(data, userId)
                return response
            else:
                return JSONResponse(content={"DATA" : "RECEIVED" , "TIME" : time.time()}, status_code=200)

    async def ConfigureAPIRoutes(self):
        @self.apiServer.app.post("/CommunicationInterface/AddBufferMsg")
        async def addBufferMsg(request: Request):
            data = await request.json()
            print("Received Buffer Message from Communication Interface")
            print(data)

            bufferUUID = data["DATA"]["BUFFER_UUID"]
            bufferMsg = data["DATA"]["BUFFER_MSG"]

            self.bufferMsgs[bufferUUID] = bufferMsg

            return JSONResponse(content={"STATUS" : "SUCCESS" , "TIME" : time.time()}, status_code=200)

    async def sendMessageToUserManager(self, mainMessage, bytes=False):
        exchangeName = "USER_MANAGER_EXCHANGE"
        routingKey = "UME_USER_HTTP_SERVER"

        if bytes:
            messageInBytes = pickle.dumps(mainMessage)
            await self.messageQueue.PublishMessage(exchangeName, routingKey, messageInBytes)
        else:
            messageInJson = json.dumps(mainMessage)
            await self.messageQueue.PublishMessage(exchangeName, routingKey, messageInJson)

    async def startService(self):
        await self.messageQueue.InitializeConnection()
        await self.messageQueue.AddQueueAndMapToCallback("UHTTPSE_CI", self.callbackCommunicationInterfaceMessages, auto_delete = True)
        await self.messageQueue.BoundQueueToExchange()
        await self.messageQueue.StartListeningToQueue()

        await self.ConfigureHTTPRoutes()
        await self.ConfigureAPIRoutes()
        
        # Start both servers
        asyncio.create_task(self.httpServer.run_app())
        await self.apiServer.run_app()

    async def callbackCommunicationInterfaceMessages(self, message):
        print("Received Message from Communication Interface")
        DecodedMessage = message.body.decode()
        DecodedMessage = json.loads(DecodedMessage)

        await self.handleCommunicationInterfaceMessages(DecodedMessage)

    async def handleCommunicationInterfaceMessages(self, CIMessage):
        msgType = CIMessage['TYPE']
        msgData = CIMessage['DATA']
        
        if msgType == "ADD_BUFFER_MSG":
            bufferUUID = msgData['BUFFER_UUID']
            bufferMsg = msgData['BUFFER_MSG']
            self.bufferMsgs[bufferUUID] = bufferMsg
            print("Buffer Message Added")
        else:
            print("Unknown Message Type")
            print("Received Message: ", CIMessage)

class Service:
    def __init__(self, userHttpServerService=None):
        self.userHttpServerService = userHttpServerService

    async def startService(self):
        print("Starting User HTTP Server Service...")
        await self.userHttpServerService.startService()

async def start_service():
    dataClass = UserHTTPServerData()
    userHttpServerService = userHttpServerService(dataClass)
    service = Service(userHttpServerService)
    await service.startService()

if __name__ == "__main__":
    asyncio.run(start_service())
