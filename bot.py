import logging
import os
import asyncio
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeChat
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ─── CONFIG ───────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID  = int(os.environ.get("ADMIN_ID", "2077682354"))
PORT      = int(os.environ.get("PORT", 8080))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")
# ──────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Flask keep-alive ──────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Admin Bot is running ✅", 200

@flask_app.route("/health")
def health():
    return "OK", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, use_reloader=False, debug=False)

# ── Shared state ──────────────────────────────────────────
state = {
    "users":          {},
    "notify":         True,
    "broadcast_mode": False,
    "ban_mode":       False,
    "unban_mode":     False,
}

# ── Helpers ───────────────────────────────────────────────
def is_admin(uid: int) -> bool:
    return uid == ADMIN_ID

def admin_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 All Users",     callback_data="cmd_users"),
            InlineKeyboardButton("📢 Broadcast",     callback_data="cmd_broadcast"),
        ],
        [
            InlineKeyboardButton("🚫 Ban User",      callback_data="cmd_ban"),
            InlineKeyboardButton("✅ Unban User",    callback_data="cmd_unban"),
        ],
        [
            InlineKeyboardButton("📊 Bot Stats",     callback_data="cmd_stats"),
            InlineKeyboardButton("🔔 Toggle Notify", callback_data="cmd_toggle_notify"),
        ],
        [
            InlineKeyboardButton("❓ Help",          callback_data="cmd_help"),
        ],
    ])

# ── Set bot commands on startup ───────────────────────────
async def post_init(app: Application):
    user_commands = [
        BotCommand("start", "Start the bot"),
    ]
    admin_commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("panel", "Open admin panel"),
    ]
    await app.bot.set_my_commands(user_commands)
    await app.bot.set_my_commands(
        admin_commands,
        scope=BotCommandScopeChat(chat_id=ADMIN_ID)
    )
    logger.info("Bot commands set successfully.")

# ── /start ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = user.id

    if uid != ADMIN_ID and uid not in state["users"]:
        state["users"][uid] = {
            "name":     user.full_name,
            "username": user.username or "N/A",
            "banned":   False,
        }

    if is_admin(uid):
        await update.message.reply_text(
            "👑 *Welcome Admin!*\n\nUse the buttons below to manage the bot.",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )
    else:
        await update.message.reply_text(
            f"👋 Hello *{user.first_name}*!\n\nSend me any message and the admin will receive it.",
            parse_mode="Markdown"
        )

# ── /panel ────────────────────────────────────────────────
async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "🛠 *Admin Panel*",
        parse_mode="Markdown",
        reply_markup=admin_keyboard()
    )

