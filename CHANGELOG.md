# Changelog

## [Unreleased] — 2026-02-16

> 마지막 커밋 `7b2742c` (feat: add full pagination, MongoDB storage, and 3-depth categories) 이후 변경사항

---

### 5. pois.py — lclsSystm3 태그 확장 및 제외 필터 리팩터링

**파일:** `src/transformers/pois.py`

#### 5-1. `_build_category_map()` — depth3 순회 추가

categories.json에서 grandchild(depth3)까지 순회하여 `lclsSystm3` 코드의 이름도 조회 가능하도록 확장.

#### 5-2. `_transform_item()` — tags 중복 제거 적용

`lclsSystm1/2/3` 세 레벨의 이름을 tags에 포함하되, `seen` set으로 중복 제거 처리.

#### 5-3. `transform_pois()` — 제외 필터 간소화

excluded 리스트 수집 및 별도 파일 저장 로직을 제거하고, list comprehension에서 직접 필터링하는 방식으로 간소화.

```python
exclude_codes = EXCLUDE_LCLS3_KR if lang == "kr" else EXCLUDE_LCLS3_EN
pois = [
    _transform_item(item, lang_key, category_map)
    for item in items
    if item.get("lclsSystm3", "") not in exclude_codes
]
```

---

### 6. main.py — `--transform-only`에서 MongoDB 저장 분리

**파일:** `main.py`

- `run_transform_pois()`에서 `_save_pois_to_mongodb()` 호출 제거 (순수 변환만 수행)
- `run_step2()`에서 `_save_pois_to_mongodb()`를 별도 호출하여 파이프라인 유지
- `--transform-only` 실행 시 MongoDB 저장이 실행되지 않음 (`--save-mongodb`로 별도 실행)

---

### 1. categories.py — MongoDB용 flat 문서 변환 추가

**파일:** `src/transformers/categories.py`

#### 1-1. EN_FALLBACK 딕셔너리 추가

영문 API에서 이름이 누락되는 카테고리를 위한 fallback 매핑 추가.

```python
EN_FALLBACK = {
    "C01": "Recommended Courses",
    "C0112": "Family Course",
    # ... 총 13개 항목
}
```

- **용도:** `transform_categories_db()`에서 영문 이름이 없을 때 사용
- **대상:** 추천코스(C01) 계열 depth1~depth3 카테고리

#### 1-2. `transform_categories_db()` 함수 추가

3-depth 카테고리 트리를 MongoDB용 flat 문서 리스트로 변환.

```
입력: fetch_category_code() 반환값 또는 raw 파일
출력: [{"_id": "AC", "name": {"en": "...", "kr": "..."}, "parent": "category"}, ...]
```

| 필드 | 설명 |
|------|------|
| `_id` | 카테고리 코드 (depth1/2/3) |
| `name` | `{"en": "...", "kr": "..."}` 다국어 이름 |
| `parent` | 상위 카테고리 코드 (depth1은 `"category"`, 루트는 `null`) |

#### 1-3. `save_categories_db()` 함수 추가

변환된 flat 문서 리스트를 `output/categories_db.json`으로 저장.

---

### 2. pois.py — 제외 필터 + 3-depth 태그 + exclude 파일 분리

**파일:** `src/transformers/pois.py`

#### 2-1. EXCLUDE_LCLS3_KR / EXCLUDE_LCLS3_EN 필터 추가

`lclsSystm3` 코드 기반으로 POI 항목을 제외하는 필터. kr/en 각각 독립 설정 가능.

```python
EXCLUDE_LCLS3_KR: list[str] = ["SH040300", "FD010100", "AC030300", ...]  # 73개 코드
EXCLUDE_LCLS3_EN: list[str] = ["SH040300", "FD010100", "AC030300", ...]  # 73개 코드
```

- **제외 카테고리 예시:**
  - `SH` — 쇼핑 일부 (면세점 등)
  - `FD` — 음식점 일부
  - `AC` — 숙박 일부
  - `EX` — 체험 일부
  - `NA` — 자연 일부
  - `VE` — 편의시설 일부

#### 2-2. `_build_category_map()` — depth3 지원 추가

기존에는 depth1, depth2만 매핑하던 것을 depth3(grandchild)까지 확장.

