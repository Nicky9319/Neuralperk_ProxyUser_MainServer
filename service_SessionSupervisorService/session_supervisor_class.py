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
            queue = await self.channel.declare_queue(name, **kwargs)
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
    """
    Session Supervisor Class - Manages rendering sessions for 3D objects.
    
    This class coordinates the rendering of Blender objects by:
    - Downloading blend files from blob storage
    - Determining frame ranges to render
    - Distributing frames among available users
    - Managing user assignments and workload distribution
    - Handling frame completion and storage
    - Coordinating with User Manager for user allocation
    
    Attributes:
        customer_id (str): Unique identifier for the customer
        object_id (str): Unique identifier for the 3D object to render
        session_id (str): Unique identifier for this rendering session
        blendFilePath (str): Path to the blend file in blob storage
        blendFileHash (str): Hash of the blend file for verification
        user_list (list): List of user IDs currently assigned to this session
        frameNumberMappedToUser (dict): Maps frame numbers to assigned user IDs
        workload_status (str): Current status - "initialized", "running", or "completed"
    """
    
    def __init__(self, customer_id = None, object_id = None, session_id = None, workload_removing_callback = None):
        """
        Initialize a new Session Supervisor instance.
        
        Sets up the session supervisor to manage rendering of a specific 3D object
        for a customer. Fetches blend file information from MongoDB service and
        prepares for workload distribution.
        
        Args:
            customer_id (str): Unique identifier for the customer who owns the object
            object_id (str): Unique identifier for the 3D object to be rendered
            session_id (str): Unique identifier for this rendering session
            workload_removing_callback (callable): Function to call when workload is completed
                                                  Should accept customer_id as parameter
                                                  
        Raises:
            ValueError: If blendFilePath is not found in API response
            Exception: If API call to get blend file information fails
            
        Example:
            supervisor = sessionSupervisorClass(
                customer_id="123e4567-e89b-12d3-a456-426614174000",
                object_id="987fcdeb-51a2-43d1-b789-123456789abc", 
                session_id="session-001"
            )
        """
        self.customer_id = customer_id
        self.object_id = object_id

        self.session_id : str  = session_id
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
        
        self.total_frames = None

        self.completed = False

        self.workload_completed_callback = workload_removing_callback


    async def initialization(self):
        """
        Initialize message queue connections and set up communication channels.
        
        This method establishes the necessary RabbitMQ connections and queues
        for communication with the User Manager service. It sets up:
        - Connection to the message broker
        - Exchange for receiving messages from User Manager
        - Queue specific to this session supervisor
        - Message consumption callback for handling incoming messages
        
        The session supervisor will listen for messages on its dedicated queue
        and can send messages to the User Manager through the USER_MANAGER_EXCHANGE.
        
        Raises:
            Exception: If message queue connection or setup fails
            
        Example:
            await supervisor.initialization()
        """
        await self.mq_client.connect()

        await self.mq_client.declare_exchange("SESSION_SUPERVISOR_EXCHANGE", exchange_type=ExchangeType.DIRECT)

        await self.mq_client.declare_queue(f"SESSION_SUPERVISOR_{self.session_id}", auto_delete = True)
        await self.mq_client.bind_queue(f"SESSION_SUPERVISOR_{self.session_id}", "SESSION_SUPERVISOR_EXCHANGE", routing_key=f"SESSION_SUPERVISOR_{self.session_id}")
        await self.mq_client.consume(f"SESSION_SUPERVISOR_{self.session_id}", self.callbackUserManagerMessages)

        await self.mq_client.declare_exchange("USER_MANAGER_EXCHANGE", exchange_type=ExchangeType.DIRECT)

        
    async def callbackUserManagerMessages(self, message):
        """
        Handle incoming messages from the User Manager service.
        
        This callback function processes messages received from the User Manager
        through the message queue. It handles various types of events including:
        - New user assignments
        - User frame rendering completion
        - User disconnection events
        - User rendering completion
        
        The function decodes JSON messages and routes them to appropriate
        handler methods based on the message topic.
        
        Args:
            message (aio_pika.Message): The incoming message from User Manager
                                       Expected to contain JSON payload with:
                                       - topic: Event type identifier
                                       - data: Event-specific data
                                       - supervisor-id: Session supervisor identifier
                                       
        Supported Topics:
            - "new-users": New users assigned to this session
            - "user-frame-rendered": A user completed rendering a frame
            - "user-rendering-completed": A user completed all assigned frames
            - "user-disconnected": A user disconnected from the session
            
        Example:
            Message payload:
            {
                "topic": "new-users",
                "supervisor-id": "session-123",
                "data": {
                    "user_list": ["user-1", "user-2"],
                    "session_supervisor_id": "session-123"
                }
            }
        """

        decoded_message = message.body.decode()
        json_message = json.loads(decoded_message)

        async def handleUserManagerMessages(payload):
            """
            Internal message handler for messages coming from User Manager.

            Flow / responsibilities:
            - Receive a decoded JSON payload from the outer callback and route
                it to the appropriate handling branch based on the `topic` field.
            - Supported topics include: "new-session", "user-frame-rendered",
                "user-rendering-completed", "user-disconnected", "new-users",
                and "user-error-sending-frame".
            - For "new-session" it updates the supervisor's session identifiers.
            - For "user-frame-rendered" it extracts frame metadata and calls
                `user_frame_rendered` to process the completed frame (download,
                store, and update DB).
            - For "user-rendering-completed" it calls a helper to ensure the
                user has sent all frames, then triggers redistribution or
                completion handling.
            - For "user-disconnected" it triggers `handle_user_disconnection` to
                remove the user and redistribute their frames.
            - For "new-users" it appends new user ids and (if workload is
                running) redistributes work with `users_added`.
            - For "user-error-sending-frame" it attempts to retrieve the frame
                from the user and, if unsuccessful, re-distributes the workload.

            Error handling:
            - This function assumes the outer callback decoded the message and
                that payload is a dict with expected keys; missing or malformed
                payloads will raise and be propagated to the outer scope.

            Note:
            - This handler is declared nested so it can access `self` and the
                outer scope easily. It does not return a value; its side effects
                are updating supervisor state and sending messages/requests to
                other services.
            """
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
                user_send_all_frames = await self.check_and_retrieve_all_user_frames(user_id)
                if user_send_all_frames == True:
                    print(f"User {user_id} has sent all frames successfully.")
                    await self.user_rendering_completed(user_id)
                else:
                    return
                    
                    

            elif payload["topic"] == "user-disconnected":
                # Handle user disconnection event
                user_id = payload["data"]["user-id"]
                print(f"User {user_id} disconnected")
                
                # Handle user disconnection and reassign frames
                await self.handle_user_disconnection(user_id)
                
            elif payload["topic"] == "new-users":
                # Handle more users event

                print(f"New users event received: {payload}")

                user_list = payload["data"]["user_list"]
                
                await self.users_added(user_list)

            elif payload["topic"] == "user-error-sending-frame":
                data = payload["data"]
                
                user_id = data["user-id"]
                frameNumber = int(data["frame-number"])
                blendFileHash = data["blend-file-hash"]
                
                response = self.sendMessageToUser_withAcknowledgment(user_id, "retrieve-frame", {"frame-number": frameNumber, "blend-file-hash": blendFileHash})
                
                if response == True:
                    print(f"User Acknowledged that it has the frame with it and hence would be sending it back to the server")
                    print(f"frameNumber : {frameNumber}, userID: {user_id}")
                    return
                else:
                    print(f"User Doesnt have the Desired Frame")
                    print("FrameNumber: {frameNumber}, UserID: {user_id}")
                    await self.distributeWorkload()

            else:
                print("Unknown Event Type")
                print("Received Event: ", payload)

        await handleUserManagerMessages(json_message)



    # -------------------------
    # Status Functions  Section
    # -------------------------

    async def get_workload_status(self):
        """
        Get the current status and progress of the rendering workload.
        
        Calculates the completion status of the rendering session by comparing
        the total frames to be rendered against the remaining frames in the queue.
        This provides a real-time view of rendering progress.
        
        Returns:
            dict: Status information containing:
                - total-frames (int): Total number of frames to render
                - completed-frames (int): Number of frames already completed
                - completion-percentage (float): Percentage of work completed (0-100)
                
        Example:
            status = await supervisor.get_workload_status()
            print(f"Progress: {status['completion-percentage']:.1f}% complete")
            # Output: Progress: 45.2% complete
        """
        completed_frames = self.total_frames - len(self.remaining_frame_list) if self.total_frames is not None else 0
        print("Frames Completed: ", completed_frames)
        
        completion_percentage = (completed_frames / self.total_frames * 100) if self.total_frames else 0
        
        return {
            "total-frames" : self.total_frames,
            "completed-frames" : completed_frames,
            "completion-percentage" : completion_percentage,
        }
    


    # -------------------------
    # Utility Functions  Section
    # -------------------------
    
    async def downloadBlendFileFromBlobStorage(self, blend_file_path: str) -> str:
        """
        Download a Blender blend file from blob storage to a temporary local location.
        
        This method downloads the blend file from the blob storage service to a
        temporary local directory so it can be processed by Blender. The file
        is stored in a session-specific temporary directory to avoid conflicts.
        
        Args:
            blend_file_path (str): Path to the blend file in blob storage
                                 Expected format: "customer_id/object_id/filename.blend"
                                 
        Returns:
            str: Path to the temporary local blend file
            
        Raises:
            ValueError: If the blend file path format is invalid
            Exception: If the download from blob storage fails
            
        Example:
            temp_path = await supervisor.downloadBlendFileFromBlobStorage(
                "customer-123/object-456/model.blend"
            )
            # Returns: "temp_blend_files/session-789/temp_blend_20240115_143022.blend"
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
        Extract the frame range (start and end frames) from a Blender blend file.
        
        This method uses Blender's command-line interface to analyze the blend file
        and determine the frame range defined in the scene. It runs a Python script
        that extracts the first and last frame numbers from the scene settings.
        
        Args:
            blend_file_path (str): Path to the local blend file to analyze
            
        Returns:
            tuple[int, int]: A tuple containing (first_frame, last_frame)
                           where first_frame is the starting frame number
                           and last_frame is the ending frame number
                           
        Raises:
            Exception: If Blender command fails or frame range cannot be extracted
            
        Example:
            first, last = await supervisor.getFrameRangeFromBlendFile("/tmp/model.blend")
            print(f"Frames to render: {first} to {last}")
            # Output: Frames to render: 1 to 250
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
        Remove temporary blend file and clean up temporary directory.
        
        This method safely removes the temporary blend file that was downloaded
        for processing. It also attempts to remove the temporary directory if
        it becomes empty after file deletion.
        
        Args:
            temp_blend_path (str): Path to the temporary blend file to delete
            
        Note:
            This method is safe to call even if the file doesn't exist.
            It will not raise an exception if the file is already deleted.
            
        Example:
            await supervisor.cleanupTempBlendFile("/tmp/session-123/temp_blend.blend")
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
        Download blend file, determine frame range, and prepare frame list for distribution.
        
        This is a comprehensive method that handles the initial setup of the rendering
        workload. It performs the following steps:
        1. Downloads the blend file from blob storage to a temporary location
        2. Analyzes the blend file to determine the frame range (start/end frames)
        3. Creates a list of all frames that need to be rendered
        4. Sets up internal tracking variables for workload management
        5. Cleans up the temporary blend file
        
        This method must be called before starting the rendering workload to
        determine how many frames need to be rendered and distributed among users.
        
        Returns:
            dict: Frame range information containing:
                - first_frame (int): Starting frame number
                - last_frame (int): Ending frame number  
                - total_frames (int): Total number of frames to render
                - frame_list (list): List of all frame numbers to render
                
        Raises:
            Exception: If any step in the process fails (download, analysis, etc.)
            
        Example:
            frame_info = await supervisor.getAndAssignFrameRange()
            print(f"Will render {frame_info['total_frames']} frames from {frame_info['first_frame']} to {frame_info['last_frame']}")
        """
        temp_blend_path = None
        
        try:
            # Step 1: Download blend file from blob storage to temporary location
            print(f"Downloading blend file from blob storage: {self.blendFilePath}")
            temp_blend_path = await self.downloadBlendFileFromBlobStorage(self.blendFilePath)
            
            # Step 2: Get frame range from the temporary blend file
            print("Getting frame range from blend file...")
            first_frame, last_frame = await self.getFrameRangeFromBlendFile(temp_blend_path)

            # For testing purposes, set the last frame to 3
            # last_frame = 3

            # Step 3: Store the frame range in instance variables
            self.first_frame = first_frame
            self.last_frame = last_frame
            
            self.total_frames = last_frame - first_frame + 1
            
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


    async def sendMessageToUser(self, user_id, topic, payload):
        """
            Send a message to a specific user through the User Service.
            
            This method sends a message to a user by making an HTTP request to the
            User Service. The message contains a topic (message type) and payload
            (message data) that the user will receive and process.
            
            Args:
                user_id (str): Unique identifier of the user to send message to
                topic (str): Type of message being sent (e.g., "start-rendering", "stop-work")
                payload (dict): Message data to send to the user
                
            Example:
                await supervisor.sendMessageToUser(
                    user_id="user-123",
                    topic="start-rendering", 
                    payload={"frame_list": [1, 2, 3], "blend_file_hash": "abc123"}
                )
        """
        await self.http_client.post(f"{self.user_service_url}/api/user-service/user/send-msg-to-user", json={"user_id": user_id, "data": payload, "topic": topic})
        print(f"Message sent to user {user_id}: {payload}")

    async def sendMessageToUser_withAcknowledgment(self, user_id, topic, payload):
        """
            Sends a message to a specific user and waits for an acknowledgment.
            This asynchronous method sends a message to the user identified by `user_id` on the specified `topic` with the provided `payload`.
            The message is sent via an HTTP POST request to the user service endpoint. The method waits for the response, which should
            include an acknowledgment from the user or the service indicating successful delivery or processing.
            Args:
                user_id (str or int): The unique identifier of the user to whom the message will be sent.
                topic (str): The topic or channel under which the message should be sent.
                payload (dict): The actual message data to be delivered to the user.
            Returns:
                response: The HTTP response object returned by the user service, which may contain acknowledgment details.
            Raises:
                httpx.HTTPError: If the HTTP request fails due to network issues or server errors.
                Exception: For any other unexpected errors during the message sending process.
            Example:
                response = await sendMessageToUser_withAcknowledgment(
                    user_id="12345",
                    topic="notification",
                    payload={"title": "Welcome", "body": "Hello, user!"}
                )  
        """
        response = await self.http_client.post(f"{self.user_service_url}/api/user-service/user/send-msg-to-user-with-acknowledgment", json={"user_id": user_id, "data": payload, "topic": topic})
        return response

    async def sendUserStopWork(self, user_list):
        """
        Send stop work messages to a list of users.
        
        This method sends a "stop-work" message to all users in the provided list,
        instructing them to stop their current rendering work. This is typically
        used when releasing users from the session or when the workload is completed.
        
        Args:
            user_list (list): List of user IDs to send stop work messages to
            
        Example:
            await supervisor.sendUserStopWork(["user-1", "user-2", "user-3"])
        """
        for user_id in user_list:
            topic = "stop-work"
            payload = {
            }
            await self.sendMessageToUser(user_id,topic, payload)

    async def sendUserStartRendering(self, user_id, frame_list):
        """
        Send a start rendering message to a user with assigned frames.
        
        This method sends a "start-rendering" message to a specific user,
        providing them with the list of frames they need to render and the
        blend file hash for verification. The user will then begin rendering
        the assigned frames.
        
        Args:
            user_id (str): Unique identifier of the user to send rendering work to
            frame_list (list): List of frame numbers the user should render
            
        Example:
            await supervisor.sendUserStartRendering("user-123", [1, 2, 3, 4, 5])
        """
            
        topic = "start-rendering"
        payload = {
            "blend_file_hash": self.blendFileHash,
            "frame_list": frame_list,
        }

        await self.sendMessageToUser(user_id, topic, payload)


    # -------------------------
    # User Management Section
    # -------------------------

    async def releaseUsers(self, user_id):
        """
        Release a user from this session supervisor and notify the User Manager.
        
        This method removes a user from the current session, stops their work,
        and notifies the User Manager that the user is now available for other
        sessions. The user is removed from the internal user list and the
        user count is decremented.
        
        Args:
            user_id (str): Unique identifier of the user to release
            
        Example:
            await supervisor.releaseUsers("user-123")
        """
        print("Releasing Users from Session Supervisor : ", self.session_id)
        self.user_list.remove(user_id)
        self.number_of_users -= 1

        await self.sendUserStopWork([user_id])

        payload = {
            "topic": "users-released",
            "supervisor-id": self.session_id,
            "data": {
                "user_list": [user_id],
            }
        }

        await self.mq_client.publish_message("USER_MANAGER_EXCHANGE", "SESSION_SUPERVISOR", json.dumps(payload))

    async def remove_users(self, user_list):
        """
        Remove multiple users from this session supervisor.
        
        This method releases multiple users from the session and handles
        workload redistribution. If the workload is still running and no
        users remain, it will request more users. If users remain, it will
        redistribute the workload among them.
        
        Args:
            user_list (list): List of user IDs to remove from the session
            
        Example:
            await supervisor.remove_users(["user-1", "user-2", "user-3"])
        """
        for user in user_list:
            await self.releaseUsers(user)
        
        if self.workload_status == "running":
            if len(self.user_list) == 0:
                background_task = asyncio.create_task(self.check_and_demand_users())
            else:
                await self.distributeWorkload()

    async def users_added(self, user_list):
        """
        Add new users to this session supervisor and distribute workload if running.
        
        This method adds new users to the session and immediately distributes
        the current workload among all available users if the workload is
        currently running. This ensures new users start contributing to the
        rendering process right away.
        
        Args:
            user_list (list): List of user IDs to add to the session
            
        Example:
            await supervisor.users_added(["user-4", "user-5"])
        """
        for user_id in user_list:
            self.user_list.append(user_id)
            self.number_of_users += 1

        if self.workload_status == "running":
            await self.distributeWorkload()

    async def demand_users(self, user_count):
        """
        Request additional users from the User Manager.
        
        This method sends a request to the User Manager asking for a specific
        number of users to be assigned to this session supervisor. The User
        Manager will then attempt to allocate available users to fulfill this
        request.
        
        Args:
            user_count (int): Number of users to request from the User Manager
            
        Example:
            await supervisor.demand_users(3)  # Request 3 users
        """
        payload = {
            "topic" : "more-users",
            "supervisor-id" : self.session_id,
            "data" : {
                "user_count" : user_count
            }
        }

        print("Demanding users from Session Supervisor : ", self.session_id)
        await self.mq_client.publish_message("USER_MANAGER_EXCHANGE", "SESSION_SUPERVISOR", json.dumps(payload))

    async def fix_user_count(self, total_user_count):
        """
        Adjust the number of users to match the desired total user count.
        
        This method ensures that the session supervisor has exactly the specified
        number of users by either requesting more users or removing excess users.
        It's useful for dynamic scaling based on workload requirements or admin
        intervention to optimize resource allocation.
        
        The method performs the following actions:
        1. If more users are needed: Requests additional users from User Manager
        2. If too many users: Removes excess users (starting from the beginning of the list)
        3. If user count is correct: No action taken
        
        Args:
            total_user_count (int): The desired total number of users for this session
                                 Must be a positive integer
                                 
        Example:
            # Current session has 2 users, want 5 users total
            await supervisor.fix_user_count(5)  # Will request 3 more users
            
            # Current session has 5 users, want 2 users total  
            await supervisor.fix_user_count(2)  # Will remove 3 users
            
            # Current session has 3 users, want 3 users total
            await supervisor.fix_user_count(3)  # No action taken
        """
        print(f"[fix_user_count] Requested total_user_count: {total_user_count}, Current number_of_users: {self.number_of_users}")
        if total_user_count > self.number_of_users:
            print(f"[fix_user_count] Need to add {total_user_count - self.number_of_users} users.")
            await self.demand_users(total_user_count - self.number_of_users)
        elif total_user_count < self.number_of_users:
            num_to_remove = self.number_of_users - total_user_count
            print(f"[fix_user_count] Need to remove {num_to_remove} users: {self.user_list[:num_to_remove]}")
            await self.remove_users(self.user_list[:num_to_remove])
        else:
            print("[fix_user_count] User count is already correct. No action needed.")
            return

    # -------------------------
    # Workload Management Section
    # -------------------------

    async def workload_completed(self):
        """
        Mark the rendering workload as completed and perform cleanup.
        
        This method is called when all frames have been successfully rendered.
        It performs the following actions:
        1. Marks the workload as completed
        2. Releases all users from the session
        3. Calls the workload completion callback
        4. Logs completion status
        
        This method should be called automatically when all frames are rendered,
        but can also be called manually if needed.
        
        Example:
            await supervisor.workload_completed()
        """
        self.completed = True
        self.workload_status = "completed"
        await self.remove_users(self.user_list)
        self.workload_removing_callback(self.customer_id)
        print("Workload Completed")

    async def distributeWorkload(self):
        """
        Distribute rendering frames among available users.
        
        This method takes the remaining frames that need to be rendered and
        distributes them evenly among all available users. It calculates how
        many frames each user should get and sends start-rendering messages
        to each user with their assigned frames.
        
        The method updates the frameNumberMappedToUser dictionary to track
        which user is responsible for each frame number.
        
        Note:
            This method should be called after getAndAssignFrameRange() to
            ensure frames are available for distribution.
            
        Example:
            await supervisor.distributeWorkload()
        """

        print(self.user_list)

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
            
            print(f"Assigned {len(user_frames)} frames to user {user_id}:")
        
        print("Workload distribution completed")
        # print(f"Frame mapping: {self.frameNumberMappedToUser}")

    async def user_frame_rendered(self, user_id: str, frame_number: int, image_binary_path: str, image_extension: str):
        """
        Process a completed frame rendered by a user.
        
        This method handles the complete workflow when a user finishes rendering
        a frame. It performs the following steps:
        1. Removes the frame from the tracking dictionary
        2. Downloads the rendered image from the temporary blob storage
        3. Deletes the temporary image file
        4. Stores the image in the final location in blob storage
        5. Updates MongoDB with frame information
        6. Checks if all frames are completed
        
        Args:
            user_id (str): ID of the user who rendered the frame
            frame_number (int): Frame number that was rendered
            image_binary_path (str): Path to the image in temporary blob storage
            image_extension (str): File extension of the rendered image (e.g., "png", "jpg")
            
        Returns:
            dict: Processing result containing status, frame info, and progress
            
        Example:
            result = await supervisor.user_frame_rendered(
                user_id="user-123",
                frame_number=42,
                image_binary_path="temp/user-123/frame_42.png",
                image_extension="png"
            )
        """
        try:
            print(f"Processing rendered frame {frame_number} from user {user_id}")
            
            # Step 1: Remove frame from mapping dictionary
            if frame_number in self.frameNumberMappedToUser:
                del self.frameNumberMappedToUser[frame_number]
                print(f"Removed frame {frame_number} from mapping dictionary")
            else:
                print(f"Warning: Frame {frame_number} not found in mapping dictionary")
                
            # Step 2: Remove frame from the remaining frame list
            print("Remaining Frame List Before Removal:")
            print(self.remaining_frame_list)
            self.remaining_frame_list.remove(frame_number)
            print("Remaining Frame List After Removal:")
            print(self.remaining_frame_lsit)
            
            # Step 3: Download image from temp bucket in blob storage
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
                
                # Step 5: Store frame information in MongoDB
                print(f"Storing frame {frame_number} information in MongoDB")
                
                mongo_payload = {
                    "objectId": self.object_id,
                    "customerId": self.customer_id,
                    "frameNumber": frame_number,
                    "imageFilePath": final_image_path
                }

                print("Mongo Payload:")
                print(mongo_payload)
                
                mongo_response = await client.post(
                    f"{self.mongodb_service_url}/api/mongodb-service/blender-objects/add-rendered-image",
                    json=mongo_payload
                )

                print("Mongo Response:")
                print(mongo_response.status_code)
                
                if mongo_response.status_code != 200:
                    print(f"Warning: Failed to store frame {frame_number} in MongoDB. Status: {mongo_response.status_code}, Response: {mongo_response.text}")
                else:
                    print(f"Successfully stored frame {frame_number} information in MongoDB")
                
                # Step 6: Check if all frames are completed
                remaining_frames = len(self.frameNumberMappedToUser)
                total_original_frames = len(self.remaining_frame_list) if self.remaining_frame_list else 0
                completed_frames = total_original_frames - remaining_frames
                
                print(f"Progress: {completed_frames}/{total_original_frames} frames completed")
                
                if remaining_frames == 0:
                    print("🎉 All frames have been rendered!")
                    await self.workload_completed()
                
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

    async def check_and_retrieve_all_user_frames(self, user_id: str):
        """
        Ensure a user has returned all frames they were assigned.

        Flow:
        - Inspect `frameNumberMappedToUser` to find any frames still mapped to
            the given `user_id`.
        - If there are no remaining frames for that user, return True
            indicating the user has sent all frames.
        - If there are remaining frames, send a "retrieve-frames-from-frame-list"
            message to the user with the list of missing frame numbers and
            return False to indicate there is outstanding work to be returned.

        Return value:
        - True: User has no remaining frames (safe to treat as completed).
        - False: User still has frames and a retrieval request was sent.

        Error handling:
        - Any exception is caught, logged, and False is returned so calling
            code treats the user as not-ready/complete.
        """
        try:
                remaining_user_frames = [frame for frame, uid in self.frameNumberMappedToUser.items() if uid == user_id]
                if len(remaining_user_frames) == 0:
                        return True
                else:
                        await self.sendMessageToUser(
                                user_id,
                                "retrieve-frames-from-frame-list",
                                {"blend_file_hash": self.blendFileHash, "frame_list": remaining_user_frames}
                        )
                        return False
        except Exception as e:
                print(f"Error in check_and_retrieve_all_user_frames for user {user_id}: {e}")
                return False

    async def user_rendering_completed(self, user_id: str):
        """
        Handle when a user completes all their assigned frames.
        
        This method is called when a user finishes rendering all frames that were
        assigned to them. It performs the following actions:
        1. Checks if all frames in the entire workload are completed
        2. If not all frames are completed, redistributes remaining frames among available users
        3. Ensures optimal workload distribution for maximum efficiency
        
        Note:
            The actual workload completion (when all frames are done) is handled
            in the user_frame_rendered method, not here.
            
        Args:
            user_id (str): ID of the user who completed their assigned frames
            
        Returns:
            dict: Result containing status and redistribution information
            
        Example:
            result = await supervisor.user_rendering_completed("user-123")
        """
        try:
            print(f"User {user_id} completed all assigned frames")
            
            # Step 1: Check if all frames are completed
            remaining_frames = len(self.frameNumberMappedToUser)
            total_original_frames = len(self.remaining_frame_list) if self.remaining_frame_list else 0
            completed_frames = total_original_frames - remaining_frames
            
            print(f"Progress check: {completed_frames}/{total_original_frames} frames completed")
            print(f"Remaining frames: {remaining_frames}")
            
            # Step 2: If all frames are completed, return success (workflow completion handled elsewhere)
            if remaining_frames == 0:
                print("🎉 All frames have been rendered!")
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

    async def handle_user_disconnection(self, user_id: str):
        """
        Handle when a user disconnects from the session.
        
        This method is called when a user unexpectedly disconnects during
        the rendering process. It removes the user from the session and
        redistributes their assigned frames among the remaining users.
        
        Args:
            user_id (str): ID of the user who disconnected
            
        Example:
            await supervisor.handle_user_disconnection("user-123")
        """
        try:
            if user_id in self.user_list:
                self.user_list.remove(user_id)
                self.number_of_users -= 1
                print(f"[handle_user_disconnection] User {user_id} disconnected and removed from user_list. Number of users now: {self.number_of_users}")
            else:
                print(f"[handle_user_disconnection] Warning: User {user_id} not found in user_list during disconnection handling.")
            
            if self.number_of_users == 0:
                background_task = asyncio.create_task(self.check_and_demand_users())
            else:
                await self.distributeWorkload()
        except Exception as e:
            print(f"[handle_user_disconnection] Error handling user disconnection for user {user_id}: {e}")

        
    async def get_rendering_progress(self):
        """
        Get detailed information about the current rendering progress.
        
        This method provides comprehensive information about the rendering
        session including completion status, active users, and frame mapping.
        Useful for monitoring and debugging the rendering process.
        
        Returns:
            dict: Progress information containing:
                - total_frames (int): Total number of frames to render
                - completed_frames (int): Number of frames completed
                - remaining_frames (int): Number of frames still to render
                - progress_percentage (float): Completion percentage (0-100)
                - workload_status (str): Current workload status
                - active_users (int): Number of users currently active
                - frame_mapping (dict): Mapping of frame numbers to user IDs
                
        Example:
            progress = await supervisor.get_rendering_progress()
            print(f"Progress: {progress['progress_percentage']:.1f}%")
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
        """
        Check if users are needed and request them from the User Manager.
        
        This method checks if the session has any users available. If no users
        are available and the workload is running, it requests additional users
        from the User Manager to continue the rendering process.
        
        Example:
            await supervisor.check_and_demand_users()
        """
        print("Checking and Demanding for more Users")
        print("Current Time when requesting users: ", datetime.datetime.now())
        if self.number_of_users == 0:
            await self.demand_users(1)
        else:
            return

    async def start_workload(self):
        """
        Start the rendering workload for this session.
        
        This method initiates the rendering process by:
        1. Checking if the workload is already completed
        2. Setting the workload status to "running"
        3. Getting the frame range and preparing frames for distribution
        4. Starting a background task to check for and request users
        
        This method should be called to begin the rendering process after
        the session supervisor has been initialized.
        
        Example:
            await supervisor.start_workload()
        """
        if self.completed:
            return
        
        self.workload_status = "running"
        await self.getAndAssignFrameRange()
        background_task = asyncio.create_task(self.check_and_demand_users())

    def __del__(self):
        """
        Destructor - handles cleanup when object is garbage collected.
        
        This is a fallback cleanup mechanism that runs when the object is
        being garbage collected. It attempts to perform async cleanup
        operations, but this is not guaranteed to work properly in all
        scenarios.
        
        Note:
            This is a fallback mechanism. Prefer calling cleanup() explicitly
            when you know the session supervisor is no longer needed.
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
        """
        Internal async cleanup method that performs resource cleanup.
        
        This method handles the actual cleanup operations including:
        1. Sending stop work messages to all users
        2. Releasing users back to the User Manager
        3. Removing user demands from the User Manager
        4. Closing message queue connections
        
        This method is called by both the destructor and the explicit cleanup method.
        """
        try:

            # Send stop work message to users
            print("Sending stop work message to users")
            await self.sendUserStopWork(self.user_list)
            
            payload = {
                "topic": "users-released",
                "supervisor-id": self.session_id,
                "data": {
                    "user_list": self.user_list,
                }
            }
            
            # Convert payload to JSON string for message queue
            message_body = json.dumps(payload)
            

            # Send users released message to user manager
            await self.mq_client.publish_message("USER_MANAGER_EXCHANGE", "SESSION_SUPERVISOR", message_body)

            payload = {
                "topic": "remove-users-demand-completely",
                "session-supervisor-id": self.session_id,
                "data": {
                }
            }

            message_body = json.dumps(payload)
            await self.mq_client.publish_message("USER_MANAGER_EXCHANGE", "SESSION_SUPERVISOR", message_body)
            
            # Close the message queue connection
            if self.mq_client.connection:
                await self.mq_client.close()
                
        except Exception as e:
            print(f"Error during async cleanup: {e}")
    
    async def cleanup(self):
        """
        Explicit cleanup method for proper resource management.
        
        This is the preferred way to clean up resources when the session supervisor
        is no longer needed. It performs all necessary cleanup operations including
        releasing users, closing connections, and notifying other services.
        
        This method should be called explicitly when you know the session supervisor
        is no longer needed, rather than relying on the destructor.
        
        Example:
            await supervisor.cleanup()
        """
        await self._async_cleanup()



# async def main():
#     session_supervisor = sessionSupervisorClass(
#         customer_id="336f66fb-3831-43ec-b20f-c0cb477c835a", 
#         object_id="3200243b-4e5a-419a-8bcf-2f589c69ae07", 
#         session_id="789"
#     )
#     # await session_supervisor.getAndAssignFrameRange()

#     # print(session_supervisor.remaining_frame_list)

#     # await session_supervisor.user_frame_rendered(user_id="123", frame_number=1, 
#     # image_binary_path="2e4110a3-1003-4153-934a-4cc39c98d858/001_ccd26e11-5113-4f2a-a8a7-ba600f3e9ab8.png", image_extension="png")

# if __name__ == "__main__":  
    # asyncio.run(main())