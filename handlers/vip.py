from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from database import get_pool
from utils.payments import create_purchase, qr_bytes, enabled
from utils.callback_loading import loading
from utils.i18n import get_lang, translate

router = Router()


def _lang(user_id: int) -> str:
    try:
        return get_lang(user_id) or "id"
    except Exception:
        return "id"


def _t(lang: str, key: str, **kwargs) -> str:
    texts = {
        "buy_vip": {
            "id": "💎 <b>BUY VIP</b>\n\nPilih paket:",
            "en": "💎 <b>BUY VIP</b>\n\nChoose a package:",
            "zh": "💎 <b>购买 VIP</b>\n\n请选择套餐：",
        },
        "back": {"id": "🔙 Kembali", "en": "🔙 Back", "zh": "🔙 返回"},
        "unavailable": {
            "id": "Paket tidak tersedia.",
            "en": "Package is not available.",
            "zh": "套餐不可用。",
        },
        "payment_failed": {
            "id": "❌ Pembayaran ditutup atau gagal.",
            "en": "❌ Payment is closed or failed.",
            "zh": "❌ 支付已关闭或失败。",
        },
        "check_payment": {
            "id": "🔄 Cek Pembayaran",
            "en": "🔄 Check Payment",
            "zh": "🔄 检查支付",
        },
        "cancel": {"id": "❌ Batal", "en": "❌ Cancel", "zh": "❌ 取消"},
        "after_pay": {
            "id": "Setelah membayar, tekan Cek Pembayaran.",
            "en": "After paying, press Check Payment.",
            "zh": "完成支付后，请点击“检查支付”。",
        },
        "manual_qr_missing": {
            "id": "❌ QR manual belum dipasang.",
            "en": "❌ Manual QR has not been configured yet.",
            "zh": "❌ 手动 QR 尚未配置。",
        },
        "manual_title": {
            "id": "🧾 <b>QR MANUAL VIP</b>",
            "en": "🧾 <b>VIP MANUAL QR</b>",
            "zh": "🧾 <b>VIP 手动 QR</b>",
        },
        "send_proof": {
            "id": "Kirim screenshot bukti pembayaran.",
            "en": "Send a screenshot of your payment proof.",
            "zh": "请发送支付凭证截图。",
        },
    }
    return texts.get(key, {}).get(lang, texts.get(key, {}).get("id", key)).format(**kwargs)


@router.callback_query(F.data.startswith("buy_vip"))
async def listvip(c):
    lang = _lang(c.from_user.id)
    rows = await (await get_pool()).fetch(
        "SELECT code,name,price,duration_days FROM vip_packages WHERE active ORDER BY price"
    )
    kb = [
        [
            InlineKeyboardButton(
                text=f'💎 {r["name"]} • Rp{int(r["price"]):,}'.replace(",", "."),
                callback_data=f'vip:{r["code"]}',
            )
        ]
        for r in rows
    ]
    kb.append([InlineKeyboardButton(text=_t(lang, "back"), callback_data="home")])
    await c.message.edit_text(
        _t(lang, "buy_vip"),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )


@router.callback_query(F.data.startswith("vip:"))
async def choose(c):
    lang = _lang(c.from_user.id)
    code = c.data.split(":", 1)[1]
    r = await (await get_pool()).fetchrow(
        "SELECT * FROM vip_packages WHERE code=$1 AND active", code
    )
    if not r:
        return await c.answer(_t(lang, "unavailable"), show_alert=True)

    rows = []
    if await enabled("bayargg"):
        rows.append([
            InlineKeyboardButton(
                text="⚡ BayarGG",
                callback_data=f"vip_provider:{code}:bayargg",
            )
        ])
    if await enabled("cashi"):
        rows.append([
            InlineKeyboardButton(
                text="💳 Cashi",
                callback_data=f"vip_provider:{code}:cashi",
            )
        ])
    if await enabled("manual"):
        rows.append([
            InlineKeyboardButton(
                text="🧾 QR Manual",
                callback_data=f"vip_manual:{code}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text=_t(lang, "back"),
            callback_data="buy_vip",
        )
    ])

    await c.message.edit_text(
        f'💎 {r["name"]}\n💵 Rp{int(r["price"]):,}'.replace(",", "."),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("vip_provider:"))
async def pay(c):
    lang = _lang(c.from_user.id)
    _, code, provider = c.data.split(":")
    r = await (await get_pool()).fetchrow(
        "SELECT * FROM vip_packages WHERE code=$1 AND active", code
    )

    result, status = await create_purchase(
        c.from_user.id,
        "vip",
        r["duration_days"],
        r["price"],
        provider,
        c.from_user.full_name,
    )
    if not result:
        return await c.answer(_t(lang, "payment_failed"), show_alert=True)

    data = qr_bytes(result.get("qr_string"))
    await c.answer()

    text = (
        f'💎 <b>{r["name"]}</b>\n'
        f'💵 Rp{int(r["price"]):,}\n'
        f'🏦 {provider.upper()}\n'
        f'🧾 <code>{result["invoice_id"]}</code>\n\n'
        f'{_t(lang, "after_pay")}'
    ).replace(",", ".")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_t(lang, "check_payment"),
                    callback_data=f'paycheck:{result["invoice_id"]}',
                )
            ],
            [
                InlineKeyboardButton(
                    text=_t(lang, "cancel"),
                    callback_data=f'paycancel:{result["invoice_id"]}',
                )
            ],
        ]
    )

    if data:
        await c.message.answer_photo(
            BufferedInputFile(data, filename="vip.png"),
            caption=text,
            parse_mode="HTML",
            reply_markup=kb,
        )
    else:
        await c.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb,
        )


@router.callback_query(F.data.startswith("vip_manual:"))
async def vip_manual(c, state):
    from handlers.payments import ManualProofState

    lang = _lang(c.from_user.id)
    code = c.data.split(":", 1)[1]
    r = await (await get_pool()).fetchrow(
        "SELECT * FROM vip_packages WHERE code=$1 AND active", code
    )
    qr = await (await get_pool()).fetchval(
        "SELECT value FROM settings WHERE key='manual_qr_file_id'"
    )

    if not qr:
        return await c.answer(_t(lang, "manual_qr_missing"), show_alert=True)

    await state.set_state(ManualProofState.proof)
    await state.update_data(
        kind="vip",
        quantity=int(r["duration_days"]),
        amount=int(r["price"]),
        target_code=None,
    )

    caption = (
        f'{_t(lang, "manual_title")}\n\n'
        f'{r["name"]}\n'
        f'💰 Rp{int(r["price"]):,}\n\n'
        f'{_t(lang, "send_proof")}'
    ).replace(",", ".")

    await c.message.answer_photo(
        qr,
        caption=caption,
        parse_mode="HTML",
    )
