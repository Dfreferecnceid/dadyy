import json
import random
import string
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message
from BOT.helper.start import USERS_FILE, load_users, save_users, load_owner_id
from BOT.plans.plan1 import activate_plus_plan
import os

user_redeem_cooldowns = {}
REDEEM_DELAY_SECONDS = 90  # 1 minute 30 seconds
REDEEM_PLAN_NAME = "Redeem Code"
REDEEM_BADGE = "🎁"
DEFAULT_BADGE = "🧿"
DEFAULT_ANTISPAM = 15
DEFAULT_MLIMIT = 5

OWNER_ID = load_owner_id()
GC_FILE = "DATA/gift_codes.txt"  # Gift codes from /gc command

def load_gift_codes():
    """Load gift codes from GC_FILE"""
    if not os.path.exists(GC_FILE):
        return {}

    gift_codes = {}
    with open(GC_FILE, 'r') as f:
        for line in f.read().splitlines():
            if '|' in line:
                code, expiration_date_str = line.split('|')
                gift_codes[code] = {
                    "expires_at": expiration_date_str,
                    "used": False,
                    "used_by": None,
                    "used_at": None
                }
    return gift_codes

def save_gift_codes(gift_codes):
    """Save gift codes to GC_FILE"""
    with open(GC_FILE, 'w') as f:
        for code, data in gift_codes.items():
            if not data["used"]:  # Only save unused codes
                f.write(f"{code}|{data['expires_at']}\n")

