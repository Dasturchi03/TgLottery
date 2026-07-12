from aiohttp import ClientSession, TCPConnector
from FreeKassa.payment_mails import MAILS
from typing import Optional
from random import choice
from utils.models import Payments
import datetime
import logging
import certifi
import hashlib
import hmac
import ssl
from pydantic import BaseModel
from typing import Optional


class CreatePayment(BaseModel):
    type: Optional[str] = None
    orderId: Optional[int] = None
    orderHash: Optional[str] = None
    location_method: Optional[str] = None
    fields: Optional[list] = None
    location: Optional[str] = None
    error: Optional[str] = None


class Client:
    def __init__(self,
                 token: str,
                 shop_id: int,
                 ):

        self.token = token
        self.shop_id = shop_id
        self.base_url = 'https://api.freekassa.com/v1'

        self.logger = logging.getLogger()
        self._session: Optional[ClientSession] = None

    def _getsession(self) -> ClientSession:

        if isinstance(self._session, ClientSession) and not self._session.closed:
            return self._session

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = TCPConnector(ssl=ssl_context)

        self._session = ClientSession(connector=connector)

        return self._session

    async def close_connection(self):
        if self._session:
            await self._session.close()

    async def _request(self, method: str, freekassa_method: str, url: str = None, **kwargs) -> dict:
        session = self._getsession()
        if url is None:
            url = self.base_url
        async with session.request(method, url + freekassa_method, **kwargs) as response:
            response = await response.json(content_type="application/json")
        return response

    async def create_payment(self, user_id: int,
                             amount: int,
                             payment_type: int) -> (Payments, CreatePayment):
        payment: Payments = Payments.create(user_id=user_id,
                                            amount=amount,
                                            date_creation=datetime.date.today(),
                                            datetime_creation=datetime.datetime.now(),
                                            payment_type=payment_type)
        redirect_url = f'https://t.me/Pure_Random_Bot'
        data = {'shopId': self.shop_id,
                'nonce': int(datetime.datetime.now().timestamp()),
                'paymentId': payment.id,
                'i': payment_type,
                'email': choice(MAILS.split('\n')),
                'amount': amount,
                'currency': 'RUB',
                'success_url': redirect_url,
                'failure_url': redirect_url,
                'notification_url': f'http://24mainbet.ru/payment-notify',
                'ip': choice(['95.214.27.169',
                              '199.195.252.239',
                              '64.62.156.108',
                              '145.224.103.132',
                              '199.195.252.239',
                              '49.230.145.86',
                              '168.119.157.136',
                              '188.166.22.148',
                              '176.59.135.125'])}
        new_data = {}
        for key in sorted(data.keys()):
            new_data[key] = data[key]

        secret = '|'.join([str(new_data[key]) for key in new_data])
        secret = hmac.new(self.token.encode(), secret.encode(), hashlib.sha256)
        new_data['signature'] = secret.hexdigest()
        response = await self._request(method='post',
                                       freekassa_method='/orders/create',
                                       json=new_data)
        payment.order_id = response.get('orderId', 0)
        payment.save()

        logging.info(f"[FreeKassa] Response create payment: {response}")
        return payment, CreatePayment(**response)
