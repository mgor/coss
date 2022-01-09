import logging
import asyncio

from typing import List, Dict, cast
from io import StringIO
from os import environ, path, getcwd
from aiohttp import ClientSession
from dataclasses import dataclass
from ssl import SSLContext
from json import loads as jsonloads

from ruamel.yaml import YAML
from marshmallow_dataclass import class_schema
from marshmallow.exceptions import ValidationError
from telegram import Bot, InputMediaPhoto
from telegram.constants import PARSEMODE_MARKDOWN_V2 as MARKDOWN
from bs4 import BeautifulSoup

yaml = YAML(typ="safe")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    @dataclass
    class Telegram:
        token: str
        chat_id: int

    products: List[str]
    telegram: Telegram


@dataclass
class Product:
    product: str
    name: str
    id: str
    price: str
    image: str
    status: str


def load_configuration() -> Config:
    products = environ.get("PRODUCTS", None)

    config: Dict[str, List[str] | Dict[str, str]] = {}

    if products is None:
        with open(path.join(getcwd(), "config.yaml"), encoding="utf-8") as fd:
            config = yaml.load(fd.read())
    else:
        telegram_token = environ.get("TELEGRAM_TOKEN", None)
        telegram_chat_id = environ.get("TELEGRAM_CHAT_ID", None)

        if telegram_token is None or telegram_chat_id is None:
            try:
                with open("/var/openfaas/secrets/token") as fd:
                    telegram_token = fd.read().strip()

                with open("/var/openfaas/secrets/chat_id") as fd:
                    telegram_chat_id = fd.read().strip()
            except FileNotFoundError:
                telegram_chat_id = telegram_token = None

        if telegram_token is None or telegram_chat_id is None:
            raise ValueError(
                "required telegram information not found in environment variables or openfaas secrets"
            )

        config.update(
            {
                "products": [product.strip() for product in products.split(" ")],
                "telegram": {
                    "token": telegram_token,
                    "chat_id": telegram_chat_id,
                },
            }
        )

    ConfigSchema = class_schema(Config)

    return ConfigSchema().load(config)


async def storage_status(product: str, session: ClientSession) -> Product:
    ssl = SSLContext()
    url = f"https://www.clasohlson.com/se/p/{product}"
    async with session.get(url, ssl=ssl) as response:
        html = await response.read()
        soup = BeautifulSoup(html, "html.parser")
        product_info: Dict[str, str] = {}
        for script in soup.find_all("script"):
            script_contents = script.get_text()
            if script.get("type") == "application/ld+json":
                product_info.update(jsonloads(script_contents))
            elif "coConfig.pdp" in script_contents:
                script_contents = (
                    script_contents.replace("coConfig.pdp = ", "")
                    .replace("'", '"')
                    .replace("productId :", '"productId":')
                    .replace(
                        "disableProductRecommendation :",
                        '"disableProductRecommendation":',
                    )
                )
                product_info.update(jsonloads(script_contents))

    id = product_info["productId"]
    if len(id) < 9:
        padding = 9 - len(id)
        id = id[:2] + "0" * padding + id[2:]

    offers = cast(Dict[str, str], product_info["offers"])

    url = (
        "https://www.clasohlson.com/se/cocheckout/getCartDataOnReload?"
        f"variantProductCode={id}"
    )

    async with session.get(url, ssl=ssl) as response:
        storage_status = await response.json()

    image = f"https://images.clasohlson.com{product_info['image']}"

    return Product(
        product=product,
        name=product_info["name"],
        id=id,
        image=image,
        price=f'{offers["price"]} {offers["priceCurrency"]}',
        status=storage_status["webStockStatus"],
    )


async def check(
    loop: asyncio.AbstractEventLoop,
    config: Config,
) -> List[Product]:
    async with ClientSession(loop=loop) as session:
        responses = await asyncio.gather(
            *[storage_status(product, session) for product in config.products],
            return_exceptions=True,
        )
        return cast(List[Product], responses)


def main() -> int:
    try:
        config = load_configuration()
        loop = asyncio.get_event_loop()
        products = loop.run_until_complete(check(loop, config))
        media_group: List[InputMediaPhoto] = []
        messages: List[str] = []
        send_message: bool = False

        for product in products:
            name = product.name.replace("-", "\\-")

            message = (
                f"[{name}: {product.price}]"
                f"(https://www.clasohlson.com/se/p/{product.product})"
            )

            if product.status != "inStock":
                message = f"~{message}~"
            else:
                send_message = True

            messages.append(message)
            media_group.append(
                InputMediaPhoto(
                    product.image,
                    caption="",
                    parse_mode=MARKDOWN,
                )
            )

        if send_message:
            bot = Bot(token=config.telegram.token)
            bot.send_media_group(chat_id=config.telegram.chat_id, media=media_group)
            bot.send_message(
                chat_id=config.telegram.chat_id,
                text="\n".join(messages),
                disable_web_page_preview=True,
                parse_mode=MARKDOWN,
            )

        return 0
    except FileNotFoundError:
        logger.error(f"config.yaml not found in {getcwd()}")
        return 1
    except ValueError as e:
        logger.error(str(e))
        return 1
    except ValidationError as e:
        error = StringIO()
        yaml.dump(e.normalized_messages(), error)
        error.seek(0)
        logger.error(f"config.yaml is not valid:\n{error.read()}")
        return 1
