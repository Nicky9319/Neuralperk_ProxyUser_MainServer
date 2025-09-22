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
    """
    A generic RabbitMQ wrapper class that provides both producer and consumer functionality.
    
    This class manages RabbitMQ connections, exchanges, queues, and message publishing/consuming.
    It supports various exchange types and provides a robust async interface for message queuing.
    """

    def __init__(self, connection_url="amqp://guest:guest@localhost/"):
        """
        Initialize the MessageQueue instance.
        
        Args:
            connection_url (str): RabbitMQ connection URL in the format 
                                'amqp://username:password@host:port/vhost'
                                Defaults to 'amqp://guest:guest@localhost/'
        """
        self.connection_url = connection_url
        self.connection = None
        self.channel = None
        self.exchanges = {}  # store declared exchanges
        self.queues = {}     # store declared queues

    async def connect(self):
        """
        Establish a robust async connection to RabbitMQ and create a channel.
        
        This method creates a persistent connection that will automatically reconnect
        if the connection is lost. The channel is used for all subsequent operations.
        
        Raises:
            aio_pika.exceptions.AMQPException: If connection to RabbitMQ fails
        """
        self.connection = await aio_pika.connect_robust(self.connection_url)
        self.channel = await self.connection.channel()

    async def declare_exchange(self, name, exchange_type=ExchangeType.DIRECT):
        """
        Declare an exchange of the specified type.
        
        Args:
            name (str): Name of the exchange to declare
            exchange_type (ExchangeType): Type of exchange (DIRECT, FANOUT, TOPIC, HEADERS)
                                         Defaults to ExchangeType.DIRECT
        
        Returns:
            aio_pika.Exchange: The declared exchange object
        
        Raises:
            Exception: If exchange declaration fails
        """
        if name not in self.exchanges:
            exchange = await self.channel.declare_exchange(name, exchange_type, durable=True)
            self.exchanges[name] = exchange
        return self.exchanges[name]

    async def declare_queue(self, name, **kwargs):
        """
        Declare a queue with specified parameters.
        
        Args:
            name (str): Name of the queue to declare
            **kwargs: Additional queue parameters such as:
                     - durable (bool): If True, queue survives broker restarts
                     - auto_delete (bool): If True, queue is deleted when no consumers
                     - exclusive (bool): If True, queue can only be used by one connection
                     - arguments (dict): Additional queue arguments
        
        Returns:
            aio_pika.Queue: The declared queue object
        
        Raises:
            Exception: If queue declaration fails
        """
        if name not in self.queues:
            queue = await self.channel.declare_queue(name, **kwargs)
            self.queues[name] = queue
        return self.queues[name]

    async def bind_queue(self, queue_name, exchange_name, routing_key=""):
        """
        Bind a queue to an exchange with an optional routing key.
        
        Args:
            queue_name (str): Name of the queue to bind
            exchange_name (str): Name of the exchange to bind to
            routing_key (str): Routing key for message routing. Defaults to empty string
        
        Raises:
            Exception: If queue or exchange not declared before binding
        """
        queue = self.queues.get(queue_name)
        exchange = self.exchanges.get(exchange_name)

        if not queue or not exchange:
            raise Exception("Queue or Exchange not declared before binding.")

        await queue.bind(exchange, routing_key=routing_key)

    async def publish_message(self, exchange_name, routing_key, message_body, headers=None):
        """
        Publish a message to an exchange with a routing key.
        
        Args:
            exchange_name (str): Name of the exchange to publish to
            routing_key (str): Routing key for message routing
            message_body (str or bytes): Message content to publish
            headers (dict, optional): Message headers. Defaults to None
        
        Raises:
            Exception: If exchange not declared before publishing
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
        Start consuming messages from a queue.
        
        Args:
            queue_name (str): Name of the queue to consume from
            callback (callable): Async function to handle received messages.
                               Should accept a message parameter
            no_ack (bool): If True, messages are automatically acknowledged.
                          If False, manual acknowledgment is required. Defaults to False
        
        Raises:
            Exception: If queue not declared before consuming
        """
        if queue_name not in self.queues:
            raise Exception(f"Queue '{queue_name}' not declared!")

        await self.queues[queue_name].consume(callback, no_ack=no_ack)

    async def close(self):
        """
        Close the RabbitMQ connection gracefully.
        
        This method properly closes the connection and cleans up resources.
        Should be called when the MessageQueue instance is no longer needed.
        """
        await self.connection.close()


