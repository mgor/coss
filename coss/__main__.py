import logging
import asyncio

from typing import List, Dict, Optional, cast
from io import StringIO, BytesIO
from os import path, getcwd
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
from PIL import Image

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
    id: str
    name: str
    product_id: str
    price: str
    image: BytesIO
    status: str


def load_configuration() -> Config:
    with open(path.join(getcwd(), "config.yaml"), encoding="utf-8") as fd:
        loaded = yaml.load(fd.read())
        ConfigSchema = class_schema(Config)

        return ConfigSchema().load(loaded)


async def storage_status(product_id: str, session: ClientSession) -> Product:
    ssl = SSLContext()
    url = f"https://www.clasohlson.com/se/p/{product_id}"
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

    product_id = product_info["productId"]
    if len(product_id) < 9:
        padding = 9 - len(product_id)
        product_id = product_id[:2] + "0" * padding + product_id[2:]

    offers = cast(Dict[str, str], product_info["offers"])

    url = (
        "https://www.clasohlson.com/se/cocheckout/getCartDataOnReload?"
        f"variantProductCode={product_id}"
    )

    async with session.get(url, ssl=ssl) as response:
        storage_status = await response.json()

    url = f"https://images.clasohlson.com{product_info['image']}"

    async with session.get(url, ssl=ssl) as response:
        image = BytesIO(await response.read())
        image.seek(0)

    return Product(
        id=product_id,
        name=product_info["name"],
        product_id=product_id,
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

        for product in products:
            name = product.name.replace("-", "\\-")

            message = (
                f"[{name}: {product.price}]"
                f"(https://www.clasohlson.com/se/p/{product.id})"
            )

            if product.status != "inStock":
                message = f"~{message}~"
            messages.append(message)
            media_group.append(
                InputMediaPhoto(
                    product.image,
                    caption="",
                    parse_mode=MARKDOWN,
                )
            )

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
    except ValidationError as e:
        error = StringIO()
        yaml.dump(e.normalized_messages(), error)
        error.seek(0)
        logger.error(f"config.yaml is not valid:\n{error.read()}")
        return 1
