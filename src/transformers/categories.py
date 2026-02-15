import json
from pathlib import Path

from src.client import load_raw

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"


def _build_tree_from_raw() -> dict:
    """raw 디렉토리의 분류체계 데이터를 로드하여 트리를 구성한다."""
    kr_depth1 = load_raw("category_code", "kr", "depth1")
    en_depth1 = load_raw("category_code", "en", "depth1")

    tree: dict = {"kr": {}, "en": {}}

    # kr depth1
    for item in kr_depth1:
        code = item.get("lclsSystmCode", item.get("code", ""))
        name = item.get("lclsSystmNm", item.get("name", ""))
        tree["kr"][code] = {"code": code, "name": name, "children": {}}

    # en depth1
    for item in en_depth1:
        code = item.get("lclsSystmCode", item.get("code", ""))
        name = item.get("lclsSystmNm", item.get("name", ""))
        tree["en"][code] = {"code": code, "name": name, "children": {}}

    # depth2 로드
    for cat1_code in tree["kr"]:
        for lang in ("kr", "en"):
            try:
                depth2 = load_raw("category_code", lang, f"depth2_{cat1_code}")
            except FileNotFoundError:
                continue
            for item in depth2:
                code = item.get("lclsSystmCode", item.get("code", ""))
                name = item.get("lclsSystmNm", item.get("name", ""))
                tree[lang][cat1_code]["children"][code] = {
                    "code": code,
                    "name": name,
                    "children": {},
                }

    # depth3 로드
    for cat1_code in tree["kr"]:
        for cat2_code in tree["kr"][cat1_code]["children"]:
            for lang in ("kr", "en"):
                try:
                    depth3 = load_raw("category_code", lang, f"depth3_{cat2_code}")
                except FileNotFoundError:
                    continue
                cat2_node = tree[lang].get(cat1_code, {}).get("children", {}).get(cat2_code)
                if not cat2_node:
                    continue
                for item in depth3:
                    code = item.get("lclsSystmCode", item.get("code", ""))
                    name = item.get("lclsSystmNm", item.get("name", ""))
                    cat2_node["children"][code] = {
                        "code": code,
                        "name": name,
                    }

    return tree


def _build_tree_from_data(cat_data: dict) -> dict:
    """fetch_category_code()의 반환값으로 트리를 구성한다."""
    tree: dict = {"kr": {}, "en": {}}

    for lang in ("kr", "en"):
        data = cat_data[lang]
        for item in data["depth1"]:
            code = item.get("lclsSystmCode", item.get("code", ""))
            name = item.get("lclsSystmNm", item.get("name", ""))
            tree[lang][code] = {"code": code, "name": name, "children": {}}

        for cat1_code, items in data["depth2"].items():
            if cat1_code not in tree[lang]:
                continue
            for item in items:
                code = item.get("lclsSystmCode", item.get("code", ""))
                name = item.get("lclsSystmNm", item.get("name", ""))
                tree[lang][cat1_code]["children"][code] = {
                    "code": code,
                    "name": name,
                    "children": {},
                }

        for cat2_code, items in data.get("depth3", {}).items():
            # cat2_code가 속하는 cat1을 찾는다
            for cat1_code, cat1_node in tree[lang].items():
                if cat2_code in cat1_node["children"]:
                    for item in items:
                        code = item.get("lclsSystmCode", item.get("code", ""))
                        name = item.get("lclsSystmNm", item.get("name", ""))
                        cat1_node["children"][cat2_code]["children"][code] = {
                            "code": code,
                            "name": name,
                        }
                    break

    return tree


def transform_categories(cat_data: dict | None = None) -> list[dict]:
    """분류체계 데이터를 categories.json 포맷으로 변환한다.

    Args:
        cat_data: fetch_category_code()의 반환값. None이면 raw에서 로드.

    Returns:
        [
            {
                "code": "XX",
                "name": {"ko": "...", "en": "..."},
                "list": [...]
            }, ...
        ]
    """
    if cat_data is None:
        tree = _build_tree_from_raw()
    else:
        tree = _build_tree_from_data(cat_data)

    # kr/en 트리를 병합하여 다국어 구조로 변환
    return _merge_trees(tree["kr"], tree["en"])


def _merge_trees(kr_tree: dict, en_tree: dict) -> list[dict]:
    """kr/en 트리를 code 기준으로 병합한다."""
    merged: list[dict] = []
    for code in kr_tree:
        kr_node = kr_tree[code]
        en_node = en_tree.get(code, {})

        node: dict = {
            "code": code,
            "name": {
                "ko": kr_node.get("name", ""),
                "en": en_node.get("name", code),
            },
        }

        kr_children = kr_node.get("children", {})
        en_children = en_node.get("children", {})
        if kr_children:
            node["list"] = _merge_trees(kr_children, en_children)

        merged.append(node)

    return merged


def save_categories(categories: dict) -> Path:
    """변환된 categories 데이터를 output/categories.json으로 저장한다."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "categories.json"
    out_path.write_text(
        json.dumps(categories, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path
