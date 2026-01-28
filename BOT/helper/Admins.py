# BOT/helper/Admins.py

import os
import json
import random
import string
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import PeerIdInvalid, UserNotParticipant
from pyrogram.enums import ChatType
import html

# File paths
USERS_FILE = "DATA/users.json"
CONFIG_FILE = "FILES/config.json"
GC_FILE = "DATA/gift_codes.txt"
BANBIN_FILE = "DATA/banbin.txt"
BANNEDU_FILE = "DATA/banned_users.txt"
DISABLED_COMMANDS_FILE = "DATA/disabled_commands.txt"
RESTRICTED_COMMANDS_FILE = "DATA/restricted_commands.txt"
GROUPS_FILE = "DATA/groups.json"

# Import from permissions module - FIXED: Only import what exists in permissions.py
from .permissions import (
    load_users, save_users, load_owner_id, get_user_plan, 
    is_user_owner, is_user_banned, is_user_registered,
    load_allowed_groups, save_allowed_groups, authorize_group, 
    deauthorize_group, is_group_authorized,
    owner_required, admin_required, registered_required,
    auth_and_free_restricted
)

# Import plan activation functions from plans folder
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from BOT.plans.plan1 import activate_plus_plan
    from BOT.plans.plan2 import activate_pro_plan
    from BOT.plans.plan3 import activate_elite_plan
    from BOT.plans.plan4 import activate_vip_plan
    from BOT.plans.plan5 import activate_ult_plan
except ImportError:
    # Fallback functions if imports fail
    def activate_plus_plan(user_id: str) -> bool:
        users = load_users()
        user = users.get(user_id)
        if not user:
            return False
        user["plan"]["plan"] = "Plus"
        user["role"] = "Plus"
        save_users(users)
        return True

    def activate_pro_plan(user_id: str) -> bool:
        users = load_users()
        user = users.get(user_id)
        if not user:
            return False
        user["plan"]["plan"] = "Pro"
        user["role"] = "Pro"
        save_users(users)
        return True

    def activate_elite_plan(user_id: str) -> bool:
        users = load_users()
        user = users.get(user_id)
        if not user:
            return False
        user["plan"]["plan"] = "Elite"
        user["role"] = "Elite"
        save_users(users)
        return True

    def activate_vip_plan(user_id: str) -> bool:
        users = load_users()
        user = users.get(user_id)
        if not user:
            return False
        user["plan"]["plan"] = "VIP"
        user["role"] = "VIP"
        save_users(users)
        return True

    def activate_ult_plan(user_id: str) -> bool:
        users = load_users()
        user = users.get(user_id)
        if not user:
            return False
        user["plan"]["plan"] = "ULTIMATE"
        user["role"] = "ULTIMATE"
        save_users(users)
        return True

# Try to import from gc folder first, then from helper
try:
    from BOT.gc.credit import initialize_user_credits, get_user_credits, reset_user_credits_now
except ImportError:
    # Fallback if gc folder doesn't exist
    from .credit import initialize_user_credits, get_user_credits

    # Fallback reset function
    def reset_user_credits_now(user_id: int):
        return False, "Credit module not available"

# Ensure DATA directory exists
os.makedirs("DATA", exist_ok=True)

def get_ist_time():
    """Get current IST time"""
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

def upgrade_user(target_id, plan_name):
    """Upgrade user to specified plan using the plan activation functions"""
    user_id_str = str(target_id)

    # Map plan names/number to activation functions
    plan_functions = {
        # Plan names (text)
        "plus": activate_plus_plan,
        "pro": activate_pro_plan,
        "elite": activate_elite_plan,
        "vip": activate_vip_plan,
        "ult": activate_ult_plan,
        "ultimate": activate_ult_plan,

        # Plan numbers (user-friendly)
        "1": activate_plus_plan,
        "2": activate_pro_plan,
        "3": activate_elite_plan,
        "4": activate_vip_plan,
        "5": activate_ult_plan,

        # Plan with "plan" prefix
        "plan1": activate_plus_plan,
        "plan2": activate_pro_plan,
        "plan3": activate_elite_plan,
        "plan4": activate_vip_plan,
        "plan5": activate_ult_plan,
    }

    # Normalize plan name (remove @ if present and convert to lowercase)
    plan_lower = plan_name.lower().strip()

    # Remove @ symbol if present
    if plan_lower.startswith('@'):
        plan_lower = plan_lower[1:]

    if plan_lower in plan_functions:
        result = plan_functions[plan_lower](user_id_str)

        if result == "already_active":
            return "already_active"
        elif result:
            return True
        else:
            return False
    else:
        # Default to Plus plan if no specific plan mentioned
        result = activate_plus_plan(user_id_str)
        if result == "already_active":
            return "already_active"
        return result

