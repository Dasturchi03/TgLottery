from aiogram.utils.keyboard import (InlineKeyboardBuilder, InlineKeyboardButton,
                                    ReplyKeyboardBuilder, KeyboardButton)
from config import ADMINS
from utils.models import BigRuffleSettings, Settings


def main_menu(user_id):
    bl_settings: BigRuffleSettings = BigRuffleSettings.get()
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text='🙎🏻‍♂️ Профиль'), KeyboardButton(text='🎁 Бонусы'))
    builder.row(KeyboardButton(text='🎟️ Моментальный розыгрыш'),
                KeyboardButton(text='🎫 Мои розыгрыши'))
    if bl_settings.activity:
        builder.row(KeyboardButton(text='🎫 Мешок денег'))
    if user_id in ADMINS:
        builder.row(KeyboardButton(text='👑 Админ-панель'))
    return builder.as_markup(resize_keyboard=True)


def profile_menu():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text='📥 Пополнить', callback_data='wallet topup'),
                InlineKeyboardButton(text='📤 Вывести', callback_data='wallet withdraw'))
    builder.row(InlineKeyboardButton(text='❓ Как пополнить баланс?', callback_data='faq_topup'))
    return builder.as_markup()


def bonus_menu():
    settings = Settings.get()
    builder = InlineKeyboardBuilder()
    builder.button(text='👉 Подписаться на канал', callback_data='follow_channel')
    builder.row(InlineKeyboardButton(text=f'👥 {settings.cost_invite} 💎 за друга', callback_data='invite_friend'),
                InlineKeyboardButton(text='🎳 Боулинг ', callback_data='bowling_game'))
    builder.row(InlineKeyboardButton(text=f'💎 {settings.pnmvpn_trial_reward} за ₽1', callback_data='pnmvpn_trial'),
                InlineKeyboardButton(text='🎯 Дартс ', callback_data='darts_game'))
    builder.row(InlineKeyboardButton(text='🎲 Игра в кости', callback_data='dice_game'),
                InlineKeyboardButton(text='🎰 777 ', callback_data='casino_game'))

    return builder.as_markup()


def pnmvpn_trial_kb(pnmvpn_bot_username: str):
    builder = InlineKeyboardBuilder()

    url = f"https://t.me/{pnmvpn_bot_username}?start=trial_bonus"
    builder.button(text='🚀 Перейти в pnmVPN', url=url)

    builder.button(text='⬅️ Назад', callback_data='bonuses_back')

    builder.adjust(1)
    return builder.as_markup()


def dice_kb(emoji: str, call_data: str):
    builder = InlineKeyboardBuilder()
    builder.button(text=emoji, callback_data=call_data)
    builder.button(text='⬅️ Назад', callback_data='bonuses_back')
    builder.adjust(1)
    return builder.as_markup()


def momentum_ruffle(ruffles):
    builder = InlineKeyboardBuilder()
    for i in ruffles:
        builder.button(text=f'{i.name} [{i.price} USDt]', callback_data=f'ruffle {i.id}')
    return builder.adjust(1).as_markup()


def big_ruffle():
    builder = InlineKeyboardBuilder()
    builder.button(text='🛒 Купить', callback_data='big_ruffle show')
    builder.button(text='👀 Заглянуть в мешок', callback_data='big_ruffle amount')
    return builder.as_markup()


def admin_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='🎟️ Моментальный розыгрыш', callback_data='admin lottery')
    builder.button(text='🎫 Мешок денег', callback_data='admin big_lottery')
    builder.button(text='⚙️ Другие настройки', callback_data='admin settings')
    builder.button(text='🎁 Бонусы', callback_data='admin bonus')
    builder.button(text='📣 Рупор', callback_data='admin talk')
    builder.button(text='🔄 Обновить базу', callback_data='admin_refresh')
    builder.button(text='🏃 Выход', callback_data='admin exit')
    return builder.adjust(2).as_markup()


def edit_ruffles(ruffles):
    builder = InlineKeyboardBuilder()
    for i in ruffles:
        builder.button(text=f'{i.name} [{i.price} USDt]', callback_data=f'admin ruffle {i.id}')
    builder.button(text='➕ Добавить', callback_data='admin add ruffle')
    builder.button(text='↩️ Назад', callback_data='admin_panel')
    return builder.adjust(2).as_markup()


def ruffle_type_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='⭐ Премиум', callback_data='admin set_ruffle_type 1')
    builder.button(text='✅ Обычный', callback_data='admin set_ruffle_type 0')
    builder.button(text='⬅️ Назад', callback_data='admin lottery')
    builder.adjust(1)
    return builder.as_markup()


