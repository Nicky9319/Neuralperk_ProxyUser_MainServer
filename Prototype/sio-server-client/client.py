import socketio

import time

# Create a Socket.IO client
sio = socketio.Client()

@sio.event
def connect():
    print('Connected to server')

@sio.event
def disconnect():
    print('Disconnected from server')
    
@sio.on("test")
def test():
    return "Heelo from the Client"

# Connect to the server on localhost:5000
sio.connect('http://localhost:5000')

time.sleep(3)

response = sio.call('test', {'data': 'Hello, Server!'}, timeout=10)
print(response)

# Keep the client running
sio.wait()