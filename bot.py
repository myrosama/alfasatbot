"""
SAT ALFA Anonymous Q&A Telegram Bot

Students compose multi-message questions (text + photos + docs),
then submit them as a single bundled question to the teacher.
Teacher receives and manages questions with inline buttons.

Open-source — configure via .env for any learning centre.
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TEACHER_ID = int(os.getenv("TEACHER_ID"))
CENTRE_NAME = os.getenv("CENTRE_NAME", "SAT ALFA")

# --- Data Persistence ---
DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "questions.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def load_data() -> dict:
    """Load persistent data from JSON file."""
    if DATA_FILE.exists():
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "next_id": 1,
        "questions": {},
        "stats": {"total": 0, "answered": 0},
        "students": [],
    }


def save_data(data: dict):
    """Save data to JSON file."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def count_pending(data: dict) -> int:
    """Count pending questions."""
    return sum(
        1 for q in data["questions"].values()
        if q["status"] in ("pending", "answering")
    )


def get_question_preview(q: dict, max_len: int = 60) -> str:
    """Extract a text preview from a question, handling both v1 and v2 formats."""
    if "parts" in q:
        # v2 format — list of parts
        texts = [p["text"] for p in q["parts"] if p.get("text")]
        preview = " ".join(texts)[:max_len]
        if not preview:
            media_count = sum(1 for p in q["parts"] if p["type"] != "text")
            preview = f"[📎 {media_count} attachment(s)]"
    else:
        # v1 format — flat text/type fields
        preview = (q.get("text", "") or "")[:max_len]
        if not preview and q.get("type") != "text":
            preview = f"[📎 {q.get('type', 'media')}]"
    return preview or "[empty]"


# --- Reply Keyboard Buttons (bottom of screen) ---
BTN_ASK = "📝 Ask a Question"
BTN_SEND = "✅ Send Question"
BTN_CANCEL = "❌ Cancel"


def main_student_keyboard() -> ReplyKeyboardMarkup:
    """Main menu keyboard for students — sits at bottom of screen."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_ASK)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def composing_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard shown while student is composing a question."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_SEND), KeyboardButton(BTN_CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def teacher_question_keyboard(q_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard for teacher to act on a question."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Reply", callback_data=f"reply_{q_id}"),
            InlineKeyboardButton("✅ Done", callback_data=f"done_{q_id}"),
        ]
    ])


def teacher_main_keyboard() -> InlineKeyboardMarkup:
    """Management keyboard for teacher."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Queue", callback_data="t_queue"),
            InlineKeyboardButton("📊 Stats", callback_data="t_stats"),
        ],
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="t_broadcast"),
            InlineKeyboardButton("🗑 Clear Done", callback_data="t_clear"),
        ],
    ])


# ========================================
# STUDENT FLOW
# ========================================

WELCOME_STUDENT = (
    f"📚 *Welcome to {CENTRE_NAME} Q&A Bot!*\n\n"
    "This bot lets you ask your teacher any SAT question — "
    "*completely anonymously*. Here's how:\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "📖 *How to use:*\n\n"
    "1️⃣ Tap *\"📝 Ask a Question\"* below\n"
    "2️⃣ Send your question — you can send *multiple messages*, "
    "including text, photos, and documents\n"
    "3️⃣ When you're done, tap *\"✅ Send Question\"*\n"
    "4️⃣ Your teacher will reply right here!\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔒 Your identity is *never* revealed to the teacher.\n"
    "💡 Tip: Include screenshots of problems for faster help!"
)

