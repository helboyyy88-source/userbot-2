#!/usr/bin/env python3
"""Userbot Promo 6: group join, templates, autorotate, and exact reports only."""
import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, SlowmodeWait, UserAlreadyParticipant
from pyrogram.types import Message, MessageEntity
from pyrogram.enums import MessageEntityType

WORKDIR = Path(__file__).parent
GROUPS_FILE = WORKDIR / "groups.json"
TEMPLATES_FILE = WORKDIR / "templates.json"
AUTOROTATE_FILE = WORKDIR / "autorotate.json"

# Railway reads these values from Variables.
try:
    API_ID = int(os.environ["TG_API_ID"])
    API_HASH = os.environ["TG_API_HASH"].strip()
    ADMIN_ID = int(os.environ["ADMIN_ID"])
except (KeyError, ValueError) as exc:
    raise RuntimeError("TG_API_ID, TG_API_HASH, dan ADMIN_ID wajib diisi melalui Railway Variables") from exc
BOT_LABEL = os.environ.get("BOT_LABEL", "USERBOT PROMO 7").strip() or "USERBOT PROMO 7"
SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
if not SESSION_STRING:
    raise RuntimeError("SESSION_STRING tidak ditemukan")

app = Client("userbot_promo_7", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

DEFAULT_CONFIG = {"enabled": False, "interval": 3600, "delay_seconds": 5,
                  "target": "batch", "report": True, "template_index": 0, "batch_index": 0}


def load_json(path, default):
    try:
        value = json.loads(path.read_text())
        return value
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def groups():
    value = load_json(GROUPS_FILE, [])
    return value if isinstance(value, list) else value.get("groups", [])


def save_groups(value):
    save_json(GROUPS_FILE, value)


def templates():
    value = load_json(TEMPLATES_FILE, {})
    return value if isinstance(value, dict) else {}


def save_templates(value):
    save_json(TEMPLATES_FILE, value)


def config():
    return DEFAULT_CONFIG | load_json(AUTOROTATE_FILE, {})


def save_config(value):
    save_json(AUTOROTATE_FILE, value)


def format_time(seconds):
    seconds = int(seconds)
    if seconds % 3600 == 0: return f"{seconds // 3600} jam"
    if seconds % 60 == 0: return f"{seconds // 60} menit"
    return f"{seconds} detik"


def parse_time(value):
    match = re.fullmatch(r"(\d+)(s|m|h)?", value.lower())
    if not match: return None
    amount, unit = match.groups()
    return int(amount) * {None: 60, "s": 1, "m": 60, "h": 3600}[unit]


def is_admin(message):
    return bool(message.from_user and message.from_user.id == ADMIN_ID)


@app.on_message(filters.private & filters.command("start"))
async def start_cmd(client, message: Message):
    if not is_admin(message): return
    me = await client.get_me()
    account = f"@{me.username}" if me.username else (me.first_name or str(me.id))
    cfg = config()
    await message.reply(
        f"🤖 **{BOT_LABEL}**\n"
        f"👤 Akun: {account}\n"
        f"📁 Grup: {len(groups())} | 📝 Template: {len(templates())}\n"
        f"🔄 Autorotate: **{'ON' if cfg['enabled'] else 'OFF'}**\n\n"
        "Kirim link `t.me` grup untuk auto-join.\n"
        "`/template daftar` · `/template simpan nama isi_promo` · `/template hapus nama`\n"
        "`/autorotate status|on|off`\n"
        "`/autorotate delay 5` · `/autorotate interval 1h`\n"
        "`/autorotate target all|batch` · `/autorotate report on|off`"
    )


@app.on_message(filters.private & filters.text & ~filters.command(["start", "template", "autorotate"]))
async def auto_join(client, message: Message):
    if not is_admin(message): return
    links = re.findall(r"https?://t\.me/(?:\+[\w-]+|joinchat/[\w-]+|[A-Za-z0-9_]+)", message.text or "")
    if not links: return
    saved = groups(); results = []
    for link in links:
        try:
            target = link if ("/+" in link or "/joinchat/" in link) else link.rstrip("/").split("/")[-1]
            chat = await client.join_chat(target)
            if not any(item.get("id") == chat.id for item in saved):
                saved.append({"id": chat.id, "title": chat.title or str(chat.id), "link": link, "added": datetime.now().isoformat()})
                save_groups(saved)
            results.append(f"✅ {chat.title}")
        except UserAlreadyParticipant:
            try:
                chat = await client.get_chat(link)
                if not any(item.get("id") == chat.id for item in saved):
                    saved.append({"id": chat.id, "title": chat.title or str(chat.id), "link": link, "added": datetime.now().isoformat()})
                    save_groups(saved)
                results.append(f"✅ Sudah join: {chat.title}")
            except Exception as exc:
                results.append(f"❌ {link}: {type(exc).__name__}")
        except Exception as exc:
            results.append(f"❌ {link}: {type(exc).__name__}")
    await message.reply("\n".join(results) + f"\n\n📁 Total grup: {len(groups())}")


def template_payload(value):
    if isinstance(value, dict):
        return value.get("text", ""), [MessageEntity(type=MessageEntityType[item["type"]], offset=item["offset"], length=item["length"], url=item.get("url"), language=item.get("language"), custom_emoji_id=item.get("custom_emoji_id")) for item in value.get("entities", [])]
    return str(value), None


def template_for_storage(message, body_start):
    entities = []
    for entity in (message.entities or []):
        start = entity.offset - body_start
        end = start + entity.length
        if start >= 0 and end <= len(message.text or "") - body_start:
            item = {"type": entity.type.name, "offset": start, "length": entity.length}
            if entity.url: item["url"] = entity.url
            if entity.language: item["language"] = entity.language
            if entity.custom_emoji_id: item["custom_emoji_id"] = entity.custom_emoji_id
            entities.append(item)
    return {"text": (message.text or "")[body_start:], "entities": entities}


@app.on_message(filters.private & filters.command("template"))
async def template_cmd(client, message: Message):
    if not is_admin(message): return
    args = (message.text or "").split(maxsplit=3)
    data = templates()
    if len(args) == 1 or args[1].lower() == "daftar":
        names = "\n".join(f"• `{name}`" for name in data) or "Belum ada template."
        await message.reply(f"📝 **Template ({len(data)})**\n{names}\n\nCara: `/template simpan nama isi_promo`"); return
    if args[1].lower() == "simpan" and len(args) >= 4:
        body_start = (message.text or "").find(args[3])
        data[args[2]] = template_for_storage(message, body_start if body_start >= 0 else 0)
        save_templates(data)
        await message.reply(f"✅ Template `{args[2]}` disimpan."); return
    if args[1].lower() == "hapus" and len(args) >= 3:
        if args[2] not in data: await message.reply("❌ Template tidak ditemukan.")
        else:
            del data[args[2]]; save_templates(data)
            await message.reply(f"✅ Template `{args[2]}` dihapus.")
        return
    await message.reply("Cara: `/template daftar` | `/template simpan nama isi_promo` | `/template hapus nama`")


@app.on_message(filters.private & filters.command("autorotate"))
async def autorotate_cmd(client, message: Message):
    if not is_admin(message): return
    args = (message.text or "").split()
    data = config(); action = args[1].lower() if len(args) > 1 else "status"
    if action == "status":
        await message.reply(f"🔄 **Autorotate**\nStatus: **{'ON' if data['enabled'] else 'OFF'}**\n"
                            f"Target: {data['target']} | Jeda: {data['delay_seconds']} dtk | Interval: {format_time(data['interval'])}\n"
                            f"Report: {'ON' if data['report'] else 'OFF'}\nTemplate: {len(templates())} | Grup: {len(groups())}"); return
    if action in ("on", "off"):
        if action == "on" and (not groups() or not templates()):
            await message.reply("❌ Tambahkan minimal 1 grup dan 1 template dulu."); return
        data["enabled"] = action == "on"; save_config(data)
        await message.reply(f"✅ Autorotate **{action.upper()}**."); return
    if action == "delay" and len(args) == 3 and args[2].isdigit():
        data["delay_seconds"] = max(1, int(args[2])); save_config(data)
        await message.reply(f"✅ Jeda: {data['delay_seconds']} detik."); return
    if action == "interval" and len(args) == 3:
        seconds = parse_time(args[2])
        if seconds and seconds > 0:
            data["interval"] = seconds; save_config(data)
            await message.reply(f"✅ Interval: {format_time(seconds)}."); return
    if action == "target" and len(args) == 3 and args[2] in ("all", "batch"):
        data["target"] = args[2]; save_config(data); await message.reply(f"✅ Target: {args[2]}."); return
    if action == "report" and len(args) == 3 and args[2] in ("on", "off"):
        data["report"] = args[2] == "on"; save_config(data); await message.reply(f"✅ Report: {args[2].upper()}."); return
    await message.reply("Cara: `/autorotate status|on|off|delay N|interval 1h|target all|batch|report on|off`")


async def autorotate_worker():
    await asyncio.sleep(30)
    while True:
        try:
            data = config()
            if not data.get("enabled"):
                await asyncio.sleep(60); continue
            target_groups = groups(); data_templates = templates()
            if not target_groups or not data_templates:
                await asyncio.sleep(60); continue
            if data.get("target") == "all": batches = [target_groups[:]]
            else:
                mid = max(1, len(target_groups) // 2)
                batches = [item for item in (target_groups[:mid], target_groups[mid:]) if item]
            batch_index = int(data.get("batch_index", 0)) % len(batches)
            template_names = list(data_templates)
            template_index = int(data.get("template_index", 0)) % len(template_names)
            batch = batches[batch_index][:]  # fixed snapshot: Target always equals Sent + Failed
            body, body_entities = template_payload(data_templates[template_names[template_index]])
            sent = failed = 0; reasons = {}; details = []
            for group in batch:
                title = group.get("title", str(group.get("id")))
                try:
                    await app.send_message(group["id"], body, entities=body_entities)
                    sent += 1; details.append(f"✅ {title}")
                    await asyncio.sleep(max(1, int(data.get("delay_seconds", 5))))
                except (FloodWait, SlowmodeWait) as exc:
                    failed += 1; key = type(exc).__name__; reasons[key] = reasons.get(key, 0) + 1
                    details.append(f"⏳ {title} — {key} {exc.value} dtk")
                except Exception as exc:
                    failed += 1; key = type(exc).__name__; reasons[key] = reasons.get(key, 0) + 1
                    details.append(f"❌ {title} — {key}: {str(exc).replace(chr(10), ' ')[:90]}")
                # Never remove a failed group. Only the user can modify the list.
            if data.get("report", True):
                scope = "Semua Grup" if len(batches) == 1 else f"Batch {'A' if batch_index == 0 else 'B'}"
                summary = ", ".join(f"{kind}: {count}" for kind, count in sorted(reasons.items())) or "Tidak ada"
                report = (f"🔄 **LAPORAN AUTOROTATE — {scope}**\n"
                          f"🧾 Template: `{template_names[template_index]}`\n"
                          f"🎯 Target: **{len(batch)}** grup\n"
                          f"✅ Terkirim: **{sent}**\n"
                          f"❌ Gagal: **{failed}**\n"
                          f"📌 Alasan gagal: {summary}\n"
                          f"🕒 Putaran berikutnya: {format_time(data['interval'])}\n\n"
                          f"**DETAIL ({len(batch)})**\n" + "\n".join(details))
                for offset in range(0, len(report), 3500):
                    await app.send_message(ADMIN_ID, report[offset:offset + 3500])
            data["template_index"] = (template_index + 1) % len(template_names)
            data["batch_index"] = (batch_index + 1) % len(batches)
            save_config(data)
            await asyncio.sleep(max(1, int(data["interval"])))
        except Exception as exc:
            print(f"[autorotate] {type(exc).__name__}: {exc}", flush=True)
            await asyncio.sleep(60)


loop = asyncio.get_event_loop()
loop.create_task(autorotate_worker())
print(f"{BOT_LABEL} starting...", flush=True)
app.run()
