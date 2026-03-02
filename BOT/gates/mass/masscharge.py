# BOT/gates/charge/stripe/masscharge.py

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
import string
import os
from pathlib import Path

# CORRECT IMPORTS based on your structure
from BOT.gates.auth.stripe.stauth import logger, load_users, is_user_banned, check_cooldown, get_user_plan
from BOT.helper.permissions import auth_and_free_restricted
from BOT.helper.Admins import is_command_disabled, get_command_offline_message
from BOT.gc.credit import deduct_credit, get_user_credits, has_sufficient_credits, charge_processor
from BOT.helper.filter import extract_cards
from BOT.gates.charge.stripe.scharge import StripeChargeChecker

# Download directory
DOWNLOAD_DIR = "BOT/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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
    
    # Remove the command part
    # First, extract everything after the command
    lines = full_text.split('\n')
    
    # Process each line
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # For the first line, remove the command prefix if present
        if i == 0:
            # Check for any command prefix and remove it
            for prefix in ['/mxc', '.mxc', '$mxc']:
                if line.startswith(prefix):
                    # Remove the command and any following whitespace
                    line = line[len(prefix):].strip()
                    break
        
        # If there's content after removing command, extract cards
        if line:
            all_cards, unique_cards = extract_cards(line)
            if unique_cards:
                card_list.extend(unique_cards)
                print(f"📝 Found {len(unique_cards)} cards in line: {line[:50]}...")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_cards = []
    for card in card_list:
        if card not in seen:
            seen.add(card)
            unique_cards.append(card)
    
    print(f"📊 Total unique cards extracted: {len(unique_cards)}")
    return unique_cards

class MassStripeChargeChecker:
    def __init__(self):
        self.checker = StripeChargeChecker()
        self.current_client = None
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
            
            # Create new client
            logger.info("🔄 Creating fresh session for charge...")
            self.current_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                http2=True
            )
            
            self.retry_count = 0
            logger.success("✅ New session created successfully")
            return True
                
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
            "session expired",
            "for security",
            "please wait",
            "429",
            "403",
            "timeout",
            "connection"
        ]
        
        error_lower = str(error_message).lower()
        for pattern in rate_limit_patterns:
            if pattern in error_lower:
                return True
        return False
    
    async def check_card_with_session(self, card_details, username, user_data, client=None, retry_count=0):
        """Check card using the charge checker"""
        start_time = time.time()
        
        # Parse card details
        cc, mes, ano, cvv = self.parse_card_details(card_details)
        
        try:
            # Use the StripeChargeChecker's check_card method
            result = await self.checker.check_card(card_details, username, user_data)
            
            # Calculate elapsed time for this card
            elapsed_time = time.time() - start_time
            
            # Format the result to include elapsed time if needed
            return result
                
        except Exception as e:
            # Check if it's a rate limit error in the exception
            if self.is_rate_limit_error(str(e)) and retry_count < self.max_retries:
                logger.info(f"🔄 Rate limit exception, retrying with new session (attempt {retry_count + 1})")
                
                # Retry this card with new session
                result = await self.check_card_with_session(
                    card_details, username, user_data, None, retry_count + 1
                )
                return result
            
            # Not a rate limit error or max retries exceeded
            bin_info = await self.checker.get_bin_info(cc)
            return self.format_mass_card_response(
                cc, mes, ano, cvv, "ERROR", str(e)[:80], 
                username, time.time()-start_time, user_data, bin_info
            )
    
    def format_mass_card_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info):
        """Format individual card response for mass check with /mxc in header - matching scharge.py UI style"""
        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🎭")

        # Determine status emoji based on message content (like in scharge.py)
        raw_message = str(message).lower()

        # Check for success patterns
        success_patterns = [
            "successfully charged",
            "thank you",
            "order placed",
            "approved",
            "success",
            "charged"
        ]

        # Check for 3D Secure patterns
        three_d_patterns = [
            "3d secure",
            "3ds",
            "requires_action",
            "authentication_required",
            "3d_secure"
        ]

        status_flag = "Declined ❌"
        status_emoji = "❌"

        if any(pattern in raw_message for pattern in success_patterns):
            status_flag = "Charged 💺"
            status_emoji = "💺"
        elif "3d secure❎" in raw_message or any(pattern in raw_message for pattern in three_d_patterns):
            status_flag = "3D Secure ❎"
            status_emoji = "❎"
        elif "approved" in status.lower():
            status_flag = "Approved ❎"
            status_emoji = "❎"
        elif "APPROVED" in status:
            status_flag = "APPROVED"
            status_emoji = "✅"

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        bank_info = bin_info['bank'].upper() if bin_info['bank'] != 'N/A' else 'N/A'

        # Format year to 4-digit for display
        display_ano = ano
        if len(ano) == 2:
            display_ano = '20' + ano

        response = f"""<b>「$cmd → /mxc」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{display_ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge 10$ ♻️
<b>[•] Status-</b> <code>{status_flag}</code>
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
    
    def parse_card_details(self, card_details):
        """Parse card details from string - using same format as massau.py (from filter.py)"""
        try:
            cc_parts = card_details.split('|')
            if len(cc_parts) < 4:
                return "", "", "", ""
            
            cc = cc_parts[0].strip().replace(" ", "")
            mes = cc_parts[1].strip()
            ano = cc_parts[2].strip()
            cvv = cc_parts[3].strip()
            
            # Format month with leading zero if needed
            if len(mes) == 1:
                mes = f"0{mes}"
            
            # Format year if needed (use 2-digit year for scharge.py)
            if len(ano) == 4:
                ano = ano[-2:]
                
            return cc, mes, ano, cvv
        except:
            return "", "", "", ""
    
    def get_processing_message_dynamic(self, total_cards, checked, hits, declines, errors, username, user_plan):
        """Get dynamic processing message that updates in real-time"""
        left = total_cards - checked
        
        return f"""<b>「$cmd → /mxc」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
