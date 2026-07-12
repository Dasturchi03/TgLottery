from peewee import Model, IntegerField, TextField, DateTimeField, BooleanField, DateField
from peewee import SqliteDatabase

db = SqliteDatabase(
    'database.db',
    pragmas={
        'journal_mode': 'wal',
        'busy_timeout': 10_000,
        'foreign_keys': 1,
    },
)


def init_db():
    Users.create_table()
    Settings.create_table()
    _ensure_schema()
    Settings.get_or_create()
    RufflesSettings.create_table()
    BigRuffleSettings.create_table()
    BigRuffleSettings.get_or_create()
    Payments.create_table()
    Tickets.create_table()
    Withdraws.create_table()


class Users(Model):
    user_id = IntegerField(unique=True)
    username = TextField()
    inactive = BooleanField(default=False)
    balance = IntegerField(default=0)
    prize_balance = IntegerField(default=0)
    prize_money = IntegerField(default=0)

    ref_money = IntegerField(default=0)
    ref_user_id = IntegerField(default=0)
    ref_payed = IntegerField(default=0)

    channel_payed = BooleanField(default=False)
    first_buy = IntegerField(default=0)
    can_withdraw_money = BooleanField(default=False)

    trial_bonus_claimed = BooleanField(default=False)
    trial_bonus_claimed_at = DateTimeField(null=True)

    class Meta:
        database = db


class Settings(Model):
    cost_invite = IntegerField(default=100)
    min_topup_balance = IntegerField(default=300)
    min_withdraw_balance = IntegerField(default=300)
    prize_follow = IntegerField(default=50)
    pnmvpn_trial_reward = IntegerField(default=1)

    # dice_game
    dice_daily_attempts = IntegerField(default=20)
    dice_double_reward = IntegerField(default=10)

    casino_daily_attempts = IntegerField(default=20)
    casino_reward = IntegerField(default=10)
    
    bowling_daily_attempts = IntegerField(default=20)
    bowling_reward = IntegerField(default=10)
    
    darts_daily_attempts = IntegerField(default=20)
    darts_reward = IntegerField(default=10)

    class Meta:
        database = db


def _ensure_schema():
    users_columns = {column.name for column in db.get_columns(Users._meta.table_name)}
    settings_columns = {column.name for column in db.get_columns(Settings._meta.table_name)}

    if "inactive" not in users_columns:
        db.execute_sql(
            f'ALTER TABLE "{Users._meta.table_name}" '
            'ADD COLUMN "inactive" INTEGER NOT NULL DEFAULT 0'
        )

    if "pnmvpn_trial_reward" not in settings_columns:
        db.execute_sql(
            f'ALTER TABLE "{Settings._meta.table_name}" '
            'ADD COLUMN "pnmvpn_trial_reward" INTEGER NOT NULL DEFAULT 1'
        )


class RufflesSettings(Model):
    name = TextField()  # Имя билета
    price = IntegerField(default=100)  # Цена билета
    mfo = IntegerField(default=5)  # Максимум билетов для одного пользователя
    mfa = IntegerField(default=20)  # Максимум билетов для данного типа
    ratio = IntegerField(default=10)  # Коэффициент
    active = BooleanField(default=False)  # активен ли розыгрыш
    ruffle_type = IntegerField(default=0) # 1 - Премиум. 0 - Обычный

    class Meta:
        database = db


class BigRuffleSettings(Model):
    price = IntegerField(default=500)
    datetime = DateTimeField(default=0)
    activity = IntegerField(default=0)
    profit = IntegerField(default=5)
    fake_amount = IntegerField(default=0)

    class Meta:
        database = db


class Payments(Model):
    user_id = IntegerField()
    order_id = IntegerField(default=0)
    amount = IntegerField()
    date_creation = DateField()
    datetime_creation = DateTimeField()
    payment_type = IntegerField()
    message_id = IntegerField(default=0)
    finished = IntegerField(default=0)

    class Meta:
        database = db


class Tickets(Model):
    user_id = IntegerField()
    ruffle_id = IntegerField()

    class Meta:
        database = db


class Withdraws(Model):
    id = IntegerField(primary_key=True)
    user_id = IntegerField()
    amount = IntegerField()
    created_datetime = DateTimeField()
    finished = BooleanField(default=False)

    class Meta:
        database = db
