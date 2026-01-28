# BOT/helper/start.py

import json
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
from pyrogram.types import CallbackQuery
import html
import pytz

# Import from permissions module
from .permissions import (
    load_users, get_user_plan, is_user_banned, is_user_owner, 
    is_user_registered, load_owner_id, group_auth_required, save_users
)

# Import disabled commands functions from Admins module - FIXED IMPORT
from .Admins import (
    is_command_disabled, get_command_offline_message,
    is_user_restricted_for_command, get_command_status
)

# Import gates menus from startg.py
from .startg import GATES_MENUS

# Try to import from gc folder first, then from helper
try:
    from BOT.gc.credit import initialize_user_credits, get_user_credits
except ImportError:
    # Fallback if gc folder doesn't exist
    from .credit import initialize_user_credits, get_user_credits

def clean_text(text):
    if not text:
        return "N/A"
    return html.unescape(text)

@Client.on_message(filters.command("start"))
@group_auth_required
async def start_command(client: Client, message: Message):
    # Check if command is disabled
    if is_command_disabled("start"):
        await message.reply(get_command_offline_message("start"))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, "start"):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    animated_texts = ["〔", "〔D", "〔A", "〔DYY", "〔DADYY〕"]

    sent = await message.reply("<pre>〔</pre>", quote=True)

    for text in animated_texts[1:]:
        await asyncio.sleep(0.2)
        await sent.edit_text(f"<pre>{text}</pre>")

    # User's display name
    name = message.from_user.first_name
    if message.from_user.last_name:
        name += f" {message.from_user.last_name}"
    profile = f"<a href='tg://user?id={message.from_user.id}'>{name}</a>"

    # Get user credits for display
    user_id_str = str(message.from_user.id)
    users = load_users()
    user_credits = "0"

    if user_id_str in users:
        user_data = users[user_id_str]
        user_credits = user_data.get("plan", {}).get("credits", "0")

    final_text = f"""
[<a href='https://t.me/WayneCHK'>⛯</a>] <b>WAYNE | Version - 1.0</b>
<pre>Constantly Upgrading...</pre>
━━━━━━━━━━━━━
<b>Hello,</b> {profile}
<i>How Can I Help You Today.?! 📊</i>
⌀ <b>Your UserID</b> - <code>{message.from_user.id}</code>
⛶ <b>BOT Status</b> - <code>Online 🟢</code>
⟐ <b>Credits</b> - <code>{user_credits}</code>
⎔ <b>Explore</b> - <b>Click the buttons below to discover</b>
all the features we offer!
"""

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Register", callback_data="register"),
            InlineKeyboardButton("Commands", callback_data="home")
        ],
        [
            InlineKeyboardButton("Buy Premium", callback_data="buy"),
            InlineKeyboardButton("Close", callback_data="close")
        ]
    ])

    await asyncio.sleep(0.5)
    await sent.edit_text(final_text.strip(), reply_markup=keyboard, disable_web_page_preview=True)

USERS_FILE = "DATA/users.json"
CONFIG_FILE = "FILES/config.json"

def get_ist_time():
    ist = pytz.timezone("Asia/Kolkata")
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def default_plan(user_id):
    OWNER_ID = load_owner_id()

    if str(user_id) == str(OWNER_ID):
        return {
            "plan": "Owner",
            "activated_at": get_ist_time(),
            "expires_at": None,
            "antispam": None,
            "mlimit": None,
            "credits": "∞",  # Owner gets infinite credits
            "badge": "🎭",
            "private": "on",
            "keyredeem": 0
        }

    return {
        "plan": "Free",
        "activated_at": get_ist_time(),
        "expires_at": None,
        "antispam": 15,
        "mlimit": 5,
        "credits": "100",  # Initial daily credits for free users
        "badge": "🧿",
        "private": "off",
        "keyredeem": 0
    }

@Client.on_callback_query(filters.regex("register"))
async def register_callback(client, callback_query):
    users = load_users()
    user_id = str(callback_query.from_user.id)

    OWNER_ID = load_owner_id()

    if user_id in users:
        user_data = users[user_id]
        first_name = user_data['first_name']
        profile = f"<a href='tg://user?id={user_id}'>{first_name}</a> ({user_data['role']})"

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Home", callback_data="home"),
             InlineKeyboardButton("Exit", callback_data="exit")]
        ])

        await callback_query.message.reply_text(f"<pre>User {profile} You Are Already Registered</pre>", reply_markup=buttons)
        return

    first_name = callback_query.from_user.first_name
    username = callback_query.from_user.username if callback_query.from_user.username else None

    plan_data = default_plan(user_id)
    role = plan_data["plan"]

    users[user_id] = {
        "first_name": first_name,
        "username": username,
        "user_id": callback_query.from_user.id,
        "registered_at": get_ist_time(),
        "plan": plan_data,
        "role": role,
        "last_credit_reset": get_ist_time()
    }

    save_users(users)

    # Initialize user credits
    initialize_user_credits(callback_query.from_user.id)

    user_data = users[user_id]
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Home", callback_data="home"),
         InlineKeyboardButton("Exit", callback_data="exit")]
    ])

    await callback_query.message.edit_text(f"""<pre>Registration Successfull ✔</pre>
╭━━━━━━━━━━
│● <b>Name</b> : <code>{first_name} [{user_data['plan']['badge']}]</code>
│● <b>UserID</b> : <code>{user_id}</code>
│● <b>Credits</b> : <code>{user_data['plan']['credits']}</code>
│● <b>Role</b> : <code>{user_data['role']}</code>
╰━━━━━━━━━━""", reply_markup=buttons)


