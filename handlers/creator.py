from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import get_pool
from utils.callback_loading import loading
from utils.i18n import get_lang

router = Router()


TRANSLATIONS = {
    "id": {
        "only_creator": "Hanya Creator.",
        "title": "Creator",
        "earnings_balance": "Saldo Pendapatan",
        "today": "Pendapatan Hari Ini",
        "month": "Pendapatan Bulan Ini",
        "sales": "Total Penjualan",
        "opened": "Total Dibuka",
        "paid_upload": "Paid upload hari ini",
        "done": "SUDAH",
        "required": "WAJIB",
        "back": "🔙 Kembali",
    },
    "en": {
        "only_creator": "Creator only.",
        "title": "Creator",
        "earnings_balance": "Earnings Balance",
        "today": "Today's Earnings",
        "month": "This Month's Earnings",
        "sales": "Total Sales",
        "opened": "Total Opened",
        "paid_upload": "Paid upload today",
        "done": "DONE",
        "required": "REQUIRED",
        "back": "🔙 Back",
    },
    "zh": {
        "only_creator": "仅限 Creator。",
        "title": "Creator",
        "earnings_balance": "收益余额",
        "today": "今日收益",
        "month": "本月收益",
        "sales": "总销售量",
        "opened": "总打开次数",
        "paid_upload": "今日付费上传",
        "done": "已完成",
        "required": "必须",
        "back": "🔙 返回",
    },
}


def tr(lang: str, key: str) -> str:
    lang = lang if lang in TRANSLATIONS else "id"
    return TRANSLATIONS[lang][key]


@router.callback_query(F.data == "creator_dashboard")
async def creator(c: CallbackQuery):
    # Always read the user's currently selected Dashboard language.
    lang = await get_lang(c.from_user.id)
    if lang not in TRANSLATIONS:
        lang = "id"

    p = await get_pool()
    r = await p.fetchrow(
        """
        SELECT earnings, total_sales
        FROM users
        WHERE user_id=$1
          AND is_creator
          AND creator_status='approved'
        """,
        c.from_user.id,
    )

    if not r:
        return await c.answer(tr(lang, "only_creator"), show_alert=True)

    today = await p.fetchval(
        """
        SELECT COALESCE(SUM(creator_income_idr), 0)
        FROM unlock_transactions
        WHERE creator_id=$1
          AND created_at::date=CURRENT_DATE
        """,
        c.from_user.id,
    ) or 0

    month = await p.fetchval(
        """
        SELECT COALESCE(SUM(creator_income_idr), 0)
        FROM unlock_transactions
        WHERE creator_id=$1
          AND date_trunc('month', created_at)=date_trunc('month', NOW())
        """,
        c.from_user.id,
    ) or 0

    opened = await p.fetchval(
        """
        SELECT COUNT(*)
        FROM unlock_transactions
        WHERE creator_id=$1
        """,
        c.from_user.id,
    ) or 0

    paid_today = bool(
        await p.fetchval(
            """
            SELECT 1
            FROM files
            WHERE owner_id=$1
              AND price_idr>0
              AND created_at::date=CURRENT_DATE
            LIMIT 1
            """,
            c.from_user.id,
        )
    )

    def rupiah(value):
        return f"Rp {int(value or 0):,}".replace(",", ".")

    text = (
        f"👑 <b>{tr(lang, 'title')}</b>\n\n"
        f"💰 {tr(lang, 'earnings_balance')}\n"
        f"{rupiah(r['earnings'])}\n\n"
        f"💵 {tr(lang, 'today')}\n"
        f"{rupiah(today)}\n\n"
        f"📅 {tr(lang, 'month')}\n"
        f"{rupiah(month)}\n\n"
        f"📦 {tr(lang, 'sales')}\n"
        f"{int(r['total_sales'] or 0)}\n\n"
        f"👁 {tr(lang, 'opened')}\n"
        f"{int(opened)}\n\n"
        f"{tr(lang, 'paid_upload')}: "
        f"<b>{tr(lang, 'done') if paid_today else tr(lang, 'required')}</b>"
    )

    await loading(c)

    await c.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=tr(lang, "back"),
                        callback_data="menu_lainnya",
                    )
                ]
            ]
        ),
    )
