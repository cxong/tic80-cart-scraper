import asyncio
import datetime as dt
import json
from pathlib import Path

import aiofiles
import aiohttp
import pandas as pd
from bs4 import BeautifulSoup

TIC80_BASE_URL = "https://tic80.com"
TIC80_CART_URL = f"{TIC80_BASE_URL}/play?cart={{cart_id}}"
OUTPUT_DIR = Path("/tmp/tic80-carts")
NUM_WORKERS = 5
MAX_CART_ID = 3400


async def cart_dl_worker(queue: asyncio.Queue):
    async with aiohttp.ClientSession() as session:
        while True:
            cart_id, dl_link = await queue.get()
            # Download carts
            out_dir = OUTPUT_DIR / "carts"
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{cart_id}.tic"
            if path.exists():
                print(f"Skipping {path=}")
            else:
                print(f"Downloading {dl_link=}...")
                async with session.get(dl_link) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(path, mode="wb") as f:
                            await f.write(await resp.read())
                        print(f"Downloaded {str(path)}")
            queue.task_done()


async def main():
    metadata = []
    cart_dl_queue = asyncio.Queue()
    cart_dl_tasks = [asyncio.create_task(cart_dl_worker(cart_dl_queue))] * NUM_WORKERS
    out_dir = OUTPUT_DIR / "meta"
    out_dir.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        for cart_id in range(1, MAX_CART_ID):
            path = out_dir / f"{cart_id}.json"
            if path.exists():
                async with aiofiles.open(path) as f:
                    contents = await f.read()
                meta = json.loads(contents)
            else:
                url = TIC80_CART_URL.format(cart_id=cart_id)
                print("Fetching cart", cart_id)
                async with session.get(url) as resp:
                    if resp.status == 404:
                        continue
                    content = await resp.text()
                soup = BeautifulSoup(content, "html.parser")
                # Scrape metadata from the cart page
                heading = soup.find("h1")
                category = heading.text.split(" > ")[0]
                title = heading.text[len(category + " > ") :]
                attr_divs = heading.find_next_siblings("div")
                desc = attr_divs[0].text
                author = next(
                    div for div in attr_divs if div.text.startswith("made by ")
                ).text.split("made by ")[1]
                uploader_div = next(
                    div for div in attr_divs if div.text.startswith("uploaded by ")
                )
                uploader = uploader_div.text.split("uploaded by ")[1]
                uploader_href = uploader_div.find("a").attrs["href"]
                uploader_id = int(uploader_href.split("id=")[1])
                uploader_link = TIC80_BASE_URL + uploader_href
                added = (
                    int(
                        next(div for div in attr_divs if div.text.startswith("added: "))
                        .find("span", class_="date")
                        .attrs["value"]
                    )
                    / 1000
                )
                try:
                    updated = (
                        int(
                            next(
                                div
                                for div in attr_divs
                                if div.text.startswith("updated: ")
                            )
                            .find("span", class_="date")
                            .attrs["value"]
                        )
                        / 1000
                    )
                except StopIteration:
                    updated = 0
                rating = int(soup.find(id="rating-label").text)
                text = (
                    heading.parent.parent.find("hr", recursive=False)
                    .find_next_sibling("p")
                    .text
                )
                dl_link = (
                    TIC80_BASE_URL
                    + soup.find("a", string="download cartridge").attrs["href"]
                )
                meta = {
                    "cart_id": cart_id,
                    "category": category,
                    "title": title,
                    "desc": desc,
                    "author": author,
                    "uploader": uploader,
                    "uploader_id": uploader_id,
                    "uploader_link": uploader_link,
                    "url": url,
                    "filename": dl_link.split("/")[-1],
                    "added": added,
                    "updated": updated,
                    "rating": rating,
                    "text": text,
                }
                async with aiofiles.open(path, mode="w") as f:
                    await f.write(json.dumps(meta))
                print(f"Scraped {cart_id=}")

            await cart_dl_queue.put((cart_id, dl_link))

            metadata.append(meta)

            cart_id += 1

    print("Waiting for workers...")
    await cart_dl_queue.join()
    for task in cart_dl_tasks:
        task.cancel()
    await asyncio.gather(*cart_dl_tasks, return_exceptions=True)

    df = pd.DataFrame(metadata)
    df.to_csv(OUTPUT_DIR / "metadata.csv")


if __name__ == "__main__":
    asyncio.run(main())