@Client.on_message(filters.command(["register", ".register"]))
@group_auth_required
async def register_command(client, message):
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

    OWNER_ID = load_owner_id()

    if user_id in users:
        user_data = users[user_id]
        first_name = user_data['first_name']
        profile = f"<a href='tg://user?id={user_id}'>{first_name}</a> ({user_data['role']})"

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Home", callback_data="home"),
             InlineKeyboardButton("Exit", callback_data="exit")]
        ])

        await client.send_message(
            chat_id=message.chat.id,
            text=f"<pre>User {profile} You Are Already Registered</pre>",
            reply_to_message_id=message.id,
            reply_markup=buttons
        )
        return

    first_name = message.from_user.first_name
    username = message.from_user.username if message.from_user.username else None

    plan_data = default_plan(user_id)
    role = plan_data["plan"]

    users[user_id] = {
        "first_name": first_name,
        "username": username,
        "user_id": message.from_user.id,
        "registered_at": get_ist_time(),
        "plan": plan_data,
        "role": role,
        "last_credit_reset": get_ist_time()
    }

    save_users(users)

    # Initialize user credits
    initialize_user_credits(message.from_user.id)

    user_data = users[user_id]
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Home", callback_data="home"),
         InlineKeyboardButton("Exit", callback_data="exit")]
    ])

    await client.send_message(
        chat_id=message.chat.id,
        text=f"""<pre>Registration Successfull ✔</pre>
╭━━━━━━━━━━
│● <b>Name</b> : <code>{first_name} [{user_data['plan']['badge']}]</code>
│● <b>UserID</b> : <code>{user_id}</code>
│● <b>Credits</b> : <code>{user_data['plan']['credits']}</code>
│● <b>Role</b> : <code>{user_data['role']}</code>
╰━━━━━━━━━━""",
        reply_to_message_id=message.id,
        reply_markup=buttons
    )

# ==================== /buy COMMAND ====================
@Client.on_message(filters.command(["buy", ".buy"]))
@group_auth_required
async def buy_command(client: Client, message: Message):
    """Show premium plans for purchase"""
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

    # Detailed plan information with credit system explanation
    plan_info = """<pre>#WAYNE ─[PREMIUM PLANS]─</pre>
━━━━━━━━━━━━━
<b>Choose the perfect plan for your needs!</b>

<b>Available Premium Plans:</b>

<b>💠 Plus Plan - $1</b>
⟐ <b>Daily Credits</b>: <code>200 Credits</code>
⟐ <b>Anti-Spam Delay</b>: <code>10 seconds</code>
⟐ <b>Mass Limit</b>: <code>10 cards per mass check</code>
⟐ <b>Badge</b>: <code>💠</code>
⟐ <b>Private Access</b>: <code>✅ Enabled</code>
⟐ <b>Features</b>: Basic gates access, 5 gate types

<b>🔰 Pro Plan - $3</b>
⟐ <b>Daily Credits</b>: <code>500 Credits</code>
⟐ <b>Anti-Spam Delay</b>: <code>8 seconds</code>
⟐ <b>Mass Limit</b>: <code>20 cards per mass check</code>
⟐ <b>Badge</b>: <code>🔰</code>
⟐ <b>Private Access</b>: <code>✅ Enabled</code>
⟐ <b>Features</b>: All gates access, 10 gate types

<b>📧 Elite Plan - $6</b>
⟐ <b>Daily Credits</b>: <code>1000 Credits</code>
⟐ <b>Anti-Spam Delay</b>: <code>5 seconds</code>
⟐ <b>Mass Limit</b>: <code>30 cards per mass check</code>
⟐ <b>Badge</b>: <code>📧</code>
⟐ <b>Private Access</b>: <code>✅ Enabled</code>
⟐ <b>Features</b>: All gates + priority access

<b>🎖 VIP Plan - $15</b>
⟐ <b>Daily Credits</b>: <code>2000 Credits</code>
⟐ <b>Anti-Spam Delay</b>: <code>3 seconds</code>
⟐ <b>Mass Limit</b>: <code>50 cards per mass check</code>
⟐ <b>Badge</b>: <code>🎖</code>
⟐ <b>Private Access</b>: <code>✅ Enabled</code>
⟐ <b>Features</b>: All gates + VIP support + early access

<b>⭐️ ULTIMATE Plan - $25</b>
⟐ <b>Daily Credits</b>: <code>2500 Credits</code>
⟐ <b>Anti-Spam Delay</b>: <code>2 seconds</code>
⟐ <b>Mass Limit</b>: <code>100 cards per mass check</code>
⟐ <b>Badge</b>: <code>⭐️</code>
⟐ <b>Private Access</b>: <code>✅ Enabled</code>
⟐ <b>Features</b>: All features + lifetime updates + custom gates

━━━━━━━━━━━━━
<b>Credit System (DAILY RESET):</b>
⟐ <b>Free Users</b>: <code>100 daily credits (resets every 24h)</code>
⟐ <b>Auth Commands</b>: <code>FREE for all users</code>
⟐ <b>Charge Commands</b>: <code>2 credits per use</code>
⟐ <b>Premium Users</b>: <code>Daily credits reset every 24h</code>
⟐ <b>Owner/Admin</b>: <code>Unlimited credits (∞)</code>

━━━━━━━━━━━━━
<b>Free Plan (For Comparison):</b>
⟐ <b>Daily Credits</b>: <code>100 Daily Credits</code>
⟐ <b>Anti-Spam Delay</b>: <code>15 seconds</code>
⟐ <b>Mass Limit</b>: <code>5 cards per mass check</code>
⟐ <b>Badge</b>: <code>🧿</code>
⟐ <b>Private Access</b>: <code>❌ Disabled</code>
⟐ <b>Features</b>: Auth commands in groups, limited access

━━━━━━━━━━━━━
<b>How to Purchase:</b>
1. Contact <code>@D_A_DYY</code> on Telegram
2. Specify which plan you want
3. Make payment (Crypto/CashApp/PayPal)
4. Receive your plan activation

<b>~ Note:</b> <code>All plans come with 24/7 support</code>
<b>~ Note:</b> <code>Bulk discounts available for multiple purchases</code>
<b>~ Note:</b> <code>Use /redeem for gift codes</code>
<b>~ Note:</b> <code>Use /info to check your credit balance and plan details</code>"""

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Contact Owner", url="https://t.me/D_A_DYY"),
            InlineKeyboardButton("Join Channel", url="https://t.me/WayneCHK")
        ],
        [
            InlineKeyboardButton("Home", callback_data="home"),
            InlineKeyboardButton("Close", callback_data="close")
        ]
    ])

    await message.reply(plan_info, reply_markup=buttons)

