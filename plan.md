# categories.json 변환 로직 변경 이력

## 개요

`output/categories.json`의 출력 포맷을 객체 기반(`{"tree": {...}}`)에서 배열 기반(`[...]`)으로 전면 변경하고,
하드코딩된 허용 코드 필터를 제거하여 API depth1 수신 데이터가 출력을 결정하도록 개선하였다.

---

## Phase 1: depth3 로직 제거 (이전 작업)

### 문제

- API에 `lclsSystm2=AC01`로 depth3 조회 시, depth1 카테고리(AC, C01, EV...)가 반환됨
- 잘못된 depth3 데이터가 `tree.AC.children.AC01.children`에 그대로 포함됨

### 해결

| 대상 | 변경 내용 |
|------|-----------|
| `src/fetchers/category_code.py` | `fetch_depth3` 함수 및 호출부 제거, 반환 구조에서 `depth3` 키 제거 |
| `src/transformers/categories.py` | `_build_tree_from_raw`, `_build_tree_from_data`에서 depth3 관련 로직 제거 |
| `raw/category_code/` | `depth3_*.json` 파일 삭제 |

---

## Phase 2: 출력 포맷 변경 (배열화 + children -> list)

### 변경 전 포맷

```json
{
  "tree": {
    "AC": {
      "code": "AC",
      "name": {"ko": "숙박", "en": "Accommodation"},
      "children": {
        "AC01": {"code": "AC01", "name": {"ko": "호텔", "en": "Hotels"}},
        "AC02": {"code": "AC02", "name": {"ko": "콘도미니엄", "en": "Condominiums"}}
      }
    }
  }
}
```

### 변경 후 포맷

```json
[
  {
    "code": "AC",
    "name": {"ko": "숙박", "en": "Accommodation"},
    "list": [
      {"code": "AC01", "name": {"ko": "호텔", "en": "Hotels"}},
      {"code": "AC02", "name": {"ko": "콘도미니엄", "en": "Condominiums"}}
    ]
  }
]
```

### 변경 사항

#### 1. `src/transformers/categories.py`

##### `transform_categories()` (line 71)

- **반환 타입**: `dict` -> `list[dict]`
- **반환값**: `{"tree": merged}` -> `_merge_trees(...)` (배열 직접 반환)
- `{"tree": ...}` 래퍼 객체 제거

```python
# Before
def transform_categories(cat_data: dict | None = None) -> dict:
    ...
    merged = _merge_trees(tree["kr"], tree["en"])
    return {"tree": merged}

# After
def transform_categories(cat_data: dict | None = None) -> list[dict]:
    ...
    return _merge_trees(tree["kr"], tree["en"])
```

##### `_merge_trees()` (line 95)

- **반환 타입**: `dict` -> `list[dict]`
- **자료구조**: `merged = {}` (dict, code를 key로 사용) -> `merged = []` (list, append)
- **필드명**: `children` -> `list`
- 재귀 호출 시에도 동일하게 `list` 필드명 사용

```python
# Before
def _merge_trees(kr_tree: dict, en_tree: dict) -> dict:
    merged = {}
    for code in kr_tree:
        ...
        if kr_children:
            node["children"] = _merge_trees(kr_children, en_children)
        merged[code] = node
    return merged

# After
def _merge_trees(kr_tree: dict, en_tree: dict) -> list[dict]:
    merged: list[dict] = []
    for code in kr_tree:
        ...
        if kr_children:
            node["list"] = _merge_trees(kr_children, en_children)
        merged.append(node)
    return merged
```

#### 2. `main.py` (line 62)

- `transform_categories()`의 반환값이 `list`로 변경됨에 따라 카운트 로직 수정

```python
# Before
tree_count = len(categories.get("tree", {}))
print(f"[Transform] categories.json 저장 완료: {path} ({tree_count} top-level categories)")

# After
print(f"[Transform] categories.json 저장 완료: {path} ({len(categories)} top-level categories)")
```

---

## Phase 3: 하드코딩 ALLOWED_CODES 제거

### 변경 전

```python
ALLOWED_CODES: set[str] = {"AC", "EV", "EX", "FD", "HS", "LS", "NA", "SH", "VE"}

def transform_categories(...):
    ...
    for lang in ("kr", "en"):
        tree[lang] = {k: v for k, v in tree[lang].items() if k in ALLOWED_CODES}
    return _merge_trees(tree["kr"], tree["en"])
```

### 문제

- 대분류 코드가 하드코딩되어 있어 API 변경(코드 추가/삭제) 시 소스 수정 필요
- depth1 수신 데이터 자체가 유효한 카테고리 목록이므로 별도 필터 불필요

### 해결

- `ALLOWED_CODES` 상수 삭제
- `transform_categories()`에서 필터링 로직 삭제
- depth1에서 수신된 코드가 곧 출력 대상

```python
def transform_categories(cat_data: dict | None = None) -> list[dict]:
    if cat_data is None:
        tree = _build_tree_from_raw()
    else:
        tree = _build_tree_from_data(cat_data)

    # kr/en 트리를 병합하여 다국어 구조로 변환
    return _merge_trees(tree["kr"], tree["en"])
```

---

## 최종 출력 결과

```bash
uv run python main.py --transform-only
```

### `output/categories.json`

- **포맷**: JSON 배열 (최상위 `[...]`)
- **대분류 수**: 10개 (API depth1 수신 기준)
- **포함 코드**: AC, C01, EV, EX, FD, HS, LS, NA, SH, VE
- **하위 카테고리**: 각 대분류의 `list` 필드에 배열로 포함

| 코드 | 한국어 | English | 하위 수 |
|------|--------|---------|---------|
| AC | 숙박 | Accommodation | 6 |
| C01 | 추천코스 | C01 (*) | 6 |
| EV | 축제/공연/행사 | Festivals/Performances/Events | 3 |
| EX | 체험관광 | Experiential Tourism | 7 |
| FD | 음식 | Food | 5 |
| HS | 역사관광 | Historical Tourism | 4 |
| LS | 레저스포츠 | Leisure Sports | 4 |
| NA | 자연관광 | Nature Tourism | 5 |
| SH | 쇼핑 | Shopping | 7 |
| VE | 문화관광 | Cultural Tourism | 12 |

> (*) C01은 영문 depth1 데이터에 존재하지 않아, 영문명이 코드 그대로 표시됨

---

## 변경 파일 요약

| 파일 | 변경 유형 | 설명 |
|------|-----------|------|
| `src/transformers/categories.py` | 수정 | 반환 타입 배열화, children->list, ALLOWED_CODES 제거 |
| `main.py` | 수정 | categories 카운트 로직 (line 62) |
| `output/categories.json` | 재생성 | 배열 포맷, 10개 대분류 |

---

## 데이터 흐름

```
raw/category_code/{kr,en}/depth1.json
        │
        ▼
_build_tree_from_raw()          ← raw 파일에서 로드
_build_tree_from_data()         ← fetch 결과에서 로드
        │
        ▼
  tree = {"kr": {...}, "en": {...}}
        │
        ▼
_merge_trees(kr_tree, en_tree)  ← ko/en 병합, dict→list 변환
        │
        ▼
  list[dict]                    ← [{code, name:{ko,en}, list:[...]}, ...]
        │
        ▼
save_categories()               ← output/categories.json 저장
```
