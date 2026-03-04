# BOT/gates/mass/masscharge012.py

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
from BOT.gates.charge.scharge012 import StripeCharge012Checker, logger, load_users, is_user_banned, check_cooldown, get_user_plan
from BOT.helper.permissions import auth_and_free_restricted
from BOT.helper.Admins import is_command_disabled, get_command_offline_message
from BOT.gc.credit import deduct_credit, get_user_credits, has_sufficient_credits, charge_processor
from BOT.helper.filter import extract_cards
from BOT.tools.proxy import PROXY_SYSTEM_AVAILABLE

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
    
    # Remove the command part
    # Split by lines
    lines = full_text.split('\n')
    
    # Skip the first line if it contains the command
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Check if this line contains the command
        if i == 0 and any(line.startswith(prefix) for prefix in ['/mxx', '.mxx', '$mxx']):
            # This is the command line, extract content after command
            parts = line.split()
            if len(parts) > 1:
                # There might be cards on the same line
                remaining_text = ' '.join(parts[1:]).strip()
                if remaining_text:
                    # Extract cards from this text
                    all_cards, unique_cards = extract_cards(remaining_text)
                    card_list.extend(unique_cards)
            continue
        
        # Regular line - extract cards from this line
        if line:
            all_cards, unique_cards = extract_cards(line)
            card_list.extend(unique_cards)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_cards = []
    for card in card_list:
        if card not in seen:
            seen.add(card)
            unique_cards.append(card)
    
    return unique_cards

class MassStripeCharge012Checker:
    def __init__(self):
        self.retry_count = 0
        self.max_retries = 2  # Maximum retries per card when rate limited
        
    def format_mass_card_response(self, cc, mes, ano, cvv, status, message, username, elapsed_time, user_data, bin_info, proxy_status="Live ⚡️"):
        """Format individual card response for mass check with /mxx in header"""
        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🧿")

        # Trim message for display
        raw_message = str(message).lower()
        trimmed_message = message

        # Determine status based on message content
        status_flag = "Declined ❌"
        status_emoji = "❌"

        if status == "APPROVED":
            status_flag = "Approved ✅"
            status_emoji = "✅"
        elif "3d secure" in raw_message or "3ds" in raw_message or "authentication required" in raw_message:
            status_flag = "3D Secure ❎"
            status_emoji = "❎"
        elif status == "DECLINED":
            status_flag = "Declined ❌"
            status_emoji = "❌"

        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        bank_info = bin_info['bank'].upper() if bin_info['bank'] != 'N/A' else 'N/A'

        response = f"""<b>「$cmd → /mxx」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> Stripe Charge €0.12 ♻️
<b>[•] Status-</b> <code>{status_flag}</code>
<b>[•] Response-</b> <code>{trimmed_message}</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Bin:</b> <code>{cc[:6]}</code>  
<b>[+] Info:</b> <code>{bin_info['scheme']} - {bin_info['type']} - {bin_info['brand']}</code>
<b>[+] Bank:</b> <code>{bank_info}</code> 🏦
<b>[+] Country:</b> <code>{bin_info['country']}</code> [{bin_info['emoji']}]
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[ﾒ] Checked By:</b> {user_display}
<b>[ϟ] Dev ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] T/t:</b> <code>{elapsed_time:.2f} 𝐬</code> |<b>P/x:</b> <code>{proxy_status}</code></b>"""

        return response
    
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
            
            # Format month with leading zero if needed
            if len(mes) == 1:
                mes = f"0{mes}"
            
            # Format year if needed
            if len(ano) == 2:
                ano = '20' + ano
                
            return cc, mes, ano, cvv
        except:
            return "", "", "", ""
    
    def get_processing_message_dynamic(self, total_cards, checked, hits, declines, errors, username, user_plan):
        """Get dynamic processing message that updates in real-time"""
        left = total_cards - checked
        
        return f"""<b>「$cmd → /mxx」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
🔄 <b>Mass Stripe Charge €0.12</b>

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
        badge = user_data.get("plan", {}).get("badge", "🧿")
        
        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        
        # Delete the processing message
        try:
            await processing_msg.delete()
        except:
            pass
        
        # Send final summary (ONLY ONCE, no duplicate footer)
        summary = f"""<b>「$cmd → /mxx」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Gateway -</b> Stripe Charge €0.12 Mass
