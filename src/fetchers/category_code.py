import asyncio

import httpx

from src.client import create_client, fetch_single, save_raw
from src.config import ENDPOINTS, REQUEST_DELAY


async def fetch_depth1(client: httpx.AsyncClient, lang: str) -> list[dict]:
    """1-depth 대분류 목록을 조회한다."""
    url = ENDPOINTS["category_code"][lang]
    items = await fetch_single(client, url)
    return items


async def fetch_depth2(
    client: httpx.AsyncClient, lang: str, cat1_code: str
) -> list[dict]:
    """2-depth 중분류 목록을 조회한다."""
    url = ENDPOINTS["category_code"][lang]
    items = await fetch_single(client, url, {"lclsSystm1": cat1_code})
    return items


async def fetch_category_code() -> dict:
    """분류체계 코드 전체(kr/en, 2-depth)를 수신하고 raw에 저장한다.

    Returns:
        {
            "kr": {"depth1": [...], "depth2": {code: [...], ...}},
            "en": {"depth1": [...], "depth2": {code: [...], ...}},
        }
    """
    result: dict = {}

    async with create_client() as client:
        for lang in ("kr", "en"):
            depth1 = await fetch_depth1(client, lang)
            save_raw(depth1, "category_code", lang, "depth1")
            print(f"  [{lang}] depth1: {len(depth1)} categories")

            depth2: dict[str, list[dict]] = {}

            for cat1 in depth1:
                cat1_code = cat1.get("lclsSystmCode", cat1.get("code", ""))
                if not cat1_code:
                    continue
                await asyncio.sleep(REQUEST_DELAY)
                children = await fetch_depth2(client, lang, cat1_code)
                depth2[cat1_code] = children
                save_raw(children, "category_code", lang, f"depth2_{cat1_code}")
                print(f"  [{lang}] depth2 ({cat1_code}): {len(children)} sub-categories")

            result[lang] = {"depth1": depth1, "depth2": depth2}

    return result
