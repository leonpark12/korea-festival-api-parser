"""행사정보조회 (searchFestival2 기반)."""

import asyncio
from datetime import date, datetime, timedelta

from src.client import create_client, fetch_all_pages
from src.config import ENDPOINTS, REQUEST_DELAY
from src.fetchers.detail_update import fetch_detail_for_poi
from src.transformers.pois import (
    EXCLUDE_LCLS3_EN,
    EXCLUDE_LCLS3_KR,
    build_category_map,
    transform_item,
)
from src.transformers.pois_detail import merge_detail_to_poi


async def fetch_festival(
    event_start_date: str | None = None,
    event_end_date: str | None = None,
) -> tuple[dict[str, list[dict]], list[dict]]:
    """행사/축제 정보를 수신하고 변환 + 상세 병합을 수행한다.

    Args:
        event_start_date: 행사 시작일 (YYYYMMDD). 기본값: 2일 전
        event_end_date: 행사 종료일 (YYYYMMDD). 기본값: 30일 후

    Returns:
        (festival_result, summaries)
        - festival_result: {"kr": [완성된 POI 목록], "en": [...]}
        - summaries: [{"contentId", "name", "region", "action", "lang", "syncDate"}]
    """
    # 날짜 기본값 계산
    today = date.today()
    if event_start_date is None:
        event_start_date = (today - timedelta(days=2)).strftime("%Y%m%d")
    if event_end_date is None:
        event_end_date = (today + timedelta(days=30)).strftime("%Y%m%d")

    category_map = build_category_map()
    sync_date = datetime.now().isoformat(timespec="seconds")

    festival_result: dict[str, list[dict]] = {"kr": [], "en": []}
    summaries: list[dict] = []

    print("=" * 50)
    print(f"행사정보조회 (eventStartDate={event_start_date}, eventEndDate={event_end_date})")
    print("=" * 50)

    async with create_client() as client:
        for lang in ("kr", "en"):
            lang_key = "ko" if lang == "kr" else "en"
            endpoint = ENDPOINTS["search_festival"][lang]

            # 1. searchFestival2 전체 페이지 수신 (최대 5회 재시도)
            print(f"\n[{lang}] searchFestival2 수신 중...")
            max_retries = 5
            items = None
            for attempt in range(1, max_retries + 1):
                try:
                    print(f"[{lang}] API 호출 시도 {attempt}/{max_retries}...")
                    items = await fetch_all_pages(
                        client, endpoint, {
                            "eventStartDate": event_start_date,
                            "eventEndDate": event_end_date,
                        }
                    )
                    break
                except Exception as e:
                    print(f"[{lang}] API 호출 실패 (시도 {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        print(f"[{lang}] 5초 후 재시도...")
                        await asyncio.sleep(5)

            if items is None:
                print(f"[{lang}] {max_retries}회 시도 모두 실패, 스킵합니다.")
                continue

            if not items:
                print(f"[{lang}] 행사 정보 없음")
                continue

            print(f"[{lang}] 수신 완료: {len(items)}건")

            # 2. 제외 카테고리 필터링
            exclude_codes = EXCLUDE_LCLS3_KR if lang == "kr" else EXCLUDE_LCLS3_EN
            filtered_items = [
                item for item in items
                if item.get("lclsSystm3", "") not in exclude_codes
            ]
            excluded_count = len(items) - len(filtered_items)
            if excluded_count > 0:
                from collections import Counter
                excluded_dist = Counter(
                    item.get("lclsSystm3", "")
                    for item in items
                    if item.get("lclsSystm3", "") in exclude_codes
                )
                top_codes = ", ".join(f"{c}({n}건)" for c, n in excluded_dist.most_common(5))
                print(f"[{lang}] 제외 카테고리 필터링: {excluded_count}건 제외 (주요: {top_codes})")

            if not filtered_items:
                print(f"[{lang}] 필터링 후 행사 대상 없음")
                continue

            # 3. 변환 + 상세 수신
            festival_pois: list[dict] = []
            for idx, item in enumerate(filtered_items, 1):
                content_id = item.get("contentid", "")
                title = item.get("title", "")
                print(f"  [{lang}] ({idx}/{len(filtered_items)}) contentId={content_id} — {title}")

                # transform_item으로 POI 변환
                poi = transform_item(item, lang_key, category_map)

                # 상세 API 호출
                await asyncio.sleep(REQUEST_DELAY)
                common, intro_items, info_items, image_items, pet_item, had_exception = (
                    await fetch_detail_for_poi(client, lang, poi, save_raw_data=False)
                )

                # 상세 병합
                updated_poi = merge_detail_to_poi(
                    poi, common, intro_items, info_items, image_items, pet_item
                )
                # kr에서 pet API 호출 후 플래그 미설정 시 보정
                if lang == "kr" and "detailPetUpdated" not in updated_poi:
                    updated_poi["detailPetUpdated"] = True

                festival_pois.append(updated_poi)

                # 요약 기록 생성
                summaries.append({
                    "contentId": content_id,
                    "name": title,
                    "region": poi.get("region", ""),
                    "action": "festival_updated",
                    "lang": lang,
                    "syncDate": sync_date,
                })

            festival_result[lang] = festival_pois
            print(f"[{lang}] 행사정보 완료: {len(festival_pois)}건")

    print("=" * 50)
    print(f"행사정보조회 완료 — kr={len(festival_result['kr'])}건, en={len(festival_result['en'])}건")
    print("=" * 50)

    return festival_result, summaries
