import asyncio
import httpx
import socketio
import uvicorn
from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from dotenv import load_dotenv

import os


load_dotenv()


# ---------------- Shared Data ---------------- #
class Data:
    def __init__(self):
        self.connected_users: Dict[str, Any] = {}
        # You can attach more shared objects herele
        self.donna_agent_instance = None  # attach your donna agent here


# ---------------- Unified Service ---------------- #
class Service:
    def __init__(self, host: str = "127.0.0.1", httpServerPrivilegedIpAddress=["127.0.0.1"], port: int = 8500, data_class_instance: Data = None):
        self.host = host
        self.port = port
        self.data_class = data_class_instance or Data()

        self.http_client = httpx.AsyncClient()

        self.privileged_ip_address = httpServerPrivilegedIpAddress

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
            message = data["message"]
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
        async def frame_rendered():
            pass
        
        @self.app.post("/api/user-service/user/rendering-completed")
        async def rendering_completed():
            pass
        

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
        service = Service(host="127.0.0.1", httpServerPrivilegedIpAddress=["127.0.0.1"], port=8500, data_class_instance=data_class)
        await service.start_server()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(start_service())
