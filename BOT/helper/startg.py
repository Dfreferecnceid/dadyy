# BOT/helper/startg.py
# Gates Menu Configuration File - UPDATED with dynamic command status and Square auth

import html
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Import command status functions from Admins module - FIXED IMPORT
try:
    from .Admins import get_command_status
except ImportError:
    # Fallback function if import fails
    def get_command_status(command_name: str) -> str:
        """Fallback: always show Active"""
        return "Active ✅"

# ==================== GATE COMMAND CONFIGURATIONS ====================

# Auth -> Stripe commands
STRIPE_AUTH_CONFIG = {
    "title": "<pre>#WAYNE 〔Stripe Auth Gates〕</pre>",
    "description": "━ ━ ━ ━ ━━━ ━ ━ ━ ━",
    "commands": [
        {
            "name": "Stripe Auth",
            "command": "$au cc|mes|ano|cvv",
            "command_key": "au",
            "status": "",  # Will be filled dynamically
            "note": "FREE"
        },
        {
            "name": "Stripe Check", 
            "command": "$chk cc|mes|ano|cvv",
            "command_key": "chk",
            "status": "",  # Will be filled dynamically
            "note": "FREE"
        }
    ]
}

# Auth -> Braintree commands  
BRAINTREE_AUTH_CONFIG = {
    "title": "<pre>#WAYNE 〔Braintree Auth Gates〕</pre>",
    "description": "━ ━ ━ ━ ━━━ ━ ━ ━ ━",
    "commands": [
        {
            "name": "Braintree Auth",
            "command": "$bu cc|mes|ano|cvv",
            "command_key": "bu",
            "status": "",  # Will be filled dynamically
            "note": "FREE"
        }
    ]
}

# Auth -> Adyen commands
ADYEN_AUTH_CONFIG = {
    "title": "<pre>#WAYNE 〔Adyen Auth Gates〕</pre>",
    "description": "━ ━ ━ ━ ━━━ ━ ━ ━ ━",
    "commands": [
        {
            "name": "Adyen Auth",
            "command": "$ad cc|mes|ano|cvv",
            "command_key": "ad",
            "status": "",  # Will be filled dynamically
            "note": "FREE"
        }
    ]
}

# Auth -> Square commands - ADDED NEW CONFIG
SQUARE_AUTH_CONFIG = {
    "title": "<pre>#WAYNE 〔Square Auth Gates〕</pre>",
    "description": "━ ━ ━ ━ ━━━ ━ ━ ━ ━",
    "commands": [
        {
            "name": "Square Auth",
            "command": "$sq cc|mes|ano|cvv",
            "command_key": "sq",
            "status": "",  # Will be filled dynamically
            "note": "FREE"
        }
    ]
}

# Charge -> Stripe commands - ADDED ALL 5 COMMANDS HERE
STRIPE_CHARGE_CONFIG = {
    "title": "<pre>#WAYNE 〔Stripe Charge Gates〕</pre>",
    "description": "━ ━ ━ ━ ━━━ ━ ━ ━ ━",
    "commands": [
        {
            "name": "Stripe Charge (/xx)) - 0.12$",
            "command": "$xx cc|mes|ano|cvv",
            "command_key": "xx",
            "status": "",  # Will be filled dynamically
            "note": "2 Credits"
        },
        {
            "name": "Stripe Charge (/xo) - 2$",
            "command": "$xo cc|mes|ano|cvv",
            "command_key": "xo",
            "status": "",  # Will be filled dynamically
            "note": "2 Credits"
        },
        {
            "name": "Stripe Charge (/xs) - 5$",
            "command": "$xs cc|mes|ano|cvv",
            "command_key": "xs",
            "status": "",  # Will be filled dynamically
            "note": "2 Credits"
        },
        {
            "name": "Stripe Charge (/xc) - 10$",
            "command": "$xc cc|mes|ano|cvv",
            "command_key": "xc",
            "status": "",  # Will be filled dynamically
            "note": "2 Credits"
        },
        {
            "name": "Stripe Charge (/xp) - 15$",
            "command": "$xp cc|mes|ano|cvv",
            "command_key": "xp",
            "status": "",  # Will be filled dynamically
            "note": "2 Credits"
        }
    ]
}

