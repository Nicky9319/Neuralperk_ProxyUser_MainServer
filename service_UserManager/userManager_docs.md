# Endpoint Documentations
## Endpoint: /SessionSupervisor
### Method
GET
### Description
Handles GET requests for the Session Supervisor. Currently, this endpoint does not perform any actions.
### Input Format
- **Parameters/Body Schema:** None
- **Query Params / Headers:** None
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** None
## Endpoint: /SessionSupervisor/NewSession
### Method
POST
### Description
Handles POST requests to create a new session for the Session Supervisor. It processes the incoming request data and headers, and sends a message to the supervisor.
### Input Format
- **Parameters/Body Schema:** JSON body containing session data.
- **Query Params / Headers:** Request headers.
### Output Format
- **Response Structure:** JSON response containing the result of the supervisor message handling.
- **Success/Failure Conditions:** Returns a JSON response with the status of the operation.
### Internal API/Function Calls
- **Dependencies:** `handleSupervisorMessages`
- **Data Flow:** Processes request data and headers, sends a message to the supervisor, and returns the response.
## Endpoint: /CustomerServer
### Method
GET
### Description
Handles GET requests for the Customer Server. Currently, this endpoint does not perform any actions.
### Input Format
- **Parameters/Body Schema:** None
- **Query Params / Headers:** None
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** None
## Endpoint: /CustomerServer
### Method
POST
### Description
Handles POST requests for the Customer Server. Currently, this endpoint does not perform any actions.
### Input Format
- **Parameters/Body Schema:** None
- **Query Params / Headers:** None
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** None
## Endpoint: /UserServer
### Method
GET
### Description
Handles GET requests for the User Server. Currently, this endpoint does not perform any actions.
### Input Format
- **Parameters/Body Schema:** None
- **Query Params / Headers:** None
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** None
## Endpoint: /UserServer
### Method
POST
### Description
Handles POST requests for the User Server. Currently, this endpoint does not perform any actions.
### Input Format
- **Parameters/Body Schema:** None
- **Query Params / Headers:** None
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** None
# Function Documentations
## Function: sendMessageToSessionSupervisor
### Description
Sends a message to the session supervisor via the message queue. The message format can be either JSON or bytes, depending on the headers.
### Input Format
- **Parameters:**
    - `exchangeName` (str): The name of the exchange.
    - `supervisorRoutingKey` (str): The routing key for the supervisor.
    - `messageToSend` (dict): The message to send.
    - `headers` (dict, optional): Additional headers for the message.
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** `MessageQueue.PublishMessage`
- **Data Flow:** Converts the message to JSON or bytes based on headers and publishes it to the message queue.
## Function: handleSupervisorMessages
### Description
Handles messages from the session supervisor. Processes different types of messages such as NEW_SESSION, ADDITIONAL_USERS, SEND_MESSAGE_TO_USER, USER_RELEASED, and INITIALIZE_SESSION.
### Input Format
- **Parameters:**
    - `supervisorMessage` (dict): The message from the supervisor.
    - `Headers` (dict): The headers of the message.
    - `response` (bool, optional): Whether to return a response.
