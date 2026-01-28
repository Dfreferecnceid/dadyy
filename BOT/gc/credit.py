# BOT/gc/credit.py - COMPLETE CORRECTED VERSION

import json
import os
from datetime import datetime, timedelta
import pytz
import asyncio
from typing import Callable, Tuple, Any, Dict
import traceback

# ==================== CORE CREDIT FUNCTIONS ====================

def get_daily_credits_for_plan(plan_type, user_role):
    """Get daily credit reset amount based on user's plan"""
    # Owner gets unlimited credits
    if user_role == "Owner" or plan_type == "Owner":
        return "∞"

    # Admin gets unlimited credits
    if user_role == "Admin":
        return "∞"

    # Map plan types to daily credit amounts
    daily_credits_map = {
        "Free": "100",
        "Plus": "200",
        "Pro": "500",
        "Elite": "1000",
        "VIP": "2000",
        "ULTIMATE": "2500",
        "Redeem Code": "200"  # Same as Plus
    }

    # Default to Free if plan not found
    return daily_credits_map.get(plan_type, "100")

def deduct_credit(user_id, amount=1):
    """Deduct credits from user account - IMPROVED ERROR HANDLING"""
    try:
        # Check if users.json exists
        if not os.path.exists("DATA/users.json"):
            return False, "Users database not found."

        # Load users
        with open("DATA/users.json", "r") as f:
            users = json.load(f)

        user_id_str = str(user_id)
        user = users.get(user_id_str)
        if not user:
            return False, "User not found. Please register with /register"

        # Get user role and plan
        user_role = user.get("role", "Free")
        user_plan = user.get("plan", {}).get("plan", "Free")
        credits = user.get("plan", {}).get("credits", "0")

        # Check if user is Owner or Admin - DON'T DEDUCT FOR THEM
        if user_role in ["Owner", "Admin"] or user_plan == "Owner":
            return True, "Owner/Admin has infinite credits"

        # Handle infinite credits case
        if credits == "∞":
            return True, "Infinite credits available"

        # Check and reset daily credits if needed
        reset_daily_credits_if_needed(user_id_str, user, users)

        # Get current credits again after possible reset
        credits = user["plan"].get("credits", "0")

        # Handle infinite credits after reset
        if credits == "∞":
            return True, "Infinite credits available"

        # Convert to int with error handling
        try:
            credits_int = int(credits)
        except (ValueError, TypeError):
            # If credits is not a number, reset to daily amount
            daily_credits = get_daily_credits_for_plan(user_plan, user_role)
            user["plan"]["credits"] = daily_credits
            try:
                credits_int = int(daily_credits)
            except:
                credits_int = 100  # Default fallback

        # Check if enough credits
        if credits_int >= amount:
            # Deduct credits
            new_credits = credits_int - amount
            user["plan"]["credits"] = str(new_credits)

            # Update last used timestamp
            user["last_credit_use"] = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")

            # Save changes
            users[user_id_str] = user
            with open("DATA/users.json", "w") as f:
                json.dump(users, f, indent=4)

            return True, f"Deducted {amount} credit(s). Remaining: {new_credits}"
        else:
            # Get daily credit amount for message
            daily_amount = get_daily_credits_for_plan(user_plan, user_role)
            return False, f"""Insufficient credits. Required: {amount}, Available: {credits_int}
Daily reset: {daily_amount} credits every 24 hours"""

    except json.JSONDecodeError:
        return False, "Database error. Please contact admin."
    except Exception as e:
        print(f"[deduct_credit error] {e}")
        return False, "System error. Please try again later."