@Client.on_message(filters.command(["cmds", ".cmds"]))
@group_auth_required
async def show_cmds(client, message):
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

    # Show the main menu directly with all 4 options including Buy
    home_text = """<pre>JOIN BEFORE USING. ✔️</pre>
<b>~ Main :</b> <b><a href="https://t.me/WayneCHK">Join Now</a></b>
<b>~ Chat Group :</b> <b><a href="https://t.me/WayneCHK">Join Now</a></b>
<b>~ Scrapper :</b> <b><a href="https://t.me/WayneCHK">Join Now</a></b>
<b>~ Note :</b> <code>Report Bugs To @D_A_DYY</code>
<b>~ Proxy :</b> <code>Live 💎</code>
<pre>Choose Category :</pre>"""

    home_buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Gates", callback_data="gates"),
            InlineKeyboardButton("Tools", callback_data="tools")
        ],
        [
            InlineKeyboardButton("Admins", callback_data="admins"),
            InlineKeyboardButton("Buy", callback_data="buy")
        ],
        [
            InlineKeyboardButton("Close", callback_data="close")
        ]
    ])

    await message.reply(
        home_text,
        reply_to_message_id=message.id,
        reply_markup=home_buttons,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex("^(exit|home|buy|close|tools|admins)$"))