def downgrade_user(target_id):
    """Downgrade user to Free plan WITH CREDIT RESET"""
    users = load_users()
    user_id_str = str(target_id)

    if user_id_str not in users:
        return False

    # Update plan to Free
    user = users[user_id_str]
    plan = user.get("plan", {})

    # Set default Free plan values WITH DAILY CREDITS
    plan.update({
        "plan": "Free",
        "activated_at": user.get("registered_at", plan.get("activated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
        "expires_at": None,
        "antispam": 15,
        "mlimit": 5,
        "badge": "🧿",
        "credits": "100",  # Reset to 100 daily credits
        "private": "off"
    })
    user["role"] = "Free"

    # Set credit reset timestamp for daily reset
    user["last_credit_reset"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_users(users)
    return True

def ban_user(user_id):
    """Ban a user"""
    with open(BANNEDU_FILE, "a") as f:
        f.write(f"{user_id}\n")
    return True

def unban_user(user_id):
    """Unban a user"""
    if not os.path.exists(BANNEDU_FILE):
        return False

    with open(BANNEDU_FILE, "r") as f:
        banned_users = f.read().splitlines()

    if str(user_id) not in banned_users:
        return False

    with open(BANNEDU_FILE, "w") as f:
        for banned_user in banned_users:
            if banned_user.strip() != str(user_id):
                f.write(f"{banned_user}\n")

    return True

def ban_bin(bin_number):
    """Ban a BIN"""
    with open(BANBIN_FILE, "a") as f:
        f.write(f"{bin_number}\n")
    return True

def unban_bin(bin_number):
    """Unban a BIN"""
    if not os.path.exists(BANBIN_FILE):
        return False

    with open(BANBIN_FILE, "r") as f:
        banned_bins = f.read().splitlines()

    if str(bin_number) not in banned_bins:
        return False

    with open(BANBIN_FILE, "w") as f:
        for banned_bin in banned_bins:
            if banned_bin.strip() != str(bin_number):
                f.write(f"{banned_bin}\n")

    return True

def random_alphanumeric(length=4):
    """Generate random alphanumeric string"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def generate_redeem_code(days, num_codes=1):
    """Generate redeem codes"""
    codes = []
    for _ in range(num_codes):
        part1 = random_alphanumeric(4)
        part2 = random_alphanumeric(4)
        code = f"WAYNE-DAD-{part1}-{part2}"

        expiration_timestamp = datetime.now() + timedelta(hours=days*24)
        expiration_date_str = expiration_timestamp.strftime("%Y-%m-%d %H:%M:%S")

        with open(GC_FILE, 'a') as f:
            f.write(f"{code}|{expiration_date_str}\n")

        codes.append((code, expiration_date_str))
    return codes

def get_all_commands():
    """Get list of all valid commands in the bot"""
    valid_commands = set()

    # UPDATED: Added new proxy commands and removed old ones
    gate_commands = [
        "au", "chk", "sx", "xc", "sk", "gen", "fake", "bin",
        "gates", "gate", "start", "help", "info", "register",
        "buy", "plans", "plan", "plus", "pro", "elite", "vip", "ultimate",
        "redeem", "looser", "broad", "notused", "off", "on", "resett",
        "banbin", "unbanbin", "ban", "unban", "add", "rmv",
        "gc", "id",
        "xx", "xo", "xs", "xc", "xp", "bt", "sh", "slf",  # Charge commands
        "mau", "mchk", "mxc", "mxp", "mxx",  # Mass commands
        # NEW PROXY COMMANDS - Added
        "addpx", "rmvpx", "rmvall", "vpx", "pxstats",
        # REMOVED OLD PROXY COMMANDS: "setpx", "delpx", "getpx"
    ]

    # Add dot and dollar variants
    for cmd in gate_commands:
        valid_commands.add(cmd)
        valid_commands.add(f"/{cmd}")
        valid_commands.add(f".{cmd}")
        valid_commands.add(f"${cmd}")

    return valid_commands

def is_valid_command(command_name: str) -> bool:
    """Check if a command is valid/exists in the bot"""
    valid_commands = get_all_commands()

    # Normalize command name
    cmd = command_name.strip()

    # Check if command exists (with or without prefix)
    return (cmd in valid_commands or 
            cmd.lstrip('/.$') in valid_commands)

def is_command_disabled(command_name: str) -> bool:
    """Check if a command is disabled globally"""
    try:
        if not os.path.exists(DISABLED_COMMANDS_FILE):
            return False

        with open(DISABLED_COMMANDS_FILE, "r") as f:
            disabled_commands = f.read().splitlines()

        # Normalize command name
        cmd = command_name.strip().lower()
        cmd_with_slash = f"/{cmd.lstrip('/').lstrip('.')}"
        cmd_with_dot = f".{cmd.lstrip('/').lstrip('.')}"

        return (cmd in disabled_commands or 
                cmd_with_slash in disabled_commands or 
                cmd_with_dot in disabled_commands)
    except Exception:
        return False

def get_command_offline_message(command_name: str) -> str:
    """Get the offline message for a disabled command"""
    return f"""<pre>🚫 Command Disabled</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Command <code>{command_name}</code> is currently disabled.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for more information.
━━━━━━━━━━━━━"""

def is_user_restricted_for_command(user_id: int, command_name: str) -> bool:
    """Check if a user is restricted from using a command"""
    try:
        if not os.path.exists(RESTRICTED_COMMANDS_FILE):
            return False

        with open(RESTRICTED_COMMANDS_FILE, "r") as f:
            restrictions = f.read().splitlines()

        for line in restrictions:
            if ':' in line:
                restricted_user_id, restricted_command = line.split(':', 1)
                if str(user_id) == restricted_user_id.strip() and command_name.strip().lower() == restricted_command.strip().lower():
                    return True
        return False
    except Exception:
        return False

def disable_command(command):
    """Disable a command globally - WITH VALIDATION"""
    # First check if command is valid
    if not is_valid_command(command):
        return "invalid_command"

    disabled_commands = set()

    if os.path.exists(DISABLED_COMMANDS_FILE):
        with open(DISABLED_COMMANDS_FILE, 'r') as f:
            disabled_commands = set(f.read().splitlines())

    command_name = command.strip('/').strip('.')
    command_with_slash = f"/{command_name}"
    command_with_dot = f".{command_name}"

    # Check if already disabled
    if (command_name in disabled_commands or 
        command_with_slash in disabled_commands or 
        command_with_dot in disabled_commands):
        return "already_disabled"

    # Add all formats
    disabled_commands.add(command_name)
    disabled_commands.add(command_with_slash)
    disabled_commands.add(command_with_dot)

    with open(DISABLED_COMMANDS_FILE, 'w') as f:
        for cmd in disabled_commands:
            f.write(f"{cmd}\n")

    return True

def enable_command(command):
    """Enable a command globally - WITH VALIDATION"""
    # First check if command is valid
    if not is_valid_command(command):
        return "invalid_command"

    if not os.path.exists(DISABLED_COMMANDS_FILE):
        return "not_disabled"

    with open(DISABLED_COMMANDS_FILE, 'r') as f:
        disabled_commands = f.read().splitlines()

    command_name = command.strip('/').strip('.')
    command_with_slash = f"/{command_name}"
    command_with_dot = f".{command_name}"

    new_disabled_commands = []
    removed = False

    for cmd in disabled_commands:
        if cmd.strip() not in [command_name, command_with_slash, command_with_dot]:
            new_disabled_commands.append(cmd)
        else:
            removed = True

    if not removed:
        return "not_disabled"

    with open(DISABLED_COMMANDS_FILE, 'w') as f:
        for cmd in new_disabled_commands:
            f.write(f"{cmd}\n")

    return True

# ==================== ADDED MISSING FUNCTIONS ====================

def get_command_status(command_name: str) -> str:
    """Get the status of a command (Active ✅ or Disabled ❌)"""
    if is_command_disabled(command_name):
        return "Disabled ❌"
    else:
        return "Active ✅"

def get_gate_command_status(gate_type: str, command_prefix: str = None) -> dict:
    """
    Get status for gate commands (for backward compatibility)
    Returns empty dict as we use direct command checking now
    """
    return {}

# ==================== /RESETT COMMAND ====================

@Client.on_message(filters.command(["resett", ".resett"]))
@owner_required
@auth_and_free_restricted
async def resett_command(client: Client, message: Message):
    """Reset user credits immediately - OWNER ONLY"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("""<pre>#WAYNE ─[RESET CREDITS]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/resett</code> or <code>.resett</code>
⟐ <b>Usage</b>: <code>/resett &lt;username or ID&gt;</code>
⟐ <b>Example</b>: <code>/resett @username</code>
⟐ <b>Example</b>: <code>/resett 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will reset user's credits to their daily amount immediately</code>
<b>~ Note:</b> <code>User's daily reset timer will still work normally</code>
<b>~ Note:</b> <code>Owner/Admin users cannot have their credits reset (they have ∞)</code>""")
        return

    target = args[1]

    try:
        if target.startswith('@'):
            target_user = await client.get_users(target)
        else:
            target_user = await client.get_users(int(target))

        target_id = target_user.id
        target_username = f"@{target_user.username}" if target_user.username else f"User {target_user.id}"
    except (ValueError, PeerIdInvalid):
        await message.reply(f"""<pre>❌ User Not Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Could not find user: <code>{target}</code>
━━━━━━━━━━━━━""")
        return

    # Check if user is registered
    if not is_user_registered(target_id):
        await message.reply(f"""<pre>❌ User Not Registered</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User {target_username} is not registered.
⟐ <b>Solution</b>: User must register first with <code>/register</code>
━━━━━━━━━━━━━""")
        return

    # Check if user is Owner/Admin (they have infinite credits)
    users = load_users()
    user_data = users.get(str(target_id), {})
    user_role = user_data.get("role", "Free")
    user_plan = user_data.get("plan", {}).get("plan", "Free")

    if user_role in ["Owner", "Admin"] or user_plan == "Owner":
        await message.reply(f"""<pre>⚠️ Cannot Reset Owner/Admin Credits</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: {target_username} is Owner/Admin and has infinite credits (∞).
⟐ <b>Role</b>: <code>{user_role}</code>
⟐ <b>Plan</b>: <code>{user_plan}</code>
━━━━━━━━━━━━━""")
        return

    # Reset user credits
    success, reset_msg = reset_user_credits_now(target_id)

    if success:
        # Get updated credits
        current_credits = get_user_credits(target_id)

        await message.reply(f"""<pre>✅ Credits Reset Successful</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Successfully reset credits for {target_username}
⟐ <b>User ID</b>: <code>{target_id}</code>
⟐ <b>New Credits</b>: <code>{current_credits}</code>
⟐ <b>Plan</b>: <code>{user_plan}</code>
⟐ <b>Role</b>: <code>{user_role}</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>User's credits have been reset to their daily amount</code>
<b>~ Note:</b> <code>Daily reset timer remains active (will reset again in 24h)</code>""")
    else:
        await message.reply(f"""<pre>❌ Reset Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to reset credits for {target_username}
⟐ <b>Error</b>: <code>{reset_msg}</code>
━━━━━━━━━━━━━""")

# ==================== COMMAND HANDLERS ====================

@Client.on_message(filters.command(["gc", ".gc"]))
@owner_required
@auth_and_free_restricted  # Use the new combined decorator
async def gc_command(client: Client, message: Message):
    """Generate gift codes - OWNER ONLY"""
    args = message.text.split()
    if len(args) < 3:
        await message.reply("""<pre>#WAYNE ─[GENERATE CODE]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/gc</code> or <code>.gc</code>
⟐ <b>Usage</b>: <code>/gc &lt;days&gt; &lt;num_codes&gt;</code>
⟐ <b>Example</b>: <code>/gc 30 5</code>
⟐ <b>Result</b>: 5 codes valid for 30 days (720 hours)
⟐ <b>Example</b>: <code>/gc 90 1</code>
⟐ <b>Result</b>: 1 code valid for 90 days (2160 hours)
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Maximum 10 codes at once</code>
<b>~ Note:</b> <code>Exact 24-hour periods (not calendar days)</code>
<b>~ Note:</b> <code>Codes can be redeemed with /redeem command</code>""")
        return

    try:
        days = int(args[1])
        num_codes = int(args[2])
        if days < 1 or days > 365:
            await message.reply("""<pre>❌ Invalid Days</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Invalid number of days. Please provide a value between 1 and 365
━━━━━━━━━━━━━""")
            return
        if num_codes < 1 or num_codes > 10:
            await message.reply("""<pre>❌ Invalid Count</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Invalid number of codes. Please provide a value between 1 and 10.
━━━━━━━━━━━━━""")
            return
    except ValueError:
        await message.reply("""<pre>❌ Invalid Input</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Invalid input. Please provide valid integers for days and number of codes.
━━━━━━━━━━━━━""")
        return

    codes = generate_redeem_code(days, num_codes)

    response = "<pre>✅ Redeem Codes Generated</pre>\n"
    response += "━━━━━━━━━━━━━\n"
    for code, expiration_date in codes:
        response += f"⟐ <b>Code</b>: <code>{code}</code>\n"

    hours_total = days * 24
    response += f"\n⟐ <b>Expiration</b>: <code>{expiration_date}</code>\n"
    response += f"⟐ <b>Valid For</b>: <code>{hours_total} hours ({days} days)</code>\n"
    response += "━━━━━━━━━━━━━\n"
    response += "<b>~ How to Redeem Your Code:</b>\n"
    response += "1. Use <code>/redeem &lt;your_code&gt;</code>\n"
    response += f"2. Each code valid for <code>{hours_total} hours</code>\n"
    response += "3. Enjoy your upgraded plan!\n"
    response += "4. Redeem at @WayneCHK_bot"

    await message.reply(response)

@Client.on_callback_query(filters.regex("^admin_plan_"))
async def handle_admin_plan_callback(client, callback_query):
    """Handle plan selection from admin menu"""
    plan_type = callback_query.data.split("_")[-1]

    plan_names = {
        "plus": "💠 Plus",
        "pro": "🔰 Pro", 
        "elite": "📧 Elite",
        "vip": "🎖 VIP",
        "ult": "⭐️ ULTIMATE"
    }

    plan_display = plan_names.get(plan_type, plan_type.capitalize())

    # Store the selected plan in callback query data for next step
    await callback_query.message.reply(f"""<pre>#WAYNE ─[UPGRADE USER]─</pre>
━━━━━━━━━━━━━
⟐ <b>Selected Plan</b>: {plan_display}
⟐ <b>Next Step</b>: Reply with username or ID
━━━━━━━━━━━━━
<b>Usage Examples:</b>
• <code>@{callback_query.from_user.username}</code>
• <code>123456789</code>
• <code>@username</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>I'll wait for your reply with the user to upgrade</code>""")

    # Store context for next message
    await callback_query.answer(f"Selected {plan_display} plan. Now reply with username/ID")

# Add handler for replying to plan selection
@Client.on_message(filters.reply & filters.private)
@owner_required
async def handle_plan_upgrade_reply(client: Client, message: Message):
    """Handle reply to plan selection message"""
    if not message.reply_to_message:
        return

    reply_text = message.reply_to_message.text
    if "Selected Plan" not in reply_text or "Next Step" not in reply_text:
        return

    # Extract plan type from previous message
    import re
    plan_match = re.search(r"Selected Plan.*?: (💠|🔰|📧|🎖|⭐️)\s*(\w+)", reply_text)
    if not plan_match:
        return

    badge = plan_match.group(1)
    plan_name = plan_match.group(2).lower()

    # Get target user from current message
    target = message.text.strip()

    try:
        if target.startswith('@'):
            target_user = await client.get_users(target)
        else:
            # Try to convert to int, if fails assume it's a username without @
            try:
                target_user = await client.get_users(int(target))
            except ValueError:
                target_user = await client.get_users(target)

        target_id = target_user.id
        target_username = f"@{target_user.username}" if target_user.username else f"User {target_user.id}"
    except (ValueError, PeerIdInvalid) as e:
        await message.reply(f"""<pre>❌ User Not Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Could not find user: <code>{target}</code>
⟐ <b>Error</b>: <code>{str(e)}</code>
━━━━━━━━━━━━━""")
        return

    # Check if user is registered
    if not is_user_registered(target_id):
        await message.reply(f"""<pre>❌ User Not Registered</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User {target_username} is not registered.
⟐ <b>Solution</b>: User must register first with <code>/register</code>
━━━━━━━━━━━━━""")
        return

    # Upgrade the user using existing function
    result = upgrade_user(target_id, plan_name)

    # Plan display names mapping
    plan_display_names = {
        "plus": "Plus", "1": "Plus", "plan1": "Plus",
        "pro": "Pro", "2": "Pro", "plan2": "Pro",
        "elite": "Elite", "3": "Elite", "plan3": "Elite",
        "vip": "VIP", "4": "VIP", "plan4": "VIP",
        "ult": "ULTIMATE", "ultimate": "ULTIMATE", "5": "ULTIMATE", "plan5": "ULTIMATE"
    }

    display_name = plan_display_names.get(plan_name.lower(), plan_name.capitalize())

    if result == "already_active":
        await message.reply(f"""<pre>ℹ️ User Already Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User {target_username} already has an active {display_name} plan.
━━━━━━━━━━━━━""")
    elif result:
        await message.reply(f"""<pre>✅ Upgrade Successful</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Successfully upgraded user {target_username} to {display_name} plan!
⟐ <b>User ID</b>: <code>{target_id}</code>
⟐ <b>Plan Applied</b>: <code>{display_name}</code>
━━━━━━━━━━━━━""")

        # Send notification to user
        try:
            await client.send_message(
                target_id,
                f"""<pre>✅ Plan Upgraded Successfully</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Your plan has been upgraded to {display_name}!
⟐ <b>Admin</b>: @{message.from_user.username if message.from_user.username else "Owner"}
⟐ <b>Upgraded At</b>: <code>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Use /info to check your new plan details</code>"""
            )
        except:
            pass
    else:
        await message.reply("""<pre>❌ Upgrade Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to upgrade user. User may not be registered.
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["looser", ".looser"]))
@owner_required
@auth_and_free_restricted  # Use the new combined decorator
async def looser_command(client: Client, message: Message):
    """Downgrade a user to FREE plan - OWNER ONLY"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("""<pre>#WAYNE ─[DOWNGRADE USER]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/looser</code> or <code>.looser</code>
⟐ <b>Usage</b>: <code>/looser &lt;username or ID&gt;</code>
⟐ <b>Example</b>: <code>/looser @username</code>
⟐ <b>Example</b>: <code>/looser 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will downgrade the user to FREE plan and reset their credits to 100 daily credits.</code>""")
        return

    target = args[1]

    try:
        if target.startswith('@'):
            target_user = await client.get_users(target)
        else:
            target_user = await client.get_users(int(target))

        target_id = target_user.id
    except (ValueError, PeerIdInvalid):
        await message.reply(f"""<pre>❌ User Not Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Could not find user: <code>{target}</code>
━━━━━━━━━━━━━""")
        return

    if downgrade_user(target_id):
        await message.reply(f"""<pre>✅ User Downgraded</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User <code>{target}</code> has been downgraded to the FREE plan.
⟐ <b>Credits Reset</b>: <code>100 daily credits (resets every 24h)</code>
⟐ <b>Note</b>: <code>User's credits have been reset to daily free limit</code>
━━━━━━━━━━━━━""")
    else:
        await message.reply("""<pre>❌ Downgrade Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to downgrade user.
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["broad", ".broad"]))
@owner_required
@auth_and_free_restricted  # Use the new combined decorator
async def broad_command(client: Client, message: Message):
    """Broadcast message to all users - OWNER ONLY"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("""<pre>#WAYNE ─[BROADCAST MESSAGE]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/broad</code> or <code>.broad</code>
⟐ <b>Usage</b>: <code>/broad &lt;your message&gt;</code>
⟐ <b>Example</b>: <code>/broad Hello everyone!</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will broadcast your message to all users.</code>""")
        return

    broadcast_message = " ".join(args[1:])

    users = load_users()
    sent_count = 0
    failed_count = 0

    await message.reply("""<pre>📢 Starting Broadcast</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Starting to send broadcast message to all users...
━━━━━━━━━━━━━""")

    for user_id_str in users.keys():
        try:
            await client.send_message(
                int(user_id_str),
                f"""<pre>📢 Broadcast Message</pre>
━━━━━━━━━━━━━
{broadcast_message}
━━━━━━━━━━━━━
<b>~ From:</b> <code>WAYNE Admin</code>"""
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1

    await message.reply(f"""<pre>✅ Broadcast Completed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Message broadcasted to all users.
⟐ <b>Sent</b>: <code>{sent_count} users</code>
⟐ <b>Failed</b>: <code>{failed_count} users</code>
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["notused", ".notused"]))
@owner_required
@auth_and_free_restricted  # Use the new combined decorator
async def notused_command(client: Client, message: Message):
    """Check unused gift codes - OWNER ONLY"""
    if not os.path.exists(GC_FILE):
        await message.reply("""<pre>ℹ️ Notification</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: No gift codes have been generated yet.
━━━━━━━━━━━━━""")
        return

    with open(GC_FILE, 'r') as f:
        valid_codes = f.read().splitlines()

    unused_codes = []
    expired_codes = []
    for line in valid_codes:
        if '|' in line:
            code, expiration_date_str = line.split('|')
            try:
                expiration_timestamp = datetime.strptime(expiration_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    expiration_timestamp = datetime.strptime(expiration_date_str, "%Y-%m-%d")
                    expiration_timestamp = expiration_timestamp.replace(hour=23, minute=59, second=59)
                except:
                    continue

            if datetime.now() > expiration_timestamp:
                expired_codes.append((code, expiration_date_str))
            else:
                unused_codes.append((code, expiration_date_str))

    # Remove expired codes
    with open(GC_FILE, 'w') as f:
        for code, expiration_date in unused_codes:
            f.write(f"{code}|{expiration_date}\n")

    response = "<pre>#WAYNE ─[UNUSED GIFT CODES]─</pre>\n"
    response += "━━━━━━━━━━━━━\n"

    if unused_codes:
        response += "✅ <b>Unused Codes:</b>\n"
        for code, expiration_date in unused_codes:
            response += f"⟐ <b>Code</b>: <code>{code}</code>\n"
            response += f"⟐ <b>Expires</b>: <code>{expiration_date}</code>\n"
            response += "━━━━━━━━━━━━━\n"
    else:
        response += "ℹ️ <b>No unused codes found.</b>\n"
        response += "━━━━━━━━━━━━━\n"

    if expired_codes:
        response += "❌ <b>Expired Codes (Removed):</b>\n"
        for code, expiration_date in expired_codes:
            response += f"⟐ <b>Code</b>: <code>{code}</code>\n"
            response += f"⟐ <b>Expired</b>: <code>{expiration_date}</code>\n"
            response += "━━━━━━━━━━━━━\n"
    else:
        response += "ℹ️ <b>No expired codes found.</b>\n"
        response += "━━━━━━━━━━━━━\n"

    await message.reply(response)

@Client.on_message(filters.command(["off", ".off"]))
@owner_required
@auth_and_free_restricted  # Use the new combined decorator
async def off_command(client: Client, message: Message):
    """Disable a command globally - OWNER ONLY - WITH VALIDATION"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("""<pre>#WAYNE ─[DISABLE COMMAND]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/off</code> or <code>.off</code>
⟐ <b>Usage</b>: <code>/off &lt;command&gt;</code>
⟐ <b>Example</b>: <code>/off /au</code>
⟐ <b>Example</b>: <code>/off .sx</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>The command will be disabled until re-enabled with /on.</code>
<b>~ Note:</b> <code>Only valid existing commands can be disabled.</code>""")
        return

    command = args[1]

    result = disable_command(command)

    if result == "invalid_command":
        # UPDATED: Added new proxy commands to the list
        await message.reply(f"""<pre>❌ Invalid Command</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Command <code>{command}</code> does not exist in this bot.
⟐ <b>Valid Commands:</b> <code>au, chk, xx, xo, xs, xc, xp, bt, sh, slf, mau, mchk, mxc, mxp, mxx, gen, fake, bin, gates, gate, start, help, info, register, buy, plans, plan, plus, pro, elite, vip, ultimate, redeem, looser, broad, notused, off, on, resett, banbin, unbanbin, ban, unban, add, rmv, gc, id, addpx, rmvpx, rmvall, vpx, pxstats</code>
━━━━━━━━━━━━━""")
    elif result == "already_disabled":
        await message.reply(f"""<pre>ℹ️ Already Disabled</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Command <code>{command}</code> is already disabled.
━━━━━━━━━━━━━""")
    elif result:
        await message.reply(f"""<pre>✅ Command Disabled</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Command <code>{command}</code> has been disabled globally.
⟐ <b>Note:</b> <code>Users will see "Command Disabled" message when trying to use it.</code>
━━━━━━━━━━━━━""")
    else:
        await message.reply(f"""<pre>❌ Disable Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to disable command <code>{command}</code>.
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["on", ".on"]))
@owner_required
@auth_and_free_restricted  # Use the new combined decorator
async def on_command(client: Client, message: Message):
    """Enable a command globally - OWNER ONLY - WITH VALIDATION"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("""<pre>#WAYNE ─[ENABLE COMMAND]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/on</code> or <code>.on</code>
