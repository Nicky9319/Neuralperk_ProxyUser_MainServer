import uuid

import json 
import subprocess
import os
import socket
import sys

import pickle

# Embedded MessageQueue class
class MessageQueue:
    def __init__(self, ConnectionURL="amqp://guest:guest@localhost/", ExchangeName="/"):
        self.ExchangeName = ExchangeName
        self.ConnectionURL = ConnectionURL
        self.Connection = None
        self.Channel = None
        self.QueueList = []
        self.QueueToCallbackMapping = {}  
        self.DeclaredExchanges = {}

    async def InitializeConnection(self):
        self.Connection = await aio_pika.connect_robust(self.ConnectionURL)
        self.Channel = await self.Connection.channel()
        await self.Channel.declare_exchange(self.ExchangeName, aio_pika.ExchangeType.DIRECT)

    async def BoundQueueToExchange(self):
        for queues in self.QueueList:
            await queues.bind(self.ExchangeName , routing_key=queues.name)
        
    async def AddNewQueue(self, QueueName,**queueParams):
        queue = await self.Channel.declare_queue(QueueName, **queueParams)
        self.QueueList.append(queue)
    
    async def MapQueueToCallback(self, QueueName, Callback):
        self.QueueToCallbackMapping[QueueName] = Callback

    async def AddQueueAndMapToCallback(self, QueueName, Callback,**queueParams):
        await self.AddNewQueue(QueueName,**queueParams)
        await self.MapQueueToCallback(QueueName, Callback)

    async def StartListeningToQueue(self):
        for queue in self.QueueList:
            await queue.consume(self.QueueToCallbackMapping[queue.name])

    async def PublishMessage(self, exchangeName , routingKey, message, headers=None):
        exchange = None
        if exchangeName not in self.DeclaredExchanges.keys():
            exchange = await self.Channel.declare_exchange(exchangeName)
            self.DeclaredExchanges[exchangeName] = exchange
        else:
            exchange = self.DeclaredExchanges[exchangeName]
        
        messageToSend = None
        if headers and "DATA_FORMAT" in headers:
            if headers["DATA_FORMAT"] == "BYTES":
                messageToSend = message
            else:
                messageToSend = message.encode()
        else:
            messageToSend = message.encode()
    
        try:
            await exchange.publish(
                aio_pika.Message(body=messageToSend, headers=headers),
                routing_key=routingKey
            )
        except Exception as e:
            print(f"Failed to publish message: {e}")

        return True

    async def CloseConnection(self):
        await self.Connection.close()

class CustomerAgentData:
    def __init__(self):
        self.connection_url = "amqp://guest:guest@localhost/"
        self.exchange_name = "CUSTOMER_AGENT_EXCHANGE"
        
        # Customer agent specific configurations
        self.session_supervisor_port_range = (15000, 16000)
        self.python_executable = ".venv/bin/python3.12"
        self.session_supervisor_script = "service_SessionSupervisor/sessionSupervisor.py"
        self.host_address = "127.0.0.1"

class customerAgent():
    def __init__(self, data_class=None):
        self.data = data_class or CustomerAgentData()
        self.sessionData = None
        self.SessionSupervisorID = None
        self.SessionSupervisorRoutingKey = None

        self.messageQueue = MessageQueue(self.data.connection_url, self.data.exchange_name)

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
        for portNumber in range(self.data.session_supervisor_port_range[0], self.data.session_supervisor_port_range[1]):
            if self.CheckPortFree(portNumber):
                return portNumber

    def SpawnSessionSupervisorService(self, sessionId):
        portToRunService = self.FindFreePort()
        print("Running on Port : " , portToRunService)
        subprocess.Popen(
            [self.data.python_executable, self.data.session_supervisor_script, "--host", self.data.host_address, "--port", f"{portToRunService}", "--id", f"{sessionId}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setpgrp
        )

        print("Session Supervisor Service started.")
        return True

    async def InitializeSession(self , sessionData):
        await self.messageQueue.InitializeConnection()

        self.sessionData = sessionData

        sessionId = self.GenerateUniqueSessionID()
        print("New Session Supervisor ID : " , sessionId)
        print(type(sessionId))

        messageToSend = {"TYPE" : "SESSION_INIT_DATA" , "DATA" : self.sessionData}
        messageInBytes = pickle.dumps(messageToSend)

        print(f"Session Data :  {sessionData.keys()}")

        headersToSend = {"DATA_FORMAT" : f"BYTES"}

        self.SpawnSessionSupervisorService(sessionId)

        print("Customer Agent : Sending the Message on Queue")

        queueID = f"SSE_{sessionId}_CA"
        print(queueID)
        print(type(queueID))

        await self.messageQueue.AddQueueAndMapToCallback(queueID, self.callbackSessionSupervisorMessages, auto_delete = True)
        await self.messageQueue.BoundQueueToExchange()
        await self.messageQueue.StartListeningToQueue()

        await self.messageQueue.PublishMessage("SESSION_SUPERVISOR_EXCHANGE", queueID, messageInBytes, headersToSend)

        print("Message Sent to Session Supervisor")

    async def callbackSessionSupervisorMessages(self, message):
        print("Received Message from Session Supervisor")
        DecodedMessage = message.body.decode()
        DecodedMessage = json.loads(DecodedMessage)

        await self.handleSessionSupervisorMessages(DecodedMessage)

    async def handleSessionSupervisorMessages(self, sessionSupervisorMessage):
        msgType = sessionSupervisorMessage['TYPE']
        msgData = sessionSupervisorMessage['DATA']
        
        if msgType == "SESSION_INITIALIZED":
            print("Session Supervisor Initialized")
        elif msgType == "SESSION_READY":
            print("Session Supervisor Ready")
        else:
            print("Unknown Message Type")
            print("Received Message: ", sessionSupervisorMessage)

class Service:
    def __init__(self, customerAgent=None):
        self.customerAgent = customerAgent

    async def startService(self):
        print("Starting Customer Agent Service...")
        # Customer agent doesn't have a continuous service, it's event-driven

async def start_service():
    dataClass = CustomerAgentData()
    customerAgentInstance = customerAgent(dataClass)
    service = Service(customerAgentInstance)
    await service.startService()

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_service())





