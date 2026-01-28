from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import PeerIdInvalid
from BOT.plans.plan1 import activate_plus_plan
from BOT.plans.plan2 import activate_pro_plan
from BOT.plans.plan3 import activate_elite_plan
from BOT.plans.plan4 import activate_vip_plan
from BOT.plans.plan5 import activate_ult_plan
from BOT.helper.permissions import owner_required, is_user_registered
from BOT.helper.start import load_users
from datetime import datetime

async def extract_target_user(client: Client, message: Message):
    """Extract target user from command with proper Telegram API resolution"""
    args = message.text.split()

    # Check if replying to a message
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user

    if len(args) < 2:
        return None

    target = args[1].strip()

    try:
        if target.startswith('@'):
            # Username with @
            user = await client.get_users(target)
        else:
            # Try as user ID
            try:
                user_id = int(target)
                user = await client.get_users(user_id)
            except ValueError:
                # Try as username without @
                user = await client.get_users(target)
        return user
    except (PeerIdInvalid, ValueError, Exception) as e:
        print(f"Error extracting user: {e}")
        return None

async def notify_user_plan_activated(app: Client, user_id: str, plan_name: str):
    """Send notification to user about plan activation"""
    users = load_users()
    user = users.get(str(user_id))
    if not user:
        return

    plan = user.get("plan", {})
    activated_at = plan.get("activated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    expires_at = plan.get("expires_at", "Never")
    antispam = plan.get("antispam", "N/A")
    mlimit = plan.get("mlimit", "N/A")
    badge = plan.get("badge", "❓")

    # Plan prices
    plan_prices = {
        "Plus": "$1",
        "Pro": "$3",
        "Elite": "$6",
        "VIP": "$15",
        "ULTIMATE": "$25"
    }

    try:
        await app.send_message(
            int(user_id),
            f"""<pre>✅ Plan Activated Successfully</pre>
━━━━━━━━━━━━━
⟐ <b>Plan:</b> <code>{plan_name}</code>
⟐ <b>Price:</b> <code>{plan_prices.get(plan_name, 'N/A')}</code>
⟐ <b>Activated At:</b> <code>{activated_at}</code>
⟐ <b>Expires At:</b> <code>{expires_at if expires_at else 'Never'}</code>
⟐ <b>Anti-Spam:</b> <code>{antispam}s</code>
⟐ <b>Mass Limit:</b> <code>{mlimit}</code>
⟐ <b>Badge:</b> {badge}
━━━━━━━━━━━━━
🎉 Thank you for choosing our premium service.
Use <code>/info</code> anytime to check your current status.
"""
        )
    except Exception as e:
        print(f"Error sending notification: {e}")

@Client.on_message(filters.command(["plus", ".plus"]))
@owner_required
async def handle_plus(client: Client, message: Message):
    """Activate Plus plan for user - OWNER ONLY"""
    target_user = await extract_target_user(client, message)
    if not target_user:
        await message.reply("""<pre>#WAYNE ─[PLUS PLAN]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/plus</code> or <code>.plus</code>
⟐ <b>Usage</b>: <code>/plus @username</code>
⟐ <b>Usage</b>: <code>/plus 123456789</code>
⟐ <b>Usage</b>: <code>/plus</code> (reply to user's message)
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Upgrades user to Plus Plan ($1)</code>""")
        return

    if not is_user_registered(target_user.id):
        await message.reply(f"""<pre>❌ User Not Registered</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User <code>@{target_user.username if target_user.username else target_user.id}</code> is not registered.
⟐ <b>Solution</b>: User must register first with <code>/register</code>
━━━━━━━━━━━━━""")
        return

    result = activate_plus_plan(str(target_user.id))
    if result == "already_active":
        await message.reply(f"""<pre>ℹ️ Already Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User <code>@{target_user.username if target_user.username else target_user.id}</code> already has an active Plus plan.
━━━━━━━━━━━━━""")
    elif result:
        await message.reply(f"""<pre>✅ Upgrade Successful</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Successfully upgraded user to <b>Plus Plan</b>!
⟐ <b>User</b>: <code>@{target_user.username if target_user.username else target_user.id}</code>
⟐ <b>User ID</b>: <code>{target_user.id}</code>
━━━━━━━━━━━━━""")
        await notify_user_plan_activated(client, str(target_user.id), "Plus")
    else:
        await message.reply("""<pre>❌ Upgrade Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to upgrade user.
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["pro", ".pro"]))
@owner_required
async def handle_pro(client: Client, message: Message):
    """Activate Pro plan for user - OWNER ONLY"""
    target_user = await extract_target_user(client, message)
    if not target_user:
        await message.reply("""<pre>#WAYNE ─[PRO PLAN]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/pro</code> or <code>.pro</code>
⟐ <b>Usage</b>: <code>/pro @username</code>
⟐ <b>Usage</b>: <code>/pro 123456789</code>
⟐ <b>Usage</b>: <code>/pro</code> (reply to user's message)
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Upgrades user to Pro Plan ($3)</code>""")
        return

    if not is_user_registered(target_user.id):
        await message.reply(f"""<pre>❌ User Not Registered</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User <code>@{target_user.username if target_user.username else target_user.id}</code> is not registered.
⟐ <b>Solution</b>: User must register first with <code>/register</code>
━━━━━━━━━━━━━""")
        return

    result = activate_pro_plan(str(target_user.id))
    if result == "already_active":
        await message.reply(f"""<pre>ℹ️ Already Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User <code>@{target_user.username if target_user.username else target_user.id}</code> already has an active Pro plan.
━━━━━━━━━━━━━""")
    elif result:
        await message.reply(f"""<pre>✅ Upgrade Successful</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Successfully upgraded user to <b>Pro Plan</b>!
⟐ <b>User</b>: <code>@{target_user.username if target_user.username else target_user.id}</code>
⟐ <b>User ID</b>: <code>{target_user.id}</code>
━━━━━━━━━━━━━""")
        await notify_user_plan_activated(client, str(target_user.id), "Pro")
    else:
        await message.reply("""<pre>❌ Upgrade Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to upgrade user.
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["elite", ".elite"]))
@owner_required
async def handle_elite(client: Client, message: Message):
    """Activate Elite plan for user - OWNER ONLY"""
    target_user = await extract_target_user(client, message)
    if not target_user:
        await message.reply("""<pre>#WAYNE ─[ELITE PLAN]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/elite</code> or <code>.elite</code>
⟐ <b>Usage</b>: <code>/elite @username</code>
⟐ <b>Usage</b>: <code>/elite 123456789</code>
⟐ <b>Usage</b>: <code>/elite</code> (reply to user's message)
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Upgrades user to Elite Plan ($6)</code>""")
        return

    if not is_user_registered(target_user.id):
        await message.reply(f"""<pre>❌ User Not Registered</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User <code>@{target_user.username if target_user.username else target_user.id}</code> is not registered.
⟐ <b>Solution</b>: User must register first with <code>/register</code>
━━━━━━━━━━━━━""")
        return

    result = activate_elite_plan(str(target_user.id))
    if result == "already_active":
        await message.reply(f"""<pre>ℹ️ Already Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User <code>@{target_user.username if target_user.username else target_user.id}</code> already has an active Elite plan.
━━━━━━━━━━━━━""")
    elif result:
        await message.reply(f"""<pre>✅ Upgrade Successful</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Successfully upgraded user to <b>Elite Plan</b>!
⟐ <b>User</b>: <code>@{target_user.username if target_user.username else target_user.id}</code>
⟐ <b>User ID</b>: <code>{target_user.id}</code>
━━━━━━━━━━━━━""")
        await notify_user_plan_activated(client, str(target_user.id), "Elite")
    else:
        await message.reply("""<pre>❌ Upgrade Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to upgrade user.
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["vip", ".vip"]))
@owner_required
async def handle_vip(client: Client, message: Message):
    """Activate VIP plan for user - OWNER ONLY"""
    target_user = await extract_target_user(client, message)
    if not target_user:
        await message.reply("""<pre>#WAYNE ─[VIP PLAN]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/vip</code> or <code>.vip</code>
⟐ <b>Usage</b>: <code>/vip @username</code>
⟐ <b>Usage</b>: <code>/vip 123456789</code>
⟐ <b>Usage</b>: <code>/vip</code> (reply to user's message)
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Upgrades user to VIP Plan ($15)</code>""")
        return

    if not is_user_registered(target_user.id):
        await message.reply(f"""<pre>❌ User Not Registered</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User <code>@{target_user.username if target_user.username else target_user.id}</code> is not registered.
⟐ <b>Solution</b>: User must register first with <code>/register</code>
━━━━━━━━━━━━━""")
        return

    result = activate_vip_plan(str(target_user.id))
    if result == "already_active":
        await message.reply(f"""<pre>ℹ️ Already Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User <code>@{target_user.username if target_user.username else target_user.id}</code> already has an active VIP plan.
━━━━━━━━━━━━━""")
    elif result:
        await message.reply(f"""<pre>✅ Upgrade Successful</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Successfully upgraded user to <b>VIP Plan</b>!
⟐ <b>User</b>: <code>@{target_user.username if target_user.username else target_user.id}</code>
⟐ <b>User ID</b>: <code>{target_user.id}</code>
━━━━━━━━━━━━━""")
        await notify_user_plan_activated(client, str(target_user.id), "VIP")
    else:
        await message.reply("""<pre>❌ Upgrade Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to upgrade user.
━━━━━━━━━━━━━""")

@Client.on_message(filters.command(["ultimate", ".ultimate", "ult", ".ult"]))
@owner_required
async def handle_ultimate(client: Client, message: Message):
    """Activate ULTIMATE plan for user - OWNER ONLY"""
    target_user = await extract_target_user(client, message)
    if not target_user:
        await message.reply("""<pre>#WAYNE ─[ULTIMATE PLAN]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/ultimate</code> or <code>/ult</code>
⟐ <b>Usage</b>: <code>/ultimate @username</code>
⟐ <b>Usage</b>: <code>/ultimate 123456789</code>
⟐ <b>Usage</b>: <code>/ultimate</code> (reply to user's message)
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Upgrades user to ULTIMATE Plan ($25)</code>""")
        return

    if not is_user_registered(target_user.id):
        await message.reply(f"""<pre>❌ User Not Registered</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User <code>@{target_user.username if target_user.username else target_user.id}</code> is not registered.
⟐ <b>Solution</b>: User must register first with <code>/register</code>
━━━━━━━━━━━━━""")
        return

    result = activate_ult_plan(str(target_user.id))
    if result == "already_active":
        await message.reply(f"""<pre>ℹ️ Already Active</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: User <code>@{target_user.username if target_user.username else target_user.id}</code> already has an active ULTIMATE plan.
━━━━━━━━━━━━━""")
    elif result:
        await message.reply(f"""<pre>✅ Upgrade Successful</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Successfully upgraded user to <b>ULTIMATE Plan</b>!
⟐ <b>User</b>: <code>@{target_user.username if target_user.username else target_user.id}</code>
⟐ <b>User ID</b>: <code>{target_user.id}</code>
━━━━━━━━━━━━━""")
        await notify_user_plan_activated(client, str(target_user.id), "ULTIMATE")
    else:
        await message.reply("""<pre>❌ Upgrade Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: Failed to upgrade user.
━━━━━━━━━━━━━""")