def has_sufficient_credits(user_id, amount=1):
    """Check if user has sufficient credits - IMPROVED ERROR HANDLING"""
    try:
        # Check if users.json exists
        if not os.path.exists("DATA/users.json"):
            return False, "Users database not found."

        with open("DATA/users.json", "r") as f:
            users = json.load(f)

        user_id_str = str(user_id)
        user = users.get(user_id_str)
        if not user:
            return False, "User not found. Please register with /register"

        # Get user role and plan
        user_role = user.get("role", "Free")
        user_plan = user.get("plan", {}).get("plan", "Free")
        credits = user.get("plan", {}).get("credits", "0")

        # Check if user is Owner or Admin - ALWAYS SUFFICIENT
        if user_role in ["Owner", "Admin"] or user_plan == "Owner":
            return True, "Owner/Admin has infinite credits"

        # Handle infinite credits
        if credits == "∞":
            return True, "Infinite credits available"

        # Check and reset daily credits if needed
        reset_daily_credits_if_needed(user_id_str, user, users)

        # Get credits after reset
        credits = user["plan"].get("credits", "0")

        # Handle infinite credits after reset
        if credits == "∞":
            return True, "Infinite credits available"

        # Convert to int with error handling
        try:
            credits_int = int(credits)
        except (ValueError, TypeError):
            # If credits is not a number, reset to daily amount
            daily_credits = get_daily_credits_for_plan(user_plan, user_role)
            user["plan"]["credits"] = daily_credits
            users[user_id_str] = user
            with open("DATA/users.json", "w") as f:
                json.dump(users, f, indent=4)
            try:
                credits_int = int(daily_credits)
            except:
                credits_int = 100  # Default fallback

        if credits_int >= amount:
            return True, f"Sufficient credits: {credits_int}"
        else:
            # Get daily credit amount for message
            daily_amount = get_daily_credits_for_plan(user_plan, user_role)
            return False, f"Insufficient credits: {credits_int}. Daily reset: {daily_amount}"

    except json.JSONDecodeError:
        return False, "Database error"
    except Exception as e:
        print(f"[has_sufficient_credits error] {e}")
        return False, "System error"

