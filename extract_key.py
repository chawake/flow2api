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

            print("\nSearching for Actions in HTML...")
            actions = re.findall(r"action['\"]?\s*[:=]\s*['\"]([a-zA-Z0-9_]+)['\"]", content)
            unique_actions = set(actions)
            for a in unique_actions:
                print(f" - {a}")

            # Find JS files
            print("\nScanning JS files for Actions...")
            scripts = re.findall(r"src=['\"]([^'\"]+\.js)['\"]", content)
            
            for s in scripts:
                if s.startswith("/"):
                    js_url = "https://labs.google" + s
                elif s.startswith("http"):
                    js_url = s
                else:
                    js_url = "https://labs.google/fx/tools/flow/" + s
                
                print(f"  Fetching {js_url}...")
                try:
                    js_resp = await session.get(js_url, proxy=PROXY_URL, impersonate="chrome110", timeout=10)
                    js_content = js_resp.text
                    
                    # Search for the KEY in the JS to find the action next to it
                    if "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV" in js_content:
                        print(f"    ✅ KEY FOUND IN {js_url}")
                        idx = js_content.find("6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV")
                        start = max(0, idx - 200)
                        end = min(len(js_content), idx + 300)
                        print(f"    CONTEXT: ...{js_content[start:end]}...\n")

                    # Also broad search for "action" again just in case
                    # Look for .execute(KEY, {action: 'NAME'}) patterns
                    # Minified might look like: .execute(k,{action:"foo"})
                    executes = re.findall(r"\.execute\([^,]+,\s*\{[^}]*action\s*:\s*['\"]([a-zA-Z0-9_]+)['\"]", js_content)
                    if executes:
                         for exc in set(executes):
                            print(f"    found .execute action: {exc}")
                            
                    # Just find "action:" strings in likely relevant files (flow-*.js)
                    if "pages/tools/flow" in js_url:
                        print(f"    ⭐ FOUND FLOW SCRIPT: {js_url}")
                        print("    Saving to '/app/flow_script.js' for analysis...")
                        with open("/app/flow_script.js", "w", encoding="utf-8") as f:
                            f.write(js_content)
                        print("    Saved.")

                except Exception as ex:
                    print(f"    Failed: {ex}")

            if "FLOW_GENERATION" in unique_actions: # basic check for logic flow
                pass 

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(extract_site_key())
