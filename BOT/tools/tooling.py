# BOT/tools/tooling.py

import datetime
import asyncio
import os
import stripe
import requests
import random
import logging
import cloudscraper
import time
import ssl
import socket
from pyrogram import Client, filters
from pyrogram.types import Message
import html
import json
import pytz
import re
from urllib.parse import urlparse, urlunparse, urljoin
import urllib.parse
import urllib3
from concurrent.futures import ThreadPoolExecutor

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import disabled commands functions from Admins module
from ..helper.Admins import (
    is_command_disabled, get_command_offline_message,
    is_user_restricted_for_command
)

# Import the new auth_and_free_restricted decorator
from ..helper.permissions import auth_and_free_restricted

# Initialize logging
logger = logging.getLogger(__name__)

# Global thread pool for concurrent requests
gate_thread_pool = ThreadPoolExecutor(max_workers=20)

# Function to get IST time
def get_ist_time():
    ist = pytz.timezone("Asia/Kolkata")
    return datetime.datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")

def clean_text(text):
    if not text:
        return "N/A"
    return html.unescape(text)

def get_message_text(message: Message):
    """Helper function to get text from message"""
    if hasattr(message, 'text'):
        return message.text
    return ''

def luhn_checksum(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10

def generate_luhn_compliant_cc(bin):
    cc_number = bin + ''.join(random.choices("0123456789", k=15 - len(bin)))
    check_digit = (10 - luhn_checksum(cc_number + '0')) % 10
    return cc_number + str(check_digit)

def replace_x_with_digits(input_str):
    result = []
    for char in input_str:
        if char == 'x':
            result.append(random.choice("0123456789"))
        else:
            result.append(char)
    return ''.join(result)

def fetch_bin_details(bin):
    url = f"https://binlist.io/lookup/{bin}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        bin_data = response.json()
        return bin_data
    except Exception as e:
        return None

# Country code mappings
COUNTRY_NAME_TO_CODE = {
    "united states": "en_US",
    "usa": "en_US", 
    "us": "en_US",
    "canada": "en_CA",
    "ca": "en_CA",
    "united kingdom": "en_GB",
    "uk": "en_GB",
    "gb": "en_GB",
    "germany": "de_DE",
    "de": "de_DE",
    "france": "fr_FR",
    "fr": "fr_FR",
    "italy": "it_IT",
    "it": "it_IT",
    "spain": "es_ES",
    "es": "es_ES",
    "australia": "en_AU",
    "au": "en_AU",
    "japan": "ja_JP",
    "jp": "ja_JP",
    "china": "zh_CN",
    "cn": "zh_CN",
    "india": "en_IN",
    "in": "en_IN",
    "brazil": "pt_BR",
    "br": "pt_BR",
    "mexico": "es_MX",
    "mx": "es_MX"
}

CODE_TO_COUNTRY_NAME = {
    "en_US": "United States",
    "en_CA": "Canada",
    "en_GB": "United Kingdom",
    "de_DE": "Germany",
    "fr_FR": "France",
    "it_IT": "Italy",
    "es_ES": "Spain",
    "en_AU": "Australia",
    "ja_JP": "Japan",
    "zh_CN": "China",
    "en_IN": "India",
    "pt_BR": "Brazil",
    "es_MX": "Mexico"
}

def get_country_code(country_input):
    country_input = country_input.lower()
    if country_input in COUNTRY_NAME_TO_CODE:
        return COUNTRY_NAME_TO_CODE[country_input]
    elif country_input in CODE_TO_COUNTRY_NAME:
        return country_input
    else:
        return None

def get_country_name(country_code):
    return CODE_TO_COUNTRY_NAME.get(country_code, "Unknown")

def parse_country_input(input_str):
    match = re.match(r"^\s*(\w+)\s*(?:\(([^)]+)\))?\s*$", input_str, re.IGNORECASE)
    if match:
        code_or_name = match.group(1).strip()
        full_name = match.group(2).strip() if match.group(2) else None
        return code_or_name, full_name
    return None, None

def fetch_fake_address(country_code):
    try:
        from faker import Faker
        fake = Faker(country_code)
        name = fake.name()

        # Enhanced address generation with proper city-state-postcode matching
        country_configs = {
            'en_US': {
                'street_format': lambda: f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Pine', 'Elm', 'Maple', 'Cedar', 'Washington', 'Lincoln', 'Park', 'First'])} {random.choice(['St', 'Ave', 'Blvd', 'Dr', 'Rd', 'Ln'])}",
                'state_city_postcode': lambda: random.choice([
                    ('CA', 'Los Angeles', '90001'), ('CA', 'San Francisco', '94102'), ('CA', 'San Diego', '92101'),
                    ('NY', 'New York', '10001'), ('NY', 'Buffalo', '14201'), ('NY', 'Rochester', '14602'),
                    ('TX', 'Houston', '77001'), ('TX', 'Dallas', '75201'), ('TX', 'Austin', '73301'),
                    ('FL', 'Miami', '33101'), ('FL', 'Orlando', '32801'), ('FL', 'Tampa', '33601'),
                    ('IL', 'Chicago', '60601'), ('IL', 'Springfield', '62701'), ('IL', 'Peoria', '61601'),
                    ('PA', 'Philadelphia', '19101'), ('PA', 'Pittsburgh', '15201'), ('PA', 'Harrisburg', '17101'),
                    ('OH', 'Columbus', '43201'), ('OH', 'Cleveland', '44101'), ('OH', 'Cincinnati', '45201'),
                    ('GA', 'Atlanta', '30301'), ('GA', 'Savannah', '31401'), ('GA', 'Augusta', '30901'),
                    ('NC', 'Charlotte', '28201'), ('NC', 'Raleigh', '27601'), ('NC', 'Greensboro', '27401'),
                    ('MI', 'Detroit', '48201'), ('MI', 'Grand Rapids', '49501'), ('MI', 'Lansing', '48901')
                ]),
                'phone': lambda: f"+1 ({random.randint(200, 999)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}"
            },
            'en_GB': {
                'street_format': lambda: f"{random.randint(1, 999)} {random.choice(['High', 'Station', 'Church', 'Victoria', 'King', 'Queen', 'London', 'Park'])} {random.choice(['Street', 'Road', 'Lane', 'Avenue', 'Close', 'Drive'])}",
                'state_city_postcode': lambda: random.choice([
                    ('England', 'London', 'SW1A 1AA'), ('England', 'Manchester', 'M1 1AA'), ('England', 'Birmingham', 'B1 1AA'),
                    ('England', 'Liverpool', 'L1 1AA'), ('England', 'Leeds', 'LS1 1AA'), ('England', 'Sheffield', 'S1 1AA'),
                    ('Scotland', 'Edinburgh', 'EH1 1AA'), ('Scotland', 'Glasgow', 'G1 1AA'), ('Scotland', 'Aberdeen', 'AB1 1AA'),
                    ('Wales', 'Cardiff', 'CF10 1AA'), ('Wales', 'Swansea', 'SA1 1AA'), ('Wales', 'Newport', 'NP10 1AA'),
                    ('Northern Ireland', 'Belfast', 'BT1 1AA'), ('Northern Ireland', 'Derry', 'BT48 1AA')
                ]),
                'phone': lambda: f"+44 {random.randint(1, 9)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}"
            },
            'en_CA': {
                'street_format': lambda: f"{random.randint(100, 9999)} {random.choice(['Main', 'King', 'Queen', 'Yonge', 'Bay', 'College', 'Dundas', 'Bloor'])} {random.choice(['St', 'Ave', 'Rd', 'Blvd', 'Dr'])}",
                'state_city_postcode': lambda: random.choice([
                    ('ON', 'Toronto', 'M5A 1A1'), ('ON', 'Ottawa', 'K1A 0A1'), ('ON', 'Hamilton', 'L8P 1A1'),
                    ('QC', 'Montreal', 'H2X 1A1'), ('QC', 'Quebec City', 'G1R 1A1'), ('QC', 'Laval', 'H7X 1A1'),
                    ('BC', 'Vancouver', 'V6A 1A1'), ('BC', 'Victoria', 'V8W 1A1'), ('BC', 'Surrey', 'V3R 1A1'),
                    ('AB', 'Calgary', 'T2P 1A1'), ('AB', 'Edmonton', 'T5J 1A1'), ('AB', 'Red Deer', 'T4N 1A1'),
                    ('MB', 'Winnipeg', 'R3C 1A1'), ('MB', 'Brandon', 'R7A 1A1')
                ]),
                'phone': lambda: f"+1 ({random.randint(200, 999)}) {random.randint(200, 999)}-{random.randint(1000, 9999)}"
            },
            'de_DE': {
                'street_format': lambda: f"{random.choice(['Hauptstraße', 'Berliner Straße', 'Münchner Straße', 'Frankfurter Allee', 'Hamburger Straße', 'Kölner Straße'])} {random.randint(1, 999)}",
                'state_city_postcode': lambda: random.choice([
                    ('Berlin', 'Berlin', '10115'), ('Hamburg', 'Hamburg', '20095'), ('Bavaria', 'Munich', '80331'),
                    ('Bavaria', 'Nuremberg', '90402'), ('North Rhine-Westphalia', 'Cologne', '50667'),
                    ('North Rhine-Westphalia', 'Düsseldorf', '40213'), ('Hesse', 'Frankfurt', '60311'),
                    ('Hesse', 'Wiesbaden', '65183'), ('Baden-Württemberg', 'Stuttgart', '70173'),
                    ('Baden-Württemberg', 'Karlsruhe', '76131'), ('Lower Saxony', 'Hanover', '30159')
                ]),
                'phone': lambda: f"+49 {random.randint(30, 89)} {random.randint(1000000, 9999999)}"
            }
        }

        if country_code in country_configs:
            config = country_configs[country_code]
            street = config['street_format']()
            state, city, postcode = config['state_city_postcode']()
            phone = config['phone']()
        else:
            # Fallback for other countries
            fake = Faker(country_code)
            street = fake.street_address()
            city = fake.city()
            state = fake.state()
            postcode = fake.postcode()
            phone = fake.phone_number()

        country = CODE_TO_COUNTRY_NAME.get(country_code, "Unknown")

        return name, street, city, state, postcode, phone, country
    except Exception as e:
        logger.error(f"Error generating fake address: {e}")
        # Fallback to US address
        from faker import Faker
        fake = Faker('en_US')
        name = fake.name()
        street = f"{random.randint(100,9999)} {random.choice(['Main St', 'Oak Ave', 'First St', 'Park Ave'])}"
        city = fake.city()
        state = fake.state()
        postcode = fake.postcode()
        phone = f"+1 ({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}"
        country = "United States"
        return name, street, city, state, postcode, phone, country

def normalize_url(url):
    """Normalize URL by removing path and query parameters and adding scheme if missing"""
    from urllib.parse import urlparse, urlunparse
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    parsed = urlparse(url)
    normalized = parsed._replace(path='', params='', query='', fragment='')
    return urlunparse(normalized)

def get_ip_address(domain):
    """Get IP address of domain"""
    try:
        return socket.gethostbyname(domain)
    except:
        return "N/A"

# Load users from JSON file (same as start.py)
def load_users():
    USERS_FILE = "DATA/users.json"
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Check if user is registered
def is_user_registered(user_id):
    users = load_users()
    return str(user_id) in users

# Get user's role
def get_user_role(user_id):
    users = load_users()
    user_data = users.get(str(user_id), {})
    return user_data.get("role", "Free")

# ============ TOOL COMMANDS ============

@Client.on_message(filters.command("status"))
@auth_and_free_restricted
async def status_command(client, message):
    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    user_id = message.from_user.id

    if not is_user_registered(user_id):
        await message.reply("<pre>🔒 You need to register first! Use /register command.</pre>")
        return

    users = load_users()
    user_id_str = str(user_id)
    user_data = users[user_id_str]

    username = message.from_user.username or "None"
    join_date = user_data.get("registered_at", "Unknown")
    plan_data = user_data.get("plan", {})
    plan_name = plan_data.get("plan", "Free")
    credits = plan_data.get("credits", "N/A")
    badge = plan_data.get("badge", "🧿")
    antispam = plan_data.get("antispam", "N/A")
    mlimit = plan_data.get("mlimit", "N/A")

    response = f"""
<pre>#WAYNE 〔User Status〕</pre>
━━━━━━━━━━━━━
⟐ <b>UserID</b>: <code>{user_id}</code>
⟐ <b>Username</b>: @{username}
⟐ <b>Plan</b>: <code>{plan_name} {badge}</code>
⟐ <b>Credits</b>: <code>{credits}</code>
⟐ <b>Anti-Spam</b>: <code>{antispam}s</code>
⟐ <b>Message Limit</b>: <code>{mlimit}</code>
⟐ <b>Joined</b>: <code>{join_date}</code>
━━━━━━━━━━━━━
<pre>Status Check Complete ✔</pre>"""

    await message.reply(response)

@Client.on_message(filters.command("fake"))
@auth_and_free_restricted
async def fake_command(client, message):
    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    user_id = message.from_user.id

    if not is_user_registered(user_id):
        await message.reply("<pre>🔒 You need to register first! Use /register command.</pre>")
        return

    text = get_message_text(message)
    args = text.split()
    if len(args) < 2:
        await message.reply("""
<pre>#WAYNE 〔/fake〕</pre>
━━━━━━━━━━━━━
<pre>Format: /fake {country}</pre>
<pre>Example: /fake us</pre>
<pre>Example: /fake united states</pre>
━━━━━━━━━━━━━
<pre>Supported Countries:</pre>
<code>US, UK, CA, DE, FR, IT, ES, AU, JP, CN, IN, BR, MX</code>
━━━━━━━━━━━━━""")
        return

    country_input = ' '.join(args[1:]).strip()
    code_or_name, full_name = parse_country_input(country_input)

    if full_name:
        country_code = get_country_code(full_name)
    else:
        country_code = get_country_code(code_or_name)

    if not country_code:
        await message.reply(f"<pre>❌ Invalid country: {country_input}</pre>\n<pre>Please provide a valid country code or name.</pre>")
        return

    name, street, city, state, postcode, phone, country = fetch_fake_address(country_code)

    if name and street:
        response = f"""<b>Random Address Generator</b>

<b>-</b> <b>Name</b>: <code>{name}</code>
<b>-</b> <b>Street Address</b>: <code>{street}</code>
<b>-</b> <b>City</b>: <code>{city}</code>
<b>-</b> <b>State/Province</b>: <code>{state}</code>
<b>-</b> <b>Postal Code</b>: <code>{postcode}</code>
<b>-</b> <b>Phone Number</b>: <code>{phone}</code>
<b>-</b> <b>Country</b>: <code>{country}</code>"""
        await message.reply(response)
    else:
        await message.reply(f"<pre>❌ Failed to generate address for: {country_input}</pre>")

@Client.on_message(filters.command("gen"))
@auth_and_free_restricted
async def gen_command(client, message):
    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    user_id = message.from_user.id

    if not is_user_registered(user_id):
        await message.reply("<pre>🔒 You need to register first! Use /register command.</pre>")
        return

    text = get_message_text(message)
    args = text.split()

    if len(args) < 2 or args[0].lower() in ['/gen', '.gen'] and len(args) == 1:
        await message.reply("""
<pre>#WAYNE 〔/gen〕</pre>
━━━━━━━━━━━━━
<pre>Format 1: /gen {BIN} {amount}</pre>
<pre>Format 2: /gen {cc|mm|yy|cvv} {amount}</pre>
━━━━━━━━━━━━━
<pre>Examples:</pre>
<code>/gen 411111 10</code>
<code>/gen 411111|12|2025|123 5</code>
━━━━━━━━━━━━━
<pre>Max Limit: 500 cards</pre>
<pre>BIN must be at least 6 digits</pre>
━━━━━━━━━━━━━""")
        return

    input_data = args[1]
    amount = 10
    if len(args) > 2:
        try:
            amount = int(args[2])
            if amount < 1:
                await message.reply("<pre>❌ Amount must be greater than 0.</pre>")
                return
            if amount > 500:
                await message.reply("<pre>❌ Maximum amount is 500.</pre>")
                return
        except ValueError:
            await message.reply("<pre>❌ Invalid amount. Please provide a valid number.</pre>")
            return

    if '|' in input_data:
        parts = input_data.split('|')
        cc = parts[0]
        mes = parts[1]
        ano = parts[2]
        cvv = parts[3]
    else:
        cc = input_data
        mes = 'x'
        ano = 'x'
        cvv = 'x'

    if 'x' in cc:
        await message.reply("""
<pre>❌ Invalid format. 'x' not allowed in CC.</pre>
━━━━━━━━━━━━━
<pre>Correct Formats:</pre>
<code>/gen {cc|mon|year|cvv} {amount}</code>
<code>/gen {BIN} {amount}</code>
━━━━━━━━━━━━━
<pre>Examples:</pre>
<code>/gen 123456|12|2025|123 10</code>
<code>/gen 123456 5</code>
━━━━━━━━━━━━━""")
        return

    if not cc[:5].isdigit():
        await message.reply("<pre>❌ CC must start with at least 5 digits.</pre>")
        return

    try:
        ccs = []
        for _ in range(amount):
            if cc.isdigit() and len(cc) >= 5:
                ccgen = generate_luhn_compliant_cc(cc[:6])
            else:
                ccgen = generate_luhn_compliant_cc(''.join(random.choices("0123456789", k=6)))

            mesgen = f"{random.randint(1, 12):02d}" if mes in ('x', 'xx') else mes
            anogen = random.randint(2025, 2035) if ano in ('x', 'xxxx') else ano
            cvvgen = f"{random.randint(100, 999):03d}" if cvv in ('x', 'xxx') else cvv
            ccs.append(f"{ccgen}|{mesgen}|{anogen}|{cvvgen}")

        bin_details = None
        if cc.isdigit() and len(cc) >= 6:
            bin_number = cc[:6]
            bin_details = fetch_bin_details(bin_number)

        if amount > 10:
            file_name = f"ccs_{user_id}.txt"
            with open(file_name, 'w') as f:
                for cc in ccs:
                    f.write(cc + "\n")

            await message.reply("<pre>✅ CCs generated successfully! Sending file...</pre>")
            await client.send_document(
                message.chat.id,
                file_name,
                caption=f"<pre>Generated {amount} CCs</pre>"
            )
            os.remove(file_name)
        else:
            response = f"""
<pre>#WAYNE 〔/gen〕</pre>
━━━━━━━━━━━━━
<pre>Amount: {amount} cards</pre>"""

            if cc.isdigit() and len(cc) >= 6:
                response += f"\n<pre>BIN: {cc[:6]}</pre>\n"

            for cc_data in ccs:
                response += f"<code>{cc_data}</code>\n"

            if bin_details and "scheme" in bin_details:
                scheme = bin_details.get("scheme", "Unknown")
                type = bin_details.get("type", "Unknown")
                brand = bin_details.get("brand", "Unknown")
                bank = bin_details.get("bank", {}).get("name", "Unknown")
                country = bin_details.get("country", {}).get("name", "Unknown")
                emoji = bin_details.get("country", {}).get("emoji", "")

                response += f"""
━━━━━━━━━━━━━
<pre>Card: {scheme} - {type} - {brand}</pre>
<pre>Bank: {bank}</pre>
<pre>Country: {country} {emoji}</pre>
━━━━━━━━━━━━━"""

            await message.reply(response)
    except Exception as e:
        await message.reply(f"<pre>❌ Failed to generate CCs. Error: {str(e)}</pre>")

@Client.on_message(filters.command("bin"))
@auth_and_free_restricted
async def bin_command(client, message):
    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    user_id = message.from_user.id

    if not is_user_registered(user_id):
        await message.reply("<pre>🔒 You need to register first! Use /register command.</pre>")
        return

    text = get_message_text(message)
    bin_input = text.replace('/bin', '').replace('.bin', '').strip()

    if not bin_input:
        await message.reply("""
<pre>#WAYNE 〔/bin〕</pre>
━━━━━━━━━━━━━
<pre>Format: /bin {BIN}</pre>
<pre>Example: /bin 411111</pre>
<pre>Example: /bin 411111|12|2025|123</pre>
<pre>Alias: .bin</pre>
━━━━━━━━━━━━━
<pre>Supports BIN or Full CC</pre>
━━━━━━━━━━━━━""")
        return

    try:
        if '|' in bin_input:
            bin_number = bin_input.split('|')[0][:6]
        else:
            bin_number = bin_input[:6]

        if len(bin_number) != 6 or not bin_number.isdigit():
            await message.reply("<pre>❌ Invalid BIN. Please provide a 6-digit BIN or card details.</pre>")
            return

        url = f"https://binlist.io/lookup/{bin_number}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        bin_data = response.json()

        if not bin_data or "scheme" not in bin_data:
            await message.reply(f"<pre>❌ No information found for BIN: {bin_number}</pre>")
            return

        scheme = bin_data.get("scheme", "None")
        type = bin_data.get("type", "None")
        brand = bin_data.get("brand", "None")
        country = bin_data.get("country", {}).get("name", "None")
        emoji = bin_data.get("country", {}).get("emoji", "None")
        bank = bin_data.get("bank", {}).get("name", "None")
        bank_url = bin_data.get("bank", {}).get("url", "None")
        bank_phone = bin_data.get("bank", {}).get("phone", "None")

        response_message = f"""<b>BIN INFO</b>
<b>BIN</b>: <code>{bin_number}</code>
<b>Brand</b>: <code>{scheme} ({brand})</code>
<b>Type</b>: <code>{type}</code>
<b>Bank Name</b>: <code>{bank}</code>
<b>Bank Url</b>: <code>{bank_url}</code>
<b>Bank Phone</b>: <code>{bank_phone}</code>
<pre>────────────────────</pre>
<b>Country</b>: <code>{country} {emoji}</code>"""

        await message.reply(response_message)
    except requests.exceptions.RequestException as e:
        await message.reply(f"<pre>❌ Failed to fetch BIN details. Error: {str(e)}</pre>")
    except ValueError as e:
        await message.reply(f"<pre>❌ Failed to parse BIN details. Error: {str(e)}</pre>")

@Client.on_message(filters.command("sk"))
@auth_and_free_restricted
async def sk_command(client, message):
    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    user_id = message.from_user.id

    if not is_user_registered(user_id):
        await message.reply("<pre>🔒 You need to register first! Use /register command.</pre>")
        return

    text = get_message_text(message)
    sk_key = text.replace('/sk', '').replace('.sk', '').strip()

    if not sk_key:
        await message.reply("""
<pre>#WAYNE 〔/sk〕</pre>
━━━━━━━━━━━━━
<pre>Format: /sk {stripe_secret_key}</pre>
<pre>Example: /sk sk_live_1234567890abcdef</pre>
<pre>Alias: .sk</pre>
━━━━━━━━━━━━━
<pre>Checks Stripe secret key validity</pre>
━━━━━━━━━━━━━""")
        return

    try:
        stripe.api_key = sk_key
        account = stripe.Account.retrieve()
        balance = stripe.Balance.retrieve()

        country = account.get("country", "N/A")
        currency = account.get("default_currency", "N/A")
        display_name = account.get("settings", {}).get("dashboard", {}).get("display_name", "N/A")
        email = account.get("email", "N/A")
        phone = account.get("business_profile", {}).get("phone", "N/A")
        url = account.get("business_profile", {}).get("url", "N/A")
        card_payments = account.get("capabilities", {}).get("card_payments", "N/A")
        charges_enabled = account.get("charges_enabled", "N/A")

        # Get balance information safely
        available_balance = 0
        pending_balance = 0
        available_currency = currency

        if balance.get("available"):
            for avail in balance["available"]:
                if avail.get("amount"):
                    available_balance = avail.get("amount", 0)
                    available_currency = avail.get("currency", currency)
                    break

        if balance.get("pending"):
            for pend in balance["pending"]:
                if pend.get("amount"):
                    pending_balance = pend.get("amount", 0)
                    break

        username = f"@{message.from_user.username}" if message.from_user.username else f"tg://openmessage?user_id={user_id}"
        user_mention = f"{username}"

        response = f"""<b>𝐒𝐊 𝐂𝐡𝐞𝐜𝐤𝐞𝐫</b>
<pre>━━━━━━━━━━━━━━</pre>

<b>𝐒𝐭𝐚𝐭𝐮𝐬</b> : <b>𝐋𝐈𝐕𝐄 ✅</b>

<b>𝐊𝐞𝐲</b> : <code>{sk_key}</code>

<b>𝐂𝐨𝐮𝐧𝐭𝐫𝐲</b> : <code>{country}</code>
<b>𝐂𝐮𝐫𝐫𝐞𝐧𝐜𝐲</b> : <code>{currency}</code>

<b>𝐃𝐢𝐬𝐩𝐥𝐚𝐲 𝐍𝐚𝐦𝐞</b> : <code>{display_name}</code>
<b>𝐄𝐦𝐚𝐢𝐥</b> : <code>{email}</code>
<b>𝐏𝐡𝐨𝐧𝐞</b> : <code>{phone}</code>
<b>𝐔𝐑𝐋</b>: <code>{url}</code>
<b>𝐂𝐚𝐫𝐝 𝐏𝐚𝐲𝐦𝐞𝐧𝐭𝐬</b> : <code>{card_payments}</code>
<b>𝐂𝐡𝐚𝐫𝐠𝐞 𝐄𝐧𝐚𝐛𝐥𝐞𝐝</b> : <code>{charges_enabled}</code>

<b>𝐁𝐚𝐥𝐚𝐧𝐜𝐞 𝐈𝐧𝐟𝐨</b>
<pre>━━━━━━━━━━━━━━</pre>
<b>𝐀𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞 𝐁𝐚𝐥𝐚𝐧𝐜𝐞</b> : <code>{available_balance}</code>
<b>𝐏𝐞𝐧𝐝𝐢𝐧𝐠 𝐁𝐚𝐥𝐚𝐧𝐜𝐞</b> : <code>{pending_balance}</code>
<pre>━━━━━━━━━━━━━━</pre> 

<b>𝐑𝐞𝐪𝐮𝐞𝐬𝐭𝐞𝐝 𝐛𝐲</b> : {user_mention}"""

        await message.reply(response)

    except stripe.error.AuthenticationError:
        username = f"@{message.from_user.username}" if message.from_user.username else f"tg://openmessage?user_id={user_id}"
        user_mention = f"{username}"

        response = f"""<b>𝐒𝐊 𝐂𝐡𝐞𝐜𝐤𝐞𝐫</b>
<pre>━━━━━━━━━━━━━━</pre>

<b>𝐒𝐭𝐚𝐭𝐮𝐬</b> : <b>𝐃𝐄𝐀𝐃 ❌</b>

<b>𝐊𝐞𝐲</b> : <code>{sk_key[:20]}...</code>

<b>𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞</b> : <code>401 Authentication Error</code>

<b>𝐌𝐞𝐬𝐬𝐚𝐠𝐞</b> : <code>Key is invalid or revoked</code>
<pre>━━━━━━━━━━━━━━</pre>

<b>𝐑𝐞𝐪𝐮𝐞𝐬𝐭𝐞𝐝 𝐛𝐲</b> : {user_mention}"""
        await message.reply(response)

    except Exception as e:
        await message.reply(f"<pre>❌ Failed to validate Stripe Key</pre>\n<pre>Error: {str(e)}</pre>")

# Website scanning functions
def find_payment_gateways_comprehensive(response_text, url):
    """ENHANCED payment gateway detection with comprehensive patterns"""
    detected_gateways = set()
    text_lower = response_text.lower()

    gateway_patterns = {
        "PayPal": [
            r'paypal', r'www\.paypal\.com', r'paypalobjects\.com',
            r'paypal\.js', r'paypal\.min\.js', r'paypal\.com/sdk/js',
            r'paypal\.com/checkoutnow', r'paypal\.com/webapps/hermes',
            r'paypal\.com/buttons', r'paypal\.com/digital',
            r'braintree\.paypal', r'paypal\.com/checkout',
            r'data-paypal', r'paypal-button', r'paypal-checkout'
        ],
        "Stripe": [
            r'stripe', r'js\.stripe\.com', r'api\.stripe\.com',
            r'stripe\.js', r'stripe\.min\.js', r'stripe\.com/v3/',
            r'Stripe\(', r'stripePaymentIntent', r'stripe\.com/elements',
            r'stripe\.com/checkout', r'stripe\.com/payments',
            r'stripe\.com/connect', r'stripe\.com/terminal',
            r'data-stripe', r'data-stripe-key', r'stripe-key',
            r'stripeToken', r'stripeSource', r'stripeCustomerId'
        ],
        "Braintree": [
            r'braintree', r'braintreegateway\.com', r'braintree\.js',
            r'braintree-client\.js', r'braintree-data-collector\.js',
            r'braintree\.min\.js', r'Braintree\.Client',
            r'braintree\.com/web', r'braintree\.com/api', r'braintree\.com/sdk',
            r'braintree\.com/visa', r'braintree\.paypal',
            r'data-braintree', r'braintree-hosted-fields'
        ],
        "Klarna": [
            r'klarna', r'klarnapayments\.com', r'klarna\.js',
            r'klarna\.min\.js', r'klarna\.com', r'klarna-widget',
            r'klarna\.payments', r'klarna\.checkout', r'klarna\.api',
            r'data-klarna', r'klarna-payment'
        ],
        "Square": [
            r'square', r'squareup\.com', r'square\.js',
            r'sq-payment-form', r'square\.min\.js',
            r'square\.com/payments', r'SqPaymentForm', r'square\.com/sdk/js', r'square\.com/online',
            r'square\.com/checkout', r'square\.com/pos',
            r'data-square', r'square-payment', r'square-wallet'
        ],
        "Authorize.Net": [
            r'authorize\.net', r'authorizenet', r'accept\.js',
            r'authorize\.min\.js', r'authorize\.net/Accept\.js',
            r'authorize\.net/v1/Accept\.js', r'Accept\.dispatch',
            r'authorize\.net/api', r'authorize\.net/xml',
            r'data-authorize', r'authorize-net', r'acceptjs'
        ],
        "2Checkout": [
            r'2checkout', r'2co\.com', r'2checkout\.com',
            r'2co\.js', r'2checkout\.min\.js',
            r'2checkout\.com/checkout/api', r'2checkout\.com/inline', r'2checkout\.com/payment',
            r'data-2checkout', r'twocheckout', r'2co-button'
        ],
        "Adyen": [
            r'adyen', r'adyen\.com', r'adyen\.js',
            r'adyen\.min\.js', r'adyen-component', r'adyen-checkout',
            r'data-adyen', r'adyen-payment'
        ],
        "Worldpay": [
            r'worldpay', r'worldpay\.com', r'worldpay\.js',
            r'worldpay\.min\.js', r'worldpay-form', r'worldpay-payment',
            r'data-worldpay', r'worldpay-button'
        ],
        "SagePay": [
            r'sagepay', r'sagepay\.com', r'sagepay\.js',
            r'sagepay\.min\.js', r'sagepay-form', r'sagepay-payment',
            r'data-sagepay', r'sagepay-button'
        ],
        "Amazon Pay": [
            r'amazon pay', r'pay\.amazon\.com', r'amazonpay\.js',
            r'amazonpay\.min\.js', r'amazonpay\.com', r'amazon-addressbook',
            r'amazon\.payments', r'amazon\.checkout',
            r'amazon\.login', r'amazon\.payment',
            r'data-amazon-pay', r'amazon-pay-button'
        ],
        "Apple Pay": [
            r'apple pay', r'apple-pay', r'applepay\.js',
            r'ApplePaySession', r'applepay\.min\.js', r'applepay\.com',
            r'apple\.pay', r'apple\.payment', r'apple\.wallet',
            r'data-apple-pay', r'apple-pay-button'
        ],
        "Google Pay": [
            r'google pay', r'gpaysdk', r'googlepay\.js',
            r'google\.pay', r'googlepay\.min\.js', r'pay\.google\.com',
            r'google\.wallet', r'google\.payment', r'googlepay\.api',
            r'data-google-pay', r'google-pay-button'
        ],
        "Venmo": [
            r'venmo', r'venmo\.com', r'venmo-button',
            r'venmo-payment', r'data-venmo'
        ],
        "Chase": [
            r'chase', r'chase\.com', r'chasepay',
            r'chase\.min\.js', r'chase\.com/payments',
            r'chase\.com/checkout', r'chase\.pay', r'chase\.bank',
            r'data-chase', r'chase-payment'
        ],
        "Cash on Delivery (COD)": [
            r'cash on delivery', r'cod', r'payment_method_cod',
            r'payment-method-cod', r'cod_payment', r'cod\.method',
            r'cash\.delivery', r'pay\.on\.delivery',
            r'data-cod', r'cod-button'
        ],
        "AWS": [
            r'aws', r'amazon web services', r'aws\.payment',
            r'aws\.billing', r'aws\.checkout', r'aws\.gateway',
            r'data-aws', r'aws-payment'
        ],
        "NAB": [
            r'nab', r'national australia bank', r'nab\.com\.au',
            r'nabtransact', r'nab\.co\.nz', r'nab\.com',
            r'nab\.payments', r'nab\.gateway', r'nab\.bank',
            r'data-nab', r'nab-payment'
        ],
        "Epay": [
            r'epay', r'e-pay', r'epay\.com',
            r'epay\.payment', r'epay\.method', r'epay\.gateway',
            r'data-epay', r'epay-button'
        ],
        "Afterpay": [
            r'afterpay', r'afterpay\.com', r'afterpay\.js',
            r'afterpay\.min\.js', r'afterpay-payment',
            r'data-afterpay', r'afterpay-button'
        ],
        "ANZ": [
            r'anz', r'australia and new zealand banking', r'anz\.com',
            r'anz\.com\.au', r'anz-payment', r'anz-gateway',
            r'data-anz', r'anz-bank'
        ],
        "CBA": [
            r'cba', r'commonwealth bank', r'commbank',
            r'commbank\.com\.au', r'cba-payment', r'cba-gateway',
            r'data-cba', r'cba-bank'
        ],
        "Magento": [
            r'magento', r'magento-payment', r'magento-checkout',
            r'magento-gateway', r'data-magento'
        ],
        "WooCommerce": [
            r'woocommerce', r'wc-', r'woocommerce-payment',
            r'woocommerce-gateway', r'data-woocommerce'
        ],
        "Eway": [
            r'eway', r'eway\.com\.au', r'eway-payment',
            r'eway-gateway', r'data-eway'
        ],
        "Clover Payments": [
            r'clover', r'clover\.com', r'clover-payment',
            r'clover-gateway', r'data-clover'
        ],
        "FirstData": [
            r'firstdata', r'firstdata\.com', r'firstdata-payment',
            r'firstdata-gateway', r'data-firstdata'
        ],
        "CyberSource": [
            r'cybersource', r'cybersource\.com', r'cybersource-payment',
            r'cybersource-gateway', r'data-cybersource'
        ],
        "Invoice": [
            r'invoice', r'invoice-payment', r'invoice-gateway',
            r'data-invoice', r'pay-by-invoice'
        ],
        "ECard": [
            r'ecard', r'e-card', r'ecard-payment',
            r'ecard-gateway', r'data-ecard'
        ],
        "CPay": [
            r'cpay', r'c-pay', r'cpay-payment',
            r'cpay-gateway', r'data-cpay'
        ],
        "AVS": [
            r'avs', r'address verification system', r'avs-check',
            r'avs-verification', r'data-avs'
        ]
    }

    for gateway_name, patterns in gateway_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                detected_gateways.add(gateway_name)
                break

    # Enhanced Stripe detection with API keys
    stripe_key_patterns = [r'pk_live_[a-zA-Z0-9]{24,}', r'pk_test_[a-zA-Z0-9]{24,}']
    for pattern in stripe_key_patterns:
        if re.search(pattern, response_text):
            detected_gateways.add("Stripe")
            break

    return list(detected_gateways) if detected_gateways else ["Unknown"]

def create_advanced_scraper():
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False, 'desktop': True},
            interpreter='nodejs',
            delay=15,
            ssl_context=ssl_context
        )
        scraper.timeout = 30
        return scraper
    except Exception as e:
        logger.error(f"Failed to create advanced scraper: {e}")
        session = requests.Session()
        session.verify = False
        session.timeout = 30
        return session

