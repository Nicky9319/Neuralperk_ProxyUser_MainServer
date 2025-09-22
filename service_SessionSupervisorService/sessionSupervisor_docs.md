# Session Supervisor Service Documentation

## Overview

The Session Supervisor Service is a FastAPI-based microservice that manages 3D rendering sessions for Blender objects. It coordinates with multiple services including User Manager, MongoDB, and Blob Storage to distribute rendering workloads across available users and track progress.

## Table of Contents

1. [API Endpoints](#api-endpoints)
2. [Session Class Documentation](#session-class-documentation)
3. [Session Supervisor Class Documentation](#session-supervisor-class-documentation)
4. [Service Classes Documentation](#service-classes-documentation)
5. [Message Queue Integration](#message-queue-integration)
6. [Error Handling](#error-handling)

---

## API Endpoints

### Service Health Check

#### `POST /api/session-supervisor-service/`
**Description:** Service health check endpoint to verify the service is running and responsive.

**Request:**
- Method: POST
- Headers: None required
- Body: None required

**Response:**
```json
{
    "message": "Session Supervisor Service is active"
}
```

**Status Codes:**
- `200`: Service is active and responding

---

### Workload Management

#### `POST /api/session-supervisor-service/start-workload`
**Description:** Start a new rendering workload for a customer's 3D object.

**Request:**
- Method: POST
- Content-Type: `application/x-www-form-urlencoded`
- Body:
  - `customer_id` (string): Unique identifier for the customer
  - `object_id` (string): Unique identifier for the 3D object to render

**Response (Success):**
```json
{
    "message": "Workload started"
}
```

**Response (Error - Already Running):**
```json
{
    "message": "One workload already running. Your Access Plan doesnt allow to run another workload"
}
```

**Response (Error - Internal Server Error):**
```json
{
    "message": "Internal server error",
    "details": "Error details here"
}
```

**Status Codes:**
- `200`: Workload started successfully
- `400`: Customer already has an active workload
- `500`: Internal server error during workload creation

**Example Request:**
```bash
curl -X POST "http://localhost:7500/api/session-supervisor-service/start-workload" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "customer_id=customer-123&object_id=object-456"
```

---

#### `POST /api/session-supervisor-service/stop-and-delete-workload`
**Description:** Stop and delete an active rendering workload for a customer.

**Request:**
- Method: POST
- Content-Type: `application/x-www-form-urlencoded`
- Body:
  - `customer_id` (string): Unique identifier for the customer

**Response (Success):**
```json
{
    "message": "Workload stopped and deleted"
}
```

**Response (Error):**
```json
{
    "message": "Failed to stop and delete workload"
}
```

**Status Codes:**
- `200`: Workload stopped and deleted successfully
- `404`: No active workload found for customer
- `500`: Error during workload termination

**Example Request:**
```bash
curl -X POST "http://localhost:7500/api/session-supervisor-service/stop-and-delete-workload" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "customer_id=customer-123"
```

---

### Status and Progress Monitoring

#### `GET /api/session-supervisor-service/get-workload-status`
**Description:** Get the current status of a customer's rendering workload.

**Request:**
- Method: GET
- Query Parameters:
  - `customer_id` (string): Unique identifier for the customer

**Response:**
```json
{
    "message": "Workload status",
    "status": {
        "workload_status": "running",
        "total_frames": 250,
        "completed_frames": 125,
        "completion_percentage": 50.0
    }
}
```

**Status Codes:**
- `200`: Status retrieved successfully
- `404`: No active workload found for customer

**Example Request:**
```bash
curl "http://localhost:7500/api/session-supervisor-service/get-workload-status?customer_id=customer-123"
```

---

#### `GET /api/session-supervisor-service/get-workload-progress`
**Description:** Get detailed progress information for a customer's rendering workload.

**Request:**
- Method: GET
- Query Parameters:
  - `customer_id` (string): Unique identifier for the customer

**Response:**
```json
{
    "total_frames": 250,
    "completed_frames": 125,
    "remaining_frames": 125,
    "progress_percentage": 50.0,
    "workload_status": "running",
    "active_users": 3,
    "frame_mapping": {
        "1": "user-123",
        "2": "user-123",
        "3": "user-456"
    }
}
```

**Status Codes:**
- `200`: Progress information retrieved successfully
- `404`: No active workload found for customer

**Example Request:**
```bash
curl "http://localhost:7500/api/session-supervisor-service/get-workload-progress?customer_id=customer-123"
```

---

### Admin Panel Controls

#### `GET /api/session-supervisor-service/get-user-count/{customer_id}`
**Description:** Get the number of users assigned to a session supervisor.

**Request:**
- Method: GET
- Path Parameters:
  - `customer_id` (string): Unique identifier for the customer

**Response (Success):**
```json
{
    "user_count": 3,
    "session_id": "session-123"
}
```

**Response (Error):**
```json
{
    "message": "No active session for customer_id: customer-123"
}
```

**Status Codes:**
- `200`: User count retrieved successfully
- `404`: No active session found for customer
- `500`: Error retrieving user count

**Example Request:**
```bash
curl "http://localhost:7500/api/session-supervisor-service/get-user-count/customer-123"
```

---

#### `POST /api/session-supervisor-service/set-user-count/{customer_id}/{user_count}`
**Description:** Set the number of users assigned to a session supervisor.

**Request:**
- Method: POST
- Path Parameters:
  - `customer_id` (string): Unique identifier for the customer
  - `user_count` (integer): Desired number of users

**Response (Success):**
```json
{
    "message": "User count updated successfully",
    "new_user_count": 5
}
```

**Response (Error):**
```json
{
    "message": "No active session for customer_id: customer-123"
}
```

**Status Codes:**
- `200`: User count updated successfully
- `404`: No active session found for customer
- `500`: Error setting user count

**Example Request:**
```bash
curl -X POST "http://localhost:7500/api/session-supervisor-service/set-user-count/customer-123/5"
```

---

## Session Class Documentation

### Overview
The `sessionClass` acts as a wrapper around the `sessionSupervisorClass`, providing a simplified interface for session management.

### Key Methods

#### `start_workload()`
**Description:** Initiates the rendering workload for the session.

**Returns:** HTTP response from the session supervisor

**Workflow:**
1. Creates a new session supervisor instance
2. Initializes the session supervisor
3. Starts the workload
4. Returns the response

#### `get_session_status()`
**Description:** Retrieves the current status of the rendering session.

**Returns:** Dictionary containing session status information

#### `get_session_progress()`
**Description:** Gets detailed progress information for the session.

**Returns:** Dictionary containing progress details

#### `stop_and_delete_workload(customer_id)`
**Description:** Stops and cleans up the rendering workload.

**Parameters:**
- `customer_id` (string): Customer identifier for cleanup

**Returns:** HTTP response indicating success or failure

---

## Session Supervisor Class Documentation

### Overview
The `sessionSupervisorClass` is the core class that manages individual rendering sessions. It handles frame distribution, user management, and communication with external services.

### Key Attributes

- `customer_id` (string): Unique identifier for the customer
- `object_id` (string): Unique identifier for the 3D object
- `session_id` (string): Unique identifier for the rendering session
- `blendFilePath` (string): Path to the blend file in blob storage
- `blendFileHash` (string): Hash of the blend file for verification
- `user_list` (list): List of user IDs currently assigned to the session
- `frameNumberMappedToUser` (dict): Maps frame numbers to assigned user IDs
- `workload_status` (string): Current status - "initialized", "running", or "completed"

### Core Methods

#### Initialization and Setup

##### `__init__(customer_id, object_id, session_id, workload_removing_callback)`
**Description:** Initialize a new Session Supervisor instance.

**Parameters:**
- `customer_id` (string): Unique identifier for the customer
- `object_id` (string): Unique identifier for the 3D object
- `session_id` (string): Unique identifier for the session
- `workload_removing_callback` (callable): Function to call when workload is completed

**Workflow:**
1. Fetches blend file information from MongoDB service
2. Sets up service URLs and HTTP clients
3. Initializes tracking variables

##### `initialization()`
**Description:** Initialize message queue connections and communication channels.

**Workflow:**
1. Establishes RabbitMQ connections
2. Sets up exchanges and queues
3. Configures message consumption callbacks

#### Message Handling

##### `callbackUserManagerMessages(message)`
**Description:** Handle incoming messages from the User Manager service.

**Supported Topics:**
- `"new-users"`: New users assigned to the session
- `"user-frame-rendered"`: A user completed rendering a frame
- `"user-rendering-completed"`: A user completed all assigned frames
- `"user-disconnected"`: A user disconnected from the session

#### Status and Utility Functions

##### `get_workload_status()`
**Description:** Get the current status and progress of the rendering workload.

**Returns:**
```json
{
    "total-frames": 250,
    "completed-frames": 125,
    "completion-percentage": 50.0
}
```

##### `downloadBlendFileFromBlobStorage(blend_file_path)`
**Description:** Download a Blender blend file from blob storage to a temporary local location.

**Parameters:**
- `blend_file_path` (string): Path to the blend file in blob storage

**Returns:** Path to the temporary local blend file

##### `getFrameRangeFromBlendFile(blend_file_path)`
**Description:** Extract the frame range (start and end frames) from a Blender blend file.

**Parameters:**
- `blend_file_path` (string): Path to the local blend file

**Returns:** Tuple of (first_frame, last_frame)

##### `getAndAssignFrameRange()`
**Description:** Download blend file, determine frame range, and prepare frame list for distribution.

**Returns:**
```json
{
    "first_frame": 1,
    "last_frame": 250,
    "total_frames": 250,
    "frame_list": [1, 2, 3, ..., 250]
}
```

#### User Management

##### `sendMessageToUser(user_id, topic, payload)`
**Description:** Send a message to a specific user through the User Service.

**Parameters:**
- `user_id` (string): Unique identifier of the user
- `topic` (string): Type of message being sent
- `payload` (dict): Message data to send

##### `sendUserStopWork(user_list)`
**Description:** Send stop work messages to a list of users.

**Parameters:**
- `user_list` (list): List of user IDs to send stop work messages to

##### `sendUserStartRendering(user_id, frame_list)`
**Description:** Send a start rendering message to a user with assigned frames.

**Parameters:**
- `user_id` (string): Unique identifier of the user
- `frame_list` (list): List of frame numbers the user should render

##### `releaseUsers(user_id)`
**Description:** Release a user from this session supervisor and notify the User Manager.

**Parameters:**
- `user_id` (string): Unique identifier of the user to release

##### `remove_users(user_list)`
**Description:** Remove multiple users from this session supervisor.

**Parameters:**
- `user_list` (list): List of user IDs to remove from the session

##### `users_added(user_list)`
**Description:** Add new users to this session supervisor and distribute workload if running.

**Parameters:**
- `user_list` (list): List of user IDs to add to the session

##### `demand_users(user_count)`
**Description:** Request additional users from the User Manager.

**Parameters:**
- `user_count` (integer): Number of users to request

##### `fix_user_count(total_user_count)`
**Description:** Adjust the number of users to match the desired total user count.

**Parameters:**
- `total_user_count` (integer): The desired total number of users

**Workflow:**
1. If more users needed: Requests additional users
2. If too many users: Removes excess users
3. If correct count: No action taken

#### Workload Management

##### `workload_completed()`
**Description:** Mark the rendering workload as completed and perform cleanup.

**Workflow:**
1. Marks workload as completed
2. Releases all users
3. Calls completion callback
4. Logs completion status

##### `distributeWorkload()`
**Description:** Distribute rendering frames among available users.

**Workflow:**
1. Calculates frames per user
2. Distributes frames evenly
3. Updates frame mapping
4. Sends start-rendering messages

##### `user_frame_rendered(user_id, frame_number, image_binary_path, image_extension)`
**Description:** Process a completed frame rendered by a user.

**Parameters:**
- `user_id` (string): ID of the user who rendered the frame
- `frame_number` (integer): Frame number that was rendered
- `image_binary_path` (string): Path to the image in temporary blob storage
- `image_extension` (string): File extension of the rendered image

**Workflow:**
1. Removes frame from tracking dictionary
2. Downloads image from temporary blob storage
3. Deletes temporary image file
4. Stores image in final location
5. Updates MongoDB with frame information
6. Checks if all frames are completed

##### `user_rendering_completed(user_id)`
**Description:** Handle when a user completes all their assigned frames.

**Parameters:**
- `user_id` (string): ID of the user who completed their assigned frames

**Workflow:**
1. Checks if all frames are completed
2. If not completed: Redistributes remaining frames
3. Ensures optimal workload distribution

##### `handle_user_disconnection(user_id)`
**Description:** Handle when a user disconnects from the session.

**Parameters:**
- `user_id` (string): ID of the user who disconnected

##### `get_rendering_progress()`
**Description:** Get detailed information about the current rendering progress.

**Returns:**
```json
{
    "total_frames": 250,
    "completed_frames": 125,
    "remaining_frames": 125,
    "progress_percentage": 50.0,
    "workload_status": "running",
    "active_users": 3,
    "frame_mapping": {
        "1": "user-123",
        "2": "user-123",
        "3": "user-456"
    }
}
```

##### `check_and_demand_users()`
**Description:** Check if users are needed and request them from the User Manager.

##### `start_workload()`
**Description:** Start the rendering workload for this session.

**Workflow:**
1. Checks if workload is already completed
2. Sets workload status to "running"
3. Gets frame range and prepares frames
4. Starts background task to check for users

#### Cleanup and Lifecycle

##### `cleanup()`
**Description:** Explicit cleanup method for proper resource management.

**Workflow:**
1. Sends stop work messages to users
2. Releases users back to User Manager
3. Removes user demands
4. Closes message queue connections

##### `__del__()`
**Description:** Destructor - handles cleanup when object is garbage collected.

**Note:** This is a fallback mechanism. Prefer calling `cleanup()` explicitly.

---

## Service Classes Documentation

### HTTP_SERVER Class

#### Overview
Manages the FastAPI web server that provides REST API endpoints for controlling and monitoring rendering sessions.

#### Key Attributes
- `app` (FastAPI): The FastAPI application instance
- `host` (string): Server host address
- `port` (integer): Server port number
- `data_class` (Data): Reference to the data management class
- `mongodb_service_url` (string): URL for MongoDB service
- `auth_service_url` (string): URL for authentication service
- `blob_service_url` (string): URL for blob storage service
- `http_client` (httpx.AsyncClient): HTTP client for service communication

#### Key Methods

##### `__init__(httpServerHost, httpServerPort, httpServerPrivilegedIpAddress, data_class_instance)`
**Description:** Initialize the HTTP Server for Session Supervisor Service.

**Parameters:**
- `httpServerHost` (string): Host address for the HTTP server
- `httpServerPort` (integer): Port number for the HTTP server
- `httpServerPrivilegedIpAddress` (list): List of privileged IP addresses
- `data_class_instance` (Data): Instance of the Data class for session management

##### `workload_removing_callback(customer_id)`
**Description:** Callback function to remove completed workload sessions.

**Parameters:**
- `customer_id` (string): Unique identifier of the customer

##### `configure_routes()`
**Description:** Configure all API routes and endpoints for the Session Supervisor Service.

##### `run_app()`
**Description:** Start the FastAPI application server.

### Data Class

#### Overview
Manages the in-memory storage of active rendering sessions.

#### Key Attributes
- `customerSessionsMapping` (dict): Dictionary mapping customer IDs to their active session supervisor instances

#### Key Methods

##### `__init__()`
**Description:** Initialize the Data class with empty session mapping.

### Service Class

#### Overview
Main service class that orchestrates the Session Supervisor Service.

#### Key Attributes
- `httpServer` (HTTP_SERVER): Instance of the HTTP server class

#### Key Methods

##### `__init__(httpServer)`
**Description:** Initialize the Service with an HTTP server instance.

##### `startService()`
**Description:** Start the Session Supervisor Service.

---

## Message Queue Integration

### Exchanges
- `USER_MANAGER_EXCHANGE`: For communication with User Manager service
- `SESSION_SUPERVISOR_EXCHANGE`: For receiving messages from User Manager

### Message Topics

#### From User Manager to Session Supervisor
- `"new-users"`: New users assigned to the session
- `"user-frame-rendered"`: A user completed rendering a frame
- `"user-rendering-completed"`: A user completed all assigned frames
- `"user-disconnected"`: A user disconnected from the session

#### From Session Supervisor to User Manager
- `"more-users"`: Request for additional users
- `"update-user-count"`: Update existing user count request
- `"users-released"`: Users released back to User Manager
- `"remove-users-demand-completely"`: Remove all user demands

### Message Format
```json
{
    "topic": "message_topic",
    "supervisor-id": "session_supervisor_id",
    "data": {
        "key": "value"
    }
}
```

---

## Error Handling

### Common Error Scenarios

#### Service Unavailable
- **Cause:** External service (MongoDB, Blob Storage, User Manager) is not responding
- **Response:** HTTP 500 with error details
- **Recovery:** Retry mechanism and fallback to default configurations

#### Invalid Parameters
- **Cause:** Missing or invalid customer_id, object_id, or user_count
- **Response:** HTTP 400 with validation error message
- **Recovery:** Client should provide valid parameters

#### Session Not Found
- **Cause:** Requesting status/progress for non-existent session
- **Response:** HTTP 404 with "No active session" message
- **Recovery:** Start a new workload first

#### Concurrent Workload Limit
- **Cause:** Customer already has an active workload
- **Response:** HTTP 400 with "One workload already running" message
- **Recovery:** Stop existing workload before starting new one

### Error Response Format
```json
{
    "message": "Error description",
    "details": "Additional error details (optional)"
}
```

---

## Configuration

### Environment Variables
- `MONGODB_SERVICE`: URL for MongoDB service (default: http://127.0.0.1:12000)
- `AUTH_SERVICE`: URL for authentication service (default: http://127.0.0.1:10000)
- `BLOB_SERVICE`: URL for blob storage service (default: http://127.0.0.1:13000)
- `USER_SERVICE`: URL for user service (default: http://127.0.0.1:8500)

### Default Configuration
- **Host:** 0.0.0.0 (accepts connections from any IP)
- **Port:** 7500
- **Privileged IPs:** 127.0.0.1 (localhost)

---

## Usage Examples

### Starting a Workload
```bash
curl -X POST "http://localhost:7500/api/session-supervisor-service/start-workload" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "customer_id=customer-123&object_id=object-456"
```

### Checking Progress
```bash
curl "http://localhost:7500/api/session-supervisor-service/get-workload-progress?customer_id=customer-123"
```

### Adjusting User Count
```bash
curl -X POST "http://localhost:7500/api/session-supervisor-service/set-user-count/customer-123/5"
```

### Stopping a Workload
```bash
curl -X POST "http://localhost:7500/api/session-supervisor-service/stop-and-delete-workload" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "customer_id=customer-123"
```

---

## Development and Deployment

### Running the Service
```bash
python session-supervisor-service.py
```

### Dependencies
- FastAPI
- uvicorn
- httpx
- aio_pika
- python-dotenv

### Production Considerations
- Use a process manager like systemd, supervisor, or Docker
- Configure proper logging
- Set up monitoring and health checks
- Implement proper error handling and retry mechanisms
- Configure load balancing if running multiple instances
