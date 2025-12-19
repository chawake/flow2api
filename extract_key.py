import asyncio
import re
from curl_cffi.requests import AsyncSession

# The proxy we know works
PROXY_URL = "http://customer-japis_GGHy7-cc-US:pN20TMl51UD7~z@pr.oxylabs.io:7777"
TARGET_URL = "https://labs.google/fx/tools/flow"

async def extract_site_key():
    print(f"Fetching {TARGET_URL} via proxy...")
    async with AsyncSession() as session:
        try:
            response = await session.get(
                TARGET_URL,
                proxy=PROXY_URL,
                impersonate="chrome110",
                timeout=30
            )
            print(f"Status: {response.status_code}")
            content = response.text
            
            # Print title to see where we are
            title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
            print(f"Page Title: {title_match.group(1) if title_match else 'No Title found'}")
            print(f"Content Preview (first 500 chars):\n{content[:500]}\n")
            
            # Look for reCAPTCHA keys pattern (standard and variations)
            # usually render=KEY or execute(KEY)
            # The one in the code is 6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV
            
            # Simple regex for typical key structure (40 chars, start with 6L/6I)
            keys = re.findall(r'(\b6[A-Za-z0-9_-]{38}\b)', content)
            
            print("\nFound Potential Keys:")
            unique_keys = set(keys)
            for k in unique_keys:
                print(f" - {k}")

            if "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV" in unique_keys:
                print("\n✅ Match found! The hardcoded key is presently on the page.")
            else:
                print("\n⚠️ NO MATCH for hardcoded key. The key might have changed!")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(extract_site_key())
