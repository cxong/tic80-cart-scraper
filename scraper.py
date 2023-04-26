import asyncio

import aiohttp
from bs4 import BeautifulSoup

TIC80_CART_URL = "https://tic80.com/play?cart={cart_id}"

async def main():
    cart_id = 0
    async with aiohttp.ClientSession() as session:
        while True:
            url = TIC80_CART_URL.format(cart_id=cart_id)
            print("Fetching cart", cart_id)
            async with session.get(url) as resp:
                if resp.status == 404:
                    break
                content = await resp.text()
            soup = BeautifulSoup(content, "html.parser")

            cart_id += 1


if __name__ == "__main__":
    asyncio.run(main())
