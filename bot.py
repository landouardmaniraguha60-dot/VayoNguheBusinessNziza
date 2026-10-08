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

    print("DATABASE: initialized successfully")


def save_group(chat_id, title, username, added_by):
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO groups (
            chat_id,
            title,
            username,
            added_by,
            active
        )
        VALUES (?, ?, ?, ?, 1)

        ON CONFLICT(chat_id)
        DO UPDATE SET
            title = excluded.title,
            username = excluded.username,
            added_by = excluded.added_by,
            active = 1
    """, (
        chat_id,
        title,
        username,
        added_by
    ))

    conn.commit()
    conn.close()

    print(
        f"DATABASE: group saved | "
        f"chat_id={chat_id} | "
        f"title={title}"
    )


def get_groups():
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute("""
        SELECT chat_id, title, username
        FROM groups
        WHERE active = 1
        ORDER BY title COLLATE NOCASE
    """)

    groups = cursor.fetchall()

    conn.close()

    return groups


def deactivate_group(chat_id):
    conn = sqlite3.connect(DB_FILE)

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE groups
        SET active = 0
        WHERE chat_id = ?
    """, (chat_id,))

    conn.commit()
    conn.close()

    print(
        f"DATABASE: group deactivated | chat_id={chat_id}"
    )


# =========================
# SECURITY
# =========================

def owner_only(update: Update):
    return (
        update.effective_user
        and update.effective_user.id == OWNER_ID
    )


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not owner_only(update):
        if update.message:
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

async def my_chat_member(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    print("========================================")
    print("MY_CHAT_MEMBER EVENT RECEIVED")
    print("========================================")

    chat_member_update = update.my_chat_member

    if not chat_member_update:
        print("MY_CHAT_MEMBER: no update object")
        return

    chat = chat_member_update.chat

    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status

    print(f"GROUP ID: {chat.id}")
    print(f"GROUP TITLE: {chat.title}")
    print(f"GROUP USERNAME: {chat.username}")
    print(f"OLD STATUS: {old_status}")
    print(f"NEW STATUS: {new_status}")

    added_by = (
        update.effective_user.id
        if update.effective_user
        else 0
    )

    # =========================
    # BOT ADDED TO GROUP
    # =========================

    if (
        new_status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR
        )
        and
        old_status in (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.KICKED
        )
    ):

        print("GROUP REGISTRATION: BOT ADDED")

        save_group(
            chat_id=chat.id,
            title=chat.title or "Unknown Group",
            username=chat.username,
            added_by=added_by
        )

        try:

            await context.bot.send_message(
                chat_id=chat.id,
                text=(
                    "🤖 Vayo Nguhe Business Nziza Bot "
                    "is now connected.\n\n"
                    "This group has been registered successfully."
                )
            )

            print(
                f"GROUP MESSAGE: sent successfully to {chat.id}"
            )

        except Exception as error:

            print(
                f"GROUP MESSAGE: failed | "
                f"chat_id={chat.id} | "
                f"error={error}"
            )

    # =========================
    # BOT REMOVED FROM GROUP
    # =========================

    elif new_status in (
        ChatMemberStatus.LEFT,
        ChatMemberStatus.KICKED
    ):

        print("GROUP REGISTRATION: BOT REMOVED")

        deactivate_group(chat.id)


# =========================
# GROUP LIST
# =========================

async def groups_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not owner_only(update):
        return

    groups = get_groups()

    if not groups:

        await update.message.reply_text(
            "👥 No groups have been registered yet."
        )

        return

    message = (
        f"👥 REGISTERED GROUPS: {len(groups)}\n\n"
    )

    for index, (
        chat_id,
        title,
        username
    ) in enumerate(groups, start=1):

        if username:
            link = f"@{username}"
        else:
            link = "Private group"

        message += (
            f"{index}. {title}\n"
            f"   {link}\n"
            f"   ID: {chat_id}\n\n"
        )

        if len(message) > 3500:

            await update.message.reply_text(
                message
            )

            message = ""

    if message:

        await update.message.reply_text(
            message
        )


# =========================
# STATS
# =========================

async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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

async def broadcast_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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

            print(
                f"BROADCAST: sent to {chat_id} | {title}"
            )

        except Exception as error:

            failed += 1

            print(
                f"BROADCAST: failed | "
                f"{chat_id} | {error}"
            )

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

async def recruit_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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

            print(
                f"RECRUIT: sent to {chat_id} | {title}"
            )

        except Exception as error:

            failed += 1

            print(
                f"RECRUIT: failed | "
                f"{chat_id} | {error}"
            )

            deactivate_group(chat_id)

        await asyncio.sleep(MESSAGE_DELAY)

    await update.message.reply_text(
        "🎯 RECRUITING FINISHED\n\n"
        f"📨 Sent: {sent}\n"
        f"❌ Failed: {failed}"
    )


# =========================
# ERROR HANDLER
# =========================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        f"BOT ERROR: {context.error}"
    )


# =========================
# HEALTH SERVER
# =========================

app = Flask(__name__)


@app.route("/")
def home():

    return "Vayo Nguhe Business Nziza Bot is running."


def run_web_server():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )


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

    # Commands

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "groups",
            groups_command
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            stats_command
        )
    )

    application.add_handler(
        CommandHandler(
            "broadcast",
            broadcast_command
        )
    )

    application.add_handler(
        CommandHandler(
            "recruit",
            recruit_command
        )
    )

    # IMPORTANT:
    # Detect when the bot is added to/removed from groups.

    application.add_handler(
        ChatMemberHandler(
            my_chat_member,
            ChatMemberHandler.MY_CHAT_MEMBER
        )
    )

    application.add_error_handler(
        error_handler
    )

    # Start Flask health server

    threading.Thread(
        target=run_web_server,
        daemon=True
    ).start()

    print(
        "========================================"
    )

    print(
        "Vayo Nguhe Business Nziza Bot is running..."
    )

    print(
        "Waiting for Telegram updates..."
    )

    print(
        "========================================"
    )

    application.run_polling(
        allowed_updates=[
            "message",
            "my_chat_member"
        ]
    )


if __name__ == "__main__":

    main()