🔄 <b>Mass Stripe Charge (10$)</b>

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
            # result is already a string, no need to await
            await message.reply(result, disable_web_page_preview=True)
            # Small delay to avoid flooding
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
        
        # Send final summary (ONLY ONCE, no duplicate footer)
        summary = f"""<b>「$cmd → /mxc」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Gateway -</b> Stripe Charge Mass (10$)
<b>[•] Status -</b> <code>Complete ✅</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Results:</b> ✅ {successful} | ❌ {failed}
<b>[+] Total Cards:</b> <code>{total_cards}</code>
<b>[+] Credits Used:</b> <code>5</code> (for entire mass check)
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
        """Format collective response when total cards <= 5 (NO duplicate footer)"""
        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🎭")
        
        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        
        # Start with header
        response = f"""<b>「$cmd → /mxc」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Gateway -</b> Stripe Charge Mass (10$)
<b>[•] Status -</b> <code>Complete ✅</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Results:</b> ✅ {successful} | ❌ {failed}
<b>[+] Total Cards:</b> <code>{total_cards}</code>
<b>[+] Credits Used:</b> <code>5</code> (for entire mass check)
━━━━━━━━━━━━━━━
"""
        
        # Add each card result with card number header
        for i, result in enumerate(results):
            response += f"<b>Card {i+1}:</b>\n{result}\n\n"
        
        # Add FINAL summary (ONLY ONCE at the very end)
        response += f"""━━━━━━━━━━━━━━━
