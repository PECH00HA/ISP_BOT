# ... (all your imports, logging, bot setup, Firebase, owner info,
#      billing_repair_engine, sync_client_to_firebase, receipt generation,
#      find_client_by_phone, etc. – keep them exactly as you had)

# --- 11. BOT HANDLERS (only the verify_client function is changed) ---

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
        
        # Determine status emoji and text
        if status.upper() == "PAID":
            status_display = "✅ PAID"
        else:
            status_display = "⚠️ UNPAID"
        
        # Outstanding balance display
        if old_bill == 0:
            outstanding_display = f"✅ Rs. 0 (Fully Paid)"
        else:
            outstanding_display = f"⚠️ Rs. {old_bill:,}"
        
        # Build the formatted response
        response_msg = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ **ACCOUNT VERIFIED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👤 **Customer Details**\n"
            f"• Name: {name}\n"
            f"• Phone: {matched_phone}\n"
            f"• Address: {address}\n"
            f"• Join Date: {join_date}\n"
            f"• VLAN ID: {vlan_id}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📦 **Internet Package**\n"
            f"• Package: {package}\n"
            f"• Monthly Fee: Rs. {package_amount:,}\n"
            f"• Status: {status_display}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💰 **Billing Summary**\n"
            f"• Total Bill: Rs. {total_bill:,}\n"
            f"• Total Paid: Rs. {total_paid:,}\n"
            f"• Outstanding Balance: {outstanding_display}\n"
            f"• Last Payment: {last_payment_date}\n"
            f"• Next Due: {next_due}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "👨‍💼 **ISP Information**\n"
            f"• Owner: {OWNER_NAME}\n"
            f"• Contact: {OWNER_PHONE}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💻 Powered by Khalid Ali Pechuha\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        # Inline keyboard (same as before)
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
        bot.send_message(message.chat.id, response_msg, parse_mode="Markdown", reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Error in verify_client: {e}")
        bot.delete_message(message.chat.id, status_msg.message_id)
        bot.send_message(message.chat.id, f"⚠️ **Technical Error**\n\nSomething went wrong. Please try again later.\n\n👨‍💼 **Contact Owner:** {OWNER_PHONE}\n💻 _System by: Khalid Ali Pechuha_", reply_markup=get_main_menu())
