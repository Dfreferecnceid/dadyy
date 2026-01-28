# BOT/gates/charge/shopify/shopify.py
# Shopify Charge Gateway - Fixed with proper encoding
# Uses meta-app-prod-store-1.myshopify.com with product "retailer-id-fix-no-mapping"

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

# Import proxy system - DISABLED to fix connection issues
try:
    from BOT.tools.proxy import get_proxy_for_user, mark_proxy_success, mark_proxy_failed
    PROXY_ENABLED = False  # Disable proxy to fix connection
except ImportError:
    PROXY_ENABLED = False

# Custom logger with ASCII formatting
class SimpleLogger:
    def __init__(self):
        pass

    def info(self, message):
        print(f"[INFO] {message}")

    def success(self, message):
        print(f"[SUCCESS] {message}")

    def warning(self, message):
        print(f"[WARNING] {message}")

    def error(self, message):
        print(f"[ERROR] {message}")

    def step(self, step_num, total_steps, message):
        print(f"[STEP {step_num}/{total_steps}] {message}")

    def network(self, message):
        print(f"[NETWORK] {message}")

    def card(self, message):
        print(f"[CARD] {message}")

    def shopify(self, message):
        print(f"[SHOPIFY] {message}")

    def debug_response(self, message):
        print(f"[DEBUG] {message}")

    def bin_info(self, message):
        print(f"[BIN] {message}")

    def user(self, message):
        print(f"[USER] {message}")

    def proxy(self, message):
        print(f"[PROXY] {message}")

# Create global logger instance
logger = SimpleLogger()

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

def check_cooldown(user_id, command_type="sh"):
    """Check cooldown for user - SKIP FOR OWNER"""
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

def find_between(s, start, end):
    """Helper function to find text between two strings"""
    try:
        return (s.split(start))[1].split(end)[0]
    except:
        return ""

