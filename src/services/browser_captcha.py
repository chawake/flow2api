"""
Browser automation to get reCAPTCHA tokens
Accesses page and executes reCAPTCHA validation using Playwright
"""
import asyncio
import time
import re
from typing import Optional, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext

from ..core.logger import debug_logger


def parse_proxy_url(proxy_url: str) -> Optional[Dict[str, str]]:
    """Parse proxy URL, separating protocol, host, port, and authentication info

    Args:
        proxy_url: Proxy URL, format: protocol://[username:password@]host:port

    Returns:
        Proxy config dictionary containing server, username, password (if authenticated)
    """
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


def validate_browser_proxy_url(proxy_url: str) -> tuple[bool, str]:
    """Validate browser proxy URL format (only HTTP and unauthenticated SOCKS5 supported)

    Args:
        proxy_url: Proxy URL

    Returns:
        (is_valid, error_message)
    """
    if not proxy_url or not proxy_url.strip():
        return True, ""  # Empty URL treated as valid (no proxy)

    proxy_url = proxy_url.strip()
    parsed = parse_proxy_url(proxy_url)

    if not parsed:
        return False, "Proxy URL format error, correct format: http://host:port or socks5://host:port"

    # Check for authentication info
    has_auth = 'username' in parsed

    # Get protocol
    protocol = parsed['server'].split('://')[0]

    # SOCKS5 doesn't support auth
    if protocol == 'socks5' and has_auth:
        return False, "Browser doesn't support authenticated SOCKS5 proxy, please use HTTP proxy or remove SOCKS5 auth"

    # HTTP/HTTPS supports auth
    if protocol in ['http', 'https']:
        return True, ""

    # SOCKS5 unauthenticated support
    if protocol == 'socks5' and not has_auth:
        return True, ""

    return False, f"Unsupported proxy protocol: {protocol}"


