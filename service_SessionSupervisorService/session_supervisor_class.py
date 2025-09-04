import asyncio
import os
from typing import Any, Dict, Literal

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

        self.session_id : Literal[str]  = session_id
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

        self.number_of_users = 0
        self.workload_status: Literal["running" , "completed", "initialized"] = "initialized"

        self.user_service_url = os.getenv("USER_SERVICE", "").strip()
        if not self.user_service_url or not (self.user_service_url.startswith("http://") or self.user_service_url.startswith("https://")):
            self.user_service_url = "http://127.0.0.1:8500"
        else:
            self.user_service_url = self.user_service_url

        self.blob_service_url = os.getenv("BLOB_SERVICE", "").strip()
        if not self.blob_service_url or not (self.blob_service_url.startswith("http://") or self.blob_service_url.startswith("https://")):
            self.blob_service_url = "http://127.0.0.1:13000"
        else:
            self.blob_service_url = self.blob_service_url

        self.remaining_frame_list = []
        self.first_frame = None
        self.last_frame = None
    

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



    # -------------------------
    # Utility Functions  Section
    # -------------------------
    
    async def downloadBlendFileFromBlobStorage(self, blend_file_path: str) -> str:
        """
        Download blend file from blob storage to a temporary local file.
        Returns the path to the temporary local file.
        """
        import tempfile
        import datetime
        
        try:
            # Create a temporary directory for this session
            temp_dir = f"temp_blend_files/{self.session_id}"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Generate a unique filename for the temporary blend file
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_blend_filename = f"temp_blend_{timestamp}.blend"
            temp_blend_path = os.path.join(temp_dir, temp_blend_filename)
            
            # Parse the blend file path to get bucket and key
            # Expected format: customer_id/object_id/filename.blend
            path_parts = blend_file_path.split('/')
            if len(path_parts) != 3:
                raise ValueError(f"Invalid blend file path format: {blend_file_path}")
            
            bucket = "blend-files"  # Fixed bucket for blend files
            key = blend_file_path
            
            print(f"Downloading blend file from bucket: {bucket}, key: {key}")
            
            # Download the blend file from blob storage
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.blob_service_url}/api/blob-service/retrieve-blend",
                    params={
                        "bucket": bucket,
                        "key": key
                    }
                )
                
                if response.status_code != 200:
                    raise Exception(f"Failed to download blend file. Status: {response.status_code}, Response: {response.text}")
                
                # Save the downloaded content to temporary file
                with open(temp_blend_path, "wb") as f:
                    f.write(response.content)
                
                print(f"Blend file downloaded successfully to: {temp_blend_path}")
                return temp_blend_path
                
        except Exception as e:
            print(f"Error downloading blend file: {e}")
            raise

    async def getFrameRangeFromBlendFile(self, blend_file_path: str) -> tuple[int, int]:
        """
        Get first and last frame from a blend file using Blender.
        Returns tuple of (first_frame, last_frame).
        """
        import subprocess
        
        try:
            script_path = "service_SessionSupervisorService/getFrameRange.py"
            
            print("Getting the frame range of the scene from blend file...")
            
            command = f"blender --background {blend_file_path} --python {script_path}"
            print(f"Command to get frame range: {command}")
            
            result = subprocess.run([command], capture_output=True, text=True, shell=True)
            
            print("Process of finding frame range completed!")
            
            if result.returncode != 0:
                raise Exception(f"Blender command failed with return code {result.returncode}. Error: {result.stderr}")
            
            output = result.stdout.split("\n")
            
            first_frame = None
            last_frame = None
            
            for line in output:
                if "FF:" in line:
                    first_frame = int(line.split(":")[1].strip())
                elif "LF:" in line:
                    last_frame = int(line.split(":")[1].strip())
            
            if first_frame is None or last_frame is None:
                raise Exception("Could not extract frame range from Blender output")
            
            print(f"First Frame: {first_frame}, Last Frame: {last_frame}")
            
            return first_frame, last_frame
            
        except Exception as e:
            print(f"Error getting frame range: {e}")
            raise

    async def cleanupTempBlendFile(self, temp_blend_path: str):
        """
        Clean up temporary blend file after processing.
        """
        try:
            if os.path.exists(temp_blend_path):
                os.remove(temp_blend_path)
                print(f"Temporary blend file cleaned up: {temp_blend_path}")
                
                # Also try to remove the temp directory if it's empty
                temp_dir = os.path.dirname(temp_blend_path)
                try:
                    os.rmdir(temp_dir)
                    print(f"Temporary directory cleaned up: {temp_dir}")
                except OSError:
                    # Directory not empty or other error, that's fine
                    pass
                    
        except Exception as e:
            print(f"Error cleaning up temporary blend file: {e}")

    async def getAndAssignFrameRange(self):
        """
        Download blend file from blob storage, get frame range, and assign frames to users.
        This method replaces the local file approach with blob storage approach.
        """
        temp_blend_path = None
        
        try:
            # Step 1: Download blend file from blob storage to temporary location
            print(f"Downloading blend file from blob storage: {self.blendFilePath}")
            temp_blend_path = await self.downloadBlendFileFromBlobStorage(self.blendFilePath)
            
            # Step 2: Get frame range from the temporary blend file
            print("Getting frame range from blend file...")
            first_frame, last_frame = await self.getFrameRangeFromBlendFile(temp_blend_path)
            
            # Step 3: Store the frame range in instance variables
            self.first_frame = first_frame
            self.last_frame = last_frame
            
            # Step 4: Create frame list for distribution
            self.remaining_frame_list = list(range(first_frame, last_frame + 1))
            
            print(f"Frame range determined: {first_frame} to {last_frame}")
            print(f"Total frames to render: {len(self.remaining_frame_list)}")
            
            return {
                "first_frame": first_frame,
                "last_frame": last_frame,
                "total_frames": len(self.remaining_frame_list),
                "frame_list": self.remaining_frame_list
            }
            
        except Exception as e:
            print(f"Error in getAndAssignFrameRange: {e}")
            raise
            
        finally:
            # Step 5: Clean up temporary blend file
            if temp_blend_path:
                await self.cleanupTempBlendFile(temp_blend_path)


    # -------------------------
    # Send User Message Events Section
    # -------------------------


    async def sendMessageToUser(self, user_id, payload):
        await self.http_client.post(f"{self.user_service_url}/api/user-service/user/send-msg-to-user", json={"user_id": user_id, "data": payload})

    async def sendUserStopWork(self, user_list):
        for user_id in user_list:
            payload = {
                "user_id": user_id,
                "data": {
                    "topic": "stop-work",
                }
            }
            await self.sendMessageToUser(user_id, payload)

    async def sendUserStartRendering(self, user_id, frame_list, blend_file_path=None):
        """
        Send start rendering message to user with frame list and blend file path.
        If blend_file_path is None, uses the blob storage path from self.blendFilePath.
        """
        if blend_file_path is None:
            blend_file_path = self.blendFilePath
            
        payload = {
            "user_id" : user_id,
            "data" : {
                "topic" : "start-rendering",
                "blend_file_path": blend_file_path,
                "frame_list": frame_list,
            }
        }

        await self.sendMessageToUser(user_id, payload)


    # -------------------------
    # User Management Section
    # -------------------------

    
    async def releaseUsers(self, user_id):
        self.user_list.remove(user_id)
        self.number_of_users -= 1

        await self.sendUserStopWork([user_id])

        payload = {
            "topic": "users-released",
            "session-id": self.session_id,
            "data": {
                "user_list": [user_id],
            }
        }

        await self.mq_client.publish_message("SESSION_SUPERVISOR_EXCHANGE", "SESSION_SUPERVISOR", json.dumps(payload))

    async def remove_users(self, user_list):
        for user in user_list:
            await self.releaseUsers(user)

    async def user_added(self, user_id):
        self.user_list.append(user_id)
        self.number_of_users += 1


    # -------------------------
    # Workload Management Section
    # -------------------------

    async def distributeWorkload(self):
        """
        Distribute workload among available users.
        This method should be called after getAndAssignFrameRange() to distribute frames.
        """
        if not self.remaining_frame_list or not self.user_list:
            print("No frames to distribute or no users available")
            return
        
        # Calculate frames per user
        total_frames = len(self.remaining_frame_list)
        num_users = len(self.user_list)
        frames_per_user = total_frames // num_users
        remaining_frames = total_frames % num_users
        
        print(f"Distributing {total_frames} frames among {num_users} users")
        print(f"Frames per user: {frames_per_user}, Remaining frames: {remaining_frames}")
        
        # Distribute frames to users
        frame_index = 0
        for i, user_id in enumerate(self.user_list):
            # Calculate how many frames this user gets
            user_frame_count = frames_per_user
            if i < remaining_frames:  # Distribute remaining frames to first few users
                user_frame_count += 1
            
            # Get frames for this user
            user_frames = self.remaining_frame_list[frame_index:frame_index + user_frame_count]
            frame_index += user_frame_count
            
            # Store frame mapping
            self.frameNumberMappedToUser[user_id] = user_frames
            
            # Send frames to user
            await self.sendUserStartRendering(user_id, user_frames)
            
            print(f"Assigned {len(user_frames)} frames to user {user_id}: {user_frames}")
        
        print("Workload distribution completed")


    async def start_workload(self):
        if self.customer_id is None or self.object_id is None:
            return JSONResponse(content={"message": "Customer ID or Object ID is missing"}, status_code=400)
        
        # Test the new getAndAssignFrameRange functionality
        try:
            print("Testing getAndAssignFrameRange with blob storage...")
            frame_info = await self.getAndAssignFrameRange()
            print(f"Frame range test successful: {frame_info}")
            return JSONResponse(content={
                "message": "Workload started successfully",
                "frame_info": frame_info
            }, status_code=200)
        except Exception as e:
            print(f"Error in start_workload: {e}")
            return JSONResponse(content={"message": f"Error starting workload: {str(e)}"}, status_code=500)


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



async def main():
    session_supervisor = sessionSupervisorClass(customer_id="2e4110a3-1003-4153-934a-4cc39c98d858", object_id="678f72d7-7284-4160-9c9a-03c12a8aa6ab", session_id="789")
    await session_supervisor.getAndAssignFrameRange()

    print(session_supervisor.remaining_frame_list)

if __name__ == "__main__":
    asyncio.run(main())