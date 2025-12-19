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
            
            # Search for anything looking like a key
            print("Searching for keys...")
            
            # Pattern 1: execute('KEY', ...)
            p1 = re.findall(r"execute\(['\"](6[a-zA-Z0-9_-]{39})['\"]", content)
            
            # Pattern 2: render=KEY
            p2 = re.findall(r"render=(6[a-zA-Z0-9_-]{39})", content)
            
            # Pattern 3: "siteKey": "KEY" or "key": "KEY"
            p3 = re.findall(r"['\"](?:siteKey|key)['\"]\s*:\s*['\"](6[a-zA-Z0-9_-]{39})['\"]", content)
            
            # Pattern 4: Broad search for any 40-char key starting with 6L/6I
            p4 = re.findall(r"\b(6[L|I][a-zA-Z0-9_-]{38})\b", content)
            
            all_keys = set(p1 + p2 + p3 + p4)
            
            print(f"\nPotential Keys Found: {len(all_keys)}")
            for k in all_keys:
                print(f" - {k}")

            hardcoded = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
            if hardcoded in all_keys:
                print(f"\n✅ CORRECT KEY: {hardcoded}")
            else:
                print(f"\n⚠️  MISMATCH: The hardcoded key\n    {hardcoded}\n    was NOT found in the page!")
                
                # Context search
                if "recaptcha" in content.lower():
                    print("\n'recaptcha' IS mentioned in the page. Context:")
                    start = content.lower().find("recaptcha")
                    print(content[start:start+200])
                else:
                    print("\n'recaptcha' is NOT mentioned in the HTML. It might be loaded via a chunk.")


        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(extract_site_key())
