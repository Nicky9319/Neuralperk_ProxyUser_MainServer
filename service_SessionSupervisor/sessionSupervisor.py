import argparse

import asyncio

import sys 
import os

import threading

import json
import requests
import datetime
import subprocess



import aio_pika

from fastapi.responses import JSONResponse



import logging


import pickle




sys.path.append(os.path.join(os.path.dirname(__file__), "../ServiceTemplates/Basic"))

from HTTP_SERVER import HTTPServer
from MESSAGE_QUEUE import MessageQueue




class renderingSupervisor:
    def __init__(self, renderingCompleteEvent, MessageQueueReference, supervisorID = None):
        self.renderingInfo = None
        self.renderingComplete = renderingCompleteEvent

        self.userList = []

        self.userIdToFrames = {}
        self.frameStatus = {}

        self.logger = logging.getLogger(__name__)

        self.ID = supervisorID
        self.messageQueue = MessageQueueReference

        self.logger.info(f"{type(self.messageQueue)}")


        self.savedBlendFilePath = None
        self.renderedImagesFolder = "RenderedImages"

# Basic Utility Section !!! ----------------------------------------------------------------------------------------------------------------------------------------------------

    async def getServiceURL(self, serviceName):
        servicePortMapping = json.load(open("ServiceURLMapping.json"))
        return servicePortMapping[serviceName]

# Basic Utility Section END !!! ------------------------------------------------------------------------------------------------------------------------------------------------


# User Interaction Section !!! ------------------------------------------------------------------------------------------------------------------------------------------------

    async def sendMessageToAllUsers(self, message):
        self.logger.info("Need to Send Message to All Users")
        for userId in self.userList:
            await self.sendMessageToSingleUser(userId, message)

    async def sendMessageToSingleUser(self, userId, message):
        exchangeName = "USER_MANAGER_EXCHANGE"
        routingKey = "UME_SESSION_SUPERVISOR"

        mainMessage = {"USER_ID" : userId, "MESSAGE_FOR_USER" : message}
        messageToSend = {"TYPE" : "SEND_MESSAGE_TO_USER" , "DATA" : mainMessage}
        messageInJson = json.dumps(messageToSend)

        headersToInclude = {"SESSION_SUPERVISOR_ID": self.ID}

        self.logger.info(f"Sending Message to User : {userId} by Publishing it to the Queue")
        await self.messageQueue.PublishMessage(exchangeName, routingKey, messageInJson, headersToInclude)
        self.logger.info(f"Message Sent to User : {userId}")



    async def handleMultipleUserDisconnect(self, userIdList):
        for userId in userIdList:
            await self.handleSingleUserDisconnect(userId)

    async def handleSingleUserDisconnect(self, userId):
        userFrames = self.userIdToFrames[userId]
        self.userList.remove(userId)
        fiteredFrames = [frame for frame in userFrames if self.frameStatus[frame] == False]
        del self.userIdToFrames[userId]

        self.logger.info(f"User : {userId} Disconnected")
        self.logger.info(f"Frames to be Reassigned : {fiteredFrames}")
        await self.distributeFrameAmongUsersAndSend(fiteredFrames, overwrite=False, extend=True)

        self.logger.info(f"Redisribution of Frames Completed")



    async def handleMultipleUserAddition(self, userIdList):
        for userId in userIdList:
            await self.handleSingleUserAddition(userId)

    async def handleSingleUserAddition(self, newUserId):
        remainingFrames = []
        
        self.logger.info(f"User : {newUserId} Added")
        for userId in self.userList:
            remainingFrames.extend(self.userIdToFrames[userId])
            self.userIdToFrames[userId] = []

        self.userList.append(newUserId)
        self.logger.info(f"User List Updated : {self.userList}")

        await self.distributeFrameAmongUsers(remainingFrames , overwrite=True)

        # await self.sendBlendFileToSingleUser(userId, self.savedBlendFileName)
        # await self.sendFramesToSingleUser(userId, self.userIdToFrames[userId])
        await self.notifySingleUserToStartRendering(newUserId, self.saveBlendFileBinary)

        for userId in self.userList:
            if userId != newUserId:
                await self.sendFramesToSingleUser(userId, self.userIdToFrames[userId], overwrite=True)




    async def handleUserMessages(self, userMessage, response=False):
        msgType = userMessage['TYPE']
        msgData = userMessage['DATA']
        userId = userMessage["USER_ID"]
        
        if msgType == "MESSAGE":
            mainMessage = msgData['MESSAGE']
            print(f"Received the following messageF rom User : {userId}")
            print(f"Message : {mainMessage}")
        elif msgType == "FRAME_RENDERED":
            await self.FrameRenderCompleted(userId, msgData)
        elif msgType == "RENDERING_COMPLETED":
            userId = msgData['USER_ID']
            await self.UserRenderingProcessCompleted(userId)


