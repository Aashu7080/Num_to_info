#!/usr/bin/env python3
# num.py — Group-only Number + Aadhaar Telegram bot
# Run in Termux: python num.py

import os
import re
import json
import time
import datetime
import requests

from telegram import (
    Update,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ===== YOUR TOKEN + OWNER CHAT ID =====
TELEGRAM_BOT_TOKEN = "8285812972:AAHkGflxgacVRE_lXD4vpbvRjIDm63-UL9I"
OWNER_CHAT_ID = 8373192284
# ======================================

# Group link (for buttons + welcome)
GROUP_LINK = "https://t.me/Num_to_info"

# APIs (pehle VIPPANELS, fir backup SHAURYA)
NUM_API_VIPP = "https://vippanels.x10.mx/numapi.php?action=api&key=month&term={}"
NUM_API_SHAU = "https://shaurya-num-2-info.vercel.app/api?number={}"

AADH_API = "https://addartofamily.vercel.app/fetch?aadhaar={}&key=fxt"

TEN = re.compile(r"^\d{10}$")
TWELVE = re.compile(r"^\d{12}$")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AashuNumBot/1.0"})
# Insecure HTTPS ko ignore karne ke liye (warnings kam ho jayenge)
SESSION.verify = False

MEMFILE = "user_mem.json"
MAX_DAILY = 10  # per user per day (admin unlimited)


# ---------- memory helpers ----------
def load_mem():
    try:
        if os.path.exists(MEMFILE):
            return json.load(open(MEMFILE, "r", encoding="utf-8"))
    except Exception:
        pass
    return {"users": [], "quota": {}}


def save_mem(m):
    try:
        json.dump(m, open(MEMFILE, "w", encoding="utf-8"), indent=2)
    except Exception:
        pass


memory = load_mem()


def register_user(uid: int):
    uid_s = str(uid)
    if uid_s not in memory.get("users", []):
        memory.setdefault("users", []).append(uid_s)
        save_mem(memory)


def today_str() -> str:
    # simple UTC-based day string
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def get_quota(uid: int):
    """
    Returns (used, remaining) for today.
    OWNER has unlimited (we still return (0, '∞')).
    """
    if uid == OWNER_CHAT_ID:
        return 0, "∞"

    memory.setdefault("quota", {})
    q = memory["quota"].get(str(uid))
    t = today_str()
    if not q or q.get("date") != t:
        q = {"date": t, "used": 0}
        memory["quota"][str(uid)] = q
        save_mem(memory)
    used = int(q.get("used", 0))
    remaining = max(0, MAX_DAILY - used)
    return used, remaining


def inc_quota(uid: int):
    if uid == OWNER_CHAT_ID:
        return 0, "∞"
    used, rem = get_quota(uid)
    if used >= MAX_DAILY:
        return used, 0
    memory["quota"][str(uid)]["used"] = used + 1
    save_mem(memory)
    used2 = used + 1
    rem2 = max(0, MAX_DAILY - used2)
    return used2, rem2


# ---------- small helpers ----------
def digits_only(s: str) -> str:
    return re.sub(r"\D", "", (s or ""))


def chunk_text(txt: str, limit: int = 3900):
    out = []
    if not txt:
        return out
    while len(txt) > limit:
        out.append(txt[:limit])
        txt = txt[limit:]
    out.append(txt)
    return out


def welcome_box(name: str, username: str, uid: int, remaining_text: str) -> str:
    if not username:
        username = "-"
    return (
        "╔═━━━━━━━━━━━══╗\n"
        "       𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 ☕︎\n"
        " ❤️ https://t.me/Num_to_info ❤\n"
        "╚═━━━━━━━━━━━══╝\n\n"
        "┏━━━━━━━━━━━━━━━━━🔻🌸\n"
        f"┣ 𝐍ᴀᴍᴇ :- {name}\n"
        f"┣ 𝐔sᴇʀ 𝐍ᴀᴍ𝐞 :- {username}\n"
        f"┣ 𝐔sᴇʀ ɪᴅ :- {uid}\n"
        "┗━━━━━━━━━━━━━━━━━🔻🌸\n\n"
        "Use /num <10-digit> or /adhar <12-digit> — or send a 10/12 digit number directly.\n"
        f"\nToday limit: {remaining_text} searches available."
    )


def format_number_output(num: str, arr: list, remaining_text: str) -> str:
    parts = []
    parts.append("✨ 📱 Mobile Search Results ✨")
    parts.append("━━━━━━━━━━━━━━")

    for it in arr:
        name = it.get("name") or "N/A"
        father = it.get("father_name") or it.get("fname") or "N/A"
        mobile = it.get("mobile") or num
        alt = it.get("alt") or it.get("alt_mobile") or "N/A"
        # address cleanup
        addr = (it.get("address") or "N/A").replace("!!", " ").replace("!", " ")
        addr = re.sub(r"\s+", " ", addr).strip()
        circle = it.get("circle") or "N/A"

        # IDs handling
        raw_id = str(it.get("id") or "")
        raw_idnum = str(it.get("id_number") or "")

        aadhaar = None
        doc_ids = []

        def push_id(val: str):
            nonlocal aadhaar, doc_ids
            val = val.strip()
            if not val:
                return
            if val.isdigit() and len(val) == 12 and aadhaar is None:
                aadhaar = val
            else:
                doc_ids.append(val)

        push_id(raw_id)
        push_id(raw_idnum)

        email = it.get("email") or it.get("mail") or ""

        parts.append("━━━━━━━━━━━━━━")
        parts.append(f"🔍 Searched Number: {num}")
        parts.append("━━━━━━━━━━━━━━")
        parts.append(f"👤 Name: {name}")
        parts.append(f"👨‍👦 Father: {father}")
        parts.append(f"📞 Mobile: {mobile}")
        parts.append(f"📱 Alt: {alt}")
        parts.append(f"🏠 Address: {addr}")
        parts.append(f"🌐 Circle: {circle}")

        # IDs print
        if doc_ids:
            if len(doc_ids) == 1:
                parts.append(f"🃏 ID: {doc_ids[0]}")
            else:
                parts.append("🃏 IDs:")
                for i, did in enumerate(doc_ids, start=1):
                    parts.append(f"   ID {i}: {did}")

        if aadhaar:
            parts.append(f"🆔 Aadhaar: {aadhaar}")

        if email:
            parts.append(f"✉️ Email: {email}")

    parts.append("━━━━━━━━━━━━━━")
    parts.append("Made by: @Aashu_officia")
    parts.append(f"📊 Today remaining: {remaining_text} searches")
    return "\n".join(parts)


def format_aadhaar_output(ad: str, data: dict, remaining_text: str) -> str:
    members = data.get("memberDetailsList") or []
    out = []
    out.append("✨ 🧑‍👩‍👧 Aadhaar Family Results ✨")
    out.append("━━━━━━━━━━━━━━")
    out.append(f"🆔 Aadhaar (masked): {ad[:4]}******{ad[-2:]}")
    out.append(f"🏠 Address: {data.get('address','N/A')}")
    out.append(f"🏷️ Scheme: {data.get('schemeName','N/A')} ({data.get('schemeId','N/A')})")
    out.append("━━━━━━━━━━━━━━")
    for m in members:
        out.append(f"👤 Name: {m.get('memberName','N/A')}")
        out.append(f"👪 Relation: {m.get('releationship_name') or m.get('relation','N/A')}")
        out.append(f"🧾 ID: {m.get('memberId','N/A')}")
        out.append("— — —")
    out.append("Made by: @Aashu_officia")
    out.append(f"📊 Today remaining: {remaining_text} searches")
    return "\n".join(out)


# ---------- fetchers (NUMBER) ----------
def fetch_number_vipp(num: str):
    """
    Pehla try: vippanels.x10.mx
    """
    try:
        r = SESSION.get(NUM_API_VIPP.format(num), timeout=10)
        r.raise_for_status()
    except Exception:
        return "⚠️ Service error.", None

    try:
        j = r.json()
    except Exception:
        return "⚠️ Service error.", None

    arr = None
    if isinstance(j, dict):
        # shapes: {"success":true,"data":[...]} OR {"data":[...]} etc
        if isinstance(j.get("data"), list):
            arr = j["data"]
        elif isinstance(j.get("data"), dict) and isinstance(j["data"].get("data"), list):
            arr = j["data"]["data"]
        elif isinstance(j.get("result"), list):
            arr = j["result"]

    if not arr or not isinstance(arr, list) or len(arr) == 0:
        # data not found yaha, but backup try karna hai
        return "❌ Data not found.", None

    return None, arr


def fetch_number_shaurya(num: str):
    """
    Backup: shaurya-num-2-info.vercel.app
    """
    try:
        r = SESSION.get(NUM_API_SHAU.format(num), timeout=10)
        r.raise_for_status()
    except Exception:
        return "⚠️ Service error.", None

    try:
        j = r.json()
    except Exception:
        return "⚠️ Service error.", None

    # j: {success, valid_until, source, data:{success, requested_number, data:[...]}}
    arr = None
    if isinstance(j, dict):
        inner = j.get("data")
        if isinstance(inner, dict):
            arr = inner.get("data")
        elif isinstance(inner, list):
            arr = inner
        elif isinstance(j.get("data"), list):
            arr = j.get("data")

    if not arr or not isinstance(arr, list) or len(arr) == 0:
        return "❌ Data not found.", None

    return None, arr


def fetch_number(num: str):
    """
    Final wrapper: pehle VIPP, phir backup SHAURYA.
    """
    # 1) VIPP try
    err1, arr1 = fetch_number_vipp(num)
    if arr1:
        return None, arr1

    # 2) Backup SHAURYA
    err2, arr2 = fetch_number_shaurya(num)
    if arr2:
        return None, arr2

    # dono fail / no data
    if err2:
        return err2, None
    return err1 or "❌ Data not found.", None


# ---------- fetcher (AADHAAR) ----------
def fetch_aadhaar(ad: str):
    try:
        r = SESSION.get(AADH_API.format(ad), timeout=10)
        r.raise_for_status()
    except Exception:
        return "⚠️ Service error.", None
    try:
        j = r.json()
    except Exception:
        return "⚠️ Service error.", None

    data = None
    if isinstance(j, dict) and j.get("memberDetailsList"):
        data = j
    elif (
        isinstance(j, dict)
        and isinstance(j.get("data"), dict)
        and j["data"].get("memberDetailsList")
    ):
        data = j["data"]

    if not data:
        return "❌ Data not found.", None

    return None, data


# ---------- group-only guard ----------
async def ensure_group_allowed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    msg = update.message

    if not chat:
        return True

    # Only block in private chats
    if chat.type == "private":
        bot = context.bot
        kb = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🌐 Use me here", url=GROUP_LINK)],
                [
                    InlineKeyboardButton(
                        "➕ Add me to a group",
                        url=f"https://t.me/{bot.username}?startgroup=true",
                    )
                ],
            ]
        )
        if msg:
            await msg.reply_text(
                "This command works only in groups. Add me to a group.",
                reply_markup=kb,
            )
        return False

    return True


