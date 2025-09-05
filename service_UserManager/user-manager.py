import asyncio
import os
from typing import Any, Dict

import aio_pika
from aio_pika import ExchangeType, Message
from click.core import F
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import Request
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import UploadFile, Form, File
import httpx
from pydantic import BaseModel
import socketio
import uvicorn

import uuid
import json

load_dotenv()

# ---------------- Message Queue ---------------- #

class MessageQueue:

    def __init__(self, connection_url="amqp://guest:guest@localhost/"):
        """
        Generic RabbitMQ wrapper.
        Works for both producer and consumer roles.
        """
        self.connection_url = connection_url
        self.connection = None
        self.channel = None
        self.exchanges = {}  # store declared exchanges
        self.queues = {}     # store declared queues

    async def connect(self):
        """Establish robust async connection and channel"""
        self.connection = await aio_pika.connect_robust(self.connection_url)
        self.channel = await self.connection.channel()

    async def declare_exchange(self, name, exchange_type=ExchangeType.DIRECT):
        """
        Declare an exchange of any type (direct, fanout, topic, headers)
        """
        if name not in self.exchanges:
            exchange = await self.channel.declare_exchange(name, exchange_type, durable=True)
            self.exchanges[name] = exchange
        return self.exchanges[name]

    async def declare_queue(self, name, **kwargs):
        """
        Declare a queue. If not durable, it will vanish when broker restarts.
        """
        if name not in self.queues:
            queue = await self.channel.declare_queue(name, durable=True, **kwargs)
            self.queues[name] = queue
        return self.queues[name]

    async def bind_queue(self, queue_name, exchange_name, routing_key=""):
        """
        Bind a queue to an exchange with an optional routing key.
        """
        queue = self.queues.get(queue_name)
        exchange = self.exchanges.get(exchange_name)

        if not queue or not exchange:
            raise Exception("Queue or Exchange not declared before binding.")

        await queue.bind(exchange, routing_key=routing_key)

    async def publish_message(self, exchange_name, routing_key, message_body, headers=None):
        """
        Publish message to exchange with routing key.
        """
        if exchange_name not in self.exchanges:
            raise Exception(f"Exchange '{exchange_name}' not declared!")

        message = Message(
            body=message_body.encode() if isinstance(message_body, str) else message_body,
            headers=headers or {},
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )

        await self.exchanges[exchange_name].publish(message, routing_key=routing_key)

    async def consume(self, queue_name, callback, no_ack=False):
        """
        Consume messages from a queue.
        """
        if queue_name not in self.queues:
            raise Exception(f"Queue '{queue_name}' not declared!")

        await self.queues[queue_name].consume(callback, no_ack=no_ack)

    async def close(self):
        """Close connection gracefully"""
        await self.connection.close()