WELCOME_TEACHER = (
    f"👩‍🏫 *Welcome, Teacher!*\n\n"
    f"You'll receive {CENTRE_NAME} student questions here anonymously.\n\n"
    "📖 *How it works:*\n"
    "• Students send bundled questions (text + photos)\n"
    "• Each arrives with *Reply* / *Done* buttons\n"
    "• Tap Reply → type your answer → sent back anonymously\n\n"
    "📋 *Commands:*\n"
    "• /queue — View pending questions\n"
    "• /stats — Answer statistics\n"
    "• /broadcast — Send announcement to all students\n"
    "• /cancel — Cancel current reply\n"
    "• /menu — Show management panel"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — show tutorial and main button."""
    user_id = update.effective_user.id

    # Track student
    data = load_data()
    if user_id != TEACHER_ID and user_id not in data.get("students", []):
        data.setdefault("students", []).append(user_id)
        save_data(data)

    if user_id == TEACHER_ID:
        await update.message.reply_text(
            WELCOME_TEACHER,
            parse_mode="Markdown",
            reply_markup=teacher_main_keyboard(),
        )
    else:
        await update.message.reply_text(
            WELCOME_STUDENT,
            parse_mode="Markdown",
            reply_markup=main_student_keyboard(),
        )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help."""
    user_id = update.effective_user.id
    if user_id == TEACHER_ID:
        await update.message.reply_text(WELCOME_TEACHER, parse_mode="Markdown",
                                         reply_markup=teacher_main_keyboard())
    else:
        await update.message.reply_text(WELCOME_STUDENT, parse_mode="Markdown",
                                         reply_markup=main_student_keyboard())


# ========================================
# STUDENT COMPOSE FLOW
# ========================================

async def start_composing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Put student into composing mode — triggered by reply keyboard button."""
    context.user_data["composing"] = True
    context.user_data["compose_parts"] = []

    await update.message.reply_text(
        (
            "📝 *Composing your question...*\n\n"
            "Send your question now — you can send *multiple messages* "
            "(text, photos, documents).\n\n"
            "When you're done, tap *\"✅ Send Question\"* at the bottom.\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ),
        parse_mode="Markdown",
        reply_markup=composing_keyboard(),
    )


async def collect_student_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect messages while student is composing."""
    user_id = update.effective_user.id
    msg = update.message

    # Teacher messages go to a different handler
    if user_id == TEACHER_ID:
        await handle_teacher_message(update, context)
        return

    # Handle reply keyboard button presses
    if msg.text == BTN_ASK:
        await start_composing(update, context)
        return
    if msg.text == BTN_SEND:
        await finish_composing_from_message(update, context)
        return
    if msg.text == BTN_CANCEL:
        await cancel_composing_from_message(update, context)
        return

    # If not composing, prompt them to use the button
    if not context.user_data.get("composing"):
        await msg.reply_text(
            "👋 To ask a question, tap the button below!",
            reply_markup=main_student_keyboard(),
        )
        return

    part = {"type": "text", "text": "", "file_id": None}

    if msg.photo:
        part["type"] = "photo"
        part["file_id"] = msg.photo[-1].file_id
        part["text"] = msg.caption or ""
    elif msg.document:
        part["type"] = "document"
        part["file_id"] = msg.document.file_id
        part["text"] = msg.caption or ""
    elif msg.text:
        part["type"] = "text"
        part["text"] = msg.text
    else:
        await msg.reply_text("❌ Only text, photos, and documents are supported.")
        return

    context.user_data.setdefault("compose_parts", []).append(part)

    count = len(context.user_data["compose_parts"])
    await msg.reply_text(
        f"📎 *Part {count} added.* Send more or tap ✅ to submit.",
        parse_mode="Markdown",
        reply_markup=composing_keyboard(),
    )


async def finish_composing_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bundle all composed parts into one question and send to teacher."""
    user_id = update.effective_user.id
    parts = context.user_data.get("compose_parts", [])

    if not parts:
        await update.message.reply_text(
            "❌ You didn't send any content. Try again!",
            reply_markup=main_student_keyboard(),
        )
        context.user_data.pop("composing", None)
        context.user_data.pop("compose_parts", None)
        return

    # Save the question
    data = load_data()
    q_id = str(data["next_id"])
    data["next_id"] += 1
    data["stats"]["total"] += 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    question_record = {
        "id": q_id,
        "student_id": user_id,
        "timestamp": now,
        "status": "pending",
        "parts": parts,
        "answer": None,
    }
    data["questions"][q_id] = question_record
    save_data(data)

    # Clear compose state
    context.user_data.pop("composing", None)
    context.user_data.pop("compose_parts", None)

    await update.message.reply_text(
        (
            f"✅ *Question #{q_id} sent anonymously!*\n\n"
            f"📎 {len(parts)} part(s) sent to your teacher.\n"
            "You'll receive a reply right here. 🔔"
        ),
        parse_mode="Markdown",
        reply_markup=main_student_keyboard(),
    )

    # Forward to teacher
    await send_question_to_teacher(context, q_id, question_record)


async def cancel_composing_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current question composition."""
    context.user_data.pop("composing", None)
    context.user_data.pop("compose_parts", None)

    await update.message.reply_text(
        "❌ Question cancelled.",
        reply_markup=main_student_keyboard(),
    )


# ========================================
# SEND QUESTION TO TEACHER
# ========================================

async def send_question_to_teacher(context: ContextTypes.DEFAULT_TYPE, q_id: str, question: dict):
    """Send a bundled question to the teacher."""
    parts = question["parts"]
    now = question["timestamp"]
    keyboard = teacher_question_keyboard(q_id)

    # Header message
    header = (
        f"📩 *New Question #{q_id}*\n"
        f"🕐 {now} • 📎 {len(parts)} part(s)\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    # Send header with first text part or alone
    text_parts = [p for p in parts if p["type"] == "text"]
    combined_text = "\n\n".join(p["text"] for p in text_parts if p["text"])

    if combined_text:
        await context.bot.send_message(
            chat_id=TEACHER_ID,
            text=f"{header}\n\n{combined_text}",
            parse_mode="Markdown",
            reply_markup=keyboard if not any(p["type"] != "text" for p in parts) else None,
        )
    else:
        await context.bot.send_message(
            chat_id=TEACHER_ID,
            text=header,
            parse_mode="Markdown",
        )

    # Send media parts
    media_parts = [p for p in parts if p["type"] in ("photo", "document")]
    for i, part in enumerate(media_parts):
        is_last = (i == len(media_parts) - 1)
        caption = part["text"] if part["text"] else None
        markup = keyboard if is_last else None

        try:
            if part["type"] == "photo":
                await context.bot.send_photo(
                    chat_id=TEACHER_ID,
                    photo=part["file_id"],
                    caption=caption,
                    reply_markup=markup,
                )
            elif part["type"] == "document":
                await context.bot.send_document(
                    chat_id=TEACHER_ID,
                    document=part["file_id"],
                    caption=caption,
                    reply_markup=markup,
                )
        except Exception as e:
            logger.error(f"Failed to send part to teacher: {e}")

    # If no media, and no text was sent with keyboard, send keyboard separately
    if not media_parts and not combined_text:
        await context.bot.send_message(
            chat_id=TEACHER_ID,
            text=f"[Empty question #{q_id}]",
            reply_markup=keyboard,
        )


# ========================================
# TEACHER FLOW
# ========================================

async def handle_teacher_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages from teacher — route replies or broadcast."""
    # Check broadcast mode
    if context.user_data.get("broadcasting"):
        await execute_broadcast(update, context)
        return

    replying_to = context.user_data.get("replying_to")

    if not replying_to:
        await update.message.reply_text(
            "💡 Use the buttons on questions to reply, or use the menu below.",
            reply_markup=teacher_main_keyboard(),
        )
        return

    data = load_data()
    question = data["questions"].get(replying_to)

    if not question:
        await update.message.reply_text("❌ Question not found.")
        context.user_data.pop("replying_to", None)
        return

    msg = update.message
    student_id = question["student_id"]
    reply_header = f"📩 *Reply to your question #{replying_to}:*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

    try:
        if msg.photo:
            await context.bot.send_photo(
                chat_id=student_id,
                photo=msg.photo[-1].file_id,
                caption=f"{reply_header}{msg.caption or ''}",
                parse_mode="Markdown",
            )
        elif msg.document:
            await context.bot.send_document(
                chat_id=student_id,
                document=msg.document.file_id,
                caption=f"{reply_header}{msg.caption or ''}",
                parse_mode="Markdown",
            )
        elif msg.text:
            await context.bot.send_message(
                chat_id=student_id,
                text=f"{reply_header}{msg.text}",
                parse_mode="Markdown",
            )

        # Mark as done
        question["status"] = "done"
        question["answer"] = msg.text or "(media)"
        data["stats"]["answered"] += 1
        save_data(data)

        await msg.reply_text(
            f"✅ *Reply sent!* (Question #{replying_to} closed)\n"
            f"💡 Pending: *{count_pending(data)}*",
            parse_mode="Markdown",
            reply_markup=teacher_main_keyboard(),
        )
    except Exception as e:
        logger.error(f"Failed to send reply: {e}")
        await msg.reply_text("❌ Failed to deliver. Student may have blocked the bot.")

    context.user_data.pop("replying_to", None)


# ========================================
# CALLBACK QUERIES
# ========================================

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all inline button presses."""
    query = update.callback_query
    data_str = query.data
    user_id = query.from_user.id

    # Teacher-only actions below
    if user_id != TEACHER_ID:
        await query.answer("⛔ Teacher only.", show_alert=True)
        return

    await query.answer()

    # Teacher management buttons
    if data_str == "t_queue":
        await show_queue(query, context)
        return
    if data_str == "t_stats":
        await show_stats(query, context)
        return
    if data_str == "t_broadcast":
        await start_broadcast(query, context)
        return
    if data_str == "t_clear":
        await clear_done(query, context)
        return

    # Question action buttons
    if data_str.startswith("reply_"):
        q_id = data_str[6:]
        await teacher_reply(query, context, q_id)
        return
    if data_str.startswith("done_"):
        q_id = data_str[5:]
        await teacher_done(query, context, q_id)
        return


async def teacher_reply(query, context, q_id):
    """Set teacher into reply mode for a specific question."""
    data = load_data()
    question = data["questions"].get(q_id)

    if not question or question["status"] == "done":
        await context.bot.send_message(
            chat_id=TEACHER_ID,
            text=f"ℹ️ Question #{q_id} is already answered or not found.",
        )
        return

    context.user_data["replying_to"] = q_id
    question["status"] = "answering"
    save_data(data)

    await context.bot.send_message(
        chat_id=TEACHER_ID,
        text=(
            f"📝 *Replying to Question #{q_id}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Type your answer below.\n"
            f"Send text, photos, or documents.\n\n"
            f"💡 Use /cancel to abort this reply."
        ),
        parse_mode="Markdown",
    )


async def teacher_done(query, context, q_id):
    """Mark a question as done without replying."""
    data = load_data()
    question = data["questions"].get(q_id)

    if not question:
        return

    if question["status"] == "done":
        await context.bot.send_message(
            chat_id=TEACHER_ID, text=f"ℹ️ Question #{q_id} already done."
        )
        return

    question["status"] = "done"
    data["stats"]["answered"] += 1
    save_data(data)

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=TEACHER_ID,
        text=f"✅ Question #{q_id} marked as done.\n💡 Pending: *{count_pending(data)}*",
        parse_mode="Markdown",
        reply_markup=teacher_main_keyboard(),
    )


# ========================================
# TEACHER COMMANDS
# ========================================

async def show_queue(source, context):
    """Show pending questions. Works from both command and callback."""
    # Determine chat_id — from command or callback
    if hasattr(source, "message") and source.message:
        chat_id = source.message.chat_id
    elif hasattr(source, "from_user"):
        chat_id = source.from_user.id
    else:
        return

    data = load_data()
    pending = [
        q for q in data["questions"].values()
        if q["status"] in ("pending", "answering")
    ]

    if not pending:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🎉 *No pending questions!* All caught up.",
            parse_mode="Markdown",
            reply_markup=teacher_main_keyboard(),
        )
        return

    lines = [f"📋 *Pending Questions ({len(pending)}):*\n"]
    for q in pending:
        icon = "⏳" if q["status"] == "pending" else "✍️"
        preview = get_question_preview(q, 60)
        lines.append(f"{icon} *#{q['id']}* — {preview}")

    await context.bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        parse_mode="Markdown",
    )

    # Re-send each with action buttons
    for q in pending:
        kb = teacher_question_keyboard(q["id"])
        preview = get_question_preview(q, 100)
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❓ *Question #{q['id']}* ({q['timestamp']})\n\n{preview}",
            parse_mode="Markdown",
            reply_markup=kb,
        )


