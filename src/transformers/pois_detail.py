"""detailCommon2/detailIntro2/detailInfo2 API 응답을 기존 POI에 병합하는 변환 로직."""

import re
from datetime import date


def _strip_html(text: str) -> str:
    """HTML 태그를 제거한다."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def _clean_item(item: dict) -> dict:
    """API 응답 항목에서 불필요한 필드를 제거하고 빈 값을 필터링한다."""
    cleaned = dict(item)
    for key in ("contentid", "contenttypeid"):
        cleaned.pop(key, None)
    # 빈 값 필드 제거
    return {k: v for k, v in cleaned.items() if v}


def merge_detail_to_poi(
    poi: dict,
    common: dict | None,
    intro_items: list[dict] | None,
    info_items: list[dict] | None,
) -> dict:
    """detailCommon2/detailIntro2/detailInfo2 응답을 기존 POI 문서에 병합한다.

    Args:
        poi: 기존 POI 문서 (pois_{lang}.json의 항목)
        common: detailCommon2 API 응답 항목 (없으면 None)
        intro_items: detailIntro2 API 응답 항목 배열 (없으면 None)
        info_items: detailInfo2 API 응답 항목 배열 (없으면 None)

    Returns:
        업데이트된 POI 문서 (원본을 복사하여 반환)
    """
    updated = dict(poi)

    # 기존 details 필드 제거 (intro로 대체)
    updated.pop("details", None)

    if common:
        # overview → description (비어있지 않을 때만)
        overview = common.get("overview", "")
        if overview:
            updated["description"] = overview

        # mlevel (신규 필드)
        mlevel = common.get("mlevel", "")
        if mlevel:
            updated["mlevel"] = mlevel

        # 좌표 업데이트 (유효한 경우만)
        mapx = common.get("mapx", "")
        mapy = common.get("mapy", "")
        if mapx and mapy and mapx != "null" and mapy != "null":
            try:
                lng = float(mapx)
                lat = float(mapy)
                if lng != 0.0 and lat != 0.0:
                    updated["coordinates"] = {"lat": lat, "lng": lng}
            except (ValueError, TypeError):
                pass

        # homepage → website (HTML 태그 제거)
        homepage = common.get("homepage", "")
        if homepage:
            updated["website"] = _strip_html(homepage)

        # tel → contact
        tel = common.get("tel", "")
        if tel:
            updated["contact"] = tel

    # detailIntro2 → intro (배열)
    if intro_items:
        updated["intro"] = [_clean_item(item) for item in intro_items]
    else:
        updated["intro"] = []

    # detailInfo2 → info (배열)
    if info_items:
        updated["info"] = [_clean_item(item) for item in info_items]
    else:
        updated["info"] = []

    # 업데이트 완료 표시 (스킵 판별용)
    updated["detailUpdatedAt"] = date.today().isoformat()

    return updated
