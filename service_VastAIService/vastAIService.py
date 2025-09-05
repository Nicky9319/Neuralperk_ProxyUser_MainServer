import asyncio
from fastapi import FastAPI, Response, Request
import uvicorn

import asyncio
import aio_pika
import json
import time

# Import the VastAI manager
from vastAIManager import VastAIManager

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

class VastAIData:
    def __init__(self):
        self.connection_url = "amqp://guest:guest@localhost/"
        self.exchange_name = "/"
        self.http_host = "127.0.0.1"
        self.http_port = 3232
        
        # VastAI specific configurations
        self.vastai_api_key = None
        self.vastai_base_url = "https://console.vast.ai/api/v0"
        self.instance_templates = {}

class VastAIService:
    def __init__(self, data_class=None):
        self.data = data_class or VastAIData()
        self.messageQueue = MessageQueue(self.data.connection_url, self.data.exchange_name)
        self.httpServer = HTTPServer(self.data.http_host, self.data.http_port)
        
        # Initialize the VastAI manager
        self.vast_manager = VastAIManager()

    async def handleQueueMessage1(self, message: aio_pika.IncomingMessage):
        """Handle VastAI instance creation requests"""
        try:
            msg_data = json.loads(message.body.decode())
            print("VastAI Create Instance Request:", msg_data)
            
            # Extract parameters
            offer_id = msg_data.get("offer_id")
            disk = msg_data.get("disk", 32)
            image = msg_data.get("image", "ubuntu:20.04")
            
            # Create instance using VastAI manager
            contract_id = self.vast_manager.create_instance(offer_id, disk, image)
            
            # Send response back via message queue
            response = {
                "status": "success" if contract_id else "failed",
                "contract_id": contract_id,
                "offer_id": offer_id
            }
            
            # You would publish this response back to the requesting service
            print("Instance creation result:", response)
            
        except Exception as e:
            print(f"Error handling create instance request: {e}")
    
    async def handleQueueMessage2(self, message: aio_pika.IncomingMessage):
        """Handle VastAI instance management requests (start/stop/destroy)"""
        try:
            msg_data = json.loads(message.body.decode())
            print("VastAI Management Request:", msg_data)
            
            action = msg_data.get("action")
            offer_id = msg_data.get("offer_id")
            
            if action == "start":
                self.vast_manager.start_instance(offer_id)
            elif action == "stop":
                self.vast_manager.stop_instance(offer_id)
            elif action == "destroy":
                self.vast_manager.destroy_instance(offer_id)
            elif action == "get_summary":
                summary = self.vast_manager.get_instance_summary(offer_id)
                print("Instance summary:", summary)
            
        except Exception as e:
            print(f"Error handling management request: {e}")

    async def configureAPIRoutes(self):
        @self.httpServer.app.get("/")
        async def read_root():
            print("VastAI Service Running")
            return {"message": "VastAI Service is Active"}
        
        @self.httpServer.app.get("/api/vastai/offers")
        async def list_offers(filters: str = None):
            """Get available VastAI offers"""
            try:
                filter_list = filters.split(",") if filters else None
                offers = self.vast_manager.list_offers(filter_list)
                return {"offers": offers}
            except Exception as e:
                return {"error": str(e)}
        
        @self.httpServer.app.post("/api/vastai/create")
        async def create_instance(request: Request):
            """Create a new VastAI instance"""
            try:
                data = await request.json()
                offer_id = data["offer_id"]
                disk = data.get("disk", 32)
                image = data.get("image", "ubuntu:20.04")
                
                contract_id = self.vast_manager.create_instance(offer_id, disk, image)
                
                return {
                    "status": "success" if contract_id else "failed",
                    "contract_id": contract_id,
                    "offer_id": offer_id
                }
            except Exception as e:
                return {"error": str(e)}
        
        @self.httpServer.app.post("/api/vastai/{action}/{offer_id}")
        async def manage_instance(action: str, offer_id: str):
            """Start, stop, or destroy an instance"""
            try:
                if action == "start":
                    self.vast_manager.start_instance(offer_id)
                elif action == "stop":
                    self.vast_manager.stop_instance(offer_id)
                elif action == "destroy":
                    self.vast_manager.destroy_instance(offer_id)
                else:
                    return {"error": "Invalid action"}
                
                return {"status": "success", "action": action, "offer_id": offer_id}
            except Exception as e:
                return {"error": str(e)}
        
        @self.httpServer.app.get("/api/vastai/summary/{offer_id}")
        async def get_summary(offer_id: str):
            """Get instance summary and costs"""
            try:
                summary = self.vast_manager.get_instance_summary(offer_id)
                return summary if summary else {"error": "Instance not found"}
            except Exception as e:
                return {"error": str(e)}
    
    async def startService(self):
        await self.messageQueue.InitializeConnection()
        await self.messageQueue.AddQueueAndMapToCallback("queue1", self.handleQueueMessage1)
        await self.messageQueue.AddQueueAndMapToCallback("queue2", self.handleQueueMessage2)
        await self.messageQueue.StartListeningToQueue()

        await self.configureAPIRoutes()
        await self.httpServer.run_app()

class Service:
    def __init__(self, vastAIService=None):
        self.vastAIService = vastAIService

    async def startService(self):
        print("Starting VastAI Service...")
        await self.vastAIService.startService()

        
async def start_service():
    dataClass = VastAIData()
    vastAIService = VastAIService(dataClass)
    service = Service(vastAIService)
    await service.startService()

if __name__ == "__main__":
    asyncio.run(start_service())