async def show_stats(source, context):
    """Show answer statistics."""
    if hasattr(source, "from_user"):
        chat_id = source.from_user.id
    elif hasattr(source, "message"):
        chat_id = source.message.chat_id
    else:
        return

    data = load_data()
    total = data["stats"]["total"]
    answered = data["stats"]["answered"]
    pending = count_pending(data)
    students = len(data.get("students", []))

    if total > 0:
        text = (
            f"📊 *{CENTRE_NAME} Q&A Stats*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 Students: *{students}*\n"
            f"📩 Total questions: *{total}*\n"
            f"✅ Answered: *{answered}*\n"
            f"⏳ Pending: *{pending}*\n"
            f"📈 Answer rate: *{(answered/total*100):.0f}%*"
        )
    else:
        text = f"📊 *{CENTRE_NAME} Q&A Stats*\n\n👥 Students: *{students}*\nNo questions yet!"

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=teacher_main_keyboard(),
    )


async def start_broadcast(query, context):
    """Put teacher into broadcast mode."""
    context.user_data["broadcasting"] = True
    await context.bot.send_message(
        chat_id=TEACHER_ID,
        text=(
            "📢 *Broadcast Mode*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Type your announcement below. It will be sent to *all students* "
            "who have used the bot.\n\n"
            "💡 Use /cancel to abort."
        ),
        parse_mode="Markdown",
    )


