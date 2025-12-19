import re

SCRIPT_PATH = "/app/flow_script.js"
SITE_KEY = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"

def analyze():
    print(f"Reading {SCRIPT_PATH}...")
    try:
        with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print("File not found! Did you run extract_key.py first?")
        return

    print(f"File size: {len(content)} bytes")

    # 1. Search for Site Key and print surrounding context (expanded)
    found_key = False
    if SITE_KEY in content:
        found_key = True
        print("\n✅ SITE KEY FOUND!")
        idx = content.find(SITE_KEY)
        start = max(0, idx - 400)
        end = min(len(content), idx + 400)
        snippet = content[start:end]
        print(f"CONTEXT (around key):\n{snippet}\n")
    else:
        print("\n❌ Site Key NOT found in this file.")

    # 2. Search for .execute("KEY", {action: "..."}) patterns
    # Handles minified variations: .execute(k,{action:"foo"}) or .execute(k,{action:a})
    print("\nSearching for .execute calls...")
    
    # Regex for .execute(VAR, {action: ...})
    # This matches .execute( then any chars until { then 'action' then : then value
    pattern = r"\.execute\([^,]+,\s*\{[^}]*action\s*:\s*([^},]+)"
    matches = re.finditer(pattern, content)
    
    found_exec = False
    for m in matches:
        found_exec = True
        print(f"FOUND EXECUTE PATTERN: {m.group(0)}")
        print(f"  -> Action Value: {m.group(1)}")

    if not found_exec:
        print("No explicit .execute(key, {action: ...}) pattern found.")

    # 3. Broad "current" action search
    # Sometimes it's passed as a variable: e.g. action: C
    # We look for "action":"VALUE" or action:"VALUE"
    print("\nBroad search for 'action':")
    action_matches = re.findall(r"['\"]?action['\"]?\s*:\s*([^,}\]]+)", content)
    unique_actions = set(action_matches)
    
    for a in unique_actions:
        # Filter noise (functions, long code blocks)
        if len(a) < 30 and "function" not in a and "(" not in a:
            print(f" - {a}")

if __name__ == "__main__":
    analyze()
