import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from flask import Flask
import threading

# ─── CONFIG ───────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7458894503:AAHwCdLgWV3NlNB1OuCnMzxq3fdiT0ZzxMs")
ADMIN_ID   = int(os.environ.get("ADMIN_ID", "2077682354"))  # e.g. 123456789
PORT       = int(os.environ.get("PORT", 8080))
# ──────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Flask keep-alive (required by Render) ─────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "MODKING Contact Bot is running ✅"

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

# ── Helpers ───────────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def admin_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📋 All Users",      callback_data="cmd_users"),
            InlineKeyboardButton("📢 Broadcast",      callback_data="cmd_broadcast"),
        ],
        [
            InlineKeyboardButton("🚫 Ban User",       callback_data="cmd_ban"),
            InlineKeyboardButton("✅ Unban User",     callback_data="cmd_unban"),
        ],
        [
            InlineKeyboardButton("📊 Bot Stats",      callback_data="cmd_stats"),
            InlineKeyboardButton("🔔 Toggle Notify",  callback_data="cmd_toggle_notify"),
        ],
        [
            InlineKeyboardButton("❓ Help",           callback_data="cmd_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

# Shared state
state = {
    "users": {},        # {user_id: {"name": ..., "username": ..., "banned": False}}
    "notify": True,     # forward user msgs to admin?
    "broadcast_mode": False,
    "ban_mode": False,
    "unban_mode": False,
}

# ── /start ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = user.id

    # Register user
    if uid != ADMIN_ID:
        state["users"][uid] = {
            "name":     user.full_name,
            "username": user.username or "N/A",
            "banned":   state["users"].get(uid, {}).get("banned", False),
        }

    if is_admin(uid):
        await update.message.reply_text(
            "👑 *Welcome Admin!*\n\nUse the buttons below to manage the bot.",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )
    else:
        await update.message.reply_text(
            f"👋 Hello *{user.first_name}*!\n\n"
            "Send me any message and the admin will receive it.",
            parse_mode="Markdown"
        )

# ── /panel (admin shortcut) ───────────────────────────────
async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🛠 *Admin Panel*", parse_mode="Markdown",
        reply_markup=admin_keyboard()
    )

# ── Handle user messages → forward to admin ───────────────
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = user.id

    if is_admin(uid):
        # Admin typed something outside button flow
        await handle_admin_text(update, context)
        return

    # Register if new
    if uid not in state["users"]:
        state["users"][uid] = {
            "name":     user.full_name,
            "username": user.username or "N/A",
            "banned":   False,
        }

    if state["users"][uid]["banned"]:
        await update.message.reply_text("🚫 You are banned from using this bot.")
        return

    if not state["notify"]:
        await update.message.reply_text("✅ Message noted! Admin will reply soon.")
        return

    # Forward to admin
    header = (
        f"📩 *New Message*\n"
        f"👤 Name: {user.full_name}\n"
        f"🔖 Username: @{user.username or 'N/A'}\n"
        f"🆔 ID: `{uid}`\n"
        f"─────────────────\n"
    )
    reply_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"↩️ Reply to {user.first_name}", callback_data=f"reply_{uid}")
    ]])

    try:
        await context.bot.send_message(ADMIN_ID, header, parse_mode="Markdown", reply_markup=reply_kb)
        await update.message.forward(ADMIN_ID)
        await update.message.reply_text("✅ Your message has been sent to the admin!")
    except Exception as e:
        logger.error(f"Forward error: {e}")