⟐ <b>Usage</b>: <code>/on &lt;command&gt;</code>
⟐ <b>Example</b>: <code>/on /au</code>
⟐ <b>Example</b>: <code>/on .sx</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>The command will be re-enabled for all users.</code>
<b>~ Note:</b> <code>Only valid existing commands can be enabled.</code>""")
        return

    command = args[1]

    result = enable_command(command)

    if result == "invalid_command":
        # UPDATED: Added new proxy commands to the list
        await message.reply(f"""<pre>❌ Invalid Command</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Command <code>{command}</code> does not exist in this bot.
⟐ <b>Valid Commands:</b> <code>au, chk, xx, xo, xs, xc, xp, bt, sh, slf, mau, mchk, mxc, mxp, mxx, gen, fake, bin, gates, gate, start, help, info, register, buy, plans, plan, plus, pro, elite, vip, ultimate, redeem, looser, broad, notused, off, on, resett, banbin, unbanbin, ban, unban, add, rmv, gc, id, addpx, rmvpx, rmvall, vpx, pxstats</code>
━━━━━━━━━━━━━""")
    elif result == "not_disabled":
        await message.reply(f"""<pre>ℹ️ Not Disabled</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Command <code>{command}</code> is not currently disabled.
━━━━━━━━━━━━━""")
    elif result:
        await message.reply(f"""<pre>✅ Command Enabled</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Command <code>{command}</code> has been enabled globally.