async def handle_main_callbacks(client, callback_query):
    data = callback_query.data

    if data == "exit" or data == "close":
        # Edit the message to show "Thanks For Using #WAYNE"
        await callback_query.message.edit_text("<pre>Thanks For Using #WAYNE</pre>")

    elif data == "home":
        # Home text with 4 options: Gates, Tools, Admins, Buy
        home_text = """<pre>JOIN BEFORE USING. ✔️</pre>
<b>~ Main :</b> <b><a href="https://t.me/WayneCHK">Join Now</a></b>
<b>~ Chat Group :</b> <b><a href="https://t.me/WayneCHK">Join Now</a></b>
<b>~ Scrapper :</b> <b><a href="https://t.me/WayneCHK">Join Now</a></b>
<b>~ Note :</b> <code>Report Bugs To @D_A_DYY</code>
<b>~ Proxy :</b> <code>Live 💎</code>
<pre>Choose Category :</pre>"""

        home_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Gates", callback_data="gates"),
                InlineKeyboardButton("Tools", callback_data="tools")
            ],
            [
                InlineKeyboardButton("Admins", callback_data="admins"),
                InlineKeyboardButton("Buy", callback_data="buy")
            ],
            [
                InlineKeyboardButton("Close", callback_data="close")
            ]
        ])

        await callback_query.message.edit_text(
            home_text,
            reply_markup=home_buttons,
            disable_web_page_preview=True
        )

    elif data == "buy":
        # Show buy plan information
        plan_info = """<pre>#WAYNE ─[PREMIUM PLANS]─</pre>
━━━━━━━━━━━━━
<b>Choose the perfect plan for your needs!</b>

<b>Available Premium Plans:</b>

<b>💠 Plus Plan - $1</b>
⟐ <b>Daily Credits</b>: <code>200 Credits</code>
⟐ <b>Anti-Spam Delay</b>: <code>10 seconds</code>
⟐ <b>Mass Limit</b>: <code>10 cards per mass check</code>
⟐ <b>Badge</b>: <code>💠</code>
⟐ <b>Private Access</b>: <code>✅ Enabled</code>
⟐ <b>Features</b>: Basic gates access, 5 gate types

<b>🔰 Pro Plan - $3</b>
⟐ <b>Daily Credits</b>: <code>500 Credits</code>
⟐ <b>Anti-Spam Delay</b>: <code>8 seconds</code>
⟐ <b>Mass Limit</b>: <code>20 cards per mass check</code>
⟐ <b>Badge</b>: <code>🔰</code>
⟐ <b>Private Access</b>: <code>✅ Enabled</code>
⟐ <b>Features</b>: All gates access, 10 gate types

<b>📧 Elite Plan - $6</b>
⟐ <b>Daily Credits</b>: <code>1000 Credits</code>
⟐ <b>Anti-Spam Delay</b>: <code>5 seconds</code>
⟐ <b>Mass Limit</b>: <code>30 cards per mass check</code>
⟐ <b>Badge</b>: <code>📧</code>
⟐ <b>Private Access</b>: <code>✅ Enabled</code>
⟐ <b>Features</b>: All gates + priority access

<b>🎖 VIP Plan - $15</b>
⟐ <b>Daily Credits</b>: <code>2000 Credits</code>
⟐ <b>Anti-Spam Delay</b>: <code>3 seconds</code>
⟐ <b>Mass Limit</b>: <code>50 cards per mass check</code>
⟐ <b>Badge</b>: <code>🎖</code>
⟐ <b>Private Access</b>: <code>✅ Enabled</code>
⟐ <b>Features</b>: All gates + VIP support + early access

<b>⭐️ ULTIMATE Plan - $25</b>
⟐ <b>Daily Credits</b>: <code>2500 Credits</code>
⟐ <b>Anti-Spam Delay</b>: <code>2 seconds</code>
⟐ <b>Mass Limit</b>: <code>100 cards per mass check</code>
⟐ <b>Badge</b>: <code>⭐️</code>
⟐ <b>Private Access</b>: <code>✅ Enabled</code>
⟐ <b>Features</b>: All features + lifetime updates + custom gates

━━━━━━━━━━━━━
<b>Credit System (DAILY RESET):</b>
⟐ <b>Free Users</b>: <code>100 daily credits (resets every 24h)</code>
⟐ <b>Auth Commands</b>: <code>FREE for all users</code>
⟐ <b>Charge Commands</b>: <code>2 credits per use</code>
⟐ <b>Premium Users</b>: <code>Daily credits reset every 24h</code>
⟐ <b>Owner/Admin</b>: <code>Unlimited credits (∞)</code>

━━━━━━━━━━━━━
<b>How to Purchase:</b>
1. Contact <code>@D_A_DYY</code> on Telegram
2. Specify which plan you want
3. Make payment (Crypto/CashApp/PayPal)
4. Receive your plan activation

<b>~ Note:</b> <code>All plans come with 24/7 support</code>
<b>~ Note:</b> <code>Bulk discounts available for multiple purchases</code>"""

        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Contact Owner", url="https://t.me/D_A_DYY"),
                InlineKeyboardButton("Join Channel", url="https://t.me/WayneCHK")
            ],
            [
                InlineKeyboardButton("Home", callback_data="home"),
                InlineKeyboardButton("Close", callback_data="close")
            ]
        ])

        await callback_query.message.edit_text(plan_info, reply_markup=buttons)

    elif data == "tools":
        # Get dynamic status for tool commands
        info_status = get_command_status("info")
        fake_status = get_command_status("fake")
        gen_status = get_command_status("gen")
        gate_status = get_command_status("gate")
        bin_status = get_command_status("bin")
        sk_status = get_command_status("sk")
        redeem_status = get_command_status("redeem")

        # Get status for proxy commands (FOR ALL USERS)
        addpx_status = get_command_status("addpx")
        rmvpx_status = get_command_status("rmvpx")
        vpx_status = get_command_status("vpx")
        buy_status = get_command_status("buy")

        # Updated tools buttons with proxy commands FOR ALL USERS
        tools_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("/info", callback_data="tool_info"),
                InlineKeyboardButton("/fake", callback_data="tool_fake")
            ],
            [
                InlineKeyboardButton("/gen", callback_data="tool_gen"),
                InlineKeyboardButton("/gate", callback_data="tool_gate")
            ],
            [
                InlineKeyboardButton("/bin", callback_data="tool_bin"),
                InlineKeyboardButton("/sk", callback_data="tool_sk")
            ],
            [
                InlineKeyboardButton("/redeem", callback_data="tool_redeem"),
                InlineKeyboardButton("Proxy", callback_data="tool_proxy")
            ],
            [
                InlineKeyboardButton("/buy", callback_data="buy"),
            ],
            [
                InlineKeyboardButton("Back", callback_data="home"),
                InlineKeyboardButton("Close", callback_data="close")
            ]
        ])

        tools_text = f"""<pre>#WAYNE 〔Tools Menu〕</pre>
━━━━━━━━━━━━━
<b>Available Tools :</b>

⟐ <b>/info</b> - <code>Check your account information and credits</code>
⟐ <b>Status:</b> <code>{info_status}</code>

⟐ <b>/fake</b> - <code>Generate fake address</code>
⟐ <b>Status:</b> <code>{fake_status}</code>

⟐ <b>/gen</b> - <code>Generate valid CCs</code>
⟐ <b>Status:</b> <code>{gen_status}</code>

⟐ <b>/gate</b> - <code>Scan website for payment gateways</code>
⟐ <b>Status:</b> <code>{gate_status}</code>

⟐ <b>/bin</b> - <code>Check BIN information</code>
⟐ <b>Status:</b> <code>{bin_status}</code>

⟐ <b>/sk</b> - <code>Check Stripe secret key</code>
⟐ <b>Status:</b> <code>{sk_status}</code>

⟐ <b>/redeem</b> - <code>Redeem gift codes</code>
⟐ <b>Status:</b> <code>{redeem_status}</code>

⟐ <b>Proxy Commands</b> - <code>Manage proxy settings (Click Proxy button)</code>
⟐ <b>Status:</b> <code>Active ✅</code>

⟐ <b>/buy</b> - <code>Buy premium plans</code>
⟐ <b>Status:</b> <code>{buy_status}</code>

━━━━━━━━━━━━━
<b>~ Note:</b> <code>Disabled commands show ❌ status</code>
<b>~ Note:</b> <code>Use /on command to enable disabled commands (Owner Only)</code>"""

        await callback_query.message.edit_text(
            tools_text,
            reply_markup=tools_buttons
        )

    elif data == "admins":
        # Admins section - Only for admin users
        users = load_users()
        user_id = str(callback_query.from_user.id)

        if user_id in users:
            user_role = users[user_id].get("role", "Free")

            if user_role in ["Owner", "Admin"]:
                # Get dynamic status for admin commands
                plan_status = get_command_status("plan")
                banbin_status = get_command_status("banbin")
                unbanbin_status = get_command_status("unbanbin")
                ban_status = get_command_status("ban")
                unban_status = get_command_status("unban")
                add_status = get_command_status("add")
                rmv_status = get_command_status("rmv")
                looser_status = get_command_status("looser")
                gc_status = get_command_status("gc")
                broad_status = get_command_status("broad")
                notused_status = get_command_status("notused")
                off_status = get_command_status("off")
                on_status = get_command_status("on")
                resett_status = get_command_status("resett")
                pxstats_status = get_command_status("pxstats")
                rmvall_status = get_command_status("rmvall")

                # Updated admin buttons with ADMIN PROXY COMMANDS
                admin_buttons = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("/plan", callback_data="admin_plan"),
                        InlineKeyboardButton("/banbin", callback_data="admin_banbin")
                    ],
                    [
                        InlineKeyboardButton("/unbanbin", callback_data="admin_unbanbin"),
                        InlineKeyboardButton("/ban", callback_data="admin_ban")
                    ],
                    [
                        InlineKeyboardButton("/unban", callback_data="admin_unban"),
                        InlineKeyboardButton("/add", callback_data="admin_add")
                    ],
                    [
                        InlineKeyboardButton("/rmv", callback_data="admin_rmv"),
                        InlineKeyboardButton("/looser", callback_data="admin_looser")
                    ],
                    [
                        InlineKeyboardButton("/gc", callback_data="admin_gc"),
                        InlineKeyboardButton("/broad", callback_data="admin_broad")
                    ],
                    [
                        InlineKeyboardButton("/notused", callback_data="admin_notused"),
                        InlineKeyboardButton("/off", callback_data="admin_off")
                    ],
                    [
                        InlineKeyboardButton("/on", callback_data="admin_on"),
                        InlineKeyboardButton("/resett", callback_data="admin_resett")
                    ],
                    [
                        InlineKeyboardButton("/pxstats", callback_data="admin_pxstats"),
                        InlineKeyboardButton("/rmvall", callback_data="admin_rmvall")
                    ],
                    [
                        InlineKeyboardButton("Back", callback_data="home"),
                        InlineKeyboardButton("Close", callback_data="close")
                    ]
                ])

                admin_text = f"""<pre>#WAYNE 〔Admin Panel〕</pre>
━━━━━━━━━━━━━
⟐ <b>Welcome, {user_role}!</b>
⟐ <b>Role</b>: <code>{user_role}</code>
⟐ <b>Available Admin Commands:</b>
━━━━━━━━━━━━━
<b>User Management:</b>
⟐ <b>/plan</b> - <code>Show plan commands menu</code> [{plan_status}]
⟐ <b>/ban</b> - <code>Ban user from bot</code> [{ban_status}]
⟐ <b>/unban</b> - <code>Unban user</code> [{unban_status}]
⟐ <b>/looser</b> - <code>Downgrade user to FREE</code> [{looser_status}]
⟐ <b>/resett</b> - <code>Reset user credits</code> [{resett_status}]

<b>BIN Management:</b>
⟐ <b>/banbin</b> - <code>Ban BIN from usage</code> [{banbin_status}]
⟐ <b>/unbanbin</b> - <code>Unban BIN</code> [{unbanbin_status}]

<b>Group Management:</b>
⟐ <b>/add</b> - <code>Add group to allowed list</code> [{add_status}]
⟐ <b>/rmv</b> - <code>Remove group from allowed list</code> [{rmv_status}]

<b>Proxy Management (Admin Only):</b>
⟐ <b>/pxstats</b> - <code>Show proxy statistics</code> [{pxstats_status}]
⟐ <b>/rmvall</b> - <code>Remove all proxies</code> [{rmvall_status}]

<b>Owner Only Commands:</b>
⟐ <b>/gc</b> - <code>Generate gift codes</code> [{gc_status}]
⟐ <b>/broad</b> - <code>Broadcast message</code> [{broad_status}]
⟐ <b>/notused</b> - <code>Check unused codes</code> [{notused_status}]
⟐ <b>/off</b> - <code>Disable command globally</code> [{off_status}]
⟐ <b>/on</b> - <code>Enable command globally</code> [{on_status}]
━━━━━━━━━━━━━
<b>~ Note:</b> <code>[] shows command status (✅=Active, ❌=Disabled)</code>
<b>~ Note:</b> <code>Owner can disable/enable commands with /off and /on</code>"""

                await callback_query.message.edit_text(
                    admin_text,
                    reply_markup=admin_buttons
                )
            else:
                await callback_query.answer("⛔ Access Denied! Admin Only.", show_alert=True)
        else:
            await callback_query.answer("⛔ You need to register first!", show_alert=True)