# Charge -> Braintree commands
BRAINTREE_CHARGE_CONFIG = {
    "title": "<pre>#WAYNE 〔Braintree Charge Gates〕</pre>",
    "description": "━ ━ ━ ━ ━━━ ━ ━ ━ ━",
    "commands": [
        {
            "name": "Braintree Charge",
            "command": "$bt cc|mes|ano|cvv",
            "command_key": "bt",
            "status": "",  # Will be filled dynamically
            "note": ""
        }
    ]
}

# Charge -> Shopify commands
SHOPIFY_CHARGE_CONFIG = {
    "title": "<pre>#WAYNE 〔Shopify Charge Gates〕</pre>",
    "description": "━ ━ ━ ━ ━━━ ━ ━ ━ ━",
    "commands": [
        {
            "name": "Shopify Charge (SH)",
            "command": "$sh cc|mes|ano|cvv",
            "command_key": "sh",
            "status": "",  # Will be filled dynamically
            "note": "NA"
        },
        {
            "name": "Self Shopify",
            "command": "$slf cc|mes|ano|cvv",
            "command_key": "slf",
            "status": "",  # Will be filled dynamically
            "note": "NA"
        }
    ]
}

# Mass commands (all in one)
MASS_COMMANDS_CONFIG = {
    "title": "<pre>#WAYNE 〔Mass Check Commands〕</pre>",
    "description": "━ ━ ━ ━ ━━━ ━ ━ ━ ━",
    "commands": [
        {
            "name": "Mass Stripe Auth (/mau)",
            "command": "$mau cc|mes|ano|cvv",
            "command_key": "mau",
            "status": "",  # Will be filled dynamically
            "note": "As Per User's Plan"
        },
        {
            "name": "Mass Stripe Check (/mchk)",
            "command": "$mchk cc|mes|ano|cvv",
            "command_key": "mchk",
            "status": "",  # Will be filled dynamically
            "note": "As Per User's Plan"
        },
        {
            "name": "Mass Stripe Charge (/mxc)",
            "command": "$mxc cc|mes|ano|cvv",
            "command_key": "mxc",
            "status": "",  # Will be filled dynamically
            "note": "As Per User's Plan"
        },
        {
            "name": "Mass Stripe Charge (/mxp)",
            "command": "$mxp cc|mes|ano|cvv",
            "command_key": "mxp",
            "status": "",  # Will be filled dynamically
            "note": "As Per User's Plan"
        },
        {
            "name": "Mass Stripe Charge (/mxx)",
            "command": "$mxx cc|mes|ano|cvv",
            "command_key": "mxx",
            "status": "",  # Will be filled dynamically
            "note": "As Per User's Plan"
        }
    ]
}

# ==================== HELPER FUNCTIONS ====================

def update_config_status(config):
    """Update command status in config dynamically"""
    for command in config["commands"]:
        command_key = command.get("command_key", "")
        if command_key:
            status = get_command_status(command_key)
            command["status"] = status
        else:
            # Try to extract command from command string
            cmd_str = command["command"]
            if cmd_str.startswith("$"):
                cmd_key = cmd_str[1:].split()[0]  # Extract $xx -> xx
                status = get_command_status(cmd_key)
                command["status"] = status
            else:
                command["status"] = "Active ✅"  # Default
    return config

