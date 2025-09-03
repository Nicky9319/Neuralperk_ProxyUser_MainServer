import asyncio
from fastapi import FastAPI, Response, Request
import uvicorn

import asyncio
import aio_pika
import json
import time

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

class MongoDBData:
    def __init__(self):
        self.connection_url = "amqp://guest:guest@localhost/"
        self.exchange_name = "/"
        self.http_host = "127.0.0.1"
        self.http_port = 5757
        
        # MongoDB specific configurations
        self.mongo_uri = "mongodb://localhost:27017/"
        self.database_name = "neuralperk"
        self.collections = {}

class MongoDBService:
    def __init__(self, data_class=None):
        self.data = data_class or MongoDBData()
        self.messageQueue = MessageQueue(self.data.connection_url, self.data.exchange_name)
        self.httpServer = HTTPServer(self.data.http_host, self.data.http_port)

    async def handleQueueMessage1(self, message: aio_pika.IncomingMessage):
        msg = message.body.decode()
        print("MongoDB Queue1 Message: ", msg)
    
    async def handleQueueMessage2(self, message: aio_pika.IncomingMessage):
        msg = message.body.decode()
        print("MongoDB Queue2 Message: ", msg)

    async def configureAPIRoutes(self):
        @self.httpServer.app.get("/")
        async def read_root():
            print("MongoDB Service Running")
            return {"message": "MongoDB Service is Active"}
    
    async def startService(self):
        await self.messageQueue.InitializeConnection()
        await self.messageQueue.AddQueueAndMapToCallback("queue1", self.handleQueueMessage1)
        await self.messageQueue.AddQueueAndMapToCallback("queue2", self.handleQueueMessage2)
        await self.messageQueue.StartListeningToQueue()

        await self.configureAPIRoutes()
        await self.httpServer.run_app()

class Service:
    def __init__(self, mongoDBService=None):
        self.mongoDBService = mongoDBService

    async def startService(self):
        print("Starting MongoDB Service...")
        await self.mongoDBService.startService()

        
async def start_service():
    dataClass = MongoDBData()
    mongoDBService = MongoDBService(dataClass)
    service = Service(mongoDBService)
    await service.startService()

if __name__ == "__main__":
    asyncio.run(start_service())