class ShopifyChargeChecker:
    def __init__(self, user_id=None):
        # Modern browser user agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
        ]
        self.user_agent = random.choice(self.user_agents)
        self.bin_cache = {}
        self.last_bin_request = 0
        self.base_url = "https://meta-app-prod-store-1.myshopify.com"
        self.product_url = f"{self.base_url}/products/retailer-id-fix-no-mapping"
        self.user_id = user_id
        self.current_proxy = None
        
        # Shopify specific cookies and tokens
        self.cookies = {}
        self.checkout_token = None
        self.session_token = None
        self.x_checkout_one_session_token = None
        self.x_checkout_web_build_id = "5927fca009d35ac648408d54c8d94b0d54813e89"
        self.cart_token = None
        self.variant_id = "42974272290658"
        
        # Fixed address details from logs
        self.fixed_address = {
            'address1': '8 Log Pond Drive',
            'address2': '',
            'city': 'Horsham',
            'state': 'PA',
            'state_short': 'PA',
            'zip': '19044',
            'country': 'US',
            'country_code': 'US',
            'phone': None
        }
        
        # BIN services
        self.bin_services = [
            {
                'url': 'https://bins.antipublic.cc/bins/{bin}',
                'headers': {'User-Agent': self.user_agent},
                'name': 'antipublic.cc',
                'parser': self.parse_antipublic
            },
            {
                'url': 'https://lookup.binlist.net/{bin}',
                'headers': {'Accept-Version': '3', 'User-Agent': self.user_agent},
                'name': 'binlist.net',
                'parser': self.parse_binlist_net
            }
        ]
        
        # Shopify error patterns
        self.shopify_errors = {
            "your card was declined": "CARD_DECLINED",
            "card has been declined": "CARD_DECLINED",
            "card_declined": "CARD_DECLINED",
            "incorrect_cvc": "INCORRECT_CVC",
            "expired_card": "EXPIRED_CARD",
            "incorrect_number": "INCORRECT_NUMBER",
            "insufficient_funds": "INSUFFICIENT_FUNDS",
            "credit_limit_exceeded": "CREDIT_LIMIT_EXCEEDED",
            "processing_error": "PROCESSING_ERROR",
            "captcha_required": "CAPTCHA_REQUIRED",
            "rate limit": "RATE_LIMITED",
            "session expired": "SESSION_EXPIRED",
            "3d_secure_required": "3D_SECURE_REQUIRED",
            "suspected fraud": "FRAUD_DETECTED",
            "timeout": "TIMEOUT_ERROR",
            "connection error": "CONNECTION_ERROR",
        }

    def parse_binlist_net(self, data):
        scheme = data.get('scheme', 'N/A').upper()
        if scheme == 'N/A':
            scheme = data.get('brand', 'N/A').upper()

        card_type = data.get('type', 'N/A').upper()
        brand = data.get('brand', 'N/A')
        bank_name = data.get('bank', {}).get('name', 'N/A').upper()
        country_name = data.get('country', {}).get('name', 'N/A')
        country_code = data.get('country', {}).get('alpha2', 'N/A')

        if country_name:
            country_name = country_name.replace('(the)', '').strip().upper()

        brand_display = brand.upper() if brand != 'N/A' else 'N/A'
        flag_emoji = self.get_country_emoji(country_code)

        return {
            'scheme': scheme,
            'type': card_type,
            'brand': brand_display,
            'bank': bank_name,
            'country': country_name,
            'country_code': country_code,
            'emoji': flag_emoji
        }

    def parse_antipublic(self, data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return {
                    'scheme': 'N/A',
                    'type': 'N/A',
                    'brand': 'N/A',
                    'bank': 'N/A',
                    'country': 'N/A',
                    'country_code': 'N/A',
                    'emoji': '🏳️'
                }

        country_code = data.get('country', 'N/A')
        country_name = data.get('country_name', country_code)
        flag_emoji = data.get('country_flag', '🏳️')

        if country_name:
            country_name = country_name.replace('(the)', '').strip().upper()

        if flag_emoji == '🏳️' or flag_emoji == 'N/A':
            if country_code != 'N/A' and len(country_code) == 2:
                flag_emoji = self.get_country_emoji(country_code)

        return {
            'scheme': data.get('brand', 'N/A').upper(),
            'type': data.get('type', 'N/A').upper(),
            'brand': data.get('brand', 'N/A').upper(),
            'bank': data.get('bank', 'N/A').upper(),
            'country': country_name,
            'country_code': country_code,
            'emoji': flag_emoji
        }

    def get_country_emoji(self, country_code):
        """Hardcoded country emoji mapping"""
        country_emojis = {
            'US': '🇺🇸', 'GB': '🇬🇧', 'CA': '🇨🇦', 'AU': '🇦🇺', 'DE': '🇩🇪',
            'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'JP': '🇯🇵', 'CN': '🇨🇳',
            'IN': '🇮🇳', 'BR': '🇧🇷', 'MX': '🇲🇽', 'RU': '🇷🇺', 'KR': '🇰🇷',
            'NL': '🇳🇱', 'CH': '🇨🇭', 'SE': '🇸🇪', 'NO': '🇳🇴', 'DK': '🇩🇰',
            'FI': '🇫🇮', 'PL': '🇵🇱', 'TR': '🇹🇷', 'AE': '🇦🇪', 'SA': '🇸🇦',
            'SG': '🇸🇬', 'MY': '🇲🇾', 'TH': '🇹🇭', 'ID': '🇮🇩', 'PH': '🇵🇭',
            'VN': '🇻🇳', 'BD': '🇧🇩', 'PK': '🇵🇰', 'NG': '🇳🇬', 'ZA': '🇿🇦'
        }
        return country_emojis.get(country_code.upper() if country_code else 'N/A', '🏳️')

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

        default_response = {
            'scheme': 'N/A',
            'type': 'N/A',
            'brand': 'N/A',
            'bank': 'N/A',
            'country': 'N/A',
            'country_code': 'N/A',
            'emoji': '🏳️'
        }

        for service in self.bin_services:
            try:
                url = service['url'].format(bin=bin_number)
                headers = service['headers']

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, headers=headers)

                    if response.status_code == 200:
                        data = response.json()
                        result = service['parser'](data)
                        
                        if result['emoji'] == '🏳️' and result['country_code'] != 'N/A':
                            result['emoji'] = self.get_country_emoji(result['country_code'])

                        self.bin_cache[bin_number] = result
                        return result
            except Exception as e:
                logger.warning(f"{service['name']} failed: {e}")
                continue

        self.bin_cache[bin_number] = default_response
        return default_response

    def generate_random_info(self):
        """Generate random user info"""
        first_names = ['John', 'Michael', 'David', 'James', 'Robert', 'William',
                      'Mary', 'Jennifer', 'Linda', 'Patricia', 'Elizabeth', 'Susan']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Miller',
                     'Davis', 'Garcia', 'Rodriguez', 'Wilson', 'Martinez']
        
        first = random.choice(first_names)
        last = random.choice(last_names)
        
        # Generate email
        email_patterns = [
            f"{first.lower()}.{last.lower()}{random.randint(1, 999)}@gmail.com",
            f"{first.lower()}{last.lower()}{random.randint(1, 99)}@outlook.com",
            f"{last.lower()}.{first.lower()}{random.randint(1, 9)}@yahoo.com"
        ]
        email = random.choice(email_patterns)
        
        # Generate phone
        area_codes = ['201', '202', '203', '205', '206', '207', '208', '209']
        area = random.choice(area_codes)
        prefix = random.randint(200, 999)
        line = random.randint(1000, 9999)
        phone = f"+1{area}{prefix}{line}"
        
        return {
            'fname': first,
            'lname': last,
            'email': email,
            'phone': phone,
            'address1': self.fixed_address['address1'],
            'city': self.fixed_address['city'],
            'state': self.fixed_address['state'],
            'state_short': self.fixed_address['state_short'],
            'zip': self.fixed_address['zip'],
            'country': self.fixed_address['country']
        }

    def detect_error_type(self, error_message):
        """Detect Shopify error type from error message"""
        if not error_message:
            return "UNKNOWN_ERROR"
        
        error_lower = error_message.lower()
        
        for pattern, error_type in self.shopify_errors.items():
            if pattern in error_lower:
                return error_type
        
        # Check for specific patterns
        if "declined" in error_lower:
            return "CARD_DECLINED"
        elif "cvv" in error_lower or "security code" in error_lower:
            return "INCORRECT_CVC"
        elif "expired" in error_lower:
            return "EXPIRED_CARD"
        elif "invalid" in error_lower:
            return "INVALID_CARD"
        elif "fund" in error_lower:
            return "INSUFFICIENT_FUNDS"
        elif "limit" in error_lower:
            return "CREDIT_LIMIT_EXCEEDED"
        
        return "UNKNOWN_ERROR"

    def clean_error_message(self, message):
        """Clean and format error message"""
        if not message:
            return "Unknown error"
        
        # Remove HTML tags
        message = re.sub(r'<[^>]+>', '', message).strip()
        
        # Remove common prefixes
        prefixes = [
            "error: ", "sorry, ", "payment failed: ", "transaction failed: ",
            "there was an error: ", "we're sorry, ", "unable to process: "
        ]
        
        for prefix in prefixes:
            if message.lower().startswith(prefix.lower()):
                message = message[len(prefix):].strip()
                break
        
        # Capitalize first letter
        if message:
            message = message[0].upper() + message[1:]
        
        return message

    async def human_delay(self, min_delay=1, max_delay=3):
        """Simulate human delay between actions"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    async def browse_store(self, client):
        """Simple store access"""
        try:
            logger.step(1, 8, "Accessing store...")
            
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            
            response = await client.get(self.base_url, headers=headers, timeout=30.0, follow_redirects=True)
            
            if response.status_code == 200:
                logger.success("Store accessed successfully")
                return True, None
            else:
                return False, f"Store access failed: {response.status_code}"
                
        except Exception as e:
            return False, f"Store browsing error: {str(e)}"

    async def add_to_cart_and_get_checkout(self, client):
        """Add product to cart and get checkout - SIMPLE VPS-FRIENDLY METHOD"""
        try:
            logger.step(2, 8, "Adding to cart...")
            
            # First try to get product info
            try:
                products_url = f"{self.base_url}/products.json"
                response = await client.get(products_url, timeout=30.0)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('products'):
                        product = data['products'][0]
                        variant = product['variants'][0] if product.get('variants') else None
                        if variant:
                            self.variant_id = str(variant['id'])
                            logger.info(f"Found product variant: {self.variant_id}")
            except:
                pass  # Use default variant_id
            
            # Add to cart
            add_url = f"{self.base_url}/cart/add.js"
            
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': self.base_url,
                'Referer': self.product_url,
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            form_data = {'id': self.variant_id, 'quantity': 1}
            
            response = await client.post(add_url, data=form_data, headers=headers, timeout=30.0)
            
            if response.status_code not in [200, 201]:
                # Try simple form POST as fallback
                add_url = f"{self.base_url}/cart/add"
                headers = {
                    'User-Agent': self.user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': self.base_url,
                    'Referer': self.product_url
                }
                response = await client.post(add_url, data=form_data, headers=headers, timeout=30.0, follow_redirects=True)
            
            logger.success("Product added to cart")
            
            # Get cart data
            logger.step(3, 8, "Getting cart data...")
            cart_url = f"{self.base_url}/cart.js"
            headers = {
                'User-Agent': self.user_agent,
                'Accept': '*/*',
                'Referer': f"{self.base_url}/cart"
            }
            
            response = await client.get(cart_url, headers=headers, timeout=30.0)
            
            if response.status_code == 200:
                cart_data = response.json()
                self.cart_token = cart_data.get("token")
                if self.cart_token:
                    logger.success(f"Got cart token: {self.cart_token[:20]}...")
                else:
                    self.cart_token = f"cart_{int(time.time())}_{random.randint(1000, 9999)}"
                    logger.warning(f"Using generated cart token: {self.cart_token}")
            
            # Go to checkout page
            logger.step(4, 8, "Loading checkout page...")
            checkout_url = f"{self.base_url}/checkout"
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Referer': f"{self.base_url}/cart"
            }
            
            response = await client.get(checkout_url, headers=headers, timeout=30.0, follow_redirects=True)
            
            if response.status_code == 200:
                # Extract session token from page
                page_content = response.text
                
                # Try to extract session token
                patterns = [
                    'session-token" content="', '"',
                    'serialized-session-token" content="&quot;', '&quot;"',
                    '"sessionToken":"', '"',
                    'data-session-token="', '"'
                ]
                
                for i in range(0, len(patterns), 2):
                    token = find_between(page_content, patterns[i], patterns[i+1])
                    if token and len(token) > 20:
                        self.x_checkout_one_session_token = token
                        logger.success(f"Extracted session token: {token[:20]}...")
                        break
                
                if not self.x_checkout_one_session_token:
                    # Generate a token if not found
                    chars = string.ascii_letters + string.digits + "-_"
                    self.x_checkout_one_session_token = ''.join(random.choice(chars) for _ in range(100))
                    logger.warning(f"Generated session token: {self.x_checkout_one_session_token[:20]}...")
                
                logger.success("Checkout page loaded")
                return True, None
            else:
                return False, f"Checkout page failed: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Cart/checkout error: {str(e)}")
            # Generate tokens anyway to continue
            self.cart_token = f"cart_{int(time.time())}_{random.randint(1000, 9999)}"
            chars = string.ascii_letters + string.digits + "-_"
            self.x_checkout_one_session_token = ''.join(random.choice(chars) for _ in range(100))
            return True, None  # Continue despite error

    async def create_payment_session(self, client, cc, mes, ano, cvv, user_info):
        """Create payment session via Shopify Payments API"""
        try:
            logger.step(5, 8, "Creating payment session...")
            
            url = "https://checkout.pci.shopifyinc.com/sessions"
            
            headers = {
                'authority': 'checkout.pci.shopifyinc.com',
                'accept': 'application/json',
                'content-type': 'application/json',
                'origin': 'https://checkout.pci.shopifyinc.com',
                'referer': 'https://checkout.pci.shopifyinc.com/',
                'user-agent': self.user_agent
            }
            
            json_data = {
                'credit_card': {
                    'number': cc.replace(' ', ''),
                    'month': int(mes),
                    'year': int(ano[-2:]),
                    'verification_value': cvv,
                    'name': f"{user_info['fname']} {user_info['lname']}",
                },
                'payment_session_scope': 'meta-app-prod-store-1.myshopify.com',
            }
            
            logger.debug_response(f"Creating payment session for card: {cc[:6]}XXXXXX{cc[-4:]}")
            
            response = await client.post(url, headers=headers, json=json_data, timeout=30.0)
            
            if response.status_code == 200:
                session_data = response.json()
                
                if "id" in session_data:
                    session_id = session_data["id"]
                    logger.success(f"Payment session created: {session_id}")
                    
                    # Check for errors
                    if session_data.get("error") or session_data.get("errors"):
                        error_info = session_data.get("error") or session_data.get("errors")
                        error_type = self.detect_error_type(str(error_info))
                        return False, f"{error_type}: {error_info}"
                    
                    return True, session_id
                else:
                    return False, "CARD_DECLINED: No session ID returned"
            else:
                return False, f"CARD_DECLINED: Payment session failed with status {response.status_code}"
                
        except Exception as e:
            error_type = self.detect_error_type(str(e))
            return False, f"{error_type}: {str(e)[:100]}"

    async def submit_payment(self, client, session_id, user_info):
        """Submit payment via GraphQL"""
        try:
            logger.step(6, 8, "Submitting payment...")
            
            graphql_url = f"{self.base_url}/checkouts/internal/graphql/persisted?operationName=SubmitForCompletion"
            
            graphql_headers = {
                'authority': 'meta-app-prod-store-1.myshopify.com',
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'origin': self.base_url,
                'referer': f"{self.base_url}/checkouts/cn/{self.cart_token or 'default'}/en-us",
                'user-agent': self.user_agent,
                'x-checkout-one-session-token': self.x_checkout_one_session_token,
                'x-checkout-web-deploy-stage': 'production',
                'x-checkout-web-server-handling': 'fast',
                'x-checkout-web-source-id': self.cart_token or 'default',
                'shopify-checkout-client': 'checkout-web/1.0'
            }
            
            # Simplified GraphQL payload
            graphql_payload = {
                "operationName": "SubmitForCompletion",
                "variables": {
                    "input": {
                        "sessionInput": {
                            "sessionToken": self.x_checkout_one_session_token
                        },
                        "queueToken": self.cart_token or f"queue_{int(time.time())}",
                        "payment": {
                            "paymentLines": [
                                {
                                    "paymentMethod": {
                                        "directPaymentMethod": {
                                            "paymentMethodIdentifier": "direct",
                                            "sessionId": session_id,
                                            "billingAddress": {
                                                "streetAddress": {
                                                    "address1": user_info['address1'],
                                                    "address2": "",
                                                    "city": user_info['city'],
                                                    "countryCode": user_info['country'],
                                                    "postalCode": user_info['zip'],
                                                    "firstName": user_info['fname'],
                                                    "lastName": user_info['lname'],
                                                    "zoneCode": user_info['state_short'],
                                                    "phone": user_info['phone']
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        },
                        "buyerIdentity": {
                            "contactInfoV2": {
                                "emailOrSms": {
                                    "value": user_info['email']
                                }
                            }
                        }
                    },
                    "attemptToken": f"{self.cart_token or 'attempt'}-{random.random()}"
                },
                "id": "d32830e07b8dcb881c73c771b679bcb141b0483bd561eced170c4feecc988a59"
            }
            
            response = await client.post(graphql_url, headers=graphql_headers, json=graphql_payload, timeout=30.0)
            
            if response.status_code == 200:
                result_data = response.json()
                
                # Check for success
                if 'data' in result_data:
                    completion = result_data['data'].get('submitForCompletion', {})
                    
                    if completion.get('__typename') in ['SubmitSuccess', 'SubmittedForCompletion']:
                        logger.success("Payment submitted successfully!")
                        return True, "Payment submitted successfully"
                    
                    if 'errors' in completion and completion['errors']:
                        error_msg = completion['errors'][0].get('localizedMessage', 'Payment rejected')
                        error_type = self.detect_error_type(error_msg)
                        return False, f"{error_type}: {error_msg}"
                
                # Check for direct errors
                if 'errors' in result_data:
                    error_msg = result_data['errors'][0].get('message', 'GraphQL error')
                    error_type = self.detect_error_type(error_msg)
                    return False, f"{error_type}: {error_msg}"
                
                return True, "Payment processed"
                
            else:
                return False, f"SERVER_ERROR: GraphQL request failed: {response.status_code}"
                
        except Exception as e:
            error_type = self.detect_error_type(str(e))
            return False, f"{error_type}: GraphQL error: {str(e)[:100]}"

    async def check_card(self, card_details, username, user_data):
        """Main card checking method"""
        start_time = time.time()
        logger.info(f"Starting Shopify Charge check...")
        
        try:
            # Parse card details
            cc_parts = card_details.split('|')
            if len(cc_parts) < 4:
                return await self.format_response("", "", "", "", "ERROR", "Invalid card format. Use: CC|MM|YY|CVV", username, time.time()-start_time, user_data)

            cc = cc_parts[0].strip().replace(" ", "")
            mes = cc_parts[1].strip()
            ano = cc_parts[2].strip()
            cvv = cc_parts[3].strip()

            # Validate card details
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

            # Get BIN info
            bin_info = await self.get_bin_info(cc)
            logger.bin_info(f"BIN: {cc[:6]} | {bin_info['scheme']} - {bin_info['type']} | {bin_info['bank']} | {bin_info['country']} [{bin_info['emoji']}]")

            # Create HTTP client WITHOUT proxy for stability
            client_params = {
                'timeout': 30.0,
                'follow_redirects': True,
                'limits': httpx.Limits(max_keepalive_connections=5, max_connections=10)
            }
            
            # Don't use proxy to avoid connection issues
            # if self.current_proxy and PROXY_ENABLED:
            #     client_params['proxy'] = self.current_proxy

            async with httpx.AsyncClient(**client_params) as client:
                # Step 1: Browse store
                success, error = await self.browse_store(client)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Store access failed: {error}", username, time.time()-start_time, user_data, bin_info)

                await self.human_delay(1, 2)

                # Step 2-4: Add to cart and get checkout
                success, error = await self.add_to_cart_and_get_checkout(client)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", f"Cart/checkout failed: {error}", username, time.time()-start_time, user_data, bin_info)

                await self.human_delay(1, 2)

                # Step 5: Generate user info
                user_info = self.generate_random_info()
                logger.user(f"User: {user_info['fname']} {user_info['lname']} | Email: {user_info['email']}")

                # Step 6: Create payment session
                success, session_result = await self.create_payment_session(client, cc, mes, ano, cvv, user_info)
                if not success:
                    elapsed_time = time.time() - start_time
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", session_result, username, elapsed_time, user_data, bin_info)

                session_id = session_result
                logger.success(f"Payment session created: {session_id}")

                await self.human_delay(1, 2)

                # Step 7: Submit GraphQL payment
                success, payment_result = await self.submit_payment(client, session_id, user_info)
                
                elapsed_time = time.time() - start_time
                
                if success:
                    logger.success(f"Payment successful in {elapsed_time:.2f}s")
                    return await self.format_response(cc, mes, ano, cvv, "APPROVED", "Successfully Charged", username, elapsed_time, user_data, bin_info)
                else:
                    logger.error(f"Payment failed: {payment_result}")
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", payment_result, username, elapsed_time, user_data, bin_info)

        except httpx.TimeoutException:
            logger.error("Request timeout")
            elapsed_time = time.time() - start_time
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "TIMEOUT_ERROR: Request timeout", username, elapsed_time, user_data, bin_info)
        except httpx.ConnectError:
            logger.error("Connection error")
            elapsed_time = time.time() - start_time
            return await self.format_response(cc, mes, ano, cvv, "ERROR", "CONNECTION_ERROR: Connection failed", username, elapsed_time, user_data, bin_info)
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            elapsed_time = time.time() - start_time
            error_type = self.detect_error_type(str(e))
            return await self.format_response(cc, mes, ano, cvv, "ERROR", f"{error_type}: {str(e)[:80]}", username, elapsed_time, user_data, bin_info)

    async def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None):
        """Format response message - KEEPING ORIGINAL UI FORMAT"""
        if bin_info is None:
            bin_info = await self.get_bin_info(cc)

        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🧑")

        # Clean error message
        if ":" in message:
            error_parts = message.split(":", 1)
            if len(error_parts) > 1:
                error_type = error_parts[0].strip()
                error_msg = error_parts[1].strip()
                message_display = f"{error_type}: {error_msg}"
            else:
                message_display = message
        else:
            message_display = message

        if status == "APPROVED":
            status_emoji = "✅"
            status_text = "APPROVED"
        elif "CARD_DECLINED" in message or "DECLINED" in message.upper():
            status_emoji = "❌"
            status_text = "DECLINED"
        elif "3D_SECURE" in message or "AUTHENTICATION" in message.upper():
            status_emoji = "🔄"
            status_text = "3D SECURE"
        elif "CAPTCHA" in message:
            status_emoji = "🤖"
            status_text = "CAPTCHA"
        elif "FRAUD" in message:
            status_emoji = "🚫"
            status_text = "FRAUD"
        elif "INSUFFICIENT" in message:
            status_emoji = "💰"
            status_text = "INSUFFICIENT FUNDS"
        else:
            status_emoji = "❌"
            status_text = "DECLINED"

        clean_name = re.sub(r'[↑↳«~∞🌀]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        bank_info = bin_info['bank'].upper() if bin_info['bank'] != 'N/A' else 'N/A'

        response = f"""<b>「$cmd → /sh」| <b>WAYNE</b> </b>