def get_dynamic_config(config_name):
    """Get config with dynamic status updates"""
    configs = {
        "stripe_auth": STRIPE_AUTH_CONFIG,
        "braintree_auth": BRAINTREE_AUTH_CONFIG,
        "adyen_auth": ADYEN_AUTH_CONFIG,
        "square_auth": SQUARE_AUTH_CONFIG,  # ADDED
        "stripe_charge": STRIPE_CHARGE_CONFIG,
        "braintree_charge": BRAINTREE_CHARGE_CONFIG,
        "shopify_charge": SHOPIFY_CHARGE_CONFIG,
        "mass": MASS_COMMANDS_CONFIG
    }

    if config_name in configs:
        return update_config_status(configs[config_name])
    return None

# ==================== MENU GENERATION FUNCTIONS ====================

def get_gates_main_menu():
    """Get the main gates menu - EXACTLY as in start.py"""
    text = """<pre>#WAYNE 〔Gates Menu〕</pre>
━━━━━━━━━━━━━
<b>Available Gate Categories:</b>

⟐ <b>Auth Gates</b> 
⟐ <b>Charge Gates</b>
⟐ <b>Mass Gates</b> 

━━━━━━━━━━━━━
<b>~ Note:</b> <code>Disabled commands show ❌ status in menus</code>"""

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Auth", callback_data="gates_auth"),
            InlineKeyboardButton("Charge", callback_data="gates_charge")
        ],
        [
            InlineKeyboardButton("Mass", callback_data="gates_mass"),
            InlineKeyboardButton("Back", callback_data="home")
        ]
    ])
    return text, buttons

def get_auth_submenu():
    """Get auth submenu (Stripe, Braintree, Adyen, Square) - UPDATED"""
    text = """<pre>#WAYNE 〔Auth Gates〕</pre>
━━━━━━━━━━━━━
<b>Available Auth Gate Types:</b>

⟐ <b>Stripe Auth</b> - <code>Authentication via Stripe</code>
⟐ <b>Braintree Auth</b> - <code>Authentication via Braintree</code>
⟐ <b>Adyen Auth</b> - <code>Authentication via Adyen</code>
⟐ <b>Square Auth</b> - <code>Authentication via Square</code>

━━━━━━━━━━━━━
<b>~ Note:</b> <code>Click on a gateway to see available commands</code>
<b>~ Note:</b> <code>Disabled commands show ❌ status</code>"""

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Stripe", callback_data="auth_stripe"),
            InlineKeyboardButton("Braintree", callback_data="auth_braintree")
        ],
        [
            InlineKeyboardButton("Adyen", callback_data="auth_adyen"),
            InlineKeyboardButton("Square", callback_data="auth_square")
        ],
        [
            InlineKeyboardButton("Back", callback_data="gates")
        ]
    ])
    return text, buttons

def get_charge_submenu():
    """Get charge submenu (Stripe, Braintree, Shopify) - EXACTLY as in start.py"""
    text = """<pre>#WAYNE 〔Charge Gates〕</pre>
━━━━━━━━━━━━━
<b>Available Charge Gate Types:</b>

⟐ <b>Stripe Charge</b>
⟐ <b>Braintree Charge</b>
⟐ <b>Shopify Charge</b>

━━━━━━━━━━━━━
<b>~ Note:</b> <code>Click on a gateway to see available commands</code>
<b>~ Note:</b> <code>Disabled commands show ❌ status</code>"""

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Stripe", callback_data="charge_stripe"),
            InlineKeyboardButton("Braintree", callback_data="charge_braintree")
        ],
        [
            InlineKeyboardButton("Shopify", callback_data="charge_shopify"),
            InlineKeyboardButton("Back", callback_data="gates")
        ]
    ])
    return text, buttons

