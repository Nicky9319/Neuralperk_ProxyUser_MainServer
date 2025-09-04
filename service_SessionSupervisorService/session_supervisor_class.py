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

import requests

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



# ------------------ Session Supervisor Class -------------------------- #

class sessionSupervisorClass:
    def __init__(self, customer_id = None, object_id = None, session_id = None):
        self.customer_id = customer_id
        self.object_id = object_id

        self.session_id = session_id
        self.sessionRoutingKey = f"SESSION_SUPERVISOR_{self.session_id}"

        self.mongodb_service_url = os.getenv("MONGODB_SERVICE", "").strip()
        if not self.mongodb_service_url or not (self.mongodb_service_url.startswith("http://") or self.mongodb_service_url.startswith("https://")):
            self.mongodb_service_url = "http://127.0.0.1:12000"
        else:
            self.mongodb_service_url = self.mongodb_service_url

        # Make API call to get blend file path
        response = requests.get(
            f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/get-blend-file-name/{self.object_id}",
            params={"customer_id": self.customer_id}
        )
        print(f"API Response Status: {response.status_code}")
        print(f"API Response: {response.text}")
        
        # Check if the API call was successful
        if response.status_code == 200:
            response_data = response.json()
            self.blendFilePath = response_data.get("blendFilePath")
            print(self.blendFilePath)
            if not self.blendFilePath:
                raise ValueError("blendFilePath not found in API response")
        else:
            raise Exception(f"Failed to get blend file path. Status code: {response.status_code}, Response: {response.text}")

        self.user_list = []
        self.frameNumberMappedToUser = {}

        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.mq_client = MessageQueue()

    

    async def initialization(self):
        await self.mq_client.connect()

        await self.mq_client.declare_exchange("SESSION_SUPERVISOR_EXCHANGE", exchange_type=ExchangeType.DIRECT)

        await self.mq_client.declare_queue(f"SESSION_SUPERVISOR_{self.session_id}")
        await self.mq_client.bind_queue(f"SESSION_SUPERVISOR_{self.session_id}", "SESSION_SUPERVISOR_EXCHANGE", routing_key=f"SESSION_SUPERVISOR_{self.session_id}")
        await self.mq_client.consume(f"SESSION_SUPERVISOR_{self.session_id}", self.callbackUserManagerMessages)

        
    async def callbackUserManagerMessages(self, message):
        """
            Callback Function to Listen to events emitted by the User Manager
            Currently It is only works with json format data.
            other data types like bytes and all Can be added later if needed.

        """

        decoded_message = message.body.decode()
        json_message = json.loads(decoded_message)

        async def handleUserManagerMessages(payload):
            if payload["topic"] == "new-session":
                self.session_id = payload["session-id"]
                self.sessionRoutingKey = f"SESSION_SUPERVISOR_{self.session_id}"
            else:
                print("Unknown Event Type")
                print("Received Event: ", payload)

        await self.handleUserManagerMessages(json_message)

    

    async def start_workload(self):
        if self.customer_id is None or self.object_id is None:
            return JSONResponse(content={"message": "Customer ID or Object ID is missing"}, status_code=400)


    def __del__(self):
        """
        Destructor - handles cleanup when object is garbage collected.
        Note: This is a fallback mechanism. Prefer calling cleanup() explicitly.
        """
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, schedule the cleanup task
                asyncio.create_task(self._async_cleanup())
            else:
                # If no loop is running, run the cleanup in a new event loop
                asyncio.run(self._async_cleanup())
        except RuntimeError:
            # No event loop available, cleanup will be skipped
            print("Warning: Could not perform async cleanup in destructor - no event loop available")
    
    async def _async_cleanup(self):
        """Internal async cleanup method"""
        try:
            payload = {
                "topic": "users-released",
                "session-id": self.session_id,
                "data": {
                    "user_list": self.user_list,
                }
            }
            
            # Convert payload to JSON string for message queue
            import json
            message_body = json.dumps(payload)
            
            await self.mq_client.publish_message("SESSION_SUPERVISOR_EXCHANGE", "SESSION_SUPERVISOR", message_body)
            
            # Close the message queue connection
            if self.mq_client.connection:
                await self.mq_client.close()
                
        except Exception as e:
            print(f"Error during async cleanup: {e}")
    
    async def cleanup(self):
        """
        Explicit cleanup method that should be called when the session supervisor is no longer needed.
        This is the preferred way to clean up resources.
        """
        await self._async_cleanup()



# async def main():
#     session_supervisor = sessionSupervisorClass(customer_id="2e4110a3-1003-4153-934a-4cc39c98d858", object_id="678f72d7-7284-4160-9c9a-03c12a8aa6ab", session_id="789")
#     await session_supervisor.start_workload()

# if __name__ == "__main__":
#     asyncio.run(main())