# User Interaction Section END !!! --------------------------------------------------------------------------------------------------------------------------------------------


# User Manager Interaction Section !!! ----------------------------------------------------------------------------------------------------------------------------------------

    async def handleUserManagerMessages(self, userManagerMessage, response=False):
        msgType = userManagerMessage['TYPE'] 
        msgData = userManagerMessage['DATA']

        self.logger.info("Received Message from User Manager")

        responseMsg = None
        if msgType == "USER_DISCONNECT":
            await self.handleSingleUserDisconnect(msgData['USER_ID'])
            responseToSend = {"STATUS" : "SUCCESS" , "MESSAGE" : "USER_DISCONNECT_HANDLED"}
            responseMsg = JSONResponse(content=responseToSend , status_code=200)
        elif msgType == "ADDITIONAL_USER_LIST":
            self.logger.info("Received Additional user List")
            await self.handleMultipleUserAddition(msgData['LIST_USER_ID'])
            responseToSend = {"STATUS" : "SUCCESS" , "MESSAGE" : "USER_DISCONNECT_HANDLED"}
            responseMsg = JSONResponse(content=responseToSend , status_code=200)
        else:
            responseToSend = {"STATUS" : "ERROR" , "MESSAGE" : "INVALID MESSAGE TYPE"}
            responseMsg = JSONResponse(content=responseToSend , status_code=400)

        if response:
            return responseMsg

# User Manager Interaction Section END !!! ------------------------------------------------------------------------------------------------------------------------------------




