#!/usr/bin/env python3
"""Userbot PACE888 - auto-join grup, send promo."""
import asyncio, json, re, sys, random, os
from datetime import datetime, date, time as dt_time
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import Message, ChatMemberUpdated
from pyrogram.errors import FloodWait, UserAlreadyParticipant

API_ID = 35179622
API_HASH = "f015a6c1fbb927fdfe42c5b11dd96e7a"
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7890900149"))
WORKDIR = Path(__file__).parent
SESSION_FILE = WORKDIR / "session_string.txt"
GROUPS_FILE = WORKDIR / "groups.json"
TEMPLATES_FILE = WORKDIR / "templates.json"
STATS_FILE = WORKDIR / "stats.json"
SCHEDULE_FILE = WORKDIR / "schedule.json"
AUTOROTATE_FILE = WORKDIR / "autorotate.json"
RANDOM_DELAY = True  # True = delay 3-8s, False = delay 3s
autorotate_task = None


def load_groups():
    try:
        data = json.loads(GROUPS_FILE.read_text())
        # Support both legacy list format and current object format.
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("groups"), list):
            return data["groups"]
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return []


def save_groups(groups):
    GROUPS_FILE.write_text(json.dumps({"groups": groups}, indent=2))


def load_stats():
    try:
        return json.loads(STATS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        today = date.today().isoformat()
        return {"date": today, "sent": 0, "failed": 0}


def save_stats(stats):
    STATS_FILE.write_text(json.dumps(stats, indent=2))


def update_stats(sent, failed):
    stats = load_stats()
    today = date.today().isoformat()
    if stats.get("date") != today:
        stats = {"date": today, "sent": 0, "failed": 0}
    stats["sent"] += sent
    stats["failed"] += failed
    save_stats(stats)


def get_delay():
    """Return delay in seconds based on RANDOM_DELAY setting"""
    if RANDOM_DELAY:
        return random.uniform(3, 8)
    return 3


def load_templates():
    try:
        return json.loads(TEMPLATES_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_templates(templates):
    TEMPLATES_FILE.write_text(json.dumps(templates, indent=2))


def cleanup_invalid_group(chat_id, groups):
    """Remove a group from list if it's invalid/inaccessible"""
    before = len(groups)
    groups[:] = [g for g in groups if g.get("id") != chat_id]
    removed = before - len(groups)
    if removed > 0:
        save_groups(groups)
    return removed > 0


# Railway: baca dari env var SESSION_STRING dulu, fallback ke file
import os as _os
SESSION_STRING = _os.environ.get("SESSION_STRING", "").strip()
if not SESSION_STRING:
    try:
        SESSION_STRING = SESSION_FILE.read_text().strip()
    except FileNotFoundError:
        pass
if not SESSION_STRING:
    raise RuntimeError("SESSION_STRING tidak ditemukan di env maupun file")

app = Client(
    "userbot_promo",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)


@app.on_message(filters.private & filters.command("start"))
async def start_cmd(client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    groups = load_groups()
    await message.reply(
        f"🤖 **Userbot Promo PACE888**\n\n"
        f"📁 Grup: **{len(groups)}**\n"
        f"👤 Akun: @orandaaa\n\n"
        "**📋 Grup & Kirim Manual**\n"
        "• Kirim link grup → auto-join\n"
        "• `/groups` → lihat daftar grup\n"
        "• `/remove <no>` → hapus grup\n"
        "• `/sendpromo teks` → kirim manual ke semua grup\n"
        "• `/schedule HH:MM teks` → jadwal kirim sekali\n\n"
        "**📝 Template Autorotate**\n"
        "• `/template` → lihat semua template\n"
        "• `/template simpan nama teks` → tambah / ganti template\n"
        "• `/template hapus nama` → hapus template\n"
        "• Autorotate memakai semua template bergantian sesuai urutan daftar.\n\n"
        "**🔄 Autorotate**\n"
        "• `/autorotate status` → lihat setting saat ini\n"
        "• `/autorotate on` / `/autorotate off`\n"
        "• `/autorotate target all|batch` → semua grup / 2 batch\n"
        "• `/autorotate delay 5` → jeda per grup (3-300 dtk)\n"
        "• `/autorotate interval 5m` → jeda antar putaran (60 dtk-24 jam)\n"
        "• `/autorotate report on|off` → laporan selesai putaran\n\n"
        "• `/random on|off` → hanya untuk broadcast manual\n"
        "• `/stats` → statistik harian"
    )


@app.on_message(filters.private & filters.command("groups"))
async def groups_cmd(client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    groups = load_groups()
    if not groups:
        await message.reply("📭 Belum ada grup")
        return
    lines = [f"📋 **Daftar Grup ({len(groups)})**"]
    lines.extend(f"{i}. {g.get('title', '?')}" for i, g in enumerate(groups[:20], 1))
    await message.reply("\n".join(lines))


@app.on_message(filters.private & filters.command("sendpromo"))
async def sendpromo_cmd(client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: `/sendpromo [teks promo]`")
        return
    groups = load_groups()
    if not groups:
        await message.reply("📭 Belum ada grup")
        return
    await message.reply(f"⏳ Mengirim ke {len(groups)} grup...")
    sent = 0
    report = []
    groups_snapshot = groups[:]  # Iterate over copy to avoid mutation issues
    for g in groups_snapshot:
        try:
            await client.send_message(g["id"], args[1])
            sent += 1
            report.append(f"✅ {g.get('title', '?')}")
            await asyncio.sleep(get_delay())
        except FloodWait as error:
            report.append(f"⏳ {g.get('title', '?')} — flood wait {error.value}s")
            await asyncio.sleep(error.value)
        except Exception as error:
            error_str = str(error)
            # Auto-cleanup invalid groups
            if "Peer id invalid" in error_str or "USER_DEACTIVATED" in error_str or "CHAT_WRITE_FORBIDDEN" in error_str:
                cleanup_invalid_group(g["id"], groups)
                report.append(f"🗑 {g.get('title', '?')} — dihapus (tidak valid)")
            else:
                report.append(f"❌ {g.get('title', '?')} — {error_str[:60]}")
    result = "\n".join(report)
    update_stats(sent, len(groups) - sent)
    await message.reply(f"**📊 Hasil Broadcast:**\n\n{result}\n\nTotal: ✅{sent} | ❌{len(groups)-sent}")


@app.on_message(filters.private & filters.text & ~filters.command(
    ["start", "groups", "sendpromo", "remove", "stats", "random",
     "autorotate", "template", "schedule"]
))
async def auto_join_handler(client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    text = message.text.strip()
    # Find all t.me links
    all_links = re.findall(r"https?://t\.me/[\w/+-]+", text)
    if not all_links:
        return
    
    groups = load_groups()
    for full_link in all_links:
        try:
            # Determine if it's a private invite or public username
            if "/joinchat/" in full_link or "/+" in full_link:
                # Private invite link - use full URL
                chat = await client.join_chat(full_link)
            elif "/c/" in full_link:
                # Skip channel links
                continue
            else:
                # Public group username - extract username only
                username = full_link.split("/")[-1]
                chat = await client.join_chat(username)
            if any(g["id"] == chat.id for g in groups):
                await message.reply(f"⚠️ Udah join: {chat.title}")
                continue
            groups.append({
                "id": chat.id,
                "title": chat.title,
                "link": full_link,
                "added": datetime.now().isoformat(),
            })
            save_groups(groups)
            await message.reply(f"✅ Join: {chat.title}\n📁 Total grup: {len(groups)}")
        except UserAlreadyParticipant:
            # Already joined - check if in our list
            try:
                chat = await client.get_chat(full_link)
                if not any(g["id"] == chat.id for g in groups):
                    groups.append({
                        "id": chat.id,
                        "title": chat.title,
                        "link": full_link,
                        "added": datetime.now().isoformat(),
                    })
                    save_groups(groups)
                    await message.reply(f"✅ Sudah join sebelumnya, ditambahkan ke list: {chat.title}\n📁 Total: {len(groups)}")
                else:
                    await message.reply(f"⚠️ Udah join & ada di list")
            except:
                await message.reply("⚠️ Udah join di grup itu")
        except FloodWait as error:
            await message.reply(f"⏳ Flood wait {error.value}s")
            await asyncio.sleep(error.value)
        except Exception as error:
            await message.reply(f"❌ Gagal join: {str(error)[:80]}")


@app.on_message(filters.private & filters.command("template"))
async def template_cmd(client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=2)
    templates = load_templates()
    
    if len(args) < 2:
        # List all templates
        if not templates:
            await message.reply("📭 Belum ada template\n\nCara: `/template simpan nama teks_promo`")
            return
        lines = [f"**📝 Template ({len(templates)})**\nGunakan di /sendpromo atau /autorotate\n"]
        for name, text in templates.items():
            lines.append(f"**{name}**: `{text[:60]}...`")
        await message.reply("\n".join(lines))
        return
    
    action = args[1].lower()
    if action == "simpan" and len(args) >= 3:
        parts = args[2].split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("❌ Format: `/template simpan nama teks`")
            return
        name, text = parts[0], parts[1]
        templates[name] = text
        save_templates(templates)
        await message.reply(f"✅ Template **{name}** disimpan ({len(text)} chars)")
    
    elif action == "hapus":
        # /template hapus nama_template
        if len(args) < 3 or not args[2].strip():
            await message.reply("Cara: `/template hapus nama_template`")
            return
        name = args[2].strip()
        if name in templates:
            del templates[name]
            save_templates(templates)
            await message.reply(f"✅ Template **{name}** dihapus")
        else:
            await message.reply(f"❌ Template **{name}** tidak ditemukan")


@app.on_message(filters.private & filters.command("stats"))
async def stats_cmd(client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    stats = load_stats()
    groups = load_groups()
    await message.reply(
        f"**📈 Statistik Userbot**\n\n"
        f"📅 Hari ini ({stats.get('date', '?')})\n"
        f"✅ Terkirim: {stats.get('sent', 0)}\n"
        f"❌ Gagal: {stats.get('failed', 0)}\n\n"
        f"📁 Total grup: {len(groups)}\n"
        f"⏱ Random delay: {'ON (3-8s)' if RANDOM_DELAY else 'OFF (3s)'}"
    )


@app.on_message(filters.private & filters.command("random"))
async def random_cmd(client, message: Message):
    global RANDOM_DELAY
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        status = "ON (3-8s)" if RANDOM_DELAY else "OFF (3s)"
        await message.reply(f"⏱ Random delay: **{status}**\n\nCara: `/random on` atau `/random off`")
        return
    action = args[1].lower()
    if action == "on":
        RANDOM_DELAY = True
        await message.reply("✅ Random delay **ON** (3-8s)")
    elif action == "off":
        RANDOM_DELAY = False
        await message.reply("✅ Random delay **OFF** (3s fix)")
    else:
        await message.reply("❌ Gunakan: `/random on` atau `/random off`")


AUTOROTATE_DEFAULTS = {
    "enabled": False,
    "interval": 3600,
    "delay_seconds": 5,
    "target": "batch",
    "report": True,
    "template_index": 0,
    "batch_index": 0,
}


def load_autorotate_config():
    data = AUTOROTATE_DEFAULTS.copy()
    try:
        raw = json.loads(AUTOROTATE_FILE.read_text())
        if isinstance(raw, dict):
            data.update(raw)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    data["interval"] = max(60, min(86400, int(data.get("interval", 3600))))
    data["delay_seconds"] = max(3, min(300, int(data.get("delay_seconds", 5))))
    data["target"] = data.get("target") if data.get("target") in ("all", "batch") else "batch"
    data["report"] = bool(data.get("report", True))
    return data


def save_autorotate_config(data):
    result = AUTOROTATE_DEFAULTS.copy()
    result.update(data)
    AUTOROTATE_FILE.write_text(json.dumps(result, indent=2))


def parse_autorotate_interval(value):
    match = re.fullmatch(r"(\d+)(s|m|h)?", value.lower())
    if not match:
        return None
    amount, unit = match.groups()
    seconds = int(amount) * {None: 1, "s": 1, "m": 60, "h": 3600}[unit]
    return seconds if 60 <= seconds <= 86400 else None


def format_autorotate_interval(seconds):
    seconds = int(seconds)
    if seconds % 3600 == 0:
        return f"{seconds // 3600} jam"
    if seconds % 60 == 0:
        return f"{seconds // 60} menit"
    return f"{seconds} detik"


@app.on_message(filters.private & filters.command("autorotate"))
async def autorotate_cmd(client, message: Message):
    global autorotate_task
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    
    if len(args) < 2:
        # Show status
        auto_data = {"enabled": False, "interval": 3600}
        if AUTOROTATE_FILE.exists():
            auto_data = json.loads(AUTOROTATE_FILE.read_text())
        status = "**ON** ⏳" if auto_data.get("enabled") else "**OFF** ⏹"
        groups = load_groups()
        batches = max(1, len(groups) // 2) if groups else 1
        templates = load_templates()
        await message.reply(
            f"🔄 **Autorotate**\n\n"
            f"Status: {status}\n"
            f"Template: {len(templates)}\n"
            f"Grup: {len(groups)} | per batch ~{max(1, len(groups)//2)} grup\n"
            f"\nCara:\n"
            f"`/autorotate on` — aktifkan\n"
            f"`/autorotate off` — matikan\n"
            f"`/autorotate status` — info lengkap"
        )
        return
    
    action = args[1].lower()
    data = load_autorotate_config()
    if action == "delay" and len(args) == 3 and args[2].isdigit():
        delay = int(args[2])
        if not 3 <= delay <= 300:
            await message.reply("❌ Delay harus 3-300 detik.")
            return
        data["delay_seconds"] = delay
        save_autorotate_config(data)
        await message.reply(f"✅ Jeda autorotate: **{delay} detik** per grup.")
        return
    if action == "interval" and len(args) == 3:
        interval = parse_autorotate_interval(args[2])
        if interval is None:
            await message.reply("❌ Format: `/autorotate interval 5m` atau `/autorotate interval 1h` (60 detik-24 jam).")
            return
        data["interval"] = interval
        save_autorotate_config(data)
        await message.reply(f"✅ Interval autorotate: **{format_autorotate_interval(interval)}**.")
        return
    if action == "target" and len(args) == 3 and args[2].lower() in ("all", "batch"):
        data["target"] = args[2].lower()
        data["batch_index"] = 0
        save_autorotate_config(data)
        label = "semua grup" if data["target"] == "all" else "dua batch bergantian"
        await message.reply(f"✅ Target autorotate: **{label}**.")
        return
    if action == "report" and len(args) == 3 and args[2].lower() in ("on", "off"):
        data["report"] = args[2].lower() == "on"
        save_autorotate_config(data)
        await message.reply(f"✅ Report autorotate: **{'ON' if data['report'] else 'OFF'}**.")
        return
    if action == "on":
        data = load_autorotate_config()
        data["enabled"] = True
        save_autorotate_config(data)
        templates = load_templates()
        groups = load_groups()
        target_label = "semua grup per putaran" if data.get("target") == "all" else "2 batch bergantian"
        msg = (
            f"✅ **Autorotate ON**\n\n"
            f"Interval: **{format_autorotate_interval(data.get('interval', 3600))}**\n"
            f"Target: **{target_label}**\n"
            f"Jeda antargrup: **{data.get('delay_seconds', 5)} detik**\n"
            f"Template: **{len(templates)}** | Grup: **{len(groups)}**\n"
            f"Report: **{'ON' if data.get('report', True) else 'OFF'}**"
        )
        if len(templates) < 1:
            msg += "\n\n⚠️ Belum ada template! Simpan dulu: `/template simpan nama teks`"
        if len(groups) < 1:
            msg += "\n\n⚠️ Belum ada grup! Kirim link grup untuk join"
        await message.reply(msg)
        
    elif action == "off":
        data = load_autorotate_config()
        data["enabled"] = False
        save_autorotate_config(data)
        await message.reply("⏹ **Autorotate OFF**")
    
    elif action == "status":
        data = {"enabled": False}
        if AUTOROTATE_FILE.exists():
            data = json.loads(AUTOROTATE_FILE.read_text())
        templates = load_templates()
        groups = load_groups()
        mid = len(groups) // 2
        batch_a_names = [g.get('title','?') for g in groups[:mid]]
        batch_b_names = [g.get('title','?') for g in groups[mid:]]
        help_lines = [f"🔄 **Autorotate**"]
        status = "ON ⏳" if data.get("enabled") else "OFF ⏹"
        help_lines.append(f"Status: {status}")
        help_lines.append(f"Interval: {format_autorotate_interval(data.get('interval', 3600))}")
        help_lines.append(f"Jeda antargrup: {data.get('delay_seconds', 5)} detik")
        help_lines.append(f"Target: {data.get('target', 'batch')}")
        help_lines.append(f"Report: {'ON' if data.get('report', True) else 'OFF'}")
        help_lines.append(f"Template: {len(templates)}")
        help_lines.append(f"\n**Batch A ({len(batch_a_names)})**")
        for n in batch_a_names[:5]: help_lines.append(f"  • {n}")
        help_lines.append(f"\n**Batch B ({len(batch_b_names)})**")
        for n in batch_b_names[:5]: help_lines.append(f"  • {n}")
        await message.reply("\n".join(help_lines))
    
    else:
        await message.reply("❌ Cara: `/autorotate on|off|status`")


@app.on_message(filters.private & filters.command("remove"))
async def remove_cmd(client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    args = message.text.split()
    if len(args) < 2:
        await message.reply("Cara: `/remove <nomor>`\n\nLihat nomor dengan `/groups`")
        return
    try:
        idx = int(args[1]) - 1
    except ValueError:
        await message.reply("❌ Nomor harus angka")
        return
    groups = load_groups()
    if idx < 0 or idx >= len(groups):
        await message.reply(f"❌ Nomor tidak valid (total {len(groups)} grup)")
        return
    removed = groups.pop(idx)
    save_groups(groups)
    
    # Leave the group
    try:
        await client.leave_chat(removed["id"])
        await message.reply(f"✅ Dihapus & keluar dari: **{removed.get('title', '?')}**\n📁 Sisa: {len(groups)} grup")
    except Exception as e:
        await message.reply(f"✅ Dihapus dari list: **{removed.get('title', '?')}**\n⚠️ Gagal keluar grup: {str(e)[:40]}\n📁 Sisa: {len(groups)} grup")


@app.on_chat_member_updated()
async def welcome_new_member(client, update: ChatMemberUpdated):
    # Auto-send promo to new members
    if not update.new_chat_member or update.new_chat_member.status not in ["member", "administrator"]:
        return
    if update.old_chat_member and update.old_chat_member.status in ["member", "administrator"]:
        return  # Not a new join, just status change
    
    groups = load_groups()
    if not any(g["id"] == update.chat.id for g in groups):
        return  # Not in our managed groups
    
    # Send welcome promo - use first template, or default
    templates = load_templates()
    if templates:
        first = list(templates.values())[0]
        welcome_text = f"🎉 **Selamat Datang!**\n\n{first}"
    else:
        welcome_text = (
            "🎉 **Selamat Datang!**\n\n"
            "🔥 **PACE888** - Situs Judi Online Terpercaya\n"
            "💰 Bonus New Member 100%\n"
            "⚡ Proses Cepat 24/7\n\n"
            "📲 Daftar sekarang: https://pace888.web.id"
        )
    try:
        await client.send_message(update.chat.id, welcome_text)
    except:
        pass  # Silent fail if can't send


print("Userbot PACE888 starting...")


async def autorotate_worker():
    """Background worker for auto-rotation every hour"""
    global autorotate_task
    await asyncio.sleep(60)  # Wait 1 min after start
    
    template_index = 0
    batch_index = 0
    
    while True:
        try:
            # Check if autorotate is enabled
            if not AUTOROTATE_FILE.exists():
                await asyncio.sleep(300)  # Check every 5 min
                continue
            
            data = json.loads(AUTOROTATE_FILE.read_text())
            if not data.get("enabled", False):
                await asyncio.sleep(300)
                continue
            
            # Get templates and groups
            templates = load_templates()
            groups = load_groups()
            
            if not templates or not groups:
                await asyncio.sleep(3600)  # Wait 1 hour
                continue
            
            # Target can be all groups per round or two rotating batches.
            if data.get("target", "batch") == "all":
                batches = [groups]
            else:
                mid = max(1, len(groups) // 2)
                batches = [groups[:mid], groups[mid:]]
            
            # Restore persisted rotation position and select safely.
            template_index = int(data.get("template_index", 0))
            batch_index = int(data.get("batch_index", 0))
            batch_count = len(batches)
            template_values = list(templates.values())
            current_template = template_values[template_index % len(template_values)]
            current_batch = batches[batch_index % batch_count]
            
            sent = 0
            batch_details = []
            for g in current_batch:
                try:
                    await app.send_message(g["id"], current_template)
                    sent += 1
                    batch_details.append(f"✅ {g.get('title', '?')}")
                    await asyncio.sleep(int(data.get("delay_seconds", 5)))
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    batch_details.append(f"⏳ {g.get('title', '?')} — flood {e.value}s")
                except Exception as e:
                    if "Peer id invalid" in str(e) or "USER_DEACTIVATED" in str(e) or "CHAT_WRITE_FORBIDDEN" in str(e):
                        cleanup_invalid_group(g["id"], groups)
                        batch_details.append(f"🗑 {g.get('title', '?')} — dihapus")
                    else:
                        batch_details.append(f"❌ {g.get('title', '?')} — {str(e)[:40]}")
            
            update_stats(sent, len(current_batch) - sent)
            
            # Send one completion report only when enabled.
            if data.get("report", True):
                batch_name = "Semua Grup" if batch_count == 1 else ("Batch A" if batch_index == 0 else "Batch B")
                report = f"🔄 **Autorotate {batch_name} Selesai**\n\n"
                report += "\n".join(batch_details) + "\n\n"
                report += f"✅ Terkirim: {sent} | ❌ Gagal: {len(current_batch) - sent}\n"
                report += f"📁 Target: {len(current_batch)} grup | Jeda: {data.get('delay_seconds', 5)} detik\n"
                report += f"🕒 Putaran berikutnya: {format_autorotate_interval(data.get('interval', 3600))} lagi"
                try:
                    await app.send_message(ADMIN_ID, report)
                except Exception as e:
                    print(f"[autorotate] report error: {type(e).__name__}: {e}", flush=True)
            
            # Rotate indices
            template_index = (template_index + 1) % len(template_values)
            batch_index += 1
            if batch_index >= batch_count:
                batch_index = 0
                # A full-cycle report only applies to the two-batch mode.
                if batch_count > 1 and data.get("report", True):
                    cycle_report = f"🎉 **Rotasi Lengkap Selesai**\n\n"
                    cycle_report += f"📊 Semua batch sudah dijalankan\n"
                    cycle_report += f"📁 Total grup: {len(groups)}\n"
                    cycle_report += f"🕒 Cycle berikutnya: {format_autorotate_interval(data.get('interval', 3600))} lagi"
                    try:
                        await app.send_message(ADMIN_ID, cycle_report)
                    except Exception as e:
                        print(f"[autorotate] cycle report error: {type(e).__name__}: {e}", flush=True)
            data.update({"template_index": template_index, "batch_index": batch_index})
            save_autorotate_config(data)
            await asyncio.sleep(int(data.get("interval", 3600)))
            
        except Exception as e:
            print(f"[autorotate] worker error: {type(e).__name__}: {e}", flush=True)
            await asyncio.sleep(300)


async def schedule_checker():
    """Check scheduled tasks every 60 seconds"""
    while True:
        await asyncio.sleep(60)
        try:
            if not SCHEDULE_FILE.exists():
                continue
            data = json.loads(SCHEDULE_FILE.read_text())
            now = datetime.now().strftime("%H:%M")
            for item in data.get("tasks", []):
                if item.get("time") == now and not item.get("done", False):
                    groups = load_groups()
                    for g in groups:
                        try:
                            await app.send_message(g["id"], item["text"])
                            await asyncio.sleep(get_delay())
                        except:
                            pass
                    item["done"] = True
                    SCHEDULE_FILE.write_text(json.dumps(data, indent=2))
        except:
            pass


@app.on_message(filters.private & filters.command("schedule"))
async def schedule_cmd(client, message: Message):
    if not message.from_user or message.from_user.id != ADMIN_ID:
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3 or args[1].lower() == "list":
        # List schedules or show help
        if SCHEDULE_FILE.exists():
            data = json.loads(SCHEDULE_FILE.read_text())
            tasks = data.get("tasks", [])
        else:
            tasks = []
        if not tasks:
            await message.reply(
                "**📅 Jadwal Promo**\n\n"
                "Cara: `/schedule HH:MM teks_promo`\n"
                "Contoh: `/schedule 19:00 🔥 Promo Malam PACE888`\n\n"
                "Belum ada jadwal."
            )
            return
        lines = [f"**📅 Jadwal ({len(tasks)})**"]
        for t in tasks:
            status = "✅" if t.get("done") else "⏳"
            lines.append(f"{status} {t['time']}: {t['text'][:40]}")
        await message.reply("\n".join(lines))
        return
    
    action = args[1].lower()
    if action == "clear":
        SCHEDULE_FILE.write_text('{"tasks": []}')
        await message.reply("✅ Semua jadwal dihapus")
        return
    
    action = args[1].lower()
    if action == "reset":
        # Reset all done flags
        if SCHEDULE_FILE.exists():
            data = json.loads(SCHEDULE_FILE.read_text())
            for t in data.get("tasks", []):
                t["done"] = False
            SCHEDULE_FILE.write_text(json.dumps(data, indent=2))
        await message.reply("✅ Semua jadwalkan direset (akan terkirim lagi)")
        return
    
    # Add new schedule: /schedule HH:MM teks
    time_str = action
    text = args[2].strip() if len(args) > 2 else ""
    
    if not re.match(r"^\d{2}:\d{2}$", time_str):
        await message.reply("❌ Format waktu: `HH:MM`\nContoh: `/schedule 19:00 promonya`")
        return
    
    # Load existing
    data = {"tasks": []}
    if SCHEDULE_FILE.exists():
        data = json.loads(SCHEDULE_FILE.read_text())
    if not isinstance(data.get("tasks"), list):
        data["tasks"] = []
    
    data["tasks"].append({"time": time_str, "text": text, "done": False})
    SCHEDULE_FILE.write_text(json.dumps(data, indent=2))
    await message.reply(f"✅ Jadwal {time_str} ditambahkan\n📝 `{text[:50]}`")


# Run schedule checker in background
loop = asyncio.get_event_loop()
loop.create_task(schedule_checker())
loop.create_task(autorotate_worker())

app.run()