def scan_website_enhanced(url):
    try:
        normalized_url = normalize_url(url)
        domain = urlparse(normalized_url).netloc
        ip_address = get_ip_address(domain)

        if not re.match(r'^https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)$', normalized_url):
            return None, None, None, None, None, None, None, None, "Invalid URL", 0, "N/A"

        start_time = time.time()
        all_detected_gateways = set()

        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        ]

        response = None
        html_text = ""
        status_code = 0
        server_info = "Unknown"
        final_url = normalized_url

        for i, user_agent in enumerate(user_agents):
            try:
                if i < 1:
                    scraper = create_advanced_scraper()
                    headers = {'User-Agent': user_agent}
                    response = scraper.get(normalized_url, headers=headers, timeout=25, verify=False)
                else:
                    session = requests.Session()
                    session.verify = False
                    headers = {'User-Agent': user_agent}
                    response = session.get(normalized_url, headers=headers, timeout=20)

                status_code = response.status_code
                final_url = response.url

                if response.status_code == 200:
                    html_text = response.text
                    initial_gateways = find_payment_gateways_comprehensive(response.text, final_url)
                    all_detected_gateways.update(initial_gateways)
                    
                    # Enhanced server info detection
                    server_info = "Unknown"
                    if 'server' in response.headers:
                        server_header = response.headers.get('server', '').lower()
                        if 'apache' in server_header:
                            server_info = "Apache"
                        elif 'nginx' in server_header:
                            server_info = "nginx"
                        elif 'cloudflare' in server_header:
                            server_info = "Cloudflare"
                        elif 'iis' in server_header or 'microsoft-iis' in server_header:
                            server_info = "IIS"
                        elif 'openresty' in server_header:
                            server_info = "OpenResty"
                        elif 'caddy' in server_header:
                            server_info = "Caddy"
                        elif 'lite speed' in server_header or 'litespeed' in server_header:
                            server_info = "LiteSpeed"
                        elif 'tomcat' in server_header:
                            server_info = "Tomcat"
                        elif 'jetty' in server_header:
                            server_info = "Jetty"
                        elif 'gunicorn' in server_header:
                            server_info = "Gunicorn"
                        elif 'node.js' in server_header or 'nodejs' in server_header:
                            server_info = "Node.js"
                        else:
                            server_info = response.headers.get('server', 'Unknown')
                    
                    # Try to get more info from headers if server is still unknown
                    if server_info == "Unknown":
                        if 'x-powered-by' in response.headers:
                            x_powered = response.headers.get('x-powered-by', '').lower()
                            if 'php' in x_powered:
                                server_info = "PHP"
                            elif 'asp.net' in x_powered:
                                server_info = "ASP.NET"
                            elif 'nodejs' in x_powered:
                                server_info = "Node.js"
                            elif 'python' in x_powered:
                                server_info = "Python"
                            elif 'ruby' in x_powered:
                                server_info = "Ruby"
                            elif 'java' in x_powered:
                                server_info = "Java"
                    
                    break
                elif response.status_code in [403, 429, 503]:
                    continue

            except Exception as e:
                continue

        time_taken = time.time() - start_time

        if not html_text:
            return None, None, None, None, None, None, None, None, "Site is blocking our requests or requires advanced JavaScript", status_code, ip_address

        # Process results for platform detection
        text_lower = html_text.lower()
        platform = "Unknown"
        
        # Comprehensive platform patterns
        platform_patterns = {
            "WordPress": [
                r'wp-content', r'wordpress', r'wp-json', r'wp-includes',
                r'wp-admin', r'wp-login', r'xmlrpc\.php', r'wp-cron\.php',
                r'wp-emoji-release', r'wp-embed', r'wp-theme', r'wp-plugin',
                r'elementor', r'divi', r'astra', r'woocommerce'
            ],
            "Shopify": [
                r'shopify', r'cdn\.shopify\.com', r'shopify\.com',
                r'shopify\.js', r'shopify\.min\.js', r'shopify-checkout',
                r'myshopify\.com', r'powered_by_shopify', r'Shopify\.theme'
            ],
            "WooCommerce": [
                r'woocommerce', r'wc-', r'woocommerce-payment',
                r'woocommerce-gateway', r'data-woocommerce', r'wc-block',
                r'wc-cart', r'wc-checkout', r'wc-product'
            ],
            "Magento": [
                r'magento', r'magento-payment', r'magento-checkout',
                r'magento-gateway', r'data-magento', r'mage\/',
                r'js\/magento', r'skin\/frontend', r'requirejs\/magento'
            ],
            "PrestaShop": [
                r'prestashop', r'presta', r'prestashop\.com',
                r'prestashop\.js', r'prestashop-theme', r'ps_shoppingcart',
                r'ps_currencyselector', r'ps_languageselector'
            ],
            "OpenCart": [
                r'opencart', r'oc-\d+', r'route=checkout', r'catalog\/view',
                r'opencart\.js', r'ocmod', r'opencart-theme'
            ],
            "Drupal": [
                r'drupal', r'drupal\.js', r'drupal\.org',
                r'sites\/default', r'misc\/drupal', r'drupal-settings',
                r'core\/modules', r'core\/themes'
            ],
            "Joomla": [
                r'joomla', r'joomla\.org', r'media\/system\/js',
                r'media\/jui', r'com_content', r'com_contact',
                r'com_users', r'com_phocagallery'
            ],
            "BigCommerce": [
                r'bigcommerce', r'bigc\.io', r'bigcommerce\.com',
                r'cdn\.bigcommerce', r'bc-sdk', r'bigcommerce-chat'
            ],
            "Squarespace": [
                r'squarespace', r'squarespace\.com', r'static1\.squarespace',
                r'assets\.squarespace', r'squarespace-cdn'
            ],
            "Wix": [
                r'wix', r'wix\.com', r'static\.wixstatic', r'wix-ui',
                r'wix-js', r'wix-react', r'wix-code'
            ],
            "Weebly": [
                r'weebly', r'weebly\.com', r'weebly\.js',
                r'cdn\.weebly', r'weebly-files'
            ],
            "Ghost": [
                r'ghost', r'ghost\.org', r'ghost\.io',
                r'ghost\.js', r'ghost-theme', r'ghost-head'
            ],
            "Webflow": [
                r'webflow', r'webflow\.com', r'webflow\.js',
                r'webflow-cdn', r'webflow-design'
            ],
            "Jimdo": [
                r'jimdo', r'jimdo\.com', r'jimdo\.js',
                r'jimdo-cdn', r'jimdo-payment'
            ],
            "Tumblr": [
                r'tumblr', r'tumblr\.com', r'tumblr_',
                r'tumblr-theme', r'tumblr-controls'
            ],
            "Ecwid": [
                r'ecwid', r'ecwid\.com', r'ecwid\.js',
                r'ecwid-cdn', r'ecwid-store'
            ],
            "Sellfy": [
                r'sellfy', r'sellfy\.com', r'sellfy\.js',
                r'sellfy-cdn', r'sellfy-payment'
            ],
            "Gumroad": [
                r'gumroad', r'gumroad\.com', r'gumroad\.js',
                r'gumroad-cdn', r'gumroad-overlay'
            ],
            "Podia": [
                r'podia', r'podia\.com', r'podia\.js',
                r'podia-cdn', r'podia-checkout'
            ],
            "Thinkific": [
                r'thinkific', r'thinkific\.com', r'thinkific\.js',
                r'thinkific-cdn', r'thinkific-course'
            ],
            "Teachable": [
                r'teachable', r'teachable\.com', r'teachable\.js',
                r'teachable-cdn', r'teachable-checkout'
            ],
            "Kajabi": [
                r'kajabi', r'kajabi\.com', r'kajabi\.js',
                r'kajabi-cdn', r'kajabi-checkout'
            ],
            "ClickFunnels": [
                r'clickfunnels', r'clickfunnels\.com', r'cf-page',
                r'cf-assets', r'cf-checkout', r'clickfunnels-js'
            ],
            "Leadpages": [
                r'leadpages', r'leadpages\.com', r'leadpages\.js',
                r'leadpages-cdn', r'leadpages-checkout'
            ],
            "Unbounce": [
                r'unbounce', r'unbounce\.com', r'unbounce\.js',
                r'unbounce-cdn', r'unbounce-page'
            ],
            "Instapage": [
                r'instapage', r'instapage\.com', r'instapage\.js',
                r'instapage-cdn', r'instapage-checkout'
            ],
            "Webnode": [
                r'webnode', r'webnode\.com', r'webnode\.js',
                r'webnode-cdn', r'webnode-store'
            ],
            "Strikingly": [
                r'strikingly', r'strikingly\.com', r'strikingly\.js',
                r'strikingly-cdn', r'strikingly-checkout'
            ],
            "Carrd": [
                r'carrd', r'carrd\.co', r'carrd\.js',
                r'carrd-cdn', r'carrd-checkout'
            ],
            "Tilda": [
                r'tilda', r'tilda\.cc', r'tilda\.js',
                r'tilda-cdn', r'tilda-payment'
            ],
            "Ucraft": [
                r'ucraft', r'ucraft\.com', r'ucraft\.js',
                r'ucraft-cdn', r'ucraft-store'
            ],
            "Duda": [
                r'duda', r'duda\.co', r'duda\.js',
                r'duda-cdn', r'duda-checkout'
            ],
            "IMCreator": [
                r'imcreator', r'imcreator\.com', r'imcreator\.js',
                r'imcreator-cdn', r'imcreator-store'
            ],
            "Voog": [
                r'voog', r'voog\.com', r'voog\.js',
                r'voog-cdn', r'voog-checkout'
            ],
            "SiteBuilder": [
                r'sitebuilder', r'sitebuilder\.com', r'sitebuilder\.js',
                r'sitebuilder-cdn', r'sitebuilder-store'
            ],
            "Zoho": [
                r'zoho', r'zoho\.com', r'zoho\.js',
                r'zoho-cdn', r'zoho-checkout', r'zoho-payment'
            ],
            "Salesforce": [
                r'salesforce', r'salesforce\.com', r'salesforce\.js',
                r'salesforce-cdn', r'salesforce-checkout', r'sfdc'
            ],
            "HubSpot": [
                r'hubspot', r'hubspot\.com', r'hubspot\.js',
                r'hubspot-cdn', r'hubspot-checkout', r'hs-analytics'
            ],
            "Mailchimp": [
                r'mailchimp', r'mailchimp\.com', r'mailchimp\.js',
                r'mailchimp-cdn', r'mailchimp-checkout', r'mc-embed'
            ],
            "Stripe": [
                r'stripe', r'js\.stripe\.com', r'stripe\.com',
                r'stripe-payment', r'stripe-checkout'
            ],
            "PayPal": [
                r'paypal', r'paypal\.com', r'paypalobjects\.com',
                r'paypal-payment', r'paypal-checkout'
            ],
            "Braintree": [
                r'braintree', r'braintreegateway\.com', r'braintree-payment',
                r'braintree-checkout'
            ],
            "Klarna": [
                r'klarna', r'klarna\.com', r'klarna-payment',
                r'klarna-checkout'
            ],
            "Square": [
                r'square', r'squareup\.com', r'square-payment',
                r'square-checkout'
            ],
            "Authorize.Net": [
                r'authorize\.net', r'authorizenet', r'accept\.js',
                r'authorize-payment'
            ],
            "2Checkout": [
                r'2checkout', r'2co\.com', r'2checkout-payment',
                r'2checkout-checkout'
            ],
            "Adyen": [
                r'adyen', r'adyen\.com', r'adyen-payment',
                r'adyen-checkout'
            ],
            "Worldpay": [
                r'worldpay', r'worldpay\.com', r'worldpay-payment',
                r'worldpay-checkout'
            ],
            "SagePay": [
                r'sagepay', r'sagepay\.com', r'sagepay-payment',
                r'sagepay-checkout'
            ],
            "Amazon Pay": [
                r'amazon pay', r'pay\.amazon\.com', r'amazon-pay',
                r'amazon-checkout'
            ],
            "Apple Pay": [
                r'apple pay', r'apple-pay', r'applepay',
                r'apple-payment'
            ],
            "Google Pay": [
                r'google pay', r'google-pay', r'googlepay',
                r'google-payment'
            ],
            "Venmo": [
                r'venmo', r'venmo\.com', r'venmo-payment',
                r'venmo-checkout'
            ],
            "Chase": [
                r'chase', r'chase\.com', r'chase-payment',
                r'chase-checkout'
            ]
        }

        # Detect platform by checking patterns
        for platform_name, patterns in platform_patterns.items():
            if any(re.search(pattern, html_text, re.IGNORECASE) for pattern in patterns):
                platform = platform_name
                break

        # If platform still Unknown, try meta tags and other indicators
        if platform == "Unknown":
            # Check for generator meta tag
            generator_match = re.search(r'<meta name="generator" content="([^"]+)"', html_text, re.IGNORECASE)
            if generator_match:
                generator = generator_match.group(1)
                if 'wordpress' in generator.lower():
                    platform = "WordPress"
                elif 'shopify' in generator.lower():
                    platform = "Shopify"
                elif 'magento' in generator.lower():
                    platform = "Magento"
                elif 'prestashop' in generator.lower():
                    platform = "PrestaShop"
                elif 'drupal' in generator.lower():
                    platform = "Drupal"
                elif 'joomla' in generator.lower():
                    platform = "Joomla"
                elif 'wix' in generator.lower():
                    platform = "Wix"
                elif 'squarespace' in generator.lower():
                    platform = "Squarespace"
                elif 'weebly' in generator.lower():
                    platform = "Weebly"
                elif 'ghost' in generator.lower():
                    platform = "Ghost"
                elif 'webflow' in generator.lower():
                    platform = "Webflow"
                else:
                    platform = generator

        # Captcha detection
        captcha = False
        captcha_type = "N/A"
        if re.search(r'recaptcha|g-recaptcha|grecaptcha', html_text, re.IGNORECASE):
            captcha = True
            captcha_type = "reCAPTCHA"
        elif re.search(r'hcaptcha|h-captcha', html_text, re.IGNORECASE):
            captcha = True
            captcha_type = "hCaptcha"
        elif re.search(r'funcaptcha', html_text, re.IGNORECASE):
            captcha = True
            captcha_type = "FunCaptcha"
        elif re.search(r'geetest', html_text, re.IGNORECASE):
            captcha = True
            captcha_type = "Geetest"
        elif re.search(r'captcha', html_text, re.IGNORECASE):
            captcha = True
            captcha_type = "Generic CAPTCHA"

        # Cloudflare detection
        cloudflare = False
        if response:
            cloudflare = "cloudflare" in (response.headers.get('server', '')).lower() or "cf-ray" in response.headers

        # Final gateway list
        gateways_list = sorted(list(set(all_detected_gateways)))
        if len(gateways_list) > 1 and "Unknown" in gateways_list:
            gateways_list.remove("Unknown")
        if not gateways_list:
            gateways_list = ["Unknown"]

        # Simple auth gate detection
        auth_gate = False
        if re.search(r'add.?payment.?method|payment.?method.?form', text_lower):
            auth_gate = True

        # Simple VBV detection
        vbv = False
        if re.search(r'vbv|verified by visa|3ds|3-d secure', text_lower, re.IGNORECASE):
            vbv = True

        return gateways_list, platform, captcha, captcha_type, cloudflare, auth_gate, vbv, time_taken, server_info, status_code, ip_address

    except Exception as e:
        logger.error(f"Error scanning website {url}: {str(e)}", exc_info=True)
        return None, None, None, None, None, None, None, None, None, f"Scanning failed: {str(e)}", "N/A"