<b>[•] Status -</b> <code>Complete ✅</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Results:</b> ✅ {successful} | ❌ {failed}
<b>[+] Total Cards:</b> <code>{total_cards}</code>
<b>[+] Credits Used:</b> <code>5</code>
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
        """
        Format collective response when total cards <= 5
        FIXED: Now properly extracts and displays card details
        """
        user_id = user_data.get("user_id", "Unknown")
        first_name = html.escape(user_data.get("first_name", "User"))
        badge = user_data.get("plan", {}).get("badge", "🧿")
        
        clean_name = re.sub(r'[↯⌁«~∞🍁]', '', first_name).strip()
        user_display = f"「{badge}」{clean_name}"
        
        # Start with header (ONLY ONCE)
        response = f"""<b>「$cmd → /mxx」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Gateway -</b> Stripe Charge €0.12 Mass
<b>[•] Status -</b> <code>Complete ✅</code>
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Results:</b> ✅ {successful} | ❌ {failed}
<b>[+] Total Cards:</b> <code>{total_cards}</code>
<b>[+] Credits Used:</b> <code>5</code> 
━━━━━━━━━━━━━━━

"""
        
        # Process each result to extract ONLY the card details
        for idx, result in enumerate(results):
            # Split the result into lines
            lines = result.split('\n')
            
            # Extract the card information block (lines between the first separator and the Checked By line)
            card_block = []
            in_card_block = False
            
            for line in lines:
                # Start collecting after we hit the separator after header
                if line == '━━━━━━━━━━━━━━━' and not in_card_block:
                    in_card_block = True
                    continue
                
                # Stop collecting when we hit the Checked By line
                if '[ﾒ] Checked By:' in line:
                    break
                
                # If we're in the card block and line is not empty, add it
                if in_card_block and line.strip():
                    # Skip the first separator line that might have been captured
                    if line == '━━━━━━━━━━━━━━━':
                        continue
                    card_block.append(line)
            
            # Join the card block and add to response
            if card_block:
                # Add a separator between cards (except for the first one)
                if idx > 0:
                    response += "\n"
                
                # Join the card lines
                card_text = '\n'.join(card_block)
                response += card_text + "\n"
        
        # Add FINAL summary (ONLY ONCE at the very end)
        response += f"""━━━━━━━━━━━━━━━
<b>[ﾒ] Checked By:</b> {user_display}
<b>[ϟ] Dev ➺</b> <b><i>DADYY</i></b>
━━━━━━━━━━━━━━━
<b>[ﾒ] Time:</b> <code>{elapsed_time:.2f} 𝐬</code> |<b>P/x:</b> <code>Mass ⚡️</code></b>"""
        
        return response