# GATES CALLBACK HANDLER - This must come BEFORE the general callback handler
@Client.on_callback_query(filters.regex("^(gates|gates_auth|gates_charge|gates_mass|auth_stripe|auth_braintree|auth_adyen|charge_stripe|charge_braintree|charge_shopify)$"))
async def handle_gates_callbacks(client, callback_query):
    """Handle all gates-related callback queries using GATES_MENUS"""
    data = callback_query.data

    if data in GATES_MENUS:
        try:
            text, buttons = GATES_MENUS[data]()
            await callback_query.message.edit_text(text, reply_markup=buttons)
        except Exception as e:
            print(f"Error handling gates callback {data}: {e}")
            await callback_query.answer("⚠️ Error loading menu", show_alert=True)
    else:
        # Fallback for gates menu
        if data == "gates":
            text = """<pre>#WAYNE 〔Gates Menu〕</pre>
━━━━━━━━━━━━━
<b>Available Gate Categories:</b>

⟐ <b>Auth Gates</b> - <code>Check card validity via authentication</code>
⟐ <b>Charge Gates</b> - <code>Test cards with small charges</code>
⟐ <b>Mass Gates</b> - <code>Check multiple cards at once</code>

━━━━━━━━━━━━━
<b>~ Note:</b> <code>Premium features require plan upgrade</code>
<b>~ Note:</b> <code>Free users can only use basic commands</code>
<b>~ Note:</b> <code>Disabled commands show ❌ status in menus</code>"""

            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Auth", callback_data="gates_auth"),
                    InlineKeyboardButton("Charge", callback_data="gates_charge")
                ],
                [
                    InlineKeyboardButton("Mass", callback_data="gates_mass"),
                    InlineKeyboardButton("Back", callback_data="home")
                ],
                [
                    InlineKeyboardButton("Close", callback_data="close")
                ]
            ])
            await callback_query.message.edit_text(text, reply_markup=buttons)

# Tool callbacks
@Client.on_callback_query(filters.regex(r"^tool_"))
async def handle_tool_callbacks(client, callback_query):
    data = callback_query.data

    if data == "tool_info":
        info_status = get_command_status("info")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE 〔/info〕</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/info</code>
⟐ <b>Status</b>: <code>{info_status}</code>
⟐ <b>Reply to User</b>: <code>/info (as reply)</code>
⟐ <b>Shows:</b> User ID, Username, Plan, Join Date, Daily Credits, Private Access Status
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Check your or others' account information</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="tools"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "tool_fake":
        fake_status = get_command_status("fake")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE 〔/fake〕</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/fake {country}</code>
