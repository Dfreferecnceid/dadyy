import json
from datetime import datetime
from BOT.helper.start import USERS_FILE, load_users, save_users

PLAN_NAME = "Elite"
PLAN_PRICE = "$6"
PLAN_BADGE = "📧"
DEFAULT_BADGE = "🧿"
DEFAULT_ANTISPAM = 15
DEFAULT_MLIMIT = 5
ELITE_ANTISPAM = 3
ELITE_MLIMIT = 10
ELITE_CREDIT_BONUS = 1000

def activate_elite_plan(user_id: str) -> bool:
    users = load_users()
    user = users.get(user_id)
    if not user:
        return False

    # Check if user already has Elite plan
    plan = user.get("plan", {})
    if plan.get("plan") == PLAN_NAME:
        return "already_active"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Add credits
    current_credits = user["plan"]["credits"]
    if current_credits != "∞":
        try:
            current_credits = int(current_credits)
            new_credits = current_credits + ELITE_CREDIT_BONUS
        except:
            new_credits = ELITE_CREDIT_BONUS
    else:
        new_credits = "∞"

    user["plan"].update({
        "plan": PLAN_NAME,
        "activated_at": now,
        "expires_at": None,  # No expiry
        "antispam": ELITE_ANTISPAM,
        "mlimit": ELITE_MLIMIT,
        "badge": PLAN_BADGE,
        "credits": new_credits,
        "private": "on"
    })
    user["role"] = PLAN_NAME
    save_users(users)
    return True