┃┃┃┃┃┃┃┃┃┃┃┃┃
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Shopify Charge
<b>[•] Status-</b> <code>{status_text} {status_emoji}</code>
<b>[•] Response-</b> <code>{message_display}</code>
┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃
<b>[+] Bin:</b> <code>{cc[:6]}</code>  
<b>[+] Info:</b> <code>{bin_info['scheme']} - {bin_info['type']} - {bin_info['brand']}</code>
<b>[+] Bank:</b> <code>{bank_info}</code> 🏦
<b>[+] Country:</b> <code>{bin_info['country']}</code> [{bin_info['emoji']}]
┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃
<b>[🛒] Checked By:</b> {user_display}
<b>[🔧] Dev ➤</b> <b><i>DADYY</i></b>
┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃
<b>[🛒] T/t:</b> <code>{elapsed_time:.2f} ⚡</code> |<b>P/x:</b> <code>Live ♥️</code></b>"""

        return response

# Command handler
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
            await message.reply("""<pre>↳ User Banned</pre>
┃┃┃┃┃┃┃┃┃┃┃┃┃
↶ <b>Message</b>: You have been banned from using this bot.
↶ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
┃┃┃┃┃┃┃┃┃┃┃┃┃""")
            return

        # Load user data
        users = load_users()
        user_id_str = str(user_id)
        if user_id_str not in users:
            await message.reply("""<pre>📜 Registration Required</pre>
