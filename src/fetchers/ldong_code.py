import asyncio

import httpx

from src.client import create_client, fetch_single, save_raw
from src.config import ENDPOINTS, REQUEST_DELAY


async def fetch_depth1(client: httpx.AsyncClient, lang: str) -> list[dict]:
    """1-depth 시/도 목록을 조회한다."""
    url = ENDPOINTS["ldong_code"][lang]
    items = await fetch_single(client, url, {"lDongListYn": "N"})
    return items


async def fetch_depth2(
    client: httpx.AsyncClient, lang: str, region_code: str
) -> list[dict]:
    """2-depth 시/군/구 목록을 조회한다."""
    url = ENDPOINTS["ldong_code"][lang]
    items = await fetch_single(
        client, url, {"lDongRegnCd": region_code, "lDongListYn": "N"}
    )
    return items


async def fetch_ldong_code() -> dict:
    """법정동 코드 전체(kr/en, 1-depth + 2-depth)를 수신하고 raw에 저장한다.

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
            save_raw(depth1, "ldong_code", lang, "depth1")
            print(f"  [{lang}] depth1: {len(depth1)} regions")

            depth2: dict[str, list[dict]] = {}
            for region in depth1:
                code = region.get("lDongRegnCd", region.get("code", ""))
                if not code:
                    continue
                await asyncio.sleep(REQUEST_DELAY)
                children = await fetch_depth2(client, lang, code)
                depth2[code] = children
                save_raw(children, "ldong_code", lang, f"depth2_{code}")
                print(f"  [{lang}] depth2 ({code}): {len(children)} districts")

            result[lang] = {"depth1": depth1, "depth2": depth2}

    return result
