import asyncio, os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
async def main():
    uri = os.getenv("MONGODB_URI")
    client = AsyncIOMotorClient(uri)
    try:
        await client.admin.command("ping")
        print("MongoDB 연결 OK")
    finally:
        client.close()

asyncio.run(main())