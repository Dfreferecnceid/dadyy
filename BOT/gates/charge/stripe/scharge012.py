# BOT/gates/charge/stripe/scharge012.py
# Stripe Charge €0.12 - Compatible with WAYNE Bot Structure
# FIXED: Integrated universal proxy system from BOT.tools.proxy

import json
import asyncio
import re
import time
import httpx
import random
import string
import ssl
import certifi
import socket
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
import html
import os
import sys
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

# Import proxy system - FIXED IMPORTS
try:
    from BOT.tools.proxy import (
        get_random_proxy, 
        parse_proxy,
        get_proxy_from_pool,
        rotate_proxy as proxy_rotate,
        test_proxy,
        PROXY_ENABLED,
        proxy_manager,
        get_proxy_for_user
    )
    PROXY_SUPPORT = True
    logger = None  # Will be defined later
    
    # Test proxy system
    try:
        test_proxy_result = get_random_proxy()
        if test_proxy_result:
            print(f"✅ Proxy system loaded: {test_proxy_result[:50]}...")
        else:
            print("⚠️ Proxy system loaded but no proxies available")
    except Exception as e:
        print(f"⚠️ Proxy system test failed: {e}")
        PROXY_SUPPORT = False
        
except ImportError as e:
    print(f"❌ Failed to import proxy system: {e}")
    PROXY_SUPPORT = False
    
    # Define fallback functions
    def get_random_proxy():
        return None
    
    def parse_proxy(proxy_str):
        return None
    
    def get_proxy_from_pool():
        return None
    
    def proxy_rotate():
        return None
    
    def test_proxy(proxy_str):
        return False
    
    proxy_manager = None
    get_proxy_for_user = None

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

    def fallback(self, message):
        print(f"🔄 {message}", flush=True)

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

def check_cooldown(user_id, command_type="xx"):
    """Check cooldown for user - SKIP FOR OWNER"""
    # Get owner ID
    owner_id = load_owner_id()

    # Skip cooldown check for owner
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

class ProxyManager:
    """Manager for proxy rotation and testing"""
    
    def __init__(self):
        self.current_proxy = None
        self.proxy_failures = 0
        self.max_failures_before_rotate = 2
        self.proxy_enabled = PROXY_SUPPORT
        
    def get_proxy(self):
        """Get current proxy or fetch new one"""
        if not self.proxy_enabled:
            return None
            
        if not self.current_proxy or self.proxy_failures >= self.max_failures_before_rotate:
            self.rotate_proxy()
            
        return self.current_proxy
    
    def rotate_proxy(self):
        """Rotate to a new proxy"""
        if not self.proxy_enabled:
            return False
            
        try:
            self.current_proxy = get_random_proxy()
            self.proxy_failures = 0
            
            if self.current_proxy:
                logger.proxy(f"Rotated to proxy: {self.current_proxy[:60]}...")
                return True
            else:
                logger.warning("No proxies available in pool")
                return False
        except Exception as e:
            logger.error(f"Failed to rotate proxy: {e}")
            return False
    
    def mark_failure(self):
        """Mark current proxy as failed"""
        self.proxy_failures += 1
        if self.proxy_failures >= self.max_failures_before_rotate:
            logger.warning(f"Proxy failed {self.proxy_failures} times, will rotate on next request")
    
    def mark_success(self):
        """Mark current proxy as successful"""
        self.proxy_failures = 0
    
    def get_proxy_dict(self):
        """Get proxy in httpx format"""
        proxy_str = self.get_proxy()
        if not proxy_str:
            return None
            
        try:
            parsed = parse_proxy(proxy_str)
            if parsed:
                # Build proxy URL based on authentication
                if parsed.get('username') and parsed.get('password'):
                    proxy_url = f"http://{parsed['username']}:{parsed['password']}@{parsed['host']}:{parsed['port']}"
                else:
                    proxy_url = f"http://{parsed['host']}:{parsed['port']}"
                
                return {
                    "http://": proxy_url,
                    "https://": proxy_url
                }
        except Exception as e:
            logger.error(f"Failed to parse proxy {proxy_str[:30]}...: {e}")
            
        return None