# ---------------- HTTP Server ---------------- #

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
        env_url = os.getenv("MONGODB_SERVICE", "").strip()
        if not env_url or not (env_url.startswith("http://") or env_url.startswith("https://")):
            self.mongodb_service_url = "http://127.0.0.1:12000"
        else:
            self.mongodb_service_url = env_url
        
        # Get Auth service URL from environment
        auth_env_url = os.getenv("AUTH_SERVICE", "").strip()
        if not auth_env_url or not (auth_env_url.startswith("http://") or auth_env_url.startswith("https://")):
            self.auth_service_url = "http://127.0.0.1:10000"
        else:
            self.auth_service_url = auth_env_url
        
        # Get Blob service URL from environment
        blob_env_url = os.getenv("BLOB_SERVICE", "").strip()
        if not blob_env_url or not (blob_env_url.startswith("http://") or blob_env_url.startswith("https://")):
            self.blob_service_url = "http://127.0.0.1:13000"
        else:
            self.blob_service_url = blob_env_url
        
        # HTTP client for making requests to MongoDB service and Auth service
        self.http_client = httpx.AsyncClient(timeout=30.0)

        self.mq_client = MessageQueue()


    # Callback Function to Listen to events emitted by the User Service
    async def callbackUserServiceMessages(self, message):
        """
            Callback Function to Listen to events emitted by the User Service
            Currently It is only works with json format data.
            other data types like bytes and all Can be added later if needed.

        """

        async def handleUserServiceEvent(payload):
            """
                payload should contain a Mandatory topic field and the data field.
            """



            topic = payload.get("topic", None)
            data = payload.get("data", None)

            if topic is None or data is None:
                print(payload)
                print("Invalid Payload")
                print("Payload Need to contain the topic and data fields. It is mandatory")
                return

            if topic == "user-frame-rendered":
                print("user Frame Rendered Event Received")
            elif topic == "user-rendering-completed":
                print("user Rendering Completed Event Received")
            else:
                print("Unknown Event Type")
                print("Received Event: ", payload)

        
        decoded_message = message.body.decode()
        json_message = json.loads(decoded_message)

        await handleUserServiceEvent(json_message)
        return
        
    async def callbackSessionSupervisorMessages(self, message):
        """
            Callback Function to Listen to events emitted by the Session Supervisor
            Currently It is only works with json format data.
            other data types like bytes and all Can be added later if needed.

        """
        print("Received Message from Session Supervisor")
        decoded_message = message.body.decode()
        json_message = json.loads(decoded_message)

        async def handleSessionSupervisorEvent(payload):
            """
                payload should contain a Mandatory topic field, supervisor id and the data field.
            """
            topic = payload.get("topic", None)
            supervisor_id = payload.get("supervisor-id", None)
            data = payload.get("data", None)

            if topic is None or supervisor_id is None or data is None:
                print("Invalid Payload")
                print("Payload Need to contain the topic, supervisor-id and data fields. It is mandatory")
                return

            if payload["topic"] == "session-supervisor-initialized":
                print("Session Supervisor Initialized Event Received")
            elif payload["topic"] == "session-supervisor-ready":
                print("Session Supervisor Ready Event Received")
            else:
                print("Unknown Event Type")
                print("Received Event: ", payload)

        await handleSessionSupervisorEvent(json_message)
        return

    async def initialization(self):
        await self.mq_client.connect()

        await self.mq_client.declare_exchange("USER_MANAGER_EXCHANGE", exchange_type=ExchangeType.DIRECT)

        await self.mq_client.declare_queue("USER_SERVICE")
        await self.mq_client.bind_queue("USER_SERVICE", "USER_MANAGER_EXCHANGE", routing_key="USER_SERVICE")
        await self.mq_client.consume("USER_SERVICE" , self.callbackUserServiceMessages)


        await self.mq_client.declare_queue("SESSION_SUPERVISOR")
        await self.mq_client.bind_queue("SESSION_SUPERVISOR", "USER_MANAGER_EXCHANGE", routing_key="SESSION_SUPERVISOR")
        await self.mq_client.consume("SESSION_SUPERVISOR" , self.callbackSessionSupervisorMessages)


    async def configure_routes(self):

        @self.app.post("/api/user-manager/")
        async def userManagerServiceRoot(request: Request):
            print("User Manager Service Root Endpoint Hit")
            return JSONResponse(content={"message": "User Manager Service is active"}, status_code=200)

        @self.app.post("/api/user-manager/session-supervisor/new-session")
        async def newSession(
            user_count: int = Form(...),
            session_supervisor_id: str = Form(...)
        ):
            pass


    async def run_app(self):
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()


# ---------------- Data Class ---------------- #

class Data():
    def __init__(self):
        self.customerSessionsMapping = {}

# ---------------- Service Class ---------------- #

class Service():
    def __init__(self, httpServer = None):
        self.httpServer = httpServer

    async def startService(self):
        await self.httpServer.initialization()
        await self.httpServer.configure_routes()
        await self.httpServer.run_app()

         
async def start_service():
    dataClass = Data()

    #<HTTP_SERVER_INSTANCE_INTIALIZATION_START>

    #<HTTP_SERVER_PORT_START>
    httpServerPort = 7000
    #<HTTP_SERVER_PORT_END>

    #<HTTP_SERVER_HOST_START>
    httpServerHost = "0.0.0.0"
    #<HTTP_SERVER_HOST_END>

    #<HTTP_SERVER_PRIVILEGED_IP_ADDRESS_START>
    httpServerPrivilegedIpAddress = ["127.0.0.1"]
    #<HTTP_SERVER_PRIVILEGED_IP_ADDRESS_END>

    http_server = HTTP_SERVER(httpServerHost=httpServerHost, httpServerPort=httpServerPort, httpServerPrivilegedIpAddress=httpServerPrivilegedIpAddress, data_class_instance=dataClass)
    #<HTTP_SERVER_INSTANCE_INTIALIZATION_END>

    service = Service(http_server)
    await service.startService()
  

if __name__ == "__main__":
    asyncio.run(start_service())
