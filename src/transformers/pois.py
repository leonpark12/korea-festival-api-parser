"""관광정보 → pois_{lang}.json + pois_geo_{lang}.json 변환"""

import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"

# lDongRegnCd → app slug 매핑
REGION_CODE_MAP = {
    "11": "seoul",
    "26": "busan",
    "27": "daegu",
    "28": "incheon",
    "29": "gwangju",
    "30": "daejeon",
    "31": "ulsan",
    "36110": "sejong",
    "41": "gyeonggi",
    "43": "chungbuk",
    "44": "chungnam",
    "46": "jeonnam",
    "47": "gyeongbuk",
    "48": "gyeongnam",
    "50": "jeju",
    "51": "gangwon",
    "52": "jeonbuk",
}

# lclsSystm3 코드 기반 제외 필터 (kr/en 각각 별도 설정 가능)
EXCLUDE_LCLS3_KR: list[str] = ["SH040300", "FD010100", "AC030300", "AC030400", "AC040100", "AC050100", "AC050200", "AC050300", "AC050400", "AC060100", "EX060100", "EX060200", "EX060300", "EX060400", "EX060500", "EX060600", "EX060700", "EX060800", "EX060900", "EX061000", "FD030100", "FD030200", "FD030300", "FD030400", "FD030500", "FD030600", "FD040100", "FD040200", "FD040300", "FD040400", "FD040500", "FD050100", "FD050200", "FD050300", "NA010500", "NA020100", "NA020200", "NA020300", "NA020400", "NA020500", "NA020600", "NA020700", "SH050100", "SH050200", "VE010300", "VE010400", "VE010500", "VE010600", "VE010700", "VE010800", "VE010900", "VE030100", "VE030200", "VE030300", "VE030400", "VE030500", "VE060200", "VE080600", "VE090100", "VE090200", "VE090300", "VE090400", "VE090500", "VE090600", "VE100100", "VE100200", "VE110100", "VE110200", "VE110300", "VE110400", "VE110500", "VE110600", "VE120100", "VE120200", "VE120300"]  # 예: ["SH040300", "FD010100"]
EXCLUDE_LCLS3_EN: list[str] = ["SH040300", "FD010100", "AC030300", "AC030400", "AC040100", "AC050100", "AC050200", "AC050300", "AC050400", "AC060100", "EX060100", "EX060200", "EX060300", "EX060400", "EX060500", "EX060600", "EX060700", "EX060800", "EX060900", "EX061000", "FD030100", "FD030200", "FD030300", "FD030400", "FD030500", "FD030600", "FD040100", "FD040200", "FD040300", "FD040400", "FD040500", "FD050100", "FD050200", "FD050300", "NA010500", "NA020100", "NA020200", "NA020300", "NA020400", "NA020500", "NA020600", "NA020700", "SH050100", "SH050200", "VE010300", "VE010400", "VE010500", "VE010600", "VE010700", "VE010800", "VE010900", "VE030100", "VE030200", "VE030300", "VE030400", "VE030500", "VE060200", "VE080600", "VE090100", "VE090200", "VE090300", "VE090400", "VE090500", "VE090600", "VE100100", "VE100200", "VE110100", "VE110200", "VE110300", "VE110400", "VE110500", "VE110600", "VE120100", "VE120200", "VE120300"]  # 예: ["SH040300", "FD010100"]


def _build_category_map() -> dict[str, dict[str, str]]:
    """categories.json을 읽어 {code: {"ko": name, "en": name}} 딕셔너리 생성."""
    cat_path = OUTPUT_DIR / "categories.json"
    categories = json.loads(cat_path.read_text(encoding="utf-8"))

    cat_map: dict[str, dict[str, str]] = {}
    for top in categories:
        cat_map[top["code"]] = top["name"]
        for child in top.get("list", []):
            cat_map[child["code"]] = child["name"]
            for grandchild in child.get("list", []):
                cat_map[grandchild["code"]] = grandchild["name"]

    return cat_map


