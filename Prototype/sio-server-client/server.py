import socketio
from aiohttp import web
import asyncio

sio = socketio.AsyncServer(async_mode='aiohttp')
app = web.Application()
sio.attach(app)

@sio.on('connect')
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.on('test')
async def handle_test(sid, data):
    print(f"Received 'test' event from {sid} with data: {data}")
    response = await sio.call('test', to=sid)
    return f"Response from server: {response}"

async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host='0.0.0.0', port=5000)
    await site.start()
    print("Server started at http://0.0.0.0:5000")
    # Keep running forever
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())