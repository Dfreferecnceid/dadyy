# main.py
import json
import asyncio
import threading
import os
import sys
import time
import sqlite3
from pyrogram import Client, idle, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType
from flask import Flask
from BOT.plans.plan1 import check_and_expire_plans as plan1_expiry
from BOT.helper.permissions import apply_global_middlewares, is_group_authorized
import nest_asyncio

# Import the automatic firewall protection
try:
    from BOT.firewall import firewall
    print("✅ Firewall protection loaded")
except ImportError:
    print("⚠️ Firewall module not found, running without firewall protection")
    firewall = None

# Load bot credentials
with open("FILES/config.json", "r", encoding="utf-8") as f:
    DATA = json.load(f)
    API_ID = DATA["API_ID"]
    API_HASH = DATA["API_HASH"]
    BOT_TOKEN = DATA["BOT_TOKEN"]

# Pyrogram plugins - Load from BOT only
plugins = dict(root="BOT")

# Clean up any existing session files to prevent lock issues
def cleanup_session_files():
    """Remove any existing session files to prevent database lock issues"""
    session_files = ["MY_BOT.session", "MY_BOT.session-journal"]
    for session_file in session_files:
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                print(f"🗑️ Removed existing session file: {session_file}")
                time.sleep(1)  # Give OS time to release file locks
            except Exception as e:
                print(f"⚠️ Could not remove {session_file}: {e}")

# Run cleanup before creating client
cleanup_session_files()

# Pyrogram client with explicit session directory
bot = Client(
    "MY_BOT",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=plugins,
    workdir=".",  # Explicitly set work directory
    sleep_threshold=30  # Increase sleep threshold to avoid connection issues
)

# List of all known bot commands (with and without prefixes)
BOT_COMMANDS = [
    # Start and basic commands
    "start", "register", "cmds", "info", "redeem", "buy",

    # Tool commands
    "fake", "gen", "gate", "bin", "sk", "setpx", "delpx", "getpx",

    # Admin commands
    "gc", "plans", "plan", "looser", "broad", "notused", "off", "on",
    "banbin", "unbanbin", "ban", "unban", "add", "rmv", "plus", "pro",
    "elite", "vip", "ultimate",

    # Gate commands
    "au", "chk", "bu", "ad",  # Auth
    "xx", "xo", "xs", "xc", "xp", "bt", "sh", "slf",  # Charge
    "mau", "mchk", "mxc", "mxp", "mxx"  # Mass
]

def is_bot_command(message_text: str) -> bool:
    """Check if message contains any bot command"""
    if not message_text:
        return False

    text_lower = message_text.strip().lower()

    for command in BOT_COMMANDS:
        if text_lower.startswith(f'/{command}') or text_lower.startswith(f'.{command}') or text_lower.startswith(f'${command}'):
            return True
        if f' /{command}' in text_lower or f' .{command}' in text_lower or f' ${command}' in text_lower:
            return True
        if text_lower.startswith(f'/{command} ') or text_lower.startswith(f'.{command} ') or text_lower.startswith(f'${command} '):
            return True

    return False

# Global group authorization check
@bot.on_message(filters.group)
async def global_group_auth_check(client: Client, message: Message):
    if message.chat.type == ChatType.PRIVATE:
        message.continue_propagation()
        return

    if not message.text:
        message.continue_propagation()
        return

    text = message.text.strip()

    if not is_bot_command(text):
        message.continue_propagation()
        return

    if text.startswith('/add') or text.startswith('.add') or text.startswith('/rmv') or text.startswith('.rmv'):
        message.continue_propagation()
        return

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

    message.continue_propagation()

apply_global_middlewares()

# Simple Flask App
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

@app.route("/health")
def health():
    """Simple health check"""
    return "OK", 200

@app.route("/status")
def status():
    """Simple status endpoint"""
    return json.dumps({
        "status": "running",
        "timestamp": time.time()
    }, indent=2)

def run_flask():
    """Run Flask server with minimal configuration"""
    try:
        # Use minimal settings to avoid conflicts
        app.run(
            host="0.0.0.0", 
            port=3000, 
            debug=False, 
            threaded=True,
            use_reloader=False  # Disable reloader to avoid multiple instances
        )
    except Exception as e:
        print(f"❌ Flask server error: {e}")

def get_flood_wait_time(error_msg: str) -> int:
    """Extract wait time from flood wait error message"""
    try:
        # Extract seconds from error message like "A wait of 236 seconds is required"
        import re
        match = re.search(r'wait of (\d+) seconds', error_msg)
        if match:
            return int(match.group(1))
    except:
        pass
    return 60  # Default 60 seconds

async def run_bot():
    """Run the Telegram bot with proper error handling"""
    max_retries = 5  # Increased retries for flood wait
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            print(f"🚀 Starting bot (Attempt {attempt + 1}/{max_retries})...")
            
            # Ensure bot is not already running
            if not bot.is_connected:
                await bot.start()
                print("✅ Bot started successfully!")

                # Start plan expiry checker
                try:
                    asyncio.create_task(plan1_expiry(bot))
                except Exception as e:
                    print(f"⚠️ Could not start plan expiry checker: {e}")

                # Keep the bot running
                await idle()

            break  # Success, exit retry loop

        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                print(f"⚠️ Database locked, retrying in {retry_delay} seconds...")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    # Clean session files before retry
                    cleanup_session_files()
                    continue
                else:
                    print("❌ Max retries reached. Could not start bot.")
                    raise
            else:
                raise
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Bot startup error: {error_msg}")
            
            # Check if it's a flood wait error
            if "FLOOD_WAIT" in error_msg:
                wait_time = get_flood_wait_time(error_msg)
                print(f"⏳ Telegram flood wait detected. Waiting {wait_time} seconds...")
                
                if attempt < max_retries - 1:
                    # Wait for the required time + buffer
                    time.sleep(wait_time + 10)
                    cleanup_session_files()
                    continue
                else:
                    print("❌ Max retries reached for flood wait.")
                    raise
            
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                # Clean session files before retry
                cleanup_session_files()
                continue
            else:
                raise

async def stop_bot():
    """Stop the bot properly"""
    try:
        if bot.is_connected:
            await bot.stop()
            print("🛑 Bot stopped.")
    except Exception as e:
        print(f"⚠️ Error stopping bot: {e}")

def save_firewall_state():
    """Save firewall state if available"""
    if firewall:
        try:
            firewall.save_blocked_ips()
            print("💾 Firewall state saved")
        except Exception as e:
            print(f"⚠️ Could not save firewall state: {e}")

async def main_async():
    """Main async function"""
    print("=" * 50)
    print("🤖 BOT STARTUP SEQUENCE")
    print("=" * 50)
    
    # Show firewall status
    if firewall:
        print("🛡️  Automatic firewall protection: ACTIVE")
        print(f"   - Blocked IPs loaded: {len(firewall.blocked_ips)}")
    else:
        print("⚠️  Firewall protection: NOT ACTIVE")

    # Start Flask in a daemon thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Flask server started on port 3000")

    # Give Flask a moment to start
    await asyncio.sleep(2)

    try:
        await run_bot()
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot error: {e}")
    finally:
        # Cleanup
        await stop_bot()
        save_firewall_state()

def main():
    """Main entry point"""
    nest_asyncio.apply()
    
    # Create and run event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(main_async())
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Application error: {e}")
    finally:
        # Cleanup event loop
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except:
            pass

if __name__ == "__main__":
    main()
