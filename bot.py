import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import requests
import json
import time
from datetime import datetime
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import random
import logging
import os
import qrcode
from functools import wraps

# --- 1. LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- 2. BOT SETUP ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8551239286:AAEd8gIDuF3GkjA9hJgoSwI405_CrWoM6X4")
bot = telebot.TeleBot(BOT_TOKEN)

# --- 3. FIREBASE SETUP ---
FIREBASE_URL = os.getenv("FIREBASE_URL", "https://d3crown-805ce-default-rtdb.firebaseio.com/d3_clients/0rulvawKt1d6M3FlxfEariNOukk1/clients.json")

# --- 4. OWNER INFORMATION ---
OWNER_NAME = "Shahid Ali Abro"
OWNER_PHONE = "03052848369"
OWNER_EMAIL = "aliabro104@gmail.com"
OWNER_WHATSAPP = "03052848369"

# --- 5. RETRY DECORATOR ---
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

# --- 6. PROFESSIONAL RECEIPT GENERATION (CANVA-QUALITY) ---

def generate_qr_code(data):
    """Generate QR code for receipt verification"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=3,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="#1a237e", back_color="white")
        
        # Convert to PIL Image
        qr_byte_arr = io.BytesIO()
        qr_img.save(qr_byte_arr, format='PNG')
        qr_byte_arr.seek(0)
        return Image.open(qr_byte_arr)
    except Exception as e:
        logger.error(f"QR generation error: {e}")
        return None

def generate_professional_receipt(client_data, is_paid=False):
    """Generate Canva-quality premium receipt with glassmorphism design"""
    try:
        # Canvas size
        width = 1080
        height = 1600
        
        # Create canvas
        image = Image.new('RGB', (width, height), color='#f0f4f8')
        draw = ImageDraw.Draw(image)
        
        # --- 1. BACKGROUND GRADIENT ---
        # Create gradient background
        for i in range(height):
            ratio = i / height
            r = int(240 - 60 * ratio)
            g = int(244 - 70 * ratio)
            b = int(248 - 80 * ratio)
            draw.line([(0, i), (width, i)], fill=(r, g, b))
        
        # --- 2. TOP HEADER (Glassmorphism) ---
        header_y = 20
        header_height = 220
        
        # Glass effect - semi-transparent
        glass_color = (26, 35, 126, 230)  # rgba
        draw.rectangle(
            [(30, header_y), (width - 30, header_y + header_height)],
            fill=(26, 35, 126),
            outline=(255, 255, 255, 50),
            width=2
        )
        
        # Inner glow
        draw.rectangle(
            [(40, header_y + 10), (width - 40, header_y + header_height - 10)],
            fill=(40, 53, 147, 50),
            outline=None
        )
        
        # --- 3. COMPANY LOGO (Text-based) ---
        try:
            font_logo = ImageFont.truetype("arial.ttf", 52)
            font_sub = ImageFont.truetype("arial.ttf", 24)
            font_bold = ImageFont.truetype("arialbd.ttf", 36)
            font_normal = ImageFont.truetype("arial.ttf", 20)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except:
            font_logo = ImageFont.load_default()
            font_sub = ImageFont.load_default()
            font_bold = ImageFont.load_default()
            font_normal = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Company Name with shadow
        shadow_offset = 3
        draw.text(
            (width//2 - 130 + shadow_offset, header_y + 40 + shadow_offset),
            "D3 CROWN",
            fill=(0, 0, 0, 100),
            font=font_logo
        )
        draw.text(
            (width//2 - 130, header_y + 40),
            "D3 CROWN",
            fill='#ffffff',
            font=font_logo
        )
        
        # Subtitle
        draw.text(
            (width//2 - 110, header_y + 100),
            "FLASH FIBER ISP",
            fill='#e0e0e0',
            font=font_sub
        )
        draw.text(
            (width//2 - 95, header_y + 130),
            "Private Limited ™",
            fill='#ffd700',
            font=font_small
        )
        
        # --- 4. STATUS BADGE (Premium Pill Shape) ---
        status_text = "PAID ✓" if is_paid else "UNPAID ✗"
        status_color = "#2e7d32" if is_paid else "#c62828"
        badge_width = 180
        badge_height = 50
        badge_x = width//2 - badge_width//2
        badge_y = header_y + header_height - 60
        
        # Badge background
        draw.rectangle(
            [(badge_x, badge_y), (badge_x + badge_width, badge_y + badge_height)],
            fill=status_color,
            outline='#ffffff',
            width=2
        )
        # Badge text
        draw.text(
            (width//2 - 70, badge_y + 12),
            status_text,
            fill='#ffffff',
            font=font_bold
        )
        
        # --- 5. RECEIPT CONTENT (Glassmorphism Card) ---
        card_y = header_y + header_height + 30
        card_height = height - card_y - 40
        
        # Card background (glass effect)
        draw.rectangle(
            [(30, card_y), (width - 30, card_y + card_height)],
            fill=(255, 255, 255, 240),
            outline=(255, 255, 255, 100),
            width=2
        )
        
        # Card inner shadow
        draw.rectangle(
            [(40, card_y + 10), (width - 40, card_y + card_height - 10)],
            fill=(240, 248, 255, 50)
        )
        
        # --- 6. RECEIPT HEADER ---
        y = card_y + 30
        
        # Receipt ID
        receipt_id = f"D3-{datetime.now().strftime('%y%m%d')}-{random.randint(100000, 999999)}"
        draw.text(
            (60, y),
            "RECEIPT #",
            fill='#666',
            font=font_small
        )
        draw.text(
            (200, y),
            receipt_id,
            fill='#1a237e',
            font=font_bold
        )
        
        # Date
        draw.text(
            (60, y + 35),
            "DATE & TIME",
            fill='#666',
            font=font_small
        )
        draw.text(
            (200, y + 35),
            datetime.now().strftime('%d %B %Y %I:%M %p'),
            fill='#1a237e',
            font=font_normal
        )
        
        y += 80
        
        # --- 7. DIVIDER ---
        draw.line([(60, y), (width - 60, y)], fill='#e0e0e0', width=2)
        y += 20
        
        # --- 8. CUSTOMER INFORMATION (Rounded Box) ---
        box_y = y
        box_height = 180
        draw.rectangle(
            [(60, box_y), (width - 60, box_y + box_height)],
            fill='#f8f9fa',
            outline='#e0e0e0',
            width=1
        )
        
        draw.text(
            (80, box_y + 15),
            "👤 CUSTOMER INFORMATION",
            fill='#1a237e',
            font=font_bold
        )
        
        customer_fields = [
            ("Name", client_data.get('name', 'N/A')),
            ("Phone", client_data.get('phone', 'N/A')),
            ("Address", client_data.get('address', 'N/A')),
            ("VLAN ID", client_data.get('vlanId', 'N/A'))
        ]
        
        y = box_y + 50
        for label, value in customer_fields:
            draw.text(
                (80, y),
                label + ":",
                fill='#666',
                font=font_normal
            )
            draw.text(
                (220, y),
                value,
                fill='#1a237e',
                font=font_normal
            )
            y += 35
        
        y = box_y + box_height + 20
        
        # --- 9. PACKAGE DETAILS ---
        draw.rectangle(
            [(60, y), (width - 60, y + 140)],
            fill='#f8f9fa',
            outline='#e0e0e0',
            width=1
        )
        
        draw.text(
            (80, y + 15),
            "📦 PACKAGE DETAILS",
            fill='#1a237e',
            font=font_bold
        )
        
        package_fields = [
            ("Package", client_data.get('package', 'N/A')),
            ("Speed", client_data.get('package', 'N/A').replace('DHCP-', '')),
            ("Monthly Fee", f"Rs. {client_data.get('packageAmount', 0):,}"),
            ("Start Date", client_data.get('packageStartDate', 'N/A'))
        ]
        
        y = y + 50
        for label, value in package_fields:
            draw.text(
                (80, y),
                label + ":",
                fill='#666',
                font=font_normal
            )
            draw.text(
                (220, y),
                value,
                fill='#1a237e',
                font=font_normal
            )
            y += 30
        
        y = y + 20
        
        # --- 10. BILLING SUMMARY (Gradient Box) ---
        amount = client_data.get('packageAmount', 0)
        old_bill = client_data.get('oldBill', 0)
        total_bill = amount + old_bill
        paid_amount = 0
        
        payment_history = client_data.get('paymentHistory', [])
        if payment_history and len(payment_history) > 0:
            for entry in payment_history:
                paid_amount += entry.get('credit', 0)
        
        remaining = total_bill - paid_amount
        
        # Billing box with gradient
        billing_y = y
        billing_height = 200
        draw.rectangle(
            [(60, billing_y), (width - 60, billing_y + billing_height)],
            fill='#1a237e',
            outline='#1a237e',
            width=1
        )
        
        draw.text(
            (80, billing_y + 15),
            "💰 BILLING SUMMARY",
            fill='#ffffff',
            font=font_bold
        )
        
        billing_fields = [
            ("Previous Balance", f"Rs. {old_bill:,}"),
            ("Current Bill", f"Rs. {amount:,}"),
            ("Total Bill", f"Rs. {total_bill:,}"),
            ("Total Paid", f"Rs. {paid_amount:,}"),
            ("Remaining Balance", f"Rs. {remaining:,}")
        ]
        
        y = billing_y + 50
        for label, value in billing_fields:
            draw.text(
                (80, y),
                label + ":",
                fill='#e0e0e0',
                font=font_normal
            )
            
            # Highlight colors for important fields
            if label == "Remaining Balance" and remaining > 0:
                text_color = '#ff6b6b'
            elif label == "Total Paid" and paid_amount > 0:
                text_color = '#69db7c'
            else:
                text_color = '#ffffff'
            
            draw.text(
                (250, y),
                value,
                fill=text_color,
                font=font_bold if label in ["Total Paid", "Remaining Balance"] else font_normal
            )
            y += 30
        
        y = billing_y + billing_height + 20
        
        # --- 11. TOTAL PAID SECTION ---
        draw.rectangle(
            [(60, y), (width - 60, y + 60)],
            fill='#2e7d32' if paid_amount > 0 else '#c62828',
            outline=None,
            width=0
        )
        
        draw.text(
            (80, y + 15),
            "TOTAL PAID",
            fill='#ffffff',
            font=font_bold
        )
        draw.text(
            (250, y + 15),
            f"Rs. {paid_amount:,}" if paid_amount > 0 else "Rs. 0",
            fill='#ffffff',
            font=font_bold
        )
        
        if paid_amount == 0:
            draw.text(
                (80, y + 40),
                "No payment recorded yet.",
                fill='#ffcdd2',
                font=font_small
            )
        
        y = y + 80
        
        # --- 12. QR CODE FOR VERIFICATION ---
        qr_data = f"D3CROWN|{receipt_id}|{client_data.get('phone', 'N/A')}|{datetime.now().strftime('%Y%m%d')}"
        qr_img = generate_qr_code(qr_data)
        
        if qr_img:
            qr_size = 120
            qr_img = qr_img.resize((qr_size, qr_size))
            image.paste(qr_img, (width - 180, y))
            
            draw.text(
                (width - 210, y + qr_size + 10),
                "Scan to Verify",
                fill='#666',
                font=font_small
            )
        
        # --- 13. FOOTER ---
        y = height - 120
        
        # Divider
        draw.line([(60, y), (width - 60, y)], fill='#e0e0e0', width=2)
        y += 20
        
        draw.text(
            (width//2 - 120, y),
            "Speed Ka Naya Andaaz!",
            fill='#1a237e',
            font=font_bold
        )
        
        y += 40
        draw.text(
            (width//2 - 140, y),
            f"📞 {OWNER_PHONE} | 📧 {OWNER_EMAIL}",
            fill='#666',
            font=font_small
        )
        y += 25
        draw.text(
            (width//2 - 130, y),
            "D3 Crown Fiber — Connecting You to Excellence",
            fill='#666',
            font=font_small
        )
        y += 25
        draw.text(
            (width//2 - 80, y),
            "- System Generated Receipt -",
            fill='#999',
            font=font_small
        )
        
        # --- 14. WATERMARK ---
        draw.text(
            (width//2 - 200, height//2),
            "D3 CROWN",
            fill=(200, 200, 200, 30),
            font=font_logo
        )
        
        # --- 15. SAVE IMAGE ---
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=95)
        img_byte_arr.seek(0)
        
        return img_byte_arr, receipt_id
        
    except Exception as e:
        logger.error(f"Error generating premium receipt: {e}")
        return None, None

# --- 7. REST OF THE CODE (Same as before) ---

def find_client_by_phone(phone_number):
    """Search for client by phone number"""
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
            
            client_phone = client.get('phone', '')
            client_phone = str(client_phone).replace('+', '').replace('-', '').replace(' ', '').strip()
            
            if client_phone == clean_phone:
                return client, client_phone
            
            if len(client_phone) >= 10 and len(clean_phone) >= 10:
                if client_phone[-10:] == clean_phone[-10:]:
                    return client, client_phone
        
        return None, None
        
    except Exception as e:
        logger.error(f"Error in find_client: {e}")
        return None, None

def format_payment_history(payment_history, limit=5):
    """Format payment history"""
    if not payment_history or len(payment_history) == 0:
        return "📊 No payment history available."
    
    history_msg = "📊 **PAYMENT HISTORY**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    recent_payments = payment_history[-limit:] if len(payment_history) > limit else payment_history
    
    for entry in reversed(recent_payments):
        date = entry.get('date', 'N/A')
        debit = entry.get('debit', 0)
        credit = entry.get('credit', 0)
        description = entry.get('description', '')
        entry_id = entry.get('entryId', '')
        
        if debit > 0:
            history_msg += f"💰 **{date}**\n   💸 Debit: Rs.{debit:,}\n"
        if credit > 0:
            history_msg += f"💰 **{date}**\n   💳 Credit: Rs.{credit:,}\n"
        if description:
            history_msg += f"   📝 {description}\n"
        if entry_id:
            history_msg += f"   🆔 {entry_id}\n"
        history_msg += "\n"
    
    if len(payment_history) > limit:
        history_msg += f"\n_Showing last {limit} of {len(payment_history)} entries_"
    
    return history_msg

def share_result_text(client_data, matched_phone):
    """Generate shareable text"""
    name = client_data.get('name', 'N/A')
    package = client_data.get('package', 'N/A')
    amount = client_data.get('packageAmount', 0)
    status = client_data.get('status', 'active')
    address = client_data.get('address', 'N/A')
    vlan_id = client_data.get('vlanId', 'N/A')
    
    return (
        f"🏢 *D3 CROWN FIBER - Account Details*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Name:* {name}\n"
        f"📞 *Phone:* {matched_phone}\n"
        f"📦 *Package:* {package}\n"
        f"💰 *Amount:* Rs.{amount:,}\n"
        f"📊 *Status:* {status.upper()}\n"
        f"📍 *Address:* {address}\n"
        f"🔢 *VLAN ID:* {vlan_id}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💻 _System by: Khalid Ali Pechuha_"
    )

# --- 8. MAIN MENU ---
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

# --- 9. BOT HANDLERS (Same as before) ---
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
    bot.reply_to(
        message,
        "📱 **Please send your registered phone number**\n"
        "Example: 03001234567\n\n"
        "💻 _System by: Khalid Ali Pechuha_",
        parse_mode="Markdown"
    )

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
    bot.reply_to(
        message,
        "📤 **Please send your registered phone number**\n"
        "to share account details on WhatsApp.\n\n"
        "Example: 03001234567\n\n"
        "💻 _System by: Khalid Ali Pechuha_",
        parse_mode="Markdown"
    )

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
    bot.reply_to(
        message,
        support_msg,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=get_main_menu()
    )

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
    bot.send_message(
        message.chat.id,
        "👋 Goodbye!",
        reply_markup=telebot.types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda msg: True)
def verify_client(message):
    user_input = message.text.strip()
    
    clean_input = user_input.replace('+', '').replace('-', '').replace(' ', '').strip()
    if not clean_input.isdigit() or len(clean_input) < 10:
        bot.reply_to(
            message,
            "❌ **Invalid Format!**\n\n"
            "Please enter a valid mobile number with at least 10 digits.\n"
            "Example: 03001234567\n\n"
            "Or use the menu buttons below.\n"
            "💻 _System by: Khalid Ali Pechuha_",
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
        return
    
    status_msg = bot.reply_to(message, "🔄 _Searching for your account, please wait..._", parse_mode="Markdown")
    
    try:
        client_data, matched_phone = find_client_by_phone(clean_input)
        
        if not client_data:
            bot.delete_message(message.chat.id, status_msg.message_id)
            bot.send_message(
                message.chat.id,
                "❌ **Access Denied!**\n\n"
                "This number is not registered in our system.\n\n"
                f"👨‍💼 **Owner:** {OWNER_NAME}\n"
                f"📞 **Contact:** {OWNER_PHONE}\n\n"
                "💻 _System by: Khalid Ali Pechuha_",
                parse_mode="Markdown",
                reply_markup=get_main_menu()
            )
            return
        
        # Extract client information
        name = client_data.get('name', 'N/A')
        package = client_data.get('package', 'N/A')
        package_amount = client_data.get('packageAmount', 'N/A')
        address = client_data.get('address', 'N/A')
        status = client_data.get('status', 'active')
        join_date = client_data.get('joinDate', 'N/A')
        vlan_id = client_data.get('vlanId', 'N/A')
        old_bill = client_data.get('oldBill', 0)
        
        if package_amount == 'N/A':
            package_display = package
        else:
            package_display = f"{package} (Rs. {package_amount:,})"
        
        payment_history = client_data.get('paymentHistory', [])
        last_payment = "N/A"
        total_paid = 0
        if payment_history and isinstance(payment_history, list) and len(payment_history) > 0:
            last_entry = payment_history[-1]
            last_payment = f"{last_entry.get('date', 'N/A')} - Rs.{last_entry.get('debit', 0):,}"
            total_paid = sum(entry.get('credit', 0) for entry in payment_history)
        
        is_paid = total_paid > 0 or status.lower() == 'paid'
        
        response_msg = (
            "✅ **ACCOUNT VERIFIED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Name:** {name}\n"
            f"📞 **Phone:** {matched_phone}\n"
            f"📦 **Package:** {package_display}\n"
            f"📊 **Status:** {status.upper()}\n"
            f"📍 **Address:** {address}\n"
            f"📅 **Join Date:** {join_date}\n"
            f"🔢 **VLAN ID:** {vlan_id}\n"
            f"💰 **Old Bill:** Rs.{old_bill:,}\n"
            f"💳 **Last Payment:** {last_payment}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💼 **Owner:** {OWNER_NAME}\n"
            f"📞 **Contact:** {OWNER_PHONE}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💻 _System by: Khalid Ali Pechuha_"
        )
        
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
        bot.send_message(
            message.chat.id,
            response_msg,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in verify_client: {e}")
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(
            message.chat.id,
            f"⚠️ **Technical Error**\n\n"
            "Something went wrong. Please try again later.\n\n"
            f"👨‍💼 **Contact Owner:** {OWNER_PHONE}\n"
            "💻 _System by: Khalid Ali Pechuha_",
            reply_markup=get_main_menu()
        )

# --- 10. CALLBACK HANDLERS ---

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    try:
        if call.data.startswith("receipt_"):
            phone = call.data.replace("receipt_", "")
            bot.answer_callback_query(call.id, "🧾 Generating premium receipt...")
            
            client_data, _ = find_client_by_phone(phone)
            if client_data:
                payment_history = client_data.get('paymentHistory', [])
                total_paid = sum(entry.get('credit', 0) for entry in payment_history) if payment_history else 0
                is_paid = total_paid > 0 or client_data.get('status', '').lower() == 'paid'
                
                img_bytes, receipt_id = generate_professional_receipt(client_data, is_paid)
                if img_bytes:
                    caption = f"🧾 **Premium Receipt #{receipt_id}**\n"
                    caption += f"👤 {client_data.get('name', 'N/A')}\n"
                    caption += f"📞 {client_data.get('phone', 'N/A')}\n"
                    caption += f"📊 Status: {'✅ PAID' if is_paid else '❌ UNPAID'}\n"
                    caption += "━━━━━━━━━━━━━━━━━━━━━━\n"
                    caption += "✨ _Canva-Quality Design with QR Verification_\n"
                    caption += "💻 _System by: Khalid Ali Pechuha_"
                    
                    bot.send_photo(
                        call.message.chat.id,
                        img_bytes,
                        caption=caption,
                        parse_mode="Markdown"
                    )
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
                share_keyboard.add(
                    InlineKeyboardButton(
                        "📤 Share on WhatsApp",
                        url=f"https://wa.me/?text={requests.utils.quote(share_text)}"
                    )
                )
                share_keyboard.add(
                    InlineKeyboardButton("📋 Copy Text", callback_data=f"copy_{phone}")
                )
                
                bot.send_message(
                    call.message.chat.id,
                    "📤 **Share Account Details**\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Click the button below to share on WhatsApp\n"
                    "or copy the text to share anywhere.\n\n"
                    "💻 _System by: Khalid Ali Pechuha_",
                    parse_mode="Markdown",
                    reply_markup=share_keyboard
                )
            else:
                bot.send_message(call.message.chat.id, "❌ Client data not found.")
        
        elif call.data.startswith("copy_"):
            phone = call.data.replace("copy_", "")
            client_data, matched_phone = find_client_by_phone(phone)
            if client_data:
                share_text = share_result_text(client_data, matched_phone)
                bot.send_message(
                    call.message.chat.id,
                    f"📋 **Copy this text:**\n\n{share_text}\n\n"
                    "💻 _System by: Khalid Ali Pechuha_",
                    parse_mode="Markdown"
                )
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
            bot.send_message(
                call.message.chat.id,
                support_msg,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        
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
            bot.edit_message_text(
                exit_msg,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
                reply_markup=None
            )
            bot.send_message(
                call.message.chat.id,
                "👋 Goodbye! Type /start to use again.",
                reply_markup=telebot.types.ReplyKeyboardRemove()
            )
        
        else:
            bot.answer_callback_query(call.id, "⚠️ Unknown command")
            
    except Exception as e:
        logger.error(f"Error in callback: {e}")
        bot.answer_callback_query(call.id, "⚠️ Error processing request")

# --- 11. RUN BOT ---
if __name__ == "__main__":
    logger.info("🏢 D3 CROWN ISP Bot Starting...")
    logger.info(f"👨‍💼 Owner: {OWNER_NAME}")
    logger.info(f"📞 Owner Phone: {OWNER_PHONE}")
    logger.info("✅ Bot Token Loaded")
    
    try:
        bot.infinity_polling(skip_pending=True, timeout=60)
    except Exception as e:
        logger.error(f"❌ Bot Error: {e}")