class BrowserCaptchaService:
    """Browser automation to get reCAPTCHA tokens (Singleton)"""

    _instance: Optional['BrowserCaptchaService'] = None
    _lock = asyncio.Lock()

    def __init__(self, db=None):
        """Initialize service (always use headless mode)"""
        self.headless = True  # Always headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self._initialized = False
        self.website_key = "6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV"
        self.db = db

    @classmethod
    async def get_instance(cls, db=None) -> 'BrowserCaptchaService':
        """Get singleton instance"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db)
                    await cls._instance.initialize()
        return cls._instance

    async def initialize(self):
        """Initialize browser (start once)"""
        if self._initialized:
            return

        try:
            # Get browser-specific proxy configuration
            proxy_url = None
            if self.db:
                captcha_config = await self.db.get_captcha_config()
                if captcha_config.browser_proxy_enabled and captcha_config.browser_proxy_url:
                    proxy_url = captcha_config.browser_proxy_url

            debug_logger.log_info(f"[BrowserCaptcha] Starting browser... (proxy={proxy_url or 'None'})")
            self.playwright = await async_playwright().start()

            # Configure browser startup parameters
            launch_options = {
                'headless': self.headless,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--start-maximized',
                    '--disable-extensions',
                    '--ignore-certificate-errors',
                ],
                'ignore_default_args': ["--enable-automation"]
            }

            # If proxy provided, parse and add proxy configuration
            if proxy_url:
                proxy_config = parse_proxy_url(proxy_url)
                if proxy_config:
                    launch_options['proxy'] = proxy_config
                    auth_info = "auth=yes" if 'username' in proxy_config else "auth=no"
                    debug_logger.log_info(f"[BrowserCaptcha] Proxy config: {proxy_config['server']} ({auth_info})")
                else:
                    debug_logger.log_warning(f"[BrowserCaptcha] Proxy URL format error: {proxy_url}")

            self.browser = await self.playwright.chromium.launch(**launch_options)
            self._initialized = True
            debug_logger.log_info(f"[BrowserCaptcha] ✅ Browser started (headless={self.headless}, proxy={proxy_url or 'None'})")
        except Exception as e:
            debug_logger.log_error(f"[BrowserCaptcha] ❌ Browser start failed: {str(e)}")
            raise

    async def get_token(self, project_id: str) -> Optional[str]:
        """Get reCAPTCHA token

        Args:
            project_id: Flow project ID

        Returns:
            reCAPTCHA token string, returns None if failed
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()
        context = None

        try:
            # Create new context
            context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                device_scale_factor=1,
                has_touch=False,
                is_mobile=False,
                java_script_enabled=True,
            )

            # --- Stealth Injections to hide automation ---
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            await context.add_init_script("""
                // Pass the Chrome Test
                window.chrome = {
                    runtime: {}
                };
            """)
            await context.add_init_script("""
                // Pass the Permissions Test
                const originalQuery = window.navigator.permissions.query;
                return window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
            await context.add_init_script("""
                // Pass the Plugins Length Test
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """)
            await context.add_init_script("""
                // Pass the Languages Test
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            """)
            
            page = await context.new_page()

            website_url = f"https://labs.google/fx/tools/flow/project/{project_id}"

            debug_logger.log_info(f"[BrowserCaptcha] Accessing page: {website_url}")

            # Access page
            try:
                await page.goto(website_url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                debug_logger.log_warning(f"[BrowserCaptcha] Page load timeout or failed: {str(e)}")

            # --- Simulate Human Interaction ---
            try:
                import random
                debug_logger.log_info("[BrowserCaptcha] Simulating human behavior...")
                # Mouse movements
                for _ in range(3):
                    x = random.randint(100, 1800)
                    y = random.randint(100, 900)
                    await page.mouse.move(x, y, steps=10)
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                
                # Small scroll
                await page.mouse.wheel(0, random.randint(100, 500))
                await asyncio.sleep(0.5)
            except Exception as ex:
                debug_logger.log_warning(f"[BrowserCaptcha] Interaction error: {ex}")

            # Check and inject reCAPTCHA v3 script
            debug_logger.log_info("[BrowserCaptcha] Checking and loading reCAPTCHA v3 script...")
            script_loaded = await page.evaluate("""
                () => {
                    if (window.grecaptcha && typeof window.grecaptcha.execute === 'function') {
                        return true;
                    }
                    return false;
                }
            """)

            if not script_loaded:
                # Inject script
                debug_logger.log_info("[BrowserCaptcha] Injecting reCAPTCHA v3 script...")
                await page.evaluate(f"""
                    () => {{
                        return new Promise((resolve) => {{
                            const script = document.createElement('script');
                            script.src = 'https://www.google.com/recaptcha/api.js?render={self.website_key}';
                            script.async = true;
                            script.defer = true;
                            script.onload = () => resolve(true);
                            script.onerror = () => resolve(false);
                            document.head.appendChild(script);
                        }});
                    }}
                """)

            # Wait for reCAPTCHA to load and initialize
            debug_logger.log_info("[BrowserCaptcha] Waiting for reCAPTCHA initialization...")
            for i in range(20):
                grecaptcha_ready = await page.evaluate("""
                    () => {
                        return window.grecaptcha &&
                               typeof window.grecaptcha.execute === 'function';
                    }
                """)
                if grecaptcha_ready:
                    debug_logger.log_info(f"[BrowserCaptcha] reCAPTCHA ready (waited {i*0.5} seconds)")
                    break
                await asyncio.sleep(0.5)
            else:
                debug_logger.log_warning("[BrowserCaptcha] reCAPTCHA initialization timeout, continuing to execute...")

            # Extra wait to ensure full initialization
            await page.wait_for_timeout(1000)

            # Execute reCAPTCHA and get token
            debug_logger.log_info("[BrowserCaptcha] Executing reCAPTCHA validation...")
            token = await page.evaluate("""
                async (websiteKey) => {
                    try {
                        if (!window.grecaptcha) {
                            console.error('[BrowserCaptcha] window.grecaptcha does not exist');
                            return null;
                        }

                        if (typeof window.grecaptcha.execute !== 'function') {
                            console.error('[BrowserCaptcha] window.grecaptcha.execute is not a function');
                            return null;
                        }

                        # Ensure grecaptcha is ready
                        await new Promise((resolve, reject) => {
                            const timeout = setTimeout(() => {
                                reject(new Error('reCAPTCHA load timeout'));
                            }, 15000);

                            if (window.grecaptcha && window.grecaptcha.ready) {
                                window.grecaptcha.ready(() => {
                                    clearTimeout(timeout);
                                    resolve();
                                });
                            } else {
                                clearTimeout(timeout);
                                resolve();
                            }
                        });

                        # Execute reCAPTCHA v3
                        const token = await window.grecaptcha.execute(websiteKey, {
                            action: 'FLOW_GENERATION'
                        });

                        return token;
                    } catch (error) {
                        console.error('[BrowserCaptcha] reCAPTCHA execution error:', error);
                        return null;
                    }
                }
            """, self.website_key)

            duration_ms = (time.time() - start_time) * 1000

            if token:
                debug_logger.log_info(f"[BrowserCaptcha] ✅ Token obtained successfully (took {duration_ms:.0f}ms)")
                return token
            else:
                debug_logger.log_error("[BrowserCaptcha] Token retrieval failed (returned null)")
                return None

        except Exception as e:
            debug_logger.log_error(f"[BrowserCaptcha] Get token exception: {str(e)}")
            return None
        finally:
            # Close context
            if context:
                try:
                    await context.close()
                except:
                    pass

    async def close(self):
        """Close browser"""
        try:
            if self.browser:
                try:
                    await self.browser.close()
                except Exception as e:
                    # Ignore connection closed errors (normal closing scenario)
                    if "Connection closed" not in str(e):
                        debug_logger.log_warning(f"[BrowserCaptcha] Exception when closing browser: {str(e)}")
                finally:
                    self.browser = None

            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception:
                    pass  # Silently handle playwright stop exception
                finally:
                    self.playwright = None

            self._initialized = False
            debug_logger.log_info("[BrowserCaptcha] Browser closed")
        except Exception as e:
            debug_logger.log_error(f"[BrowserCaptcha] Close browser exception: {str(e)}")
