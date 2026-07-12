import asyncio
import datetime
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters.command import Command
from filters.admin import IsAdmin
from utils.models import RufflesSettings, Settings, BigRuffleSettings, Users, Tickets
from utils.keyboards import (edit_ruffles, ruffle_type_kb, back_button, admin_edit_ruffle_kb, admin_edit_settings_kb,
                             admin_bl_settings_kb, next_kb, admin_bonuses, main_menu, url_buttons_kb)
from utils.states import Admin
from utils.playout import start_big_ruffle
from config import scheduler
from utils.bonus_operations import credit_bonus, credit_bonus_to_user

admin_router = Router()


def _find_user(identifier: str) -> Users | None:
    value = identifier.strip().lstrip('@')
    if not value:
        return None

    if value.isdigit():
        user = Users.get_or_none(Users.user_id == int(value))
        if user:
            return user

    value_lower = value.lower()
    for user in Users.select():
        username = (user.username or '').lstrip('@').lower()
        if username == value_lower:
            return user
    return None


async def _get_active_bot_user(bot, user: Users):
    try:
        bot_user = await bot.get_chat(user.user_id)
    except TelegramRetryAfter as error:
        await asyncio.sleep(error.retry_after)
        try:
            bot_user = await bot.get_chat(user.user_id)
        except Exception as retry_error:
            print(f'[{user.user_id}] Retry failed while refresh user - {retry_error}')
            return None
    except (TelegramBadRequest, TelegramForbiddenError):
        user.inactive = True
        user.save()
        return None
    except Exception as e:
        print(f'[{user.user_id}] Exception while refresh user - {e}')
        return None

    user.username = bot_user.username or ''
    user.inactive = False
    user.save()
    return bot_user


async def _sync_user_from_telegram(bot, user: Users) -> bool | None:
    bot_user = await _get_active_bot_user(bot, user)
    if bot_user is None:
        return None if not user.inactive else False
    return True


def _user_label(user: Users) -> str:
    return f"@{user.username}" if user.username else f"ID {user.user_id}"


async def _refresh_users_database(bot, progress=None) -> tuple[int, int, int]:
    active = 0
    inactive = 0
    updated_usernames = 0
    users = list(Users.select())
    for index, user in enumerate(users, start=1):
        old_username = user.username or ''
        sync_result = await _sync_user_from_telegram(bot, user)
        if sync_result is True:
            active += 1
            if old_username != (user.username or ''):
                updated_usernames += 1
        elif sync_result is False:
            inactive += 1
        elif user.inactive:
            inactive += 1
        else:
            active += 1
        if progress and (index % 25 == 0 or index == len(users)):
            await progress(index, len(users))
        await asyncio.sleep(0.05)
    return active, inactive, updated_usernames


