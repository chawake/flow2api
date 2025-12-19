import asyncio
import time
from playwright.async_api import async_playwright

# Proxy from logs
PROXY_URL = "http://customer-japis_GGHy7-cc-US:pN20TMl51UD7~z@pr.oxylabs.io:7777"
PROJECT_ID = "93d91248-e1de-48f2-b9b4-ad2e9b084948" # From logs

async def spy_action():
    print(f"🕵️  Spying on ReCAPTCHA Action for Project: {PROJECT_ID}")
    
    async with async_playwright() as p:
        # Launch with Stealth Args
        browser = await p.chromium.launch(
            headless=True,
            proxy={'server': 'http://pr.oxylabs.io:7777', 'username': 'customer-japis_GGHy7-cc-US', 'password': 'pN20TMl51UD7~z'},
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars', 
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ],
            ignore_default_args=["--enable-automation"]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US'
        )

        # Stealth Scripts
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Inject Spy Hook BEFORE page loads
        await context.add_init_script("""
            // Hook into window.grecaptcha
            Object.defineProperty(window, 'grecaptcha', {
                configurable: true,
                enumerable: true,
                get: function() {
                    return this._grecaptcha;
                },
                set: function(original) {
                    this._grecaptcha = original;
                    if (original && !original._hooked) {
                        const originalExecute = original.execute;
                        original.execute = function(siteKey, options) {
                            console.log('>>> CAPTCHA EXECUTE INTERCEPTED:');
                            console.log('    SiteKey:', siteKey);
                            console.log('    Action:', options ? options.action : 'UNDEFINED');
                            return originalExecute.apply(this, arguments);
                        };
                        original._hooked = true;
                    }
                }
            });
        """)

        page = await context.new_page()
        
        # Listen for console logs
        page.on("console", lambda msg: print(f"PAGE LOG: {msg.text}") if "CAPTCHA" in msg.text else None)

        url = f"https://labs.google/fx/tools/flow/project/{PROJECT_ID}"
        print(f"Navigating to {url}...")
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"Nav warning: {e}")

        print("Waiting for page activity...")
        # Scroll / Move mouse to trigger hidden checks
        await page.mouse.move(500, 500)
        await page.mouse.wheel(0, 500)
        
        await asyncio.sleep(15)
        
        await browser.close()
        print("Done spying.")

if __name__ == "__main__":
    asyncio.run(spy_action())