# Main Process Management Section !!! ------------------------------------------------------------------------------------------------------------------------------------------
    

    # Save the Image Derived from Image Binary in the Directory with the Mentioned Extension
    async def saveImageInDirectory(self, imageBinary, frameNumber , imageExtension = 'png'):
        print("Image Saved FRAME NUMBER : " , frameNumber)
        with open(self.renderedImagesFolder + f"/{frameNumber}.{imageExtension}" , "wb") as file:
            file.write(imageBinary)

    # Checks if the All the frames from all the Worker nodes has been Received, i.e. The Rendering is Completed from Worker Nodes end or Not
    async def checkRenderingProcessCompleted(self):
        for userId in self.userList:
            if len(self.userIdToFrames[userId]) > 0:
                return False
        
        return True




    # Handles the User Rendering Process Completed Message from the User
    async def UserRenderingProcessCompleted(self, userId):
        if len(self.userIdToFrames[userId]) == 0:
            await self.notifySingleUserRenderingCompleted(userId)
            self.userList.remove(userId)
            self.userIdToFrames.pop(userId)
            await self.userFreedUpAfterCompletingWork(userId)
        else:
            messageToSend = {"TYPE" : "SEND_FRAMES", "DATA" : self.userIdToFrames[userId]}
            await self.sendMessageToSingleUser(userId , messageToSend)

    # Handles the Frame Rendered Message from the User
    async def FrameRenderCompleted(self, userId, dataRenderedFrame):
        frameNumber = dataRenderedFrame['FRAME_NUMBER']
        imageBinary = dataRenderedFrame['IMAGE_BINARY']
        imageExtension = dataRenderedFrame['IMAGE_EXTENSION']
        
        await self.saveImageInDirectory(imageBinary, frameNumber, imageExtension)

        self.frameStatus[frameNumber] = True
        if frameNumber in self.userIdToFrames[userId]:
            self.userIdToFrames[userId].remove(frameNumber)
        
        if await self.checkRenderingProcessCompleted():
            await self.notifyAllUsersRenderingCompleted()
            self.renderingComplete.set()




    
    # Distribute the Frames Among Users and Send the new Added Frames to them
    async def distributeFrameAmongUsersAndSend(self, frameList, overwrite = False, extend=False):
        numberOfUsers = len(self.userList)
        for userNumber in range(numberOfUsers):
            newAddedFrames = frameList[userNumber :: numberOfUsers]
            if overwrite:
                self.userIdToFrames[self.userList[userNumber]] = newAddedFrames
                await self.sendFramesToSingleUser(self.userList[userNumber] , newAddedFrames , overwrite=True)
            elif extend:
                self.userIdToFrames[self.userList[userNumber]].extend(newAddedFrames)
                await self.sendFramesToSingleUser(self.userList[userNumber] , newAddedFrames , extend=True)
            else:
                self.idToFrames[self.userList[userNumber]] = newAddedFrames
                await self.sendFramesToSingleUser(self.userList[userNumber] , newAddedFrames)

    # Distribute the a list of Frames Among Remaining Users
    async def distributeFrameAmongUsers(self, frameList , overwrite = False):
        numberOfUsers = len(self.userList)
        for userNumber in range(numberOfUsers):
            if not overwrite:
                self.userIdToFrames[self.userList[userNumber]].extend(frameList[userNumber :: numberOfUsers])
            else:
                self.userIdToFrames[self.userList[userNumber]] = frameList[userNumber :: numberOfUsers]






    # Sends the Blend File to a Particular User
    async def sendBlendFileToSingleUser(self, userId, blendFilePath):
        mainMessage = {"BINARY_BLEND_FILE" : blendFilePath , "META_DATA" : "EXTRACT_BLEND_FILE_FROM_PATH"}
        messageToSend = {"TYPE" : "BLEND_FILE" , "DATA" : mainMessage}
        await self.sendMessageToSingleUser(userId , messageToSend)
    
    # Sends the Blend File to All Users
    async def sendBlendFileToAllUsers(self, blendFilePath):
        mainMessage = {"BINARY_BLEND_FILE" : blendFilePath , "META_DATA" : "EXTRACT_BLEND_FILE_FROM_PATH"}
        messageToSend = {"TYPE" : "BLEND_FILE" , "DATA" : mainMessage}
        await self.sendMessageToAllUsers(messageToSend)



    # Sends the Frame List to a particular User
    async def sendFramesToSingleUser(self, userId, framesList, overwrite = False, extend=False):
        mainMessage = {"FRAMES" : framesList}
        messageToSend = None

        if overwrite:
            messageToSend = {"TYPE" : "FRAME_LIST_OVERWRITE" , "DATA" : mainMessage}
        elif extend:
            messageToSend = {"TYPE" : "FRAME_LIST_EXTEND" , "DATA" : mainMessage}
        else:
            messageToSend = {"TYPE" : "FRAME_LIST" , "DATA" : mainMessage}

        await self.sendMessageToSingleUser(userId , messageToSend)

    # Send the Frame List to All Users
    async def sendFramesToAllUsers(self, overwrite = False, extend=False):
        for userId in self.userList:
            await self.sendFramesToSingleUser(userId, self.userIdToFrames[userId], overwrite=overwrite, extend=extend)



    # Sends the Message to a Single User to Start the Rendering Process
    async def notifySingleUserToStartRendering(self, userId, blendFilePath):
        userFrames = self.userIdToFrames[userId]
        mainMessage = {"FRAMES" : userFrames, "BINARY_BLEND_FILE" : blendFilePath, "META_DATA" : "EXTRACT_BLEND_FILE_FROM_PATH"}
        messageToSend = {"TYPE" : "INITIALIZE_AND_RUN_MANAGER", "DATA" : mainMessage}
        await self.sendMessageToSingleUser(userId , messageToSend)

    # Sends the Message to All Users to Start the Rendering Process
    async def notifyAllUsersToStartRendering(self, blendFilePath):
        for userId in self.userList:
            await self.notifySingleUserToStartRendering(userId, blendFilePath)



    # Sends the necessary files and data to a Single users so that they can start the Rendering Process
    async def notifySingleUserRenderingCompleted(self, userId):
        messageToSend = {"TYPE" : "RENDERING_COMPLETED"}
        await self.sendMessageToSingleUser(userId , messageToSend)

    # Sends the necessary files and data to all users so that they can start the Rendering Process
    async def notifyAllUsersRenderingCompleted(self):
        messageToSend = {"TYPE" : "RENDERING_COMPLETED"}
        self.sendMessageToAllUsers(messageToSend)










    # Returns a Dictionary Storing the Status of Frames ranging from [Start Frame , End Frame]
    async def createFrameStatusDict(self , startFrame , endFrame):
        # print("FRAME STATUS DICT CODE SNIPPET")
        # print(start_frame , last_frame)
        frameStatus = {}
        for frame_number in range(startFrame , endFrame + 1):
            # print(frame_number)
            frameStatus[frame_number] = False
            # print(frameStatus[frame_number])
        
        # print(f"Frame Status Dict Before Sending : \n" , frameStatus)
        return frameStatus

    # Assing Frames to Users when No Frame has been assigned to them , Does not send the frames to them
    async def assignFramesToUsers(self , firstFrame , lastFrame , number_of_workers):
        # print("ASSIGN FRAMES TO USERS CODE SNIPPET")
        # print(first_frame , last_frame , number_of_workers)
        frames_list = list(range(firstFrame , lastFrame + 1))
        # print("FRAMES LIST NOTIONAL")
        # print(frames_list)
        idToFrames = {}
        for worker_number in range(number_of_workers):
            print("WORKER NUMBER  : " , worker_number)
            print(firstFrame + worker_number)
            print(frames_list[firstFrame + worker_number :: number_of_workers])
            idToFrames[self.userList[worker_number]] = frames_list[worker_number :: number_of_workers]
        
        # print(f"Frames Assigned to Each User : \n", id_to_frames)
        return idToFrames

    # Returns the Last and First Frame of a Scene in Blender
    async def getLastAndFirstFrame(self , blendFileName):
        script_path = "service_SessionSupervisor/getFrameRange.py"

        self.logger.info("Getting the Frame Range of the Scene !!!")

        command = f"blender --background {blendFileName} --python {script_path}"
        self.logger.info(f"Command to Get Frame Range : {command}")
        result = subprocess.run([command], capture_output=True , text = True, shell=True)
        
        self.logger.info("Process Of Finding Frame Completed !!!")


        output = result.stdout.split("\n")

        first_frame = [line.split(":")[1] for line in output if "FF" in line.split(":")[0]][0]
        last_frame = [line.split(":")[1] for line in output if "LF" in line.split(":")[0]][0]

        frameList = [last_frame, first_frame]
        self.logger.info(f"First Frame : {first_frame} , Last Frame : {last_frame}")
        
        return frameList
    
    # Stores the Blend File In Local Directoy from the Binary it is given and also stores the name of the Folder
    async def saveBlendFileBinary(self , binaryBlendData , customerEmail):
        # dir_path = f'CustomerData/paarthsaxena2005@gmail.com/Rendering'
        dir_path = f"CustomerData/{customerEmail}/Rendering"
        os.makedirs(dir_path , exist_ok=True)

        file_name = (datetime.datetime.now().strftime("%Y-%m-%d,%H-%M-%S"))
        sub_dir_path = f'{dir_path}/{file_name}'
        os.makedirs(sub_dir_path , exist_ok=True)

        input_file_path = f'{sub_dir_path}/InputBlendFile'
        os.makedirs(input_file_path , exist_ok=True)

        output_file_path = f'{sub_dir_path}/RenderedFiles'
        os.makedirs(output_file_path , exist_ok=True)

        renderer_images_path = f'{output_file_path}/Images'
        os.makedirs(renderer_images_path , exist_ok=True)

        renderer_videos_path = f'{output_file_path}/Video'
        os.makedirs(renderer_videos_path , exist_ok=True)

        with open(f"{input_file_path}/{str(file_name)}.blend" , "wb") as file:
            file.write(binaryBlendData)
        

        self.renderedImagesFolder = renderer_images_path    


        return f"{input_file_path}/{str(file_name)}" + ".blend"




    




    # Combining the Indiviual Frames to Final Video
    async def reconcileFrameToVideo(self):
        print("Reconciling the Frames to Video !!!")
        pass




    # Makes the Decision to What to do with User after it has completed its given Rendering Work
    async def userFreedUpAfterCompletingWork(self, userId):
        pass






    # Releasing A single User from the Rendering Process
    async def releaseSingleUser(self, userId):
        pass

    # Releasing All the Users from the Rendering Process
    async def releaseAllUsers(self):
        pass        





    # Asks for More Users from the User Manager
    async def askMoreUser(self, userCount = 0):
        if userCount == 0:
            return
        
        userManagerServiceURL = await self.getServiceURL("USER_MANAGER")
        mainMessage = {"USER_COUNT" : userCount}
        messageToSend = {"TYPE" : "ADDITIONAL_USERS" , "DATA" : mainMessage}

        headersToSend = {"SESSION_SUPERVISOR_ID": self.ID}

        self.logger.info("SENDING ADDITONAL USER DEMAND ")
        await asyncio.to_thread(requests.post, f"http://{userManagerServiceURL}/SessionSupervisor/NewSession" , json=messageToSend, headers=headersToSend)



    # Initial Setup for the Rendering Process
    async def RenderingProcessInititalSetup(self):
        while True:
            if len(self.userList) == 0:
                userManagerServiceURL = await self.getServiceURL("USER_MANAGER")
                mainMessage = {"USER_COUNT" : 1}
                # mainMessage = {"USER_COUNT" : "ALL"}
                messageToSend = {"TYPE" : "NEW_SESSION" , "DATA" : mainMessage}
                # messageInJson = json.dumps(messageToSend)

                headersToSend = {"SESSION_SUPERVISOR_ID": self.ID}

                response = requests.post(f"http://{userManagerServiceURL}/SessionSupervisor/NewSession" , json=messageToSend, headers=headersToSend)

                if response.status_code == 200:
                    data = json.loads(response.text)
                    self.userList = data['LIST_USER_ID']

                    if data["NOTICE"] == "NOT_SUFFICIENT":
                        print("Not Sufficent Users to Start the Rendering Process")
                        print("Waiting for 30 Seconds")
                        await asyncio.sleep(30)

                        # import time
                        # time.sleep(30)

                    elif data["NOTICE"] == "SUFFICIENT":
                        break
            else:
                break

        
        