┃┃┃┃┃┃┃┃┃┃┃┃┃
↶ <b>Message</b>: You need to register first with /register
↶ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
┃┃┃┃┃┃┃┃┃┃┃┃┃""")
            return

        user_data = users[user_id_str]
        user_plan = user_data.get("plan", {})
        plan_name = user_plan.get("plan", "Free")

        # Check cooldown (owner is automatically skipped in check_cooldown function)
        can_use, wait_time = check_cooldown(user_id, "sh")
        if not can_use:
            await message.reply(f"""<pre>⏱️ Cooldown Active</pre>
┃┃┃┃┃┃┃┃┃┃┃┃┃
↶ <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
↶ <b>Your Plan:</b> <code>{plan_name}</code>
↶ <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
┃┃┃┃┃┃┃┃┃┃┃┃┃""")
            return

        args = message.text.split()
        if len(args) < 2:
            if charge_processor:
                await message.reply(charge_processor.get_usage_message(
                    "sh", 
                    "Shopify Charge",
                    "4111111111111111|12|2025|123"
                ))
            else:
                await message.reply("""<pre>#WAYNE ━[SHOPIFY CHARGE]━━</pre>
┃┃┃┃┃┃┃┃┃┃┃┃┃
↶ <b>Command</b>: <code>/sh</code> or <code>.sh</code> or <code>$sh</code>
↶ <b>Usage</b>: <code>/sh cc|mm|yy|cvv</code>
↶ <b>Example</b>: <code>/sh 4111111111111111|12|2025|123</code>
┃┃┃┃┃┃┃┃┃┃┃┃┃
<b>~ Note:</b> <code>Charges via Shopify gateway (Deducts 2 credits AFTER check completes)</code>
<b>~ Note:</b> <code>Free users can use in authorized groups with credit deduction</code>
<b>~ Store:</b> <code>meta-app-prod-store-1.myshopify.com</code>
<b>~ Product:</b> <code>retailer-id-fix-no-mapping</code>
<b>~ Address:</b> <code>8 Log Pond Drive, Horsham PA 19044</code>
<b>~ Shipping:</b> <code>Local Pickup</code>
<b>~ Tip:</b> <code>None</code>""")
            return

        card_details = args[1].strip()

        cc_parts = card_details.split('|')
        if len(cc_parts) < 4:
            await message.reply("""<pre>❌ Invalid Format</pre>
