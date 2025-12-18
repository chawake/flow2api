import asyncio
import time
import re
import os
from typing import Optional, Dict
from playwright.async_api import async_playwright, BrowserContext, Page

from ..core.logger import debug_logger

# ... (Keeping original parse_proxy_url and validate_browser_proxy_url functions unchanged) ...
def parse_proxy_url(proxy_url: str) -> Optional[Dict[str, str]]:
    """Parse proxy URL, separating protocol, host, port, and authentication info"""
    proxy_pattern = r'^(socks5|http|https)://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)$'
    match = re.match(proxy_pattern, proxy_url)
    if match:
        protocol, username, password, host, port = match.groups()
        proxy_config = {'server': f'{protocol}://{host}:{port}'}
        if username and password:
            proxy_config['username'] = username
            proxy_config['password'] = password
        return proxy_config
    return None 

class BrowserCaptchaService:
    """Browser automation to get reCAPTCHA token (Persistent headed mode)"""

    _instance: Optional['BrowserCaptchaService'] = None
    _lock = asyncio.Lock()

    def __init__(self, db=None):
        """Initialize service"""
        # === Modification 1: Set to headed mode ===
        self.headless = False 
        self.playwright = None
        # Note: In persistent mode, we operate on context instead of browser
        self.context: Optional[BrowserContext] = None 
        self._initialized = False
        self.website_key = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
        self.db = db
        
        # === Modification 2: Specify local data storage directory ===
        # This will create a browser_data folder in the script directory to save login state
        self.user_data_dir = os.path.join(os.getcwd(), "browser_data")

    @classmethod
    async def get_instance(cls, db=None) -> 'BrowserCaptchaService':
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db)
                    # First call doesn't force initialization, wait for lazy loading in get_token, or can await here
        return cls._instance

    async def initialize(self):
        """Initialize persistent browser context"""
        if self._initialized and self.context:
            return

        try:
            proxy_url = None
            if self.db:
                captcha_config = await self.db.get_captcha_config()
                if captcha_config.browser_proxy_enabled and captcha_config.browser_proxy_url:
                    proxy_url = captcha_config.browser_proxy_url

            debug_logger.log_info(f"[BrowserCaptcha] Starting browser (User Data Dir: {self.user_data_dir})...")
            self.playwright = await async_playwright().start()

            # Configure startup options
            launch_options = {
                'headless': self.headless,
                'user_data_dir': self.user_data_dir, # Specify data directory
                'viewport': {'width': 1280, 'height': 720}, # Set default window size
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            }

            # Proxy configuration
            if proxy_url:
                proxy_config = parse_proxy_url(proxy_url)
                if proxy_config:
                    launch_options['proxy'] = proxy_config
                    debug_logger.log_info(f"[BrowserCaptcha] Using proxy: {proxy_config['server']}")

            # === Modification 3: Use launch_persistent_context ===
            # This will start a browser window with state
            self.context = await self.playwright.chromium.launch_persistent_context(**launch_options)
            
            # Set default timeout
            self.context.set_default_timeout(30000)

            self._initialized = True
            debug_logger.log_info(f"[BrowserCaptcha] ✅ Browser started (Profile: {self.user_data_dir})")
            
        except Exception as e:
            debug_logger.log_error(f"[BrowserCaptcha] ❌ Browser start failed: {str(e)}")
            raise

    async def get_token(self, project_id: str) -> Optional[str]:
        """Get reCAPTCHA token"""
        # Ensure browser is started
        if not self._initialized or not self.context:
            await self.initialize()

        start_time = time.time()
        page: Optional[Page] = None

        try:
            # === Modification 4: New page in existing context, instead of new context ===
            # This reuses saved Cookies in this context (your login state)
            page = await self.context.new_page()

            website_url = f"https://labs.google/fx/tools/flow/project/{project_id}"
            debug_logger.log_info(f"[BrowserCaptcha] Accessing page: {website_url}")

            # Access page
            try:
                await page.goto(website_url, wait_until="domcontentloaded")
            except Exception as e:
                debug_logger.log_warning(f"[BrowserCaptcha] Page load warning: {str(e)}")

            # --- Key point: If manual intervention is needed ---
            # You can add logic here: if it's the first run or detected not logged in,
            # you can pause the script, wait for manual operation then continue.
            # Example: await asyncio.sleep(30) 
            
            # ... (Injection and reCAPTCHA execution logic same as original, omitted for brevity) ...
            # ... Please copy code from "Check and inject reCAPTCHA v3 script" to token retrieval part here ...
            
            # Here for demonstration, simplified injection logic (please keep your original full logic):
            script_loaded = await page.evaluate("() => { return !!(window.grecaptcha && window.grecaptcha.execute); }")
            if not script_loaded:
                await page.evaluate(f"""
                    () => {{
                        const script = document.createElement('script');
                        script.src = 'https://www.google.com/recaptcha/api.js?render={self.website_key}';
                        script.async = true; script.defer = true;
                        document.head.appendChild(script);
                    }}
                """)
                # Wait for loading... (Keep your original wait loop)
                await page.wait_for_timeout(2000) 

            # Execute get Token (Keep your original execute logic)
            token = await page.evaluate(f"""
                async () => {{
                    try {{
                        return await window.grecaptcha.execute('{self.website_key}', {{ action: 'FLOW_GENERATION' }});
                    }} catch (e) {{ return null; }}
                }}
            """)
            
            if token:
                debug_logger.log_info(f"[BrowserCaptcha] ✅ Token obtained successfully")
                return token
            else:
                debug_logger.log_error("[BrowserCaptcha] Token retrieval failed")
                return None

        except Exception as e:
            debug_logger.log_error(f"[BrowserCaptcha] Exception: {str(e)}")
            return None
        finally:
            # === Modification 5: Only close Page (tab), not Context (browser window) ===
            if page:
                try:
                    await page.close()
                except:
                    pass

    async def close(self):
        """Completely close browser (called when cleaning up resources)"""
        try:
            if self.context:
                await self.context.close() # This will close the entire browser window
                self.context = None
            
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
            self._initialized = False
            debug_logger.log_info("[BrowserCaptcha] Browser service closed")
        except Exception as e:
            debug_logger.log_error(f"[BrowserCaptcha] Close exception: {str(e)}")

    # Add a helper method for manual login
    async def open_login_window(self):
        """Call this method to open a permanent window for Google login"""
        await self.initialize()
        page = await self.context.new_page()
        await page.goto("https://accounts.google.com/")
        print("Please log in to your account in the opened browser. Once logged in, no need to close the browser; the script will automatically use this state next time it runs.")