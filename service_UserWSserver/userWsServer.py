import asyncio

import sys
import os
import threading

import socketio
import json

from aiohttp import web

from fastapi import Request,  Response

sys.path.append(os.path.join(os.path.dirname(__file__), "../ServiceTemplates/Basic"))

from HTTP_SERVER import HTTPServer
from MESSAGE_QUEUE import MessageQueue
from WS_SERVER import WebSocketServer

class userWsServerService:
    def __init__(self, wsServerHost, wsServerPort, httpServerHost, httpServerPort):
        self.messageQueue = MessageQueue("amqp://guest:guest@localhost/" , "USER_WS_SERVER_EXCHANGE")
        self.apiServer = HTTPServer(httpServerHost, httpServerPort)

        self.wsServer = WebSocketServer(wsServerHost, wsServerPort)
        self.wsServer.sio = socketio.AsyncServer(async_mode='aiohttp',ping_timeout=60, ping_interval=25 , max_http_buffer_size=1024*1024*100)
        self.wsServer.app = web.Application()
        self.wsServer.sio.attach(self.wsServer.app)


        self.clients = {}


    async def ConfigureApiRoutes(self):
        pass
        

    async def ConfigureWsMethods(self):
        @self.wsServer.sio.event
        async def connect(sid, environ , auth=None):
            print(f"A New User with ID {sid} Connected")
            print(auth)

            self.clients[sid] = environ
            
            mainMessage = {"USER_ID" : sid}
            messageToSend = {"TYPE": "NEW_USER" , "DATA": mainMessage}
        
            await self.sendMessageToUserManager(messageToSend)

        @self.wsServer.sio.event
        async def disconnect(sid):
            del self.clients[sid]

            mainMessage = {"USER_ID" : sid}
            messageToSend = {"TYPE": "REMOVE_USER" , "DATA": mainMessage}

            await self.sendMessageToUserManager(messageToSend)

        @self.wsServer.sio.on("GET_SID")
        async def get_sid(sid):
            return sid



    async def handleCommunicationInterfaceMessages(self, CIMessage , response=False):
        msgType = CIMessage['TYPE']
        msgData = CIMessage['DATA']
        responseMsg = None
        if msgType == "SEND_BUFFER_REQUEST":
            userId = msgData['USER_ID']
            bufferUUID = msgData['BUFFER_UUID']
            await self.wsServer.sio.emit("REQUEST_BUFFER" , bufferUUID , to=userId)
            responseMsg = {"STATUS": "SUCCESS"}
        else:
            print("Unknown Message Type")
            print("Received Message: ", CIMessage)

        
        if response:
            return responseMsg

    async def callbackCommunicationInterfaceMessages(self, message):
        print("Received Message from Communication Interface")
        DecodedMessage = message.body.decode()
        DecodedMessage = json.loads(DecodedMessage)

        await self.handleCommunicationInterfaceMessages(DecodedMessage)
        

    async def sendMessageToUserManager(self, mainMessage):
        print("Sending Message to User Manager")
        exchangeName = "COMMUNICATION_INTERFACE_EXCHANGE"
        routingKey = "CIE_USER_WS_SERVER"

        messageToSend = {"TYPE": "MESSAGE_FOR_USER_MANAGER" , "DATA": mainMessage}

        messageInJson = json.dumps(messageToSend)
        await self.messageQueue.PublishMessage(exchangeName, routingKey, messageInJson)

    async def startService(self):
        await self.messageQueue.InitializeConnection()
        await self.messageQueue.AddQueueAndMapToCallback("UWSSE_CI", self.callbackCommunicationInterfaceMessages, auto_delete=True)
        await self.messageQueue.BoundQueueToExchange()
        await self.messageQueue.StartListeningToQueue()

        await self.ConfigureWsMethods()
        await self.wsServer.start()

        await self.ConfigureApiRoutes()
        await self.apiServer.run_app()


async def start_service():
    service = userWsServerService("127.0.0.1" , 6000 , "127.0.0.1" , 6001)
    await service.startService()

if __name__ == "__main__":
    print("Starting User Ws Server Service")
    asyncio.run(start_service())

