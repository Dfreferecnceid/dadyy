import json
import random
import string
from datetime import datetime, timedelta
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from BOT.helper.start import USERS_FILE, load_users, save_users, load_owner_id
from BOT.helper.Admins import (
    is_command_disabled, get_command_offline_message,
    is_user_restricted_for_command
)
from BOT.helper.permissions import auth_and_free_restricted

user_redeem_cooldowns = {}
REDEEM_DELAY_SECONDS = 90
REDEEM_PLAN_NAME = "Plus"
REDEEM_BADGE = "🎁"
DEFAULT_BADGE = "🧿"
DEFAULT_ANTISPAM = 15
DEFAULT_MLIMIT = 5

# Plan benefits
PLUS_ANTISPAM = 13
PLUS_CREDIT_BONUS = 200
PLUS_MLIMIT = 10
PLUS_BADGE = "💠"
PLUS_PRIVATE = "on"

OWNER_ID = load_owner_id()
GC_FILE_TXT = "DATA/gift_codes.txt"
GC_FILE_JSON = "DATA/gift_codes.json"

def load_gift_codes():
    """Load gift codes from JSON file"""
    gift_codes = {}
    os.makedirs("DATA", exist_ok=True)

    if os.path.exists(GC_FILE_JSON):
        try:
            with open(GC_FILE_JSON, 'r') as f:
                gift_codes = json.load(f)
            return gift_codes
        except Exception as e:
            print(f"Error loading JSON gift codes: {e}")
            return convert_txt_to_json()

    return convert_txt_to_json()

def convert_txt_to_json():
    """Convert old txt format to new JSON format"""
    gift_codes = {}

    if not os.path.exists(GC_FILE_TXT):
        save_gift_codes(gift_codes)
        return gift_codes

    try:
        with open(GC_FILE_TXT, 'r') as f:
            lines = f.read().splitlines()

        for line in lines:
            if '|' in line:
                code, expiration_date_str = line.split('|')
                gift_codes[code] = {
                    "expires_at": expiration_date_str,
                    "used": False,
                    "used_by": None,
                    "used_at": None,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "days_valid": 0,
                    "plan": "Plus"
                }

        save_gift_codes(gift_codes)
        try:
            os.remove(GC_FILE_TXT)
        except:
            pass

        return gift_codes
    except Exception as e:
        print(f"Error converting txt to JSON: {e}")
        return {}

def save_gift_codes(gift_codes):
    """Save gift codes to JSON file"""
    os.makedirs("DATA", exist_ok=True)
    with open(GC_FILE_JSON, 'w') as f:
        json.dump(gift_codes, f, indent=4)

def get_user_redeemed_codes(user_id: str):
    """Get all codes redeemed by a user"""
    gift_codes = load_gift_codes()
    user_codes = []

    for code, data in gift_codes.items():
        if data.get("used_by") == user_id:
            user_codes.append({
                "code": code,
                "used_at": data.get("used_at"),
                "expires_at": data.get("expires_at"),
                "plan": data.get("plan", "Plus")
            })

    return user_codes

def has_active_plan(user_id: str) -> bool:
    """Check if user has any active plan"""
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    except:
        return False

    user = users.get(str(user_id))
    if not user:
        return False

    user_plan = user.get("plan", {}).get("plan", "Free")
    user_role = user.get("role", "Free")
    
    if user_plan != "Free" or user_role != "Free":
        return True
    
    expires_at = user.get("plan", {}).get("expires_at")
    if expires_at:
        try:
            now = datetime.now()
            expiry_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
            if now <= expiry_dt:
                return True
        except:
            pass
    
    return False

def get_active_plan_info(user_id: str):
    """Get information about user's active plan"""
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    except:
        return None
    
    user = users.get(str(user_id))
    if not user:
        return None
    
    plan_data = user.get("plan", {})
    plan = plan_data.get("plan", "Free")
    expires_at = plan_data.get("expires_at")
    role = user.get("role", "Free")
    
    return {
        "plan": plan,
        "expires_at": expires_at,
        "role": role,
        "is_permanent": expires_at is None and plan != "Free"
    }

