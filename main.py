# main.py
import json
import asyncio
import threading
import os
import sys
import time
from pyrogram import Client, idle, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType
from flask import Flask
from BOT.plans.plan1 import check_and_expire_plans as plan1_expiry
from BOT.helper.permissions import apply_global_middlewares, is_group_authorized

# Import the automatic firewall protection
try:
    from BOT.firewall import firewall
    FIREWALL_LOADED = True
except ImportError:
    FIREWALL_LOADED = False

# Load bot credentials
with open("FILES/config.json", "r", encoding="utf-8") as f:
    DATA = json.load(f)
    API_ID = DATA["API_ID"]
    API_HASH = DATA["API_HASH"]
    BOT_TOKEN = DATA["BOT_TOKEN"]

# Pyrogram plugins - Load from BOT only
plugins = dict(root="BOT")

# Clean up any existing session files
def cleanup_session_files():
    """Remove any existing session files"""
    session_files = ["MY_BOT.session", "MY_BOT.session-journal"]
    for session_file in session_files:
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                print(f"🗑️ Removed: {session_file}")
                time.sleep(1)
            except:
                pass

# Run cleanup
cleanup_session_files()

# Create Pyrogram client
bot = Client(
    "MY_BOT",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=plugins,
    workdir=".",
    sleep_threshold=30
)

# Command prefixes to check
COMMAND_PREFIXES = ['/', '.', '$']

# Global group authorization check
@bot.on_message(filters.group)
async def global_group_auth_check(client: Client, message: Message):
    """Check if group is authorized before processing commands"""
    if not message.text:
        return
    
    text = message.text.strip()
    
    # Check if message starts with any command prefix
    if not any(text.startswith(prefix) for prefix in COMMAND_PREFIXES):
        return
    
    # Skip /add and /rmv commands (they need to work to authorize groups)
    if text.startswith(('/add', '.add', '/rmv', '.rmv')):
        return
    
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

apply_global_middlewares()

# Simple Flask App
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    """Run Flask server"""
    try:
        app.run(host="0.0.0.0", port=3000, debug=False, threaded=True, use_reloader=False)
    except Exception as e:
        print(f"❌ Flask error: {e}")

def extract_flood_wait(error_msg: str) -> int:
    """Extract wait time from flood wait error"""
    try:
        import re
        match = re.search(r'wait of (\d+) seconds', error_msg)
        if match:
            return int(match.group(1))
    except:
        pass
    return 60  # Default

async def start_bot_with_retry():
    """Start bot with retry logic for flood wait"""
    max_attempts = 3
    
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"🚀 Starting bot (Attempt {attempt}/{max_attempts})...")
            
            if not bot.is_connected:
                await bot.start()
                print("✅ Bot started successfully!")
                
                # Set bot commands (optional but good for UX)
                try:
                    await bot.set_bot_commands([
                        ("start", "Start the bot"),
                        ("register", "Register in the bot"),
                        ("cmds", "Show all commands"),
                        ("info", "Check your info"),
                        ("buy", "Buy premium plans"),
                        ("redeem", "Redeem gift code")
                    ])
                    print("✅ Bot commands set")
                except:
                    print("⚠️ Could not set bot commands")
                
                # Start plan expiry checker
                try:
                    asyncio.create_task(plan1_expiry(bot))
                    print("✅ Plan expiry checker started")
                except Exception as e:
                    print(f"⚠️ Plan checker error: {e}")
                
                return True
                
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Attempt {attempt} failed: {error_msg}")
            
            if "FLOOD_WAIT" in error_msg:
                wait_time = extract_flood_wait(error_msg)
                print(f"⏳ Flood wait detected. Waiting {wait_time} seconds...")
                time.sleep(wait_time + 5)
                continue
                
            if attempt < max_attempts:
                print(f"Retrying in 10 seconds...")
                time.sleep(10)
                cleanup_session_files()
            else:
                print("❌ Max attempts reached")
                return False
    
    return False

async def main():
    """Main async function"""
    print("=" * 50)
    print("🤖 BOT STARTUP SEQUENCE")
    print("=" * 50)
    
    if FIREWALL_LOADED:
        print("🛡️  Firewall: ACTIVE")
    else:
        print("⚠️  Firewall: NOT LOADED")
    
    # Start Flask
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Flask server started on port 3000")
    
    # Wait a bit for Flask
    await asyncio.sleep(2)
    
    # Start the bot
    if await start_bot_with_retry():
        try:
            print("🤖 Bot is now running and should respond to commands!")
            print("📱 Test with: /start or /cmds")
            await idle()
        except KeyboardInterrupt:
            print("\n👋 Bot stopped by user")
        except Exception as e:
            print(f"❌ Bot runtime error: {e}")
        finally:
            # Clean shutdown
            if bot.is_connected:
                await bot.stop()
                print("🛑 Bot stopped cleanly")
    else:
        print("❌ Could not start bot after retries")

if __name__ == "__main__":
    # Handle asyncio properly
    try:
        # Try to get existing loop
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # Create new loop if none exists
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n👋 Application stopped")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        # Save firewall state if loaded
        if FIREWALL_LOADED:
            try:
                firewall.save_blocked_ips()
                print("💾 Firewall state saved")
            except:
                pass
        
        # Close the loop
        try:
            loop.close()
        except:
            pass
