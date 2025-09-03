# Endpoint Documentations
## Endpoint: /requestSessionCreation
### Method
POST
### Description
Handles the session creation request for a customer. It checks if the email is already in session, validates the credentials, and initiates the session creation process.
### Input Format
- **Parameters/Body Schema:**
    - `EMAIL` (str): The email of the customer.
    - `DATA` (dict): Additional data required for session creation.
    - `PERSONA_TYPE` (str): The type of persona.
    - `PASSWORD` (str): The password of the customer.
- **Headers:**
    - `content-type` (str): The content type of the request, either 'application/json' or 'application/bytes'.
### Output Format
- **Response Structure:**
    - `MESSAGE` (str): Status message indicating the result of the session creation request.
- **Success/Failure Conditions:**
    - 200: Session creation request is accepted.
    - 400: Session is already running.
    - 401: Invalid email or password.
    - 500: Session creation failed.
### Internal API/Function Calls
- **Dependencies:** `getServiceURL`, `handleSessionCreationRequest`
- **Data Flow:** Validates credentials via `CREDENTIAL_SERVER` and processes session creation request.
## Endpoint: /initializeSession
### Method
POST
### Description
Initializes a customer session based on a pending session creation request.
### Input Format
- **Parameters/Body Schema:**
    - `EMAIL` (str): The email of the customer.
### Output Format
- **Response Structure:**
    - `MESSAGE` (str): Status message indicating the result of the session initialization.
- **Success/Failure Conditions:**
    - 200: Session initialized successfully.
    - 404: No pending session for the customer.
    - 500: Session creation failed.
### Internal API/Function Calls
- **Dependencies:** `initializeCustomerSession`
- **Data Flow:** Initializes a new customer agent session and updates session status.
## Endpoint: /handleSessionRequests
### Method
PUT
### Description
Placeholder for handling session requests. Currently not implemented.
### Input Format
- **Parameters/Body Schema:** None
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** None
## Endpoint: /serverRunning
### Method
GET
### Description
Checks if the server is running.
### Input Format
- **Parameters/Body Schema:** None
### Output Format
- **Response Structure:**
    - `MESSAGE` (str): Status message indicating the server is running.
- **Success/Failure Conditions:**
    - 200: Server is running.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** None
## Endpoint: /sessionSTATUS
### Method
GET
### Description
Checks the status of a customer session.
### Input Format
- **Query Params:**
    - `message` (str): JSON string containing `PERSONA_TYPE` and `EMAIL`.
### Output Format
- **Response Structure:**
    - `MESSAGE` (str): Status message indicating the session status.
- **Success/Failure Conditions:**
    - 200: Session status retrieved successfully.
    - 400: Invalid request.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Retrieves session status based on email and persona type.
# Function Documentations
## Function: getServiceURL
### Description
Fetches the service URL for a given service name from the `ServiceURLMapping.json` file.
### Input Format
- **Parameters:**
    - `serviceName` (str): The name of the service.
### Output Format
- **Response Structure:**
    - `str`: The URL of the requested service.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Reads the service URL mapping from a JSON file.
## Function: ConfigureHttpRoutes
### Description
Configures the HTTP routes for the customer server service.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `handleSessionCreationRequest`, `initializeCustomerSession`
- **Data Flow:** Sets up the HTTP routes and their corresponding handlers.
## Function: initializeCustomerSession
### Description
Initializes a customer session by creating a new customer agent and starting the session.
### Input Format
- **Parameters:**
    - `customerEmail` (str): The email of the customer.
### Output Format
- **Response Structure:**
    - `bool`: True if the session is initialized successfully.
### Internal API/Function Calls
- **Dependencies:** `customerAgent.InitializeSession`
- **Data Flow:** Creates a new customer agent and initializes the session with the provided email.
## Function: startService
### Description
Starts the customer server service by configuring HTTP routes and running the HTTP server.
### Input Format
- **Parameters:** None
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** `ConfigureHttpRoutes`, `HTTPServer.run_app`
- **Data Flow:** Configures HTTP routes and starts the HTTP server.
# Classes Documentation
## Class: CustomerServerService
### Description
Represents the customer server service, which handles session creation, initialization, and status checking for customers.
### Attributes
- `httpServer` (HTTPServer): The HTTP server instance.
- `sessionCreationRequests` (dict): Dictionary to store session creation requests.
- `sessionStatus` (dict): Dictionary to store session statuses.
- `customerAgentList` (dict): Dictionary to store customer agents.
- `CateringRequestLock` (threading.Lock): Lock for handling catering requests.
### Methods
- `__init__(self, httpServerHost, httpServerPort)`: Initializes the customer server service with the given host and port.
- `getServiceURL(self, serviceName)`: Fetches the service URL for a given service name.
- `ConfigureHttpRoutes(self)`: Configures the HTTP routes for the customer server service.
- `initializeCustomerSession(self, customerEmail)`: Initializes a customer session.
- `startService(self)`: Starts the customer server service.

