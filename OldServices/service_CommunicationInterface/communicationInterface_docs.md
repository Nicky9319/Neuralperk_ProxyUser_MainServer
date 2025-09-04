# Endpoint Documentations
## Endpoint: /CommunicationInterface/AddBufferMsg
### Method
POST
### Description
Adds a buffer message for a user. This endpoint is used to store a message temporarily before it is sent to the user.
### Input Format
- **Parameters/Body Schema:**
    - `messageToSend` (dict): The message to be added to the buffer. It contains:
        - `TYPE` (str): The type of the message, e.g., "ADD_BUFFER_MSG".
        - `DATA` (dict): The actual data of the message, which includes:
            - `BUFFER_UUID` (str): A unique identifier for the buffer message.
            - `BUFFER_MSG` (str): The message content.
### Output Format
- **Response Structure:**
    - HTTP 200: Buffer message added successfully.
    - HTTP 400: Bad request if the input format is incorrect.
### Internal API/Function Calls
- **Dependencies:** `sendMessageToWsServer`
- **Data Flow:** The message is first added to the buffer and then a request is sent to the WebSocket server to notify the user.
# Function Documentations
## Function: getServiceURL
### Description
Fetches the service URL for a given service name from the `ServiceURLMapping.json` file.
### Input Format
- **Parameters:**
    - `serviceName` (str): The name of the service for which the URL is required.
### Output Format
- **Response Structure:**
    - Returns the URL of the requested service as a string.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Reads the service URL mapping from a JSON file and returns the URL for the specified service.
## Function: ConfigureApiRoutes
### Description
Configures the API routes for the service. Currently, this function is a placeholder and does not perform any actions.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** None
## Function: sendMessageToUserManager
### Description
Sends a message to the User Manager service via a message queue.
### Input Format
- **Parameters:**
    - `userManagerMessage` (dict): The message to be sent to the User Manager.
    - `headers` (dict, optional): Additional headers for the message, such as data format.
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `MessageQueue.PublishMessage`
- **Data Flow:** The message is serialized (either as JSON or bytes) and published to the User Manager exchange.
## Function: SendMessageToHttpServer
### Description
Sends a message to the HTTP server via a message queue.
### Input Format
- **Parameters:**
    - `messageToSend` (dict): The message to be sent to the HTTP server.
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `MessageQueue.PublishMessage`
- **Data Flow:** The message is serialized as JSON and published to the HTTP server exchange.
## Function: sendMessageToWsServer
### Description
Sends a message to the WebSocket server via a message queue.
### Input Format
- **Parameters:**
    - `messageToSend` (dict): The message to be sent to the WebSocket server.
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `MessageQueue.PublishMessage`
- **Data Flow:** The message is serialized as JSON and published to the WebSocket server exchange.
## Function: sendMessageToUser
### Description
Sends a message to a specific user by first adding it to a buffer and then notifying the WebSocket server.
### Input Format
- **Parameters:**
    - `userId` (str): The ID of the user to whom the message is to be sent.
    - `message` (str): The message content.
### Output Format
- **Response Structure:**
    - Prints a success message if the buffer message is added and the WebSocket server is notified successfully.
### Internal API/Function Calls
- **Dependencies:** `getServiceURL`, `requests.post`, `sendMessageToWsServer`
- **Data Flow:** The message is added to a buffer via an HTTP POST request and then a notification is sent to the WebSocket server.
## Function: handleUserManagerMessages
### Description
Handles messages received from the User Manager service.
### Input Format
- **Parameters:**
    - `userManagerMessage` (dict): The message received from the User Manager.
    - `response` (bool, optional): Whether to return a response message.
### Output Format
- **Response Structure:**
    - Returns a response message if `response` is True.
