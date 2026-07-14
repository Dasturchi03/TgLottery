from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from utils.models import Users, Tickets, BigRuffleSettings
from utils.keyboards import next_kb
from utils.playout import start_ruffle
from utils.verification import has_deposit
from config import DISPLAY_CURRENCY


big_ruffle_router = Router()


@big_ruffle_router.callback_query(F.data == 'big_ruffle show')
async def big_ruffle_handle(callback: CallbackQuery):
    settings: BigRuffleSettings = BigRuffleSettings.get()
    await callback.message.edit_text(
        f'''⚠️ Вы уверены что хотите занять слот? Стоимость {settings.price} {DISPLAY_CURRENCY} спишется с Вашего баланса в профиле''',
        reply_markup=next_kb(f'big_ruffle buy'))


@big_ruffle_router.callback_query(F.data == 'big_ruffle amount')
async def big_ruffle_handle(callback: CallbackQuery):
    tickets = Tickets.select().where(Tickets.ruffle_id == 0)
    big_ruffle: BigRuffleSettings = BigRuffleSettings.get()
    amount = (len(tickets) * big_ruffle.price) - 10
    if amount < big_ruffle.fake_amount:
        show_amount = big_ruffle.fake_amount
    else:
        show_amount = amount - (amount * big_ruffle.profit / 100)
    await callback.answer(f'👀 Сумма в мешке: {show_amount} {DISPLAY_CURRENCY}')


@big_ruffle_router.callback_query(F.data == 'big_ruffle buy')
async def buy_big_ruffle_handle(callback: CallbackQuery):
    ruffle_id = 0
    ruffle: BigRuffleSettings = BigRuffleSettings.get()

    if not ruffle.activity:
        return await callback.message.edit_text('⛔ Этот розыгрыш на данный момент не доступен')

    # NEW: deposit required
    if not has_deposit(callback.from_user.id):
        return await callback.message.edit_text(
            'Этот розыгрыш доступен только для верифицированных пользователей. '
            'Для верификации необходимо пополнить баланс 1 раз.'
        )

    user_tickets = (Tickets.select().where(Tickets.user_id == callback.from_user.id).
                    where(Tickets.ruffle_id == ruffle_id))
    user: Users = Users.get_or_none(Users.user_id == callback.from_user.id)

    if not user:
        return await callback.message.edit_text('⛔ Ошибка профиля. Нажмите /start')

    if user.balance >= ruffle.price:
        user.balance -= ruffle.price
        Tickets.create(user_id=callback.from_user.id, ruffle_id=ruffle_id)
        await callback.message.edit_text(
            f'✅ Вы заняли слот в событии «Мешок денег» за {ruffle.price} {DISPLAY_CURRENCY}. Розыгрыш начнется {ruffle.datetime}\n'
            f' - Слотов занято - {len(user_tickets) + 1} шт.\n'
        )
        user.can_withdraw_money = True
        user.save()
    else:
        await callback.message.edit_text('❌ У Вас недостаточно средств для покупки данной лотереи')
