# Endpoint Documentations
## Endpoint: GET_SID
### Method
WebSocket Event
### Description
This WebSocket event is used to retrieve the session ID (SID) of the connected client.
### Input Format
- **Parameters/Body Schema:** None
- **Query Params / Headers:** None
### Output Format
- **Response Structure:** Returns the session ID (SID) of the connected client.
- **Success/Failure Conditions:** Returns the SID on success.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** The SID is directly returned to the client.
# Function Documentations
## Function: ConfigureApiRoutes
### Description
Configures the API routes for the HTTP server. Currently, this function is a placeholder and does not configure any routes.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** None
## Function: ConfigureWsMethods
### Description
Configures the WebSocket methods for handling events such as connect, disconnect, and custom events like GET_SID.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** WebSocketServer, socketio
- **Data Flow:** Sets up event handlers for WebSocket connections and custom events.
## Function: handleCommunicationInterfaceMessages
### Description
Handles messages received from the communication interface and processes them based on their type.
### Input Format
- **Parameters:**
    - **CIMessage (dict):** The message received from the communication interface.
    - **response (bool):** Flag to indicate if a response is required.
### Output Format
- **Response Structure:** Returns a response message if the response flag is set.
- **Success/Failure Conditions:** Returns a success message for known message types, otherwise logs an unknown message type.
### Internal API/Function Calls
- **Dependencies:** WebSocketServer, socketio
- **Data Flow:** Processes the message and emits events to WebSocket clients if necessary.
## Function: callbackCommunicationInterfaceMessages
### Description
Callback function for handling messages from the communication interface queue.
### Input Format
- **Parameters:**
    - **message (object):** The message object received from the queue.
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** handleCommunicationInterfaceMessages
- **Data Flow:** Decodes the message and passes it to handleCommunicationInterfaceMessages for processing.
## Function: sendMessageToUserManager
### Description
Sends a message to the User Manager via the communication interface.
### Input Format
- **Parameters:**
    - **mainMessage (dict):** The main message to be sent to the User Manager.
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** MessageQueue
- **Data Flow:** Publishes the message to the communication interface exchange.
## Function: startService
### Description
Starts the user WebSocket server service, including initializing the message queue, configuring WebSocket methods, and starting the HTTP and WebSocket servers.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** MessageQueue, WebSocketServer, HTTPServer
- **Data Flow:** Initializes connections, sets up event handlers, and starts the servers.
## Function: start_service
### Description
Entry point for starting the user WebSocket server service.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** userWsServerService
- **Data Flow:** Creates an instance of userWsServerService and starts the service.
# Classes Documentation
## Class: userWsServerService
### Description
A service class for managing WebSocket and HTTP servers, handling communication with the User Manager, and processing messages from the communication interface.
### Attributes
- **messageQueue (MessageQueue):** The message queue for communication with the User Manager.
- **apiServer (HTTPServer):** The HTTP server for handling API requests.
- **wsServer (WebSocketServer):** The WebSocket server for handling WebSocket connections and events.
- **clients (dict):** A dictionary to keep track of connected clients.
### Methods
- **__init__(self, wsServerHost, wsServerPort, httpServerHost, httpServerPort):** Initializes the service with the specified WebSocket and HTTP server hosts and ports.
- **ConfigureApiRoutes(self):** Configures the API routes for the HTTP server.
- **ConfigureWsMethods(self):** Configures the WebSocket methods for handling events.
- **handleCommunicationInterfaceMessages(self, CIMessage, response=False):** Handles messages from the communication interface.
- **callbackCommunicationInterfaceMessages(self, message):** Callback function for handling messages from the communication interface queue.
- **sendMessageToUserManager(self, mainMessage):** Sends a message to the User Manager.
- **startService(self):** Starts the user WebSocket server service.