def _format_date(raw: str) -> str:
    """'20250312152659' → '2025-03-12'"""
    if not raw or len(raw) < 8:
        return ""
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def _transform_item(item: dict, lang: str, category_map: dict) -> dict:
    """단일 항목을 POI 포맷으로 변환한다.

    Args:
        item: area_based 원본 항목
        lang: "ko" 또는 "en"
        category_map: {code: {"ko": name, "en": name}}
    """
    content_id = item.get("contentid", "")

    # category: lclsSystm1 코드 → 언어별 name
    cat_code = item.get("lclsSystm1", "")
    category = category_map.get(cat_code, {}).get(lang, cat_code)

    # coordinates
    lat_str = item.get("mapy", "")
    lng_str = item.get("mapx", "")
    coordinates = {
        "lat": float(lat_str) if lat_str else 0.0,
        "lng": float(lng_str) if lng_str else 0.0,
    }

    # address: addr1 + addr2
    addr1 = item.get("addr1", "").strip()
    addr2 = item.get("addr2", "").strip()
    address = " ".join(filter(None, [addr1, addr2]))

    # region: lDongRegnCd → slug
    region = REGION_CODE_MAP.get(item.get("lDongRegnCd", ""), "")

    # images: 빈값 필터링
    images = [
        img
        for img in [item.get("firstimage", ""), item.get("firstimage2", "")]
        if img
    ]

    # tags: lclsSystm1, lclsSystm2, lclsSystm3 코드의 언어별 name (중복 제거)
    tags = []
    seen: set[str] = set()
    for key in ("lclsSystm1", "lclsSystm2", "lclsSystm3"):
        code = item.get(key, "")
        if code:
            name = category_map.get(code, {}).get(lang, "")
            if name and name not in seen:
                tags.append(name)
                seen.add(name)

    # source: 원본 데이터 추적용
    source = {
        "area": item.get("lDongRegnCd", ""),
        "lcls": [v for v in [item.get("lclsSystm1", ""), item.get("lclsSystm2", ""), item.get("lclsSystm3", "")] if v],
    }

    return {
        "id": content_id,
        "slug": content_id,
        "category": category,
        "coordinates": coordinates,
        "name": item.get("title", ""),
        "address": address,
        "description": item.get("title", ""),
        "region": region,
        "images": images,
        "contact": item.get("tel", ""),
        "website": "",
        "tags": tags,
        "updatedAt": _format_date(item.get("modifiedtime", "")),
        "source": source,
    }


def _to_geojson_feature(poi: dict) -> dict:
    """POI item → GeoJSON Feature 변환."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [poi["coordinates"]["lng"], poi["coordinates"]["lat"]],
        },
        "properties": {
            "id": poi["id"],
            "slug": poi["slug"],
            "category": poi["category"],
            "name": poi["name"],
            "region": poi["region"],
        },
    }


def transform_pois() -> dict[str, dict]:
    """area_based_{lang}.json → pois/geojson 변환.

    Returns:
        {"kr": {"pois": [...], "geojson": {...}}, "en": {...}}
    """
    category_map = _build_category_map()

    result: dict[str, dict] = {}
    for lang in ("kr", "en"):
        lang_key = "ko" if lang == "kr" else "en"

        data_path = OUTPUT_DIR / f"area_based_{lang}.json"
        if not data_path.exists():
            print(f"[Transform] {data_path} 파일 없음, 건너뜀")
            continue

        items = json.loads(data_path.read_text(encoding="utf-8"))

        exclude_codes = EXCLUDE_LCLS3_KR if lang == "kr" else EXCLUDE_LCLS3_EN
        pois = []
        excluded = []
        for item in items:
            transformed = _transform_item(item, lang_key, category_map)
            if item.get("lclsSystm3", "") in exclude_codes:
                excluded.append(transformed)
            else:
                pois.append(transformed)

        geojson = {
            "type": "FeatureCollection",
            "features": [_to_geojson_feature(poi) for poi in pois],
        }

        result[lang] = {"pois": pois, "geojson": geojson, "excluded": excluded}

    return result


def save_pois(data: dict[str, dict]) -> list[Path]:
    """변환된 데이터를 output/pois_{lang}.json, pois_geo_{lang}.json으로 저장.

    제외된 항목은 pois_exclude_{lang}.json으로 별도 저장 (DB 미입력).
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    for lang, content in data.items():
        pois_path = OUTPUT_DIR / f"pois_{lang}.json"
        pois_path.write_text(
            json.dumps(content["pois"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        saved.append(pois_path)

        geo_path = OUTPUT_DIR / f"pois_geo_{lang}.json"
        geo_path.write_text(
            json.dumps(content["geojson"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        saved.append(geo_path)

        excluded = content.get("excluded", [])
        if excluded:
            exclude_path = OUTPUT_DIR / f"pois_exclude_{lang}.json"
            exclude_path.write_text(
                json.dumps(excluded, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            saved.append(exclude_path)

    return saved
