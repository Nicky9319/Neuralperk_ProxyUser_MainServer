import asyncio
import sys
import os
import threading

import socketio
import json
import pickle

import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse

sys.path.append(os.path.join(os.path.dirname(__file__), "../ServiceTemplates/Basic"))

from HTTP_SERVER import HTTPServer
from MESSAGE_QUEUE import MessageQueue

class userHttpServerService:
    def __init__(self, httpServerHost, httpServerPort, apiServerHost, apiServerPort):
        self.messageQueue = MessageQueue("amqp://guest:guest@localhost/" , "USER_HTTP_SERVER_EXCHANGE")
        self.apiServer = HTTPServer(apiServerHost, apiServerPort)
        self.httpServer = HTTPServer(httpServerHost, httpServerPort)

        self.bufferMsgs = {}



    async def handleUserMessage(self, userMessage, userID):
        msgType = userMessage['TYPE']
        msgData = userMessage['DATA']
        if msgType == "FRAME_RENDERED":
            userId = userID

            # mainMessage = {"MESSAGE" : msgData , "USER_ID" : userId}
            # mainMessage = userMessage
            mainMessage = {"TYPE" : msgType , "DATA" : msgData, "USER_ID" : userId}

            messageToSend = {"TYPE" : "USER_MESSAGE" , "DATA" : mainMessage}
            await self.sendMessageToUserManager(messageToSend, bytes=True)
            return JSONResponse(content={"DATA" : "RECEIVED" , "TIME" : time.time()}, status_code=200)
        elif msgType == "RENDER_COMPLETED":
            userId = userID
            mainMessage = {"MESSAGE" : msgData , "USER_ID" : userId}
            messageToSend = {"TYPE" : "USER_MESSAGE" , "DATA" : mainMessage}
            self.sendMessageToUserManager(messageToSend)
            return JSONResponse(content={"DATA" : "RECEIVED" , "TIME" : time.time()}, status_code=200)
        elif msgType == "TEST":  
            print("Test message Received : " , msgData["TEST"])
            return JSONResponse(content={"DATA" : "RECEIVED" , "TIME" : time.time()}, status_code=200)
        else:
            print("Received Normal Message !!!")
            return JSONResponse(content={"DATA" : "RECEIVED" , "TIME" : time.time()}, status_code=200)


    async def RefineDataFromMetaData(self, bufferMsgData):
        print(bufferMsgData)
        MetaDataType = bufferMsgData["META_DATA"]
        if MetaDataType == "EXTRACT_BLEND_FILE_FROM_PATH":
            def getBlendBinaryFromPath(blendPath):
                print(f"Blender File Path : {bufferMsgData['BINARY_BLEND_FILE']}") 
                
                fileBinary = None
                with open(bufferMsgData["BINARY_BLEND_FILE"] , 'rb') as file:
                    fileBinary =  file.read()
                
                return fileBinary
                
                
            bufferMsgData["BINARY_BLEND_FILE"] = getBlendBinaryFromPath(bufferMsgData["BINARY_BLEND_FILE"])
        else:
            pass

        return bufferMsgData

    async def ConfigureHTTPRoutes(self):
        @self.httpServer.app.get("/")
        async def getDataFromServer(bufferUUID: str):
            if bufferUUID in self.bufferMsgs.keys():
                bufferMsg = self.bufferMsgs[bufferUUID]

                bufferMsgData = bufferMsg["DATA"]

                if type(bufferMsg) == dict and "META_DATA" in bufferMsgData.keys():
                    bufferMsgData = await self.RefineDataFromMetaData(bufferMsgData)

                print("Sending Msg to User")

                del self.bufferMsgs[bufferUUID]
                return Response(content=pickle.dumps(bufferMsg), status_code=200, media_type="application/octet-stream")
            return Response(content=pickle.dumps({"message": "No Buffer Message"}), status_code=400, media_type="application/octet-stream")

        @self.httpServer.app.post("/")
        async def sendDataToServer(request: Request):
            data = None
            if request.headers.get("content-type") == "application/octet-stream":
                data = await request.body()
                data = pickle.loads(data)
            else:
                data = await request.json()

            userId = data["USER_ID"]
            userMessage = data["MAIN_DATA"]
            requestResponse = await self.handleUserMessage(userMessage,userId)
            return requestResponse


    async def ConfigureAPIRoutes(self):
        @self.apiServer.app.post("/CommunicationInterface/AddBufferMsg")
        async def addBufferMsg(request: Request):
            data = await request.json()
            response = await self.handleCommunicationInterfaceMessages(data, response=True)
            return Response(content=json.dumps(response), media_type="application/json")
    


    async def handleCommunicationInterfaceMessages(self, CIMessage , response=False):
        msgType = CIMessage['TYPE']
        msgData = CIMessage['DATA']
        responseMsg = None
        if msgType == "ADD_BUFFER_MSG":
            print("Adding buffer message")
            bufferUUID = msgData['BUFFER_UUID']
            bufferMsg = msgData['BUFFER_MSG']
            self.bufferMsgs[bufferUUID] = bufferMsg
            responseMsg = {"STATUS" : "SUCCESS"}
        else:
            print("Unknown message type")
            print(CIMessage)
            responseMsg = {"STATUS" : "FAILED" , "ERROR" : "Unknown message type"}
            
        if response:
            return responseMsg
        
    async def callbackCommunicationInterfaceMessages(self, message):
        DecodedMessage = message.body.decode()
        DecodedMessage = json.loads(DecodedMessage)

        await self.handleCommunicationInterfaceMessages(DecodedMessage)
        


    async def sendMessageToUserManager(self, mainMessage, bytes=False):
        exchangeName = "COMMUNICATION_INTERFACE_EXCHANGE"
        routingKey = "CIE_USER_HTTP_SERVER"

        messageToSend = {"TYPE" : "MESSAGE_FOR_USER_MANAGER" , "DATA" : mainMessage}

        if bytes:
            messageInBytes = pickle.dumps(messageToSend)
            headersToSend = {'DATA_FORMAT': 'BYTES'}
            await self.messageQueue.PublishMessage(exchangeName, routingKey, messageInBytes, headers=headersToSend)
        else:
            messageInJson = json.dumps(messageToSend)
            await self.messageQueue.PublishMessage(exchangeName, routingKey, messageInJson)


    async def startService(self):
        await self.messageQueue.InitializeConnection()
        await self.messageQueue.AddQueueAndMapToCallback("UHTTPSE_CI", self.callbackCommunicationInterfaceMessages)
        await self.messageQueue.BoundQueueToExchange()
        await self.messageQueue.StartListeningToQueue()

        await self.ConfigureAPIRoutes()
        asyncio.create_task(self.apiServer.run_app())

        await self.ConfigureHTTPRoutes()
        await self.httpServer.run_app()




async def start_service():
    service = userHttpServerService("127.0.0.1" , 10000 , "127.0.0.1" , 10001)
    await service.startService()


if __name__ == "__main__":
    asyncio.run(start_service())
