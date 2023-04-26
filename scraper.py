import asyncio
from pathlib import Path

import aiofiles
import aiohttp
import pandas as pd
from bs4 import BeautifulSoup

TIC80_BASE_URL = "https://tic80.com"
TIC80_CART_URL = f"{TIC80_BASE_URL}/play?cart={{cart_id}}"
OUTPUT_DIR = Path("/tmp/tic80-carts")


async def main():
    cart_id = 1
    metadata = []
    async with aiohttp.ClientSession() as session:
        while True:
            url = TIC80_CART_URL.format(cart_id=cart_id)
            print("Fetching cart", cart_id)
            async with session.get(url) as resp:
                if resp.status == 404:
                    break
                content = await resp.text()
            soup = BeautifulSoup(content, "html.parser")

            # Download carts
            out_dir = (OUTPUT_DIR / "carts")
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{cart_id}.tic"
            dl_link = TIC80_BASE_URL + soup.find("a", string="download cartridge").attrs["href"]
            if path.exists():
                print(f"Skipping {path=}")
            else:
                print(f"Downloading {dl_link=}...")
                async with session.get(dl_link) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(path, mode="wb") as f:
                            await f.write(await resp.read())
                        print(f"Downloaded {str(path)}")

            metadata.append({
                "cart_id": cart_id,
                "url": url,
                "filename": dl_link.split("/")[-1],
            })
            cart_id += 1
    df = pd.DataFrame(metadata)
    df.to_csv(OUTPUT_DIR / "metadata.csv")


if __name__ == "__main__":
    asyncio.run(main())
