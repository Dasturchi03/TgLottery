import hashlib
import hmac
import unittest

from utils.models import Users, Settings, db
from utils.bonus_content import bonus_page_caption, referral_caption
from utils.bonus_operations import credit_bonus, credit_bonus_to_user
from handlers.admin import _find_user
from crypto_webhook import (
    TrialCreditIn,
    _calc_signature,
    credit_trial_bonus,
    verify_crypto_webhook_signature,
)
from config import CRYPTOBOT_TOKEN
from utils.keyboards import bonus_menu


class StageOneRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.close()
        db.init(':memory:')
        db.connect()
        db.create_tables([Users, Settings])

    def setUp(self):
        Users.delete().execute()
        Settings.delete().execute()
        Settings.create(cost_invite=7, pnmvpn_trial_reward=3)

    @classmethod
    def tearDownClass(cls):
        db.close()

    def test_bonus_page_uses_diamond_semantics(self):
        caption = bonus_page_caption()
        self.assertIn('💎', caption)
        self.assertNotIn('USDT', caption)
        self.assertNotIn('USDt', caption)

    def test_referral_caption_uses_current_admin_value(self):
        caption = referral_caption('https://t.me/example')
        self.assertIn('7 💎', caption)
        self.assertNotIn('USDt', caption)

    def test_bonus_keyboard_uses_current_referral_and_pnmvpn_values(self):
        markup = bonus_menu()
        texts = [button.text for row in markup.inline_keyboard for button in row]
        self.assertIn('👥 7 💎 за друга', texts)
        self.assertIn('💎 3 за ₽1', texts)

    def test_find_user_by_telegram_id_and_case_insensitive_username(self):
        user = Users.create(user_id=10001, username='NewName')
        self.assertEqual(_find_user('10001').id, user.id)
        self.assertEqual(_find_user('@newname').id, user.id)

    def test_credit_all_is_database_first(self):
        users = [
            Users.create(user_id=1, username='one'),
            Users.create(user_id=2, username='two', inactive=True),
        ]
        self.assertEqual(credit_bonus([user.id for user in users], 5), 2)
        self.assertEqual([u.prize_balance for u in Users.select().order_by(Users.id)], [5, 5])

    def test_credit_one(self):
        user = Users.create(user_id=1, username='one')
        self.assertTrue(credit_bonus_to_user(user, 4))
        self.assertEqual(Users.get_by_id(user.id).prize_balance, 4)

    def test_pnmvpn_reward_is_dynamic_and_idempotent(self):
        user = Users.create(user_id=77, username='trial')
        payload = TrialCreditIn(user_id=user.user_id)
        signature = _calc_signature(user.user_id)
        first = credit_trial_bonus(payload, signature)
        second = credit_trial_bonus(payload, signature)
        self.assertEqual(first['status'], 'credited')
        self.assertEqual(first['amount'], 3)
        self.assertEqual(second['status'], 'already_claimed')
        self.assertEqual(Users.get_by_id(user.id).prize_balance, 3)

    def test_crypto_webhook_signature_checks_raw_body(self):
        body = b'{"update_type":"invoice_paid"}'
        secret = hashlib.sha256(CRYPTOBOT_TOKEN.encode()).digest()
        signature = hmac.new(secret, body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_crypto_webhook_signature(body, signature))
        self.assertFalse(verify_crypto_webhook_signature(body + b' ', signature))
        self.assertFalse(verify_crypto_webhook_signature(body, None))


if __name__ == '__main__':
    unittest.main()