⟐ <b>Note:</b> <code>Users can now use this command again.</code>
━━━━━━━━━━━━━""")
    else:
        await message.reply(f"""<pre>❌ Enable Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to enable command <code>{command}</code>.
━━━━━━━━━━━━━""")

# ==================== ADMIN COMMANDS (OWNER OR ADMIN) ====================

@Client.on_message(filters.command(["banbin", ".banbin"]))
@admin_required
@auth_and_free_restricted  # Use the new combined decorator
async def banbin_command(client: Client, message: Message):
    """Ban a BIN - OWNER OR ADMIN"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("""<pre>#WAYNE ─[BAN BIN]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/banbin</code> or <code>.banbin</code>
⟐ <b>Usage 1</b>: <code>/banbin &lt;6-digit BIN&gt;</code>
⟐ <b>Usage 2</b>: <code>/banbin &lt;ccnum|mon|year|cvv&gt;</code>
⟐ <b>Example</b>: <code>/banbin 123456</code>
⟐ <b>Example</b>: <code>/banbin 411111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will ban the BIN from being used.</code>""")
        return

    input_data = args[1]

    if '|' in input_data:
        try:
            cc, mes, ano, cvv = input_data.split('|')
            bin_number = cc[:6]
        except ValueError:
            await message.reply("""<pre>❌ Invalid Format</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Invalid card format. Use: <code>/banbin &lt;ccnum|mon|year|cvv&gt;</code>
