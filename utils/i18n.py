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

# Broad UI word/phrase fallback. This is intentionally limited to common bot UI
# vocabulary; it avoids translating arbitrary user-generated identifiers.
WORD_DICT = {
"en": {
 "Kirim":"Send","Masukkan":"Enter","Masukkan username":"Enter username","Masukkan nominal":"Enter amount","Tidak ada":"No","ada":"available","gagal":"failed","berhasil":"successful","sukses":"success","Proses":"Process","proses":"process","Sedang":"Currently","tunggu":"wait","Tunggu":"Please wait","pilih":"choose","Pilih":"Choose","untuk":"for","dengan":"with","tanpa":"without","milik":"owned by","sendiri":"own","dibuka":"opened","buka":"open","membuka":"opening","tersedia":"available","tidak":"not","ditemukan":"found","aktif":"active","nonaktif":"inactive","Harga":"Price","harga":"price","Jumlah":"Amount","jumlah":"amount","Total":"Total","total":"total","media":"media","Code":"Code","code":"code","User":"User","user":"user","Admin":"Admin","Creator":"Creator","Kreator":"Creator","Poin":"Points","poin":"points","Star":"Stars","Saldo":"Balance","VIP":"VIP","Gratis":"Free","FREE":"FREE","Bayar":"Pay","Pembayaran":"Payment","Pembayaran":"Payment","beli":"buy","Beli":"Buy","Belum":"Not yet","sudah":"already","Hari":"Days","hari":"days","Jam":"Hours","jam":"hours","menit":"minutes","detik":"seconds","waktu":"time","akses":"access","Akses":"Access","batas":"limit","Batas":"Limit","perpanjangan":"extension","Perpanjangan":"Extension","akun":"account","Akun":"Account","bahasa":"language","Bahasa":"Language","kembali":"back","Kembali":"Back","Lanjut":"Continue","Batal":"Cancel","Selesai":"Done","Simpan":"Save","Hapus":"Delete","Edit":"Edit","Tambah":"Add","Pilih":"Choose","Daftar":"Register","Masuk":"Login","Keluar":"Logout","notifikasi":"notification","Notifikasi":"Notification","alasan":"reason","Alasan":"Reason","nama":"name","Nama":"Name","judul":"title","Judul":"Title","tag":"tag","Tag":"Tag","role":"role","Role":"Role","status":"status","Status":"Status","saldo":"balance","poin":"points","star":"stars","withdraw":"withdrawal","Withdraw":"Withdrawal","manual":"manual","otomatis":"automatically","Otomatis":"Automatically","kirim":"send","terima":"receive","diterima":"received","sisa":"remaining","satu":"one","semua":"all","media":"media","Views":"Views","Like":"Like","Hate":"Hate","Favorit":"Favorite","Favorit":"Favorite","Error":"Error","Kesalahan":"Error","berikut":"following","silakan":"please","Silakan":"Please","contoh":"example","Contoh":"Example","catatan":"note","Catatan":"Note"
},
"zh": {
 "Kirim":"发送","Masukkan":"输入","Masukkan username":"输入用户名","Masukkan nominal":"输入金额","Tidak ada":"没有","ada":"有","gagal":"失败","berhasil":"成功","sukses":"成功","Proses":"处理","proses":"处理","Sedang":"正在","tunggu":"等待","Tunggu":"请稍候","pilih":"选择","Pilih":"选择","untuk":"用于","dengan":"使用","tanpa":"无需","milik":"属于","sendiri":"自己","dibuka":"已打开","buka":"打开","membuka":"打开","tersedia":"可用","tidak":"不","ditemukan":"找到","aktif":"启用","nonaktif":"停用","Harga":"价格","harga":"价格","Jumlah":"数量","jumlah":"数量","Total":"总计","total":"总计","media":"媒体","Code":"代码","code":"代码","User":"用户","user":"用户","Admin":"管理员","Creator":"创作者","Kreator":"创作者","Poin":"积分","poin":"积分","Star":"Star","Saldo":"余额","VIP":"VIP","Gratis":"免费","FREE":"免费","Bayar":"支付","Pembayaran":"支付","beli":"购买","Beli":"购买","Belum":"尚未","sudah":"已经","Hari":"天","hari":"天","Jam":"小时","jam":"小时","menit":"分钟","detik":"秒","waktu":"时间","akses":"访问","Akses":"访问","batas":"限制","Batas":"限制","perpanjangan":"续期","Perpanjangan":"续期","akun":"账户","Akun":"账户","bahasa":"语言","Bahasa":"语言","kembali":"返回","Kembali":"返回","Lanjut":"继续","Batal":"取消","Selesai":"完成","Simpan":"保存","Hapus":"删除","Edit":"编辑","Tambah":"添加","Daftar":"注册","Masuk":"登录","Keluar":"退出","notifikasi":"通知","Notifikasi":"通知","alasan":"原因","Alasan":"原因","nama":"名称","Nama":"名称","judul":"标题","Judul":"标题","tag":"标签","Tag":"标签","role":"角色","Role":"角色","status":"状态","Status":"状态","saldo":"余额","poin":"积分","star":"Star","withdraw":"提现","Withdraw":"提现","manual":"手动","otomatis":"自动","Otomatis":"自动","kirim":"发送","terima":"接收","diterima":"已收到","sisa":"剩余","semua":"全部","Views":"浏览","Like":"点赞","Hate":"踩","Favorit":"收藏","Error":"错误","Kesalahan":"错误","berikut":"如下","silakan":"请","Silakan":"请","contoh":"示例","Contoh":"示例","catatan":"备注","Catatan":"备注"
}
}

def translate(text: str | None, lang: str) -> str | None:
    if not text or lang == "id" or lang not in DICT:
        return text
    out = text
    # Longer phrases first, exact substring replacement.
    for src, dst in sorted(DICT[lang].items(), key=lambda x: len(x[0]), reverse=True):
        out = out.replace(src, dst)
    # Common dynamic labels. Apply only after exact phrases.
    if lang in WORD_DICT:
        for src, dst in sorted(WORD_DICT[lang].items(), key=lambda x: len(x[0]), reverse=True):
            # Word-boundary replacement for ordinary UI vocabulary.
            out = re.sub(r'(?<![A-Za-zÀ-ÿ])' + re.escape(src) + r'(?![A-Za-zÀ-ÿ])', dst, out)
    if lang == "en":
        out = re.sub(r'(\d+)\s+media\b', r'\1 media', out)
    elif lang == "zh":
        out = re.sub(r'(\d+)\s+media\b', r'\1 个媒体', out)
    return out
