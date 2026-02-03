# BOT/helper/permissions.py

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType
import json
import os

# File paths
GROUPS_FILE = "DATA/groups.json"
CONFIG_FILE = "FILES/config.json"
USERS_FILE = "DATA/users.json"

def load_owner_id():
    """Load OWNER_ID from config file"""
    try:
        with open(CONFIG_FILE, "r") as f:
            config_data = json.load(f)
            return config_data.get("OWNER")
    except FileNotFoundError:
        print("Config file not found.")
        return None

def load_allowed_groups():
    """Load allowed groups from groups.json - Returns a LIST"""
    if not os.path.exists(GROUPS_FILE):
        print("Groups file not found, creating empty list:", GROUPS_FILE)
        save_allowed_groups([])  # Create empty file
        return []

    try:
        with open(GROUPS_FILE, "r") as f:
            data = json.load(f)

        # Check if data is a list
        if isinstance(data, list):
            return data
        # Check if data is a dictionary with "groups" key
        elif isinstance(data, dict) and "groups" in data:
            return data["groups"]
        # If it's a dictionary without "groups" key, return empty list
        elif isinstance(data, dict):
            return []
        # If it's something else, return empty list
        else:
            print(f"Warning: Invalid format in {GROUPS_FILE}, expected list or dict with 'groups' key")
            return []
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"Error loading groups file, creating new one: {GROUPS_FILE}")
        save_allowed_groups([])
        return []

def save_allowed_groups(groups):
    """Save allowed groups to groups.json - Accepts a LIST"""
    # Ensure DATA directory exists
    os.makedirs("DATA", exist_ok=True)

    # Ensure groups is a list
    if not isinstance(groups, list):
        groups = []

    # Save as a list (not dict) for easy append/remove operations
    with open(GROUPS_FILE, "w") as f:
        json.dump(groups, f, indent=4)

def is_group_authorized(chat_id):
    """Check if group is authorized to use the bot"""
    allowed_groups = load_allowed_groups()
    return chat_id in allowed_groups

def authorize_group(chat_id):
    """Add group to authorized list - Returns True if added, False if already exists"""
    groups = load_allowed_groups()

    # Ensure groups is a list
    if not isinstance(groups, list):
        groups = []

    if chat_id not in groups:
        groups.append(chat_id)
        save_allowed_groups(groups)
        return True
    return False

def deauthorize_group(chat_id):
    """Remove group from authorized list - Returns True if removed, False if not found"""
    groups = load_allowed_groups()

    # Ensure groups is a list
    if not isinstance(groups, list):
        groups = []

    if chat_id in groups:
        groups.remove(chat_id)
        save_allowed_groups(groups)
        return True
    return False

