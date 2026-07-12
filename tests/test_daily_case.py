import asyncio
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from peewee import SqliteDatabase

from utils.daily_case import (
    CasePrize,
    daily_case_button_text,
    format_remaining,
    resolve_case_roll,
)
from utils.daily_case_operations import record_terminal_outcome
from utils.daily_case_notifications import (
    NOTIFICATION_CLAIM_LEASE,
    claim_ready_case_notifications,
    complete_case_notification,
    send_ready_case_notifications,
)
from utils.daily_case_storage import (
    acquire_daily_case_lock,
    add_extra_dice_attempts,
    daily_case_lock_key,
    extra_dice_attempts_key,
    get_extra_dice_attempts,
    release_daily_case_lock,
)
from utils.models import Settings, Users, _ensure_schema, db


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    async def get(self, key):
        return self.values.get(key)

    async def incrby(self, key, amount):
        self.values[key] = int(self.values.get(key, 0)) + amount
        return self.values[key]

    async def expire(self, key, seconds):
        self.expirations[key] = seconds
        return True

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        if ex:
            self.expirations[key] = ex
        return True

    async def eval(self, script, number_of_keys, key, token):
        if self.values.get(key) == token:
            del self.values[key]
            return 1
        return 0


class FakeBot:
    def __init__(self, fail=False):
        self.fail = fail
        self.messages = []

    async def send_message(self, chat_id, text, **kwargs):
        if self.fail:
            raise RuntimeError('temporary Telegram failure')
        self.messages.append((chat_id, text, kwargs))


class DailyCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not db.is_closed():
            db.close()
        db.init(':memory:')
        db.connect()
        db.create_tables([Users, Settings])

    def setUp(self):
        Users.delete().execute()
        Settings.delete().execute()
        Settings.create()

    @classmethod
    def tearDownClass(cls):
        db.close()

    def test_probability_boundaries(self):
        expected = {
            1: (CasePrize.EMPTY, 0),
            25: (CasePrize.EMPTY, 0),
            26: (CasePrize.DICE_ATTEMPTS, 1),
            48: (CasePrize.DICE_ATTEMPTS, 1),
            49: (CasePrize.DIAMONDS, 1),
            68: (CasePrize.DIAMONDS, 1),
            69: (CasePrize.DICE_ATTEMPTS, 2),
            79: (CasePrize.DICE_ATTEMPTS, 2),
            80: (CasePrize.DIAMONDS, 2),
            86: (CasePrize.DIAMONDS, 2),
            87: (CasePrize.DICE_ATTEMPTS, 3),
            90: (CasePrize.DICE_ATTEMPTS, 3),
            91: (CasePrize.DIAMONDS, 3),
            93: (CasePrize.DIAMONDS, 3),
            94: (CasePrize.REROLL, 0),
            100: (CasePrize.REROLL, 0),
        }
        for roll, result in expected.items():
            outcome = resolve_case_roll(roll)
            self.assertEqual((outcome.prize, outcome.amount), result)

    def test_probability_table_contains_exactly_100_slots(self):
        counts = Counter(resolve_case_roll(roll).prize for roll in range(1, 101))
        self.assertEqual(counts[CasePrize.EMPTY], 25)
        self.assertEqual(counts[CasePrize.DICE_ATTEMPTS], 38)
        self.assertEqual(counts[CasePrize.DIAMONDS], 30)
        self.assertEqual(counts[CasePrize.REROLL], 7)

    def test_probability_rejects_out_of_range_values(self):
        for value in (0, 101, True, 1.5):
            with self.assertRaises(ValueError):
                resolve_case_roll(value)

    def test_dynamic_button_and_rounded_countdown(self):
        now = datetime(2026, 7, 12, 12, 0, 0)
        self.assertEqual(daily_case_button_text(None, now), '🎁 Ежедневный кейс')
        opened = now - timedelta(hours=5, minutes=17)
        self.assertEqual(daily_case_button_text(opened, now), '⏳ Кейс (18:43)')
        self.assertEqual(format_remaining(timedelta(seconds=1)), '00:01')
        self.assertEqual(daily_case_button_text(now - timedelta(hours=24), now), '🎁 Ежедневный кейс')

    def test_terminal_diamond_result_is_atomic_and_cooldown_guarded(self):
        user = Users.create(user_id=500, username='case-user')
        opened_at = datetime(2026, 7, 12, 12, 0, 0)
        outcome = resolve_case_roll(80)
        self.assertTrue(record_terminal_outcome(user.user_id, outcome, opened_at))
        self.assertFalse(record_terminal_outcome(user.user_id, outcome, opened_at))
        refreshed = Users.get_by_id(user.id)
        self.assertEqual(refreshed.prize_balance, 2)
        self.assertIsNotNone(refreshed.daily_case_opened_at)
        self.assertIsNone(refreshed.daily_case_notification_sent_at)

    def test_daily_redis_extra_attempts_accumulate(self):
        async def scenario():
            redis = FakeRedis()
            self.assertEqual(await get_extra_dice_attempts(redis, 42), 0)
            self.assertEqual(await add_extra_dice_attempts(redis, 42, 2), 2)
            self.assertEqual(await add_extra_dice_attempts(redis, 42, 1), 3)
            self.assertEqual(await get_extra_dice_attempts(redis, 42), 3)
            key = extra_dice_attempts_key(42)
            self.assertGreaterEqual(redis.expirations[key], 60)

        asyncio.run(scenario())

    def test_parallel_case_lock_allows_only_one_owner(self):
        async def scenario():
            redis = FakeRedis()
            first = await acquire_daily_case_lock(redis, 42)
            second = await acquire_daily_case_lock(redis, 42)
            self.assertIsNotNone(first)
            self.assertIsNone(second)
            await release_daily_case_lock(redis, 42, 'wrong-token')
            self.assertIn(daily_case_lock_key(42), redis.values)
            await release_daily_case_lock(redis, 42, first)
            self.assertNotIn(daily_case_lock_key(42), redis.values)

        asyncio.run(scenario())

    def test_notification_claim_prevents_duplicates_and_recovers_stale_claim(self):
        now = datetime(2026, 7, 13, 13, 0, 0)
        user = Users.create(
            user_id=700,
            username='notify',
            daily_case_opened_at=now - timedelta(hours=25),
        )
        first = claim_ready_case_notifications(now)
        second = claim_ready_case_notifications(now)
        self.assertEqual(first, [user.id])
        self.assertEqual(second, [])

        Users.update(
            daily_case_notification_claimed_at=now - NOTIFICATION_CLAIM_LEASE - timedelta(seconds=1)
        ).where(Users.id == user.id).execute()
        self.assertEqual(claim_ready_case_notifications(now), [user.id])

    def test_silent_notification_marks_sent_and_has_open_button(self):
        async def scenario():
            now = datetime(2026, 7, 13, 13, 0, 0)
            user = Users.create(
                user_id=701,
                username='notify-success',
                daily_case_opened_at=now - timedelta(hours=24),
            )
            bot = FakeBot()
            stats = await send_ready_case_notifications(bot, now=now)
            self.assertEqual(stats['sent'], 1)
            self.assertEqual(len(bot.messages), 1)
            chat_id, text, kwargs = bot.messages[0]
            self.assertEqual(chat_id, user.user_id)
            self.assertEqual(text, '📦 Кейс снова можно открыть!')
            self.assertTrue(kwargs['disable_notification'])
            button = kwargs['reply_markup'].inline_keyboard[0][0]
            self.assertEqual(button.callback_data, 'daily_case_open')
            refreshed = Users.get_by_id(user.id)
            self.assertIsNotNone(refreshed.daily_case_notification_sent_at)
            self.assertIsNone(refreshed.daily_case_notification_claimed_at)
            self.assertEqual((await send_ready_case_notifications(bot, now=now))['claimed'], 0)

        asyncio.run(scenario())

    def test_temporary_notification_failure_releases_claim_for_retry(self):
        async def scenario():
            now = datetime(2026, 7, 13, 13, 0, 0)
            user = Users.create(
                user_id=702,
                username='notify-retry',
                daily_case_opened_at=now - timedelta(hours=25),
            )
            failed = await send_ready_case_notifications(FakeBot(fail=True), now=now)
            self.assertEqual(failed['failed'], 1)
            refreshed = Users.get_by_id(user.id)
            self.assertIsNone(refreshed.daily_case_notification_claimed_at)
            self.assertIsNone(refreshed.daily_case_notification_sent_at)

            successful_bot = FakeBot()
            retried = await send_ready_case_notifications(successful_bot, now=now)
            self.assertEqual(retried['sent'], 1)
            self.assertEqual(len(successful_bot.messages), 1)

        asyncio.run(scenario())

    def test_old_notification_completion_cannot_mark_a_new_case_cycle(self):
        claimed_at = datetime(2026, 7, 13, 13, 0, 0)
        user = Users.create(
            user_id=703,
            username='notify-race',
            daily_case_opened_at=claimed_at - timedelta(hours=25),
        )
        self.assertEqual(claim_ready_case_notifications(claimed_at), [user.id])
        new_outcome = resolve_case_roll(1)
        self.assertTrue(record_terminal_outcome(user.user_id, new_outcome, claimed_at))
        self.assertFalse(complete_case_notification(user.id, claimed_at, claimed_at))
        refreshed = Users.get_by_id(user.id)
        self.assertIsNone(refreshed.daily_case_notification_sent_at)
        self.assertIsNone(refreshed.daily_case_notification_claimed_at)


class DailyCaseMigrationTests(unittest.TestCase):
    def test_old_database_gets_nullable_case_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'old.db'
            database = SqliteDatabase(path)
            database.connect()
            database.execute_sql(
                'CREATE TABLE users (id INTEGER PRIMARY KEY, user_id INTEGER, username TEXT)'
            )
            database.execute_sql(
                'CREATE TABLE settings (id INTEGER PRIMARY KEY, cost_invite INTEGER)'
            )
            _ensure_schema(database)
            columns = {column.name: column for column in database.get_columns('users')}
            self.assertIn('daily_case_opened_at', columns)
            self.assertIn('daily_case_notification_sent_at', columns)
            self.assertIn('daily_case_notification_claimed_at', columns)
            self.assertTrue(columns['daily_case_opened_at'].null)
            self.assertTrue(columns['daily_case_notification_sent_at'].null)
            self.assertTrue(columns['daily_case_notification_claimed_at'].null)
            database.close()


if __name__ == '__main__':
    unittest.main()