# ── Admin text handler (for broadcast / ban / reply) ──────
async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if state.get("broadcast_mode"):
        state["broadcast_mode"] = False
        count = 0
        for uid, info in state["users"].items():
            if not info["banned"]:
                try:
                    await context.bot.send_message(uid, f"📢 *Broadcast:*\n\n{text}", parse_mode="Markdown")
                    count += 1
                except:
                    pass
        await update.message.reply_text(f"📢 Broadcast sent to {count} users.", reply_markup=admin_keyboard())

    elif state.get("ban_mode"):
        state["ban_mode"] = False
        try:
            uid = int(text.strip())
            if uid in state["users"]:
                state["users"][uid]["banned"] = True
                await update.message.reply_text(f"🚫 User `{uid}` has been banned.", parse_mode="Markdown", reply_markup=admin_keyboard())
            else:
                await update.message.reply_text("❌ User ID not found.", reply_markup=admin_keyboard())
        except ValueError:
            await update.message.reply_text("❌ Invalid ID. Send a number.", reply_markup=admin_keyboard())

    elif state.get("unban_mode"):
        state["unban_mode"] = False
        try:
            uid = int(text.strip())
            if uid in state["users"]:
                state["users"][uid]["banned"] = False
                await update.message.reply_text(f"✅ User `{uid}` has been unbanned.", parse_mode="Markdown", reply_markup=admin_keyboard())
            else:
                await update.message.reply_text("❌ User ID not found.", reply_markup=admin_keyboard())
        except ValueError:
            await update.message.reply_text("❌ Invalid ID. Send a number.", reply_markup=admin_keyboard())

    elif context.user_data.get("reply_to"):
        target_uid = context.user_data.pop("reply_to")
        try:
            await context.bot.send_message(target_uid, f"📬 *Admin Reply:*\n\n{text}", parse_mode="Markdown")
            await update.message.reply_text("✅ Reply sent!", reply_markup=admin_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Failed: {e}", reply_markup=admin_keyboard())
    else:
        await update.message.reply_text("Use the panel buttons 👇", reply_markup=admin_keyboard())

# ── Button callbacks ───────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    uid   = query.from_user.id

    if not is_admin(uid):
        await query.answer("⛔ Admin only!", show_alert=True)
        return

    if data == "cmd_users":
        if not state["users"]:
            msg = "👥 *No users yet.*"
        else:
            lines = ["👥 *Registered Users:*\n"]
            for i, (u_id, info) in enumerate(state["users"].items(), 1):
                status = "🚫 Banned" if info["banned"] else "✅ Active"
                lines.append(f"{i}. {info['name']} | @{info['username']} | `{u_id}` | {status}")
            msg = "\n".join(lines)
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=admin_keyboard())

    elif data == "cmd_broadcast":
        state["broadcast_mode"] = True
        state["ban_mode"]       = False
        state["unban_mode"]     = False
        await query.edit_message_text("📢 *Broadcast Mode*\n\nSend the message to broadcast to all users:", parse_mode="Markdown")

    elif data == "cmd_ban":
        state["ban_mode"]       = True
        state["broadcast_mode"] = False
        state["unban_mode"]     = False
        await query.edit_message_text("🚫 *Ban User*\n\nSend the user's Telegram ID:", parse_mode="Markdown")

    elif data == "cmd_unban":
        state["unban_mode"]     = True
        state["broadcast_mode"] = False
        state["ban_mode"]       = False
        await query.edit_message_text("✅ *Unban User*\n\nSend the user's Telegram ID:", parse_mode="Markdown")

    elif data == "cmd_stats":
        total  = len(state["users"])
        banned = sum(1 for u in state["users"].values() if u["banned"])
        active = total - banned
        notify = "🟢 ON" if state["notify"] else "🔴 OFF"
        msg = (
            f"📊 *Bot Statistics*\n\n"
            f"👥 Total Users : {total}\n"
            f"✅ Active      : {active}\n"
            f"🚫 Banned      : {banned}\n"
            f"🔔 Notify      : {notify}"
        )
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=admin_keyboard())

    elif data == "cmd_toggle_notify":
        state["notify"] = not state["notify"]
        status = "🟢 ON" if state["notify"] else "🔴 OFF"
        await query.edit_message_text(
            f"🔔 Notifications are now *{status}*",
            parse_mode="Markdown", reply_markup=admin_keyboard()
        )

    elif data == "cmd_help":
        help_text = (
            "❓ *Admin Commands Help*\n\n"
            "📋 *All Users* — List all registered users\n"
            "📢 *Broadcast* — Send a message to all users\n"
            "🚫 *Ban User* — Ban a user by ID\n"
            "✅ *Unban User* — Unban a user by ID\n"
            "📊 *Bot Stats* — View bot statistics\n"
            "🔔 *Toggle Notify* — Turn message forwarding on/off\n\n"
            "💡 Users can message the bot and you'll receive it here with a Reply button."
        )
        await query.edit_message_text(help_text, parse_mode="Markdown", reply_markup=admin_keyboard())

    elif data.startswith("reply_"):
        target_uid = int(data.split("_")[1])
        context.user_data["reply_to"] = target_uid
        name = state["users"].get(target_uid, {}).get("name", str(target_uid))
        await query.edit_message_text(
            f"↩️ *Reply to {name}*\n\nType your reply message:",
            parse_mode="Markdown"
        )

# ── Main ──────────────────────────────────────────────────
def main():
    # Start Flask in background thread
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_user_message))

    logger.info("MODKING Contact Bot started...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