@Client.on_message(filters.command("redeem"))
async def redeem_code_command(client: Client, message: Message):
    """Handle gift code redemption from /gc command"""
    users = load_users()
    user_id = str(message.from_user.id)

    if len(message.command) < 2:
        await message.reply("""<pre>#WAYNE ─[REDEEM CODE]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/redeem</code>
⟐ <b>Usage</b>: <code>/redeem &lt;gift_code&gt;</code>
⟐ <b>Example</b>: <code>/redeem WAYNE-DAD-ABCD-EFGH</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Gift codes upgrade you to Plus plan for specified days</code>""", reply_to_message_id=message.id)
        return

    code = message.command[1].strip().upper()

    # Check if it's a valid gift code format - FIXED: Remove length check
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
⟐ <b>Possible Reasons</b>:
   • Code doesn't exist
   • Code has been deleted
   • Wrong code entered
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    code_data = gift_codes[code]

    if code_data["used"]:
        used_by = code_data['used_by'] or 'Unknown'
        used_at = code_data['used_at'] or 'Unknown'
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
    except Exception as e:
        # If date parsing fails, assume code is valid
        print(f"Error parsing expiry date: {e}")

    # Calculate days remaining
    try:
        expiry_time = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
        days_remaining = (expiry_time - current_time).days
        hours_remaining = int((expiry_time - current_time).seconds / 3600)
        if days_remaining < 0:
            days_remaining = 0
            hours_remaining = 0
    except:
        days_remaining = "Unknown"
        hours_remaining = "Unknown"

    # IMPORTANT: Upgrade user to Plus plan WITH expiry date
    # This passes the expires_at parameter to activate_plus_plan()
    result = activate_plus_plan(user_id, expires_at)

    if result == "already_active":
        # User already has Plus plan, just extend expiry and add credits
        user = users[user_id]

        # Update expiry date from gift code (if needed)
        current_expiry = user["plan"].get("expires_at")
        if current_expiry is None:
            # User has permanent plan, keep it permanent (don't add expiry)
            pass
        elif current_expiry is not None:
            # User already has temporary plan, update to new expiry if later
            try:
                current_expiry_time = datetime.strptime(current_expiry, "%Y-%m-%d %H:%M:%S")
                new_expiry_time = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                if new_expiry_time > current_expiry_time:
                    user["plan"]["expires_at"] = expires_at
                    days_remaining = (new_expiry_time - current_time).days
                    hours_remaining = int((new_expiry_time - current_time).seconds / 3600)
                else:
                    # Keep existing later expiry
                    expires_at = current_expiry
            except:
                pass

        # Add Plus plan credit bonus (200 credits)
        current_credits = user["plan"]["credits"]
        if current_credits != "∞":
            try:
                current_credits = int(current_credits)
                new_credits = current_credits + 200  # Plus plan bonus
                user["plan"]["credits"] = str(new_credits)
            except:
                user["plan"]["credits"] = "200"

        response = f"""<pre>✅ Gift Code Redeemed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Gift code <code>{code}</code> redeemed successfully!
⟐ <b>Status</b>: Plus plan extended
⟐ <b>Expires At</b>: <code>{expires_at}</code>
⟐ <b>Days Remaining</b>: <code>{days_remaining} days ({hours_remaining} hours)</code>
⟐ <b>Bonus</b>: 200 credits added
⟐ <b>User ID</b>: <code>{user_id}</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Your Plus plan has been extended with gift code benefits</code>"""
    elif result:
        # Successfully upgraded to Plus plan
        response = f"""<pre>✅ Gift Code Redeemed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Gift code <code>{code}</code> redeemed successfully!
⟐ <b>Status</b>: Upgraded to Plus Plan
⟐ <b>Expires At</b>: <code>{expires_at}</code>
⟐ <b>Days Remaining</b>: <code>{days_remaining} days ({hours_remaining} hours)</code>
⟐ <b>Bonus</b>: 200 credits added
⟐ <b>User ID</b>: <code>{user_id}</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Enjoy your Plus plan benefits!</code>"""
    else:
        await message.reply(
            """<pre>❌ Redeem Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to redeem gift code.
⟐ <b>Possible Reason</b>: User registration issue.
━━━━━━━━━━━━━""",
            reply_to_message_id=message.id
        )
        return

    # Mark code as used
    code_data["used"] = True
    code_data["used_by"] = user_id
    code_data["used_at"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
    gift_codes[code] = code_data

    # Save data
    save_users(users)
    save_gift_codes(gift_codes)

    await message.reply(response, reply_to_message_id=message.id)

@Client.on_message(filters.command(["mycode", ".mycode"]))
async def mycode_command(client: Client, message: Message):
    """Check user's redeem code status"""
    users = load_users()
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
    keyredeem = plan.get("keyredeem", 0)
    current_plan = plan.get("plan", "Free")
    expires_at = plan.get("expires_at", "Never (Permanent)" if plan.get("expires_at") is None else plan.get("expires_at"))

    # Load gift codes to find which ones user used
    gift_codes = load_gift_codes()
    user_codes = []

    for code, data in gift_codes.items():
        if data["used_by"] == user_id:
            user_codes.append({
                "code": code,
                "used_at": data["used_at"],
                "expires_at": data["expires_at"]
            })

    response = f"""<pre>#WAYNE ─[MY CODE STATUS]─</pre>
━━━━━━━━━━━━━
⟐ <b>User ID</b>: <code>{user_id}</code>
⟐ <b>Current Plan</b>: <code>{current_plan}</code>
⟐ <b>Plan Expires</b>: <code>{expires_at}</code>
⟐ <b>Total Redeems</b>: <code>{keyredeem}</code>
━━━━━━━━━━━━━"""

    if user_codes:
        response += "\n<b>📋 Your Redeemed Codes:</b>\n"
        for idx, code_info in enumerate(user_codes[:10], 1):  # Show max 10 codes
            response += f"{idx}. <code>{code_info['code']}</code>\n"
            response += f"   └ Used: <code>{code_info['used_at']}</code>\n"
            response += f"   └ Expires: <code>{code_info['expires_at']}</code>\n"

        if len(user_codes) > 10:
            response += f"\n<b>...</b> <code>and {len(user_codes) - 10} more codes</code>\n"
    else:
        response += "\n<b>📋 Your Redeemed Codes:</b>\n"
        response += "<code>No gift codes redeemed yet.</code>\n"

    response += """━━━━━━━━━━━━━
<b>~ How to Get Codes:</b>
• Ask admin for gift codes
• Use <code>/redeem CODE</code> to activate
• Each code gives Plus plan benefits"""

    await message.reply(response, reply_to_message_id=message.id)

@Client.on_message(filters.command(["checkcode", ".checkcode"]))
async def checkcode_command(client: Client, message: Message):
    """Check if a gift code is valid"""
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
        used_by = code_data['used_by'] or 'Unknown'
        used_at = code_data['used_at'] or 'Unknown'
        await message.reply(
            f"""<pre>❌ Code Already Used</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Gift code <code>{code}</code> has been used.
⟐ <b>Used By</b>: <code>{used_by}</code>
⟐ <b>Used At</b>: <code>{used_at}</code>
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
━━━━━━━━━━━━━
<b>~ Benefits:</b>
• Upgrades to Plus Plan
• 200 Credits Bonus
• Reduced Antispam (13s)
• Private Mode Enabled""",
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
                valid_codes.append((code, data))  # Assume valid if date parsing fails

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
        for code, data in valid_codes[:5]:  # Show first 5 only
            response += f"• <code>{code}</code>\n"
            response += f"  └ Expires: <code>{data['expires_at']}</code>\n"
        if len(valid_codes) > 5:
            response += f"<code>... and {len(valid_codes) - 5} more</code>\n"

    await message.reply(response, reply_to_message_id=message.id)