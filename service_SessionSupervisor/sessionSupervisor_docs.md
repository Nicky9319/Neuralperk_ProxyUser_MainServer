# Endpoint Documentations
## Endpoint: /SessionSupervisor/NewSession
### Method
POST
### Description
Initializes a new session for rendering by requesting additional users from the User Manager service.
### Input Format
- **Parameters/Body Schema:**
    - `USER_COUNT` (int): The number of users required for the session.
- **Headers:**
    - `SESSION_SUPERVISOR_ID` (str): The ID of the session supervisor.
### Output Format
- **Response Structure:**
    - `STATUS` (str): "SUCCESS" or "ERROR".
    - `MESSAGE` (str): Description of the result.
    - `LIST_USER_ID` (list): List of user IDs assigned to the session (on success).
    - `NOTICE` (str): "SUFFICIENT" or "NOT_SUFFICIENT".
- **Success/Failure Conditions:**
    - Success: When users are successfully assigned.
    - Failure: When there are not enough users available.
### Internal API/Function Calls
- **Dependencies:** `getServiceURL`, `requests.post`
- **Data Flow:** Sends a request to the User Manager service to get additional users.
# Function Documentations
## Function: getServiceURL
### Description
Fetches the service URL for a given service name from the `ServiceURLMapping.json` file.
### Input Format
- **Parameters:**
    - `serviceName` (str): The name of the service.
### Output Format
- **Response Structure:**
    - Returns the URL of the requested service.
### Internal API/Function Calls
- **Dependencies:** `json.load`
- **Data Flow:** Reads the service URL mapping from a JSON file and returns the URL for the specified service.
## Function: saveImageInDirectory
### Description
Saves an image binary to the specified directory with the given frame number and extension.
### Input Format
- **Parameters:**
    - `imageBinary` (bytes): The binary data of the image.
    - `frameNumber` (int): The frame number to be used in the file name.
    - `imageExtension` (str): The file extension for the image (default is 'png').
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `open`
- **Data Flow:** Writes the image binary to a file in the specified directory.
## Function: checkRenderingProcessCompleted
### Description
Checks if all frames from all worker nodes have been received, indicating that the rendering process is complete.
### Input Format
- **Parameters:**
    - None
### Output Format
- **Response Structure:**
    - Returns `True` if all frames are received, otherwise `False`.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Iterates through the user list and checks if all frames have been rendered.
## Function: UserRenderingProcessCompleted
### Description
Handles the completion of the rendering process for a specific user.
### Input Format
- **Parameters:**
    - `userId` (str): The ID of the user who completed the rendering process.
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `notifySingleUserRenderingCompleted`, `sendMessageToSingleUser`, `userFreedUpAfterCompletingWork`
- **Data Flow:** Notifies the user and updates the user list and frame assignments.
## Function: FrameRenderCompleted
### Description
Handles the completion of rendering for a specific frame by a user.
### Input Format
- **Parameters:**
    - `userId` (str): The ID of the user who rendered the frame.
    - `dataRenderedFrame` (dict): The data of the rendered frame, including frame number, image binary, and image extension.
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `saveImageInDirectory`, `checkRenderingProcessCompleted`, `notifyAllUsersRenderingCompleted`
- **Data Flow:** Saves the rendered frame, updates the frame status, and checks if the rendering process is complete.
## Function: distributeFrameAmongUsersAndSend
### Description
Distributes a list of frames among users and sends the frames to them.
### Input Format
- **Parameters:**
    - `frameList` (list): The list of frames to be distributed.
    - `overwrite` (bool): Whether to overwrite existing frame assignments (default is False).
    - `extend` (bool): Whether to extend existing frame assignments (default is False).
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `sendFramesToSingleUser`
- **Data Flow:** Distributes frames among users and sends the frame list to each user.
## Function: distributeFrameAmongUsers
### Description
Distributes a list of frames among users without sending the frames to them.
### Input Format
- **Parameters:**
    - `frameList` (list): The list of frames to be distributed.
    - `overwrite` (bool): Whether to overwrite existing frame assignments (default is False).
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Distributes frames among users and updates the frame assignments.
## Function: sendBlendFileToSingleUser
### Description
Sends the blend file to a specific user.
### Input Format
- **Parameters:**
    - `userId` (str): The ID of the user.
    - `blendFilePath` (str): The path to the blend file.
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `sendMessageToSingleUser`
- **Data Flow:** Sends the blend file path to the specified user.
## Function: sendBlendFileToAllUsers
### Description
Sends the blend file to all users.
### Input Format
- **Parameters:**
    - `blendFilePath` (str): The path to the blend file.
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `sendMessageToAllUsers`
- **Data Flow:** Sends the blend file path to all users.
## Function: sendFramesToSingleUser
### Description
Sends a list of frames to a specific user.
### Input Format
- **Parameters:**
    - `userId` (str): The ID of the user.
    - `framesList` (list): The list of frames to be sent.
    - `overwrite` (bool): Whether to overwrite existing frame assignments (default is False).
    - `extend` (bool): Whether to extend existing frame assignments (default is False).
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `sendMessageToSingleUser`
- **Data Flow:** Sends the frame list to the specified user.
## Function: sendFramesToAllUsers
### Description
Sends the frame list to all users.
### Input Format
- **Parameters:**
    - `overwrite` (bool): Whether to overwrite existing frame assignments (default is False).
    - `extend` (bool): Whether to extend existing frame assignments (default is False).
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `sendFramesToSingleUser`
- **Data Flow:** Sends the frame list to all users.
## Function: notifySingleUserToStartRendering
### Description
Notifies a specific user to start the rendering process.
### Input Format
- **Parameters:**
    - `userId` (str): The ID of the user.
    - `blendFilePath` (str): The path to the blend file.
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `sendMessageToSingleUser`
- **Data Flow:** Sends a message to the specified user to start rendering.
## Function: notifyAllUsersToStartRendering
### Description
Notifies all users to start the rendering process.
### Input Format
- **Parameters:**
    - `blendFilePath` (str): The path to the blend file.
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `notifySingleUserToStartRendering`
- **Data Flow:** Sends a message to all users to start rendering.
## Function: notifySingleUserRenderingCompleted
### Description
Notifies a specific user that the rendering process is completed.
### Input Format
- **Parameters:**
    - `userId` (str): The ID of the user.
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `sendMessageToSingleUser`
- **Data Flow:** Sends a message to the specified user that rendering is completed.
## Function: notifyAllUsersRenderingCompleted
### Description
Notifies all users that the rendering process is completed.
### Input Format
- **Parameters:**
    - None
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `sendMessageToAllUsers`
- **Data Flow:** Sends a message to all users that rendering is completed.
## Function: createFrameStatusDict
### Description
Creates a dictionary to store the status of frames ranging from start frame to end frame.
### Input Format
- **Parameters:**
    - `startFrame` (int): The starting frame number.
    - `endFrame` (int): The ending frame number.