def admin_edit_ruffle_kb(ruffle_id):
    builder = InlineKeyboardBuilder()
    builder.button(text='📝 Название', callback_data=f'edit_ruffle name {ruffle_id}')
    builder.button(text='💵 Цена', callback_data=f'edit_ruffle price {ruffle_id}')
    builder.button(text='🔼 Макс. для 1', callback_data=f'edit_ruffle mfo {ruffle_id}')
    builder.button(text='🔼 Макс. для всех', callback_data=f'edit_ruffle mfa {ruffle_id}')
    builder.button(text='⚖️ Коэффициент', callback_data=f'edit_ruffle ratio {ruffle_id}')
    builder.button(text='🗑️ Удалить', callback_data=f'delete_ruffle {ruffle_id}')
    builder.button(text='🔄 Активность', callback_data=f'activate_ruffle {ruffle_id}')
    builder.button(text='↩️ Назад', callback_data=f'admin lottery')
    return builder.adjust(2).as_markup()


def admin_edit_settings_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text='📥 Мин. сумма пополнения', callback_data='admin_edit topup'))
    builder.row(InlineKeyboardButton(text='📤 Мин. сумма вывода', callback_data='admin_edit withdraw'))
    builder.row(
        InlineKeyboardButton(text='📩 Реферал', callback_data='admin_edit referal'),
        InlineKeyboardButton(text='🚀 Подписка', callback_data='admin_edit follow')
    )
    builder.row(InlineKeyboardButton(text='💎 pnmVPN trial', callback_data='admin_edit pnmvpn_trial'))
    builder.row(
        InlineKeyboardButton(text='🎲 K (кости)', callback_data='admin_edit dice_k'),
        InlineKeyboardButton(text='🎲 N (награда)', callback_data='admin_edit dice_n')
    )

    builder.row(
        InlineKeyboardButton(text='🎰 K (777)', callback_data='admin_edit casino_k'),
        InlineKeyboardButton(text='🎰 N (777)', callback_data='admin_edit casino_n')
    )
    builder.row(
        InlineKeyboardButton(text='🎳 K (боулинг)', callback_data='admin_edit bowling_k'),
        InlineKeyboardButton(text='🎳 N (боулинг)', callback_data='admin_edit bowling_n')
    )
    builder.row(
        InlineKeyboardButton(text='🎯 K (дартс)', callback_data='admin_edit darts_k'),
        InlineKeyboardButton(text='🎯 N (дартс)', callback_data='admin_edit darts_n')
    )

    builder.row(InlineKeyboardButton(text='↩️ Назад', callback_data='admin_panel'))
    return builder.as_markup()


def url_buttons_kb(buttons: list[dict]):
    """
    buttons: [{"text": "...", "url": "..."}]
    """
    if not buttons:
        return None
    b = InlineKeyboardBuilder()
    for btn in buttons:
        b.row(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
    return b.as_markup()


def admin_bl_settings_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='🔄 Активность', callback_data='admin_bl activity')
    builder.button(text='💵 Цена', callback_data='admin_bl price')
    builder.button(text='📅 Дата и время', callback_data='admin_bl datetime')
    builder.button(text='🔥 Профит', callback_data='admin_bl profit')
    builder.button(text='🤥 Фейк-сумма', callback_data='admin_bl fake_amount')
    builder.button(text='↩️ Назад', callback_data=f'admin_panel')
    return builder.adjust(2).as_markup()


def admin_bonuses():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text='👤 Выдать одному', callback_data='admin give_bonus one'),
                InlineKeyboardButton(text='👥 Выдать всем', callback_data='admin give_bonus all'))
    builder.row(InlineKeyboardButton(text='🔴 Снять бонусы', callback_data=f'admin remove_bonus'))
    builder.row(InlineKeyboardButton(text='↩️ Назад', callback_data=f'admin_panel'))
    return builder.as_markup()


def channel_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='🌐 Подписаться', url='https://t.me/Main_Bet_Channel')
    builder.button(text='✅ Проверить', callback_data='check follow_channel')
    return builder.adjust(2).as_markup()


def paying_kb(url):
    builder = InlineKeyboardBuilder()
    builder.button(text='💳 Оплатить', url=url)
    return builder.as_markup()


def choice_type_pay_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text='💳 Картой', callback_data='choice_type_pay card')
    builder.button(text='🏛️ СБП', callback_data='choice_type_pay sbp')
    return builder.adjust(2).as_markup()


def next_kb(callback):
    builder = InlineKeyboardBuilder()
    builder.button(text='✅ Продолжить', callback_data=callback)
    return builder.as_markup()


def accept_decline(user_id, summ):
    builder = InlineKeyboardBuilder()
    builder.button(text='✅ Одобрить', callback_data=f'withdraw_accept {user_id} {summ}')
    builder.button(text='❌ Отменить', callback_data=f'withdraw_decline {user_id} {summ}')
    try:
        builder.button(text='👤 Написать', url=f'tg://user?id={user_id}')
    except:
        pass
    return builder.adjust(1).as_markup()


def write_kb(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text='👤 Написать', url=f'tg://user?id={user_id}'))
    return builder.as_markup()


def back_button(callback, name='↩️ Назад'):
    builder = InlineKeyboardBuilder()
    builder.button(text=name, callback_data=callback)
    return builder.as_markup()


def crypto_pay_kb(bot_url: str, miniapp_url: str):
    builder = InlineKeyboardBuilder()
    builder.button(text='CryptoBot', url=bot_url)
    builder.button(text='В приложении', url=miniapp_url)
    return builder.adjust(2).as_markup()