⟐ <b>Status</b>: <code>{fake_status}</code>
⟐ <b>Example</b>: <code>/fake us</code>
⟐ <b>Example</b>: <code>/fake united states</code>
⟐ <b>Supported Countries:</b> US, UK, CA, DE, FR, IT, ES, AU, JP, CN, IN, BR, MX
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Generates random address details</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="tools"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "tool_gen":
        gen_status = get_command_status("gen")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE 〔/gen〕</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/gen {BIN} {amount}</code>
⟐ <b>Command</b>: <code>/gen {cc|mm|yy|cvv} {amount}</code>
⟐ <b>Status</b>: <code>{gen_status}</code>
⟐ <b>Example</b>: <code>/gen 411111 10</code>
⟐ <b>Example</b>: <code>/gen 411111|12|2025|123 5</code>
⟐ <b>Max Limit</b>: <code>500 cards</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Generates Luhn-valid cards</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="tools"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "tool_gate":
        gate_status = get_command_status("gate")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE 〔/gate〕</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/gate {website_url}</code>
⟐ <b>Status</b>: <code>{gate_status}</code>
⟐ <b>Example</b>: <code>/gate example.com</code>
⟐ <b>Example</b>: <code>/gate https://shop.example.com</code>
⟐ <b>Features:</b> Payment Gateway Detection, VBV Check, Auth Gate Detection
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Advanced scanning with 20-40 seconds</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="tools"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "tool_bin":
        bin_status = get_command_status("bin")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE 〔/bin〕</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/bin {BIN}</code>
⟐ <b>Status</b>: <code>{bin_status}</code>
⟐ <b>Example</b>: <code>/bin 411111</code>
⟐ <b>Example</b>: <code>/bin 411111|12|2025|123</code>
⟐ <b>Alias</b>: <code>.bin</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Supports BIN or Full CC</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="tools"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "tool_sk":
        sk_status = get_command_status("sk")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE 〔/sk〕</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/sk {stripe_secret_key}</code>
⟐ <b>Status</b>: <code>{sk_status}</code>
⟐ <b>Example</b>: <code>/sk sk_live_1234567890abcdef</code>
⟐ <b>Alias</b>: <code>.sk</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Checks Stripe secret key validity</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="tools"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "tool_redeem":
        redeem_status = get_command_status("redeem")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE 〔/redeem〕</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/redeem {gift_code}</code>
