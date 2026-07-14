import hmac
import hashlib
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status, HTTPException, Header
from pydantic import BaseModel, Field
from config import bot, CRYPTOBOT_TOKEN, CRYPTO_WEBHOOK_SECRET, ADMINS, DISPLAY_CURRENCY
from utils.models import Users, Payments, Settings, init_db, db
from cryptobot import Invoice
from config import PNMVPN_HMAC_SECRET

app = FastAPI()
init_db()


def verify_crypto_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    secret = hashlib.sha256(CRYPTOBOT_TOKEN.encode()).digest()
    expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post(f"/{CRYPTO_WEBHOOK_SECRET}")
async def root(
    request: Request,
    crypto_pay_api_signature: str | None = Header(default=None),
):
    raw_body = await request.body()
    if not verify_crypto_webhook_signature(raw_body, crypto_pay_api_signature):
        raise HTTPException(status_code=403, detail='Bad Crypto Pay signature')
    try:
        data = await request.json()
    except ValueError as error:
        raise HTTPException(status_code=400, detail='Invalid JSON') from error
    if data.get('update_type', '') != 'invoice_paid':
        return status.HTTP_200_OK
    try:
        invoice = Invoice(**data.get('payload', {}))
        payload_parts = invoice.payload.split('_')
        order_id = int(payload_parts[1])
    except (TypeError, ValueError, IndexError) as error:
        raise HTTPException(status_code=400, detail='Invalid invoice payload') from error
    try:
        payment = Payments.get_by_id(order_id)
    except Exception as e:
        for admin in ADMINS:
            await bot.send_message(int(admin),
                                   f'❌ Пришел неопознанный платеж под номером #{order_id}\n'
                                   f'Сумма: {invoice.amount} {DISPLAY_CURRENCY}\n'
                                   f'error: {e}')
        return status.HTTP_402_PAYMENT_REQUIRED
    if float(payment.amount) != float(invoice.amount):
        for admin in ADMINS:
            await bot.send_message(int(admin),
                                   f'❌ Пришел опознанный платеж под номером #{order_id} с другой суммой\n'
                                   f'Сумма: {payment.amount} {DISPLAY_CURRENCY}\n'
                                   f'Сумма списания: {invoice.amount} {DISPLAY_CURRENCY}\n')
        return status.HTTP_402_PAYMENT_REQUIRED
    referral_notification = None
    with db.atomic():
        claimed = (Payments.update(finished=1)
                   .where((Payments.id == payment.id) & (Payments.finished == 0))
                   .execute())
        if not claimed:
            return status.HTTP_200_OK
        user: Users = Users.get_or_none(Users.user_id == payment.user_id)
        if not user:
            raise HTTPException(status_code=404, detail='Payment user not found')
        user.balance += payment.amount
        user.can_withdraw_money = False
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
        ref_user_id, reward = referral_notification
        try:
            username = await bot.get_chat(user.user_id)
            await bot.send_message(
                ref_user_id,
                f'✅ Вы получили вознаграждение за своего реферала @{username.username or user.user_id} '
                f'в размере {reward} 💎',
            )
        except Exception as error:
            print(f'Unable to notify referral reward: {error}')

    try:
        await bot.edit_message_text(text=f'✅ Платёж успешно выполнен! Ваш баланс пополнен на: {payment.amount} {DISPLAY_CURRENCY}',
                                    chat_id=payment.user_id,
                                    message_id=payment.message_id)
    except Exception as error:
        print(f'Unable to update payment message #{payment.id}: {error}')
    try:
        for admin in ADMINS:
            await bot.send_message(int(admin), f'''🆕 Поступил новый платёж 🆕\n
👤 Новый баланс пользователя: {user.balance}
🆔 Номер заказа: {payment.id}
🪪 Логин: {user.username}
#️⃣ Telegram ID: {user.user_id}
💰 Сумма: {payment.amount} {DISPLAY_CURRENCY} [{invoice.amount} {DISPLAY_CURRENCY}]''')
    except Exception as error:
        print(f'Unable to notify admins about payment #{payment.id}: {error}')
    return status.HTTP_200_OK


class TrialCreditIn(BaseModel):
    user_id: int = Field(..., description="Telegram user_id")

def _calc_signature(user_id: int) -> str:
    """
    Canonical string: just user_id as string.
    You can change to JSON canonical later if needed.
    """
    msg = str(user_id).encode()
    return hmac.new(PNMVPN_HMAC_SECRET.encode(), msg, hashlib.sha256).hexdigest()


@app.post("/pnmvpn/trial/credit")
def credit_trial_bonus(payload: TrialCreditIn, x_signature: str | None = Header(default=None)):
    if not PNMVPN_HMAC_SECRET:
        raise HTTPException(status_code=500, detail="HMAC secret is not configured")

    if not x_signature:
        raise HTTPException(status_code=401, detail="Missing X-Signature header")

    expected = _calc_signature(payload.user_id)

    if not hmac.compare_digest(x_signature, expected):
        raise HTTPException(status_code=403, detail="Bad signature")

    user = Users.get_or_none(Users.user_id == payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if getattr(user, "trial_bonus_claimed", False):
        return {
            "status": "already_claimed",
            "user_id": payload.user_id,
            "trial_bonus_claimed": True,
            "prize_balance": user.prize_balance,
        }

    settings = Settings.get()
    reward = settings.pnmvpn_trial_reward
    claimed_at = datetime.now(timezone.utc)
    with db.atomic():
        updated = (Users.update(
            prize_balance=Users.prize_balance + reward,
            trial_bonus_claimed=True,
            trial_bonus_claimed_at=claimed_at,
        ).where(
            (Users.id == user.id) & (Users.trial_bonus_claimed == False)
        ).execute())
    if not updated:
        user = Users.get_by_id(user.id)
        return {
            "status": "already_claimed",
            "user_id": payload.user_id,
            "trial_bonus_claimed": True,
            "prize_balance": user.prize_balance,
        }
    user = Users.get_by_id(user.id)

    return {
        "status": "credited",
        "user_id": payload.user_id,
        "amount": reward,
        "trial_bonus_claimed": True,
        "trial_bonus_claimed_at": (
            user.trial_bonus_claimed_at.isoformat()
            if hasattr(user.trial_bonus_claimed_at, 'isoformat')
            else user.trial_bonus_claimed_at
        ),
        "prize_balance": user.prize_balance
    }
