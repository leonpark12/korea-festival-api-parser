# Changelog

## [Unreleased] — 2026-03-05

### 11. detailImage2 API 추가 — 이미지 배열 대체

POI의 전체 이미지 목록을 `detailImage2` API로 가져와 기존 `firstimage` 기반 `images` 배열을 대체.

#### 수정 파일

- **`src/config.py`** — `ENDPOINTS`에 `detail_image` (kr/en) 추가
- **`src/fetchers/detail_update.py`**
  - `_fetch_detail_for_poi()` 반환: 3-tuple → 4-tuple (`image_items` 추가)
  - `detailImage2` API 호출 추가 (contentId만 전달)
  - `_filter_pending_pois()` 스킵 조건에 `detailImageUpdated` 플래그 체크 추가
- **`src/transformers/pois_detail.py`**
  - `_normalize_url()` 헬퍼 추가 (http → https 정규화)
  - `merge_detail_to_poi()` 시그니처 5인자로 변경 (`image_items` 추가)
  - 이미지 병합 로직: `originimgurl` → `images` 배열, `smallimageurl` → `thumbnail`
  - `detailImageUpdated` 플래그 설정으로 이미지 API 처리 완료 표시
  - 이미지가 없는 POI는 기존 `images`/`thumbnail` 유지
- **`src/storage/mongodb.py`** — `update_fields`에 `images`, `detailImageUpdated` 추가

---

### 10. Step 3 MongoDB 불필요한 업데이트 수정

**파일:** `src/fetchers/detail_update.py`

`fetch_detail_update()`가 새로 업데이트한 POI뿐 아니라 기존 업데이트된 전체 POI를 반환하여 MongoDB에 불필요한 업데이트가 발생하는 문제 수정.

#### 변경 내용

- `newly_updated` 리스트 추가: 이번 실행에서 새로 업데이트한 POI만 별도 추적
- `result[lang]`에 전체 리스트(`final_list`) 대신 `newly_updated`만 반환
- JSON 파일 저장(`_save_details`)은 기존대로 전체 리스트 유지 (누적 관리)
- 업데이트 대상이 없는 경우 기존 전체 리스트 대신 빈 리스트 `[]` 반환

---

## [Unreleased] — 2026-03-04

### 9. POI 상세 업데이트 — 반복정보(detailInfo2) 추가 및 소개정보 데이터 구조 변경

detailInfo2(반복정보) API를 추가하고, 기존 `details` flat dict를 `intro`(배열) + `info`(배열) 구조로 변경.

#### 9-1. `src/config.py` — `detail_info` 엔드포인트 추가

- `ENDPOINTS`에 `detail_info` (kr/en) 추가 — detailInfo2 API

#### 9-2. `src/transformers/pois_detail.py` — 데이터 구조 변경

- `_clean_item(item)` 헬퍼 함수 추출: contentid/contenttypeid 제거 + 빈 값 필터링
- `merge_detail_to_poi(poi, common, intro_items, info_items)` 시그니처 변경 (4인자)
- detailIntro2 → `intro` 배열 (기존 `details` flat dict에서 변경)
- detailInfo2 → `info` 배열 (신규)
- 기존 `details` 필드는 `pop`으로 제거, 데이터 없는 경우에도 빈 배열 `[]` 설정

#### 9-3. `src/fetchers/detail_update.py` — detailInfo2 호출 추가

- `_fetch_detail_for_poi()` 반환: `(common_item, intro_items, info_items)` 3-tuple
- detailIntro2: `items[0]` → `items` 전체 배열 반환
- detailInfo2: 신규 호출 (contentId + contentTypeId), 전체 배열 반환
- `_filter_pending_pois()` 스킵 판별 강화: `detailUpdatedAt` + `intro` + `info` 모두 존재해야 스킵
  - 기존 `details`만 있는 POI는 자동 재처리 대상

#### 9-4. `src/storage/mongodb.py` — 필드 마이그레이션

- `update_fields`: `details` → `intro` + `info`
- `$unset: {"details": ""}` 추가로 기존 `details` 필드 제거

---

### 8. POI 상세 정보 업데이트 기능 추가

`detailCommon2`(공통정보) / `detailIntro2`(소개정보) API를 통해 기존 POI에 상세 데이터를 보강하는 기능.

#### 8-1. `src/config.py` — 엔드포인트 및 상수 추가