━━━━━━━━━━━━━""")
            return
    else:
        if len(input_data) != 6 or not input_data.isdigit():
            await message.reply("""<pre>❌ Invalid BIN</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Invalid BIN. Please provide a 6-digit BIN.
━━━━━━━━━━━━━""")
            return
        bin_number = input_data

    ban_bin(bin_number)
    await message.reply(f"""<pre>✅ BIN Banned</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: BIN <code>{bin_number}</code> has been banned.
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["unbanbin", ".unbanbin"]))
@admin_required
@auth_and_free_restricted  # Use the new combined decorator
async def unbanbin_command(client: Client, message: Message):
    """Unban a BIN - OWNER OR ADMIN"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("""<pre>#WAYNE ─[UNBAN BIN]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/unbanbin</code> or <code>.unbanbin</code>
⟐ <b>Usage 1</b>: <code>/unbanbin &lt;6-digit BIN&gt;</code>
⟐ <b>Usage 2</b>: <code>/unbanbin &lt;ccnum|mon|year|cvv&gt;</code>
⟐ <b>Example</b>: <code>/unbanbin 123456</code>
⟐ <b>Example</b>: <code>/unbanbin 411111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will unban the BIN if it was previously banned.</code>""")
        return

    input_data = args[1]

    if '|' in input_data:
        try:
            cc, mes, ano, cvv = input_data.split('|')
            bin_number = cc[:6]
        except ValueError:
            await message.reply("""<pre>❌ Invalid Format</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Invalid card format. Use: <code>/unbanbin &lt;ccnum|mon|year|cvv&gt;</code>