# ── User message handler ──────────────────────────────────
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = user.id

    if is_admin(uid):
        await handle_admin_text(update, context)
        return

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

    header = (
        f"📩 *New Message*\n"
        f"👤 Name: {user.full_name}\n"
        f"🔖 Username: @{user.username or 'N/A'}\n"
        f"🆔 ID: `{uid}`\n"
        f"─────────────────"
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

# ── Admin text handler ────────────────────────────────────
async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    if state["broadcast_mode"]:
        state["broadcast_mode"] = False
        count = 0
        for u_id, info in state["users"].items():
            if not info["banned"]:
                try:
                    await context.bot.send_message(u_id, f"📢 *Broadcast:*\n\n{text}", parse_mode="Markdown")
                    count += 1
                except Exception:
                    pass
        await update.message.reply_text(f"📢 Broadcast sent to {count} users.", reply_markup=admin_keyboard())

    elif state["ban_mode"]:
        state["ban_mode"] = False
        try:
            target = int(text.strip())
            if target in state["users"]:
                state["users"][target]["banned"] = True
                await update.message.reply_text(f"🚫 User `{target}` banned.", parse_mode="Markdown", reply_markup=admin_keyboard())
            else:
                await update.message.reply_text("❌ User ID not found.", reply_markup=admin_keyboard())
        except ValueError:
            await update.message.reply_text("❌ Send a valid numeric ID.", reply_markup=admin_keyboard())

    elif state["unban_mode"]:
        state["unban_mode"] = False
        try:
            target = int(text.strip())
            if target in state["users"]:
                state["users"][target]["banned"] = False
                await update.message.reply_text(f"✅ User `{target}` unbanned.", parse_mode="Markdown", reply_markup=admin_keyboard())
            else:
                await update.message.reply_text("❌ User ID not found.", reply_markup=admin_keyboard())
        except ValueError:
            await update.message.reply_text("❌ Send a valid numeric ID.", reply_markup=admin_keyboard())

    elif context.user_data.get("reply_to"):
        target_uid = context.user_data.pop("reply_to")
        try:
            await context.bot.send_message(target_uid, f"📬 *Admin Reply:*\n\n{text}", parse_mode="Markdown")
            await update.message.reply_text("✅ Reply sent!", reply_markup=admin_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to send: {e}", reply_markup=admin_keyboard())
    else:
        await update.message.reply_text("Use the panel buttons 👇", reply_markup=admin_keyboard())

# ── Button callbacks ──────────────────────────────────────
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid  = query.from_user.id

    if not is_admin(uid):
        await query.answer("⛔ Admin only!", show_alert=True)
        return

    state["broadcast_mode"] = False
    state["ban_mode"]        = False
    state["unban_mode"]      = False

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
        await query.edit_message_text(
            "📢 *Broadcast Mode*\n\nType the message to send to all users:",
            parse_mode="Markdown"
        )

    elif data == "cmd_ban":
        state["ban_mode"] = True
        await query.edit_message_text(
            "🚫 *Ban User*\n\nSend the user's Telegram ID:",
            parse_mode="Markdown"
        )

    elif data == "cmd_unban":
        state["unban_mode"] = True
        await query.edit_message_text(
            "✅ *Unban User*\n\nSend the user's Telegram ID:",
            parse_mode="Markdown"
        )

    elif data == "cmd_stats":
        total  = len(state["users"])
        banned = sum(1 for u in state["users"].values() if u["banned"])
        active = total - banned
        notify = "🟢 ON" if state["notify"] else "🔴 OFF"
        await query.edit_message_text(
            f"📊 *Bot Statistics*\n\n"
            f"👥 Total Users : {total}\n"
            f"✅ Active      : {active}\n"
            f"🚫 Banned      : {banned}\n"
            f"🔔 Notify      : {notify}",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )

    elif data == "cmd_toggle_notify":
        state["notify"] = not state["notify"]
        status = "🟢 ON" if state["notify"] else "🔴 OFF"
        await query.edit_message_text(
            f"🔔 Notifications are now *{status}*",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )

    elif data == "cmd_help":
        await query.edit_message_text(
            "❓ *Admin Commands Help*\n\n"
            "📋 *All Users* — List all registered users\n"
            "📢 *Broadcast* — Send message to all users\n"
            "🚫 *Ban User* — Ban a user by Telegram ID\n"
            "✅ *Unban User* — Unban a user by Telegram ID\n"
            "📊 *Bot Stats* — View bot statistics\n"
            "🔔 *Toggle Notify* — Turn message forwarding on/off\n\n"
            "💡 When a user messages the bot, you receive it with a Reply button.",
            parse_mode="Markdown",
            reply_markup=admin_keyboard()
        )

    elif data.startswith("reply_"):
        target_uid = int(data.split("_")[1])
        context.user_data["reply_to"] = target_uid
        name = state["users"].get(target_uid, {}).get("name", str(target_uid))
        await query.edit_message_text(
            f"↩️ *Replying to {name}*\n\nType your reply message now:",
            parse_mode="Markdown"
        )

# ── Main ──────────────────────────────────────────────────
async def run_bot():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_user_message))

    logger.info("Admin Bot is starting...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )
    logger.info("Admin Bot is polling...")

    # Keep running forever
    await asyncio.Event().wait()

def main():
    # Start Flask in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info(f"Flask server started on port {PORT}")

    # Run bot with asyncio directly (avoids PTB internal loop conflicts)
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