### Output Format
- **Response Structure:** JSON response containing the result of the message handling.
- **Success/Failure Conditions:** Returns a JSON response with the status of the operation.
### Internal API/Function Calls
- **Dependencies:** `sendMessageToSessionSupervisor`, `MessageQueue.PublishMessage`
- **Data Flow:** Processes the supervisor message and headers, performs actions based on the message type, and returns the response if required.
## Function: callbackSupervisorMessages
### Description
Callback function for handling messages from the session supervisor. Decodes the message and passes it to `handleSupervisorMessages`.
### Input Format
- **Parameters:**
    - `message` (Message): The message from the message queue.
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** `handleSupervisorMessages`
- **Data Flow:** Decodes the message and headers, and calls `handleSupervisorMessages`.
## Function: handleCustomerServerMessages
### Description
Handles messages from the customer server. Currently, this function only prints the message type.
### Input Format
- **Parameters:**
    - `customerServerMessage` (dict): The message from the customer server.
    - `response` (bool, optional): Whether to return a response.
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Prints the message type.
## Function: callbackCustomerServerMessages
### Description
Callback function for handling messages from the customer server. Decodes the message and passes it to `handleCustomerServerMessages`.
### Input Format
- **Parameters:**
    - `message` (Message): The message from the message queue.
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** `handleCustomerServerMessages`
- **Data Flow:** Decodes the message and calls `handleCustomerServerMessages`.
## Function: handleUserServerMessages
### Description
Handles messages from the user server. Processes different types of messages such as USER_MESSAGE, NEW_USER, REMOVE_USER.
### Input Format
- **Parameters:**
    - `userServerMessage` (dict): The message from the user server.
    - `response` (bool, optional): Whether to return a response.
    - `headers` (dict, optional): Additional headers for the message.
### Output Format
- **Response Structure:** JSON response containing the result of the message handling.
- **Success/Failure Conditions:** Returns a JSON response with the status of the operation.
### Internal API/Function Calls
- **Dependencies:** `sendMessageToSessionSupervisor`, `MessageQueue.PublishMessage`
- **Data Flow:** Processes the user server message and headers, performs actions based on the message type, and returns the response if required.
## Function: callbackUserServerMessages
### Description
Callback function for handling messages from the user server. Decodes the message and passes it to `handleUserServerMessages`.
### Input Format
- **Parameters:**
    - `message` (Message): The message from the message queue.
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** `handleUserServerMessages`
- **Data Flow:** Decodes the message and headers, and calls `handleUserServerMessages`.
## Function: startService
### Description
Starts the User Manager Service. Initializes the message queue, configures API routes, and starts listening to the message queue.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** `messageQueue.InitializeConnection`, `messageQueue.AddQueueAndMapToCallback`, `messageQueue.BoundQueueToExchange`, `messageQueue.StartListeningToQueue`, `ConfigureApiRoutes`, `apiServer.run_app`
- **Data Flow:** Initializes the message queue, configures API routes, and starts the API server.
## Function: start_service
### Description
Creates an instance of `UserManagerService` and starts the service.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
- **Success/Failure Conditions:** None
### Internal API/Function Calls
- **Dependencies:** `UserManagerService.startService`
- **Data Flow:** Creates an instance of `UserManagerService` and calls `startService`.
# Classes Documentation
## Class: UserManagerService
### Description
Manages user sessions, handles messages from session supervisors, customer servers, and user servers. Provides API endpoints for managing sessions and users.
### Attributes
- `messageQueue` (MessageQueue): The message queue for communication.
- `apiServer` (HTTPServer): The API server for handling HTTP requests.
- `users` (list): List of users.
- `userToSupervisorIdMapping` (dict): Mapping of user IDs to supervisor IDs.
- `supervisorToRoutingKeyMapping` (dict): Mapping of supervisor IDs to routing keys.
### Methods
- `__init__(self, httpServerHost, httpServerPort)`: Initializes the UserManagerService with the given HTTP server host and port.
- `ConfigureApiRoutes(self)`: Configures the API routes for the service.
- `sendMessageToSessionSupervisor(self, exchangeName, supervisorRoutingKey, messageToSend, headers=None)`: Sends a message to the session supervisor.
- `handleSupervisorMessages(self, supervisorMessage, Headers, response=False)`: Handles messages from the session supervisor.
- `callbackSupervisorMessages(self, message)`: Callback function for handling messages from the session supervisor.
- `handleCustomerServerMessages(self, customerServerMessage, response=False)`: Handles messages from the customer server.
- `callbackCustomerServerMessages(self, message)`: Callback function for handling messages from the customer server.
- `handleUserServerMessages(self, userServerMessage, response=False, headers=None)`: Handles messages from the user server.
- `callbackUserServerMessages(self, message)`: Callback function for handling messages from the user server.
- `startService(self)`: Starts the User Manager Service.