def upgrade_user_direct(user_id: str, expires_at: str):
    """Directly upgrade user to Plus plan by writing to file"""
    try:
        # Read users file directly
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
        
        user_id_str = str(user_id)
        if user_id_str not in users:
            print(f"[ERROR] User {user_id_str} not found")
            return False
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get current credits
        current_credits = users[user_id_str].get("plan", {}).get("credits", "0")
        if current_credits != "∞":
            try:
                current_credits = int(current_credits)
                new_credits = current_credits + PLUS_CREDIT_BONUS
            except:
                new_credits = PLUS_CREDIT_BONUS
        else:
            new_credits = "∞"
        
        # Get current keyredeem
        current_keyredeem = users[user_id_str].get("plan", {}).get("keyredeem", 0)
        
        # DIRECTLY update the user data
        if "plan" not in users[user_id_str]:
            users[user_id_str]["plan"] = {}
        
        # Set all plan fields
        users[user_id_str]["plan"]["plan"] = "Plus"
        users[user_id_str]["plan"]["activated_at"] = now
        users[user_id_str]["plan"]["expires_at"] = expires_at
        users[user_id_str]["plan"]["antispam"] = PLUS_ANTISPAM
        users[user_id_str]["plan"]["badge"] = PLUS_BADGE
        users[user_id_str]["plan"]["credits"] = str(new_credits)
        users[user_id_str]["plan"]["private"] = PLUS_PRIVATE
        users[user_id_str]["plan"]["mlimit"] = PLUS_MLIMIT
        users[user_id_str]["plan"]["keyredeem"] = current_keyredeem + 1
        
        # Update role
        users[user_id_str]["role"] = "Plus"
        
        # Write directly back to file
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
        
        print(f"[DEBUG] Successfully upgraded user {user_id_str} to Plus plan")
        print(f"[DEBUG] New plan data: {users[user_id_str]['plan']}")
        
        # Verify the write
        with open(USERS_FILE, 'r') as f:
            verification = json.load(f)
        
        if user_id_str in verification:
            saved_plan = verification[user_id_str].get("plan", {}).get("plan", "Unknown")
            print(f"[DEBUG] Verification - saved plan: {saved_plan}")
            return saved_plan == "Plus"
        
        return True
        
    except Exception as e:
        print(f"[ERROR] in upgrade_user_direct: {e}")
        import traceback
        traceback.print_exc()
        return False

