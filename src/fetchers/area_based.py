import asyncio
import json
from pathlib import Path

import httpx

from src.client import create_client, fetch_all_pages, save_raw
from src.config import ENDPOINTS, REQUEST_DELAY

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"
CONTENT_TYPES_PATH = OUTPUT_DIR / "content-types.json"
REGIONS_PATH = OUTPUT_DIR / "regions.json"


def _load_content_types() -> list[dict]:
    return json.loads(CONTENT_TYPES_PATH.read_text(encoding="utf-8"))


def _load_regions() -> list[dict]:
    return json.loads(REGIONS_PATH.read_text(encoding="utf-8"))


def _get_content_type_ids(lang: str) -> list[str]:
    """언어별 사용 가능한 contentTypeId 목록을 반환한다."""
    content_types = _load_content_types()
    ids = []
    for ct in content_types:
        code = ct.get("code", {})
        if lang in code and code[lang]:
            ids.append(str(code[lang]))
    return ids


def _get_region_codes() -> list[str]:
    """API 조회용 법정동 숫자 코드 목록을 반환한다."""
    from src.transformers.regions import REGION_CODE_MAP

    return list(REGION_CODE_MAP.keys())


async def fetch_area_based() -> dict:
    """지역기반 관광정보를 contentTypeId × lDongRegnCd 조합으로 조회하여 저장한다.

    totalCount 기반으로 모든 페이지를 순회하여 전체 데이터를 다운받는다.
    raw: 각 호출 결과를 개별 파일로 저장 (raw/area_based/{lang}/ct{id}_rg{code}.json)
    output: area_based_kr.json, area_based_en.json

    Returns:
        {"kr": [...], "en": [...]}
    """
    region_codes = _get_region_codes()
    result: dict[str, list[dict]] = {"kr": [], "en": []}

    async with create_client() as client:
        for lang in ("kr", "en"):
            url = ENDPOINTS["area_based"][lang]
            content_type_ids = _get_content_type_ids(lang)
            total_combos = len(content_type_ids) * len(region_codes)
            count = 0

            for ct_id in content_type_ids:
                for region_code in region_codes:
                    count += 1
                    print(
                        f"  [{lang}] ({count}/{total_combos}) "
                        f"contentTypeId={ct_id}, lDongRegnCd={region_code}"
                    )
                    await asyncio.sleep(REQUEST_DELAY)
                    items = await fetch_all_pages(
                        client,
                        url,
                        {
                            "arrange": "A",
                            "contentTypeId": ct_id,
                            "lDongRegnCd": region_code,
                        },
                    )
                    print(f"    → {len(items)}건 수신")
                    # raw: 개별 파일로 저장
                    save_raw(items, "area_based", lang, f"ct{ct_id}_rg{region_code}")
                    result[lang].extend(items)

            print(f"  [{lang}] 총 {len(result[lang])}건 수신 완료")

    # output 저장
    _save_output(result)
    return result


def _save_output(data: dict[str, list[dict]]) -> None:
    """output 디렉토리에 area_based_kr.json, area_based_en.json으로 저장한다."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for lang in ("kr", "en"):
        out_path = OUTPUT_DIR / f"area_based_{lang}.json"
        out_path.write_text(
            json.dumps(data[lang], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  [Output] {out_path} ({len(data[lang])}건)")