━━━━━━━━━━━━━""")
            return
    else:
        if len(input_data) != 6 or not input_data.isdigit():
            await message.reply("""<pre>❌ Invalid BIN</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Invalid BIN. Please provide a 6-digit BIN.
━━━━━━━━━━━━━""")
            return
        bin_number = input_data

    if unban_bin(bin_number):
        await message.reply(f"""<pre>✅ BIN Unbanned</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: BIN <code>{bin_number}</code> has been unbanned.
━━━━━━━━━━━━━""")
    else:
        await message.reply(f"""<pre>ℹ️ Notification</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: BIN <code>{bin_number}</code> is not banned or could not be unbanned.
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["ban", ".ban"]))
@admin_required
@auth_and_free_restricted  # Use the new combined decorator
async def ban_command(client: Client, message: Message):
    """Ban a user - OWNER OR ADMIN"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("""<pre>#WAYNE ─[BAN USER]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/ban</code> or <code>.ban</code>
⟐ <b>Usage</b>: <code>/ban &lt;username or ID&gt;</code>
⟐ <b>Example</b>: <code>/ban @username</code>
⟐ <b>Example</b>: <code>/ban 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will ban the user from using the bot.</code>""")
        return

    target = args[1]

    try:
        if target.startswith('@'):
            target_user = await client.get_users(target)
        else:
            target_user = await client.get_users(int(target))

        target_id = target_user.id
        target_username = f"@{target_user.username}" if target_user.username else f"User {target_user.id}"
    except (ValueError, PeerIdInvalid):
        await message.reply(f"""<pre>❌ User Not Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Could not find user: <code>{target}</code>
