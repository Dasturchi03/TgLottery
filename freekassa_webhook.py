import hashlib
import hmac

from fastapi import Request, Query, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from typing import Dict
from config import bot, FREEKASSA_MERCHANT_ID, FREEKASSA_SECRET_WORD_2, DISPLAY_CURRENCY
from utils.models import Payments, Users, Settings, db, init_db

app = FastAPI()
init_db()


def verify_freekassa_signature(merchant_id: str, amount: str, order_id: str, signature: str) -> bool:
    if not FREEKASSA_SECRET_WORD_2:
        return False
    check_string = f'{merchant_id}:{amount}:{FREEKASSA_SECRET_WORD_2}:{order_id}'
    expected = hashlib.md5(check_string.encode()).hexdigest()
    return hmac.compare_digest(signature.lower(), expected.lower())


@app.post("/payment-notify")
async def payment_handler(request: Request,
                          MERCHANT_ID=Query(),
                          AMOUNT=Query(),
                          intid=Query(),
                          MERCHANT_ORDER_ID=Query(),
                          P_EMAIL=Query(),
                          P_PHONE=Query(),
                          CUR_ID=Query(),
                          commission=Query(),
                          SIGN=Query()):
    """Receive pay-event from FreeKassa"""
    if FREEKASSA_MERCHANT_ID and str(MERCHANT_ID) != FREEKASSA_MERCHANT_ID:
        raise HTTPException(status_code=403, detail='Wrong merchant')
    if not verify_freekassa_signature(str(MERCHANT_ID), str(AMOUNT), str(MERCHANT_ORDER_ID), str(SIGN)):
        raise HTTPException(status_code=403, detail='Wrong signature')
    payment: Payments = Payments.get_by_id(int(MERCHANT_ORDER_ID))
    if float(payment.amount) != float(AMOUNT):
        raise HTTPException(status_code=400, detail='Wrong payment amount')
    referral_notification = None
    with db.atomic():
        claimed = (Payments.update(finished=1)
                   .where((Payments.id == payment.id) & (Payments.finished == 0))
                   .execute())
        if not claimed:
            return HTMLResponse('YES')
        user = Users.get_or_none(Users.user_id == payment.user_id)
        if not user:
            raise HTTPException(status_code=404, detail='Payment user not found')
        user.balance += payment.amount
        if not user.first_buy:
            user.first_buy = 1
        if user.ref_user_id and not user.ref_payed:
            ref_user = Users.get_or_none(Users.user_id == user.ref_user_id)
            if ref_user:
                settings = Settings.get()
                user.ref_payed = 1
                ref_user.prize_balance += settings.cost_invite
                ref_user.ref_money += settings.cost_invite
                ref_user.save()
                referral_notification = (ref_user.user_id, settings.cost_invite)
        user.save()
    if referral_notification:
        try:
            ref_user_id, reward = referral_notification
            username = await bot.get_chat(user.user_id)
            await bot.send_message(ref_user_id,
                                   f'✅ Вы получили вознаграждение за своего реферала @{username.username or user.user_id} '
                                   f'в размере {reward} 💎')
        except Exception as e:
            print(f'Unable to notify referral reward: {e}')
    try:
        await bot.delete_message(payment.user_id, payment.message_id)
        await bot.send_message(payment.user_id, f"✅ Ваш баланс пополнен на {payment.amount} {DISPLAY_CURRENCY}")
    except Exception as e:
        print(f'Unable to notify payment user: {e}')
    return HTMLResponse('YES')