@Client.on_message(filters.command(["mxx", ".mxx", "$mxx"]))
@auth_and_free_restricted
async def handle_mass_stripe_charge_012(client: Client, message: Message):
    file_path = None  # Track downloaded file path for cleanup
    approved_sent = 0  # Track how many approved cards we've sent
    
    try:
        user_id = message.from_user.id
        username = message.from_user.username or str(user_id)
        
        # Check if command is disabled
        command_text = message.text.split()[0] if message.text else ""
        command_name = command_text.lstrip('/.$') if command_text else "mxx"
        
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
        
        # Check if proxy system is available
        if not PROXY_SYSTEM_AVAILABLE:
            await message.reply("""<pre>❌ Proxy System Unavailable</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Proxy system is not available.
⟐ <b>Solution</b>: <code>Ensure BOT/tools/proxy.py exists and is working</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
            return
        
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

• Reply to a text file or message containing cards with /mxx

<code>/mxx
5414963811565512|09|28|822
4221352001240530|12|26|050</code>
━━━━━━━━━━━━━
⟐ <b>Note:</b> <code>Cards will be auto-filtered from any format</code>
━━━━━━━━━━━━━""")
            return
        
        card_count = len(card_list)
        
        # ========== PLAN-BASED CARD LIMIT CHECK ==========
        max_allowed = get_card_limit_by_plan(plan_name, user_role)
        
        # Check if card count exceeds plan limit (owner/admin with unlimited pass through)
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
        can_use, wait_time = check_cooldown(user_id, "mxx")
        if not can_use:
            await message.reply(f"""<pre>⏳ Cooldown Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please wait {wait_time:.1f} seconds before using this command again.
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
⟐ <b>Anti-Spam:</b> <code>{user_plan.get('antispam', 15)}s</code>
━━━━━━━━━━━━━""")
            return
        
        # IMPORTANT: Check if user has enough credits for mass charge (5 credits for entire command)
        has_credits, credit_msg = has_sufficient_credits(user_id, 5)
        
        if not has_credits:
            current_credits = get_user_credits(user_id)
            await message.reply(f"""<pre>❌ Insufficient Credits</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You don't have enough credits for mass charge.
⟐ <b>Required:</b> <code>5 credits</code> 
⟐ <b>Available:</b> <code>{current_credits}</code>
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
━━━━━━━━━━━━━""")
            return
        
        # IMPORTANT: Deduct 5 credits BEFORE processing mass charge (ONCE for entire command)
        deduct_success, deduct_msg = deduct_credit(user_id, 5)
        
        if not deduct_success:
            await message.reply(f"""<pre>❌ Credit Deduction Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: {deduct_msg}
━━━━━━━━━━━━━""")
            return
        
        start_time = time.time()
        
        # Create mass checker instance
        mass_checker = MassStripeCharge012Checker()
        
        # Send initial processing message
        processing_msg = await message.reply(
            mass_checker.get_processing_message_dynamic(card_count, 0, 0, 0, 0, username, plan_name)
        )
        
        results = []
        successful = 0
        failed = 0
        errors = 0
        
        # Process each card - EACH CARD NEEDS ITS OWN FRESH CHECKER INSTANCE
        for i, card_details in enumerate(card_list):
            checked = i + 1
            
            # Create fresh checker for each card with user_id for proxy
            try:
                # Create new checker instance for each card (pass user_id for proxy)
                card_checker = StripeCharge012Checker(user_id=user_id)
                
                # Check card using fresh session
                result = await card_checker.check_card(
                    card_details, 
                    username, 
                    user_data
                )
                
                # Store result for potential collective response
                results.append(result)
                
                if "Approved ✅" in result:
                    successful += 1
                    # For >5 cards, send approved cards immediately
                    if card_count > 5:
                        await mass_checker.send_approved_card_immediately(
                            client, message, result, i+1, card_count
                        )
                        approved_sent += 1
                elif "3D Secure ❎" in result:
                    successful += 1  # Count 3D Secure as hit for mass stats
                    # For >5 cards, send approved cards immediately
                    if card_count > 5:
                        await mass_checker.send_approved_card_immediately(
                            client, message, result, i+1, card_count
                        )
                        approved_sent += 1
                elif "Declined ❌" in result:
                    failed += 1
                else:
                    errors += 1
                    
            except Exception as e:
                # Handle individual card error
                cc_part = card_details.split('|')[0] if '|' in card_details else ""
                
                # Create temporary checker for bin info
                temp_checker = StripeCharge012Checker()
                bin_info = await temp_checker.get_bin_info(cc_part)
                
                error_result = mass_checker.format_mass_card_response(
                    cc_part,
                    card_details.split('|')[1] if len(card_details.split('|')) > 1 else "",
                    card_details.split('|')[2] if len(card_details.split('|')) > 2 else "",
                    card_details.split('|')[3] if len(card_details.split('|')) > 3 else "",
                    "ERROR", 
                    f"Check failed: {str(e)[:50]}", 
                    username, 
                    0, 
                    user_data, 
                    bin_info,
                    "Dead 🚫"
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
                except:
                    pass
            
            # Add delay between cards to avoid rate limiting
            if i < len(card_list) - 1:
                await asyncio.sleep(random.uniform(2, 4))
        
        elapsed_time = time.time() - start_time
        
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
            check_cooldown(user_id, "mxx")
            
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