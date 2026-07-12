from aiohttp import ClientSession, TCPConnector
from typing import Optional
import ssl
import certifi
from cryptobot.models import Invoice, ButtonName, Asset, Transfer, Balance


class Client:
    def __init__(self,
                 token: str,
                 base_url: str = None,
                 ):

        self.base_url = "https://pay.crypt.bot/api/" if base_url is None else base_url

        self.token = token

        self._session: Optional[ClientSession] = None

    def _getsession(self) -> ClientSession:

        if isinstance(self._session, ClientSession) and not self._session.closed:
            return self._session

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = TCPConnector(ssl=ssl_context)

        self._session = ClientSession(connector=connector)

        return self._session

    async def _request(self, method, **kwargs) -> dict:
        session = self._getsession()
        async with session.get(self.base_url + method, **kwargs) as response:
            response = await response.json(content_type="application/json")

        await self._session.close()

        return response

    async def create_payment(self,
                             amount: float,
                             asset: Asset = None,
                             currency_type: str = 'crypto',
                             fiat: str = None,
                             description: str = None,
                             hidden_message: str = None,
                             accepted_assets: str = None,
                             paid_btn_name: ButtonName = None,
                             paid_btn_url: str = None,
                             payload: str = None,
                             allow_comments: bool = True,
                             allow_anonymous: bool = True,
                             expires_in: int = None):
        method = 'createInvoice'

        data = {
            "asset": asset.name if asset is not None else None,
            "currency_type": currency_type,
            "fiat": fiat,
            "accepted_assets": accepted_assets,
            "amount": str(amount),
            "description": description,
            "hidden_message": hidden_message,
            "paid_btn_url": paid_btn_url,
            "payload": payload,
            "allow_comments": allow_comments,
            "allow_anonymous": allow_anonymous,
            "expires_in": expires_in,
        }

        for key, value in dict(data).items():
            if value is None:
                del data[key]
        if paid_btn_name:
            data["paid_btn_name"] = paid_btn_name.name

        response = await self._request(method, json=data, headers={'Crypto-Pay-API-Token': self.token})
        info = response.get('result')
        print(response)
        return Invoice(**info)

    async def transfer(self, user_id: int,
                       asset: Asset,
                       amount: str | int,
                       spend_id: str | int):
        method = 'transfer'

        data = {
            "user_id": user_id,
            "asset": asset.value,
            "amount": amount,
            "spend_id": spend_id,
        }

        response = await self._request(method, json=data, headers={'Crypto-Pay-API-Token': self.token})
        info = response.get('result')
        print(response)
        return Transfer(**info)

    async def get_balance(self):
        method = 'getBalance'

        response = await self._request(method, headers={'Crypto-Pay-API-Token': self.token})
        info = response.get('result')[0]
        print(response)
        return Balance(**info)