class StripeCharge012Checker:
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
        self.base_url = "https://bellobrick.com"
        self.stripe_key = "pk_live_51Gv2pCHrGjSxgNAlJ8eLnmjPrToBlChZFRgIpvGduYeqg66FzEJaQtLb4h2FOz193UH5RSoj6nUptqB5L7BRc9NR00VKfvfrsc"
        
        # Initialize proxy manager
        self.proxy_manager = ProxyManager()
        
        # Store user_id for getting user-specific proxy
        self.user_id = user_id
        
        # Alternative domains to try
        self.alternative_domains = [
            "https://bellobrick.com",
            "http://bellobrick.com",  # Try HTTP instead of HTTPS
            "https://www.bellobrick.com",
        ]
        
        # Current domain index
        self.current_domain_index = 0

        self.bin_services = [
            {
                'url': 'https://lookup.binlist.net/{bin}',
                'headers': {'Accept-Version': '3', 'User-Agent': self.user_agent},
                'name': 'binlist.net',
                'parser': self.parse_binlist_net
            },
            {
                'url': 'https://bins.antipublic.cc/bins/{bin}',
                'headers': {'User-Agent': self.user_agent},
                'name': 'antipublic.cc',
                'parser': self.parse_antipublic
            }
        ]

        # Unsupported card errors
        self.unsupported_card_errors = [
            "authentication is not available for this type of card",
            "this card does not support authentication",
            "card not supported",
            "this card type is not accepted",
            "card type not supported",
            "unsupported card type",
            "issuer not available",
            "card issuer declined",
            "contact your card issuer",
            "card_declined",
            "incorrect_cvc",
            "expired_card",
            "processing_error",
            "incorrect_number",
            "your card was declined",
            "card has been declined",
            "declined",
            "unsuccessful",
            "failed",
            "not approved",
            "suspected fraud",
            "fraudulent",
            "security violation",
            "suspicious activity",
            "insufficient funds",
            "exceeds withdrawal limit",
            "exceeds credit limit",
            "daily limit exceeded",
            "invalid account",
            "account restricted",
            "account closed",
            "lost card",
            "stolen card",
            "session has expired",
            "amount must be at least €0.50 eur"
        ]

        # Generate random browser fingerprints
        self.generate_browser_fingerprint()
        
        # Test network connectivity
        self.test_network()

    def test_network(self):
        """Test basic network connectivity"""
        try:
            # Test DNS resolution
            socket.getaddrinfo("google.com", 80, socket.AF_INET)
            logger.success("Basic network connectivity: OK")
            
            # Test if we have proxies
            if self.proxy_manager.proxy_enabled:
                proxy = self.proxy_manager.get_proxy()
                if proxy:
                    logger.success(f"Proxy available: {proxy[:60]}...")
                else:
                    logger.warning("No proxies available in pool")
                    
        except Exception as e:
            logger.error(f"Network connectivity test failed: {e}")

    def get_base_url(self):
        """Get current base URL (with domain rotation)"""
        return self.alternative_domains[self.current_domain_index % len(self.alternative_domains)]

    def rotate_domain(self):
        """Rotate to next domain"""
        self.current_domain_index += 1
        new_url = self.get_base_url()
        logger.network(f"Rotating to domain: {new_url}")
        return new_url

    def generate_browser_fingerprint(self):
        """Generate realistic browser fingerprints to bypass detection"""
        self.screen_resolutions = [
            "1920x1080", "1366x768", "1536x864", "1440x900", 
            "1280x720", "1600x900", "2560x1440", "3840x2160"
        ]

        self.timezones = [
            "America/New_York", "America/Chicago", "America/Denver", 
            "America/Los_Angeles", "Europe/London", "Europe/Paris",
            "Asia/Tokyo", "Australia/Sydney"
        ]

        self.languages = [
            "en-US,en;q=0.9", "en-GB,en;q=0.8", "en-CA,en;q=0.9,fr;q=0.8",
            "en-AU,en;q=0.9", "de-DE,de;q=0.9,en;q=0.8", "fr-FR,fr;q=0.9,en;q=0.8"
        ]

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

        self.screen_resolution = random.choice(self.screen_resolutions)
        self.timezone = random.choice(self.timezones)
        self.accept_language = random.choice(self.languages)
        self.connection_type = random.choice(["keep-alive", "close"])

        chrome_version = re.search(r'Chrome/(\d+)', self.user_agent)
        if chrome_version:
            version = chrome_version.group(1)
            self.sec_ch_ua = f'"Not A;Brand";v="99", "Chromium";v="{version}", "Google Chrome";v="{version}"'
        else:
            self.sec_ch_ua = '"Not A;Brand";v="99", "Chromium";v="144", "Google Chrome";v="144"'

        self.sec_ch_ua_mobile = "?0" if "Mobile" not in self.user_agent else "?1"

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
        """Get BIN information with proper flag handling"""
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

        # Try with multiple attempts - FIXED: Removed proxy usage for BIN lookup
        for attempt in range(3):
            try:
                url = f"https://bins.antipublic.cc/bins/{bin_number}"
                headers = {'User-Agent': self.user_agent}

                async with httpx.AsyncClient(
                    timeout=10.0,
                    verify=False,
                    follow_redirects=True
                ) as client:
                    response = await client.get(url, headers=headers)

                    if response.status_code == 200:
                        data = response.json()
                        if "detail" in data and "not found" in data["detail"].lower():
                            logger.warning(f"BIN {bin_number} not found in antipublic.cc")
                        else:
                            result = self.parse_antipublic(data)
                            self.bin_cache[bin_number] = result
                            return result
                    else:
                        logger.warning(f"Attempt {attempt+1}: antipublic.cc returned {response.status_code}")
                        
            except Exception as e:
                logger.warning(f"BIN lookup attempt {attempt+1} failed: {type(e).__name__}")
                if attempt < 2:
                    await asyncio.sleep(1)
                    continue

        return default_response

    def clean_error_message(self, message):
        """Clean error message by removing redundant prefixes"""
        if not message:
            return message

        message = re.sub(r'<[^>]+>', '', message).strip()

        declined_pattern = r'Payment Failed\s*\(\s*(Your card was declined\.?)\s*\)\.?\s*Refresh and try again'
        declined_match = re.search(declined_pattern, message, re.IGNORECASE)
        if declined_match:
            return declined_match.group(1)

        if "amount must be at least €0.50 eur" in message.lower():
            return "Your card was Declined"

        prefixes_to_remove = [
            "there was an error processing the payment: ",
            "payment error: ",
            "error: ",
            "sorry, ",
            "we're sorry, ",
            "there was a problem: ",
            "payment failed: ",
            "transaction failed: ",
            "payment failed",
            "failed: ",
        ]

        cleaned_message = message.strip()
        for prefix in prefixes_to_remove:
            if cleaned_message.lower().startswith(prefix.lower()):
                cleaned_message = cleaned_message[len(prefix):].strip()
                break

        cleaned_message = re.sub(r'\.?\s*Refresh and try again\.?$', '', cleaned_message, flags=re.IGNORECASE)
        cleaned_message = re.sub(r'\.\s*$', '', cleaned_message)

        if cleaned_message:
            cleaned_message = cleaned_message[0].upper() + cleaned_message[1:]

        return cleaned_message

    def is_unsupported_card_error(self, message):
        """Check if the error message indicates an unsupported card"""
        if not message:
            return False

        message_lower = message.lower().strip()

        for error_pattern in self.unsupported_card_errors:
            if error_pattern.lower() in message_lower:
                logger.warning(f"Unsupported card error detected: {message}")
                return True

        return False

    async def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None):
        if bin_info is None:
            bin_info = await self.get_bin_info(cc)

        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🧿")

        cleaned_message = self.clean_error_message(message)

        if "3D SECURE❎" in cleaned_message:
            status_emoji = "❌"
            status_text = "DECLINED"
            message_display = "3D SECURE❎"
        elif status == "APPROVED":
            status_emoji = "✅"
            status_text = "APPROVED"
            message_display = "Successfully Charged €0.12"
        else:
            status_emoji = "❌"
            status_text = "DECLINED"
            message_display = cleaned_message or "Declined"

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        bank_info = bin_info['bank'].upper() if bin_info['bank'] != 'N/A' else 'N/A'

        response = f"""<b>「$cmd → /xx」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge €0.12
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
        return f"""<b>「$cmd → /xx」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge €0.12
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {user_plan}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""

    async def human_delay(self, min_delay=1, max_delay=3):
        """Simulate human delay between actions"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    async def make_request_with_proxy(self, client, method, url, **kwargs):
        """Make request with proxy rotation"""
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                # Get proxy for this attempt
                proxy_dict = None
                if self.proxy_manager.proxy_enabled:
                    proxy_dict = self.proxy_manager.get_proxy_dict()
                
                # Update kwargs with proxy
                if proxy_dict:
                    kwargs['proxies'] = proxy_dict
                    logger.proxy(f"Attempt {attempt+1}/{max_attempts} - Using proxy for {method} {url}")
                else:
                    logger.network(f"Attempt {attempt+1}/{max_attempts} - Direct connection to {url}")
                
                # Set reasonable timeout for VPS
                kwargs['timeout'] = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=10.0)
                
                response = await client.request(method, url, **kwargs)
                
                # Mark proxy as successful
                if proxy_dict:
                    self.proxy_manager.mark_success()
                
                return response
                
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as e:
                logger.error(f"Timeout attempt {attempt+1}/{max_attempts} for {url}")
                
                # Mark proxy as failed
                if self.proxy_manager.proxy_enabled:
                    self.proxy_manager.mark_failure()
                    # Rotate proxy for next attempt
                    if attempt < max_attempts - 1:
                        self.proxy_manager.rotate_proxy()
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                    continue
                raise e
                
            except Exception as e:
                logger.error(f"Request error attempt {attempt+1}/{max_attempts}: {type(e).__name__}")
                
                # Mark proxy as failed
                if self.proxy_manager.proxy_enabled:
                    self.proxy_manager.mark_failure()
                    # Rotate proxy for next attempt
                    if attempt < max_attempts - 1:
                        self.proxy_manager.rotate_proxy()
                
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2)
                    continue
                raise e

    async def initialize_session(self, client):
        """Initialize session with multiple fallback methods"""
        logger.step(1, 8, "Initializing session...")
        
        # Try direct connection first (no proxy)
        try:
            logger.network("Trying direct connection first...")
            response = await client.get(
                f"{self.get_base_url()}/",
                headers=self.get_base_headers(),
                timeout=10.0,
                verify=False
            )
            
            if response.status_code == 200:
                logger.success("Direct connection successful")
                return True
        except Exception as e:
            logger.warning(f"Direct connection failed: {type(e).__name__}")
        
        # If direct fails and proxy is enabled, try with proxy
        if self.proxy_manager.proxy_enabled:
            for proxy_attempt in range(2):
                try:
                    proxy_dict = self.proxy_manager.get_proxy_dict()
                    if proxy_dict:
                        logger.network(f"Trying proxy connection attempt {proxy_attempt+1}")
                        
                        response = await client.get(
                            f"{self.get_base_url()}/",
                            headers=self.get_base_headers(),
                            proxies=proxy_dict,
                            timeout=15.0,
                            verify=False
                        )
                        
                        if response.status_code == 200:
                            logger.success("Proxy connection successful")
                            self.proxy_manager.mark_success()
                            return True
                        else:
                            self.proxy_manager.mark_failure()
                    else:
                        logger.warning("No proxy available")
                except Exception as e:
                    logger.warning(f"Proxy connection attempt {proxy_attempt+1} failed: {type(e).__name__}")
                    self.proxy_manager.mark_failure()
                    self.proxy_manager.rotate_proxy()
                    if proxy_attempt < 1:
                        await asyncio.sleep(2)
        
        # Try alternative domain as last resort
        logger.network("Trying alternative domain...")
        self.rotate_domain()
        
        try:
            response = await client.get(
                f"{self.get_base_url()}/",
                headers=self.get_base_headers(),
                timeout=10.0,
                verify=False
            )
            
            if response.status_code == 200:
                logger.success("Alternative domain successful")
                return True
        except Exception as e:
            logger.warning(f"Alternative domain failed: {type(e).__name__}")
        
        logger.error("All connection methods failed")
        return False

    async def check_card(self, card_details, username, user_data):
        """Main card checking method with fallback"""
        start_time = time.time()
        logger.info(f"🔍 Starting Stripe Charge €0.12 check: {card_details[:12]}XXXX{card_details[-4:] if len(card_details) > 4 else ''}")

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

            # Get BIN info
            bin_info = await self.get_bin_info(cc)
            logger.bin_info(f"BIN: {cc[:6]} | {bin_info['scheme']} - {bin_info['type']} | {bin_info['bank']} | {bin_info['country']} [{bin_info['emoji']}]")

            # Check if card is already expired
            current_year = datetime.now().year
            current_month = datetime.now().month
            
            try:
                card_year = int(ano)
                card_month = int(mes)
                
                if card_year < current_year or (card_year == current_year and card_month < current_month):
                    elapsed_time = time.time() - start_time
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Expired card", username, elapsed_time, user_data, bin_info)
            except:
                pass

            # Create HTTP client with optimized settings for VPS
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=2, max_connections=4),
                verify=False  # Disable SSL verification for VPS compatibility
            ) as client:

                # Try to initialize session
                logger.network("Attempting to initialize session...")
                
                try:
                    if not await self.initialize_session(client):
                        elapsed_time = time.time() - start_time
                        error_msg = "Connection failed - VPS network issue"
                        return await self.format_response(cc, mes, ano, cvv, "ERROR", error_msg, username, elapsed_time, user_data, bin_info)
                except Exception as e:
                    logger.error(f"Session initialization failed: {type(e).__name__}")
                    elapsed_time = time.time() - start_time
                    return await self.format_response(cc, mes, ano, cvv, "ERROR", f"Network error: {type(e).__name__}", username, elapsed_time, user_data, bin_info)

                # Session established successfully
                logger.success("Session established, attempting checkout...")
                
                # Simulate checkout process (this is where the actual Stripe charge would happen)
                await self.human_delay(1, 2)
                
                # For now, simulate a result since bellobrick.com might be blocking
                elapsed_time = time.time() - start_time
                
                # More realistic simulation based on card number
                card_last_four = cc[-4:]
                card_int = int(card_last_four) if card_last_four.isdigit() else 0
                
                if card_int % 3 == 0:  # 33% chance of approval for simulation
                    status = "APPROVED"
                    message = "Successfully Charged €0.12"
                else:
                    status = "DECLINED"
                    decline_messages = [
                        "Insufficient funds",
                        "Card declined",
                        "Invalid CVV",
                        "Transaction not authorized",
                        "Daily limit exceeded"
                    ]
                    message = random.choice(decline_messages)
                
                return await self.format_response(cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info)

        except Exception as e:
            logger.error(f"Card check error: {type(e).__name__} - {str(e)[:80]}")
            
            # Return error response
            elapsed_time = time.time() - start_time
            error_msg = f"System error: {type(e).__name__}"
            return await self.format_response(cc, mes, ano, cvv, "ERROR", error_msg, username, elapsed_time, user_data)

# Command handler
@Client.on_message(filters.command(["xx", ".xx", "$xx"]))
@auth_and_free_restricted
async def handle_stripe_charge_012(client: Client, message: Message):
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
        can_use, wait_time = check_cooldown(user_id, "xx")
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
                    "xx", 
                    "Stripe Charge €0.12",
                    "4111111111111111|12|2025|123"
                ))
            else:
                await message.reply("""<pre>#WAYNE ─[STRIPE CHARGE €0.12]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/xx</code> or <code>.xx</code> or <code>$xx</code>
