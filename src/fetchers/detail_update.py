"""POI 상세 정보(detailCommon2, detailIntro2, detailInfo2) 수신 및 병합 로직."""

import asyncio
import json
from pathlib import Path

from src.client import create_client, fetch_single, save_raw
from src.config import DETAIL_UPDATE_MAX_POIS, ENDPOINTS, REQUEST_DELAY
from src.transformers.pois_detail import merge_detail_to_poi

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"

# 중간 저장 주기 (건)
CHECKPOINT_INTERVAL = 50


def _load_pois(lang: str) -> list[dict]:
    """output/pois_{lang}.json에서 전체 POI 목록을 로드한다."""
    path = OUTPUT_DIR / f"pois_{lang}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _load_details(lang: str) -> list[dict]:
    """output/pois_details_{lang}.json에서 기존 업데이트 결과를 로드한다."""
    path = OUTPUT_DIR / f"pois_details_{lang}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_details(lang: str, details: list[dict]) -> Path:
    """업데이트된 POI 목록을 output/pois_details_{lang}.json으로 저장한다."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"pois_details_{lang}.json"
    path.write_text(
        json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def _filter_pending_pois(
    all_pois: list[dict],
    existing_details: list[dict],
    region: str | None,
    limit: int,
    lang: str = "kr",
    force: bool = False,
) -> list[dict]:
    """업데이트가 필요한 POI만 필터링한다.

    Args:
        all_pois: 전체 POI 목록
        existing_details: 이미 업데이트된 POI 목록
        region: 지역 slug 필터 (None이면 전체)
        limit: 최대 처리 건수
        lang: 언어 코드 (kr/en) — kr일 때만 detailPetUpdated 체크
        force: True이면 완료 체크를 무시하고 모든 POI를 재수신 대상으로 포함

    Returns:
        업데이트가 필요한 POI 목록 (limit개 이하)
    """
    # force 모드일 때는 완료 체크 무시
    if force:
        updated_ids: set[str] = set()
    else:
        # 이미 업데이트된 ID 집합
        # kr: detailUpdatedAt + intro + info + detailImageUpdated + detailPetUpdated 모두 존재해야 스킵
        # en: detailUpdatedAt + intro + info + detailImageUpdated 있으면 스킵 (pet 미지원)
        def _is_complete(d: dict) -> bool:
            base = d.get("detailUpdatedAt") and "intro" in d and "info" in d and d.get("detailImageUpdated")
            if not base:
                return False
            if lang == "kr":
                return bool(d.get("detailPetUpdated"))
            return True

        updated_ids = {
            d["id"]
            for d in existing_details
            if _is_complete(d)
        }

    pending = []
    for poi in all_pois:
        # intro와 info가 모두 있는 POI만 스킵
        if poi["id"] in updated_ids:
            continue
        # 지역 필터 적용
        if region and poi.get("region") != region:
            continue
        pending.append(poi)
        if len(pending) >= limit:
            break

    return pending


def _print_progress(lang: str, total: int, done: int, batch: int) -> None:
    """진행 상황을 출력한다."""
    remaining = total - done
    print(
        f"[{lang}] 전체: {total:,}건 | "
        f"완료: {done:,}건 | "
        f"남은: {remaining:,}건 | "
        f"이번 처리: {batch:,}건"
    )


async def _fetch_detail_for_poi(
    client,
    lang: str,
    poi: dict,
) -> tuple[dict | None, list[dict] | None, list[dict] | None, list[dict] | None, dict | None]:
    """단일 POI에 대해 detailCommon2, detailIntro2, detailInfo2, detailImage2, detailPetTour2를 호출한다.

    Returns:
        (common_item, intro_items, info_items, image_items, pet_item) — 각각 API 응답 또는 None
    """
    content_id = poi["id"]
    content_type_id = poi.get("source", {}).get("contentTypeId", "")

    common_item = None
    intro_items = None
    info_items = None
    image_items = None
    pet_item = None

    # detailCommon2 호출 (공통 파라미터 + contentId만 사용)
    try:
        url = ENDPOINTS["detail_common"][lang]
        items = await fetch_single(
            client,
            url,
            {"contentId": content_id},
        )
        if items:
            common_item = items[0]
            save_raw(items, "detail_common", lang, content_id)
    except Exception as e:
        print(f"    [경고] detailCommon2 호출 실패 (contentId={content_id}): {e}")

    await asyncio.sleep(REQUEST_DELAY)

    # detailIntro2 호출 (전체 배열 반환)
    try:
        url = ENDPOINTS["detail_intro"][lang]
        params = {"contentId": content_id}
        if content_type_id:
            params["contentTypeId"] = content_type_id
        items = await fetch_single(client, url, params)
        if items:
            intro_items = items
            save_raw(items, "detail_intro", lang, content_id)
    except Exception as e:
        print(f"    [경고] detailIntro2 호출 실패 (contentId={content_id}): {e}")

    await asyncio.sleep(REQUEST_DELAY)

    # detailInfo2 호출 (반복정보, 전체 배열 반환)
    try:
        url = ENDPOINTS["detail_info"][lang]
        params = {"contentId": content_id}
        if content_type_id:
            params["contentTypeId"] = content_type_id
        items = await fetch_single(client, url, params)
        if items:
            info_items = items
            save_raw(items, "detail_info", lang, content_id)
    except Exception as e:
        print(f"    [경고] detailInfo2 호출 실패 (contentId={content_id}): {e}")

    await asyncio.sleep(REQUEST_DELAY)

    # detailImage2 호출 (이미지 목록, contentId만 전달)
    try:
        url = ENDPOINTS["detail_image"][lang]
        items = await fetch_single(
            client,
            url,
            {"contentId": content_id},
        )
        if items:
            image_items = items
            save_raw(items, "detail_image", lang, content_id)
    except Exception as e:
        print(f"    [경고] detailImage2 호출 실패 (contentId={content_id}): {e}")

    # detailPetTour2 호출 (반려동물 정보, 한글(kr)만 지원, 첫 번째 항목만 추출)
    if lang in ENDPOINTS.get("detail_pet", {}):
        await asyncio.sleep(REQUEST_DELAY)
        try:
            url = ENDPOINTS["detail_pet"][lang]
            items = await fetch_single(
                client,
                url,
                {"contentId": content_id},
            )
            if items:
                pet_item = items[0]
                save_raw(items, "detail_pet", lang, content_id)
        except Exception as e:
            print(f"    [경고] detailPetTour2 호출 실패 (contentId={content_id}): {e}")

    return common_item, intro_items, info_items, image_items, pet_item


async def fetch_detail_update(
    region: str | None = None,
    limit: int = DETAIL_UPDATE_MAX_POIS,
    force: bool = False,
) -> dict[str, list[dict]]:
    """POI 상세 정보를 수신하여 기존 POI에 병합한다.

    Args:
        region: 지역 slug 필터 (None이면 전체)
        limit: 각 언어당 최대 처리 건수

    Returns:
        {"kr": [업데이트된 POI 목록], "en": [...]}
    """
    result: dict[str, list[dict]] = {}

    print("=" * 50)
    print("POI 상세 업데이트 진행 상황")
    print("=" * 50)

    async with create_client() as client:
        for lang in ("kr", "en"):
            all_pois = _load_pois(lang)
            if not all_pois:
                print(f"[{lang}] pois_{lang}.json 파일 없음, 건너뜀")
                continue

            existing_details = _load_details(lang)
            # 기존 업데이트 결과를 딕셔너리로 변환 (빠른 조회용)
            details_map = {d["id"]: d for d in existing_details}

            # 지역 필터 적용한 전체 대상 수 (진행 상황 표시용)
            if region:
                total_target = len(
                    [p for p in all_pois if p.get("region") == region]
                )
            else:
                total_target = len(all_pois)

            done_count = len(
                [d for d in existing_details if d.get("detailUpdatedAt")]
            )

            # 미처리 POI 필터링
            pending = _filter_pending_pois(
                all_pois, existing_details, region, limit, lang, force
            )

            _print_progress(lang, total_target, done_count, len(pending))

            if not pending:
                print(f"[{lang}] 모든 POI가 이미 업데이트 완료됨")
                result[lang] = []
                continue

            success_count = 0
            newly_updated = []  # 새로 업데이트한 POI만 추적
            for idx, poi in enumerate(pending, 1):
                print(
                    f"  [{lang}] ({idx}/{len(pending)}) "
                    f"contentId={poi['id']} — {poi.get('name', '')}"
                )

                await asyncio.sleep(REQUEST_DELAY)
                common, intro_items, info_items, image_items, pet_item = await _fetch_detail_for_poi(
                    client, lang, poi
                )

                # 모두 실패한 경우 스킵
                if common is None and intro_items is None and info_items is None and image_items is None and pet_item is None:
                    print(f"    → 스킵 (API 응답 없음)")
                    continue

                # 병합
                # 기존 상세 데이터가 있으면 그것을 기반으로 병합 (--force 재수신 시 기존 데이터 보존)
                base_poi = details_map.get(poi["id"], poi)
                updated_poi = merge_detail_to_poi(
                    base_poi, common, intro_items, info_items, image_items, pet_item
                )
                details_map[updated_poi["id"]] = updated_poi
                newly_updated.append(updated_poi)
                success_count += 1

                # 중간 저장 (checkpoint)
                if success_count % CHECKPOINT_INTERVAL == 0:
                    checkpoint_list = list(details_map.values())
                    _save_details(lang, checkpoint_list)
                    print(
                        f"    [체크포인트] {success_count}건 중간 저장 완료"
                    )

            # 최종 저장
            final_list = list(details_map.values())
            path = _save_details(lang, final_list)
            result[lang] = newly_updated  # 새로 업데이트한 POI만 반환
            print(
                f"[{lang}] 완료: {success_count}건 업데이트, "
                f"총 {len(final_list)}건 저장 → {path}"
            )

    print("=" * 50)
    return result