@admin_router.callback_query(IsAdmin(), F.data == 'admin lottery')
async def admin_lottery(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    ruffles = [i for i in RufflesSettings.select()]
    await callback.message.edit_text('🎰 Вы в разделе редактирования розыгрышей',
                                     reply_markup=edit_ruffles(ruffles))


@admin_router.callback_query(IsAdmin(), F.data == 'admin add ruffle')
async def admin_add_ruffle(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.add_ruffle)
    await callback.message.edit_text('➡️ Введите имя нового моментального розыгрыша',
                                     reply_markup=back_button('admin lottery'))


@admin_router.message(IsAdmin(), Admin.add_ruffle)
async def add_ruffle_handle(message: Message, state: FSMContext):
    await state.update_data(new_ruffle_name=message.text.strip())
    await state.set_state(Admin.add_ruffle_type)

    await message.answer(
        f'✅ Название: {message.text.strip()}\n\n'
        f'Теперь выберите тип розыгрыша:',
        reply_markup=ruffle_type_kb()
    )


@admin_router.callback_query(IsAdmin(), Admin.add_ruffle_type, F.data.startswith('admin set_ruffle_type'))
async def admin_set_ruffle_type(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    name = data.get('new_ruffle_name')

    if not name:
        await state.clear()
        return await callback.message.edit_text(
            '⛔ Ошибка: не найдено название розыгрыша. Попробуйте создать заново.',
            reply_markup=back_button('admin lottery')
        )

    ruffle_type = int(callback.data.split()[-1])  # 0 or 1

    RufflesSettings.create(name=name, ruffle_type=ruffle_type)

    type_label = 'Премиум' if ruffle_type == 1 else 'Обычный'
    await state.clear()

    await callback.message.edit_text(
        f'''✅ Вы успешно добавили новый розыгрыш

🎟 Название: {name}
🏷 Тип: {type_label}

⚙️ По умолчанию установлены данные: цена - 100, максимум билетов для одного пользователя - 5, максимум билетов - 20
✏️ Чтобы их изменить, вернитесь к списку розыгрышей, выберите его и совершите необходимые действия''',
        reply_markup=back_button('admin lottery', '🎰 Вернуться к розыгрышам')
    )


@admin_router.callback_query(IsAdmin(), F.data.startswith('admin ruffle'))
async def admin_edit_ruffle(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    ruffle = RufflesSettings.get_by_id(int(callback.data.split()[2]))
    text = f'''🎟️ Название: {ruffle.name}
🔄 Активность: {'🟢 Включен' if ruffle.active else '🔴 Выключен'}
💵 Цена: {ruffle.price} USDt
🔼 Максимум билетов для пользователя: {ruffle.mfo} шт.
🔼 Максимум билетов для розыгрыша: {ruffle.mfa} шт.
⚖️ Коэффициент выиграша: x{ruffle.ratio}'''
    await callback.message.edit_text(text, reply_markup=admin_edit_ruffle_kb(ruffle.id))


@admin_router.callback_query(IsAdmin(), F.data.startswith('edit_ruffle'))
async def edit_ruffle_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.edit_ruffle)
    data = callback.data.split()
    await state.update_data(value=data[1], ruffle_id=data[2])
    await callback.message.edit_text('👉 Введите новое значение для выбранного розыгрыша',
                                     reply_markup=back_button('admin lottery'))


@admin_router.callback_query(IsAdmin(), F.data.startswith('delete_ruffle'))
async def delete_ruffle(callback: CallbackQuery):
    ruffle = RufflesSettings.get_by_id(int(callback.data.split()[1]))
    tickets = Tickets.select().where(Tickets.ruffle_id == ruffle.id)
    for i in tickets:
        user: Users = Users.get_or_none(Users.user_id == i.user_id)
        user.balance += ruffle.price
        user.save()
        i.delete_instance()
    await callback.message.edit_text(f'✅ Вы успешно удалили розыгрыш {ruffle.name}',
                                     reply_markup=back_button('admin lottery'))
    ruffle.delete_instance()


@admin_router.callback_query(IsAdmin(), F.data.startswith('activate_ruffle'))
async def activate_ruffle(callback: CallbackQuery, state: FSMContext):
    ruffle = RufflesSettings.get_by_id(int(callback.data.split()[1]))
    await callback.answer(f'✅ {ruffle.name} {"де" if ruffle.active else ""}активирован')
    ruffle.active = False if ruffle.active else True
    ruffle.save()
    new_callback = CallbackQuery(id=callback.id,
                                 from_user=callback.from_user,
                                 chat_instance=callback.chat_instance,
                                 message=callback.message,
                                 data=f'admin ruffle {ruffle.id}')
    await admin_edit_ruffle(new_callback, state)


@admin_router.message(IsAdmin(), Admin.edit_ruffle)
async def enter_new_value_for_ruffle(message: Message, state: FSMContext):
    data = await state.get_data()
    new_value, ruffle_id = data['value'], int(data['ruffle_id'])
    if new_value != 'name' and not message.text.isdigit():
        return await message.answer('❌ Данное значение должно быть только из цифр\n🔁 Попробуйте еще раз',
                                    reply_markup=back_button('admin lottery'))
    ruffle = RufflesSettings.get_by_id(ruffle_id)
    if new_value == 'name':
        ruffle.name = message.text
    elif new_value == 'price':
        ruffle.price = int(message.text)
    elif new_value == 'mfo':
        ruffle.mfo = int(message.text)
    elif new_value == 'mfa':
        ruffle.mfa = int(message.text)
    elif new_value == 'ratio':
        ruffle.ratio = int(message.text)
    else:
        await message.answer('error, check module admin')
    await message.answer('✅ Вы успешно изменили значение для выбранного розыгрыша',
                         reply_markup=back_button('admin lottery'))
    ruffle.save()
    await state.clear()


@admin_router.callback_query(IsAdmin(), F.data == 'admin settings')
async def admin_settings(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    settings = Settings.get()
    await callback.message.edit_text(f'''⚙️ Настройки

📩 Сумма за приглашенного друга: {settings.cost_invite} 💎
📥 Минимальная сумма для пополнения: {settings.min_topup_balance} USDt
📤 Минимальная сумма для вывода: {settings.min_withdraw_balance} USDt
🚀 Бонус за подписку на канал: {settings.prize_follow} 💎
💎 Бонус pnmVPN trial: {settings.pnmvpn_trial_reward} 💎

🎲 Кости: попыток в день (K): {settings.dice_daily_attempts}
🎲 Кости: награда за дубль (N): {settings.dice_double_reward} 💎

🎰 777: попыток в день (K): {settings.casino_daily_attempts}
🎰 777: награда (N): {settings.casino_reward} 💎

🎳 Боулинг: попыток в день (K): {settings.bowling_daily_attempts}
🎳 Боулинг: награда (N): {settings.bowling_reward} 💎

🎯 Дартс: попыток в день (K): {settings.darts_daily_attempts}
🎯 Дартс: награда (N): {settings.darts_reward} 💎
''', reply_markup=admin_edit_settings_kb())


@admin_router.callback_query(IsAdmin(), F.data.startswith('admin_edit'))
async def admin_edit_settings(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.edit_settings)
    await state.update_data(settings_field=callback.data.split()[1])
    await callback.message.edit_text('👉 Введите новое значение для выбранной настройки',
                                     reply_markup=back_button('admin settings'))


@admin_router.message(IsAdmin(), Admin.edit_settings)
async def admin_editing_settigns_handler(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer('❌ Данное значение должно быть только из цифр\n🔁 Попробуйте еще раз',
                                    reply_markup=back_button('admin settings'))
    data = await state.get_data()
    field = data['settings_field']
    settings = Settings.get()
    if field == 'referal':
        settings.cost_invite = int(message.text)
    elif field == 'topup':
        settings.min_topup_balance = int(message.text)
    elif field == 'withdraw':
        settings.min_withdraw_balance = int(message.text)
    elif field == 'follow':
        settings.prize_follow = int(message.text)
    elif field == 'pnmvpn_trial':
        settings.pnmvpn_trial_reward = int(message.text)
    elif field == 'dice_k':
        settings.dice_daily_attempts = int(message.text)
    elif field == 'dice_n':
        settings.dice_double_reward = int(message.text)
    elif field == 'casino_k':
        settings.casino_daily_attempts = int(message.text)
    elif field == 'casino_n':
        settings.casino_reward = int(message.text)
    elif field == 'bowling_k':
        settings.bowling_daily_attempts = int(message.text)
    elif field == 'bowling_n':
        settings.bowling_reward = int(message.text)
    elif field == 'darts_k':
        settings.darts_daily_attempts = int(message.text)
    elif field == 'darts_n':
        settings.darts_reward = int(message.text)

    else:
        return await message.answer("❌ Неизвестное поле настройки", reply_markup=back_button('admin settings'))

    settings.save()
    await message.answer('✅ Вы успешно изменили значение для выбранной настройки',
                         reply_markup=back_button('admin settings'))
    await state.clear()


@admin_router.callback_query(IsAdmin(), F.data == 'admin big_lottery')
async def admin_edit_big_ruffle(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    bl_settings = BigRuffleSettings.get()
    await callback.message.edit_text(f'''✍ Редактирование большого розыгрыша

🔄 Активность: {'🟢 Включен' if bl_settings.activity else '🔴 Выключен'}
💵 Цена: {bl_settings.price}
📅 Дата и время: {bl_settings.datetime if bl_settings.datetime else 'Не указана'}''',
                                     reply_markup=admin_bl_settings_kb())


@admin_router.callback_query(IsAdmin(), F.data.startswith('admin_bl'))
async def admin_bl_editing(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split()[1]
    bl_settings = BigRuffleSettings.get()
    if field == 'activity':
        bl_settings.activity = 1 if not bl_settings.activity else 0
        bl_settings.save()
        text = "включили" if bl_settings.activity else "выключили"
        await callback.message.edit_text(f'✅ Вы успешно {text} «Мешок денег»',
                                         reply_markup=back_button('admin big_lottery'))
        if bl_settings.activity:
            try:
                scheduler.remove_job('start_big_ruffle')
            except:
                pass
            scheduler.add_job(start_big_ruffle,
                              trigger='date',
                              next_run_time=bl_settings.datetime,
                              id='start_big_ruffle',
                              kwargs={'bot': callback.bot})
            for user in Users.select():
                try:
                    await callback.bot.send_message(user.user_id,
                                                    '🥳 Внимание! Лотерея «Мешок денег» снова доступна, играй и выигрывай большой куш!',
                                                    reply_markup=main_menu(user.user_id))
                except:
                    pass
        else:
            try:
                scheduler.remove_job('start_big_ruffle')
            except:
                pass
        return
    await state.set_state(Admin.edit_big_ruffle)
    await state.update_data(change_field=field)
    text = ''
    if field == 'datetime':
        text = ' в формате 31.12.2000 15:30 (число.месяц.год час:минуты)'
    elif field in ['price', 'profit', 'fake_amount']:
        text = ' только из цифр'
    await callback.message.edit_text('👉 Введите новое значение для выбранной настройки' + text,
                                     reply_markup=back_button('admin big_lottery'))


@admin_router.message(IsAdmin(), Admin.edit_big_ruffle)
async def admin_bl_editing_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data['change_field']
    bl_settings: BigRuffleSettings = BigRuffleSettings.get()
    if field in ['price', 'profit', 'fake_amount']:
        if message.text.isdigit():
            if field == 'price':
                bl_settings.price = int(message.text)
            elif field == 'profit':
                bl_settings.profit = int(message.text)
            elif field == 'fake_amount':
                bl_settings.fake_amount = int(message.text)
        else:
            return await message.answer('❌ Ошибка! Введите цифры для того, чтобы назначить цену большому розыгрышу',
                                        reply_markup=back_button('admin big_lottery'))
    if field == 'datetime':
        try:
            date = datetime.datetime.strptime(message.text, "%d.%m.%Y %H:%M")
            if date < datetime.datetime.now():
                return await message.answer('❌ Ошибка! Дата должна быть будущей, не прошедешей',
                                            reply_markup=back_button('admin big_lottery'))
            bl_settings.datetime = date
            if bl_settings.activity:
                try:
                    scheduler.remove_job('start_big_ruffle')
                except:
                    pass
                scheduler.add_job(start_big_ruffle,
                                  trigger='date',
                                  next_run_time=bl_settings.datetime,
                                  id='start_big_ruffle',
                                  kwargs={'bot': message.bot})
        except ValueError as e:
            return await message.answer(
                '❌ Ошибка! Используйте формат 31.12.2000 15:30 (число.месяц.год час:минуты)',
                reply_markup=back_button('admin big_lottery'))
    await message.answer('✅ Вы успешно поменяли значение выбранной настройки',
                         reply_markup=back_button('admin big_lottery'))
    await state.clear()
    bl_settings.save()


@admin_router.callback_query(IsAdmin(), F.data == 'admin bonus')
async def admin_bonus(callback: CallbackQuery):
    await callback.message.edit_text('🎁 Вы перешли в административный раздел выдачи бонусов\n'
                                     '👥 Выберите действие',
                                     reply_markup=admin_bonuses())


@admin_router.callback_query(IsAdmin(), F.data.startswith('admin give_bonus'))
async def admin_give_bonus(callback: CallbackQuery, state: FSMContext):
    await state.update_data(bonus_to=callback.data.split()[2])
    await state.set_state(Admin.bonus_amount)
    await callback.message.edit_text('💵 Отлично! Теперь введите сумму, которую Вы хотите начислить на бонусный счет',
                                     reply_markup=back_button('admin_panel'))


@admin_router.message(IsAdmin(), Admin.bonus_amount)
async def admin_take_amount(message: Message, state: FSMContext):
    if message.text.isdigit():
        await state.update_data(bonus_amount=message.text)
        data = await state.get_data()
        if data['bonus_to'] == 'all':
            await message.answer(
                f'📝 Вы уверены что хотите выдать всем пользователям бонус в размере {message.text} 💎?',
                reply_markup=next_kb('admin bonus_confirm'))
        elif data['bonus_to'] == 'one':
            await state.set_state(Admin.bonus_username)
            await message.answer('👤 Введите username пользователя без @', reply_markup=back_button('admin_panel'))
    else:
        await message.answer('❌ Сумма должна состоять только из цифр!')


@admin_router.message(IsAdmin(), Admin.bonus_username)
async def admin_take_username(message: Message, state: FSMContext):
    forwarded_user = getattr(message, 'forward_from', None)
    identifier = str(forwarded_user.id) if forwarded_user else (message.text or '')
    user = _find_user(identifier)
    if user:
        bot_user = await _get_active_bot_user(message.bot, user)
        await state.update_data(bonus_userid=user.id)
        data = await state.get_data()
        first_name = bot_user.first_name if bot_user else 'Недоступен в Telegram'
        await message.answer(f'''✅ Пользователь {_user_label(user)} найден!

👤 Имя: {first_name} [{_user_label(user)}]
🆔 TG ID: {user.user_id}
💰 Баланс: {user.balance} USDt
🎁 Бонусный счет: {user.prize_balance} 💎

📝 Вы уверены что хотите выдать данному пользователю бонус в размере {data["bonus_amount"]} 💎?''',
                             reply_markup=next_kb('admin bonus_confirm'))
    else:
        await message.answer('❌ Такого пользователя найти не получилось\n'
                             '🔄 Введите актуальный Telegram ID, сохранённый username или перешлите сообщение пользователя.',
                             reply_markup=back_button('admin_panel'))


@admin_router.callback_query(IsAdmin(), F.data == 'admin bonus_confirm')
async def admin_bonus_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text('⏳ Процесс запущен . . .')
    data = await state.get_data()
    if data['bonus_to'] == 'all':
        users = list(Users.select())
        amount = int(data['bonus_amount'])
        credited = credit_bonus([user.id for user in users], amount)
        notified = 0
        unavailable = 0
        errors = 0
        for i in users:
            try:
                await callback.bot.send_message(i.user_id, f'🎁 Подгон от Админа - {data["bonus_amount"]} 💎. '
                                                           f'Проверь баланс 🙃')
                i.inactive = False
                i.save()
                notified += 1
            except (TelegramBadRequest, TelegramForbiddenError):
                i.inactive = True
                i.save()
                unavailable += 1
            except Exception as e:
                print(f'[{i.user_id}] Exception while give bonus - {e}')
                errors += 1
        await callback.message.edit_text(f'✅ Бонус {amount} 💎 начислен: {credited}\n'
                                         f'📨 Уведомлены: {notified}\n'
                                         f'🚫 Недоступны: {unavailable}\n'
                                         f'⚠️ Ошибки уведомления: {errors}',
                                         reply_markup=back_button('admin_panel'))
    elif data['bonus_to'] == 'one':
        user = Users.get_by_id(int(data['bonus_userid']))
        amount = int(data['bonus_amount'])
        credit_bonus_to_user(user, amount)
        notification_sent = True
        try:
            await callback.bot.send_message(user.user_id, f'🎁 Подгон от Админа - {data["bonus_amount"]} 💎. '
                                                          f'Проверь баланс 🙃')
        except (TelegramBadRequest, TelegramForbiddenError):
            user.inactive = True
            user.save()
            notification_sent = False
        else:
            user.inactive = False
            user.save()
        await callback.message.edit_text(
            f'✅ Пользователю {_user_label(user)} начислено {amount} 💎\n'
            f'📨 Уведомление: {"доставлено" if notification_sent else "не доставлено"}',
            reply_markup=back_button('admin_panel'),
        )
    await state.clear()


@admin_router.callback_query(IsAdmin(), F.data == 'admin remove_bonus')
async def admin_remove_bonus(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.remove_bonus_username)
    await callback.message.edit_text('👤 Введите username пользователя без @, у которого хотите снять бонусы',
                                   reply_markup=back_button('admin_panel'))

@admin_router.message(IsAdmin(), Admin.remove_bonus_username)
async def admin_remove_bonus_username(message: Message, state: FSMContext):
    user = _find_user(message.text)
    if user:
        bot_user = await _get_active_bot_user(message.bot, user)
        if not bot_user:
            await message.answer(f'⚠️ Пользователь @{message.text} удалил бота')
        else:
            await state.update_data(remove_bonus_userid=user.id)
            await state.set_state(Admin.remove_bonus_amount)
            await message.answer(f'''✅ Пользователь {_user_label(user)} найден!

👤 Имя: {bot_user.first_name} [{_user_label(user)}]
🆔 TG ID: {user.user_id}
💰 Баланс: {user.balance} USDt
🎁 Бонусный счет: {user.prize_balance} 💎

💵 Введите сумму бонусов, которую хотите снять:''',
                               reply_markup=back_button('admin_panel'))
    else:
        await message.answer('❌ Такого пользователя найти не получилось\n'
                           '🔄 Попробуйте еще раз или возвращайтесь в админ-панель',
                           reply_markup=back_button('admin_panel'))

@admin_router.message(IsAdmin(), Admin.remove_bonus_amount)
async def admin_remove_bonus_amount(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer('❌ Сумма должна состоять только из цифр!')
    
    data = await state.get_data()
    amount = int(message.text)
    user = Users.get_by_id(data['remove_bonus_userid'])
    
    if amount > user.prize_balance:
        amount = user.prize_balance
    
    user.prize_balance -= amount
    user.save()
    
    try:
        await message.bot.send_message(user.user_id, 
                                     f'🔴 Администратор снял с вашего бонусного счета {amount} 💎')
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
    
    await message.answer(f'✅ У пользователя {_user_label(user)} успешно снято {amount} 💎 бонусов\n'
                        f'Текущий бонусный баланс: {user.prize_balance} 💎',
                        reply_markup=back_button('admin_panel'))
    await state.clear()


@admin_router.callback_query(IsAdmin(), F.data == 'admin talk')
async def admin_talk_handle(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.talk_input)
    await callback.message.edit_text('📣 Вы перешли в раздел рупора\n'
                                   'Напишите текст, который хотите отправить пользователям\n'
                                   '(если текст не нужен, отправьте "-")',
                                   reply_markup=back_button('admin_panel'))


@admin_router.message(IsAdmin(), Admin.talk_input)
async def admin_input_handle(message: Message, state: FSMContext):
    await state.update_data(text=message.text if message.text != "-" else None)
    await state.set_state(Admin.talk_media)
    await message.answer('📎 Теперь отправьте фото или видео для рассылки\n'
                        '(можно отправить несколько файлов, когда закончите - нажмите кнопку "Продолжить")',
                        reply_markup=next_kb('takl_buttons_next'))
    await state.update_data(media=[], buttons=[])


@admin_router.message(IsAdmin(), Admin.talk_media, F.photo | F.video)
async def admin_media_handle(message: Message, state: FSMContext):
    data = await state.get_data()
    media = data.get('media', [])
    
    file_id = None
    if message.photo:
        file_id = {'type': 'photo', 'file_id': message.photo[-1].file_id}
    elif message.video:
        file_id = {'type': 'video', 'file_id': message.video.file_id}
        
    if file_id:
        media.append(file_id)
        await state.update_data(media=media)
        await message.answer(f'✅ Медиафайл добавлен! Всего файлов: {len(media)}\n'
                           'Отправьте еще файлы или нажмите "Начать рассылку"',
                           reply_markup=next_kb('talk_buttons_next'))


@admin_router.callback_query(IsAdmin(), F.data == 'talk_buttons_next')
async def talk_buttons_next(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Admin.talk_buttons)
    await callback.message.edit_text(
        "🔗 Теперь добавьте инлайн кнопки со ссылками.\n\n"
        "Формат: Текст | https://example.com\n"
        "Каждая кнопка с новой строки.\n\n"
        "Если кнопки не нужны — отправьте: -",
        reply_markup=back_button('admin_panel')
    )


def _parse_buttons(text: str) -> list[dict]:
    text = (text or "").strip()
    if text == "-" or not text:
        return []
    buttons = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" not in line:
            continue
        title, url = [p.strip() for p in line.split("|", 1)]
        if not title or not url:
            continue
        if not (url.startswith("http://") or url.startswith("https://")):
            continue
        buttons.append({"text": title[:64], "url": url})
    return buttons


@admin_router.message(IsAdmin(), Admin.talk_buttons)
async def admin_talk_buttons_handle(message: Message, state: FSMContext):
    buttons = _parse_buttons(message.text)
    await state.update_data(buttons=buttons)

    await message.answer(
        f"✅ Кнопки сохранены: {len(buttons)}\n"
        "Нажмите «Начать рассылку»",
        reply_markup=next_kb('start_mailing')
    )


@admin_router.callback_query(IsAdmin(), F.data == 'start_mailing')
async def start_mailing(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get('text')
    media = data.get('media', [])
    buttons = data.get('buttons', [])

    kb = url_buttons_kb(buttons)

    if not text and not media:
        await callback.message.edit_text(
            '❌ Необходимо указать текст или добавить медиафайлы!',
            reply_markup=back_button('admin_panel')
        )
        return

    new_msg = await callback.message.edit_text('⏳ Процесс запущен . . .')
    users = Users.select()

    for user in users:
        try:
            if len(media) == 0:
                await callback.bot.send_message(
                    user.user_id,
                    text or "",
                    reply_markup=kb
                )

            elif len(media) == 1:
                m = media[0]
                if m['type'] == 'photo':
                    await callback.bot.send_photo(
                        user.user_id,
                        m['file_id'],
                        caption=text,
                        reply_markup=kb
                    )
                else:
                    await callback.bot.send_video(
                        user.user_id,
                        m['file_id'],
                        caption=text,
                        reply_markup=kb
                    )

            else:
                media_group = []
                for i, m in enumerate(media):
                    item = {'type': m['type'], 'media': m['file_id']}
                    if i == 0 and text:
                        item['caption'] = text
                    media_group.append(item)

                await callback.bot.send_media_group(user.user_id, media=media_group)

                if kb:
                    await callback.bot.send_message(
                        user.user_id,
                        "🔗 Ссылки:",
                        reply_markup=kb
                    )

        except Exception as e:
            print(f'[{user.user_id}] Exception while send messages - {e}')

    await new_msg.edit_text('✅ Рассылка успешно выполнена!',
                            reply_markup=back_button('admin_panel'))
    await state.clear()


@admin_router.message(IsAdmin(), Command('admin_refresh'))
async def admin_refresh(message: Message):
    msg = await message.answer('Процесс . . .')
    async def progress(done, total):
        await msg.edit_text(f'⏳ Обновлено {done}/{total}')
    active, inactive, renamed = await _refresh_users_database(message.bot, progress)
    await msg.edit_text(f'✅ База обновлена!\nАктивных: {active}\nНедоступных: {inactive}\nUsername обновлено: {renamed}')


@admin_router.callback_query(IsAdmin(), F.data == 'admin_refresh')
async def admin_refresh_callback(callback: CallbackQuery):
    msg = await callback.message.edit_text('Процесс . . .')
    async def progress(done, total):
        await msg.edit_text(f'⏳ Обновлено {done}/{total}')
    active, inactive, renamed = await _refresh_users_database(callback.bot, progress)
    await msg.edit_text(
        f'✅ База обновлена!\nАктивных: {active}\nНедоступных: {inactive}\nUsername обновлено: {renamed}',
        reply_markup=back_button('admin_panel')
    )


@admin_router.callback_query(IsAdmin(), F.data == 'admin exit')
async def admin_exit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.answer('✅ Вы успешно вышли из админ-панели')
