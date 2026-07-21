import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import requests
import json
import time
from datetime import datetime, timedelta
import io
from PIL import Image, ImageDraw, ImageFont
import random
import logging
import os
from functools import wraps
import calendar
import sys
import atexit

# ============================================================
# 0. PID CHECK – prevents duplicate instances (409 Conflict)
# ============================================================
PID_FILE = "/tmp/d3crown_bot.pid"

def check_pid():
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            old_pid = int(f.read())
            try:
                os.kill(old_pid, 0)
                print("⚠️ Another instance is running. Exiting.")
                sys.exit(1)
            except OSError:
                # stale PID file – remove it
                os.remove(PID_FILE)
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.remove(PID_FILE) if os.path.exists(PID_FILE) else None)

check_pid()

# ============================================================
# 1. LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# 2. BOT SETUP
# ============================================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8551239286:AAEd8gIDuF3GkjA9hJgoSwI405_CrWoM6X4")
bot = telebot.TeleBot(BOT_TOKEN)   # <-- BOT DEFINED HERE

# ============================================================
# 3. FIREBASE SETUP
# ============================================================
FIREBASE_URL = os.getenv("FIREBASE_URL", "https://d3crown-805ce-default-rtdb.firebaseio.com/d3_clients/0rulvawKt1d6M3FlxfEariNOukk1/clients.json")

# ============================================================
# 4. OWNER INFORMATION
# ============================================================
OWNER_NAME = "Shahid Ali Abro"
OWNER_PHONE = "03052848369"
OWNER_EMAIL = "aliabro104@gmail.com"
OWNER_WHATSAPP = "03052848369"

