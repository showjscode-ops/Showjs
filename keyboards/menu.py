from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.i18n import translate

def _t(text, lang):
    return translate(text, lang) or text

def home_kb(lang="id"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=_t("📤 Up File",lang),callback_data="upfile"),InlineKeyboardButton(text=_t("📥 Get File",lang),callback_data="getfile")],
        [InlineKeyboardButton(text=_t("🔑 Code",lang),callback_data="code_all"),InlineKeyboardButton(text=_t("🏆 Top 10 Code",lang),callback_data="top_codes")],
        [InlineKeyboardButton(text=_t("💎 Buy VIP",lang),callback_data="buy_vip"),InlineKeyboardButton(text=_t("⭐ Buy Star",lang),callback_data="buy_stars")],
        [InlineKeyboardButton(text=_t("🪙 Buy Poin",lang),callback_data="buy_points"),InlineKeyboardButton(text=_t("💳 Deposit",lang),callback_data="deposit")],
        [InlineKeyboardButton(text=_t("🎁 Cek In",lang),callback_data="checkin"),InlineKeyboardButton(text=_t("📂 Menu Lainnya",lang),callback_data="menu_lainnya")]
    ])

def other_menu_kb(creator=False, lang="id"):
    rows=[
      [InlineKeyboardButton(text=_t("📋 My Code",lang),callback_data="my_code"),InlineKeyboardButton(text=_t("👥 Group Code",lang),callback_data="group_code")],
      [InlineKeyboardButton(text=_t("🏆 Top 10 Code",lang),callback_data="top_codes")]
    ]
    if creator:
        rows.append([InlineKeyboardButton(text=_t("👑 Creator",lang),callback_data="creator_dashboard"),InlineKeyboardButton(text=_t("💸 Withdraw",lang),callback_data="withdraw")])
    else:
        rows.append([InlineKeyboardButton(text=_t("👑 Jadi Kreator",lang),callback_data="creator_apply")])
    rows.append([InlineKeyboardButton(text=_t("🎁 Check In",lang),callback_data="checkin"),InlineKeyboardButton(text=_t("❓ Help",lang),callback_data="help")])
    rows.append([InlineKeyboardButton(text=_t("🌐 Ganti Bahasa",lang),callback_data="change_language")])
    rows.append([InlineKeyboardButton(text=_t("🔙 Kembali",lang),callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def provider_kb(prefix, lang="id"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="QR 2",callback_data=f"provider:{prefix}:bayargg")],
        [InlineKeyboardButton(text="QR 1",callback_data=f"provider:{prefix}:cashi")],
        [InlineKeyboardButton(text=_t("🧾 QR Manual",lang),callback_data=f"manualpkg:{prefix}")],
        [InlineKeyboardButton(text=_t("🔙 Kembali",lang),callback_data="home")]
    ])