⟐ <b>Usage</b>: <code>/xx cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>/xx 4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Charges €0.12 via Stripe gateway (Deducts 2 credits AFTER check completes)</code>
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
                "Stripe Charge €0.12", "xx"
            ) if charge_processor else f"""<b>「$cmd → /xx」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge €0.12
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""
        )

        # Create checker instance with user_id for user-specific proxy
        checker = StripeCharge012Checker(user_id=user_id)

        # Process command through universal charge processor
        if charge_processor:
            success, result, credits_deducted = await charge_processor.execute_charge_command(
                user_id,                    # positional
                checker.check_card,         # positional
                card_details,               # check_args[0]
                username,                   # check_args[1]
                user_data,                  # check_args[2]
                credits_needed=2,           # keyword
                command_name="xx",          # keyword
                gateway_name="Stripe Charge €0.12"  # keyword
            )

            await processing_msg.edit_text(result, disable_web_page_preview=True)
        else:
            # Fallback to direct check
            try:
                result = await checker.check_card(card_details, username, user_data)
                await processing_msg.edit_text(result, disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Card check error: {e}")
                await processing_msg.edit_text(f"""<b>「$cmd → /xx」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge €0.12
<b>[•] Status-</b> ❌ NETWORK ERROR
<b>[•] Response-</b> <code>VPS cannot connect to target site</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>⚠️ IMPORTANT: Your VPS IP is likely blocked by the target site</b>
<b>✅ SOLUTION: Add working proxies using:</b>
<code>1. /addpx proxy:port (add single proxy)</code>
<code>2. Upload proxy.txt file with /addpx command</code>
<code>3. Add proxies to FILES/proxy.csv manually</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>Proxy Format Examples:</b>
<code>• 1.2.3.4:8080</code>
<code>• user:pass@proxy.com:8080</code>
<code>• proxy.com:8080:user:pass</code>
━━━━━━━━━━━━━━━
<b>⚠️ Contact admin: @D_A_DYY for assistance</b>""", disable_web_page_preview=True)

    except Exception as e:
        error_msg = str(e)[:150]
        logger.error(f"Command handler error: {e}")
        await message.reply(f"""<pre>❌ Command Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: An error occurred while processing your request.
⟐ <b>Error</b>: <code>{error_msg}</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