<b>[ﾒ] Checked By:</b> {user_display}
<b>[ϟ] Dev ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] Time:</b> <code>{elapsed_time:.2f} 𝐬</code> |<b>P/x:</b> <code>Mass ⚡️</code></b>"""
        
        return response

@Client.on_message(filters.command(["mxc", ".mxc", "$mxc"]))
@auth_and_free_restricted
async def handle_mass_stripe_charge(client: Client, message: Message):
    file_path = None  # Track downloaded file path for cleanup
    approved_sent = 0  # Track how many approved cards we've sent
    
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)
        
        # Check if command is disabled
        command_text = message.text.split()[0] if message.text else ""
        command_name = command_text.lstrip('/.$') if command_text else "mxc"
        
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
• Reply to a text file or message containing cards with /mxc

<b>Format 2 (Multi-line after command):</b>
<code>/mxc
5414963811565512|09|28|822
4221352001240530|12|26|050</code>

<b>Format 3 (Single line):</b>
<code>/mxc 5414963811565512|09|28|822</code>

<b>Format 4 (Multiple cards in one line):</b>
<code>/mxc 5414963811565512|09|28|822 4221352001240530|12|26|050</code>

⟐ <b>Note:</b> <code>Cards will be auto-filtered from any format</code>
━━━━━━━━━━━━━""")
            return
        
        card_count = len(card_list)
        
        # Check cooldown (owner is automatically skipped)
        can_use, wait_time = check_cooldown(user_id, "mxc")
        if not can_use:
            await message.reply(f"""<pre>⏳ Cooldown Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
⟐ <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
━━━━━━━━━━━━━""")
            return
        
        # IMPORTANT: Check if user has enough credits for mass check (5 credits for entire command)
        has_credits, credit_msg = has_sufficient_credits(user_id, 5)
        
        if not has_credits:
            current_credits = get_user_credits(user_id)
            await message.reply(f"""<pre>❌ Insufficient Credits</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You don't have enough credits for mass charge.
⟐ <b>Required:</b> <code>5 credits</code> (for entire mass check)
⟐ <b>Available:</b> <code>{current_credits}</code>
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
━━━━━━━━━━━━━""")
            return
        
        # IMPORTANT: Deduct 5 credits BEFORE processing mass check (ONCE for entire command)
        deduct_success, deduct_msg = deduct_credit(user_id, 5)
        
        if not deduct_success:
            await message.reply(f"""<pre>❌ Credit Deduction Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: {deduct_msg}
━━━━━━━━━━━━━""")
            return
        
        start_time = time.time()
        
        # Create mass checker instance
        mass_checker = MassStripeChargeChecker()
        
        # Send initial processing message
        processing_msg = await message.reply(
            mass_checker.get_processing_message_dynamic(card_count, 0, 0, 0, 0, username, plan_name)
        )
        
        results = []
        successful = 0
        failed = 0
        errors = 0
        
        # Process each card
        for i, card_details in enumerate(card_list):
            checked = i + 1
            
            print(f"🔍 Processing card {i+1}/{card_count}: {card_details}")
            
            # Check card 
            try:
                # Format card details for scharge.py (ensure 2-digit year)
                cc_parts = card_details.split('|')
                if len(cc_parts) >= 4:
                    cc = cc_parts[0].strip().replace(" ", "")
                    mes = cc_parts[1].strip().zfill(2)
                    ano = cc_parts[2].strip()
                    cvv = cc_parts[3].strip()
                    
                    # Format year to 2-digit if needed
                    if len(ano) == 4:
                        ano = ano[-2:]
                    
                    formatted_card = f"{cc}|{mes}|{ano}|{cvv}"
                else:
                    formatted_card = card_details
                
                # Use the charge checker
                result = await mass_checker.checker.check_card(formatted_card, username, user_data)
                
                # Store result for potential collective response
                results.append(result)
                
                # Determine if it's a hit (approved/charged)
                if "Charged 💺" in result or "APPROVED" in result or "3D Secure" in result:
                    successful += 1
                    # For >5 cards, send approved cards immediately
                    if card_count > 5:
                        await mass_checker.send_approved_card_immediately(
                            client, message, result, i+1, card_count
                        )
                        approved_sent += 1
                elif "DECLINED" in result or "Declined" in result:
                    failed += 1
                else:
                    errors += 1
                    
            except Exception as e:
                print(f"❌ Error processing card {card_details}: {str(e)}")
                # Handle individual card error
                cc = card_details.split('|')[0] if '|' in card_details else "Unknown"
                bin_info = await mass_checker.checker.get_bin_info(cc)
                
                # Parse card parts for formatting
                cc_parts = card_details.split('|')
                if len(cc_parts) >= 4:
                    cc = cc_parts[0].strip().replace(" ", "")
                    mes = cc_parts[1].strip().zfill(2)
                    ano = cc_parts[2].strip()
                    cvv = cc_parts[3].strip()
                else:
                    cc, mes, ano, cvv = "Unknown", "00", "00", "000"
                
                error_result = mass_checker.format_mass_card_response(
                    cc, mes, ano, cvv, "ERROR", f"Check failed: {str(e)[:50]}", 
                    username, 0, user_data, bin_info
                )
                results.append(error_result)
                errors += 1
            
            # Update progress message with dynamic stats
            if (i + 1) % 2 == 0 or i == len(card_list) - 1:
                try:
                    await processing_msg.edit_text(
                        mass_checker.get_processing_message_dynamic(
                            card_count, checked, successful, failed, errors, username, plan_name
                        )
                    )
                except Exception as e:
                    print(f"⚠️ Failed to update progress: {e}")
            
            # REDUCED DELAY: 1-2 seconds for faster processing
            if i < len(card_list) - 1:
                await asyncio.sleep(random.uniform(1, 2))
        
        elapsed_time = time.time() - start_time
        
        print(f"✅ Mass charge complete: {successful} hits, {failed} declines, {errors} errors")
        
        # DECISION BASED ON CARD COUNT
        if card_count > 5:
            # For >5 cards: We've already sent approved cards immediately
            # Now just send the final summary
            await mass_checker.send_final_summary(
                client, message, successful, failed + errors, 
                card_count, username, elapsed_time, user_data, processing_msg
            )
        else:
            # For <=5 cards: Send collective response with all cards
            final_response = await mass_checker.format_mass_response_collective(
                results, successful, failed + errors, card_count, username, elapsed_time, user_data
            )
            
            # Update cooldown
            check_cooldown(user_id, "mxc")
            
            # Send final result
            try:
                await processing_msg.edit_text(final_response, disable_web_page_preview=True)
            except Exception as e:
                print(f"Failed to edit message: {e}")
                # If editing fails, send as new message
                try:
                    await message.reply(final_response, disable_web_page_preview=True)
                except Exception as e:
                    print(f"Failed to send mass charge results: {e}")
        
        # Clean up downloaded file if any
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"🗑️ Deleted temporary file: {file_path}")
            except Exception as e:
                print(f"⚠️ Failed to delete file {file_path}: {e}")
                
    except Exception as e:
        error_msg = str(e)[:150]
        print(f"❌ Mass Charge Error: {error_msg}")
        await message.reply(f"""<pre>❌ Mass Charge Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: An error occurred while processing mass charge.
⟐ <b>Error</b>: <code>{error_msg}</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        
        # Clean up downloaded file if any in case of error
        if 'file_path' in locals() and file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