⟐ <b>Status</b>: <code>{redeem_status}</code>
⟐ <b>Example</b>: <code>/redeem WAYNE-DAD-ABCD-1234</code>
⟐ <b>Upgrades To:</b> PLUS Plan
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Redeem gift codes to upgrade your plan</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="tools"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "tool_proxy":
        # Get dynamic status for ALL USER PROXY COMMANDS
        addpx_status = get_command_status("addpx")
        rmvpx_status = get_command_status("rmvpx")
        vpx_status = get_command_status("vpx")

        await callback_query.message.edit_text(
            f"""<pre>#WAYNE 〔Proxy Commands〕</pre>
━━━━━━━━━━━━━
<b>Proxy Management Commands (Available to All Users):</b>

⟐ <b>/addpx</b> - <code>Add a new proxy to the system</code>
⟐ <b>Status:</b> <code>{addpx_status}</code>
⟐ <b>Free Users:</b> <code>Authorized groups only</code>
⟐ <b>Premium Users:</b> <code>Private chat enabled</code>

⟐ <b>/rmvpx</b> - <code>Remove a specific proxy</code>
⟐ <b>Status:</b> <code>{rmvpx_status}</code>
⟐ <b>Free Users:</b> <code>Authorized groups only</code>
⟐ <b>Premium Users:</b> <code>Private chat enabled</code>

⟐ <b>/vpx</b> - <code>View all active proxies</code>
⟐ <b>Status:</b> <code>{vpx_status}</code>
⟐ <b>All Users:</b> <code>Available everywhere</code>

━━━━━━━━━━━━━
<b>Usage Examples:</b>
⟐ <code>/addpx ip:port:user:pass</code>
⟐ <code>/addpx user:pass@ip:port</code>
⟐ <code>/addpx http://user:pass@ip:port</code>
⟐ <code>/rmvpx ip:port</code>
⟐ <code>/vpx</code>

━━━━━━━━━━━━━
<b>~ Note:</b> <code>Free users can use /addpx and /rmvpx in authorized groups only</code>
<b>~ Note:</b> <code>Premium users can use proxy commands in private chat</code>
<b>~ Note:</b> <code>[] shows command status (✅=Active, ❌=Disabled)</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="tools"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

# Admin callbacks
@Client.on_callback_query(filters.regex(r"^admin_"))
async def handle_admin_callbacks(client, callback_query):
    data = callback_query.data

    # Check if user is admin
    users = load_users()
    user_id = str(callback_query.from_user.id)

    if user_id not in users:
        await callback_query.answer("⛔ You need to register first!", show_alert=True)
        return

    user_role = users[user_id].get("role", "Free")

    # Check owner-only commands
    owner_only_commands = ["looser", "gc", "broad", "notused", "off", "on", "add", "rmv", "resett", "pxstats", "rmvall"]
    command_name = data.replace("admin_", "")

    if command_name in owner_only_commands and user_role != "Owner":
        await callback_query.answer("⛔ Owner Only Command!", show_alert=True)
        return

    if data == "admin_plan":
        plus_status = get_command_status("plus")
        pro_status = get_command_status("pro")
        elite_status = get_command_status("elite")
        vip_status = get_command_status("vip")
        ultimate_status = get_command_status("ultimate")

        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[PLAN COMMANDS MENU]─</pre>
━━━━━━━━━━━━━
<b>Available Plan Upgrade Commands:</b>

⟐ <b>/plus</b> - <code>Upgrade user to Plus Plan</code> [{plus_status}]
⟐ <b>/pro</b> - <code>Upgrade user to Pro Plan</code> [{pro_status}]
⟐ <b>/elite</b> - <code>Upgrade user to Elite Plan</code> [{elite_status}]
⟐ <b>/vip</b> - <code>Upgrade user to VIP Plan</code> [{vip_status}]
⟐ <b>/ultimate</b> - <code>Upgrade user to ULTIMATE Plan</code> [{ultimate_status}]

<b>Usage Examples:</b>
<code>/plus @username</code> - Upgrades user to Plus Plan
<code>/pro 123456789</code> - Upgrades user ID to Pro Plan
<code>/elite @username</code> - Upgrades user to Elite Plan

<b>Other Plan Related Commands:</b>
⟐ <b>/redeem &lt;code&gt;</b> - <code>Redeem gift code for Plus plan</code>
⟐ <b>/info</b> - <code>Check your current plan status and credits</code>
⟐ <b>/buy</b> - <code>Buy premium plans</code>
⟐ <b>/plans</b> - <code>Admin: Interactive plan upgrade menu (Owner Only)</code>

━━━━━━━━━━━━━
<b>~ Note:</b> <code>These commands work for admin users only</code>
<b>~ Note:</b> <code>[] shows command status (✅=Active, ❌=Disabled)</code>
<b>~ Note:</b> <code>Regular users can use /redeem for gift codes</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_banbin":
        status = get_command_status("banbin")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[BAN BIN]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/banbin</code> or <code>.banbin</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage 1</b>: <code>/banbin &lt;6-digit BIN&gt;</code>
⟐ <b>Usage 2</b>: <code>/banbin &lt;ccnum|mon|year|cvv&gt;</code>
⟐ <b>Example</b>: <code>/banbin 123456</code>
⟐ <b>Example</b>: <code>/banbin 411111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will ban the BIN from being used.</code>
<b>~ Note:</b> <code>Accessible to: Owner & Admin</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_unbanbin":
        status = get_command_status("unbanbin")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[UNBAN BIN]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/unbanbin</code> or <code>.unbanbin</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage 1</b>: <code>/unbanbin &lt;6-digit BIN&gt;</code>
⟐ <b>Usage 2</b>: <code>/unbanbin &lt;ccnum|mon|year|cvv&gt;</code>
⟐ <b>Example</b>: <code>/unbanbin 123456</code>
⟐ <b>Example</b>: <code>/unbanbin 411111|12|2025|123</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will unban the BIN if it was previously banned.</code>
<b>~ Note:</b> <code>Accessible to: Owner & Admin</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_ban":
        status = get_command_status("ban")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[BAN USER]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/ban</code> or <code>.ban</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: <code>/ban &lt;username or ID&gt;</code>
⟐ <b>Example</b>: <code>/ban @username</code>
⟐ <b>Example</b>: <code>/ban 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will ban the user from using the bot.</code>
<b>~ Note:</b> <code>Accessible to: Owner & Admin</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_unban":
        status = get_command_status("unban")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[UNBAN USER]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/unban</code> or <code>.unban</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: <code>/unban &lt;username or ID&gt;</code>
⟐ <b>Example</b>: <code>/unban @username</code>
⟐ <b>Example</b>: <code>/unban 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will unban the user if they were previously banned.</code>
<b>~ Note:</b> <code>Accessible to: Owner & Admin</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_looser":
        status = get_command_status("looser")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[DOWNGRADE USER]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/looser</code> or <code>.looser</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: <code>/looser &lt;username or ID&gt;</code>
⟐ <b>Example</b>: <code>/looser @username</code>
⟐ <b>Example</b>: <code>/looser 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will downgrade the user to FREE plan.</code>
<b>~ Note:</b> <code>Accessible to: Owner Only</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_add":
        status = get_command_status("add")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[ADD GROUP]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/add</code> or <code>.add</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: <code>/add &lt;chat_id&gt;</code>
⟐ <b>Example</b>: <code>/add -1001234567890</code>
⟐ <b>Example</b>: <code>/add 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Adds group to allowed list (groups.json)</code>
<b>~ Note:</b> <code>Accessible to: Owner Only</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_rmv":
        status = get_command_status("rmv")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[REMOVE GROUP]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/rmv</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: <code>/rmv &lt;chat_id&gt;</code>
⟐ <b>Example</b>: <code>/rmv -1001234567890</code>
⟐ <b>Example</b>: <code>/rmv 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Removes group from allowed list (groups.json)</code>
<b>~ Note:</b> <code>Accessible to: Owner Only</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_gc":
        status = get_command_status("gc")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[GENERATE CODE]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/gc</code> or <code>.gc</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: <code>/gc &lt;days&gt; &lt;num_codes&gt;</code>
⟐ <b>Example</b>: <code>/gc 30 5</code>
⟐ <b>Result</b>: 5 codes valid for 30 days (720 hours)
⟐ <b>Example</b>: <code>/gc 90 1</code>
⟐ <b>Result</b>: 1 code valid for 90 days (2160 hours)
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Maximum 10 codes at once</code>
<b>~ Note:</b> <code>Exact 24-hour periods (not calendar days)</code>
<b>~ Note:</b> <code>Codes can be redeemed with /redeem command</code>
<b>~ Note:</b> <code>Accessible to: Owner Only</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_broad":
        status = get_command_status("broad")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[BROADCAST MESSAGE]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/broad</code> or <code>.broad</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: <code>/broad &lt;your message&gt;</code>
⟐ <b>Example</b>: <code>/broad Hello everyone!</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will broadcast your message to all users.</code>
<b>~ Note:</b> <code>Accessible to: Owner Only</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_notused":
        status = get_command_status("notused")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[CHECK UNUSED CODES]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/notused</code> or <code>.notused</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: Simply use <code>/notused</code>
⟐ <b>Result</b>: Shows all unused and expired gift codes
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Accessible to: Owner Only</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_off":
        status = get_command_status("off")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[DISABLE COMMAND]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/off</code> or <code>.off</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: <code>/off &lt;command&gt;</code>
⟐ <b>Example</b>: <code>/off /sx</code>
⟐ <b>Example</b>: <code>/off .sx</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>The command will be disabled until re-enabled with /on.</code>
<b>~ Note:</b> <code>Accessible to: Owner Only</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_on":
        status = get_command_status("on")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[ENABLE COMMAND]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/on</code> or <code>.on</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: <code>/on &lt;command&gt;</code>
⟐ <b>Example</b>: <code>/on /sx</code>
⟐ <b>Example</b>: <code>/on .sx</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>The command will be re-enabled for all users.</code>
<b>~ Note:</b> <code>Accessible to: Owner Only</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_resett":
        status = get_command_status("resett")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[RESET CREDITS]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/resett</code> or <code>.resett</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: <code>/resett &lt;username or ID&gt;</code>
⟐ <b>Example</b>: <code>/resett @username</code>
⟐ <b>Example</b>: <code>/resett 123456789</code>
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This will reset user's credits to their daily amount immediately</code>
<b>~ Note:</b> <code>Owner/Admin users cannot have their credits reset (they have ∞)</code>
<b>~ Note:</b> <code>Accessible to: Owner Only</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_pxstats":
        status = get_command_status("pxstats")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[PROXY STATISTICS]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/pxstats</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: Simply use <code>/pxstats</code>
⟐ <b>Shows:</b> Proxy count, Active proxies, Last updated, Usage statistics
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Shows detailed proxy statistics and usage</code>
<b>~ Note:</b> <code>Accessible to: Owner & Admin</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    elif data == "admin_rmvall":
        status = get_command_status("rmvall")
        await callback_query.message.edit_text(
            f"""<pre>#WAYNE ─[REMOVE ALL PROXIES]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/rmvall</code>
⟐ <b>Status</b>: <code>{status}</code>
⟐ <b>Usage</b>: Simply use <code>/rmvall</code>
⟐ <b>Warning:</b> This will remove ALL proxies from the system!
━━━━━━━━━━━━━
<b>~ Note:</b> <code>This is a destructive operation - cannot be undone</code>
<b>~ Note:</b> <code>Accessible to: Owner Only</code>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="admins"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
        )

    else:
        await callback_query.answer("Coming Soon!", show_alert=True)