@Client.on_message(filters.command("gate"))
@auth_and_free_restricted
async def gate_command(client, message):
    # Check if command is disabled
    command_text = message.text.split()[0] if message.text else ""
    if is_command_disabled(command_text):
        await message.reply(get_command_offline_message(command_text))
        return

    # Check if user is restricted
    if is_user_restricted_for_command(message.from_user.id, command_text):
        await message.reply("""<pre>🚫 Access Restricted</pre>
━━━━━━━━━━━━━
⟐ <b>Message</b>: You are restricted from using this command.
⟐ <b>Contact</b>: <code>@D_A_DYY</code> for assistance.
━━━━━━━━━━━━━""")
        return

    user_id = message.from_user.id

    if not is_user_registered(user_id):
        await message.reply("<pre>🔒 You need to register first! Use /register command.</pre>")
        return

    text = get_message_text(message)
    args = text.split()
    if len(args) < 2:
        await message.reply("""
<pre>#WAYNE 〔/gate〕</pre>
━━━━━━━━━━━━━
<pre>Format: /gate {website_url}</pre>
<pre>Example: /gate example.com</pre>
<pre>Example: /gate https://shop.example.com</pre>
━━━━━━━━━━━━━
<pre>Features:</pre>
<code>Payment Gateway Detection</code>
<code>VBV Check</code>
<code>Auth Gate Detection</code>
━━━━━━━━━━━━━
<pre>Scan time: 20-40 seconds</pre>
━━━━━━━━━━━━━""")
        return

    url = args[1].strip()
    normalized_url = normalize_url(url)

    processing_msg = await message.reply(f"<pre>🌐 Scanning {normalized_url}... ⚡ Advanced scan in progress (20-40 seconds)</pre>")

    try:
        scan_results = await asyncio.get_event_loop().run_in_executor(
            gate_thread_pool, scan_website_enhanced, normalized_url
        )

        if len(scan_results) == 11:
            gateways, platform, captcha, captcha_type, cloudflare, auth_gate, vbv, time_taken, server_info, status_code, ip_address = scan_results
        else:
            await processing_msg.edit("<pre>❌ Failed to scan website. Invalid response format.</pre>")
            return

        if gateways is None and platform is None:
            error_msg = status_code if isinstance(status_code, str) else "Site is blocking our requests or requires advanced JavaScript"
            await processing_msg.edit(f"""
<pre>❌ Scan Failed</pre>
━━━━━━━━━━━━━
<pre>URL: {normalized_url}</pre>
<pre>Error: {error_msg}</pre>
━━━━━━━━━━━━━""")
            return

        # Format status text based on status code
        status_text = f"{status_code}"
        if status_code == 200:
            status_text = f"{status_code} (𝙊𝙆)"

        # Format true/false with appropriate emojis
        captcha_text = "𝙁𝙖𝙡𝙨𝙚 ❌" if not captcha else "𝙏𝙧𝙪𝙚 ✅"
        cloudflare_text = "𝙁𝙖𝙡𝙨𝙚 ❌" if not cloudflare else "𝙏𝙧𝙪𝙚 ✅"
        auth_gate_text = "𝙁𝙖𝙡𝙨𝙚 ❌" if not auth_gate else "𝙏𝙧𝙪𝙚 ✅"
        vbv_text = "𝙁𝙖𝙡𝙨𝙚 ❌" if not vbv else "𝙏𝙧𝙪𝙚 ✅"

        # Format the response with the requested UI
        response = f"""<b>━━━━━━━ 𝓢𝓲𝓽𝓮 𝓢𝓽𝓪𝓽𝓾𝓼 ━━━━━━━</b>
<b>𝘐𝘱 𝘈𝘥𝘥𝘳𝘦𝘴𝘴</b> : <code>{ip_address}</code>
<b>𝘚𝘪𝘵𝘦</b>       : <code>{normalized_url}</code>
<b>𝘏𝘛𝘛𝘗 𝘚𝘵𝘢𝘵𝘶𝘴</b> : <code>{status_text}</code>
<pre>─────────┈∘◦┄┄┄┄┄∘◦┈────────</pre>
<b>𝙋𝙖𝙮𝙢𝙚𝙣𝙩 𝙈𝙚𝙩𝙝𝙤𝙙𝙨</b>: <code>{', '.join(gateways) if gateways else 'None detected'}</code>

<b>𝘾𝙖𝙥𝙩𝙘𝙝𝙖</b>     : <b>{captcha_text}</b>
<b>𝘾𝙖𝙥𝙩𝙘𝙝𝙖 𝙏𝙮𝙥𝙚</b> : <code>{captcha_type or 'N/A'}</code>
<b>𝘾𝙡𝙤𝙪𝙙𝙛𝙡𝙖𝙧𝙚</b>  : <b>{cloudflare_text}</b>
<pre>─────────┈∘◦┄┄┄┄┄∘◦┈────────</pre>
<b>𝙋𝙡𝙖𝙩𝙛𝙤𝙧𝙢</b>    : <code>{platform or 'Unknown'}</code>
<b>𝙎𝙚𝙧𝙫𝙚𝙧 𝐈𝐧𝐟𝐨</b> : <code>{server_info or 'Unknown'}</code>

<b>𝘼𝙪𝙩𝙝 𝙂𝘢𝙩𝙚</b>   : <b>{auth_gate_text}</b>
<b>𝙑𝘽𝙑</b>         : <b>{vbv_text}</b>
<pre>━━━━━━━━━━━━━━━━━━━━━</pre>
<b>𝙏𝙞𝙢𝙚 𝙏𝙖𝙠𝙚𝙣</b>  : <code>{time_taken:.2f}</code> <b>𝙨𝙚𝙘𝙤𝙣𝙙𝙨</b>"""

        await processing_msg.edit(response.strip())

    except Exception as e:
        error_msg = str(e) if str(e) else "Unknown error"
        await processing_msg.edit(f"<pre>❌ Unexpected error: {error_msg}</pre>")

# Update the USERS_FILE path
USERS_FILE = "DATA/users.json"
