import json
from pathlib import Path

from src.client import load_raw

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"

# 법정동 코드 → region slug 매핑 (API 실제 반환 코드 기준)
REGION_CODE_MAP = {
    "11": "seoul",
    "26": "busan",
    "27": "daegu",
    "28": "incheon",
    "29": "gwangju",
    "30": "daejeon",
    "31": "ulsan",
    "36110": "sejong",  # 세종특별자치시 (5자리 코드)
    "41": "gyeonggi",
    "43": "chungbuk",
    "44": "chungnam",
    "46": "jeonnam",
    "47": "gyeongbuk",
    "48": "gyeongnam",
    "50": "jeju",
    "51": "gangwon",  # 강원특별자치도 (신규 코드)
    "52": "jeonbuk",  # 전북특별자치도 (신규 코드)
}

# 한글 시/도 이름 → 짧은 이름 매핑
KR_SHORT_NAME = {
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "경기도": "경기",
    "강원특별자치도": "강원",
    "충청북도": "충북",
    "충청남도": "충남",
    "전북특별자치도": "전북",
    "전라남도": "전남",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주특별자치도": "제주",
}


def transform_regions(ldong_data: dict | None = None) -> list[dict]:
    """법정동 1-depth 데이터를 regions.json 포맷으로 변환한다.

    Args:
        ldong_data: fetch_ldong_code()의 반환값. None이면 raw에서 로드.

    Returns:
        [{"code": "seoul", "name": {"ko": "서울", "en": "Seoul"}}, ...]
    """
    if ldong_data is None:
        kr_depth1 = load_raw("ldong_code", "kr", "depth1")
        en_depth1 = load_raw("ldong_code", "en", "depth1")
    else:
        kr_depth1 = ldong_data["kr"]["depth1"]
        en_depth1 = ldong_data["en"]["depth1"]

    # 영문 이름 매핑: code -> name
    en_name_map: dict[str, str] = {}
    for item in en_depth1:
        code = item.get("lDongRegnCd", item.get("code", ""))
        name = item.get("lDongRegnNm", item.get("name", ""))
        if code and name:
            en_name_map[code] = name

    regions = []
    for item in kr_depth1:
        code = item.get("lDongRegnCd", item.get("code", ""))
        kr_name = item.get("lDongRegnNm", item.get("name", ""))

        if code not in REGION_CODE_MAP:
            continue

        slug = REGION_CODE_MAP[code]
        short_kr = KR_SHORT_NAME.get(kr_name, kr_name)
        en_name = en_name_map.get(code, slug.capitalize())

        regions.append({
            "code": slug,
            "name": {
                "ko": short_kr,
                "en": en_name,
            },
        })

    return regions


def save_regions(regions: list[dict]) -> Path:
    """변환된 regions 데이터를 output/regions.json으로 저장한다."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "regions.json"
    out_path.write_text(
        json.dumps(regions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path