# Add /info command
@Client.on_message(filters.command(["info", ".info"]))
@group_auth_required
async def info_command(client: Client, message: Message):
    """Show user's current info including credits"""
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

    user_id = message.from_user.id

    # Get credits
    credits = get_user_credits(user_id)

    # Load user data for plan info
    users = load_users()
    user_data = users.get(str(user_id), {})

    if not user_data:
        await message.reply("""<pre>❌ User Not Found</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You need to register first with /register
━━━━━━━━━━━━━""")
        return

    user_plan = user_data.get("plan", {}).get("plan", "Free")
    user_role = user_data.get("role", "Free")
    first_name = user_data.get("first_name", "User")
    registered_at = user_data.get("registered_at", "N/A")
    plan_data = user_data.get("plan", {})
    badge = plan_data.get("badge", "🧿")
    private_status = plan_data.get("private", "off")
    antispam = plan_data.get("antispam", "15")
    mlimit = plan_data.get("mlimit", "5")

    response = f"""<pre>#WAYNE ─[USER INFORMATION]─</pre>
━━━━━━━━━━━━━
⟐ <b>Name</b>: <code>{first_name} [{badge}]</code>
⟐ <b>User ID</b>: <code>{user_id}</code>
⟐ <b>Username</b>: <code>@{message.from_user.username if message.from_user.username else 'N/A'}</code>
⟐ <b>Plan</b>: <code>{user_plan}</code>
⟐ <b>Role</b>: <code>{user_role}</code>
⟐ <b>Registered At</b>: <code>{registered_at}</code>
⟐ <b>Current Credits</b>: <code>{credits}</code>
⟐ <b>Private Access</b>: <code>{'✅ ON' if private_status == 'on' else '❌ OFF'}</code>
⟐ <b>Anti-Spam Delay</b>: <code>{antispam} seconds</code>
⟐ <b>Mass Limit</b>: <code>{mlimit} cards</code>
━━━━━━━━━━━━━
"""

    if user_plan == "Free" and user_role == "Free":
        response += """<b>Free User Details:</b>
⟐ <b>Daily Credits</b>: <code>100 credits (resets every 24h)</code>
⟐ <b>Auth Commands</b>: <code>FREE in authorized groups</code>
⟐ <b>Charge Commands</b>: <code>2 credits each in authorized groups</code>
⟐ <b>Private Chat</b>: <code>Limited access (auth commands only)</code>
"""
    else:
        # Get daily credits for premium users
        daily_credits = {
            "Plus": "200",
            "Pro": "500", 
            "Elite": "1000",
            "VIP": "2000",
            "ULTIMATE": "2500",
            "Owner": "∞",
            "Admin": "∞",
            "Redeem Code": "200"
        }.get(user_plan, "100")

        response += f"""<b>Premium User Details:</b>
⟐ <b>Daily Credits</b>: <code>{daily_credits} credits (resets every 24h)</code>
⟐ <b>Auth Commands</b>: <code>FREE everywhere</code>
⟐ <b>Charge Commands</b>: <code>2 credits each</code>
⟐ <b>Private Chat</b>: <code>Full access enabled</code>
"""

    response += """━━━━━━━━━━━━━
<b>Free Commands (No Credits):</b>
⟐ <code>$au, $chk, $bu, $ad</code>

<b>Charge Commands (2 Credits Each):</b>
⟐ <code>$xx, $xo, $xs, $xc, $xp, $bt, $sh, $slf</code>
⟐ <code>$mau, $mchk, $mxc, $mxp, $mxx</code>

━━━━━━━━━━━━━
<b>~ Note:</b> <code>Check your credits before using charge commands</code>
<b>~ Note:</b> <code>All users get daily credit resets based on their plan</code>
<b>~ Note:</b> <code>Use /buy to upgrade for more daily credits and features</code>"""

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Buy Premium", callback_data="buy"),
            InlineKeyboardButton("Home", callback_data="home")
        ],
        [
            InlineKeyboardButton("Close", callback_data="close")
        ]
    ])

    await message.reply(response, reply_markup=buttons)
