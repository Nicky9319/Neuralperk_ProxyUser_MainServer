import uuid

import json 
import subprocess
import os
import socket
import sys

import pickle



sys.path.append(os.path.join(os.path.dirname(__file__), "../ServiceTemplates/Basic"))


from MESSAGE_QUEUE import MessageQueue


class customerAgent():
    def __init__(self):
        self.sessionData = None
        self.SessionSupervisorID = None
        self.SessionSupervisorRoutingKey = None

        self.messageQueue = MessageQueue("amqp://guest:guest@localhost/" , "CUSTOMER_AGENT_EXCHANGE")

    def CheckGenerateSessionIdIsUnique(self , sessionID):
        return True

    def GenerateUniqueSessionID(self):
        while True:
            sessionID = uuid.uuid4().hex
            if self.CheckGenerateSessionIdIsUnique(sessionID):
                self.SessionSupervisorID = sessionID
                self.SessionSupervisorRoutingKey = f"SSE_{sessionID}_CA"
                return sessionID

    def CheckPortFree(self , port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) != 0

    def FindFreePort(self):
        for portNumber in range(15000,16000):
            if self.CheckPortFree(portNumber):
                return portNumber

    def SpawnSessionSupervisorService(self, sessionId):
        portToRunService = self.FindFreePort()
        print("Running on Port : " , portToRunService)
        subprocess.Popen(["python3" , "service_SessionSupervisor/sessionSupervisor.py" , "--host", "127.0.0.1" , "--port", f"{portToRunService}" , "--id" , f"{sessionId}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setpgrp
        )

        # subprocess.run(["python3" , "service_SessionSupervisor/sessionSupervisor.py" , "--host", "127.0.0.1" , "--port", f"{portToRunService}" , "--id" , f"{sessionId}"],)


    async def InitializeSession(self , sessionData):
        await self.messageQueue.InitializeConnection()

        self.sessionData = sessionData


        sessionId = self.GenerateUniqueSessionID()
        print(sessionId)
        await self.messageQueue.Channel.declare_exchange("SESSION_SUPERVISOR_EXCHANGE" , type="direct")

        sessionSupervisorQueue =  await self.messageQueue.Channel.declare_queue(f"SSE_{sessionId}_CA" , auto_delete=True)
        # sessionSupervisorQueue =  await self.messageQueue.Channel.declare_queue(f"SSE_{sessionId}_CA", durable=True)

        await sessionSupervisorQueue.bind("SESSION_SUPERVISOR_EXCHANGE" , routing_key=f"SSE_{sessionId}_CA")

        # sessionInfo = {"SESSION_DATA" : self.sessionData}
        messageToSend = {"TYPE" : "SESSION_INIT_DATA" , "DATA" : self.sessionData}
        messageInBytes = pickle.dumps(messageToSend)

        print(f"Session Data :  {sessionData.keys()}")

        headersToSend = {"DATA_FORMAT" : f"BYTES"}

        await self.messageQueue.PublishMessage("SESSION_SUPERVISOR_EXCHANGE" , f"SSE_{sessionId}_CA" , messageInBytes , headers=headersToSend)

        self.SpawnSessionSupervisorService(sessionId)

    async def HandleSessionRequests(self , customerRequest):
        pass





