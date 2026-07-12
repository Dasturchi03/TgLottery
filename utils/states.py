from aiogram.fsm.state import State, StatesGroup


class Admin(StatesGroup):
    add_ruffle = State()
    add_ruffle_type = State()
    edit_ruffle = State()
    edit_settings = State()
    edit_big_ruffle = State()
    talk_input = State()
    bonus_amount = State()
    bonus_username = State()
    remove_bonus_username = State()
    remove_bonus_amount = State()
    talk_media = State()
    talk_buttons = State()


class Wallet(StatesGroup):
    topup = State()
    withdraw_to = State()
    withdraw_card = State()
    withdraw_summ = State()
