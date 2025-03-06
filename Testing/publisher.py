import aio_pika
import asyncio
import json

async def publishData(exchange_name, routing_key, message, headers=None):
    # Establish a connection to RabbitMQ server
    connection = await aio_pika.connect_robust("amqp://guest:guest@localhost/")
    async with connection:
        channel = await connection.channel()

        # Declare an exchange
        exchange = await channel.declare_exchange(exchange_name, aio_pika.ExchangeType.DIRECT)

        # Set the headers
        message_headers = headers if headers else {}
        properties = aio_pika.Message(
            body=message.encode(),
            headers=message_headers
        )

        # Publish the message
        await exchange.publish(
            properties,
            routing_key=routing_key
        )
        print(f" [x] Sent '{message}' to exchange '{exchange_name}' with routing key '{routing_key}' and headers '{message_headers}'")

# Example usage
async def main():
    # Mention the Exchange Name
    exchange_name = "SESSION_SUPERVISOR_EXCHANGE"

    # Mention the Routing Key
    routing_key = "SSE_33a23f757417499c83764e872fca5fbf_CA"

    
    mainMessage = {"LOG_LEVEL" : "INFO", "LOG_MESSAGE" : "this is a test"}
    messageToSend = {"TYPE" : "LOG", "DATA" : mainMessage}

    headers = {"SESSION_SUPERVISOR_ID" : "nothing"}

    await publishData(exchange_name, routing_key, json.dumps(messageToSend), headers=headers)

if __name__ == "__main__":
    asyncio.run(main())