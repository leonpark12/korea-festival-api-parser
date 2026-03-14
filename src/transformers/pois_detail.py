"""detailCommon2/detailIntro2/detailInfo2 API 응답을 기존 POI에 병합하는 변환 로직."""

import re
from datetime import date


def _strip_html(text: str) -> str:
    """HTML 태그를 제거한다."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def _normalize_url(url: str) -> str:
    """이미지 URL을 https로 정규화한다."""
    if url.startswith("http://"):
        return "https://" + url[7:]
    return url


def _clean_item(item: dict) -> dict:
    """API 응답 항목에서 불필요한 필드를 제거하고 빈 값을 필터링한다."""
    cleaned = dict(item)
    for key in ("contentid", "contenttypeid", "serialnum"):
        cleaned.pop(key, None)
    # 빈 값 필드 제거
    return {k: v for k, v in cleaned.items() if v}


def merge_detail_to_poi(
    poi: dict,
    common: dict | None,
    intro_items: list[dict] | None,
    info_items: list[dict] | None,
    image_items: list[dict] | None = None,
    pet_item: dict | None = None,
) -> dict:
    """detailCommon2/detailIntro2/detailInfo2/detailImage2/detailPetTour2 응답을 기존 POI 문서에 병합한다.

    Args:
        poi: 기존 POI 문서 (pois_{lang}.json의 항목)
        common: detailCommon2 API 응답 항목 (없으면 None)
        intro_items: detailIntro2 API 응답 항목 배열 (없으면 None)
        info_items: detailInfo2 API 응답 항목 배열 (없으면 None)
        image_items: detailImage2 API 응답 항목 배열 (없으면 None)
        pet_item: detailPetTour2 API 응답 첫 번째 항목 (없으면 None, 한글만 지원)

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

        # mlevel (정수 변환)
        mlevel = common.get("mlevel", "")
        if mlevel:
            try:
                updated["mlevel"] = int(mlevel)
            except (ValueError, TypeError):
                updated["mlevel"] = 0

        # 좌표 업데이트 (유효한 경우만)
        mapx = common.get("mapx", "")
        mapy = common.get("mapy", "")
        if mapx and mapy and mapx != "null" and mapy != "null":
            try:
                lng = float(mapx)
                lat = float(mapy)
                if lng != 0.0 and lat != 0.0:
                    updated["coordinates"] = {"lat": lat, "lng": lng}
                    updated["location"] = {
                        "type": "Point",
                        "coordinates": [lng, lat],
                    }
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

    # detailImage2 → images 배열 + thumbnail
    if image_items:
        images = [
            _normalize_url(item.get("originimgurl", ""))
            for item in image_items
            if item.get("originimgurl")
        ]
        if images:
            updated["images"] = images
        # 첫 번째 smallimageurl → thumbnail
        first_small = image_items[0].get("smallimageurl", "")
        if first_small:
            updated["thumbnail"] = _normalize_url(first_small)
    # API 호출 완료 표시 (이미지가 없는 POI도 완료로 처리)
    updated["detailImageUpdated"] = True

    # detailPetTour2 → pet (단일 객체, 한글만 지원)
    if pet_item is not None:
        cleaned = _clean_item(pet_item)
        if cleaned:
            updated["pet"] = cleaned
        updated["detailPetUpdated"] = True

    # 업데이트 완료 표시 (스킵 판별용)
    updated["detailUpdatedAt"] = date.today().isoformat()

    return updated
