from yoomoney import Quickpay, Client, Authorize
from config import YOOMONEY_API


async def create_pay(amount, label):
    quickpay = Quickpay(
        receiver=YOOMONEY_API[:YOOMONEY_API.find('.')],
        quickpay_form="button",
        targets="Пополнение баланса",
        paymentType="AC",
        sum=amount,
        label=label,
    )
    return quickpay.base_url


async def get_balance():
    client = Client(YOOMONEY_API)
    return client.account_info().balance


def auth():
    Authorize(
          client_id="E34975460179364365F7898B4B42F333CB97FE6F900FF70B8F1215C049AEF4D7",
          redirect_uri="https://t.me/Pure_Random_Bot",
          scope=["account-info",
                 "operation-history",
                 "operation-details",
                 "incoming-transfers",
                 "payment-p2p",
                 "payment-shop",
                 ]
          )