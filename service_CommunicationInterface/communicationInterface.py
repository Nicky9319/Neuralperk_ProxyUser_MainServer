import asyncio

import sys
import os
import threading

import uuid

import json

from fastapi import Request,  Response

import requests

import pickle

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

class CommunicationInterfaceData:
    def __init__(self):
        self.connection_url = "amqp://guest:guest@localhost/"
        self.exchange_name = "COMMUNICATION_INTERFACE_EXCHANGE"
        self.http_host = "127.0.0.1"
        self.http_port = 7000
        
        # Communication interface specific configurations
        self.service_url_mapping_file = "ServiceURLMapping.json"
        self.default_timeout = 30
        self.max_retries = 3
        self.buffer_cleanup_interval = 300  # 5 minutes

class CommunicationInterfaceService():
    def __init__(self, data_class=None):
        self.data = data_class or CommunicationInterfaceData()
        self.messageQueue = MessageQueue(self.data.connection_url, self.data.exchange_name)
        self.apiServer = HTTPServer(self.data.http_host, self.data.http_port)

    async def getServiceURL(self, serviceName):
        servicePortMapping = json.load(open(self.data.service_url_mapping_file))
        return servicePortMapping[serviceName]

    async def ConfigureApiRoutes(self):
        pass

    async def sendMessageToUserManager(self, userManagerMessage, headers=None):
        print("Sending Message to User Manager")
        exchangeName = "USER_MANAGER_EXCHANGE"
        routing_key = "UME_USER_SERVER"

        if headers and "DATA_FORMAT" in headers:
            if headers["DATA_FORMAT"] == "BYTES":
                messageInBytes = pickle.dumps(userManagerMessage)
                await self.messageQueue.PublishMessage(exchangeName, routing_key, messageInBytes, headers)
                return
            else:
                messageInJson = json.dumps(userManagerMessage)
                await self.messageQueue.PublishMessage(exchangeName, routing_key, messageInJson, headers)
                return
        else:
            messageInJson = json.dumps(userManagerMessage)
            await self.messageQueue.PublishMessage(exchangeName, routing_key, messageInJson)

        # messageInJson = json.dumps(userManagerMessage)
        # await self.messageQueue.PublishMessage(exchangeName, routing_key, messageInJson)
        print("Message Sent to User Manager")

    async def SendMessageToHttpServer(self, messageToSend):
        exchangeName = "USER_HTTP_SERVER_EXCHANGE"
        routing_key = "UHTTPSE_CI"
        messageInJson = json.dumps(messageToSend)
        await self.messageQueue.PublishMessage(exchangeName, routing_key, messageInJson)

    async def sendMessageToWsServer(self, messageToSend):
        exchangeName = "USER_WS_SERVER_EXCHANGE"
        routing_key = "UWSSE_CI"
        messageInJson = json.dumps(messageToSend)
        # print("CI: Sending Message To Ws Server")
        await self.messageQueue.PublishMessage(exchangeName, routing_key, messageInJson)
        # print("CI : Message Send to Ws Server")
        
    async def sendMessageToUser(self, userId, message):
        generateMessageUUID = str(uuid.uuid4())
        
        mainMessage = {"BUFFER_UUID" : generateMessageUUID , "BUFFER_MSG" : message}
        messageToSend = {"TYPE": "ADD_BUFFER_MSG" , "DATA": mainMessage}

        userHttpServerServiceURL = await self.getServiceURL("USER_HTTP_SERVER")
        response = requests.post(f"http://{userHttpServerServiceURL}/CommunicationInterface/AddBufferMsg", json=messageToSend)
        if response.status_code == 200:
            print("Buffer Message Added to User")
            mainMessage = {"USER_ID" : userId , "BUFFER_UUID" : generateMessageUUID}
            messageToSend = {"TYPE": "SEND_BUFFER_REQUEST" , "DATA": mainMessage}
            await self.sendMessageToWsServer(messageToSend)

    async def handleUserManagerMessages(self, userManagerMessage, response=False):
        print(type(userManagerMessage))
        msgType = userManagerMessage['TYPE']
        msgData = userManagerMessage['DATA']
        responseMsg = None
        if msgType == "SEND_MESSAGE_TO_USER":
            print("CI : User Manager Asked to Send Message to User")
            userId = msgData["USER_ID"]
            message = msgData["MESSAGE_FOR_USER"]
            await self.sendMessageToUser(userId, message)
            responseMsg = {"STATUS": "SUCCESS"}
        else:
            print("Unknown Message Type")
            print("Received Message: ", userManagerMessage)
            responseMsg = {"STATUS": "FAILED", "ERROR": "Unknown message type"}

        if response:
            return responseMsg

    async def callbackUserManagerMessages(self, message):
        print("Received Message from User Manager")
        DecodedMessage = message.body.decode()
        DecodedMessage = json.loads(DecodedMessage)

        await self.handleUserManagerMessages(DecodedMessage)

    async def startService(self):
        await self.messageQueue.InitializeConnection()
        await self.messageQueue.AddQueueAndMapToCallback("CIE_USER_MANAGER", self.callbackUserManagerMessages, auto_delete = True)
        await self.messageQueue.BoundQueueToExchange()
        await self.messageQueue.StartListeningToQueue()

        await self.ConfigureApiRoutes()
        await self.apiServer.run_app()

class Service:
    def __init__(self, communicationInterfaceService=None):
        self.communicationInterfaceService = communicationInterfaceService

    async def startService(self):
        print("Starting Communication Interface Service...")
        await self.communicationInterfaceService.startService()

async def start_service():
    dataClass = CommunicationInterfaceData()
    communicationInterfaceService = CommunicationInterfaceService(dataClass)
    service = Service(communicationInterfaceService)
    await service.startService()

if __name__ == "__main__":
    asyncio.run(start_service())