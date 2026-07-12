import os

from dotenv import load_dotenv
from aiogram import F, Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from FreeKassa import Client
from cryptobot import Client as CryptoBot
from aiogram.fsm.storage.redis import RedisStorage, Redis

load_dotenv()


def _required_env(name: str) -> str:
    value = os.getenv(name, '').strip()
    if not value:
        raise RuntimeError(f'Required environment variable {name} is not configured')
    return value


BOT_API = _required_env('BOT_API')
FREEKASSA_TOKEN = os.getenv('FREEKASSA_TOKEN', '')
YOOMONEY_API = os.getenv('YOOMONEY_API', '')
CRYPTOBOT_TOKEN = _required_env('CRYPTOBOT_TOKEN')
CRYPTO_WEBHOOK_SECRET = os.getenv('CRYPTO_WEBHOOK_SECRET', CRYPTOBOT_TOKEN)
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_USER = os.getenv('REDIS_USER', 'redisadmin')
REDIS_PASSWORD = os.getenv('REDIS_USER_PASSWORD') or os.getenv('REDIS_PASSWORD', '')
REDIS_LINK = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'
ADMINS = [566466985, 290757505, 1030165038]
CHANNEL_ID = -1002010011646
MAIN_CHANNEL_ID = -1001967035849
PNMVPN_BOT_USERNAME = 'pnmvpn_bot'

PNMVPN_HMAC_SECRET = _required_env('PNMVPN_HMAC_SECRET')
FREEKASSA_MERCHANT_ID = os.getenv('FREEKASSA_MERCHANT_ID', '')
FREEKASSA_SECRET_WORD_2 = os.getenv('FREEKASSA_SECRET_WORD_2', '')
CASE_NOTIFICATION_SCAN_SECONDS = max(10, int(os.getenv('CASE_NOTIFICATION_SCAN_SECONDS', '60')))


bot = Bot(BOT_API)
storage = RedisStorage(Redis(host=REDIS_HOST,
                             port=REDIS_PORT,
                             username=REDIS_USER,
                             password=REDIS_PASSWORD))
dp = Dispatcher(storage=storage)
redis = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    username=REDIS_USER,
    password=REDIS_PASSWORD,
    decode_responses=True
)
scheduler = AsyncIOScheduler()
crypto = CryptoBot(token=CRYPTOBOT_TOKEN)
# FKClient = Client(shop_id=57572,
#                   token=FREEKASSA_TOKEN)
