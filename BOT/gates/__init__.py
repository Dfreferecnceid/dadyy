# gates/__init__.py
# Gate modules initialization

import importlib
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def register_gate_handlers(bot):
    """Register all gate command handlers with the bot"""
    
    gate_modules = [
        # Auth gates
        ("auth.stripe", ["au", "mau"]),
        ("auth.braintree", ["bu"]),
        ("auth.adyen", ["ad"]),
        
        # Charge gates
        ("charge.stripe", ["xx", "xo", "xs", "xc", "xp"]),
        ("charge.braintree", ["bt"]),
        ("charge.shopify", ["sh", "slf"]),
        
        # Mass gates
        ("mass", ["mau", "mchk", "mxc", "mxp", "mxx"])
    ]
    
    registered_commands = []
    
    for module_path, commands in gate_modules:
        try:
            # Import the module
            module = importlib.import_module(f"gates.{module_path}")
            
            # Check if module has a register function
            if hasattr(module, 'register_handlers'):
                module.register_handlers(bot)
                print(f"✅ Registered handlers from gates.{module_path}")
            else:
                print(f"⚠️ Module gates.{module_path} has no register_handlers function")
                
            registered_commands.extend(commands)
            
        except ImportError as e:
            print(f"⚠️ Could not import gates.{module_path}: {e}")
        except Exception as e:
            print(f"❌ Error registering gates.{module_path}: {e}")
    
    # Remove duplicates
    registered_commands = list(set(registered_commands))
    
    print(f"✅ Total gate commands registered: {len(registered_commands)}")
    print(f"✅ Commands: {', '.join(sorted(registered_commands))}")
    
    return registered_commands