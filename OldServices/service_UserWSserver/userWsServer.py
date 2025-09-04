import asyncio

import sys
import os
import threading

import socketio
import json

from aiohttp import web

from fastapi import Request,  Response

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

# Embedded WebSocketServer class
class WebSocketServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sio = socketio.AsyncServer()
        self.app = web.Application()
        self.sio.attach(self.app)

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host=self.host, port=self.port)
        await site.start()
        print(f"WebSocket server started at http://{self.host}:{self.port}")

class UserWSServerData:
    def __init__(self):
        self.connection_url = "amqp://guest:guest@localhost/"
        self.exchange_name = "USER_WS_SERVER_EXCHANGE"
        self.ws_host = "127.0.0.1"
        self.ws_port = 9000
        self.http_host = "127.0.0.1"
        self.http_port = 9001
        
        # User WebSocket server specific configurations
        self.ping_timeout = 60
        self.ping_interval = 25
        self.max_http_buffer_size = 1024 * 1024 * 100  # 100MB
        self.cors_allowed_origins = "*"

class userWsServerService:
    def __init__(self, data_class=None):
        self.data = data_class or UserWSServerData()
        self.messageQueue = MessageQueue(self.data.connection_url, self.data.exchange_name)
        self.apiServer = HTTPServer(self.data.http_host, self.data.http_port)

        self.wsServer = WebSocketServer(self.data.ws_host, self.data.ws_port)
        self.wsServer.sio = socketio.AsyncServer(
            async_mode='aiohttp',
            ping_timeout=self.data.ping_timeout, 
            ping_interval=self.data.ping_interval, 
            max_http_buffer_size=self.data.max_http_buffer_size
        )
        self.wsServer.app = web.Application()
        self.wsServer.sio.attach(self.wsServer.app)

        self.clients = {}

    async def ConfigureApiRoutes(self):
        pass
        

    async def ConfigureWsMethods(self):
        @self.wsServer.sio.event
        async def connect(sid, environ , auth=None):
            print(f"A New User with ID {sid} Connected")
            print(auth)

            self.clients[sid] = environ
            
            mainMessage = {"USER_ID" : sid}
            messageToSend = {"TYPE": "NEW_USER" , "DATA": mainMessage}
        
            await self.sendMessageToUserManager(messageToSend)

        @self.wsServer.sio.event
        async def disconnect(sid):
            del self.clients[sid]

            mainMessage = {"USER_ID" : sid}
            messageToSend = {"TYPE": "REMOVE_USER" , "DATA": mainMessage}

            await self.sendMessageToUserManager(messageToSend)

        @self.wsServer.sio.on("GET_SID")
        async def get_sid(sid):
            return sid

    async def handleCommunicationInterfaceMessages(self, CIMessage , response=False):
        msgType = CIMessage['TYPE']
        msgData = CIMessage['DATA']
        responseMsg = None
        if msgType == "SEND_BUFFER_REQUEST":
            userId = msgData['USER_ID']
            bufferUUID = msgData['BUFFER_UUID']
            await self.wsServer.sio.emit("REQUEST_BUFFER" , bufferUUID , to=userId)
            responseMsg = {"STATUS": "SUCCESS"}
        else:
            print("Unknown Message Type")
            print("Received Message: ", CIMessage)

        
        if response:
            return responseMsg

    async def callbackCommunicationInterfaceMessages(self, message):
        print("Received Message from Communication Interface")
        DecodedMessage = message.body.decode()
        DecodedMessage = json.loads(DecodedMessage)

        await self.handleCommunicationInterfaceMessages(DecodedMessage)
        

    async def sendMessageToUserManager(self, mainMessage):
        print("Sending Message to User Manager")
        exchangeName = "COMMUNICATION_INTERFACE_EXCHANGE"
        routingKey = "CIE_USER_WS_SERVER"

        messageToSend = {"TYPE": "MESSAGE_FOR_USER_MANAGER" , "DATA": mainMessage}

        messageInJson = json.dumps(messageToSend)
        await self.messageQueue.PublishMessage(exchangeName, routingKey, messageInJson)

    async def startService(self):
        await self.messageQueue.InitializeConnection()
        await self.messageQueue.AddQueueAndMapToCallback("UWSSE_CI", self.callbackCommunicationInterfaceMessages, auto_delete = True)
        await self.messageQueue.BoundQueueToExchange()
        await self.messageQueue.StartListeningToQueue()

        await self.ConfigureApiRoutes()
        await self.ConfigureWsMethods()
        
        # Start both servers
        asyncio.create_task(self.wsServer.start())
        await self.apiServer.run_app()

class Service:
    def __init__(self, userWsServerService=None):
        self.userWsServerService = userWsServerService

    async def startService(self):
        print("Starting User WebSocket Server Service...")
        await self.userWsServerService.startService()

async def start_service():
    dataClass = UserWSServerData()
    userWsServerService = userWsServerService(dataClass)
    service = Service(userWsServerService)
    await service.startService()

if __name__ == "__main__":
    asyncio.run(start_service())