# ---------- handlers ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_group_allowed(update, context):
        return

    user = update.effective_user
    register_user(user.id)

    used, rem = get_quota(user.id)
    if rem == "∞":
        remaining_text = "∞"
    else:
        remaining_text = f"{rem}/{MAX_DAILY}"

    txt = welcome_box(
        user.first_name or "User",
        user.username or "-",
        user.id,
        remaining_text,
    )
    await update.message.reply_text(txt)


async def num_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_group_allowed(update, context):
        return

    user = update.effective_user
    uid = user.id

    # Check limit
    used, rem = get_quota(uid)
    if rem != "∞" and rem <= 0:
        await update.message.reply_text(
            "❌ Aaj ke 10 successful search complete ho chuke hain.\n"
            "Kal fir try karein (limit 24 ghante baad reset ho jayegi)."
        )
        return

    # find candidate number
    candidate = ""
    if context.args:
        candidate = digits_only(" ".join(context.args))
    else:
        candidate = digits_only(update.message.text or "")

    if not candidate:
        return await update.message.reply_text(
            "📱 Example: /num 9876543210\nType number:",
            reply_markup=ForceReply(input_field_placeholder="Type 10-digit number"),
        )

    if not TEN.fullmatch(candidate):
        return await update.message.reply_text(
            "❌ Sirf 10 digits chahiye. Example: /num 9876543210"
        )

    # special insult
    if candidate == "9129326824":
        return await update.message.reply_text("bap ko dhundh raha kya nikal ☠️🤟")

    await update.message.reply_text("🔎 Searching...")

    err, arr = fetch_number(candidate)
    if err:
        return await update.message.reply_text(err)

    # success => decrease quota
    used2, rem2 = inc_quota(uid)
    if rem2 == "∞":
        remaining_text = "∞"
    else:
        remaining_text = f"{rem2}/{MAX_DAILY}"

    out = format_number_output(candidate, arr, remaining_text)
    for part in chunk_text(out):
        await update.message.reply_text(part)