┃┃┃┃┃┃┃┃┃┃┃┃┃
↶ <b>Message</b>: Invalid card format.
↶ <b>Correct Format</b>: <code>cc|mm|yy|cvv</code>
↶ <b>Example</b>: <code>4111111111111111|12|2025|123</code>
┃┃┃┃┃┃┃┃┃┃┃┃┃""")
            return

        cc = cc_parts[0]
        mes = cc_parts[1]
        ano = cc_parts[2]
        cvv = cc_parts[3]

        # Show processing message
        processing_msg = await message.reply(
            charge_processor.get_processing_message(
                cc, mes, ano, cvv, username, plan_name, 
                "Shopify Charge", "sh"
            ) if charge_processor else f"""<b>「$cmd → /sh」| <b>WAYNE</b> </b>
┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Shopify Charge
<b>[•] Status-</b> Processing... ⏱️
┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
<b>[+] Store:</b> meta-app-prod-store-1.myshopify.com
┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃
<b>Checking card... Please wait.</b>"""
        )

        # Create checker instance
        checker = ShopifyChargeChecker(user_id)

        # Process command through universal charge processor
        if charge_processor:
            success, result, credits_deducted = await charge_processor.execute_charge_command(
                user_id,                    # positional
                checker.check_card,         # positional
                card_details,               # check_args[0]
                username,                   # check_args[1]
                user_data,                  # check_args[2]
                credits_needed=2,           # keyword
                command_name="sh",          # keyword
                gateway_name="Shopify Charge"  # keyword
            )

            await processing_msg.edit_text(result, disable_web_page_preview=True)
        else:
            # Fallback to old method if charge_processor not available
            result = await checker.check_card(card_details, username, user_data)
            await processing_msg.edit_text(result, disable_web_page_preview=True)

    except Exception as e:
        error_msg = str(e)[:150]
        await message.reply(f"""<pre>❌ Command Error</pre>
┃┃┃┃┃┃┃┃┃┃┃┃┃
↶ <b>Message</b>: An error occurred while processing your request.
↶ <b>Error</b>: <code>{error_msg}</code>
↶ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
┃┃┃┃┃┃┃┃┃┃┃┃┃""")
