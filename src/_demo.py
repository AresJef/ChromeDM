import asyncio
from chromedm import ChromeDM


async def demo():
    cdm = ChromeDM()
    for _ in range(10):
        driver = await cdm.install(
            1, proxy="http://127.0.0.1:7890", timeout=10, max_cache=20
        )
        print(driver)

    print(cdm.get_chrome_version())


if __name__ == "__main__":
    asyncio.run(demo())
