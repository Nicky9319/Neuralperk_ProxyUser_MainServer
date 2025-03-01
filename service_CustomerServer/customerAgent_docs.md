# Endpoint Documentations
# Function Documentations
## Function: CheckGenerateSessionIdIsUnique
### Method
def CheckGenerateSessionIdIsUnique(self, sessionID)
### Description
Checks if the generated session ID is unique.
### Input Format
- **Parameters/Body Schema:**
    - `sessionID` (str): The session ID to check for uniqueness.
### Output Format
- **Response Structure:**
    - Returns `True` (bool) if the session ID is unique.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** The function checks the uniqueness of the session ID.
## Function: GenerateUniqueSessionID
### Method
def GenerateUniqueSessionID(self)
### Description
Generates a unique session ID and sets the session supervisor ID and routing key.
### Input Format
- **Parameters/Body Schema:** None
### Output Format
- **Response Structure:**
    - Returns `sessionID` (str): The generated unique session ID.
### Internal API/Function Calls
- **Dependencies:** Calls `CheckGenerateSessionIdIsUnique` to ensure the session ID is unique.
- **Data Flow:** Generates a session ID, checks its uniqueness, and sets the session supervisor ID and routing key.
## Function: CheckPortFree
### Method
def CheckPortFree(self, port)
### Description
Checks if a given port is free.
### Input Format
- **Parameters/Body Schema:**
    - `port` (int): The port number to check.
### Output Format
- **Response Structure:**
    - Returns `True` (bool) if the port is free, otherwise `False`.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** The function checks if the specified port is free.
## Function: FindFreePort
### Method
def FindFreePort(self)
### Description
Finds a free port within a specified range.
### Input Format
- **Parameters/Body Schema:** None
### Output Format
- **Response Structure:**
    - Returns `portNumber` (int): The free port number found.
### Internal API/Function Calls
- **Dependencies:** Calls `CheckPortFree` to check if ports are free.
- **Data Flow:** Iterates through a range of ports to find a free one.
## Function: SpawnSessionSupervisorService
### Method
def SpawnSessionSupervisorService(self, sessionId)
### Description
Spawns a new session supervisor service on a free port.
### Input Format
- **Parameters/Body Schema:**
    - `sessionId` (str): The session ID for which the supervisor service is spawned.
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** Calls `FindFreePort` to find a free port.
- **Data Flow:** Finds a free port and spawns a new session supervisor service using `subprocess.Popen`.
## Function: InitializeSession
### Method
async def InitializeSession(self, sessionData)
### Description
Initializes a new session with the provided session data.
### Input Format
- **Parameters/Body Schema:**
    - `sessionData` (dict): The data for initializing the session.
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** Calls `GenerateUniqueSessionID`, `SpawnSessionSupervisorService`, and uses `MessageQueue` for message handling.
- **Data Flow:** Initializes the message queue, generates a unique session ID, declares exchanges and queues, and publishes the session initialization data.
## Function: HandleSessionRequests
### Method
async def HandleSessionRequests(self, customerRequest)
### Description
Handles incoming session requests from customers.
### Input Format
- **Parameters/Body Schema:**
    - `customerRequest` (dict): The customer request data.
### Output Format
- **Response Structure:** None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Placeholder function for handling session requests.
# Classes Documentation
## Class: customerAgent
### Description
Handles customer agent operations including session initialization, session supervisor service spawning, and session request handling.
### Methods
- `__init__(self)`: Initializes the customerAgent instance.
- `CheckGenerateSessionIdIsUnique(self, sessionID)`: Checks if the generated session ID is unique.
- `GenerateUniqueSessionID(self)`: Generates a unique session ID.
- `CheckPortFree(self, port)`: Checks if a given port is free.
- `FindFreePort(self)`: Finds a free port within a specified range.
- `SpawnSessionSupervisorService(self, sessionId)`: Spawns a new session supervisor service on a free port.
- `InitializeSession(self, sessionData)`: Initializes a new session with the provided session data.
- `HandleSessionRequests(self, customerRequest)`: Handles incoming session requests from customers.