# Main Process Management Section END !!! --------------------------------------------------------------------------------------------------------------------------------------




class sessionSupervisorService:
    def __init__(self, httpServerHost, httpServerPort , supervisorID = None):
        self.messageQueue = MessageQueue("amqp://guest:guest@localhost/" , "SESSION_SUPERVISOR_EXCHANGE")
        self.apiServer = HTTPServer(httpServerHost, httpServerPort)

        self.renderingComplete = asyncio.Event()

        self.ID = supervisorID
        self.customerEmail = None

        self.supervisor = None

        logging.basicConfig(filename = f"Logging/ss.log" ,level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)


    
    async def ConfigureApiRoutes(self):
        pass



    async def ManageRenderingProcess(self, renderingInfo):
        self.supervisor = renderingSupervisor(self.renderingComplete, self.messageQueue, self.ID)
        await self.supervisor.RenderingProcessInititalSetup()

        self.savedBlendFilePath = await self.supervisor.saveBlendFileBinary(renderingInfo['DATA_BINARY_BLENDFILE'] , self.customerEmail)
        self.supervisor.saveBlendFileBinary = self.savedBlendFilePath

        self.logger.info(f"Blend File Saved at : {self.savedBlendFilePath}")

        LastFrame, FirstFrame = await self.supervisor.getLastAndFirstFrame(self.savedBlendFilePath)
        LastFrame = int(LastFrame)
        FirstFrame = int(FirstFrame)

        numberOfWorkers = len(self.supervisor.userList)


        self.supervisor.userIdToFrames = await self.supervisor.assignFramesToUsers(FirstFrame , LastFrame , numberOfWorkers)
        self.supervisor.frameStatus = await self.supervisor.createFrameStatusDict(FirstFrame , LastFrame)






        # await self.supervisor.sendBlendFileToAllUsers(self.savedBlendFilePath)
        # await self.supervisor.sendFramesToAllUsers() 

        await self.supervisor.notifyAllUsersToStartRendering(self.savedBlendFilePath)




        self.renderingComplete.wait()

        await self.supervisor.releaseAllUsers()
        await self.supervisor.reconcileFrameToVideo()

        self.renderingComplete.clear()

        print("Rendering Process Completed !!!")


        ''' 
            what To Do After this Goes Here, Maybe Messaging Customer Agent and Stuff for Same 
        '''




    async def handleCustomerAgentMessages(self, customerAgentMessage, response=False):
        msgType = customerAgentMessage['TYPE']
        msgData = customerAgentMessage['DATA']

        if msgType == "SESSION_INIT_DATA":
            metaData = msgData["META_DATA"]

            sessionData = msgData["SESSION_DATA"]
            jobProfile = sessionData["JOB_PROFILE"]
            if jobProfile == "RENDERING":
                self.customerEmail = metaData["EMAIL"]
                renderingInfo = sessionData

                asyncio.create_task(self.ManageRenderingProcess(renderingInfo))

                responseToSend = {"STATUS" : "SUCCESS" , "MESSAGE" : "RENDERING JOB INITIATED"}
                responseMsg = JSONResponse(content=responseToSend , status_code=200)
        elif msgType == "MESSAGE_TEST":
            print(f"Message Test : {msgData}")
        else:
            responseToSend = {"STATUS" : "ERROR" , "MESSAGE" : "INVALID MESSAGE TYPE"}
            responseMsg = JSONResponse(content=responseToSend , status_code=400)

        if response:
            return responseMsg
                
    async def callbackCustomerAgentMessages(self, message):
        Headers = message.headers
        print(Headers)

        DecodedMessage = None

        if "DATA_FORMAT" in Headers:
            if Headers["DATA_FORMAT"] == "BYTES":
                DecodedMessage = pickle.loads(message.body)
            else:
                DecodedMessage = message.body.decode()
                DecodedMessage = json.loads(DecodedMessage)
        else:
            DecodedMessage = message.body.decode()
            DecodedMessage = json.loads(DecodedMessage)


        await self.handleCustomerAgentMessages(DecodedMessage)



    async def handleUserManagerMessages(self, userManagerMessage, response=False, headers=None):
        msgType = userManagerMessage['TYPE']
        msgData = userManagerMessage['DATA']

        self.logger.info("Received Message from User Manager")
        self.logger.info(f"Message Type : {msgType}")

        responseMsg = None

        if msgType == "USER_MESSAGE":
            responseMsg = await self.supervisor.handleUserMessages(msgData, response=True)
        elif msgType == "USER_MANAGER_MESSAGE":
            responseMsg = await self.supervisor.handleUserManagerMessages(msgData, response=True)
        else:
            responseToSend = {"STATUS" : "ERROR" , "MESSAGE" : "INVALID MESSAGE TYPE"}
            responseMsg = JSONResponse(content=responseToSend , status_code=400)

        if response:
            return responseMsg

    async def callbackUserManagerMessages(self, message):

        # DecodedMessage = message.body.decode()
        # DecodedMessage = json.loads(DecodedMessage)

        DecodedMessage = None
        headers = message.headers

        if headers and "DATA_FORMAT" in headers:
            if headers["DATA_FORMAT"] == "BYTES":
                self.logger.info("Decoding Bytes Message")
                DecodedMessage = pickle.loads(message.body)
            else:
                DecodedMessage = message.body.decode()
                DecodedMessage = json.loads(DecodedMessage)
        else:
            DecodedMessage = message.body.decode()
            DecodedMessage = json.loads(DecodedMessage)
        

        await self.handleUserManagerMessages(DecodedMessage, headers=headers)



    async def InformUserManagerAboutSessionInitialization(self):
        exchangeName = "USER_MANAGER_EXCHANGE"
        routingKey = "UME_SESSION_SUPERVISOR"
        
        mainMessage = None
        messageToSend = {"TYPE" : "INITIALIZE_SESSION" , "DATA" : mainMessage}
        messageInJson = json.dumps(messageToSend)

        headersToInclude = {"SESSION_SUPERVISOR_ID": self.ID}

        await self.messageQueue.PublishMessage(exchangeName, routingKey, messageInJson, headersToInclude)

    async def start_server(self):
        await self.messageQueue.InitializeConnection()

        # Sending Information To User Manager that Session has been Initialized
        await self.InformUserManagerAboutSessionInitialization()

        await self.messageQueue.AddQueueAndMapToCallback(f"SSE_{self.ID}_CA", self.callbackCustomerAgentMessages, auto_delete=True)
        await self.messageQueue.AddQueueAndMapToCallback(f"SSE_{self.ID}_UM", self.callbackUserManagerMessages)
        await self.messageQueue.BoundQueueToExchange()
        await self.messageQueue.StartListeningToQueue()

        # self.logger.info("All Initiate Configurations Done")

        await self.ConfigureApiRoutes()
        await self.apiServer.run_app()
        


async def start_service():

    parser = argparse.ArgumentParser(description='Start a simple HTTP server.')
    parser.add_argument('--host', type=str, default='localhost', help='Hostname to listen on')
    parser.add_argument('--port', type=int, default=15000, help='Port to listen on')
    parser.add_argument('--id', type=str, default=None, help='Id of the Session Supervisor')
    args = parser.parse_args()


    server = sessionSupervisorService(httpServerHost=args.host, httpServerPort=args.port , supervisorID=args.id)
    await server.start_server()

if __name__ == "__main__":
    asyncio.run(start_service())


