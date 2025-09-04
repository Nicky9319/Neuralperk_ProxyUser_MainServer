import asyncio
import os
from typing import Any, Dict

import aio_pika
from aio_pika import ExchangeType, Message
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



# ---------------- Shared Data ---------------- #
class Data:
    def __init__(self):
        self.connected_users: Dict[str, Any] = {}
        # You can attach more shared objects herele
        self.donna_agent_instance = None  # attach your donna agent here

        self.mq_client = MessageQueue()
    
    async def initialization(self):
        await self.mq_client.connect()


        # This Configs are just for Development and Tetsing purposes

        await self.mq_client.declare_exchange("USER_MANAGER_EXCHANGE", exchange_type=ExchangeType.DIRECT)
        # await self.mq_client.declare_queue("USER_SERVICE")
        # await self.mq_client.bind_queue("USER_SERVICE", "USER_MANAGER_EXCHANGE", routing_key="USER_SERVICE")


# ---------------- Unified Service ---------------- #
class Service:
    def __init__(self, host: str = "127.0.0.1", httpServerPrivilegedIpAddress=["127.0.0.1"], port: int = 8500, data_class_instance: Data = None):
        self.host = host
        self.port = port
        self.data_class = data_class_instance or Data()

        self.http_client = httpx.AsyncClient()

        self.privileged_ip_address = httpServerPrivilegedIpAddress
        self.user_manager_exchange_name = "USER_MANAGER_EXCHANGE"

        # FastAPI app
        self.app = FastAPI()
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Socket.IO server
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins="*",
            ping_timeout=60,
            ping_interval=25,
            transports=["websocket", "polling"],
        )

        # Merge Socket.IO and FastAPI into one ASGI app
        self.asgi_app = socketio.ASGIApp(self.sio, self.app)

        # uvicorn server instance
        self.server = None

        # Get MongoDB service URL from environment
        env_url = os.getenv("MONGO_DB_SERVICE", "").strip()
        if not env_url or not (env_url.startswith("http://") or env_url.startswith("https://")):
            self.mongodb_service_url = "http://127.0.0.1:12000"
        else:
            self.mongodb_service_url = env_url
        
        # Get Blob service URL from environment
        blob_env_url = os.getenv("BLOB_SERVICE", "").strip()
        if not blob_env_url or not (blob_env_url.startswith("http://") or blob_env_url.startswith("https://")):
            self.blob_service_url = "http://127.0.0.1:13000"
        else:
            self.blob_service_url = blob_env_url
        

        self.user_manager_exchange_name = "USER_MANAGER_EXCHANGE"


        

    # -------- Utility Functions -------- #
    async def send_message_to_user(self, sid, message):
        self.sio.emit("request-buffer", message, to=sid)

    # -------- Configure Routes -------- #
    async def configure_http_routes(self):
        @self.app.get("/api/user-service/")
        async def root():
            return {"message": "Donna Agent is running"}

        @self.app.post("/api/user-service/user-manager/send-msg-to-user")
        async def send_msg_to_user(request: Request):
            data = await request.json()
            user_id = data["user_id"]
            message = data["data"]
            await self.send_message_to_user(user_id, message)
            return {"status": 200, "message": "Message sent to user"}

        @self.app.get("/api/user-service/user/get-blend-file/{blend_file_hash}")
        async def get_blend_file(blend_file_hash: str):
            try:
                # Step 1: Query MongoDB service for blend file path
                try:
                    blend_file_data = await self.http_client.get(
                        f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/find-by-hash/{blend_file_hash}",
                        timeout=10.0
                    )
                except Exception as e:
                    print(f"Error contacting MongoDB service: {str(e)}")
                    raise HTTPException(
                        status_code=502,
                        detail=f"Failed to contact MongoDB service: {str(e)}"
                    )

                if blend_file_data.status_code != 200:
                    try:
                        error_detail = blend_file_data.json().get("detail", blend_file_data.text)
                    except Exception:
                        error_detail = blend_file_data.text
                    print(f"MongoDB service returned error: {blend_file_data.status_code} - {error_detail}")
                    raise HTTPException(
                        status_code=blend_file_data.status_code,
                        detail=f"MongoDB service error: {error_detail}"
                    )

                try:
                    blend_file_json = blend_file_data.json()
                except Exception as e:
                    print(f"Failed to parse MongoDB response JSON: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to parse MongoDB service response"
                    )

                blend_file_path = blend_file_json.get("blendFilePath")
                if not blend_file_path:
                    print("blendFilePath not found in MongoDB response")
                    raise HTTPException(
                        status_code=404,
                        detail="Blend file not found for the given hash"
                    )

                bucket = "blend-files"
                key = blend_file_path

                print(f"Retrieving from bucket: {bucket}, key: {key}")

                # Step 2: Proxy the response directly from blob service to client
                print(f"Proxying blend file from blob service...")

                # Create a streaming response that proxies the blob service
                async def proxy_blend_file():
                    try:
                        async with httpx.AsyncClient() as proxy_client:
                            async with proxy_client.stream(
                                "GET",
                                f"{self.blob_service_url}/api/blob-service/retrieve-blend",
                                params={
                                    "bucket": bucket,
                                    "key": key
                                },
                                timeout=30.0
                            ) as response:
                                if response.status_code != 200:
                                    # If blob service fails, we need to handle it differently
                                    try:
                                        error_content = await response.aread()
                                        error_detail = error_content.decode(errors="replace")
                                    except Exception:
                                        error_detail = "Unknown error"
                                    print(f"Blob service returned error: {response.status_code} - {error_detail}")
                                    raise HTTPException(
                                        status_code=response.status_code,
                                        detail=f"Blob service error: {error_detail}"
                                    )

                                # Stream the response directly to the client
                                async for chunk in response.aiter_bytes():
                                    yield chunk

                    except HTTPException:
                        raise
                    except Exception as e:
                        print(f"Error in proxy stream: {str(e)}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to proxy blend file: {str(e)}"
                        )

                # Return streaming response with proper headers
                file_name = os.path.basename(blend_file_path) if blend_file_path else "blendfile.blend"
                print(f"Proxying blend file: {file_name}")

                return StreamingResponse(
                    proxy_blend_file(),
                    media_type="application/octet-stream",
                    headers={
                        "Content-Disposition": f"attachment; filename=\"{file_name}\"",
                        "Cache-Control": "no-cache"
                    }
                )
            except HTTPException:
                raise
            except Exception as e:
                print(f"Unexpected error in get_blend_file: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal server error: {str(e)}"
                )

        @self.app.post("/api/user-service/user/frame-rendered")
        async def frame_rendered(
            userId: str = Form(...),
            frameNumber: str = Form(...),
            imageBinary: UploadFile = File(...),
            imageExtension: str = Form(...)
        ):
            try:
                random_id = str(uuid.uuid4())
                # Try to upload the image to the blob service
                try:
                    response = await self.http_client.post(
                        f"{self.blob_service_url}/api/blob-service/store-temp",
                        data={
                            "key": f"{userId}/{frameNumber}_{random_id}.{imageExtension}",
                        },
                        files={"file": (imageBinary.filename, await imageBinary.read(), "application/octet-stream")}
                    )
                except Exception as e:
                    print(f"Error uploading to blob service: {e}")
                    return JSONResponse(
                        content={"error": f"Failed to upload image to blob service: {str(e)}"},
                        status_code=500
                    )

                # Check if the blob service returned an error
                if response.status_code != 200:
                    try:
                        error_content = await response.aread()
                        error_detail = error_content.decode(errors="replace")
                    except Exception:
                        error_detail = "Unknown error"
                    print(f"Blob service returned error: {response.status_code} - {error_detail}")
                    return JSONResponse(
                        content={"error": f"Blob service error: {error_detail}"},
                        status_code=response.status_code
                    )

                print(response)

                new_payload = {
                    "topic": "user-frame-rendered",
                    "payload": {
                        "user-id": userId,
                        "frame-number": frameNumber,
                        "image-extension": imageExtension,
                        "image-binary-path": f"{userId}/{frameNumber}_{random_id}.{imageExtension}"
                    }
                }

                try:
                    await self.data_class.mq_client.publish_message(self.user_manager_exchange_name, "USER_SERVICE", json.dumps(new_payload))
                except Exception as e:
                    print(f"Error publishing message to MQ: {e}")
                    return JSONResponse(
                        content={"error": f"Failed to publish message to user manager: {str(e)}"},
                        status_code=500
                    )

                return JSONResponse(content={"message": "Rendered Image Recevied Successfully"}, status_code=200)
            except Exception as e:
                print(f"Unexpected error in frame_rendered: {e}")
                return JSONResponse(
                    content={"error": f"Internal server error: {str(e)}"},
                    status_code=500
                )
        
        @self.app.post("/api/user-service/user/rendering-completed")
        async def rendering_completed(
            userId: str = Form(...)
        ):
            try:
                new_payload = {
                    "topic": "user-rendering-completed",
                    "payload": {
                        "user-id": userId
                    }
                }
                try:
                    await self.data_class.mq_client.publish_message(self.user_manager_exchange_name, "USER_SERVICE", json.dumps(new_payload))
                except Exception as e:
                    print(f"Error publishing rendering completed message to MQ: {e}")
                    return JSONResponse(
                        content={"error": f"Failed to publish rendering completed event: {str(e)}"},
                        status_code=500
                    )

                return JSONResponse(content={"message": "Rendering Completed Event Received Successfully"}, status_code=200)
            except Exception as e:
                print(f"Unexpected error in rendering_completed: {e}")
                return JSONResponse(
                    content={"error": f"Internal server error: {str(e)}"},
                    status_code=500
                )
        

        # Add more FastAPI routes here as needed...

    # -------- Configure Socket.IO -------- #
    async def configure_socketio_routes(self):
        @self.sio.event
        async def connect(sid, environ):
            self.data_class.connected_users[sid] = environ
            print(f"🔌 Client connected: {sid}")

        @self.sio.event
        async def disconnect(sid):
            self.data_class.connected_users.pop(sid, None)
            print(f"❌ Client disconnected: {sid}")

        @self.sio.on("get-sid")
        async def get_sid(sid):
            return sid

    # -------- Start Server -------- #
    async def start_server(self):
        try:
            await self.configure_http_routes()
            await self.configure_socketio_routes()

            config = uvicorn.Config(
                app=self.asgi_app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True,
            )
            self.server = uvicorn.Server(config)

            print(f"🚀 Starting server at http://{self.host}:{self.port}")
            await self.server.serve()
        except Exception as e:
            print(f"❌ Error starting server: {e}")
            raise

    # -------- Stop Server -------- #
    async def stop_server(self):
        if self.server:
            print("🛑 Stopping server...")
            self.server.should_exit = True


# ---------------- Entrypoint ---------------- #
async def start_service():
    try:
        data_class = Data()
        await data_class.initialization()
        service = Service(host="127.0.0.1", httpServerPrivilegedIpAddress=["127.0.0.1"], port=8500, data_class_instance=data_class)
        await service.start_server()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(start_service())