def generate_commands_display(config_name):
    """Generate formatted display for commands with dynamic status"""
    config = get_dynamic_config(config_name)
    if not config:
        return "<pre>❌ Configuration not found</pre>"

    text = f"{config['title']}\n{config['description']}\n"

    for idx, cmd in enumerate(config["commands"], 1):
        # Get actual command status
        command_key = cmd.get("command_key", "")
        if command_key:
            status = get_command_status(command_key)
        else:
            status = cmd.get("status", "Active ✅")

        text += f"\n⟐ <b>Name</b>: <code>{cmd['name']}</code>\n"
        text += f"⟐ <b>Command</b>: <code>{cmd['command']}</code>\n"
        text += f"⟐ <b>Status</b>: <code>{status}</code>\n"

        if cmd.get('note'):
            text += f"⟐ <b>Note</b>: <code>{cmd['note']}</code>\n"

        if idx < len(config["commands"]):
            text += f"{config['description']}\n"

    # Add footer with status explanation
    text += f"\n{config['description']}\n"
    text += "<b>~ Status Legend:</b>\n"
    text += "⟐ <code>Active ✅</code> - Command is available\n"
    text += "⟐ <code>Disabled ❌</code> - Command is temporarily disabled\n"
    text += "⟐ <code>Coming Soon ⏳</code> - Feature in development\n"

    return text

def get_stripe_auth_menu():
    """Get Stripe Auth commands menu with dynamic status"""
    text = generate_commands_display("stripe_auth")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Back", callback_data="gates_auth"),
         InlineKeyboardButton("Close", callback_data="exit")]
    ])
    return text, buttons

def get_braintree_auth_menu():
    """Get Braintree Auth commands menu with dynamic status"""
    text = generate_commands_display("braintree_auth")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Back", callback_data="gates_auth"),
         InlineKeyboardButton("Close", callback_data="exit")]
    ])
    return text, buttons

def get_adyen_auth_menu():
    """Get Adyen Auth commands menu with dynamic status"""
    text = generate_commands_display("adyen_auth")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Back", callback_data="gates_auth"),
         InlineKeyboardButton("Close", callback_data="exit")]
    ])
    return text, buttons

def get_square_auth_menu():
    """Get Square Auth commands menu with dynamic status"""
    text = generate_commands_display("square_auth")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Back", callback_data="gates_auth"),
         InlineKeyboardButton("Close", callback_data="exit")]
    ])
    return text, buttons

def get_stripe_charge_menu():
    """Get Stripe Charge commands menu with dynamic status - UPDATED with all 5 commands"""
    text = generate_commands_display("stripe_charge")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Back", callback_data="gates_charge"),
         InlineKeyboardButton("Close", callback_data="exit")]
    ])
    return text, buttons

def get_braintree_charge_menu():
    """Get Braintree Charge commands menu with dynamic status"""
    text = generate_commands_display("braintree_charge")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Back", callback_data="gates_charge"),
         InlineKeyboardButton("Close", callback_data="exit")]
    ])
    return text, buttons

def get_shopify_charge_menu():
    """Get Shopify Charge commands menu with dynamic status"""
    text = generate_commands_display("shopify_charge")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Back", callback_data="gates_charge"),
         InlineKeyboardButton("Close", callback_data="exit")]
    ])
    return text, buttons

def get_mass_commands_menu():
    """Get all Mass commands menu with dynamic status"""
    text = generate_commands_display("mass")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Back", callback_data="gates"),
         InlineKeyboardButton("Close", callback_data="exit")]
    ])
    return text, buttons

# ==================== MENU MAPPING FOR EASY ACCESS ====================

GATES_MENUS = {
    # Main gates menu
    "gates": get_gates_main_menu,

    # Auth submenus
    "gates_auth": get_auth_submenu,
    "auth_stripe": get_stripe_auth_menu,
    "auth_braintree": get_braintree_auth_menu,
    "auth_adyen": get_adyen_auth_menu,
    "auth_square": get_square_auth_menu,  # ADDED

    # Charge submenus
    "gates_charge": get_charge_submenu,
    "charge_stripe": get_stripe_charge_menu,
    "charge_braintree": get_braintree_charge_menu,
    "charge_shopify": get_shopify_charge_menu,

    # Mass commands
    "gates_mass": get_mass_commands_menu,
}