### Output Format
- **Response Structure:**
    - Returns a dictionary with frame numbers as keys and their status (False) as values.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Creates a dictionary with frame numbers and their initial status.
## Function: assignFramesToUsers
### Description
Assigns frames to users when no frames have been assigned to them.
### Input Format
- **Parameters:**
    - `firstFrame` (int): The first frame number.
    - `lastFrame` (int): The last frame number.
    - `number_of_workers` (int): The number of worker nodes.
### Output Format
- **Response Structure:**
    - Returns a dictionary with user IDs as keys and their assigned frames as values.
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Distributes frames among users and returns the frame assignments.
## Function: getLastAndFirstFrame
### Description
Returns the last and first frame of a scene in Blender.
### Input Format
- **Parameters:**
    - `blendFileName` (str): The name of the blend file.
### Output Format
- **Response Structure:**
    - Returns a list containing the last frame and first frame.
### Internal API/Function Calls
- **Dependencies:** `subprocess.run`
- **Data Flow:** Runs a Blender script to get the frame range and returns the first and last frame.
## Function: saveBlendFileBinary
### Description
Stores the blend file in a local directory from the given binary data and also stores the name of the folder.
### Input Format
- **Parameters:**
    - `binaryBlendData` (bytes): The binary data of the blend file.
    - `customerEmail` (str): The email of the customer.
### Output Format
- **Response Structure:**
    - Returns the path to the saved blend file.
### Internal API/Function Calls
- **Dependencies:** `os.makedirs`, `open`
- **Data Flow:** Saves the blend file binary to a directory and returns the file path.
## Function: reconcileFrameToVideo
### Description
Combines the individual frames into a final video.
### Input Format
- **Parameters:**
    - None
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Combines frames into a video (implementation not provided).
## Function: userFreedUpAfterCompletingWork
### Description
Makes the decision on what to do with a user after they have completed their rendering work.
### Input Format
- **Parameters:**
    - `userId` (str): The ID of the user.
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Decides the next steps for the user (implementation not provided).
## Function: releaseSingleUser
### Description
Releases a single user from the rendering process.
### Input Format
- **Parameters:**
    - `userId` (str): The ID of the user.
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Releases the user from the rendering process (implementation not provided).
## Function: releaseAllUsers
### Description
Releases all users from the rendering process.
### Input Format
- **Parameters:**
    - None
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** None
- **Data Flow:** Releases all users from the rendering process (implementation not provided).
## Function: askMoreUser
### Description
Requests more users from the User Manager service.
### Input Format
- **Parameters:**
    - `userCount` (int): The number of additional users required (default is 0).
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `getServiceURL`, `requests.post`
- **Data Flow:** Sends a request to the User Manager service for additional users.
## Function: RenderingProcessInititalSetup
### Description
Initial setup for the rendering process, including requesting users from the User Manager service.
### Input Format
- **Parameters:**
    - None
