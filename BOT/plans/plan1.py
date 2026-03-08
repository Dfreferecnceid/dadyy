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
PLUS_MLIMIT = 10

OWNER_ID = load_owner_id()

def activate_plus_plan(user_id: str, expires_at: str = None):
    """Activate Plus plan with optional expiry date
    - If expires_at is None: Permanent plan (direct upgrade)
    - If expires_at is provided: Temporary plan (gift code)"""
    
    try:
        # Load users
        users = load_users()
        user_id_str = str(user_id)
        
        if user_id_str not in users:
            print(f"[ERROR] User {user_id_str} not found in database")
            return False

        user = users[user_id_str]
        
        # Get current plan info
        current_plan = user.get("plan", {}).get("plan", "Free")
        current_expiry = user.get("plan", {}).get("expires_at")
        current_role = user.get("role", "Free")
        
        print(f"[DEBUG] Activating Plus for user {user_id_str}")
        print(f"[DEBUG] Current plan: {current_plan}, Role: {current_role}, Expiry: {current_expiry}")
        print(f"[DEBUG] New expiry: {expires_at}")
        
        # CRITICAL CHECK: If user already has an ACTIVE plan
        if current_plan != "Free" or current_role != "Free":
            
            # If this is a gift code redemption (expires_at is provided)
            if expires_at is not None:
                
                # Check if user has permanent plan (no expiry)
                if current_expiry is None:
                    print(f"[DEBUG] User has permanent plan - cannot redeem")
                    return "already_premium_permanent"
                
                # Check if user has active temporary plan
                if current_expiry:
                    try:
                        now = datetime.now()
                        expiry_time = datetime.strptime(current_expiry, "%Y-%m-%d %H:%M:%S")
                        
                        if now < expiry_time:
                            # Plan is still active
                            print(f"[DEBUG] User has active temporary plan until {current_expiry}")
                            return "already_active"
                        else:
                            # Plan has expired - allow redemption
                            print(f"[DEBUG] User's plan expired on {current_expiry}, allowing redemption")
                            # Continue with activation
                            pass
                    except Exception as e:
                        print(f"[DEBUG] Error checking expiry: {e}")
                        # If expiry date is invalid, treat as expired and allow redemption
                        pass
        
        # If we get here, user can be upgraded
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get current credits
        current_credits = user.get("plan", {}).get("credits", "0")
        if current_credits != "∞":
            try:
                current_credits = int(current_credits)
                new_credits = current_credits + PLUS_CREDIT_BONUS
            except:
                new_credits = PLUS_CREDIT_BONUS
        else:
            new_credits = "∞"

        # CRITICAL: Create a completely new plan dictionary to avoid reference issues
        new_plan = {
            "plan": PLAN_NAME,
            "activated_at": now,
            "expires_at": expires_at,
            "antispam": PLUS_ANTISPAM,
            "badge": PLAN_BADGE,
            "credits": str(new_credits),
            "private": "on",
            "mlimit": PLUS_MLIMIT
        }
        
        # Copy existing keyredeem if it exists
        if "keyredeem" in user.get("plan", {}):
            new_plan["keyredeem"] = user["plan"]["keyredeem"] + 1
        else:
            new_plan["keyredeem"] = 1
            
        # Copy other existing plan data if needed
        if "mlimit" in user.get("plan", {}):
            pass  # Already set above
        
        # Replace the entire plan dictionary
        user["plan"] = new_plan
        
        # Update role
        user["role"] = PLAN_NAME
        
        # CRITICAL: Save users immediately
        save_users(users)
        print(f"[DEBUG] Users saved to {USERS_FILE}")
        
        # CRITICAL: Verify the save worked by reloading
        verification = load_users()
        if user_id_str in verification:
            saved_plan = verification[user_id_str].get("plan", {}).get("plan", "Unknown")
            saved_expiry = verification[user_id_str].get("plan", {}).get("expires_at")
            saved_role = verification[user_id_str].get("role", "Unknown")
            saved_credits = verification[user_id_str].get("plan", {}).get("credits", "Unknown")
            saved_keyredeem = verification[user_id_str].get("plan", {}).get("keyredeem", "Unknown")
            
            print(f"[DEBUG] VERIFICATION AFTER SAVE:")
            print(f"[DEBUG]   - Plan: {saved_plan}")
            print(f"[DEBUG]   - Expiry: {saved_expiry}")
            print(f"[DEBUG]   - Role: {saved_role}")
            print(f"[DEBUG]   - Credits: {saved_credits}")
            print(f"[DEBUG]   - Key Redeemed: {saved_keyredeem}")
            
            if saved_plan == PLAN_NAME:
                print(f"[DEBUG] ✓ Plan saved successfully!")
                return True
            else:
                print(f"[DEBUG] ✗ Plan save FAILED! Expected {PLAN_NAME}, got {saved_plan}")
                return False
        else:
            print(f"[DEBUG] ✗ User {user_id_str} not found in verification!")
            return False
        
    except Exception as e:
        print(f"[ERROR] in activate_plus_plan: {e}")
        import traceback
        traceback.print_exc()
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
                            "days_valid": 0
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
                if plan.get("plan") == PLAN_NAME and plan.get("expires_at"):
                    expires_at = plan.get("expires_at")

                    if expires_at:
                        try:
                            expiry_time = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                            if now >= expiry_time:
                                print(f"[DEBUG] Expiring plan for user {user_id}")
                                # Create new Free plan dictionary
                                new_plan = {
                                    "plan": "Free",
                                    "activated_at": user.get("registered_at", plan.get("activated_at", now.strftime("%Y-%m-%d %H:%M:%S"))),
                                    "expires_at": None,
                                    "antispam": DEFAULT_ANTISPAM,
                                    "mlimit": DEFAULT_MLIMIT,
                                    "badge": DEFAULT_BADGE,
                                    "credits": "100",
                                    "private": "off"
                                }
                                
                                # Copy keyredeem if it exists
                                if "keyredeem" in plan:
                                    new_plan["keyredeem"] = plan["keyredeem"]
                                
                                user["plan"] = new_plan
                                user["role"] = "Free"
                                user["last_credit_reset"] = now.strftime("%Y-%m-%d %H:%M:%S")
                                changed = True

                                # Notify the user
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
                                except:
                                    pass

                        except Exception as e:
                            print(f"Error checking expiry for user {user_id}: {e}")

            if changed:
                save_users(users)
                print(f"[DEBUG] Expired plans saved to {USERS_FILE}")

        except Exception as e:
            print(f"[ERROR] in check_and_expire_plans: {e}")
            
        await asyncio.sleep(5)
