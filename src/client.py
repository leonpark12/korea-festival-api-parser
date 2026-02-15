import asyncio
import json
import math
from pathlib import Path

import httpx

from src.config import API_KEY, COMMON_PARAMS, REQUEST_DELAY

RAW_DIR = Path(__file__).resolve().parent.parent / "raw"


def _build_params(extra: dict | None = None) -> dict:
    """공통 파라미터에 serviceKey와 추가 파라미터를 병합한다."""
    params = {**COMMON_PARAMS}
    params["serviceKey"] = API_KEY
    if extra:
        params.update(extra)
    return params


def _parse_response(data: dict) -> tuple[list[dict], int]:
    """API 응답에서 items 리스트와 totalCount를 추출한다."""
    body = data.get("response", {}).get("body", {})
    total_count = body.get("totalCount", 0)

    items_wrapper = body.get("items", "")
    if not items_wrapper or items_wrapper == "":
        return [], total_count

    item = items_wrapper.get("item", [])
    if isinstance(item, dict):
        item = [item]
    return item, total_count


async def fetch_all_pages(
    client: httpx.AsyncClient,
    endpoint_url: str,
    extra_params: dict | None = None,
) -> list[dict]:
    """totalCount 기반으로 모든 페이지를 순회하여 전체 items를 반환한다."""
    params = _build_params(extra_params)
    params["pageNo"] = 1

    resp = await client.get(endpoint_url, params=params)
    resp.raise_for_status()
    data = resp.json()

    items, total_count = _parse_response(data)
    if total_count == 0:
        return []

    all_items = list(items)
    num_of_rows = int(params.get("numOfRows", 100))
    total_pages = math.ceil(total_count / num_of_rows)

    for page in range(2, total_pages + 1):
        await asyncio.sleep(REQUEST_DELAY)
        params["pageNo"] = page
        resp = await client.get(endpoint_url, params=params)
        resp.raise_for_status()
        data = resp.json()
        page_items, _ = _parse_response(data)
        all_items.extend(page_items)

    return all_items


async def fetch_single(
    client: httpx.AsyncClient,
    endpoint_url: str,
    extra_params: dict | None = None,
) -> list[dict]:
    """단일 페이지만 조회하여 items를 반환한다."""
    params = _build_params(extra_params)
    resp = await client.get(endpoint_url, params=params)
    resp.raise_for_status()
    data = resp.json()
    items, _ = _parse_response(data)
    return items


def save_raw(data: list[dict], category: str, lang: str, filename: str) -> Path:
    """원본 API 응답 데이터를 raw/ 디렉토리에 JSON으로 저장한다."""
    out_dir = RAW_DIR / category / lang
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{filename}.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def load_raw(category: str, lang: str, filename: str) -> list[dict]:
    """raw/ 디렉토리에서 저장된 JSON 데이터를 로드한다."""
    path = RAW_DIR / category / lang / f"{filename}.json"
    if not path.exists():
        raise FileNotFoundError(f"Raw data not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def create_client() -> httpx.AsyncClient:
    """타임아웃이 설정된 httpx AsyncClient를 생성한다."""
    return httpx.AsyncClient(timeout=httpx.Timeout(30.0))
