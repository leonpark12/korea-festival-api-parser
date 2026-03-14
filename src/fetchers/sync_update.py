"""관광정보 증분 동기화 (areaBasedSyncList2 기반)."""

import asyncio
import json
from datetime import datetime
from pathlib import Path


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

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"


def _classify_by_showflag(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """showflag 값으로 업데이트/삭제 대상을 분류한다.

    Returns:
        (update_items, delete_items)
        - update_items: showflag가 0이 아닌 항목 (업데이트 대상)
        - delete_items: showflag가 0인 항목 (삭제 대상)
    """
    update_items = []
    delete_items = []

    for item in items:
        showflag = str(item.get("showflag", "1"))
        if showflag == "0":
            delete_items.append(item)
        else:
            update_items.append(item)

    return update_items, delete_items


def _remove_from_output(lang: str, delete_ids: set[str]) -> int:
    """output/pois_{lang}.json에서 삭제 대상 POI를 제거한다.

    Returns:
        제거된 건수
    """
    path = OUTPUT_DIR / f"pois_{lang}.json"
    if not path.exists():
        return 0

    pois = json.loads(path.read_text(encoding="utf-8"))
    filtered = [p for p in pois if p["id"] not in delete_ids]
    removed = len(pois) - len(filtered)

    if removed > 0:
        path.write_text(
            json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[{lang}] pois_{lang}.json에서 {removed}건 삭제")

    return removed


async def fetch_sync_update(modifiedtime: str) -> tuple[dict, dict, list]:
    """수정된 관광정보를 수신하고 변환/상세 업데이트를 수행한다.

    Args:
        modifiedtime: YYYYMMDD 형식 문자열

    Returns:
        (upserted_result, deleted_result, summaries)
        - upserted_result: {"kr": [완성된 POI 목록], "en": [...]}
        - deleted_result: {"kr": [삭제 ID 목록], "en": [...]}
        - summaries: [{"contentId", "name", "region", "action", "lang", "syncDate"}]
    """
    category_map = build_category_map()
    sync_date = datetime.now().isoformat(timespec="seconds")

    upserted_result: dict[str, list[dict]] = {"kr": [], "en": []}
    deleted_result: dict[str, list[str]] = {"kr": [], "en": []}
    summaries: list[dict] = []

    print("=" * 50)
    print(f"관광정보 동기화 (modifiedtime={modifiedtime})")
    print("=" * 50)

    async with create_client() as client:
        for lang in ("kr", "en"):
            lang_key = "ko" if lang == "kr" else "en"
            endpoint = ENDPOINTS["area_based_sync"][lang]

            # 1. areaBasedSyncList2 전체 페이지 수신 (최대 5회 재시도)
            print(f"\n[{lang}] areaBasedSyncList2 수신 중 (modifiedtime={modifiedtime})...")
            max_retries = 5
            items = None
            for attempt in range(1, max_retries + 1):
                try:
                    print(f"[{lang}] API 호출 시도 {attempt}/{max_retries}...")
                    items = await fetch_all_pages(
                        client, endpoint, {"modifiedtime": modifiedtime}
                    )
                    break
                except Exception as e:
                    print(f"[{lang}] API 호출 실패 (시도 {attempt}/{max_retries}): {e}")
                    if attempt < max_retries:
                        print(f"[{lang}] {5}초 후 재시도...")
                        await asyncio.sleep(5)

            if items is None:
                print(f"[{lang}] {max_retries}회 시도 모두 실패, 스킵합니다.")
                continue

            if not items:
                print(f"[{lang}] 수정된 항목 없음")
                continue

            print(f"[{lang}] 수신 완료: {len(items)}건")

            # 2. showflag 분류
            update_items, delete_items = _classify_by_showflag(items)
            print(f"[{lang}] 업데이트: {len(update_items)}건, 삭제: {len(delete_items)}건")

            # 3-a. 삭제 대상 처리
            if delete_items:
                delete_ids = [item.get("contentid", "") for item in delete_items]
                deleted_result[lang] = delete_ids

                # output 파일에서 제거
                _remove_from_output(lang, set(delete_ids))

                # 삭제 요약 기록
                for item in delete_items:
                    summaries.append({
                        "contentId": item.get("contentid", ""),
                        "name": item.get("title", ""),
                        "region": "",
                        "action": "deleted",
                        "lang": lang,
                        "syncDate": sync_date,
                    })

            # 3-b. 업데이트 대상 처리
            if not update_items:
                continue

            # 제외 카테고리 필터링
            exclude_codes = EXCLUDE_LCLS3_KR if lang == "kr" else EXCLUDE_LCLS3_EN
            filtered_items = [
                item for item in update_items
                if item.get("lclsSystm3", "") not in exclude_codes
            ]
            excluded_count = len(update_items) - len(filtered_items)
            if excluded_count > 0:
                # 제외된 카테고리 분포를 요약하여 출력
                from collections import Counter
                excluded_dist = Counter(
                    item.get("lclsSystm3", "")
                    for item in update_items
                    if item.get("lclsSystm3", "") in exclude_codes
                )
                top_codes = ", ".join(f"{c}({n}건)" for c, n in excluded_dist.most_common(5))
                print(f"[{lang}] 제외 카테고리 필터링: {excluded_count}건 제외 (주요: {top_codes})")

            if not filtered_items:
                print(f"[{lang}] 필터링 후 업데이트 대상 없음 (수신 {len(update_items)}건 전부 제외 카테고리)")
                continue

            # 변환 + 상세 수신
            updated_pois: list[dict] = []
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

                updated_pois.append(updated_poi)

                # 업데이트 요약 기록
                summaries.append({
                    "contentId": content_id,
                    "name": title,
                    "region": poi.get("region", ""),
                    "action": "updated",
                    "lang": lang,
                    "syncDate": sync_date,
                })

            upserted_result[lang] = updated_pois
            print(f"[{lang}] 업데이트 완료: {len(updated_pois)}건")

    print("=" * 50)
    print(f"동기화 완료 — 업데이트: kr={len(upserted_result['kr'])}건, en={len(upserted_result['en'])}건 | "
          f"삭제: kr={len(deleted_result['kr'])}건, en={len(deleted_result['en'])}건")
    print("=" * 50)

    return upserted_result, deleted_result, summaries