### Internal API/Function Calls
- **Dependencies:** `sendMessageToUser`
- **Data Flow:** Processes the message based on its type and performs the appropriate action.
## Function: callbackUserManagerMessages
### Description
Callback function for handling messages from the User Manager queue.
### Input Format
- **Parameters:**
    - `message` (Message): The message received from the queue.
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `handleUserManagerMessages`
- **Data Flow:** Decodes the message and passes it to `handleUserManagerMessages` for processing.
## Function: handleUserHttpServerMessages
### Description
Handles messages received from the HTTP server.
### Input Format
- **Parameters:**
    - `UserHttpServerMessage` (dict): The message received from the HTTP server.
    - `response` (bool, optional): Whether to return a response message.
    - `headers` (dict, optional): Additional headers for the message.
### Output Format
- **Response Structure:**
    - Returns a response message if `response` is True.
### Internal API/Function Calls
- **Dependencies:** `sendMessageToUserManager`
- **Data Flow:** Processes the message based on its type and performs the appropriate action.
## Function: callbackUserHttpServerMessages
### Description
Callback function for handling messages from the HTTP server queue.
### Input Format
- **Parameters:**
    - `message` (Message): The message received from the queue.
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `handleUserHttpServerMessages`
- **Data Flow:** Decodes the message and passes it to `handleUserHttpServerMessages` for processing.
## Function: handleUserWsServerMessages
### Description
Handles messages received from the WebSocket server.
### Input Format
- **Parameters:**
    - `UserWsServerMessage` (dict): The message received from the WebSocket server.
    - `response` (bool, optional): Whether to return a response message.
### Output Format
- **Response Structure:
    - Returns a response message if `response` is True.
### Internal API/Function Calls
- **Dependencies:** `sendMessageToUserManager`
- **Data Flow:** Processes the message based on its type and performs the appropriate action.
## Function: callbackUserWsServerMessages
### Description
Callback function for handling messages from the WebSocket server queue.
### Input Format
- **Parameters:**
    - `message` (Message): The message received from the queue.
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `handleUserWsServerMessages`
- **Data Flow:** Decodes the message and passes it to `handleUserWsServerMessages` for processing.
## Function: startService
### Description
Starts the communication interface service by initializing the message queue, configuring API routes, and running the HTTP server.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `messageQueue.InitializeConnection`, `messageQueue.AddQueueAndMapToCallback`, `messageQueue.BoundQueueToExchange`, `messageQueue.StartListeningToQueue`, `ConfigureApiRoutes`, `apiServer.run_app`
- **Data Flow:** Initializes the message queue, sets up the necessary queues and callbacks, and starts the HTTP server.
## Function: start_service
### Description
Creates an instance of `CommunicationInterfaceService` and starts the service.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `CommunicationInterfaceService.startService`
- **Data Flow:** Instantiates the service and calls the `startService` method.
# Classes Documentation
## Class: CommunicationInterfaceService
### Description
A service class that handles communication between different components such as the User Manager, HTTP server, and WebSocket server.
### Methods
- `__init__(self, httpServerHost, httpServerPort)`: Initializes the service with the given HTTP server host and port.
- `getServiceURL(self, serviceName)`: Fetches the service URL for a given service name.
- `ConfigureApiRoutes(self)`: Configures the API routes for the service.
- `sendMessageToUserManager(self, userManagerMessage, headers=None)`: Sends a message to the User Manager service.
- `SendMessageToHttpServer(self, messageToSend)`: Sends a message to the HTTP server.
- `sendMessageToWsServer(self, messageToSend)`: Sends a message to the WebSocket server.
- `sendMessageToUser(self, userId, message)`: Sends a message to a specific user.
- `handleUserManagerMessages(self, userManagerMessage, response=False)`: Handles messages received from the User Manager service.
- `callbackUserManagerMessages(self, message)`: Callback function for handling messages from the User Manager queue.
- `handleUserHttpServerMessages(self, UserHttpServerMessage, response=False, headers=None)`: Handles messages received from the HTTP server.
- `callbackUserHttpServerMessages(self, message)`: Callback function for handling messages from the HTTP server queue.
- `handleUserWsServerMessages(self, UserWsServerMessage, response=False)`: Handles messages received from the WebSocket server.
- `callbackUserWsServerMessages(self, message)`: Callback function for handling messages from the WebSocket server queue.
- `startService(self)`: Starts the communication interface service.