### Output Format
- **Response Structure:**
    - None
### Internal API/Function Calls
- **Dependencies:** `getServiceURL`, `requests.post`, `asyncio.sleep`
- **Data Flow:** Requests users from the User Manager service and waits if not enough users are available.
# Classes Documentation
## Class: renderingSupervisor
### Description
Manages the rendering process, including user interactions, frame assignments, and rendering status.
### Attributes
- `renderingInfo` (dict): Information about the rendering process.
- `renderingComplete` (asyncio.Event): Event to signal the completion of rendering.
- `userList` (list): List of user IDs involved in the rendering process.
- `userIdToFrames` (dict): Mapping of user IDs to their assigned frames.
- `frameStatus` (dict): Status of each frame (rendered or not).
- `logger` (logging.Logger): Logger for the class.
- `ID` (str): Supervisor ID.
- `messageQueue` (MessageQueue): Reference to the message queue.
- `savedBlendFilePath` (str): Path to the saved blend file.
- `renderedImagesFolder` (str): Directory for rendered images.
### Methods
- `getServiceURL`: Fetches the service URL for a given service name.
- `sendMessageToAllUsers`: Sends a message to all users.
- `sendMessageToSingleUser`: Sends a message to a single user.
- `handleMultipleUserDisconnect`: Handles the disconnection of multiple users.
- `handleSingleUserDisconnect`: Handles the disconnection of a single user.
- `handleMultipleUserAddition`: Handles the addition of multiple users.
- `handleSingleUserAddition`: Handles the addition of a single user.
- `handleUserMessages`: Handles messages from users.
- `handleUserManagerMessages`: Handles messages from the User Manager.
- `saveImageInDirectory`: Saves an image binary to the specified directory.
- `checkRenderingProcessCompleted`: Checks if all frames have been rendered.
- `UserRenderingProcessCompleted`: Handles the completion of rendering for a user.
- `FrameRenderCompleted`: Handles the completion of rendering for a frame.
- `distributeFrameAmongUsersAndSend`: Distributes frames among users and sends them.
- `distributeFrameAmongUsers`: Distributes frames among users.
- `sendBlendFileToSingleUser`: Sends the blend file to a single user.
- `sendBlendFileToAllUsers`: Sends the blend file to all users.
- `sendFramesToSingleUser`: Sends frames to a single user.
- `sendFramesToAllUsers`: Sends frames to all users.
- `notifySingleUserToStartRendering`: Notifies a user to start rendering.
- `notifyAllUsersToStartRendering`: Notifies all users to start rendering.
- `notifySingleUserRenderingCompleted`: Notifies a user that rendering is completed.
- `notifyAllUsersRenderingCompleted`: Notifies all users that rendering is completed.
- `createFrameStatusDict`: Creates a dictionary to store frame statuses.
- `assignFramesToUsers`: Assigns frames to users.
- `getLastAndFirstFrame`: Gets the first and last frame of a scene.
- `saveBlendFileBinary`: Saves the blend file binary to a directory.
- `reconcileFrameToVideo`: Combines frames into a video.
- `userFreedUpAfterCompletingWork`: Decides what to do with a user after rendering.
- `releaseSingleUser`: Releases a single user from rendering.
- `releaseAllUsers`: Releases all users from rendering.
- `askMoreUser`: Requests more users from the User Manager.
- `RenderingProcessInititalSetup`: Initial setup for the rendering process.
## Class: sessionSupervisorService
### Description
Manages the session supervisor service, including API routes, rendering process, and message handling.
### Attributes
- `messageQueue` (MessageQueue): Reference to the message queue.
- `apiServer` (HTTPServer): Reference to the API server.
- `renderingComplete` (asyncio.Event): Event to signal the completion of rendering.
- `ID` (str): Supervisor ID.
- `customerEmail` (str): Email of the customer.
- `supervisor` (renderingSupervisor): Reference to the rendering supervisor.
- `logger` (logging.Logger): Logger for the class.
### Methods
- `ConfigureApiRoutes`: Configures the API routes for the service.
- `ManageRenderingProcess`: Manages the rendering process.
- `handleCustomerAgentMessages`: Handles messages from the customer agent.
- `callbackCustomerAgentMessages`: Callback for customer agent messages.
- `handleUserManagerMessages`: Handles messages from the User Manager.
- `callbackUserManagerMessages`: Callback for User Manager messages.
- `InformUserManagerAboutSessionInitialization`: Informs the User Manager about session initialization.
- `start_server`: Starts the session supervisor service.
