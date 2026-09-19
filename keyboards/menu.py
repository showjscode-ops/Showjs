
from aiogram.types import InlineKeyboardMarkup,InlineKeyboardButton
def home_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Up File",callback_data="upfile"),InlineKeyboardButton(text="📥 Get File",callback_data="getfile")],
        [InlineKeyboardButton(text="🔑 Code",callback_data="my_code"),InlineKeyboardButton(text="🏆 Top 10 Code",callback_data="top_codes")],
        [InlineKeyboardButton(text="💎 Buy VIP",callback_data="buy_vip"),InlineKeyboardButton(text="⭐ Buy Star",callback_data="buy_stars")],
        [InlineKeyboardButton(text="🪙 Buy Poin",callback_data="buy_points"),InlineKeyboardButton(text="💳 Deposit",callback_data="deposit")],
        [InlineKeyboardButton(text="🎁 Cek In",callback_data="checkin"),InlineKeyboardButton(text="📂 Menu Lainnya",callback_data="menu_lainnya")]
    ])
def other_menu_kb(creator=False):
    rows=[
      [InlineKeyboardButton(text="📋 My Code",callback_data="my_code"),InlineKeyboardButton(text="👥 Group Code",callback_data="group_code")],
      [InlineKeyboardButton(text="🏆 Top 10 Code",callback_data="top_codes")]
    ]
    if creator: rows.append([InlineKeyboardButton(text="👑 Creator",callback_data="creator_dashboard"),InlineKeyboardButton(text="💸 Withdraw",callback_data="withdraw")])
    rows.append([InlineKeyboardButton(text="🎁 Check In",callback_data="checkin"),InlineKeyboardButton(text="❓ Help",callback_data="help")])
    rows.append([InlineKeyboardButton(text="🔙 Kembali",callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
def provider_kb(prefix):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚡ BayarGG",callback_data=f"provider:{prefix}:bayargg")],[InlineKeyboardButton(text="💳 Cashi",callback_data=f"provider:{prefix}:cashi")],[InlineKeyboardButton(text="🧾 QR Manual",callback_data=f"manualpkg:{prefix}")],[InlineKeyboardButton(text="🔙 Kembali",callback_data="home")]])
