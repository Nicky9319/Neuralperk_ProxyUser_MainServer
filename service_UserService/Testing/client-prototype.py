import asyncio
import socketio

# Create a Socket.IO async client
sio = socketio.AsyncClient()

# ---------------- Event Handlers ---------------- #
@sio.event
async def connect():
    print("✅ Connected to server")

    # Test calling the "get-sid" event
    sid = await sio.call("get-sid")
    print(f"🔌 Server returned sid: {sid}")

@sio.event
async def disconnect():
    print("❌ Disconnected from server")

# ---------------- Main ---------------- #
async def main():
    try:
        # Connect to your running server (adjust port if needed)
        await sio.connect("http://127.0.0.1:8500", transports=["websocket"])
        # Keep the event loop running to listen for events
        await sio.wait()
    except Exception as e:
        print(f"⚠️ Connection error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