━━━━━━━━━━━━━""")
        return

    ban_user(target_id)
    await message.reply(f"""<pre>✅ User Banned</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User {target_username} has been banned.
⟐ <b>User ID</b>: <code>{target_id}</code>
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["unban", ".unban"]))
@admin_required
@auth_and_free_restricted  # Use the new combined decorator
async def unban_command(client: Client, message: Message):
    """Unban a user - OWNER OR ADMIN"""
    args = message.text.split()
    if len(args) < 2:
        await message.reply("""<pre>#WAYNE ─[UNBAN USER]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/unban</code> or <code>.unban</code>
⟐ <b>Usage</b>: <code>/unban &lt;username or ID&gt;</code>
⟐ <b>Example</b>: <code>/unban @username</code>
⟐ <b>Example</b>: <code>/unban 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will unban the user if they were previously banned.</code>""")
        return

    target = args[1]

    try:
        if target.startswith('@'):
            target_user = await client.get_users(target)
        else:
            target_user = await client.get_users(int(target))

        target_id = target_user.id
        target_username = f"@{target_user.username}" if target_user.username else f"User {target_user.id}"
    except (ValueError, PeerIdInvalid):
        await message.reply(f"""<pre>❌ User Not Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Could not find user: <code>{target}</code>
━━━━━━━━━━━━━""")
        return

    if unban_user(target_id):
        await message.reply(f"""<pre>✅ User Unbanned</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User {target_username} has been unbanned.
⟐ <b>User ID</b>: <code>{target_id}</code>
━━━━━━━━━━━━━""")
    else:
        await message.reply(f"""<pre>ℹ️ Notification</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User {target_username} is not banned or could not be unbanned.
━━━━━━━━━━━━━""")

