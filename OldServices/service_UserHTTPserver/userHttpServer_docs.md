# Endpoint Documentations
## Endpoint: getDataFromServer
### Method
GET
### Description
Fetches data from the server based on the provided buffer UUID. If the buffer UUID exists in the server's buffer messages, it returns the corresponding message. Otherwise, it returns an error message.
### Input Format
- **Query Params:**
    - `bufferUUID` (str): The UUID of the buffer message to retrieve.
### Output Format
- **Response Structure:**
    - Success: Returns the buffer message as a pickled binary stream with HTTP status code 200.
    - Failure: Returns an error message with HTTP status code 400.
### Internal API/Function Calls
- **Dependencies:** `RefineDataFromMetaData`
- **Data Flow:** Checks if the buffer UUID exists in `self.bufferMsgs`. If it does, processes the message and returns it. Otherwise, returns an error message.
## Endpoint: sendDataToServer
### Method
POST
### Description
Sends data to the server. The data can be in JSON format or as a pickled binary stream. The server processes the user message and returns a response.
### Input Format
- **Body Schema:**
    - `USER_ID` (str): The ID of the user sending the message.
    - `MAIN_DATA` (dict): The main data of the user message.
- **Headers:**
    - `content-type` (str): Specifies the format of the data (either `application/json` or `application/octet-stream`).
### Output Format
- **Response Structure:**
    - Success: Returns a JSON response indicating the message was received with HTTP status code 200.
    - Failure: Returns an error message.
### Internal API/Function Calls
- **Dependencies:** `handleUserMessage`
- **Data Flow:** Parses the request data, processes the user message, and returns the appropriate response.
## Endpoint: addBufferMsg
### Method
POST
### Description
Adds a buffer message to the server's buffer messages. This endpoint is part of the communication interface.
### Input Format
- **Body Schema:**
    - `TYPE` (str): The type of the message.
    - `DATA` (dict): The data of the message, including `BUFFER_UUID` and `BUFFER_MSG`.
### Output Format
- **Response Structure:**
    - Success: Returns a JSON response indicating the buffer message was added successfully.
    - Failure: Returns an error message.
### Internal API/Function Calls
- **Dependencies:** `handleCommunicationInterfaceMessages`
- **Data Flow:** Parses the request data, processes the communication interface message, and returns the appropriate response.
# Function Documentations
## Function: handleUserMessage
### Description
Handles user messages based on their type. Processes messages such as `FRAME_RENDERED`, `RENDER_COMPLETED`, and `TEST`.
### Input Format
- **Parameters:**
    - `userMessage` (dict): The user message containing `TYPE` and `DATA`.
    - `userID` (str): The ID of the user sending the message.
### Output Format
- **Response Structure:**
    - Success: Returns a JSON response indicating the message was received with HTTP status code 200.
    - Failure: Returns an error message.
### Internal API/Function Calls
- **Dependencies:** `sendMessageToUserManager`
- **Data Flow:** Processes the user message based on its type and sends it to the user manager if necessary.
## Function: RefineDataFromMetaData
### Description
Refines data from metadata. Processes specific metadata types to extract and return the refined data.
### Input Format
- **Parameters:**
    - `bufferMsgData` (dict): The buffer message data containing metadata.
### Output Format
- **Response Structure:**
    - Returns the refined buffer message data.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Processes the buffer message data based on its metadata type and returns the refined data.
## Function: ConfigureHTTPRoutes
### Description
Configures the HTTP routes for the HTTP server. Defines the endpoints for getting and sending data to the server.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `getDataFromServer`, `sendDataToServer`
- **Data Flow:** Defines the HTTP routes and their corresponding handlers.
## Function: ConfigureAPIRoutes
### Description
Configures the API routes for the API server. Defines the endpoints for the communication interface.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `addBufferMsg`
- **Data Flow:** Defines the API routes and their corresponding handlers.
## Function: handleCommunicationInterfaceMessages
### Description
Handles messages from the communication interface. Processes messages such as `ADD_BUFFER_MSG`.
### Input Format
- **Parameters:**
    - `CIMessage` (dict): The communication interface message containing `TYPE` and `DATA`.
    - `response` (bool): Whether to return a response message.
### Output Format
- **Response Structure:**
    - Returns a response message if `response` is True.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Processes the communication interface message based on its type and returns a response if necessary.
## Function: callbackCommunicationInterfaceMessages
### Description
Callback function for handling communication interface messages. Decodes and processes the message.
### Input Format
- **Parameters:**
    - `message` (object): The message object containing the message body.
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `handleCommunicationInterfaceMessages`
- **Data Flow:** Decodes the message body, processes the communication interface message, and handles it.
## Function: sendMessageToUserManager
### Description
Sends a message to the user manager. The message can be sent in JSON or binary format.
### Input Format
- **Parameters:**
    - `mainMessage` (dict): The main message to send.
    - `bytes` (bool): Whether to send the message in binary format.
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `messageQueue.PublishMessage`
- **Data Flow:** Prepares the message in the specified format and publishes it to the message queue.
## Function: startService
### Description
Starts the user HTTP server service. Initializes the message queue, configures routes, and starts the servers.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `messageQueue.InitializeConnection`, `messageQueue.AddQueueAndMapToCallback`, `messageQueue.BoundQueueToExchange`, `messageQueue.StartListeningToQueue`, `ConfigureAPIRoutes`, `ConfigureHTTPRoutes`, `apiServer.run_app`, `httpServer.run_app`
- **Data Flow:** Initializes the message queue, configures the API and HTTP routes, and starts the servers.
# Classes Documentation
## Class: userHttpServerService
### Description
A service class for handling user HTTP server operations. Manages message queues, HTTP and API servers, and processes user messages.
### Attributes
- `messageQueue` (MessageQueue): The message queue for communication.
- `apiServer` (HTTPServer): The API server instance.
- `httpServer` (HTTPServer): The HTTP server instance.
- `bufferMsgs` (dict): A dictionary to store buffer messages.
### Methods
- `__init__(self, httpServerHost, httpServerPort, apiServerHost, apiServerPort)`: Initializes the service with the specified server hosts and ports.
- `handleUserMessage(self, userMessage, userID)`: Handles user messages based on their type.
- `RefineDataFromMetaData(self, bufferMsgData)`: Refines data from metadata.
- `ConfigureHTTPRoutes(self)`: Configures the HTTP routes for the HTTP server.
- `ConfigureAPIRoutes(self)`: Configures the API routes for the API server.
- `handleCommunicationInterfaceMessages(self, CIMessage, response=False)`: Handles messages from the communication interface.
- `callbackCommunicationInterfaceMessages(self, message)`: Callback function for handling communication interface messages.
- `sendMessageToUserManager(self, mainMessage, bytes=False)`: Sends a message to the user manager.
- `startService(self)`: Starts the user HTTP server service.
