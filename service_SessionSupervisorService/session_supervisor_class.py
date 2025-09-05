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
import datetime

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
            self.blendFileHash = response_data.get("blendFileHash")
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
            elif payload["topic"] == "user-frame-rendered":
                # Handle frame rendered event from user service
                frame_data = payload["data"]
                user_id = frame_data["user-id"]
                frame_number = int(frame_data["frame-number"])
                image_extension = frame_data["image-extension"]
                image_binary_path = frame_data["image-binary-path"]
                
                print(f"Received frame rendered event: user={user_id}, frame={frame_number}")
                
                # Process the rendered frame
                result = await self.user_frame_rendered(
                    user_id=user_id,
                    frame_number=frame_number,
                    image_binary_path=image_binary_path,
                    image_extension=image_extension
                )
                
                print(f"Frame processing result: {result}")
                
            elif payload["topic"] == "user-rendering-completed":
                # Handle user rendering completed event
                user_id = payload["payload"]["user-id"]
                print(f"User {user_id} completed all assigned frames")
                
                # Call the new user_rendering_completed method
                result = await self.user_rendering_completed(user_id)
                print(f"User completion handling result: {result}")

            elif payload["topic"] == "user-disconnected":
                # Handle user disconnection event
                user_id = payload["payload"]["user-id"]
                print(f"User {user_id} disconnected")
                
                # Handle user disconnection and reassign frames
                await self.handle_user_disconnection(user_id)
                
            elif payload["topic"] == "new-users":
                # Handle more users event
                user_count = payload["data"]["user_count"]
                user_list = payload["data"]["user_list"]
                print(f"More users event received: {user_count}")
                
                await self.users_added(user_list)

            else:
                print("Unknown Event Type")
                print("Received Event: ", payload)

        await handleUserManagerMessages(json_message)



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
                "topic": "stop-work",
                "data": {
                }
            }
            await self.sendMessageToUser(user_id, payload)

    async def sendUserStartRendering(self, user_id, frame_list):
        """
        Send start rendering message to user with frame list and blend file path.
        If blend_file_path is None, uses the blob storage path from self.blendFilePath.
        """
            
        payload = {
            "user_id" : user_id,
            "topic": "start-rendering",
            "data" : {
                "blend_file_hash": self.blendFileHash,
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

        await self.mq_client.publish_message("USER_MANAGER_EXCHANGE", "SESSION_SUPERVISOR", json.dumps(payload))

    async def remove_users(self, user_list):
        for user in user_list:
            await self.releaseUsers(user)
        
        if self.workload_status == "running":
            if len(self.user_list) == 0:
                background_task = asyncio.create_task(self.check_and_demand_users())
            else:
                await self.distributeWorkload()

    async def users_added(self, user_list):
        for user_id in user_list:
            self.user_list.append(user_id)
            self.number_of_users += 1

        if self.workload_status == "running":
            await self.distributeWorkload()

    async def demand_users(self, user_count):
        payload = {
            "topic" : "more-users",
            "session-id" : self.session_id,
            "data" : {
                "user_count" : user_count
            }
        }

        await self.mq_client.publish_message("USER_MANAGER_EXCHANGE", "SESSION_SUPERVISOR", json.dumps(payload))

    # -------------------------
    # Workload Management Section
    # -------------------------

    async def workload_completed(self):
        await self.remove_users(self.user_list)
        print("Workload Completed")

    async def distributeWorkload(self):
        """
        Distribute workload among available users.
        This method should be called after getAndAssignFrameRange() to distribute frames.
        frameNumberMappedToUser maps frame_number -> user_id (not user_id -> frame_list)
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
            
            # Store frame mapping: frame_number -> user_id
            for frame_number in user_frames:
                self.frameNumberMappedToUser[frame_number] = user_id
            
            # Send frames to user
            await self.sendUserStartRendering(user_id, user_frames)
            
            print(f"Assigned {len(user_frames)} frames to user {user_id}: {user_frames}")
        
        print("Workload distribution completed")
        print(f"Frame mapping: {self.frameNumberMappedToUser}")

    async def user_frame_rendered(self, user_id: str, frame_number: int, image_binary_path: str, image_extension: str):
        """
        Handle when a user completes rendering a frame.
        1. Remove frame from frameNumberMappedToUser dictionary
        2. Download image from blob storage (temp bucket)
        3. Delete image from temp bucket
        4. Store image in correct location: customer_id/object_id/frame_number.png
        """
        try:
            print(f"Processing rendered frame {frame_number} from user {user_id}")
            
            # Step 1: Remove frame from mapping dictionary
            if frame_number in self.frameNumberMappedToUser:
                del self.frameNumberMappedToUser[frame_number]
                print(f"Removed frame {frame_number} from mapping dictionary")
            else:
                print(f"Warning: Frame {frame_number} not found in mapping dictionary")
            
            # Step 2: Download image from temp bucket in blob storage
            print(f"Downloading image from temp bucket: {image_binary_path}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Download from temp bucket
                download_response = await client.get(
                    f"{self.blob_service_url}/api/blob-service/retrieve-temp",
                    params={"key": image_binary_path}
                )
                
                if download_response.status_code != 200:
                    raise Exception(f"Failed to download image from temp bucket. Status: {download_response.status_code}")
                
                image_data = download_response.content
                print(f"Downloaded image data: {len(image_data)} bytes")
                
                # Step 3: Delete image from temp bucket
                print(f"Deleting image from temp bucket: {image_binary_path}")
                delete_response = await client.delete(
                    f"{self.blob_service_url}/api/blob-service/delete-temp",
                    params={"key": image_binary_path}
                )
                
                if delete_response.status_code not in [200, 204]:
                    print(f"Warning: Failed to delete temp image. Status: {delete_response.status_code}")
                else:
                    print("Successfully deleted image from temp bucket")
                
                # Step 4: Store image in correct location
                # Format: customer_id/object_id/frame_number.png
                frame_filename = f"{frame_number:03d}.{image_extension}"  # Zero-padded frame number
                final_image_path = f"{self.customer_id}/{self.object_id}/{frame_filename}"
                
                print(f"Storing image in final location: {final_image_path}")
                
                # Upload to rendered-frames bucket
                upload_response = await client.post(
                    f"{self.blob_service_url}/api/blob-service/store-image",
                    data={
                        "bucket": "rendered-frames",        # ✅ Correct: Form fields go in 'data'
                        "key": final_image_path,            # ✅ Correct: Form fields go in 'data'
                        "type": image_extension             # ✅ Correct: Form fields go in 'data'
                    },
                    files={
                        "image": (frame_filename, image_data, "application/octet-stream")  # ✅ Correct: Only file goes in 'files'
                    }
                )
                
                if upload_response.status_code != 200:
                    raise Exception(f"Failed to upload image to final location. Status: {upload_response.status_code}")
                
                print(f"Successfully stored frame {frame_number} at {final_image_path}")
                
                # Step 5: Check if all frames are completed
                remaining_frames = len(self.frameNumberMappedToUser)
                total_original_frames = len(self.remaining_frame_list) if self.remaining_frame_list else 0
                completed_frames = total_original_frames - remaining_frames
                
                print(f"Progress: {completed_frames}/{total_original_frames} frames completed")
                
                if remaining_frames == 0:
                    print("🎉 All frames have been rendered!")
                    await self.handle_all_frames_completed()
                
                return {
                    "status": "success",
                    "frame_number": frame_number,
                    "final_path": final_image_path,
                    "remaining_frames": remaining_frames,
                    "total_frames": total_original_frames
                }
                
        except Exception as e:
            print(f"Error processing rendered frame {frame_number}: {e}")
            return {
                "status": "error",
                "frame_number": frame_number,
                "error": str(e)
            }

    async def user_rendering_completed(self, user_id: str):
        """
        Handle when a user completes all their assigned frames.
        1. Check if all frames are completed
        2. If all frames are completed, invoke workload_completed method
        3. If not all frames are completed, redistribute remaining frames between available users
        """
        try:
            print(f"User {user_id} completed all assigned frames")
            
            # Step 1: Check if all frames are completed
            remaining_frames = len(self.frameNumberMappedToUser)
            total_original_frames = len(self.remaining_frame_list) if self.remaining_frame_list else 0
            completed_frames = total_original_frames - remaining_frames
            
            print(f"Progress check: {completed_frames}/{total_original_frames} frames completed")
            print(f"Remaining frames: {remaining_frames}")
            
            # Step 2: If all frames are completed, invoke workload_completed method
            if remaining_frames == 0:
                print("🎉 All frames have been rendered!")
                await self.workload_completed()
                return {
                    "status": "all_completed",
                    "message": "All frames completed, workload finished",
                    "completed_frames": completed_frames,
                    "total_frames": total_original_frames
                }
            
            # Step 3: If not all frames are completed, redistribute remaining frames
            print(f"Redistributing {remaining_frames} remaining frames among {len(self.user_list)} available users")
            
            # Get list of remaining frames
            remaining_frame_numbers = list(self.frameNumberMappedToUser.keys())
            
            # Redistribute frames among available users
            if self.user_list and remaining_frame_numbers:
                # Calculate frames per user for redistribution
                num_users = len(self.user_list)
                frames_per_user = len(remaining_frame_numbers) // num_users
                extra_frames = len(remaining_frame_numbers) % num_users
                
                print(f"Redistribution: {frames_per_user} frames per user, {extra_frames} extra frames")
                
                # Distribute frames to users
                frame_index = 0
                for i, user_id in enumerate(self.user_list):
                    # Calculate how many frames this user gets
                    user_frame_count = frames_per_user
                    if i < extra_frames:  # Distribute extra frames to first few users
                        user_frame_count += 1
                    
                    # Get frames for this user
                    user_frames = remaining_frame_numbers[frame_index:frame_index + user_frame_count]
                    frame_index += user_frame_count
                    
                    if user_frames:  # Only send if there are frames to assign
                        # Update frame mapping: frame_number -> user_id
                        for frame_number in user_frames:
                            self.frameNumberMappedToUser[frame_number] = user_id
                        
                        # Send frames to user
                        await self.sendUserStartRendering(user_id, user_frames)
                        
                        print(f"Reassigned {len(user_frames)} frames to user {user_id}: {user_frames}")
                
                print("Frame redistribution completed")
                print(f"Updated frame mapping: {self.frameNumberMappedToUser}")
                
                return {
                    "status": "redistributed",
                    "message": f"Redistributed {len(remaining_frame_numbers)} frames among {num_users} users",
                    "remaining_frames": len(remaining_frame_numbers),
                    "total_frames": total_original_frames,
                    "completed_frames": completed_frames
                }
            else:
                print("No users available for redistribution")
                return {
                    "status": "no_users",
                    "message": "No users available for frame redistribution",
                    "remaining_frames": remaining_frames,
                    "total_frames": total_original_frames
                }
                
        except Exception as e:
            print(f"Error in user_rendering_completed: {e}")
            return {
                "status": "error",
                "message": f"Error handling user completion: {str(e)}",
                "user_id": user_id
            }
   
    async def handle_all_frames_completed(self):
        """
        Handle when all frames have been rendered.
        This method can be extended to trigger video compilation, notifications, etc.
        """
        print("🎬 All frames completed! Starting post-processing...")
        
        # Update workload status
        self.workload_status = "completed"
        
        # Here you could:
        # 1. Trigger video compilation from frames
        # 2. Send completion notification to customer
        # 3. Clean up resources
        # 4. Update database with completion status
        
        # Example: Send completion message to user manager
        
    async def get_rendering_progress(self):
        """
        Get the current rendering progress.
        Returns information about completed frames, remaining frames, etc.
        """
        total_frames = len(self.remaining_frame_list) if self.remaining_frame_list else 0
        remaining_frames = len(self.frameNumberMappedToUser)
        completed_frames = total_frames - remaining_frames
        
        progress_percentage = (completed_frames / total_frames * 100) if total_frames > 0 else 0
        
        return {
            "total_frames": total_frames,
            "completed_frames": completed_frames,
            "remaining_frames": remaining_frames,
            "progress_percentage": round(progress_percentage, 2),
            "workload_status": self.workload_status,
            "active_users": len(self.user_list),
            "frame_mapping": dict(self.frameNumberMappedToUser)  # Convert to regular dict for JSON serialization
        }

    async def check_and_demand_users(self):
        while True:
            if self.number_of_users == 0:
                await self.demand_users(1)
                await asyncio.sleep(20)
            else:
                break

    async def start_workload(self):
        background_task = asyncio.create_task(self.check_and_demand_users())

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
    session_supervisor = sessionSupervisorClass(
        customer_id="336f66fb-3831-43ec-b20f-c0cb477c835a", 
        object_id="3200243b-4e5a-419a-8bcf-2f589c69ae07", 
        session_id="789"
    )
    # await session_supervisor.getAndAssignFrameRange()

    # print(session_supervisor.remaining_frame_list)

    # await session_supervisor.user_frame_rendered(user_id="123", frame_number=1, 
    # image_binary_path="2e4110a3-1003-4153-934a-4cc39c98d858/001_ccd26e11-5113-4f2a-a8a7-ba600f3e9ab8.png", image_extension="png")

if __name__ == "__main__":  
    asyncio.run(main())