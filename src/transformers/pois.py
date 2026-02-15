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


def _build_category_map() -> dict[str, dict[str, str]]:
    """categories.json을 읽어 {code: {"ko": name, "en": name}} 딕셔너리 생성."""
    cat_path = OUTPUT_DIR / "categories.json"
    categories = json.loads(cat_path.read_text(encoding="utf-8"))

    cat_map: dict[str, dict[str, str]] = {}
    for top in categories:
        cat_map[top["code"]] = top["name"]
        for child in top.get("list", []):
            cat_map[child["code"]] = child["name"]

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

    # tags: lclsSystm1, lclsSystm2 코드의 언어별 name
    tags = []
    for key in ("lclsSystm1", "lclsSystm2"):
        code = item.get(key, "")
        if code:
            name = category_map.get(code, {}).get(lang, "")
            if name:
                tags.append(name)

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

        pois = [_transform_item(item, lang_key, category_map) for item in items]

        geojson = {
            "type": "FeatureCollection",
            "features": [_to_geojson_feature(poi) for poi in pois],
        }

        result[lang] = {"pois": pois, "geojson": geojson}

    return result


def save_pois(data: dict[str, dict]) -> list[Path]:
    """변환된 데이터를 output/pois_{lang}.json, pois_geo_{lang}.json으로 저장."""
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

    return saved
