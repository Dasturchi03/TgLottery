import datetime
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from utils.states import Wallet
from utils.keyboards import write_kb, crypto_pay_kb, accept_decline
from utils.models import Settings
from config import CHANNEL_ID, DISPLAY_CURRENCY, crypto, MAIN_CHANNEL_ID
from utils.models import Users, Payments, Withdraws
from cryptobot import Invoice, ButtonName, Asset
from filters.admin import IsAdmin

wallet_router = Router()


@wallet_router.callback_query(F.data == 'wallet topup')
async def wallet_topup(callback: CallbackQuery, state: FSMContext):
    # await state.clear()
    # await callback.message.edit_text(f'🤔 Выберите Ваш способ пополнения', reply_markup=choice_type_pay_kb())
    # await state.update_data(pay_type=36)
    settings = Settings.get()
    await callback.message.edit_caption(caption=f'✍ Введите количество {DISPLAY_CURRENCY}, которое хотите купить\n\n'
                                     f'💸 Минимальная покупка: {settings.min_topup_balance} {DISPLAY_CURRENCY}')
    await state.set_state(Wallet.topup)


# @wallet_router.callback_query(F.data.startswith('choice_type_pay'))
# async def wallet_topup(callback: CallbackQuery, state: FSMContext):
#     await state.update_data(pay_type=44 if callback.data.split()[1] == 'sbp' else 36)
#     settings = Settings.get()
#     await callback.message.edit_text(f'✍ Введите сумму на которую Вы хотите пополнить баланс\n\n'
#                                      f'💸 Минимальная сумма для пополнения: {settings.min_topup_balance} 💎')
#     await state.set_state(Wallet.topup)


@wallet_router.message(Wallet.topup)
async def wallet_topup_handler(message: Message, state: FSMContext):
    settings = Settings.get()
    if message.text.isdigit() and int(message.text) >= settings.min_topup_balance:
        amount = int(message.text)
        data = await state.get_data()
        # payment, freekassa_payment = await FKClient.create_payment(user_id=message.from_user.id,
        #                                                            amount=amount,
        #                                                            payment_type=data.get('pay_type', 36))

        payment: Payments = Payments.create(user_id=message.from_user.id,
                                            amount=amount,
                                            date_creation=datetime.date.today(),
                                            datetime_creation=datetime.datetime.now(),
                                            payment_type=data.get('pay_type', 36))
        invoice: Invoice = await crypto.create_payment(amount=amount,
                                                       asset=Asset.USDT,
                                                       accepted_assets='USDT',
                                                       description='Чтобы получить свой товар, перейдите в бота по кнопке ниже',
                                                       paid_btn_name=ButtonName.viewItem,
                                                       paid_btn_url='https://t.me/Pure_Random_Bot',
                                                       payload=f'order_{payment.id}')

        msg = await message.answer(f'''ℹ️ Произведите оплату в криптовалюте через кошелёк @CryptoBot

<b>🆔 Номер заказа: #{payment.id}</b>
{DISPLAY_CURRENCY} Сумма: <i>{payment.amount} {DISPLAY_CURRENCY}</i>''',
                                   parse_mode="HTML",
                                   reply_markup=crypto_pay_kb(invoice.bot_invoice_url,
                                                              invoice.mini_app_invoice_url))
        payment.message_id = msg.message_id
        payment.save()
        await state.clear()
    else:
        await message.answer(f'❌ Ошибка, используйте только цифры для того, чтобы ввести необходимую сумму. '
                             f'Так же сумма должна быть больше или равной минимальной покупке - '
                             f'{settings.min_topup_balance} {DISPLAY_CURRENCY}\n'
                             f'Например: 500')


@wallet_router.callback_query(F.data == 'wallet withdraw')
async def wallet_withdraw(callback: CallbackQuery, state: FSMContext):
    user: Users = Users.get_or_none(Users.user_id == callback.from_user.id)
    if not user.can_withdraw_money:
        return await callback.answer(
            f'❌ Вы не можете обменять средства!\nДля обмена необходимо занять хотя бы 1 слот после пополнения баланса',
            show_alert=True)
    settings = Settings.get()
    await callback.message.edit_caption(caption=f'‼️ Внимание ‼️ Для вывода должен быть создан крипто-кошелек, иначе средства пропадут безвозвратно.\n'
                                     f'📝 Укажите все необходимые детали для вывода средств на ваш крипто-кошелёк.\n'
                                     f'💸 Минимальный обмен: {settings.min_withdraw_balance} {DISPLAY_CURRENCY}\n'
                                     f'💵 Введите количество {DISPLAY_CURRENCY} на обмен:\n\n'
                                     f'💳 <i>*Минимальная сумма для вывода: {settings.min_withdraw_balance} {DISPLAY_CURRENCY}</i>',
                                     parse_mode="HTML")
    await state.set_state(Wallet.withdraw_summ)