def reset_daily_credits_if_needed(user_id_str, user, users):
    """Reset daily credits for ALL users if it's a new day - IMPROVED ERROR HANDLING"""
    try:
        user_plan = user.get("plan", {})
        plan_type = user_plan.get("plan", "Free")
        user_role = user.get("role", "Free")

        # Skip reset for Owner/Admin (they have infinite credits)
        if user_role in ["Owner", "Admin"] or plan_type == "Owner":
            # Ensure Owner/Admin have "∞" credits
            if user_plan.get("credits") != "∞":
                user["plan"]["credits"] = "∞"
                users[user_id_str] = user
            return False

        current_time = datetime.now(pytz.timezone("Asia/Kolkata"))

        # Get last reset time
        last_reset = user.get("last_credit_reset")
        if not last_reset:
            # First time, set initial reset time and credits
            daily_credits = get_daily_credits_for_plan(plan_type, user_role)
            user["last_credit_reset"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
            user["plan"]["credits"] = daily_credits
            users[user_id_str] = user
            return True

        # Parse last reset time with error handling
        try:
            last_reset_time = datetime.strptime(last_reset, "%Y-%m-%d %H:%M:%S")
            last_reset_time = pytz.timezone("Asia/Kolkata").localize(last_reset_time)
        except ValueError:
            # If time format is wrong, reset now
            daily_credits = get_daily_credits_for_plan(plan_type, user_role)
            user["plan"]["credits"] = daily_credits
            user["last_credit_reset"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
            users[user_id_str] = user
            return True

        # Check if 24 hours have passed
        time_diff = current_time - last_reset_time

        if time_diff >= timedelta(hours=24):
            # Reset credits based on user's plan
            daily_credits = get_daily_credits_for_plan(plan_type, user_role)
            user["plan"]["credits"] = daily_credits
            user["last_credit_reset"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
            users[user_id_str] = user
            return True

        return False
    except Exception as e:
        print(f"[reset_daily_credits error] {e}")
        # Try to at least set basic credits
        try:
            user["plan"]["credits"] = "100"
            users[user_id_str] = user
        except:
            pass
        return False

def deduct_credit_bulk(user_id, amount):
    """Deduct multiple credits at once"""
    return deduct_credit(user_id, amount)

def get_user_credits(user_id):
    """Get user's current credits - IMPROVED ERROR HANDLING"""
    try:
        # Check if users.json exists
        if not os.path.exists("DATA/users.json"):
            return "0"

        with open("DATA/users.json", "r") as f:
            users = json.load(f)

        user_id_str = str(user_id)
        user = users.get(user_id_str)
        if not user:
            return "0"

        # Get user role and plan
        user_role = user.get("role", "Free")
        user_plan = user.get("plan", {}).get("plan", "Free")

        # Owner/Admin always have infinite credits
        if user_role in ["Owner", "Admin"] or user_plan == "Owner":
            return "∞"

        # Check and reset daily credits if needed
        reset_daily_credits_if_needed(user_id_str, user, users)

        # Get credits
        credits = user["plan"].get("credits", "0")

        # Handle any corrupted credit values
        if credits == "∞":
            return "∞"

        try:
            # Try to convert to int to validate
            int(credits)
            return credits
        except (ValueError, TypeError):
            # Reset to daily amount
            daily_credits = get_daily_credits_for_plan(user_plan, user_role)
            user["plan"]["credits"] = daily_credits
            users[user_id_str] = user
            with open("DATA/users.json", "w") as f:
                json.dump(users, f, indent=4)
            return daily_credits

    except json.JSONDecodeError:
        return "0"
    except Exception as e:
        print(f"[get_user_credits error] {e}")
        return "0"

def add_credits(user_id, amount):
    """Add credits to user account - IMPROVED ERROR HANDLING"""
    try:
        # Check if users.json exists
        if not os.path.exists("DATA/users.json"):
            return False, "Users database not found."

        with open("DATA/users.json", "r") as f:
            users = json.load(f)

        user_id_str = str(user_id)
        user = users.get(user_id_str)
        if not user:
            return False, "User not found."

        # Get user role and plan
        user_role = user.get("role", "Free")
        user_plan = user.get("plan", {}).get("plan", "Free")
        credits = user.get("plan", {}).get("credits", "0")

        # Don't add to infinite credits (Owner/Admin)
        if user_role in ["Owner", "Admin"] or user_plan == "Owner" or credits == "∞":
            return True, "User has infinite credits"

        # Convert to int with error handling
        try:
            current = int(credits) if credits != "∞" else 0
        except (ValueError, TypeError):
            current = 0

        new_total = current + amount
        user["plan"]["credits"] = str(new_total)

        users[user_id_str] = user
        with open("DATA/users.json", "w") as f:
            json.dump(users, f, indent=4)

        return True, f"Added {amount} credits. Total: {new_total}"
    except json.JSONDecodeError:
        return False, "Database error"
    except Exception as e:
        print(f"[add_credits error] {e}")
        return False, "System error"

# ==================== UNIVERSAL CHARGE COMMAND HANDLER ====================

class ChargeCommandProcessor:
    """Universal charge command handler - Deducts credits ONLY after check completes"""

    def __init__(self):
        self.owner_id = None

    def load_owner_id(self):
        """Load OWNER_ID from config file"""
        try:
            with open("FILES/config.json", "r") as f:
                config_data = json.load(f)
                self.owner_id = config_data.get("OWNER")
                return self.owner_id
        except:
            return None

    def load_users(self):
        """Load users from users.json"""
        try:
            with open("DATA/users.json", "r") as f:
                return json.load(f)
        except:
            return {}

    def is_user_owner_or_admin(self, user_data: Dict) -> bool:
        """Check if user is Owner or Admin"""
        if not user_data:
            return False

        user_role = user_data.get("role", "Free")
        user_plan = user_data.get("plan", {}).get("plan", "Free")

        return user_role in ["Owner", "Admin"] or user_plan == "Owner"

    def get_user_plan_info(self, user_id: int) -> Tuple[Dict, str]:
        """Get user data and plan name"""
        users = self.load_users()
        user_id_str = str(user_id)

        if user_id_str not in users:
            return None, "Not Registered"

        user_data = users[user_id_str]
        plan_name = user_data.get("plan", {}).get("plan", "Free")

        return user_data, plan_name

    def validate_user_for_charge(self, user_id: int, credits_needed: int = 2) -> Tuple[bool, str, Dict]:
        """
        Validate user before processing charge command

        Returns:
            Tuple: (is_valid, message, user_data)
        """
        try:
            # Load owner ID if not loaded
            if self.owner_id is None:
                self.load_owner_id()

            # Get user data
            user_data, plan_name = self.get_user_plan_info(user_id)
            if not user_data:
                return False, "User not registered. Use /register first.", None

            # Check if Owner/Admin
            if self.is_user_owner_or_admin(user_data):
                return True, f"Owner/Admin detected - will not deduct credits", user_data

            # Check if user has sufficient credits
            has_credits, credit_msg = has_sufficient_credits(user_id, credits_needed)

            if not has_credits:
                current_credits = get_user_credits(user_id)
                error_msg = f"""<pre>💳 Insufficient Credits</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: {credit_msg}
⟐ <b>Required:</b> <code>{credits_needed} credits</code>
⟐ <b>Available:</b> <code>{current_credits}</code>
⟐ <b>Your Plan:</b> <code>{plan_name}</code>
━━━━━━━━━━━━━"""
                return False, error_msg, None

            return True, "User validated successfully", user_data

        except Exception as e:
            error_msg = f"Validation error: {str(e)[:100]}"
            return False, error_msg, None

    async def execute_charge_command(
        self, 
        user_id: int, 
        check_callback: Callable,
        *check_args,  # FIXED: Accepts variable number of positional arguments
        credits_needed: int = 2,
        command_name: str = "unknown",
        gateway_name: str = "Unknown Gateway"
    ) -> Tuple[bool, str, bool]:
        """
        Universal method to execute charge commands
        Credits are ONLY deducted AFTER the check completes successfully

        Args:
            user_id: Telegram user ID (POSITIONAL)
            check_callback: Function that performs the actual card check (POSITIONAL)
            *check_args: Arguments to pass to check_callback (POSITIONAL)
            credits_needed: Credits required for this command (default: 2)
            command_name: Command name for logging
            gateway_name: Gateway name for logging

        Returns:
            Tuple: (success, message, credits_deducted)
        """
        try:
            print(f"[ChargeProcessor] Processing {command_name} for user {user_id}")

            # Step 1: Validate user
            is_valid, validation_msg, user_data = self.validate_user_for_charge(user_id, credits_needed)

            if not is_valid:
                print(f"[ChargeProcessor] User validation failed: {validation_msg[:50]}")
                return False, validation_msg, False

            # Step 2: Execute the actual check
            print(f"[ChargeProcessor] Starting card check for {command_name}")
            try:
                # This is where the actual card checking happens
                # Pass all check_args to the callback
                result = await check_callback(*check_args)

                # IMPORTANT: If we reach here, the check HAS STARTED AND COMPLETED
                # (approved, declined, or system error - doesn't matter)

                # Step 3: Check completed - NOW deduct credits
                print(f"[ChargeProcessor] Check completed, deducting {credits_needed} credits")
                credits_deducted = await self.deduct_credits_after_check(
                    user_id, credits_needed, user_data, command_name
                )

                # NO CREDIT MESSAGE ADDED - User can check credits with /info
                print(f"[ChargeProcessor] Command {command_name} completed successfully")
                return True, result, credits_deducted

            except Exception as check_error:
                # Card check FAILED before completion - DO NOT DEDUCT CREDITS
                error_msg = f"""<pre>❌ Check Failed</pre>
━━━━━━━━━━━━━
⟐ <b>Gateway</b>: {gateway_name}
⟐ <b>Message</b>: Card checking failed to complete.
⟐ <b>Error</b>: <code>{str(check_error)[:100]}</code>
⟐ <b>Credits</b>: <code>NOT deducted - check failed before completion</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━"""

                print(f"[ChargeProcessor] Check failed before completion: {str(check_error)[:50]}")
                return False, error_msg, False

        except Exception as e:
            # General processing error - DO NOT DEDUCT CREDITS
            error_msg = f"""<pre>❌ Processing Error</pre>
━━━━━━━━━━━━━
⟐ <b>Gateway</b>: {gateway_name}
⟐ <b>Message</b>: An error occurred while processing your request.
⟐ <b>Error</b>: <code>{str(e)[:100]}</code>
⟐ <b>Credits</b>: <code>NOT deducted - processing failed</code>
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━"""

            print(f"[ChargeProcessor] Processing error: {str(e)[:50]}")
            return False, error_msg, False

    async def deduct_credits_after_check(
        self, 
        user_id: int, 
        credits_needed: int, 
        user_data: Dict, 
        command_name: str
    ) -> bool:
        """
        Deduct credits after successful card check completion
        Returns True if credits were deducted, False otherwise
        """
        try:
            # Skip deduction for Owner/Admin
            if self.is_user_owner_or_admin(user_data):
                print(f"[ChargeProcessor] Owner/Admin - skipping credit deduction for {command_name}")
                return False

            # Deduct credits for regular users
            deduct_success, deduct_msg = deduct_credit(user_id, credits_needed)

            if deduct_success:
                print(f"[ChargeProcessor] Deducted {credits_needed} credits for {command_name}")
                return True
            else:
                print(f"[ChargeProcessor] Credit deduction failed for {command_name}: {deduct_msg}")
                return False

        except Exception as e:
            print(f"[ChargeProcessor] Error deducting credits for {command_name}: {str(e)[:50]}")
            return False

    def get_processing_message(
        self, 
        cc: str, 
        mes: str, 
        ano: str, 
        cvv: str, 
        username: str, 
        user_plan: str, 
        gateway_name: str, 
        command_name: str
    ) -> str:
        """Generate processing message for charge commands"""
        return f"""<b>「$cmd → /{command_name}」| <b>WAYNE</b> </b>
━━━━━━━━━━━━━━━
<b>[•] Card-</b> <code>{cc}|{mes}|{ano}|{cvv}</code>
<b>[•] Gateway -</b> {gateway_name}
<b>[•] Status-</b> Processing... ⏳
━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━ ━
<b>[+] Plan:</b> {user_plan}
<b>[+] User:</b> @{username}
━━━━━━━━━━━━━━━
<b>Checking..</b>"""

    def get_usage_message(
        self, 
        command_name: str, 
        gateway_name: str, 
        example_card: str = "4111111111111111|12|2025|123"
    ) -> str:
        """Generate usage message for charge commands"""
        return f"""<pre>#WAYNE ─[{gateway_name.upper()}]─</pre>
━━━━━━━━━━━━━
⟐ <b>Command</b>: <code>/{command_name}</code> or <code>.{command_name}</code> or <code>${command_name}</code>
⟐ <b>Usage</b>: <code>/{command_name} cc|mm|yy|cvv</code>
⟐ <b>Example</b>: <code>/{command_name} {example_card}</code>
⟐ <b>Gate</b>: {gateway_name}
━━━━━━━━━━━━━
<b>~ Note:</b> <code>Tests card with charge (Deducts 2 credits AFTER check completes)</code>
<b>~ Note:</b> <code>Credits are ONLY deducted when check actually runs and completes</code>
<b>~ Note:</b> <code>If check fails to start, NO credits are deducted</code>"""

# ==================== HELPER FUNCTIONS ====================

# Initialize default credits for new users
def initialize_user_credits(user_id):
    """Initialize credits for new user - IMPROVED ERROR HANDLING"""
    try:
        # Check if users.json exists, create if not
        if not os.path.exists("DATA/users.json"):
            os.makedirs("DATA", exist_ok=True)
            with open("DATA/users.json", "w") as f:
                json.dump({}, f)

        with open("DATA/users.json", "r") as f:
            users = json.load(f)

        user_id_str = str(user_id)
        if user_id_str in users:
            user = users[user_id_str]
            user_plan = user.get("plan", {})
            plan_type = user_plan.get("plan", "Free")
            user_role = user.get("role", "Free")

            # Get daily credits based on plan
            daily_credits = get_daily_credits_for_plan(plan_type, user_role)

            # Set initial credits
            user["plan"]["credits"] = daily_credits
            user["last_credit_reset"] = datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
            users[user_id_str] = user

            with open("DATA/users.json", "w") as f:
                json.dump(users, f, indent=4)
            return True

        return False
    except json.JSONDecodeError:
        # Create fresh database
        os.makedirs("DATA", exist_ok=True)
        with open("DATA/users.json", "w") as f:
            json.dump({}, f)
        return False
    except Exception as e:
        print(f"[initialize_user_credits error] {e}")
        return False

def check_and_reset_all_users_credits():
    """Check and reset credits for all users (can be run daily via cron job) - IMPROVED"""
    try:
        # Check if users.json exists
        if not os.path.exists("DATA/users.json"):
            return 0

        with open("DATA/users.json", "r") as f:
            users = json.load(f)

        current_time = datetime.now(pytz.timezone("Asia/Kolkata"))
        updated_count = 0

        for user_id_str, user in users.items():
            try:
                user_plan = user.get("plan", {})
                plan_type = user_plan.get("plan", "Free")
                user_role = user.get("role", "Free")

                # Skip Owner/Admin (they have infinite credits)
                if user_role in ["Owner", "Admin"] or plan_type == "Owner":
                    # Ensure they have "∞" credits
                    if user_plan.get("credits") != "∞":
                        user["plan"]["credits"] = "∞"
                        users[user_id_str] = user
                        updated_count += 1
                    continue

                last_reset = user.get("last_credit_reset")
                if last_reset:
                    try:
                        last_reset_time = datetime.strptime(last_reset, "%Y-%m-%d %H:%M:%S")
                        last_reset_time = pytz.timezone("Asia/Kolkata").localize(last_reset_time)

                        # Check if 24 hours have passed
                        time_diff = current_time - last_reset_time

                        if time_diff >= timedelta(hours=24):
                            daily_credits = get_daily_credits_for_plan(plan_type, user_role)
                            user["plan"]["credits"] = daily_credits
                            user["last_credit_reset"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
                            users[user_id_str] = user
                            updated_count += 1
                    except ValueError:
                        # Reset if time format is wrong
                        daily_credits = get_daily_credits_for_plan(plan_type, user_role)
                        user["plan"]["credits"] = daily_credits
                        user["last_credit_reset"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
                        users[user_id_str] = user
                        updated_count += 1
            except:
                continue  # Skip problem users

        if updated_count > 0:
            with open("DATA/users.json", "w") as f:
                json.dump(users, f, indent=4)

        return updated_count

    except json.JSONDecodeError:
        return 0
    except Exception as e:
        print(f"[check_and_reset_all_users_credits error] {e}")
        return 0

# ==================== RESETT COMMAND FUNCTION ====================

def reset_user_credits_now(user_id: int) -> Tuple[bool, str]:
    """
    Reset user's credits to their daily amount immediately
    Used by /resett command (Owner only)

    Returns: (success, message)
    """
    try:
        # Check if users.json exists
        if not os.path.exists("DATA/users.json"):
            return False, "Users database not found."

        with open("DATA/users.json", "r") as f:
            users = json.load(f)

        user_id_str = str(user_id)
        user = users.get(user_id_str)
        if not user:
            return False, "User not found."

        # Get user role and plan
        user_role = user.get("role", "Free")
        user_plan = user.get("plan", {}).get("plan", "Free")

        # Get daily credits for this plan
        daily_credits = get_daily_credits_for_plan(user_plan, user_role)

        # Reset credits to daily amount
        user["plan"]["credits"] = daily_credits

        # Update reset time to NOW
        current_time = datetime.now(pytz.timezone("Asia/Kolkata"))
        user["last_credit_reset"] = current_time.strftime("%Y-%m-%d %H:%M:%S")

        # Save changes
        users[user_id_str] = user
        with open("DATA/users.json", "w") as f:
            json.dump(users, f, indent=4)

        return True, f"Reset credits for user {user_id}. New credits: {daily_credits}"

    except Exception as e:
        print(f"[reset_user_credits_now error] {e}")
        return False, f"Error resetting credits: {str(e)}"

# ==================== GLOBAL INSTANCE ====================

# Create global instance of ChargeCommandProcessor
charge_processor = ChargeCommandProcessor()