```python
# 변경 전: depth2까지
for child in top.get("list", []):
    cat_map[child["code"]] = child["name"]

# 변경 후: depth3까지
for child in top.get("list", []):
    cat_map[child["code"]] = child["name"]
    for grandchild in child.get("list", []):
        cat_map[grandchild["code"]] = grandchild["name"]
```

#### 2-3. `_transform_item()` — tags에 lclsSystm3 추가 + 중복 제거

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| tags 소스 | `lclsSystm1`, `lclsSystm2` | `lclsSystm1`, `lclsSystm2`, `lclsSystm3` |
| 중복 처리 | 없음 | `seen` set으로 중복 제거 |

#### 2-4. `transform_pois()` — 제외 항목 분리 수집

```python
# 변경 전: 필터 없이 전체 변환
pois = [_transform_item(item, lang_key, category_map) for item in items]
result[lang] = {"pois": pois, "geojson": geojson}

# 변경 후: 포함/제외 분리
for item in items:
    transformed = _transform_item(item, lang_key, category_map)
    if item.get("lclsSystm3", "") in exclude_codes:
        excluded.append(transformed)
    else:
        pois.append(transformed)
result[lang] = {"pois": pois, "geojson": geojson, "excluded": excluded}
```

#### 2-5. `save_pois()` — exclude 파일 저장 추가

제외된 항목을 `pois_exclude_{lang}.json`으로 별도 저장.

| 출력 파일 | 용도 | DB 저장 |
|-----------|------|---------|
| `pois_kr.json` | 한국어 POI 데이터 | O |
| `pois_en.json` | 영문 POI 데이터 | O |
| `pois_geo_kr.json` | 한국어 GeoJSON | O |
| `pois_geo_en.json` | 영문 GeoJSON | O |
| `pois_exclude_kr.json` | 한국어 제외 항목 | **X** |
| `pois_exclude_en.json` | 영문 제외 항목 | **X** |

---

### 3. main.py — 실행 흐름 개선

**파일:** `main.py`

#### 3-1. `run_transform_categories()` — categories_db 변환 추가

```python
# 추가된 부분
docs = transform_categories_db(cat_data)
db_path = save_categories_db(docs)
```

Step 1 실행 시 `categories.json`과 함께 `categories_db.json`도 자동 생성.

#### 3-2. `run_transform_pois()` — MongoDB 저장 분리

```python
# 변경 전: 변환 함수 내에서 MongoDB 저장 호출
def run_transform_pois():
    data = transform_pois()
    paths = save_pois(data)
    _save_pois_to_mongodb(data)   # ← 제거됨

# 변경 후: run_step2()에서 별도 호출
async def run_step2():
    await run_fetch_area_based()
    run_transform_pois()          # 변환만
    _save_pois_to_mongodb()       # MongoDB 저장 (output 파일 기반)
```

- **변경 이유:** 변환과 저장의 관심사 분리. `--transform-only` 실행 시 MongoDB 저장을 건너뛸 수 있음.

#### 3-3. `.env.example` — MONGODB_URI 추가

```
DATA_GO_KR_API_KEY=your_api_key_here
MONGODB_URI=your_mongodb_uri
```

---

### 4. 삭제된 파일

| 파일 | 사유 |
|------|------|
| `지역기반 관광정보.txt` | 초기 요구사항 메모 파일 → 구현 완료 후 제거 |

---

### 전체 데이터 흐름 요약

```
[API] → fetch → [raw/] → transform → [output/] → MongoDB
                                         │
                                         ├── categories.json       (앱용 트리 구조)
                                         ├── categories_db.json    (MongoDB용 flat)
                                         ├── regions.json
                                         ├── pois_kr.json          → DB 저장
                                         ├── pois_en.json          → DB 저장
                                         ├── pois_geo_kr.json      → DB 저장
                                         ├── pois_geo_en.json      → DB 저장
                                         ├── pois_exclude_kr.json  → DB 미저장 (참조용)
                                         └── pois_exclude_en.json  → DB 미저장 (참조용)
```

### 실행 방법

```bash
# 전체 Step 1 (코드 데이터 수신 + 변환)
python main.py --step 1

# 전체 Step 2 (관광정보 수신 + 변환 + MongoDB 저장)
python main.py --step 2

# 변환만 실행 (raw 데이터 필요, MongoDB 저장 안함)
python main.py --transform-only

# MongoDB 저장만 실행 (output 파일 필요)
python main.py --save-mongodb
```