# ==================== GROUP MANAGEMENT COMMANDS (OWNER ONLY) ====================

@Client.on_message(filters.command(["add", ".add"]))
@owner_required
@auth_and_free_restricted  # Use the new combined decorator
async def add_group_command(client: Client, message: Message):
    """Add group to allowed list - OWNER ONLY (works in both private and groups)"""
    args = message.text.split()

    if len(args) < 2:
        # If used in a group without arguments, add that group
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            chat_id = message.chat.id
            if authorize_group(chat_id):
                await message.reply(f"""<pre>✅ Group Added</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This group has been added to allowed list.
⟐ <b>Group ID</b>: <code>{chat_id}</code>
⟐ <b>Group Title</b>: <code>{html.escape(message.chat.title) if message.chat.title else 'N/A'}</code>
━━━━━━━━━━━━━""")
            else:
                await message.reply(f"""<pre>ℹ️ Already Added</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This group is already in allowed list.
━━━━━━━━━━━━━""")
            return

        # Private chat without arguments
        await message.reply("""<pre>#WAYNE ─[ADD GROUP]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/add</code> or <code>.add</code>
⟐ <b>Usage 1</b>: <code>/add &lt;chat_id&gt;</code> (in private)
⟐ <b>Usage 2</b>: <code>/add</code> (in group, adds current group)
⟐ <b>Example</b>: <code>/add -1001234567890</code>
⟐ <b>Example</b>: <code>/add 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Adds group to allowed list (groups.json)</code>""")
        return

    try:
        chat_id = int(args[1])

        if authorize_group(chat_id):
            await message.reply(f"""<pre>✅ Group Added</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Group <code>{chat_id}</code> has been added to allowed list.
━━━━━━━━━━━━━""")
        else:
            await message.reply(f"""<pre>ℹ️ Already Added</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Group <code>{chat_id}</code> is already in allowed list.
━━━━━━━━━━━━━""")
    except ValueError:
        await message.reply("""<pre>❌ Invalid Chat ID</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please provide a valid chat ID (numeric).
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["rmv", ".rmv"]))
@owner_required
@auth_and_free_restricted  # Use the new combined decorator
async def rmv_group_command(client: Client, message: Message):
    """Remove group from allowed list - OWNER ONLY (works in both private and groups)"""
    args = message.text.split()

    if len(args) < 2:
        # If used in a group without arguments, remove that group
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            chat_id = message.chat.id
            if deauthorize_group(chat_id):
                await message.reply(f"""<pre>✅ Group Removed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This group has been removed from allowed list.
⟐ <b>Group ID</b>: <code>{chat_id}</code>
⟐ <b>Group Title</b>: <code>{html.escape(message.chat.title) if message.chat.title else 'N/A'}</code>
━━━━━━━━━━━━━""")
            else:
                await message.reply(f"""<pre>ℹ️ Not Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This group is not in allowed list.
━━━━━━━━━━━━━""")
            return

        # Private chat without arguments
        await message.reply("""<pre>#WAYNE ─[REMOVE GROUP]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/rmv</code> or <code>.rmv</code>
⟐ <b>Usage 1</b>: <code>/rmv &lt;chat_id&gt;</code> (in private)
⟐ <b>Usage 2</b>: <code>/rmv</code> (in group, removes current group)
⟐ <b>Example</b>: <code>/rmv -1001234567890</code>
⟐ <b>Example</b>: <code>/rmv 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Removes group from allowed list (groups.json)</code>""")
        return

    try:
        chat_id = int(args[1])

        if deauthorize_group(chat_id):
            await message.reply(f"""<pre>✅ Group Removed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Group <code>{chat_id}</code> has been removed from allowed list.
━━━━━━━━━━━━━""")
        else:
            await message.reply(f"""<pre>ℹ️ Not Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Group <code>{chat_id}</code> is not in allowed list.
━━━━━━━━━━━━━""")
    except ValueError:
        await message.reply("""<pre>❌ Invalid Chat ID</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please provide a valid chat ID (numeric).
━━━━━━━━━━━━━""")