import json
import asyncio
import os
from datetime import datetime, timedelta
from pyrogram import Client, filters
from BOT.helper.start import USERS_FILE, load_users, save_users, load_owner_id

PLAN_NAME = "Plus"
PLAN_PRICE = "$1"
PLAN_BADGE = "💠"
DEFAULT_BADGE = "🧿"
DEFAULT_ANTISPAM = 15
DEFAULT_MLIMIT = 5
PLUS_ANTISPAM = 13
PLUS_CREDIT_BONUS = 200

OWNER_ID = load_owner_id()

def activate_plus_plan(user_id: str, expires_at: str = None) -> bool:
    """Activate Plus plan with optional expiry date
    - If expires_at is None: Permanent plan (direct upgrade)
    - If expires_at is provided: Temporary plan (gift code)"""

    users = load_users()
    user = users.get(user_id)
    if not user:
        return False

    # NEW: Check if user already has redeemed any gift code
    # Load gift codes data to check if user has redeemed any code
    gift_codes = load_gift_codes()
    user_has_redeemed = False

    for code_data in gift_codes.values():
        if code_data.get("used_by") == user_id:
            user_has_redeemed = True
            break

    # NEW: Check if user is already premium (not Free)
    user_plan = user.get("plan", {}).get("plan", "Free")
    is_premium = user_plan != "Free"

    # If user already has redeemed a gift code, return special code
    if user_has_redeemed and expires_at is not None:
        return "already_redeemed"

    # If user is already premium and trying to redeem gift code, return special code
    if is_premium and expires_at is not None:
        return "already_premium"

    # Check if user already has Plus plan
    plan = user.get("plan", {})
    if plan.get("plan") == PLAN_NAME:
        # Check if this is extending an existing plan
        current_expiry = plan.get("expires_at")

        # If user has permanent plan (expires_at = None) and trying to add gift code
        if current_expiry is None and expires_at is not None:
            # NEW: User with permanent Plus plan cannot redeem gift codes
            return "already_premium_permanent"
        elif current_expiry is not None and expires_at is not None:
            # User has temporary plan, extending with new expiry
            # Use the later expiry date
            try:
                current_expiry_date = datetime.strptime(current_expiry, "%Y-%m-%d %H:%M:%S")
                new_expiry_date = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                if new_expiry_date > current_expiry_date:
                    expires_at = new_expiry_date.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    expires_at = current_expiry  # Keep existing later expiry
            except:
                pass

        return "already_active"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Add credits
    current_credits = user["plan"]["credits"]
    if current_credits != "∞":
        try:
            current_credits = int(current_credits)
            new_credits = current_credits + PLUS_CREDIT_BONUS
        except:
            new_credits = PLUS_CREDIT_BONUS
    else:
        new_credits = "∞"

    user["plan"].update({
        "plan": PLAN_NAME,
        "activated_at": now,
        "expires_at": expires_at,  # Could be None (permanent) or date (temporary)
        "antispam": PLUS_ANTISPAM,
        "badge": PLAN_BADGE,
        "credits": new_credits,
        "private": "on"
    })
    user["role"] = PLAN_NAME
    save_users(users)
    return True

def load_gift_codes():
    """Load gift codes from GC_FILE - supports both txt and json formats"""
    GC_FILE_TXT = "DATA/gift_codes.txt"
    GC_FILE_JSON = "DATA/gift_codes.json"

    gift_codes = {}

    # First try to load from JSON file
    if os.path.exists(GC_FILE_JSON):
        try:
            with open(GC_FILE_JSON, 'r') as f:
                gift_codes = json.load(f)
            return gift_codes
        except:
            pass

    # If JSON doesn't exist, try to load from txt and convert
    if os.path.exists(GC_FILE_TXT):
        try:
            with open(GC_FILE_TXT, 'r') as f:
                for line in f.read().splitlines():
                    if '|' in line:
                        code, expiration_date_str = line.split('|')
                        gift_codes[code] = {
                            "expires_at": expiration_date_str,
                            "used": False,
                            "used_by": None,
                            "used_at": None,
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "days_valid": 0  # Will be calculated
                        }

            # Save as JSON for future use
            save_gift_codes(gift_codes)
            return gift_codes
        except:
            pass

    return gift_codes

def save_gift_codes(gift_codes):
    """Save gift codes to JSON file"""
    GC_FILE_JSON = "DATA/gift_codes.json"

    # Ensure DATA directory exists
    os.makedirs("DATA", exist_ok=True)

    with open(GC_FILE_JSON, 'w') as f:
        json.dump(gift_codes, f, indent=4)

async def check_and_expire_plans(app: Client):
    """Check and expire Plus plans (only for gift code ones with expiry)"""
    while True:
        users = load_users()
        now = datetime.now()
        changed = False

        for user_id, user in users.items():
            plan = user.get("plan", {})

            # Check if the plan is Plus and has an expiry time
            # Only expire if expires_at is not None (temporary plans)
            if plan.get("plan") == PLAN_NAME and plan.get("expires_at"):
                expires_at = plan.get("expires_at")

                # Process the expiration
                if expires_at:
                    try:
                        expiry_time = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                        if now >= expiry_time:
                            # Revert to Free plan
                            user["plan"].update({
                                "plan": "Free",
                                "activated_at": user.get("registered_at", plan["activated_at"]),
                                "expires_at": None,
                                "antispam": DEFAULT_ANTISPAM,
                                "mlimit": DEFAULT_MLIMIT,
                                "badge": DEFAULT_BADGE,
                                "private": "off"
                            })
                            user["role"] = "Free"
                            changed = True

                            # Notify the user that the plan expired
                            try:
                                await app.send_message(
                                    int(user_id),
                                    """<pre>Notification ❗️</pre>
<b>~ Your Gift Code Plan Is Expired</b>
<b>~ Renew your plan</b> (<code>/buy</code>)
<b>~ Contact to Owner at @SyncBlastBot</b>
                               """)
                            except Exception as e:
                                print(f"Error sending expiration message: {e}")

                    except Exception as e:
                        print(f"Error checking expiry for user {user_id}: {e}")

        if changed:
            save_users(users)

        await asyncio.sleep(5)  # Check every 5 seconds
