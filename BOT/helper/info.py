from pyrogram import Client, filters
from pyrogram.types import Message
from BOT.helper.start import load_users
from datetime import datetime
from pyrogram.enums import ChatMemberStatus

def calculate_expiry(expiry_time):
    if not expiry_time:
        return "∞"
    try:
        now = datetime.now()
        expiry_dt = datetime.strptime(expiry_time, "%Y-%m-%d %H:%M:%S")
        diff = expiry_dt - now
        days = diff.days
        hours = diff.seconds // 3600
        if diff.total_seconds() <= 0:
            return "Expired"
        return f"{days}d, {hours}h left"
    except:
        return "Invalid Date"

def get_plan_display(plan_data):
    """Get the actual plan name and status for display"""
    plan = plan_data.get("plan", "Free")
    expires_at = plan_data.get("expires_at")
    
    if plan == "Free":
        return "Free", "🧿"
    elif expires_at:
        try:
            now = datetime.now()
            expiry_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
            if now > expiry_dt:
                return f"{plan} (Expired)", "❌"
            else:
                # Plan is active - show actual plan name
                return f"{plan}", "✅"
        except:
            return f"{plan}", "✅"
    else:
        # Permanent plan
        return f"{plan} (Permanent)", "💎"

@Client.on_message(filters.command(["info", ".info", "$info"]))
async def info_command(client, message: Message):
    db = load_users()

    # 1. Check for reply
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user

    # 2. Check for command argument
    elif len(message.command) > 1:
        arg = message.command[1]

        # Mentioned username
        if arg.startswith("@"):
            try:
                target_user = await client.get_users(arg)
            except Exception as e:
                return await message.reply(f"❌ Unable to find user `{arg}`.")
        # Numeric user ID
        elif arg.isdigit():
            try:
                target_user = await client.get_users(int(arg))
            except Exception as e:
                return await message.reply(f"❌ Unable to find user `{arg}`.")
        else:
            return await message.reply("<b>❌ Invalid input.</b>\n Use /info @username or user_id or reply to a user.")
    else:
        # 3. Fallback to self
        target_user = message.from_user

    uid = str(target_user.id)
    user_data = db.get(uid)

    if not user_data:
        return await message.reply("<pre>User not found in database ❌</pre>.")

    fname = user_data.get("first_name", "N/A")
    username = f"@{user_data['username']}" if user_data.get("username") else "N/A"
    profile = f'<a href="tg://user?id={uid}">Profile</a>'

    plan_data = user_data.get("plan", {})
    plan_name = plan_data.get("plan", "Free")
    credits = plan_data.get("credits", "0")
    registered_at = user_data.get("registered_at", "N/A")
    expiry = calculate_expiry(plan_data.get("expires_at"))
    mlimit = plan_data.get("mlimit", "N/A")
    keyredeemed = plan_data.get("keyredeem", 0)
    
    # Get the actual plan display with emoji
    plan_display, plan_emoji = get_plan_display(plan_data)
    
    # Get badge based on plan
    badge = plan_data.get("badge", "🧿")
    
    # Determine if plan is active
    expires_at = plan_data.get("expires_at")
    is_active = True
    if expires_at:
        try:
            now = datetime.now()
            expiry_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
            if now > expiry_dt:
                is_active = False
        except:
            pass

    msg = f"""
<pre>[{uid}] ~ WAYNE</pre>
━━━━━━━━━━━━━━
• <b>Firstname :</b> <code>{fname}</code>
• <b>UserID :</b> <code>{uid}</code>
• <b>Username :</b> <code>{username}</code>
• <b>Profile :</b> {profile}
━ ━ ━ ━ ━ ━━━ ━ ━ ━ ━ ━
[ﾒ] <b>Status :</b> <code>{plan_display}</code> {badge}
⚬ <b>Credits :</b> <code>{credits}</code>
⚬ <b>Plan :</b> <code>{plan_name}</code>
⚬ <b>Plan Expiry :</b> <code>{expiry}</code>
⚬ <b>Mass Limit :</b> <code>{mlimit}</code>
⚬ <b>Key Redeemed :</b> <code>{keyredeemed}</code>
[ﾒ] <b>Registered At :</b> <code>{registered_at}</code>
"""
    await message.reply(msg, quote=True)