async def adhar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_group_allowed(update, context):
        return

    user = update.effective_user
    uid = user.id

    used, rem = get_quota(uid)
    if rem != "∞" and rem <= 0:
        await update.message.reply_text(
            "❌ Aaj ke 10 successful search complete ho chuke hain.\n"
            "Kal fir try karein (limit 24 ghante baad reset ho jayegi)."
        )
        return

    candidate = ""
    if context.args:
        candidate = digits_only(" ".join(context.args))
    else:
        candidate = digits_only(update.message.text or "")

    if not candidate:
        return await update.message.reply_text(
            "🆔 Example: /adhar 658014451208\nType Aadhaar:",
            reply_markup=ForceReply(input_field_placeholder="Type 12-digit Aadhaar"),
        )

    if not TWELVE.fullmatch(candidate):
        return await update.message.reply_text(
            "❌ Sirf 12 digits chahiye. Example: /adhar 658014451208"
        )

    await update.message.reply_text("🔎 Fetching Aadhaar family...")

    err, data = fetch_aadhaar(candidate)
    if err:
        return await update.message.reply_text(err)

    used2, rem2 = inc_quota(uid)
    if rem2 == "∞":
        remaining_text = "∞"
    else:
        remaining_text = f"{rem2}/{MAX_DAILY}"

    out = format_aadhaar_output(candidate, data, remaining_text)
    for part in chunk_text(out):
        await update.message.reply_text(part)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_group_allowed(update, context):
        return

    txt = (update.message.text or "").strip()
    d = digits_only(txt)

    if TEN.fullmatch(d):
        context.args = [d]
        await num_cmd(update, context)
        return

    if TWELVE.fullmatch(d):
        context.args = [d]
        await adhar_cmd(update, context)
        return

    await update.message.reply_text(
        "Use /num <10-digit> or /adhar <12-digit> — or send a 10/12 digit number directly."
    )


async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_group_allowed(update, context):
        return
    if update.effective_user.id != OWNER_CHAT_ID:
        return await update.message.reply_text("Unauthorized.")
    await update.message.reply_text(
        "Registered users:\n" + "\n".join(memory.get("users", []) or ["(none)"])
    )


# ---------- main ----------
def main():
    # delete webhook to avoid conflicts
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook",
            timeout=3,
            verify=False,
        )
    except Exception:
        pass

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("num", num_cmd))
    app.add_handler(CommandHandler("adhar", adhar_cmd))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 Bot running... Group-only + daily limit enabled.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