- `ENDPOINTS`에 `detail_common`, `detail_intro` (kr/en) 추가
- `DETAIL_UPDATE_MAX_POIS = 1000` 상수 추가 (각 언어당 일일 API 호출 제한)

#### 8-2. `src/transformers/pois_detail.py` (신규)

- `merge_detail_to_poi(poi, common, intro)`: detailCommon2/detailIntro2 응답을 기존 POI 문서에 병합
  - `overview` → `description`, `mlevel` (신규), `mapx/mapy` → `coordinates`, `homepage` → `website` (HTML 제거), `tel` → `contact`
  - `intro` 전체 → `details` (contentid/contenttypeid 제거)
  - `detailUpdatedAt` 필드 추가 (증분 업데이트 스킵 판별용)

#### 8-3. `src/fetchers/detail_update.py` (신규)

- `fetch_detail_update(region, limit)`: 핵심 수신 로직
  - `pois_{lang}.json`에서 대상 로드 → `pois_details_{lang}.json` 기반 스킵 판별
  - 언어별 독립 처리, 50건마다 중간 저장(checkpoint)
  - 시작 시 진행 상황 리포트 출력
  - 기존 `fetch_single()`, `save_raw()`, `create_client()` 재활용
- detailCommon2 호출 시 공통 파라미터 + `contentId`만 전달 (API 스펙 준수)
  - `defaultYN`/`overviewYN`/`mapinfoYN` 등 비공식 파라미터 사용 시 `INVALID_REQUEST_PARAMETER_ERROR` 발생

#### 8-4. `src/storage/mongodb.py` — `update_pois_details_to_mongodb()` 추가

- 기존 `pois_kr`/`pois_en` 컬렉션에 `$set`으로 부분 업데이트
- 대상 필드: description, mlevel, coordinates, contact, website, details, detailUpdatedAt
- `upsert=False` — 기존 문서만 업데이트

#### 8-5. `main.py` — CLI 옵션 확장

새 옵션:
- `--step 3`: POI 상세 업데이트 (수신 + MongoDB 저장)
- `--fetch detail_update`: 수신만 실행 (MongoDB 저장 없이)
- `--region <slug>`: 지역 필터 (예: `incheon`, `seoul`)
- `--limit <N>`: 각 언어당 최대 처리 건수 (기본: 1000)
- `--save-mongodb-details`: output 파일 기반 MongoDB 상세 업데이트만 실행

#### 출력 파일

| 파일 | 설명 |
|------|------|
| `output/pois_details_kr.json` | 상세 업데이트된 POI (한국어, 증분 누적) |
| `output/pois_details_en.json` | 상세 업데이트된 POI (영어, 증분 누적) |
| `raw/detail_common/{lang}/{contentId}.json` | detailCommon2 원본 응답 |
| `raw/detail_intro/{lang}/{contentId}.json` | detailIntro2 원본 응답 |

---

### 7. pois.py — 좌표 변환 에러 수정

**파일:** `src/transformers/pois.py`

#### 7-1. `_safe_float()` 헬퍼 함수 추가

API 원본 데이터의 `mapy`/`mapx` 필드에 문자열 `'null'`이 포함되어 `ValueError: could not convert string to float: 'null'` 에러 발생.
`_safe_float()` 모듈 레벨 함수를 추가하여 `'null'`, 빈값, 기타 변환 불가 값을 안전하게 0.0으로 처리.

#### 7-2. `_transform_item()` — 좌표 파싱에 `_safe_float` 적용

```python
# 변경 전
"lat": float(lat_str) if lat_str else 0.0,
"lng": float(lng_str) if lng_str else 0.0,

# 변경 후
"lat": _safe_float(lat_str),
"lng": _safe_float(lng_str),
```

---

## [Unreleased] — 2026-02-28

### 6. shrimp-rules.md — 프로젝트 규칙 문서 초기화

**파일:** `shrimp-rules.md`

Shrimp Task Manager MCP용 프로젝트 규칙 문서를 생성. 코드베이스 분석 기반으로 다음 항목을 포함:
- 프로젝트 아키텍처 및 디렉토리 구조
- 코드 표준 (네이밍, 타입 힌트, 경로 처리, JSON 저장, 주석)
- 기능 구현 표준 (fetcher/transformer/storage 패턴)
- 핵심 파일 상호작용 규칙
- AI 의사결정 표준
- 금지 사항

---

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
