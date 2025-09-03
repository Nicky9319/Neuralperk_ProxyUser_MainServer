import asyncio
import httpx
import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


# ---------------- Shared Data ---------------- #
class Data:
    def __init__(self):
        self.connected_users: Dict[str, Any] = {}
        # You can attach more shared objects here
        self.db_service_url = "127.0.0.1:8000"  # example
        self.donna_agent_instance = None  # attach your donna agent here


# ---------------- Unified Service ---------------- #
class Service:
    def __init__(self, host: str = "127.0.0.1", port: int = 8500, data_class_instance: Data = None):
        self.host = host
        self.port = port
        self.data_class = data_class_instance or Data()

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

    # -------- Configure Routes -------- #
    async def configure_routes(self):
        @self.app.get("/")
        async def root():
            return {"message": "Donna Agent is running"}

        @self.app.get("/api/get-all-tasks")
        async def get_all_tasks():
            try:
                response = await self.data_class.donna_agent_instance.get_all_tasks_details()
                if response["status"]:
                    return {"status": 200, "payload": response.get("payload", [])}
                return {"status": 400, "message": response.get("details", "Failed")}
            except Exception as e:
                return {"status": 500, "message": f"Error: {e}"}

        # Add more FastAPI routes here as needed...

    # -------- Configure Socket.IO -------- #
    async def configure_socket(self):
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
            await self.configure_routes()
            await self.configure_socket()

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
        service = Service(host="127.0.0.1", port=8500, data_class_instance=data_class)
        await service.start_server()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(start_service())
