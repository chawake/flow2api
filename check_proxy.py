import asyncio
from curl_cffi.requests import AsyncSession

# The proxy URL provided by the user
PROXY_URL = "http://customer-japis_GGHy7-cc-US:pN20TMl51UD7~z@pr.oxylabs.io:7777"

async def check_proxy():
    print(f"Testing proxy: {PROXY_URL}")
    print("-" * 50)
    
    async with AsyncSession() as session:
        # Test 1: Check IP Address (using httpbin or similar)
        try:
            print("\nAttempting to fetch public IP via Proxy...")
            response = await session.get(
                "https://api.ipify.org?format=json",
                proxy=PROXY_URL,
                timeout=10,
                impersonate="chrome110"
            )
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
            if response.status_code == 200:
                print("✅ IP Check Successful!")
            else:
                print("❌ IP Check Failed!")
        except Exception as e:
            print(f"❌ IP Check Exception: {e}")

        # Test 2: Check Google Access (to confirm it's not blocked)
        try:
            print("\nAttempting to connect to Google (VideoFX base)...")
            response = await session.get(
                "https://labs.google/fx/api",
                proxy=PROXY_URL,
                timeout=10,
                impersonate="chrome110"
            )
            print(f"Status Code: {response.status_code}")
            # 200 or 404 is fine (means we reached the server), 403 would be bad
            if response.status_code in [200, 404]: 
                print("✅ Google Connection Successful (Server reachable)")
            elif response.status_code == 403:
                print("❌ Google Blocked this IP (403 Forbidden)")
            else:
                print(f"⚠️ Google returned status: {response.status_code}")
        except Exception as e:
            print(f"❌ Google Connection Exception: {e}")

if __name__ == "__main__":
    asyncio.run(check_proxy())
