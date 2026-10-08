import os
import sqlite3
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ChatMemberHandler,
)

# =========================
# CONFIGURATION
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 8613895639

DB_FILE = "groups.db"

# Small delay between group messages
MESSAGE_DELAY = 1.5


# =========================
# DATABASE
# =========================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            username TEXT,
            added_by INTEGER,
            active INTEGER DEFAULT 1
        )
    """)

    conn.commit()
    conn.close()


def save_group(chat_id, title, username, added_by):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO groups (chat_id, title, username, added_by, active)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(chat_id)
        DO UPDATE SET
            title = excluded.title,
            username = excluded.username,
            active = 1
    """, (chat_id, title, username, added_by))

    conn.commit()
    conn.close()


def get_groups():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT chat_id, title, username
        FROM groups
        WHERE active = 1
    """)

    groups = cursor.fetchall()
    conn.close()

    return groups


def deactivate_group(chat_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE groups SET active = 0 WHERE chat_id = ?",
        (chat_id,)
    )

    conn.commit()
    conn.close()


# =========================
# SECURITY
# =========================

def owner_only(update: Update):
    return update.effective_user and update.effective_user.id == OWNER_ID


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not owner_only(update):
        await update.message.reply_text(
            "This bot is privately managed."
        )
        return

    await update.message.reply_text(
        "🤖 Vayo Nguhe Business Nziza Bot\n\n"
        "Welcome Owner.\n\n"
        "Commands:\n"
        "/groups - View registered groups\n"
        "/stats - View statistics\n"
        "/broadcast MESSAGE - Send message to all groups\n"
        "/recruit MESSAGE - Send recruiting message to all groups"
    )


# =========================
# GROUP REGISTRATION
# =========================

async def my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):

    chat_member_update = update.my_chat_member

    if not chat_member_update:
        return

    chat = chat_member_update.chat
    new_status = chat_member_update.new_chat_member.status
    old_status = chat_member_update.old_chat_member.status

    # Bot has been added to a group
    if new_status in [
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR
    ] and old_status in [
        ChatMemberStatus.LEFT,
        ChatMemberStatus.KICKED
    ]:

        save_group(
            chat.id,
            chat.title or "Unknown Group",
            chat.username,
            update.effective_user.id if update.effective_user else 0
        )

        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=(
                    "🤖 Vayo Nguhe Business Nziza Bot is now connected.\n\n"
                    "This group has been registered successfully."
                )
            )
        except Exception:
            pass

    # Bot was removed
    elif new_status in [
        ChatMemberStatus.LEFT,
        ChatMemberStatus.KICKED
    ]:

        deactivate_group(chat.id)


# =========================
# GROUP LIST
# =========================

async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not owner_only(update):
        return

    groups = get_groups()

    if not groups:
        await update.message.reply_text(
            "👥 No groups have been registered yet."
        )
        return

    message = f"👥 REGISTERED GROUPS: {len(groups)}\n\n"

    for index, (chat_id, title, username) in enumerate(groups, start=1):

        if username:
            link = f"@{username}"
        else:
            link = "Private group"

        message += f"{index}. {title}\n"
        message += f"   {link}\n"
        message += f"   ID: {chat_id}\n\n"

        # Telegram message size protection
        if len(message) > 3500:
            await update.message.reply_text(message)
            message = ""

    if message:
        await update.message.reply_text(message)


# =========================
# STATS
# =========================

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not owner_only(update):
        return

    groups = get_groups()

    await update.message.reply_text(
        "📊 BOT STATISTICS\n\n"
        f"👥 Active Groups: {len(groups)}\n"
        f"👑 Owner ID: {OWNER_ID}\n"
        f"🤖 Bot: Vayo Nguhe Business Nziza"
    )


# =========================
# BROADCAST
# =========================

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not owner_only(update):
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n\n"
            "/broadcast Your message here"
        )
        return

    message = " ".join(context.args)

    groups = get_groups()

    if not groups:
        await update.message.reply_text(
            "❌ No active groups found."
        )
        return

    sent = 0
    failed = 0

    await update.message.reply_text(
        f"📢 Broadcasting...\n\n"
        f"Target groups: {len(groups)}"
    )

    for chat_id, title, username in groups:

        try:

            await context.bot.send_message(
                chat_id=chat_id,
                text=message
            )

            sent += 1

        except Exception:

            failed += 1
            deactivate_group(chat_id)

        await asyncio.sleep(MESSAGE_DELAY)

    await update.message.reply_text(
        "✅ BROADCAST FINISHED\n\n"
        f"📨 Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )


# =========================
# RECRUITING
# =========================

async def recruit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not owner_only(update):
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n\n"
            "/recruit Your recruiting message here"
        )
        return

    message = " ".join(context.args)

    groups = get_groups()

    if not groups:
        await update.message.reply_text(
            "❌ No active groups found."
        )
        return

    sent = 0
    failed = 0

    await update.message.reply_text(
        f"🎯 Recruiting campaign started.\n\n"
        f"Target groups: {len(groups)}"
    )

    for chat_id, title, username in groups:

        try:

            await context.bot.send_message(
                chat_id=chat_id,
                text=message
            )

            sent += 1

        except Exception:

            failed += 1
            deactivate_group(chat_id)

        await asyncio.sleep(MESSAGE_DELAY)

    await update.message.reply_text(
        "🎯 RECRUITING FINISHED\n\n"
        f"📨 Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )


# =========================
# HEALTH SERVER FOR RENDER
# =========================

app = Flask(__name__)


@app.route("/")
def home():
    return "Vayo Nguhe Business Nziza Bot is running."


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# =========================
# MAIN
# =========================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("groups", groups_command)
    )

    application.add_handler(
        CommandHandler("stats", stats_command)
    )

    application.add_handler(
        CommandHandler("broadcast", broadcast_command)
    )

    application.add_handler(
        CommandHandler("recruit", recruit_command)
    )

    application.add_handler(
        ChatMemberHandler(
            my_chat_member,
            ChatMemberHandler.MY_CHAT_MEMBER
        )
    )

    # Start health server
    threading.Thread(
        target=run_web_server,
        daemon=True
    ).start()

    print("Vayo Nguhe Business Nziza Bot is running...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