async def execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send broadcast message to all students."""
    msg = update.message
    data = load_data()
    students = data.get("students", [])

    if not students:
        await msg.reply_text("❌ No students have used the bot yet.")
        context.user_data.pop("broadcasting", None)
        return

    sent = 0
    failed = 0
    broadcast_text = f"📢 *Announcement from {CENTRE_NAME}:*\n━━━━━━━━━━━━━━━━━━━━━━\n\n{msg.text}"

    for student_id in students:
        try:
            if msg.photo:
                await context.bot.send_photo(
                    chat_id=student_id,
                    photo=msg.photo[-1].file_id,
                    caption=broadcast_text,
                    parse_mode="Markdown",
                )
            elif msg.document:
                await context.bot.send_document(
                    chat_id=student_id,
                    document=msg.document.file_id,
                    caption=broadcast_text,
                    parse_mode="Markdown",
                )
            else:
                await context.bot.send_message(
                    chat_id=student_id,
                    text=broadcast_text,
                    parse_mode="Markdown",
                )
            sent += 1
        except Exception as e:
            logger.warning(f"Broadcast to {student_id} failed: {e}")
            failed += 1

    context.user_data.pop("broadcasting", None)
    await msg.reply_text(
        f"📢 *Broadcast sent!*\n\n✅ Delivered: *{sent}*\n❌ Failed: *{failed}*",
        parse_mode="Markdown",
        reply_markup=teacher_main_keyboard(),
    )


async def clear_done(query, context):
    """Clear all completed questions from storage."""
    data = load_data()
    before = len(data["questions"])
    data["questions"] = {
        k: v for k, v in data["questions"].items()
        if v["status"] != "done"
    }
    after = len(data["questions"])
    removed = before - after
    save_data(data)

    await context.bot.send_message(
        chat_id=TEACHER_ID,
        text=f"🗑 *Cleared {removed} resolved question(s).*\n💡 Remaining: *{after}*",
        parse_mode="Markdown",
        reply_markup=teacher_main_keyboard(),
    )


async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /queue."""
    if update.effective_user.id != TEACHER_ID:
        return
    await show_queue(update, context)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /stats."""
    if update.effective_user.id != TEACHER_ID:
        return
    await show_stats(update, context)


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command handler for /broadcast."""
    if update.effective_user.id != TEACHER_ID:
        return
    context.user_data["broadcasting"] = True
    await update.message.reply_text(
        "📢 *Broadcast Mode*\n\n"
        "Type your announcement. It will be sent to all students.\n"
        "Use /cancel to abort.",
        parse_mode="Markdown",
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current reply or broadcast mode."""
    user_id = update.effective_user.id

    if user_id == TEACHER_ID:
        was_replying = context.user_data.pop("replying_to", None)
        was_broadcasting = context.user_data.pop("broadcasting", None)
        if was_replying or was_broadcasting:
            await update.message.reply_text(
                "❌ Cancelled.",
                reply_markup=teacher_main_keyboard(),
            )
        else:
            await update.message.reply_text("Nothing to cancel.")
    else:
        # Student cancel composing
        context.user_data.pop("composing", None)
        context.user_data.pop("compose_parts", None)
        await update.message.reply_text(
            "❌ Question cancelled.",
            reply_markup=main_student_keyboard(),
        )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show management panel for teacher."""
    if update.effective_user.id != TEACHER_ID:
        return
    await update.message.reply_text(
        f"⚙️ *{CENTRE_NAME} Management*",
        parse_mode="Markdown",
        reply_markup=teacher_main_keyboard(),
    )


# ========================================
# MAIN
# ========================================

def main():
    """Start the bot."""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found! Create a .env file with BOT_TOKEN=your_token")
        return

    print(f"🤖 {CENTRE_NAME} Bot starting...")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("queue", cmd_queue))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("menu", cmd_menu))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Messages
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND,
        collect_student_message,
    ))

    print("✅ Bot is running! Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