# ---------------- HTTP Server ---------------- #

class HTTP_SERVER():
    """
    HTTP server class that manages user sessions and coordinates with various microservices.
    
    This class provides a FastAPI-based HTTP server that handles user management,
    session supervision, and communication with MongoDB, Auth, and Blob services.
    It also manages message queue communication for real-time user distribution.
    """
    
    def __init__(self, httpServerHost, httpServerPort, httpServerPrivilegedIpAddress=["127.0.0.1"], data_class_instance=None):
        """
        Initialize the HTTP server instance.
        
        Args:
            httpServerHost (str): Host address to bind the server to
            httpServerPort (int): Port number to bind the server to
            httpServerPrivilegedIpAddress (list): List of privileged IP addresses for access control
            data_class_instance (Data, optional): Instance of the Data class for shared state
        """
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


        self.user_demand_queue = []

        self.activeSessions = []
        self.users = []
        print("All Users : ", self.users)
        self.idle_users = []

        self.userToSupervisorIdMapping = {} # This is Mapping from the user id to the Session supervisor ID itself
        self.supervisorToRoutingKeyMapping = {} # This is Mapping from the session supervisor Id to the routing key itself

        self.distributingUsers = False


    async def callbackUserServiceMessages(self, message):
        """
        Callback function to handle messages from the User Service.
        
        This function processes various user-related events such as frame rendering,
        rendering completion, new user connections, and user disconnections.
        It forwards relevant events to the appropriate session supervisors.
        
        Args:
            message (aio_pika.Message): The message received from the User Service queue
        
        Note:
            Currently only supports JSON format data. Other data types can be added later.
        """

        async def handleUserServiceEvent(payload):
            """
            Handle individual user service events based on topic.
            
            Args:
                payload (dict): Event payload containing:
                    - topic (str): Event type identifier (mandatory)
                    - data (dict): Event-specific data (mandatory)
            
            Supported topics:
                - user-frame-rendered: User has rendered a frame
                - user-rendering-completed: User has completed rendering
                - new-user: New user has connected
                - user-disconnected: User has disconnected
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
                user_id = data["user-id"]
                supervisor_id = self.userToSupervisorIdMapping[user_id]
                supervisor_routing_key = self.supervisorToRoutingKeyMapping[supervisor_id]

                await self.mq_client.publish_message("SESSION_SUPERVISOR_EXCHANGE", supervisor_routing_key, json.dumps(payload))
            elif topic == "user-rendering-completed":
                print("user Rendering Completed Event Received")
                user_id = data["user-id"]
                supervisor_id = self.userToSupervisorIdMapping[user_id]
                supervisor_routing_key = self.supervisorToRoutingKeyMapping[supervisor_id]

                await self.mq_client.publish_message("SESSION_SUPERVISOR_EXCHANGE", supervisor_routing_key, payload)
            elif topic == "new-user":
                print("New User Event Received")
                print("Current Connected Users: ", self.users)
                user_id = data["user_id"]
                self.users.append(user_id)
                self.idle_users.append(user_id)
                await self.distributeUsers()
            elif topic == "user-disconnected":
                print("User Disconnected Event Received")
                user_id = data["user_id"]
                payload = {
                    "topic": "user-disconnected",
                    "data": {
                        "user_id": user_id
                    }
                }


                print("Sending User Disconnected Event to Session Supervisor")
                supervisor_id = self.userToSupervisorIdMapping[user_id]
                supervisor_routing_key = self.supervisorToRoutingKeyMapping[supervisor_id]

                await self.mq_client.publish_message("SESSION_SUPERVISOR_EXCHANGE", supervisor_routing_key, json.dumps(payload))
                self.users.remove(user_id)
                if user_id in self.idle_users:
                    self.idle_users.remove(user_id)
                # Remove user from supervisor mapping when disconnected
                if user_id in self.userToSupervisorIdMapping:
                    del self.userToSupervisorIdMapping[user_id]
                await self.distributeUsers()


            else:
                print("Unknown Event Type")
                print("Received Event: ", payload)

        
        decoded_message = message.body.decode()
        json_message = json.loads(decoded_message)

        await handleUserServiceEvent(json_message)
        return
        
    async def callbackSessionSupervisorMessages(self, message):
        """
        Callback function to handle messages from Session Supervisors.
        
        This function processes session supervisor events such as user demand requests,
        user count updates, user releases, and demand removal requests.
        It manages the user distribution queue and coordinates user allocation.
        
        Args:
            message (aio_pika.Message): The message received from the Session Supervisor queue
        
        Note:
            Currently only supports JSON format data. Other data types can be added later.
        """
        print("Received Message from Session Supervisor")
        decoded_message = message.body.decode()
        json_message = json.loads(decoded_message)

        async def handleSessionSupervisorEvent(payload):
            """
            Handle individual session supervisor events based on topic.
            
            Args:
                payload (dict): Event payload containing:
                    - topic (str): Event type identifier (mandatory)
                    - supervisor-id (str): Session supervisor identifier (mandatory)
                    - data (dict): Event-specific data (mandatory)
            
            Supported topics:
                - more-users: Request for additional users
                - update-user-count: Update the number of users needed
                - users-released: Release users back to idle pool
                - remove-users-demand-completely: Remove all user demand for supervisor
            """
            topic = payload.get("topic", None)
            supervisor_id = payload.get("supervisor-id", None)
            data = payload.get("data", None)

            if topic is None or supervisor_id is None or data is None:
                print("Invalid Payload")
                print("Payload Need to contain the topic, supervisor-id and data fields. It is mandatory")
                print("Payload: ", payload)
                return

            if payload["topic"] == "more-users":
                print("More Users Event Received")
                user_count = data["user_count"]
                if supervisor_id not in [ele["session_supervisor_id"] for ele in self.user_demand_queue]:
                    self.user_demand_queue.append({
                        "user_count": user_count,
                        "session_supervisor_id": supervisor_id
                    })
                await self.distributeUsers()
            elif payload["topic"] == "update-user-count":
                print("Update User Count Event Received")
                user_count = data["user_count"]
                # Find and update existing demand for this supervisor
                for demand in self.user_demand_queue:
                    if demand["session_supervisor_id"] == supervisor_id:
                        old_count = demand["user_count"]
                        demand["user_count"] = user_count
                        print(f"Updated user count for supervisor {supervisor_id}: {old_count} -> {user_count}")
                        break
                else:
                    # If no existing demand found, create a new one
                    self.user_demand_queue.append({
                        "user_count": user_count,
                        "session_supervisor_id": supervisor_id
                    })
                    print(f"Created new demand for supervisor {supervisor_id}: {user_count} users")
                await self.distributeUsers()
            elif payload["topic"] == "users-released":
                print("Users Released Event Received")
                user_list = data["user_list"]
                for user_id in user_list:
                    self.idle_users.append(user_id)
                    # Remove user from supervisor mapping when released
                    if user_id in self.userToSupervisorIdMapping:
                        del self.userToSupervisorIdMapping[user_id]
                await self.distributeUsers()
            elif payload["topic"] == "remove-users-demand-completely":
                print("Remove Users Demand Event Received")
                supervisor_id = data["session_supervisor_id"]
                
                for demand in self.user_demand_queue:
                    if demand["session_supervisor_id"] == supervisor_id:
                        self.user_demand_queue.remove(demand)
                        print(f"Removed demand for supervisor {supervisor_id}")
                        break
            else:
                print("Unknown Event Type")
                print("Received Event: ", payload)

        await handleSessionSupervisorEvent(json_message)
        return

    async def initialization(self):
        """
        Initialize the HTTP server and message queue connections.
        
        This method sets up:
        - RabbitMQ connection and channels
        - Message exchanges (USER_MANAGER_EXCHANGE, SESSION_SUPERVISOR_EXCHANGE)
        - Message queues (USER_SERVICE, SESSION_SUPERVISOR)
        - Queue bindings and message consumers
        
        Raises:
            Exception: If message queue setup fails
        """
        await self.mq_client.connect()

        await self.mq_client.declare_exchange("USER_MANAGER_EXCHANGE", exchange_type=ExchangeType.DIRECT)

        await self.mq_client.declare_queue("USER_SERVICE", auto_delete=True)
        await self.mq_client.bind_queue("USER_SERVICE", "USER_MANAGER_EXCHANGE", routing_key="USER_SERVICE")
        await self.mq_client.consume("USER_SERVICE" , self.callbackUserServiceMessages)


        await self.mq_client.declare_queue("SESSION_SUPERVISOR", auto_delete=True)
        await self.mq_client.bind_queue("SESSION_SUPERVISOR", "USER_MANAGER_EXCHANGE", routing_key="SESSION_SUPERVISOR")
        await self.mq_client.consume("SESSION_SUPERVISOR" , self.callbackSessionSupervisorMessages)

        await self.mq_client.declare_exchange("SESSION_SUPERVISOR_EXCHANGE", exchange_type=ExchangeType.DIRECT)


    async def sendUserToSessionSupervisor(self, user_list, session_supervisor_id):
        """
        Send a list of users to a specific session supervisor.
        
        Args:
            user_list (list): List of user IDs to send to the supervisor
            session_supervisor_id (str): ID of the target session supervisor
        
        Raises:
            Exception: If session supervisor ID not found in routing mapping
        """
        try:
            if session_supervisor_id not in self.supervisorToRoutingKeyMapping:
                print(f"Error: session_supervisor_id={session_supervisor_id} not found in supervisorToRoutingKeyMapping. Cannot send users.")
                return

            print(f"Sending users {user_list} to session supervisor {session_supervisor_id}")

            payload = {
                "topic": "new-users",
                "data": {
                    "user_list": user_list,
                    "session_supervisor_id": session_supervisor_id
                }
            }



            await self.mq_client.publish_message(
                "SESSION_SUPERVISOR_EXCHANGE",
                self.supervisorToRoutingKeyMapping[session_supervisor_id],
                json.dumps(payload)
            )
        except Exception as e:
            print(f"Exception in sendUserToSessionSupervisor: {e}")


    async def distributeUsers(self):
        """
        Distribute idle users to session supervisors based on demand.
        
        This method processes the user demand queue and assigns available idle users
        to session supervisors that have requested them. It ensures that users are
        properly mapped to supervisors and handles partial fulfillment of demands.
        
        The distribution process:
        1. Checks if distribution is already in progress (prevents concurrent execution)
        2. Processes demands from the user_demand_queue
        3. Assigns idle users to supervisors based on demand
        4. Updates user-to-supervisor mappings
        5. Sends users to appropriate supervisors via message queue
        
        Note:
            This method is thread-safe and prevents concurrent execution using
            the distributingUsers flag.
        """
        print("Distributing Users is being Called !!!")

        print(self.users)
        
        if getattr(self, "distributingUsers", False):
            print("distributeUsers called while already distributing. Exiting early.")
            return

        if len(self.user_demand_queue) == 0 or len(self.idle_users) == 0:
            print(f"No distribution needed: user_demand_queue={len(self.user_demand_queue)}, idle_users={len(self.idle_users)}")
            return

        self.distributingUsers = True
        try:
            while len(self.user_demand_queue) > 0 and len(self.idle_users) > 0:
                user_demand_record = self.user_demand_queue.pop(0)
                user_count = user_demand_record["user_count"]
                session_supervisor_id = user_demand_record["session_supervisor_id"]

                print(f"Processing demand: session_supervisor_id={session_supervisor_id}, user_count={user_count}, idle_users_available={len(self.idle_users)}")

                # The following line is the source of the error in your logs:
                # Exception in distributeUsers: '07149475-6561-403d-9722-7f22141ae93d'
                # This means that session_supervisor_id is not present in self.supervisorToRoutingKeyMapping
                # So, when sendUserToSessionSupervisor is called, it tries to access a key that does not exist.
                # This can happen if the session supervisor has not registered or the mapping was not set up.

                if session_supervisor_id not in self.supervisorToRoutingKeyMapping:
                    print(f"Error: session_supervisor_id={session_supervisor_id} not found in supervisorToRoutingKeyMapping. Skipping this demand.")
                    continue

                if user_count <= len(self.idle_users):
                    users_to_send = self.idle_users[:user_count]
                    print(f"Assigning users {users_to_send} to session_supervisor_id={session_supervisor_id}")
                    
                    # Update userToSupervisorIdMapping for all users being sent
                    for user_id in users_to_send:
                        self.userToSupervisorIdMapping[user_id] = session_supervisor_id
                    
                    await self.sendUserToSessionSupervisor(users_to_send, session_supervisor_id)
                    # print(f"Idle users after sending users to session supervisor: {self.idle_users}")
                    self.idle_users = self.idle_users[user_count:]
                    # print(f"Idle users after sending users to session supervisor: {self.idle_users}")
                else:
                    print(f"Not enough idle users. Assigning all idle users {self.idle_users} to session_supervisor_id={session_supervisor_id}")
                    
                    # Update userToSupervisorIdMapping for all remaining idle users
                    for user_id in self.idle_users:
                        self.userToSupervisorIdMapping[user_id] = session_supervisor_id
                    
                    await self.sendUserToSessionSupervisor(self.idle_users, session_supervisor_id)
                    self.idle_users = []
        except Exception as e:
            print(f"Exception in distributeUsers: {e}")
        finally:
            self.distributingUsers = False
            print("Finished distributing users.")
                


    async def configure_routes(self):
        """
        Configure HTTP API routes for the FastAPI application.
        
        This method sets up all the REST API endpoints including:
        - Service health check endpoint
        - Session supervisor registration endpoint
        
        The routes handle various user management and session supervision operations.
        """

        @self.app.post("/api/user-manager/")
        async def userManagerServiceRoot(request: Request):
            """
            Root endpoint for the User Manager service.
            
            Args:
                request (Request): FastAPI request object
            
            Returns:
                JSONResponse: Service status confirmation
            """
            print("User Manager Service Root Endpoint Hit")
            return JSONResponse(content={"message": "User Manager Service is active"}, status_code=200)

        @self.app.post("/api/user-manager/session-supervisor/new-session")
        async def newSession(
            user_count: int = Form(...),
            session_supervisor_id: str = Form(...)
        ):
            """
            Register a new session supervisor and set up routing.
            
            Args:
                user_count (int): Number of users requested by the supervisor
                session_supervisor_id (str): Unique identifier for the session supervisor
            
            This endpoint:
            - Adds the supervisor to active sessions
            - Sets up routing key mapping for message queue communication
            - Enables the supervisor to receive user assignments
            """
            self.activeSessions.append(session_supervisor_id)
            self.supervisorToRoutingKeyMapping[session_supervisor_id] = f"SESSION_SUPERVISOR_{session_supervisor_id}"

    async def run_app(self):
        """
        Start the FastAPI application server.
        
        This method configures and starts the uvicorn server with the specified
        host and port settings. The server will handle HTTP requests and run
        until explicitly stopped.
        
        Raises:
            Exception: If server startup fails
        """
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()


# ---------------- Data Class ---------------- #

class Data():
    """
    Data class for managing shared application state.
    
    This class holds global data structures that need to be shared across
    different components of the user manager service.
    """
    
    def __init__(self):
        """
        Initialize the Data instance with empty data structures.
        
        Attributes:
            customerSessionsMapping (dict): Mapping of customer IDs to their session data
        """
        self.customerSessionsMapping = {}

# ---------------- Service Class ---------------- #

class Service():
    """
    Main service class that orchestrates the user manager service.
    
    This class coordinates the startup and operation of the HTTP server
    and manages the overall service lifecycle.
    """
    
    def __init__(self, httpServer = None):
        """
        Initialize the Service instance.
        
        Args:
            httpServer (HTTP_SERVER, optional): HTTP server instance to manage.
                                              Defaults to None
        """
        self.httpServer = httpServer

    async def startService(self):
        """
        Start the user manager service.
        
        This method performs the complete service startup sequence:
        1. Initialize message queue connections and routes
        2. Configure HTTP API routes
        3. Start the HTTP server
        
        Raises:
            Exception: If any step in the startup sequence fails
        """
        await self.httpServer.initialization()
        await self.httpServer.configure_routes()
        await self.httpServer.run_app()

         
async def start_service():
    """
    Main entry point for starting the user manager service.
    
    This function initializes all necessary components and starts the service:
    - Creates a Data instance for shared state management
    - Configures HTTP server settings (host, port, privileged IPs)
    - Initializes the HTTP server with the data instance
    - Creates and starts the main service
    
    The service will run indefinitely until explicitly stopped.
    
    Configuration:
        - HTTP Server Port: 7000
        - HTTP Server Host: 0.0.0.0 (all interfaces)
        - Privileged IP Addresses: ["127.0.0.1"]
    """
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
    """
    Entry point when the script is run directly.
    
    This block ensures the service starts only when the script is executed
    directly (not when imported as a module). It uses asyncio.run() to start
    the async service in the event loop.
    """
    asyncio.run(start_service())