# ============================================================
# 5. RETRY DECORATOR
# ============================================================
def retry_on_failure(max_retries=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
            return None, None
        return wrapper
    return decorator

# ============================================================
# 6. BILLING REPAIR ENGINE (completely rebuilt)
# ============================================================
def parse_date(date_str):
    if not date_str:
        return None
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d",
        "%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    return None

def compute_month_diff(start_date, end_date):
    if not start_date or not end_date:
        return 0
    if start_date > end_date:
        return 0
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day < start_date.day:
        months -= 1
    return max(0, months)

def billing_repair_engine(client_data, phone):
    """Recalculate everything from scratch – never trust oldBill."""
    if not client_data:
        return None

    client_data.setdefault('paymentHistory', [])
    client_data.setdefault('packageAmount', 0)
    client_data.setdefault('packageStartDate', None)
    client_data.setdefault('status', 'UNPAID')
    client_data.setdefault('oldBill', 0)

    package_amount = client_data.get('packageAmount', 0)
    if package_amount <= 0:
        # No package amount → no billing
        client_data['oldBill'] = 0
        client_data['status'] = 'PAID'
        client_data['totalPaid'] = 0
        client_data['remainingBalance'] = 0
        client_data['totalBill'] = 0
        client_data['lastPaymentDate'] = 'N/A'
        client_data['nextDueDate'] = 'N/A'
        return client_data

    # Parse start date
    start_str = client_data.get('packageStartDate')
    start_date = parse_date(start_str)
    if not start_date:
        logger.warning(f"No valid start date for {phone}, assuming today")
        start_date = datetime.now()
        client_data['packageStartDate'] = start_date.strftime("%Y-%m-%d")

    today = datetime.now()
    months_elapsed = compute_month_diff(start_date, today)
    if months_elapsed < 0:
        months_elapsed = 0

    total_bill = package_amount * months_elapsed

    # Sum credits
    total_paid = 0
    last_payment_date = None
    for entry in client_data.get('paymentHistory', []):
        credit = entry.get('credit', 0)
        if credit > 0:
            total_paid += credit
            entry_date = entry.get('date')
            if entry_date:
                dt = parse_date(entry_date)
                if dt and (not last_payment_date or dt > last_payment_date):
                    last_payment_date = dt

    remaining = total_bill - total_paid
    if remaining < 0:
        remaining = 0

    status = "PAID" if remaining <= 0 else "UNPAID"

    # Next due date (only for unpaid)
    if status == "UNPAID":
        if last_payment_date:
            next_due = last_payment_date + timedelta(days=30)
        else:
            next_due = start_date + timedelta(days=30 * (months_elapsed + 1))
        client_data['nextDueDate'] = next_due.strftime("%Y-%m-%d")
    else:
        client_data['nextDueDate'] = "N/A"

    client_data['oldBill'] = remaining
    client_data['status'] = status
    client_data['totalPaid'] = total_paid
    client_data['remainingBalance'] = remaining
    client_data['totalBill'] = total_bill
    client_data['lastPaymentDate'] = last_payment_date.strftime("%Y-%m-%d") if last_payment_date else "N/A"
    client_data['isPaid'] = (status == "PAID")

    if not isinstance(client_data.get('paymentHistory'), list):
        client_data['paymentHistory'] = []

    return client_data

def sync_client_to_firebase(phone, client_data):
    """Update Firebase with repaired billing data."""
    try:
        response = requests.get(FIREBASE_URL, timeout=15)
        if response.status_code != 200:
            logger.error(f"Firebase fetch error: {response.status_code}")
            return False
        clients = response.json()
        if not clients or not isinstance(clients, list):
            return False

        clean_phone = phone.replace('+', '').replace('-', '').replace(' ', '').strip()
        for idx, cl in enumerate(clients):
            if not isinstance(cl, dict):
                continue
            client_phone = str(cl.get('phone', '')).replace('+', '').replace('-', '').replace(' ', '').strip()
            if client_phone == clean_phone:
                # Update only billing-related fields
                clients[idx]['oldBill'] = client_data.get('oldBill', 0)
                clients[idx]['status'] = client_data.get('status', 'UNPAID')
                clients[idx]['totalPaid'] = client_data.get('totalPaid', 0)
                clients[idx]['remainingBalance'] = client_data.get('remainingBalance', 0)
                clients[idx]['totalBill'] = client_data.get('totalBill', 0)
                clients[idx]['lastPaymentDate'] = client_data.get('lastPaymentDate', 'N/A')
                clients[idx]['nextDueDate'] = client_data.get('nextDueDate', 'N/A')
                clients[idx]['paymentHistory'] = client_data.get('paymentHistory', [])
                clients[idx]['packageStartDate'] = client_data.get('packageStartDate')
                break

        response = requests.put(FIREBASE_URL, json=clients, timeout=15)
        if response.status_code in (200, 201):
            logger.info(f"Firebase sync successful for {phone}")
            return True
        else:
            logger.error(f"Firebase update failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error syncing to Firebase: {e}")
        return False

# ============================================================
# 7. PROFESSIONAL RECEIPT GENERATION (Canva-quality)
# ============================================================
def generate_professional_receipt(client_data, is_paid=False):
    try:
        width, height = 1080, 1550
        image = Image.new('RGB', (width, height), color='#f0f4f8')
        draw = ImageDraw.Draw(image)

        # Gradient background
        for i in range(height):
            ratio = i / height
            r = int(240 - 60 * ratio)
            g = int(244 - 70 * ratio)
            b = int(248 - 80 * ratio)
            draw.line([(0, i), (width, i)], fill=(r, g, b))

        # Header
        header_y, header_height = 20, 220
        draw.rectangle([(30, header_y), (width-30, header_y+header_height)],
                       fill=(26,35,126), outline=(255,255,255,50), width=2)
        draw.rectangle([(40, header_y+10), (width-40, header_y+header_height-10)],
                       fill=(40,53,147,50))

        try:
            font_logo = ImageFont.truetype("arial.ttf", 52)
            font_sub = ImageFont.truetype("arial.ttf", 24)
            font_bold = ImageFont.truetype("arialbd.ttf", 36)
            font_normal = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except:
            font_logo = font_sub = font_bold = font_normal = font_small = ImageFont.load_default()

        draw.text((width//2 - 130, header_y+40), "D3 CROWN", fill='#ffffff', font=font_logo)
        draw.text((width//2 - 110, header_y+100), "FLASH FIBER ISP", fill='#e0e0e0', font=font_sub)
        draw.text((width//2 - 95, header_y+130), "Private Limited ™", fill='#ffd700', font=font_small)

        # Status badge
        status_text = "PAID ✓" if is_paid else "UNPAID ✗"
        status_color = "#2e7d32" if is_paid else "#c62828"
        badge_w, badge_h = 180, 50
        badge_x = width//2 - badge_w//2
        badge_y = header_y + header_height - 60
        draw.rectangle([(badge_x, badge_y), (badge_x+badge_w, badge_y+badge_h)],
                       fill=status_color, outline='#ffffff', width=2)
        draw.text((width//2 - 70, badge_y+12), status_text, fill='#ffffff', font=font_bold)

        # Receipt card
        card_y = header_y + header_height + 30
        card_h = height - card_y - 40
        draw.rectangle([(30, card_y), (width-30, card_y+card_h)],
                       fill=(255,255,255,240), outline=(255,255,255,100), width=2)
        draw.rectangle([(40, card_y+10), (width-40, card_y+card_h-10)],
                       fill=(240,248,255,50))

        y = card_y + 30
        receipt_id = f"D3-{datetime.now().strftime('%y%m%d')}-{random.randint(100000, 999999)}"
        draw.text((60, y), "RECEIPT #", fill='#666', font=font_small)
        draw.text((200, y), receipt_id, fill='#1a237e', font=font_bold)
        draw.text((60, y+35), "DATE & TIME", fill='#666', font=font_small)
        draw.text((200, y+35), datetime.now().strftime('%d %B %Y %I:%M %p'), fill='#1a237e', font=font_normal)

        y += 80
        draw.line([(60, y), (width-60, y)], fill='#e0e0e0', width=2)
        y += 20

        # Customer info
        box_y = y
        box_h = 180
        draw.rectangle([(60, box_y), (width-60, box_y+box_h)],
                       fill='#f8f9fa', outline='#e0e0e0', width=1)
        draw.text((80, box_y+15), "👤 CUSTOMER INFORMATION", fill='#1a237e', font=font_bold)
        cust_fields = [
            ("Name", client_data.get('name','N/A')),
            ("Phone", client_data.get('phone','N/A')),
            ("Address", client_data.get('address','N/A')),
            ("VLAN ID", client_data.get('vlanId','N/A'))
        ]
        y = box_y+50
        for label, value in cust_fields:
            draw.text((80, y), label+":", fill='#666', font=font_normal)
            draw.text((220, y), value, fill='#1a237e', font=font_normal)
            y += 35
        y = box_y+box_h+20

        # Package details
        draw.rectangle([(60, y), (width-60, y+140)],
                       fill='#f8f9fa', outline='#e0e0e0', width=1)
        draw.text((80, y+15), "📦 PACKAGE DETAILS", fill='#1a237e', font=font_bold)
        pkg_fields = [
            ("Package", client_data.get('package','N/A')),
            ("Speed", client_data.get('package','N/A').replace('DHCP-','')),
            ("Monthly Fee", f"Rs. {client_data.get('packageAmount',0):,}"),
            ("Start Date", client_data.get('packageStartDate','N/A'))
        ]
        y += 50
        for label, value in pkg_fields:
            draw.text((80, y), label+":", fill='#666', font=font_normal)
            draw.text((220, y), value, fill='#1a237e', font=font_normal)
            y += 30
        y += 20

        # Billing summary
        total_bill = client_data.get('totalBill', 0)
        total_paid = client_data.get('totalPaid', 0)
        remaining = client_data.get('remainingBalance', 0)

        billing_y = y
        billing_h = 200
        draw.rectangle([(60, billing_y), (width-60, billing_y+billing_h)],
                       fill='#1a237e', outline='#1a237e', width=1)
        draw.text((80, billing_y+15), "💰 BILLING SUMMARY", fill='#ffffff', font=font_bold)
        b_fields = [
            ("Total Bill (All Months)", f"Rs. {total_bill:,}"),
            ("Total Paid", f"Rs. {total_paid:,}"),
            ("Outstanding Balance", f"Rs. {remaining:,}")
        ]
        y = billing_y+50
        for label, value in b_fields:
            draw.text((80, y), label+":", fill='#e0e0e0', font=font_normal)
            color = '#ff6b6b' if label=="Outstanding Balance" and remaining>0 else '#ffffff'
            draw.text((250, y), value, fill=color, font=font_bold if label in ["Total Paid","Outstanding Balance"] else font_normal)
            y += 30
        y = billing_y+billing_h+20

        # Total paid box
        draw.rectangle([(60, y), (width-60, y+60)],
                       fill='#2e7d32' if total_paid>0 else '#c62828')
        draw.text((80, y+15), "TOTAL PAID", fill='#ffffff', font=font_bold)
        draw.text((250, y+15), f"Rs. {total_paid:,}" if total_paid>0 else "Rs. 0", fill='#ffffff', font=font_bold)
        if total_paid == 0:
            draw.text((80, y+40), "No payment recorded yet.", fill='#ffcdd2', font=font_small)
        y += 80

        # Footer
        y = height - 120
        draw.line([(60, y), (width-60, y)], fill='#e0e0e0', width=2)
        y += 20
        draw.text((width//2 - 120, y), "Speed Ka Naya Andaaz!", fill='#1a237e', font=font_bold)
        y += 40
        draw.text((width//2 - 140, y), f"📞 {OWNER_PHONE} | 📧 {OWNER_EMAIL}", fill='#666', font=font_small)
        y += 25
        draw.text((width//2 - 130, y), "D3 Crown Fiber — Connecting You to Excellence", fill='#666', font=font_small)
        y += 25
        draw.text((width//2 - 80, y), "- System Generated Receipt -", fill='#999', font=font_small)

        draw.text((width//2 - 200, height//2 - 50), "D3 CROWN", fill=(200,200,200,30), font=font_logo)

        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=95)
        img_byte_arr.seek(0)
        return img_byte_arr, receipt_id

    except Exception as e:
        logger.error(f"Error generating receipt: {e}")
        return None, None

# ============================================================
# 8. FIND CLIENT (with auto‑repair and Firebase sync)
# ============================================================
@retry_on_failure(max_retries=3, delay=2)
def find_client_by_phone(phone_number):
    try:
        clean_phone = phone_number.replace('+', '').replace('-', '').replace(' ', '').strip()
        response = requests.get(FIREBASE_URL, timeout=15)
        if response.status_code != 200:
            logger.error(f"Firebase error: {response.status_code}")
            return None, None
        clients_data = response.json()
        if not clients_data or not isinstance(clients_data, list):
            logger.error("Invalid client data format")
            return None, None

        for client in clients_data:
            if not isinstance(client, dict):
                continue
            client_phone = str(client.get('phone', '')).replace('+', '').replace('-', '').replace(' ', '').strip()
            if client_phone == clean_phone:
                repaired = billing_repair_engine(client, clean_phone)
                if repaired:
                    sync_client_to_firebase(clean_phone, repaired)
                    return repaired, client_phone
                else:
                    return client, client_phone
            if len(client_phone) >= 10 and len(clean_phone) >= 10:
                if client_phone[-10:] == clean_phone[-10:]:
                    repaired = billing_repair_engine(client, clean_phone)
                    if repaired:
                        sync_client_to_firebase(clean_phone, repaired)
                        return repaired, client_phone
                    else:
                        return client, client_phone
        return None, None
    except Exception as e:
        logger.error(f"Error in find_client: {e}")
        return None, None

# ============================================================
# 9. PAYMENT HISTORY & SHARE TEXT HELPERS
# ============================================================
def format_payment_history(payment_history, limit=5):
    if not payment_history:
        return "📊 No payment history available."
    msg = "📊 **PAYMENT HISTORY**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    recent = payment_history[-limit:] if len(payment_history)>limit else payment_history
    for entry in reversed(recent):
        date = entry.get('date','N/A')
        debit = entry.get('debit',0)
        credit = entry.get('credit',0)
        desc = entry.get('description','')
        eid = entry.get('entryId','')
        if debit > 0:
            msg += f"💰 **{date}**\n   💸 Debit: Rs.{debit:,}\n"
        if credit > 0:
            msg += f"💰 **{date}**\n   💳 Credit: Rs.{credit:,}\n"
        if desc:
            msg += f"   📝 {desc}\n"
        if eid:
            msg += f"   🆔 {eid}\n"
        msg += "\n"
    if len(payment_history) > limit:
        msg += f"\n_Showing last {limit} of {len(payment_history)} entries_"
    return msg

def share_result_text(client_data, matched_phone):
    name = client_data.get('name','N/A')
    package = client_data.get('package','N/A')
    amount = client_data.get('packageAmount',0)
    status = client_data.get('status','active')
    address = client_data.get('address','N/A')
    vlan = client_data.get('vlanId','N/A')
    old_bill = client_data.get('oldBill',0)
    total_bill = client_data.get('totalBill',0)
    total_paid = client_data.get('totalPaid',0)
    return (
        f"🏢 *D3 CROWN FIBER - Account Details*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Name:* {name}\n"
        f"📞 *Phone:* {matched_phone}\n"
        f"📦 *Package:* {package}\n"
        f"💰 *Monthly Fee:* Rs.{amount:,}\n"
        f"📊 *Status:* {status.upper()}\n"
        f"📍 *Address:* {address}\n"
        f"🔢 *VLAN ID:* {vlan}\n"
        f"💵 *Total Bill:* Rs.{total_bill:,}\n"
        f"💳 *Total Paid:* Rs.{total_paid:,}\n"
        f"⚠️ *Outstanding:* Rs.{old_bill:,}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💻 _System by: Khalid Ali Pechuha_"
    )

# ============================================================
# 10. MAIN MENU
# ============================================================
def get_main_menu():
    markup = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = KeyboardButton("📱 Check Account")
    btn2 = KeyboardButton("📦 View Packages")
    btn3 = KeyboardButton("🆘 Support Helpline")
    btn4 = KeyboardButton("📤 Share Result")
    btn5 = KeyboardButton("❌ Exit/Close")
    markup.add(btn1, btn2, btn3)
    markup.add(btn4, btn5)
    return markup

# ============================================================
# 11. BOT HANDLERS
# ============================================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🏢 **D3 Crown Flash Fiber**\n"
        "**Private Limited ™**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "السلام علیکم! 🤲\n"
        "Assalam-o-Alaikum! 👋\n\n"
        "✨ **D3 Crown Flash Fiber ISP Portal**\n"
        "آپ کا خوش آمدید\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 **Services:**\n"
        "• High-Speed Fiber Internet\n"
        "• 24/7 Customer Support\n"
        "• Business & Residential Plans\n"
        "• Professional ISP Solutions\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📱 **Send your registered phone number**\n"
        "to check account details\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💼 **Owner:** {OWNER_NAME}\n"
        f"📞 **Contact:** {OWNER_PHONE}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💻 _System by: Khalid Ali Pechuha_"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())

@bot.message_handler(func=lambda msg: msg.text == "📱 Check Account")
def check_account(message):
    bot.reply_to(message, "📱 **Please send your registered phone number**\nExample: 03001234567\n\n💻 _System by: Khalid Ali Pechuha_", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📦 View Packages")
def show_packages(message):
    package_msg = (
        "📋 **D3 CROWN PACKAGES**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💠 **DHCP-4Mbps** → Rs. 1,800/mo\n"
        "💠 **DHCP-6Mbps** → Rs. 2,100/mo\n"
        "💠 **DHCP-8Mbps** → Rs. 2,300/mo\n"
        "💠 **DHCP-10Mbps** → Rs. 2,600/mo\n"
        "💠 **DHCP-12Mbps** → Rs. 3,000/mo\n"
        "💠 **DHCP-15Mbps** → Rs. 3,500/mo\n"
        "💠 **DHCP-20Mbps** → Rs. 4,500/mo\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔄 _Package upgrade ke liye support se rabta karein_\n\n"
        f"📞 **Support:** {OWNER_PHONE}\n"
        "💻 _System by: Khalid Ali Pechuha_"
    )
    bot.reply_to(message, package_msg, parse_mode="Markdown", reply_markup=get_main_menu())

@bot.message_handler(func=lambda msg: msg.text == "📤 Share Result")
def share_result_button(message):
    bot.reply_to(message, "📤 **Please send your registered phone number**\nto share account details on WhatsApp.\n\nExample: 03001234567\n\n💻 _System by: Khalid Ali Pechuha_", parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🆘 Support Helpline")
def show_support(message):
    support_msg = (
        "🆘 **D3 CROWN SUPPORT**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📞 **Helpline:** {OWNER_PHONE}\n"
        f"📧 **Email:** {OWNER_EMAIL}\n"
        f"💬 **WhatsApp:** [Click to Chat](https://wa.me/92{OWNER_WHATSAPP})\n"
        f"🕐 **Response Time:** 24/7\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💼 **Owner:** {OWNER_NAME}\n"
        f"📞 **Contact:** {OWNER_PHONE}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💻 _System by: Khalid Ali Pechuha_"
    )
    bot.reply_to(message, support_msg, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=get_main_menu())

@bot.message_handler(func=lambda msg: msg.text == "❌ Exit/Close")
def exit_bot(message):
    exit_msg = (
        "👋 **Thank you for using D3 CROWN ISP!**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "اللہ حافظ! 🤲\n"
        "✅ Bot session closed successfully.\n\n"
        "🔄 To restart, type /start\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💻 _System by: Khalid Ali Pechuha_"
    )
    bot.reply_to(message, exit_msg, parse_mode="Markdown")
    bot.send_message(message.chat.id, "👋 Goodbye!", reply_markup=telebot.types.ReplyKeyboardRemove())

# ============================================================
# 12. VERIFY CLIENT – with exact template
# ============================================================
@bot.message_handler(func=lambda msg: True)
def verify_client(message):
    user_input = message.text.strip()
    clean_input = user_input.replace('+', '').replace('-', '').replace(' ', '').strip()
    if not clean_input.isdigit() or len(clean_input) < 10:
        bot.reply_to(message, "❌ **Invalid Format!**\n\nPlease enter a valid mobile number with at least 10 digits.\nExample: 03001234567\n\nOr use the menu buttons below.\n💻 _System by: Khalid Ali Pechuha_", parse_mode="Markdown", reply_markup=get_main_menu())
        return
    
    status_msg = bot.reply_to(message, "🔄 _Searching for your account, please wait..._", parse_mode="Markdown")
    
    try:
        client_data, matched_phone = find_client_by_phone(clean_input)
        if not client_data:
            bot.delete_message(message.chat.id, status_msg.message_id)
            bot.send_message(message.chat.id, "❌ **Access Denied!**\n\nThis number is not registered in our system.\n\n" + f"👨‍💼 **Owner:** {OWNER_NAME}\n📞 **Contact:** {OWNER_PHONE}\n\n💻 _System by: Khalid Ali Pechuha_", parse_mode="Markdown", reply_markup=get_main_menu())
            return
        
        # --- Extract repaired data ---
        name = client_data.get('name', 'N/A')
        package = client_data.get('package', 'N/A')
        package_amount = client_data.get('packageAmount', 0)
        address = client_data.get('address', 'N/A')
        status = client_data.get('status', 'UNPAID')
        join_date = client_data.get('joinDate', 'N/A')
        vlan_id = client_data.get('vlanId')
        if not vlan_id:
            vlan_id = "Not Assigned"
        old_bill = client_data.get('oldBill', 0)
        total_bill = client_data.get('totalBill', 0)
        total_paid = client_data.get('totalPaid', 0)
        last_payment_date = client_data.get('lastPaymentDate', 'N/A')
        next_due = client_data.get('nextDueDate', 'N/A')
        
        # --- Build the response exactly as per template ---
        response = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ **ACCOUNT VERIFIED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👤 Name: " + name + "\n"
            "📞 Phone: " + matched_phone + "\n"
            "📍 Address: " + address + "\n"
            "📅 Join Date: " + join_date + "\n"
            "🔢 VLAN ID: " + vlan_id + "\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 Package: " + package + "\n"
            "💵 Monthly Fee: Rs. " + f"{package_amount:,}" + "\n"
            "📊 Status: " + ("✅ PAID" if status.upper() == "PAID" else "⚠️ UNPAID") + "\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💰 BILLING SUMMARY\n\n"
            "💳 Total Bill: Rs. " + f"{total_bill:,}" + "\n"
            "💵 Total Paid: Rs. " + f"{total_paid:,}" + "\n"
        )
        
        # Outstanding line
        if old_bill == 0:
            response += "✅ Outstanding Balance: Rs. 0 (Fully Paid)\n"
        else:
            response += "⚠️ Outstanding Balance: Rs. " + f"{old_bill:,}" + "\n"
        
        response += "📆 Last Payment: " + last_payment_date + "\n"
        
        # Add Due Date only if UNPAID
        if status.upper() != "PAID" and next_due != "N/A":
            response += "📅 Due Date: " + next_due + "\n"
        
        response += (
            "\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👨‍💼 ISP INFORMATION\n\n"
            "👤 Owner: " + OWNER_NAME + "\n"
            "📞 Contact: " + OWNER_PHONE + "\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🙏 Thank you for choosing\n"
            "🌐 D3 Crown Fiber Internet\n\n"
            "💻 System by: Khalid Ali Pechuha\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        # Inline keyboard
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("🧾 Download Premium Receipt", callback_data=f"receipt_{matched_phone}"),
            InlineKeyboardButton("📊 Payment History", callback_data=f"history_{matched_phone}")
        )
        keyboard.add(
            InlineKeyboardButton("📋 Package Details", callback_data="package_details"),
            InlineKeyboardButton("📤 Share Result", callback_data=f"share_{matched_phone}")
        )
        keyboard.add(
            InlineKeyboardButton("🆘 Support", callback_data="contact_support"),
            InlineKeyboardButton("❌ Close", callback_data="close_bot")
        )
        
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, response, parse_mode="Markdown", reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in verify_client: {e}")
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, f"⚠️ **Technical Error**\n\nSomething went wrong. Please try again later.\n\n👨‍💼 **Contact Owner:** {OWNER_PHONE}\n💻 _System by: Khalid Ali Pechuha_", reply_markup=get_main_menu())

# ============================================================
# 13. CALLBACK HANDLERS
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    try:
        if call.data.startswith("receipt_"):
            phone = call.data.replace("receipt_", "")
            bot.answer_callback_query(call.id, "🧾 Generating premium receipt...")
            client_data, _ = find_client_by_phone(phone)
            if client_data:
                is_paid = client_data.get('status', '').upper() == "PAID"
                img_bytes, receipt_id = generate_professional_receipt(client_data, is_paid)
                if img_bytes:
                    caption = f"🧾 **Premium Receipt #{receipt_id}**\n"
                    caption += f"👤 {client_data.get('name', 'N/A')}\n"
                    caption += f"📞 {client_data.get('phone', 'N/A')}\n"
                    caption += f"📊 Status: {'✅ PAID' if is_paid else '❌ UNPAID'}\n"
                    caption += f"💰 Outstanding: Rs.{client_data.get('oldBill', 0):,}\n"
                    caption += "━━━━━━━━━━━━━━━━━━━━━━\n"
                    caption += "✨ _Canva-Quality Design_\n"
                    caption += "💻 _System by: Khalid Ali Pechuha_"
                    bot.send_photo(call.message.chat.id, img_bytes, caption=caption, parse_mode="Markdown")
                else:
                    bot.send_message(call.message.chat.id, "❌ Error generating premium receipt.")
            else:
                bot.send_message(call.message.chat.id, "❌ Client data not found.")
        
        elif call.data.startswith("history_"):
            phone = call.data.replace("history_", "")
            bot.answer_callback_query(call.id, "📊 Fetching payment history...")
            client_data, _ = find_client_by_phone(phone)
            if client_data:
                payment_history = client_data.get('paymentHistory', [])
                history_msg = format_payment_history(payment_history)
                bot.send_message(call.message.chat.id, history_msg, parse_mode="Markdown")
            else:
                bot.send_message(call.message.chat.id, "❌ Client data not found.")
        
        elif call.data.startswith("share_"):
            phone = call.data.replace("share_", "")
            bot.answer_callback_query(call.id, "📤 Share result...")
            client_data, matched_phone = find_client_by_phone(phone)
            if client_data:
                share_text = share_result_text(client_data, matched_phone)
                share_keyboard = InlineKeyboardMarkup(row_width=1)
                share_keyboard.add(InlineKeyboardButton("📤 Share on WhatsApp", url=f"https://wa.me/?text={requests.utils.quote(share_text)}"))
                share_keyboard.add(InlineKeyboardButton("📋 Copy Text", callback_data=f"copy_{phone}"))
                bot.send_message(call.message.chat.id, "📤 **Share Account Details**\n━━━━━━━━━━━━━━━━━━━━━━\nClick the button below to share on WhatsApp\nor copy the text to share anywhere.\n\n💻 _System by: Khalid Ali Pechuha_", parse_mode="Markdown", reply_markup=share_keyboard)
            else:
                bot.send_message(call.message.chat.id, "❌ Client data not found.")
        
        elif call.data.startswith("copy_"):
            phone = call.data.replace("copy_", "")
            client_data, matched_phone = find_client_by_phone(phone)
            if client_data:
                share_text = share_result_text(client_data, matched_phone)
                bot.send_message(call.message.chat.id, f"📋 **Copy this text:**\n\n{share_text}\n\n💻 _System by: Khalid Ali Pechuha_", parse_mode="Markdown")
            else:
                bot.send_message(call.message.chat.id, "❌ Client data not found.")
        
        elif call.data == "package_details":
            bot.answer_callback_query(call.id, "📋 Showing package details")
            package_msg = (
                "📋 **D3 CROWN PACKAGES**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "💠 **DHCP-4Mbps** → Rs. 1,800/mo\n"
                "💠 **DHCP-6Mbps** → Rs. 2,100/mo\n"
                "💠 **DHCP-8Mbps** → Rs. 2,300/mo\n"
                "💠 **DHCP-10Mbps** → Rs. 2,600/mo\n"
                "💠 **DHCP-12Mbps** → Rs. 3,000/mo\n"
                "💠 **DHCP-15Mbps** → Rs. 3,500/mo\n"
                "💠 **DHCP-20Mbps** → Rs. 4,500/mo\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔄 _Package upgrade ke liye support se rabta karein_\n\n"
                f"📞 **Support:** {OWNER_PHONE}\n"
                "💻 _System by: Khalid Ali Pechuha_"
            )
            bot.send_message(call.message.chat.id, package_msg, parse_mode="Markdown")
        
        elif call.data == "contact_support":
            bot.answer_callback_query(call.id, "📞 Opening support")
            support_msg = (
                "🆘 **D3 CROWN SUPPORT**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📞 **Helpline:** {OWNER_PHONE}\n"
                f"📧 **Email:** {OWNER_EMAIL}\n"
                f"💬 **WhatsApp:** [Click to Chat](https://wa.me/92{OWNER_WHATSAPP})\n"
                f"🕐 **Response Time:** 24/7\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👨‍💼 **Owner:** {OWNER_NAME}\n"
                f"📞 **Contact:** {OWNER_PHONE}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "💻 _System by: Khalid Ali Pechuha_"
            )
            bot.send_message(call.message.chat.id, support_msg, parse_mode="Markdown", disable_web_page_preview=True)
        
        elif call.data == "close_bot":
            bot.answer_callback_query(call.id, "👋 Closing bot...")
            exit_msg = (
                "👋 **Thank you for using D3 CROWN ISP!**\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "اللہ حافظ! 🤲\n"
                "✅ Bot session closed successfully.\n\n"
                "🔄 To restart, type /start\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "💻 _System by: Khalid Ali Pechuha_"
            )
            bot.edit_message_text(exit_msg, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=None)
            bot.send_message(call.message.chat.id, "👋 Goodbye! Type /start to use again.", reply_markup=telebot.types.ReplyKeyboardRemove())
        
        else:
            bot.answer_callback_query(call.id, "⚠️ Unknown command")
            
    except Exception as e:
        logger.error(f"Error in callback: {e}")
        bot.answer_callback_query(call.id, "⚠️ Error processing request")

# ============================================================
# 14. RUN BOT
# ============================================================
if __name__ == "__main__":
    logger.info("🏢 D3 CROWN ISP Bot Starting...")
    logger.info(f"👨‍💼 Owner: {OWNER_NAME}")
    logger.info(f"📞 Owner Phone: {OWNER_PHONE}")
    logger.info("✅ Bot Token Loaded")
    try:
        bot.infinity_polling(skip_pending=True, timeout=60)
    except Exception as e:
        logger.error(f"❌ Bot Error: {e}")
