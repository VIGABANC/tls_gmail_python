import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get('http://127.0.0.1:10001/test-telegram', timeout=15.0)
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