@Client.on_message(filters.command("redeem"))
@auth_and_free_restricted
async def redeem_code_command(client: Client, message: Message):
    """Handle gift code redemption from /gc command"""
    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    users = load_users()
    user_id = str(message.from_user.id)

    if len(message.command) < 2:
        await message.reply("""<pre>#WAYNE ─[REDEEM CODE]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/redeem</code>
⟐ <b>Usage</b>: <code>/redeem &lt;gift_code&gt;</code>
⟐ <b>Example</b>: <code>/redeem WAYNE-DAD-ABCD-EFGH</code>
━━━━━━━━━━━━━
<b>~ Rules:</b>
• FREE users can redeem gift codes
• Users with ACTIVE plans CANNOT redeem codes
• Wait for current plan to expire before redeeming another

<b>~ Note:</b> <code>Gift codes upgrade you to Plus plan for specified days</code>""", reply_to_message_id=message.id)
        return

    code = message.command[1].strip().upper()

    # Check if it's a valid gift code format
    if not code.startswith("WAYNE-DAD-"):
        await message.reply(
            f"""<pre>❌ Invalid Code Format</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Invalid gift code format.
⟐ <b>Correct Format</b>: <code>WAYNE-DAD-XXXX-XXXX</code>
⟐ <b>Your Code</b>: <code>{code}</code>
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    gift_codes = load_gift_codes()

    if code not in gift_codes:
        await message.reply(
            f"""<pre>❌ Code Not Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Gift code <code>{code}</code> not found.
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    code_data = gift_codes[code]

    if code_data["used"]:
        used_by = code_data.get('used_by') or 'Unknown'
        used_at = code_data.get('used_at') or 'Unknown'
        await message.reply(
            f"""<pre>❌ Code Already Used</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Gift code <code>{code}</code> has already been used.
⟐ <b>Used By</b>: <code>{used_by}</code>
⟐ <b>Used At</b>: <code>{used_at}</code>
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    if user_id == OWNER_ID:
        await message.reply(
            """<pre>😄 Owner Notification</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You're the owner! You don't need to redeem gift codes.
⟐ <b>Tip</b>: Use <code>/plans</code> to upgrade users directly.
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    if user_id not in users:
        await message.reply(
            """<pre>❌ Registration Required</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please register first!
⟐ <b>Action</b>: Use <code>/register</code> command to get started.
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    # Check if code is expired
    expires_at = code_data["expires_at"]
    current_time = datetime.now()

    try:
        expiry_time = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
        if current_time > expiry_time:
            await message.reply(
                f"""<pre>❌ Code Expired</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Gift code <code>{code}</code> has expired.
⟐ <b>Expired On</b>: <code>{expires_at}</code>
⟐ <b>Current Time</b>: <code>{current_time.strftime('%Y-%m-%d %H:%M:%S')}</code>
━━━━━━━━━━━━━""",
                reply_to_message_id=message.id
            )
            return

        days_remaining = (expiry_time - current_time).days
        hours_remaining = int((expiry_time - current_time).seconds / 3600)
    except Exception as e:
        days_remaining = "Unknown"
        hours_remaining = "Unknown"

    # Check if user already has an active plan
    if has_active_plan(user_id):
        plan_info = get_active_plan_info(user_id)
        
        if plan_info['is_permanent']:
            await message.reply(
                f"""<pre>❌ Permanent Plan User</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You have a permanent {plan_info['plan']} plan.
⟐ <b>Current Plan</b>: <code>{plan_info['plan']}</code>
⟐ <b>Rule</b>: Permanent plan users cannot redeem gift codes
━━━━━━━━━━━━━""",
                reply_to_message_id=message.id
            )
            return
        else:
            if plan_info['expires_at']:
                try:
                    now = datetime.now()
                    expiry_dt = datetime.strptime(plan_info['expires_at'], "%Y-%m-%d %H:%M:%S")
                    
                    if now <= expiry_dt:
                        days_left = (expiry_dt - now).days
                        hours_left = int((expiry_dt - now).seconds / 3600)
                        
                        await message.reply(
                            f"""<pre>❌ Active Plan Detected</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You already have an active {plan_info['plan']} plan!
⟐ <b>Current Plan</b>: <code>{plan_info['plan']}</code>
⟐ <b>Plan Expires</b>: <code>{plan_info['expires_at']}</code>
⟐ <b>Time Remaining</b>: <code>{days_left} days ({hours_left} hours)</code>
⟐ <b>Rule</b>: Wait for your current plan to expire before redeeming another code
━━━━━━━━━━━━━""",
                            reply_to_message_id=message.id
                        )
                        return
                except:
                    pass

    # DIRECTLY upgrade the user WITHOUT using plan1.py
    print(f"[DEBUG] Attempting to directly upgrade user {user_id}")
    upgrade_success = upgrade_user_direct(user_id, expires_at)
    
    if not upgrade_success:
        await message.reply(
            """<pre>❌ Upgrade Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to upgrade user. Please contact admin.
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    # Mark code as used
    code_data["used"] = True
    code_data["used_by"] = user_id
    code_data["used_at"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
    gift_codes[code] = code_data

    # Save gift codes
    save_gift_codes(gift_codes)

    # Success message
    response = f"""<pre>✅ Gift Code Redeemed Successfully!</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Gift code <code>{code}</code> redeemed successfully!
⟐ <b>Status</b>: Upgraded to Plus Plan
⟐ <b>Expires At</b>: <code>{expires_at}</code>
⟐ <b>Days Remaining</b>: <code>{days_remaining} days ({hours_remaining} hours)</code>
⟐ <b>Bonus</b>: 200 credits added
⟐ <b>User ID</b>: <code>{user_id}</code>
━━━━━━━━━━━━━
<b>~ Benefits:</b>
• Plus Plan features enabled
• 200 Credits added
• Reduced Anti-Spam (13s)
• Private Mode enabled
• Mass Limit: 10 cards

<b>~ Important Rules:</b>
• Plan will expire on {expires_at}

<b>~ Note:</b> <code>Enjoy your Plus plan benefits!</code>"""

    await message.reply(response, reply_to_message_id=message.id)

@Client.on_message(filters.command(["mycode", ".mycode"]))
async def mycode_command(client: Client, message: Message):
    """Check user's redeem code status"""
    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    except:
        users = {}

    user_id = str(message.from_user.id)

    if user_id not in users:
        await message.reply(
            """<pre>❌ Registration Required</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please register first!
⟐ <b>Action</b>: Use <code>/register</code> command to get started.
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    user = users[user_id]
    plan = user.get("plan", {})
    current_plan = plan.get("plan", "Free")
    current_expiry = plan.get("expires_at", "Never (Permanent)" if plan.get("expires_at") is None else plan.get("expires_at"))
    
    # Check if user has any active plan
    can_redeem = not has_active_plan(user_id)

    # Check if user has redeemed any codes
    user_codes = get_user_redeemed_codes(user_id)

    response = f"""<pre>#WAYNE ─[MY CODE STATUS]─</pre>
━━━━━━━━━━━━━
⟐ <b>User ID</b>: <code>{user_id}</code>
⟐ <b>Current Plan</b>: <code>{current_plan}</code>
⟐ <b>Plan Expires</b>: <code>{current_expiry}</code>
⟐ <b>Redeem Status</b>: <code>{'✅ Can Redeem (Free User)' if can_redeem else '❌ Cannot Redeem (Has Active Plan)'}</code>
⟐ <b>Total Redeemed Codes</b>: <code>{len(user_codes)}</code>
━━━━━━━━━━━━━"""

    if user_codes:
        response += "\n<b>📋 Your Redeemed Codes:</b>\n"
        for idx, code_info in enumerate(user_codes[:10], 1):
            response += f"{idx}. <code>{code_info['code']}</code>\n"
            response += f"   └ Used: <code>{code_info['used_at']}</code>\n"
            response += f"   └ Expires: <code>{code_info['expires_at']}</code>\n"
            response += f"   └ Plan: <code>{code_info['plan']}</code>\n"

        if len(user_codes) > 10:
            response += f"\n<b>...</b> <code>and {len(user_codes) - 10} more codes</code>\n"
    else:
        response += "\n<b>📋 Your Redeemed Codes:</b>\n"
        response += "<code>No gift codes redeemed yet.</code>\n"

    response += """━━━━━━━━━━━━━
<b>~ Important Rules:</b>
• ONLY FREE users can redeem gift codes
• Users with ACTIVE plans CANNOT redeem codes
• Wait for current plan to expire before redeeming another
• Each code gives Plus plan benefits

<b>~ How to Get Codes:</b>
• Use <code>/redeem CODE</code> to activate
• Contact admin to purchase codes"""

    await message.reply(response, reply_to_message_id=message.id)

@Client.on_message(filters.command(["checkcode", ".checkcode"]))
async def checkcode_command(client: Client, message: Message):
    """Check if a gift code is valid"""
    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    if len(message.command) < 2:
        await message.reply(
            """<pre>#WAYNE ─[CHECK CODE]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/checkcode</code>
⟐ <b>Usage</b>: <code>/checkcode &lt;gift_code&gt;</code>
⟐ <b>Example</b>: <code>/checkcode WAYNE-DAD-ABCD-EFGH</code>
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    code = message.command[1].strip().upper()

    if not code.startswith("WAYNE-DAD-"):
        await message.reply(
            f"""<pre>❌ Invalid Format</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Invalid gift code format.
⟐ <b>Required Format</b>: WAYNE-DAD-XXXX-XXXX
⟐ <b>Your Input</b>: <code>{code}</code>
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    gift_codes = load_gift_codes()
    current_time = datetime.now()

    if code not in gift_codes:
        await message.reply(
            f"""<pre>❌ Code Not Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Gift code <code>{code}</code> not found in system.
⟐ <b>Status</b>: Invalid or deleted
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    code_data = gift_codes[code]

    if code_data["used"]:
        used_by = code_data.get('used_by') or 'Unknown'
        used_at = code_data.get('used_at') or 'Unknown'
        await message.reply(
            f"""<pre>❌ Code Already Used</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Gift code <code>{code}</code> has been used.
⟐ <b>Status</b>: ❌ Not Available
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    expires_at = code_data["expires_at"]

    try:
        expiry_time = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")

        if current_time > expiry_time:
            status = "❌ Expired"
            days_remaining = 0
            hours_remaining = 0
        else:
            status = "✅ Valid"
            days_remaining = (expiry_time - current_time).days
            hours_remaining = int((expiry_time - current_time).seconds / 3600)

        await message.reply(
            f"""<pre>✅ Code Information</pre>
━━━━━━━━━━━━━
⟐ <b>Code</b>: <code>{code}</code>
⟐ <b>Status</b>: {status}
⟐ <b>Expires At</b>: <code>{expires_at}</code>
⟐ <b>Time Remaining</b>: <code>{days_remaining} days ({hours_remaining} hours)</code>
⟐ <b>Used</b>: <code>{'Yes' if code_data['used'] else 'No'}</code>
⟐ <b>Created At</b>: <code>{code_data.get('created_at', 'Unknown')}</code>
━━━━━━━━━━━━━
<b>~ Benefits:</b>
• Upgrades to Plus Plan
• 200 Credits Bonus
• Reduced Antispam (13s)
• Private Mode Enabled
• Mass Limit: 10 cards

<b>~ Important Rules:</b>
• Users with active plans CANNOT redeem
• Expires on date shown""",
            reply_to_message_id=message.id
        )

    except Exception as e:
        await message.reply(
            f"""<pre>⚠️ Code Information</pre>
━━━━━━━━━━━━━
⟐ <b>Code</b>: <code>{code}</code>
⟐ <b>Status</b>: ⚠️ Valid (Date format issue)
⟐ <b>Expires At</b>: <code>{expires_at}</code>
⟐ <b>Used</b>: <code>{'Yes' if code_data['used'] else 'No'}</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Date parsing error: {str(e)}</code>""",
            reply_to_message_id=message.id
        )

# Add admin command to check all codes (owner only)
@Client.on_message(filters.command(["allcodes", ".allcodes"]))
async def allcodes_command(client: Client, message: Message):
    """Show all gift codes (OWNER ONLY)"""
    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    user_id = str(message.from_user.id)

    if user_id != OWNER_ID:
        await message.reply(
            """<pre>❌ Permission Denied</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Only owner can view all gift codes.
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    gift_codes = load_gift_codes()
    current_time = datetime.now()

    if not gift_codes:
        await message.reply(
            """<pre>📋 All Gift Codes</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: No gift codes generated yet.
⟐ <b>Action</b>: Use <code>/gc</code> to generate gift codes.
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    valid_codes = []
    used_codes = []
    expired_codes = []

    for code, data in gift_codes.items():
        if data["used"]:
            used_codes.append((code, data))
        else:
            try:
                expiry_time = datetime.strptime(data["expires_at"], "%Y-%m-%d %H:%M:%S")
                if current_time > expiry_time:
                    expired_codes.append((code, data))
                else:
                    valid_codes.append((code, data))
            except:
                valid_codes.append((code, data))

    response = """<pre>📋 ALL GIFT CODES</pre>
━━━━━━━━━━━━━
<b>📊 Statistics:</b>
• Total Codes: <code>{}</code>
• Valid Codes: <code>{}</code>
• Used Codes: <code>{}</code>
• Expired Codes: <code>{}</code>
━━━━━━━━━━━━━""".format(
        len(gift_codes), len(valid_codes), len(used_codes), len(expired_codes)
    )

    if valid_codes:
        response += "\n<b>✅ Valid Codes:</b>\n"
        for code, data in valid_codes[:5]:
            response += f"• <code>{code}</code>\n"
            response += f"  └ Expires: <code>{data['expires_at']}</code>\n"
        if len(valid_codes) > 5:
            response += f"<code>... and {len(valid_codes) - 5} more</code>\n"

    await message.reply(response, reply_to_message_id=message.id)
