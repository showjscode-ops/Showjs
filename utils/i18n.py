from __future__ import annotations
import re
from database import get_pool

SUPPORTED = {"id": "🇮🇩 Indonesia", "en": "🇬🇧 English", "zh": "🇨🇳 中文"}

async def get_lang(user_id: int) -> str:
    try:
        v = await (await get_pool()).fetchval("SELECT COALESCE(language,'') FROM users WHERE user_id=$1", user_id)
        return v if v in SUPPORTED else ""
    except Exception:
        return ""

async def set_lang(user_id: int, lang: str):
    if lang not in SUPPORTED:
        lang = "id"
    await (await get_pool()).execute("UPDATE users SET language=$1 WHERE user_id=$2", lang, user_id)

LANG_KB = {
    "id": "Pilih Bahasa",
    "en": "Choose Language",
    "zh": "选择语言",
}

# Exact/phrase translations used by the bot UI. User supplied titles, tags, codes,
# usernames and numbers are deliberately not translated.
DICT = {
"en": {
"MENU LAINNYA":"MORE MENU","Dashboard":"Dashboard","ID":"ID","Status":"Status","Saldo":"Balance","Poin":"Points","Star":"Stars",
"FREE":"FREE","VIP":"VIP","CREATOR":"CREATOR","Belum paham cara menggunakan bot? Klik":"Need help using the bot? Tap",
"Help":"Help","Up File":"Upload File","Get File":"Get File","Code":"Code","Top 10 Code":"Top 10 Codes","Buy VIP":"Buy VIP","Buy Star":"Buy Stars","Buy Poin":"Buy Points","Deposit":"Deposit","Cek In":"Check In","Menu Lainnya":"More Menu",
"My Code":"My Code","Group Code":"Group Code","Jadi Kreator":"Become Creator","Creator":"Creator","Withdraw":"Withdraw","Kembali":"Back","🔙 Kembali":"🔙 Back",
"📥 Kirim CODE yang ingin dibuka.":"📥 Send the CODE you want to open.",
"❌ Code tidak valid.":"❌ Invalid code.","❌ Code tidak ditemukan.":"❌ Code not found.",
"📥 Buka Code":"📥 Open Code","📂 Buka Code (Gratis)":"📂 Open Code (Free)","CODE MILIK SENDIRI":"YOUR OWN CODE",
"Media milikmu dapat dibuka tanpa Poin, Star, atau Saldo.":"Your own media can be opened without Points, Stars, or Balance.",
"OPEN CODE":"OPEN CODE","Pilih cara membuka:":"Choose how to open:","Pilih pembayaran:":"Choose payment:",
"🆓 FREE CODE":"🆓 FREE CODE","💰 Harga:":"💰 Price:","Media":"Media","Views":"Views",
"Buka Gratis (VIP)":"Open Free (VIP)","Buka dengan":"Open with","Poin":"Points","Star":"Stars","Saldo":"Balance",
"Like":"Like","Hate":"Hate","Favorit":"Favorite","Batal":"Cancel","Lanjut kirim":"Continue sending",
"Semua media selesai dikirim.":"All media have been sent.","MEDIA TIDAK TERSEDIA":"MEDIA NOT AVAILABLE",
"Media gagal dikirim:":"Media failed to send:","Media ke":"Media","Semua media selesai":"All media sent",
"Done Create":"Done Create","Judul":"Title","Tag":"Tag","Type":"Type","total":"total",
"FREE CODE":"FREE CODE","Bagikan code ini ke teman-teman untuk membuka media ini.":"Share this code with friends to open the media.",
"BUY VIP":"BUY VIP","Pilih paket:":"Choose a package:","Paket tidak tersedia.":"Package unavailable.",
"Pembayaran ditutup atau gagal.":"Payment is closed or failed.","Setelah membayar, tekan Cek Pembayaran.":"After paying, tap Check Payment.",
"Cek Pembayaran":"Check Payment","Hanya Creator.":"Creator only.","Withdraw sedang ditutup.":"Withdraw is currently closed.",
"❌ Nominal tidak valid.":"❌ Invalid amount.","❌ Nominal tidak valid":"❌ Invalid amount",
"Saldo tidak cukup.":"Balance is insufficient.","❌ Saldo tidak cukup.":"❌ Insufficient balance.",
"Pengajuan WD berhasil. Menunggu admin.":"✅ Withdrawal request submitted. Waiting for admin.",
"📤 Up File":"📤 Upload File","📥 Get File":"📥 Get File","📂 Menu Lainnya":"📂 More Menu",
"Bahasa":"Language","Ganti Bahasa":"Change Language","Pilih bahasa:":"Choose your language:",
},
"zh": {
"MENU LAINNYA":"更多菜单","Dashboard":"控制面板","ID":"ID","Status":"状态","Saldo":"余额","Poin":"积分","Star":"Star",
"FREE":"免费","VIP":"VIP","CREATOR":"创作者","Belum paham cara menggunakan bot? Klik":"不了解如何使用？点击",
"Help":"帮助","Up File":"上传文件","Get File":"获取文件","Code":"代码","Top 10 Code":"代码排行榜","Buy VIP":"购买 VIP","Buy Star":"购买 Star","Buy Poin":"购买积分","Deposit":"充值","Cek In":"签到","Menu Lainnya":"更多菜单",
"My Code":"我的代码","Group Code":"群组代码","Jadi Kreator":"成为创作者","Creator":"创作者","Withdraw":"提现","Kembali":"返回","🔙 Kembali":"🔙 返回",
"📥 Kirim CODE yang ingin dibuka.":"📥 发送要打开的 CODE。",
"❌ Code tidak valid.":"❌ CODE 无效。","❌ Code tidak ditemukan.":"❌ 未找到 CODE。",
"📥 Buka Code":"📥 打开 CODE","📂 Buka Code (Gratis)":"📂 免费打开 CODE","CODE MILIK SENDIRI":"自己的 CODE",
"Media milikmu dapat dibuka tanpa Poin, Star, atau Saldo.":"自己的媒体无需积分、Star或余额即可打开。",
"OPEN CODE":"打开 CODE","Pilih cara membuka:":"选择打开方式：","Pilih pembayaran:":"选择支付方式：",
"🆓 FREE CODE":"🆓 免费 CODE","💰 Harga:":"💰 价格：","Media":"媒体","Views":"浏览",
"Buka Gratis (VIP)":"VIP 免费打开","Buka dengan":"使用","Poin":"积分","Star":"Star","Saldo":"余额",
"Like":"点赞","Hate":"踩","Favorit":"收藏","Batal":"取消","Lanjut kirim":"继续发送",
"Semua media selesai dikirim.":"所有媒体发送完成。","MEDIA TIDAK TERSEDIA":"媒体不可用",
"Media gagal dikirim:":"媒体发送失败：","Media ke":"媒体","Semua media selesai":"所有媒体发送完成",
"Done Create":"创建完成","Judul":"标题","Tag":"标签","Type":"类型","total":"总计",
"FREE CODE":"免费 CODE","Bagikan code ini ke teman-teman untuk membuka media ini.":"分享此 CODE 给朋友即可打开媒体。",
"BUY VIP":"购买 VIP","Pilih paket:":"选择套餐：","Paket tidak tersedia.":"套餐不可用。",
"Pembayaran ditutup atau gagal.":"支付已关闭或失败。","Setelah membayar, tekan Cek Pembayaran.":"付款后点击检查支付。",
"Cek Pembayaran":"检查支付","Hanya Creator.":"仅限创作者。","Withdraw sedang ditutup.":"提现目前已关闭。",
"❌ Nominal tidak valid.":"❌ 金额无效。","Saldo tidak cukup.":"余额不足。","❌ Saldo tidak cukup.":"❌ 余额不足。",
"Pengajuan WD berhasil. Menunggu admin.":"✅ 提现申请成功，等待管理员处理。",
"📤 Up File":"📤 上传文件","📥 Get File":"📥 获取文件","📂 Menu Lainnya":"📂 更多菜单",
"Bahasa":"语言","Ganti Bahasa":"切换语言","Pilih bahasa:":"选择语言：",
}
}

def translate(text: str | None, lang: str) -> str | None:
    if not text or lang == "id" or lang not in DICT:
        return text
    out = text
    # Longer phrases first, exact substring replacement.
    for src, dst in sorted(DICT[lang].items(), key=lambda x: len(x[0]), reverse=True):
        out = out.replace(src, dst)
    # Common dynamic labels.
    if lang == "en":
        out = re.sub(r'(\d+)\s+media\b', r'\1 media', out)
    elif lang == "zh":
        out = re.sub(r'(\d+)\s+media\b', r'\1 个媒体', out)
    return out