@wallet_router.message(Wallet.withdraw_summ)
async def withdraw_summ(message: Message, state: FSMContext):
    settings = Settings.get()
    if message.text.isdigit() and int(message.text) >= settings.min_withdraw_balance:
        user = Users.get_or_none(Users.user_id == message.from_user.id)
        if user.balance < int(message.text):
            return await message.answer('❌ Ошибка! Недостаточно средств на балансе, введите другую сумму')
        try:
            text = f'''🆕 {message.from_user.first_name} [{f"@{message.from_user.username}" if message.from_user.username else "отсутствует"}] запрашивает вывод средств\n
💰 Баланс пользователя: {user.balance} {DISPLAY_CURRENCY}
💰 Новый баланс: {user.balance - int(message.text)} {DISPLAY_CURRENCY}
🔄 Сумма обмена: {message.text} {DISPLAY_CURRENCY}'''
            user.balance -= int(message.text)
            user.save()
            await message.bot.send_message(CHANNEL_ID, text, parse_mode="HTML",
                                           reply_markup=accept_decline(message.from_user.id, int(message.text)))
            await message.answer(
                '✅ Вы успешно подали заявку на обмен средств (на баланс вашего кошелька в @CryptoBot)\n'
                'Пожалуйста, ожидайте рассмотрения заявки в течении нескольких часов')
        except Exception as e:
            await message.bot.send_message(CHANNEL_ID,
                                           f'🆕 У пользователя {message.from_user.first_name} [{f"@{message.from_user.username}" if message.from_user.username else "отсутствует"}] возникла ошибка при выводе средств: {e}',
                                           parse_mode="HTML", reply_markup=write_kb(message.from_user.id))
            await message.answer(
                '❌ Возникла ошибка при обмене! Администрация уже в курсе проблемы, ожидайте пока с вами свяжутся в течении дня')
        await state.clear()
    else:
        await message.answer(f'❌ Ошибка! Введите сумму для вывода, только из цифр, она должна быть больше '
                             f'или равна минимальной сумме для вывода - {settings.min_withdraw_balance} {DISPLAY_CURRENCY}')


@wallet_router.callback_query(IsAdmin(), F.data.startswith('withdraw_'))
async def withdraw_accept_handle(callback: CallbackQuery):
    do, user_id, summ = callback.data.split()
    user: Users = Users.get_or_none(Users.user_id == user_id)
    if do == 'withdraw_accept':
        await callback.message.edit_text(callback.message.text +
                                         f'\n\n✅ Вы успешно одобрили обмен средств пользователю на сумму {summ} {DISPLAY_CURRENCY}',
                                         reply_markup=write_kb(user_id))
        try:
            withdraw: Withdraws = Withdraws.create(user_id=user.user_id,
                                                   amount=int(summ),
                                                   created_datetime=datetime.datetime.now())
            await crypto.transfer(user_id=user.user_id,
                                  asset=Asset.USDT,
                                  amount=int(summ),
                                  spend_id=withdraw.id)
            await callback.bot.send_message(user_id, f'✅ Вам одобрили вывод средств на сумму {summ} {DISPLAY_CURRENCY}')
        except Exception as e:
            print(e)

        await callback.bot.send_message(MAIN_CHANNEL_ID,
                                        f'🎉 Выигрыш в размере {summ} {DISPLAY_CURRENCY} отправлен {f"@{user.username}" if user.username != "None" else "отсутствует"}\n🥳 Поздравляем!')
    elif do == 'withdraw_decline':
        await callback.message.edit_text(callback.message.text +
                                         f'\n\n❌ Вы отказали в обмене средств пользователю на сумму {summ} {DISPLAY_CURRENCY}',
                                         reply_markup=write_kb(user_id))
        try:
            await callback.bot.send_message(user_id, f'❌ Вам отказали в выводе средств на сумму {summ} {DISPLAY_CURRENCY}')
        except Exception as e:
            print(e)


@wallet_router.callback_query(F.data == 'faq_topup')
async def send_video_faq(callback: CallbackQuery):
    await callback.message.answer_video('BAACAgIAAxkBAAJJm2d-KxqF_OEBoNGjgxIh9flJNndxAAI-aAACI3rpS27vL--ZLKDUNgQ')