def load_users():
    """Load users from users.json"""
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_users(users):
    """Save users to users.json"""
    os.makedirs("DATA", exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def get_user_plan(user_id):
    """Get user's plan information"""
    users = load_users()
    user_id_str = str(user_id)

    if user_id_str in users:
        return users[user_id_str].get("plan", {})
    return {}

def is_user_owner(user_id):
    """Check if user is owner"""
    owner_id = load_owner_id()
    return str(user_id) == str(owner_id)

def is_user_banned(user_id):
    """Check if user is banned"""
    try:
        if not os.path.exists("DATA/banned_users.txt"):
            return False

        with open("DATA/banned_users.txt", "r") as f:
            banned_users = f.read().splitlines()

        return str(user_id) in banned_users
    except:
        return False

def is_user_registered(user_id):
    """Check if user is registered"""
    users = load_users()
    return str(user_id) in users

def owner_required(func):
    """Decorator to check if user is owner"""
    async def wrapper(client, message):
        if not is_user_owner(message.from_user.id):
            await message.reply("""<pre>⛔ Owner Only</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This command is for owner only.
━━━━━━━━━━━━━""")
            return
        return await func(client, message)
    return wrapper

def admin_required(func):
    """Decorator to check if user is admin or owner"""
    async def wrapper(client, message):
        user_id = message.from_user.id

        if is_user_owner(user_id):
            return await func(client, message)

        users = load_users()
        user_data = users.get(str(user_id), {})
        user_role = user_data.get("role", "Free")

        if user_role not in ["Owner", "Admin"]:
            await message.reply("""<pre>⛔ Admin Only</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This command is for admin users only.
━━━━━━━━━━━━━""")
            return

        return await func(client, message)
    return wrapper

def registered_required(func):
    """Decorator to check if user is registered"""
    async def wrapper(client, message):
        if not is_user_registered(message.from_user.id):
            await message.reply("""<pre>⛔ Not Registered</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You need to register first with /register
━━━━━━━━━━━━━""")
            return
        return await func(client, message)
    return wrapper

def is_free_user(user_id):
    """Check if user is a free user"""
    users = load_users()
    user_id_str = str(user_id)

    if user_id_str not in users:
        return True  # Unregistered users are treated as free

    user_data = users[user_id_str]
    user_role = user_data.get("role", "Free")
    user_plan = user_data.get("plan", {}).get("plan", "Free")

    return user_role == "Free" and user_plan == "Free"

# NEW: Check if command is an admin command
def is_admin_command(command_text):
    """Check if command is an admin-only command"""
    if not command_text:
        return False

    # Admin commands (Owner/Admin only)
    admin_commands = [
        # Plan upgrade commands
        "plus", "pro", "elite", "vip", "ultimate",
        # User management
        "ban", "unban", "looser",
        # BIN management
        "banbin", "unbanbin",
        # Group management
        "add", "rmv",
        # Owner only commands
        "gc", "broad", "notused", "off", "on", "plans", "plan", "resett",
        # NEW: Keep pxstats as owner only, but addpx, rmvpx, vpx are NOT admin commands
        "pxstats", "rmvall"  # These remain owner only
    ]

    # Remove prefixes
    clean_command = command_text.lstrip('/').lstrip('.').lstrip('$').lower().split()[0]

    return clean_command in admin_commands

def is_allowed_for_free_users(command_text):
    """Check if a command is allowed for free users in private chats"""
    if not command_text:
        return False

    # FIXED: Free users in private chat can use these commands
    # UPDATED: Added proxy commands for all users
    allowed_commands = [
        "start", "register", "cmds", "info", "buy", "redeem",
        # Proxy commands - available for all users
        "addpx", "rmvpx", "vpx"
        # Removed: "gen", "fake", "gate", "bin", "sk", "au", "chk", "bu", "ad", "sq"
    ]

    # Remove prefixes
    clean_command = command_text.lstrip('/').lstrip('.').lstrip('$').lower().split()[0]

    return clean_command in allowed_commands

# NEW: Check if command is a charge command
def is_charge_command(command_text):
    """Check if command is a charge command (requires credits)"""
    if not command_text:
        return False

    # Charge commands that require 2 credits
    charge_commands = [
        "xx", "xo", "xs", "xc", "xp",  # Stripe charge
        "bt", "sh", "slf",  # Braintree & Shopify charge
        "mau", "mchk", "mxc", "mxp", "mxx"  # Mass charge
    ]

    # Remove prefixes
    clean_command = command_text.lstrip('/').lstrip('.').lstrip('$').lower().split()[0]

    return clean_command in charge_commands

# Check if command is an auth command (free for all IN GROUPS ONLY)
def is_auth_command(command_text):
    """Check if command is an auth command"""
    if not command_text:
        return False

    # Auth commands are free for everyone BUT ONLY IN AUTHORIZED GROUPS
    # UPDATED: Added "sq" for Square auth
    auth_commands = ["au", "chk", "bu", "ad", "sq"]

    # Remove prefixes
    clean_command = command_text.lstrip('/').lstrip('.').lstrip('$').lower().split()[0]

    return clean_command in auth_commands

# NEW: Check if command is a gate command (any gate/charge/auth command)
def is_gate_command(command_text):
    """Check if command is any type of gate command"""
    if not command_text:
        return False

    # All gate-related commands
    # UPDATED: Added "sq" for Square auth
    gate_commands = [
        # Auth commands
        "au", "chk", "bu", "ad", "sq",
        # Charge commands
        "xx", "xo", "xs", "xc", "xp", "bt", "sh", "slf",
        # Mass commands
        "mau", "mchk", "mxc", "mxp", "mxx"
    ]

    # Remove prefixes
    clean_command = command_text.lstrip('/').lstrip('.').lstrip('$').lower().split()[0]

    return clean_command in gate_commands

# NEW: Check if user has admin privileges
def is_user_admin(user_id):
    """Check if user is admin or owner"""
    if is_user_owner(user_id):
        return True

    users = load_users()
    user_data = users.get(str(user_id), {})
    user_role = user_data.get("role", "Free")

    return user_role in ["Owner", "Admin"]

# NEW: Check if command is a proxy command (available for all users)
def is_proxy_command(command_text):
    """Check if command is a proxy command (available for all users)"""
    if not command_text:
        return False

    # Proxy commands that are available for all authenticated users
    proxy_commands = ["addpx", "rmvpx", "vpx"]

    # Remove prefixes
    clean_command = command_text.lstrip('/').lstrip('.').lstrip('$').lower().split()[0]

    return clean_command in proxy_commands

# NEW: Check credits for charge commands - FIXED VERSION
def check_credits_for_charge(user_id, command_text):
    """Check if user has enough credits for charge commands - FIXED FOR ALL USERS"""
    try:
        # Try multiple import paths for credit module
        try:
            from BOT.gc.credit import has_sufficient_credits, get_user_credits
        except ImportError:
            try:
                from gc.credit import has_sufficient_credits, get_user_credits
            except ImportError:
                try:
                    from .credit import has_sufficient_credits, get_user_credits
                except ImportError:
                    # If all imports fail, create fallback functions
                    def has_sufficient_credits(user_id, amount):
                        return True, "Credit system not available"

                    def get_user_credits(user_id):
                        users = load_users()
                        user_data = users.get(str(user_id), {})
                        return user_data.get("plan", {}).get("credits", "100")

                    return True, "Credit system not available, allowing command"

        if not is_charge_command(command_text):
            return True, "Not a charge command"

        # Check if user has sufficient credits (2 credits per charge command)
        has_credits, msg = has_sufficient_credits(user_id, 2)

        # Parse the message to see if it's an error or success
        if not has_credits:
            # Check if it's a system error
            if "system" in msg.lower() or "error" in msg.lower() or "database" in msg.lower():
                # Get current credits for message
                current_credits = get_user_credits(user_id)
                # Get user plan for display
                users = load_users()
                user_data = users.get(str(user_id), {})
                user_plan = user_data.get("plan", {}).get("plan", "Free")

                return False, f"""<pre>❌ Credit System Error</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Please contact admin to fix credit system.
⟐ <b>Your Plan</b>: <code>{user_plan}</code>
⟐ <b>Your Credits</b>: <code>{current_credits}</code>
━━━━━━━━━━━━━"""

            # Normal insufficient credits case
            # Get current credits for message
            current_credits = get_user_credits(user_id)
            return False, f"""<pre>❌ Insufficient Credits</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This charge command requires 2 credits.
⟐ <b>Available Credits</b>: <code>{current_credits}</code>
⟐ <b>Required Credits</b>: <code>2</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Credits reset every 24 hours</code>
<b>~ Note:</b> <code>Upgrade to premium for more daily credits</code>"""

        return True, f"Sufficient credits available"

    except Exception as e:
        print(f"[check_credits_for_charge error] {e}")
        # Fallback: allow command if credit check fails
        return True, f"Error checking credits: {str(e)}"

# UPDATED: Combined decorator with credit check for charge commands - FIXED FOR FREE USERS
def auth_and_free_restricted(func):
    """Combined decorator that checks both group authorization and free user restrictions - FIXED"""
    async def wrapper(client, message):
        # Skip if not a text message
        if not message.text:
            return await func(client, message)

        text = message.text.strip()

        # Check if it's a bot command
        is_bot_cmd = (
            text.startswith('/') or 
            text.startswith('.') or 
            text.startswith('$')
        )

        if not is_bot_cmd:
            return await func(client, message)

        # Extract command
        parts = text.split()
        if not parts:
            return await func(client, message)

        command_text = parts[0]

        # ========== GROUP CHECKS ==========
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            # Allow /add and /rmv commands in any group (for owner to authorize)
            if text.startswith('/add') or text.startswith('.add') or \
               text.startswith('/rmv') or text.startswith('.rmv'):
                # Check if user is admin/owner for these commands
                if not is_user_admin(message.from_user.id):
                    await message.reply("""<pre>⛔ Admin Only</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This command is for admin users only.
━━━━━━━━━━━━━""")
                    return
                return await func(client, message)

            # Check if group is authorized
            if not is_group_authorized(message.chat.id):
                await message.reply_text(
                    "<pre>⛔️ Group Not Authorized</pre>\n"
                    "━━━━━━━━━━━━━\n"
                    "⟐ <b>Message</b>: This group is not authorized to use the bot.\n"
                    "⟐ <b>Contact</b>: <code>@D_A_DYY</code> for authorization.\n"
                    "━━━━━━━━━━━━━",
                    quote=True
                )
                return

            # Group is authorized - check command type
            user_id = message.from_user.id

            # Check for admin commands first
            if is_admin_command(command_text):
                if not is_user_admin(user_id):
                    await message.reply("""<pre>⛔ Admin Only</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This command is for admin users only.
━━━━━━━━━━━━━""")
                    return

            # Proxy commands are available for all users in authorized groups
            if is_proxy_command(command_text):
                return await func(client, message)

            # Auth commands are free for all users in authorized groups
            if is_auth_command(command_text):
                return await func(client, message)

            # Charge commands need credit check
            if is_charge_command(command_text):
                # Check credits
                has_credits, credit_msg = check_credits_for_charge(user_id, command_text)
                if not has_credits:
                    await message.reply(credit_msg)
                    return
                # Credits check passed, continue to command
                return await func(client, message)

            # Other commands (gen, fake, bin, etc.)
            return await func(client, message)

        # ========== PRIVATE CHAT CHECKS ==========
        elif message.chat.type == ChatType.PRIVATE:
            # Get user data
            users = load_users()
            user_id_str = str(message.from_user.id)

            # If user is not registered, they can only use /register and /start
            if user_id_str not in users:
                if text.startswith('/register') or text.startswith('.register') or \
                   text.startswith('/start') or text.startswith('.start'):
                    return await func(client, message)
                await message.reply("""<pre>🔒 Registration Required</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You need to register first with /register
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
                return

            user_data = users[user_id_str]
            user_role = user_data.get("role", "Free")
            user_plan = user_data.get("plan", {}).get("plan", "Free")
            private_status = user_data.get("plan", {}).get("private", "off")

            # Check admin commands in private (always allowed for admin/owner)
            if is_admin_command(command_text):
                if not is_user_admin(message.from_user.id):
                    await message.reply("""<pre>⛔ Admin Only</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This command is for admin users only.
━━━━━━━━━━━━━""")
                    return
                # Admin users can use admin commands in private
                return await func(client, message)

            # Check if user is premium (Owner, Admin, or has private access ON)
            is_premium_user = (
                user_role != "Free" or 
                user_plan != "Free" or 
                private_status == "on"
            )

            # Premium users have full access in private
            if is_premium_user:
                return await func(client, message)

            # ========== FREE USER IN PRIVATE CHAT ==========
            # Free users in private chat have VERY restricted access

            # Check if it's a basic allowed command
            if is_allowed_for_free_users(command_text):
                return await func(client, message)

            # Proxy commands are available for all users in private too
            if is_proxy_command(command_text):
                return await func(client, message)

            # FIXED: Free users CANNOT use any gate/charge/auth commands in private
            if is_gate_command(command_text) or is_auth_command(command_text) or is_charge_command(command_text):
                await message.reply("""<pre>Notification ❗️</pre>
<b>~ Message :</b> <code>Only For Premium Users !</code>
<b>~ Buy Premium →</b> <b><a href="https://t.me/D_A_DYY">Click Here</a></b>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Free users can use auth/charge commands ONLY in authorized groups</code>
<b>~ Note:</b> <code>Type /buy to get Premium for private access</code>
<b>~ Note:</b> <code>Join authorized groups to use gate commands for free</code>""")
                return

            # Unknown command for free user
            await message.reply("""<pre>Notification ❗️</pre>
<b>~ Message :</b> <code>Command not available for free users in private chat</code>
<b>~ Buy Premium →</b> <b><a href="https://t.me/D_A_DYY">Click Here</a></b>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Free users can use commands ONLY in authorized groups</code>
<b>~ Note:</b> <code>Type /buy to get Premium for private access</code>""")
            return

        # For other chat types (channels, etc.), allow
        return await func(client, message)

    return wrapper

# FIXED: Add back group_auth_required as an alias for compatibility
def group_auth_required(func):
    """Alias for auth_and_free_restricted for backward compatibility"""
    async def wrapper(client, message):
        return await auth_and_free_restricted(func)(client, message)
    return wrapper

async def is_premium_user(message: Message) -> bool:
    """Check if user has premium plan - ONLY for bot commands"""
    try:
        # First check if it's a bot command
        if not message.text:
            return False

        text = message.text.strip()

        # Check if message starts with bot command prefix (/, ., or $)
        is_bot_cmd = (
            text.startswith('/') or 
            text.startswith('.') or 
            text.startswith('$')
        )

        if not is_bot_cmd:
            return False  # Not a bot command, ignore

        users = load_users()
        user_id = str(message.from_user.id)

        user_data = users.get(user_id)
        if not user_data:
            await message.reply("""<pre>🔒 Not Registered</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You need to register first with /register
━━━━━━━━━━━━━""")
            return False

        user_role = user_data.get("role", "Free")
        user_plan = user_data.get("plan", {}).get("plan", "Free")
        private_status = user_data.get("plan", {}).get("private", "off")

        # Premium users are: Owner, Admin, or users with private access ON
        is_premium = (
            user_role != "Free" or 
            user_plan != "Free" or 
            private_status == "on"
        )

        if not is_premium:
            # Check if it's an auth command (free for all)
            clean_command = text.lstrip('/').lstrip('.').lstrip('$').lower().split()[0]

            if is_auth_command(clean_command):
                return True  # Auth commands are free for all

            # Check if it's a proxy command (available for all)
            if is_proxy_command(clean_command):
                return True  # Proxy commands are available for all

            # Check if it's an admin command
            if is_admin_command(clean_command):
                await message.reply("""<pre>⛔ Admin Only</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This command is for admin users only.
━━━━━━━━━━━━━""")
                return False

            # Check if user is in an authorized group
            if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                if is_group_authorized(message.chat.id):
                    # Free users can use charge commands in authorized groups (with credits)
                    return True
                else:
                    await message.reply("""<pre>⛔️ Group Not Authorized</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This group is not authorized to use the bot.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for authorization.
━━━━━━━━━━━━━""")
                    return False

            # Free user in private chat - show premium message
            await message.reply("""<pre>Notification ❗️</pre>
<b>~ Message :</b> <code>Only For Premium Users !</code>
<b>~ Buy Premium →</b> <b><a href="https://t.me/D_A_DYY">Click Here</a></b>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Free users can use charge commands in authorized groups with credit deduction</code>
<b>~ Note:</b> <code>Type /buy to get Premium for private access</code>""")
            return False

        return True  # ✅ Premium user
    except Exception as e:
        print(f"[ERROR in is_premium_user] {e}")
        return False

async def check_private_access(message: Message) -> bool:
    """Check if user can access private commands - ONLY for bot commands"""
    try:
        # ✅ Step 0: Check if it's a bot command
        if not message.text:
            return False  # Not a text message, not a bot command

        text = message.text.strip()

        # Check if message starts with bot command prefix (/, ., or $)
        is_bot_cmd = (
            text.startswith('/') or 
            text.startswith('.') or 
            text.startswith('$')
        )

        if not is_bot_cmd:
            return False  # Not a bot command, ignore

        # ✅ Step 1: Check if group is allowed
        allowed_groups = load_allowed_groups()

        # Check if in group/supergroup
        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            if message.chat.id in allowed_groups:
                return True  # Allowed group → no private check
            else:
                # Not authorized group - ONLY for bot commands
                await message.reply_text(
                    "<pre>⛔️ Group Not Authorized</pre>\n"
                    "━━━━━━━━━━━━━\n"
                    "⟐ <b>Message</b>: This group is not authorized to use the bot.\n"
                    "⟐ <b>Contact</b>: <code>@D_A_DYY</code> for authorization.\n"
                    "━━━━━━━━━━━━━",
                    quote=True
                )
                return False

        # ✅ Step 2: Private chat → check user plan
        users = load_users()
        user_id = str(message.from_user.id)
        user_data = users.get(user_id)

        if not user_data:
            await message.reply("""<pre>🔒 Not Registered</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You need to register first with /register
━━━━━━━━━━━━━""")
            return False

        user_role = user_data.get("role", "Free")
        user_plan = user_data.get("plan", {}).get("plan", "Free")
        private_status = user_data.get("plan", {}).get("private", "off")

        # Check if user is premium
        is_premium = (
            user_role != "Free" or 
            user_plan != "Free" or 
            private_status == "on"
        )

        if not is_premium:
            # Check if command is allowed for free users in private
            clean_command = text.lstrip('/').lstrip('.').lstrip('$').lower().split()[0]

            # Check admin commands
            if is_admin_command(clean_command):
                await message.reply("""<pre>⛔ Admin Only</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: This command is for admin users only.
━━━━━━━━━━━━━""")
                return False

            # Check auth commands (free for all)
            if is_auth_command(clean_command):
                return True

            # Check proxy commands (available for all)
            if is_proxy_command(clean_command):
                return True

            allowed_commands = [
                "start", "register", "cmds", "info", "buy", "redeem",
                "gen", "fake", "gate", "bin", "sk", 
                "au", "chk", "bu", "ad", "sq"  # Auth commands are free
            ]

            if clean_command in allowed_commands:
                return True  # Allowed command for free users

            # Premium-only command for free user
            await message.reply("""<pre>Notification ❗️</pre>
<b>~ Message :</b> <code>Only For Premium Users !</code>
<b>~ Buy Premium →</b> <b><a href="https://t.me/D_A_DYY">Click Here</a></b>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Free users can use charge commands in authorized groups with credit deduction</code>
<b>~ Note:</b> <code>Type /buy to get Premium for private access</code>""")
            return False

        return True
    except Exception as e:
        print(f"[ERROR in check_private_access] {e}")
        return False

def apply_global_middlewares():
    """DEPRECATED: Global middlewares are no longer used"""
    # This function is kept for compatibility but does nothing
    # Commands use @group_auth_required decorator instead
    pass

# NEW: Initialize user credits on registration
def initialize_user_on_registration(user_id):
    """Initialize credits for newly registered user"""
    try:
        # Try multiple import paths
        try:
            from BOT.gc.credit import initialize_user_credits
        except ImportError:
            try:
                from gc.credit import initialize_user_credits
            except ImportError:
                try:
                    from .credit import initialize_user_credits
                except ImportError:
                    # Fallback if all imports fail
                    def initialize_user_credits(user_id):
                        return True
                    return True
        return initialize_user_credits(user_id)
    except Exception as e:
        print(f"[initialize_user_on_registration error] {e}")
        return False

# Ensure groups.json file exists with proper format
if not os.path.exists(GROUPS_FILE):
    print(f"Creating {GROUPS_FILE} with empty list...")
    save_allowed_groups([])
else:
    # Validate existing groups.json format
    try:
        with open(GROUPS_FILE, "r") as f:
            data = json.load(f)

        # If it's a dictionary, convert it to list format
        if isinstance(data, dict):
            print(f"Converting {GROUPS_FILE} from dict to list format...")
            if "groups" in data:
                save_allowed_groups(data["groups"])
            else:
                save_allowed_groups([])
    except:
        # If file is corrupted, recreate it
        print(f"Recreating corrupted {GROUPS_FILE}...")
        save_allowed_groups([])
