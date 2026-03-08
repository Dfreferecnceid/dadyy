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

def activate_plus_plan(user_id: str, expires_at: str = None):
    """Activate Plus plan with optional expiry date
    - If expires_at is None: Permanent plan (direct upgrade)
    - If expires_at is provided: Temporary plan (gift code)"""
    
    try:
        users = load_users()
        user = users.get(user_id)
        if not user:
            return False

        # Check current plan
        plan = user.get("plan", {})
        current_plan = plan.get("plan", "Free")
        current_expiry = plan.get("expires_at")
        current_role = user.get("role", "Free")
        
        # DEBUG PRINT
        print(f"[DEBUG] Activating Plus for user {user_id}")
        print(f"[DEBUG] Current plan: {current_plan}, Role: {current_role}, Expiry: {current_expiry}")
        print(f"[DEBUG] New expiry: {expires_at}")
        
        # Check if user already has an ACTIVE plan (not Free)
        if current_plan != "Free" or current_role != "Free":
            # User has some plan
            
            if expires_at is not None:
                # This is a gift code redemption attempt
                if current_expiry is None:
                    # User has permanent plan - cannot redeem
                    print(f"[DEBUG] User has permanent plan - cannot redeem")
                    return "already_premium_permanent"
                else:
                    # User has temporary plan - check if it's active
                    try:
                        now = datetime.now()
                        expiry_time = datetime.strptime(current_expiry, "%Y-%m-%d %H:%M:%S")
                        
                        if now <= expiry_time:
                            # Plan is still active - cannot redeem
                            print(f"[DEBUG] User has active temporary plan - cannot redeem")
                            return "already_active"
                        else:
                            # Plan has expired - allow redemption
                            print(f"[DEBUG] User's plan expired - allowing redemption")
                            # Continue with activation
                            pass
                    except Exception as e:
                        print(f"[DEBUG] Error checking expiry: {e}")
                        # If expiry date is invalid, treat as expired and allow redemption
                        pass
        
        # If we get here, user can be upgraded
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Add credits
        current_credits = user.get("plan", {}).get("credits", "0")
        if current_credits != "∞":
            try:
                current_credits = int(current_credits)
                new_credits = current_credits + PLUS_CREDIT_BONUS
            except:
                new_credits = PLUS_CREDIT_BONUS
        else:
            new_credits = "∞"

        # Update user data
        user["plan"].update({
            "plan": PLAN_NAME,
            "activated_at": now,
            "expires_at": expires_at,  # Could be None (permanent) or date (temporary)
            "antispam": PLUS_ANTISPAM,
            "badge": PLAN_BADGE,
            "credits": str(new_credits),
            "private": "on",
            "mlimit": 10  # Plus plan gets 10 mass limit
        })
        user["role"] = PLAN_NAME
        
        # Increment keyredeem count
        if "keyredeem" not in user["plan"]:
            user["plan"]["keyredeem"] = 0
        user["plan"]["keyredeem"] = user["plan"]["keyredeem"] + 1
        
        # Save users
        save_users(users)
        
        print(f"[DEBUG] Plus plan activated successfully for user {user_id}")
        print(f"[DEBUG] New plan: {user['plan']['plan']}, Expiry: {user['plan']['expires_at']}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] in activate_plus_plan: {e}")
        return False

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
        try:
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
                                    "activated_at": user.get("registered_at", plan.get("activated_at", now.strftime("%Y-%m-%d %H:%M:%S"))),
                                    "expires_at": None,
                                    "antispam": DEFAULT_ANTISPAM,
                                    "mlimit": DEFAULT_MLIMIT,
                                    "badge": DEFAULT_BADGE,
                                    "credits": "100",  # Reset to free credits
                                    "private": "off"
                                })
                                user["role"] = "Free"
                                user["last_credit_reset"] = now.strftime("%Y-%m-%d %H:%M:%S")
                                changed = True

                                # Notify the user that the plan expired
                                try:
                                    await app.send_message(
                                        int(user_id),
                                        """<pre>Notification ❗️</pre>
━━━━━━━━━━━━━━
<b>~ Your Gift Code Plan Has Expired</b>
<b>~ You are now back to Free plan</b>
<b>~ You can now redeem another gift code</b>
<b>~ Contact Owner for new codes</b>
━━━━━━━━━━━━━━"""
                                    )
                                except Exception as e:
                                    print(f"Error sending expiration message: {e}")

                        except Exception as e:
                            print(f"Error checking expiry for user {user_id}: {e}")

            if changed:
                save_users(users)

        except Exception as e:
            print(f"[ERROR] in check_and_expire_plans: {e}")
            
        await asyncio.sleep(5)  # Check every 5 seconds
