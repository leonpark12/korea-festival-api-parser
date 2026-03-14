# Changelog

## [Unreleased] — 2026-03-14

### 28. categories.json 리포지토리 포함 및 워크플로우 정리

카테고리 데이터(~52KB)는 거의 변경되지 않으므로 리포지토리에 직접 포함하여, GitHub Actions 환경에서 API 호출 없이 `build_category_map()`이 정상 동작하도록 변경.

#### 수정 파일

- **`.gitignore`** — `!output/categories.json` 예외 추가 (git 추적 대상에 포함)
- **`.github/workflows/festival-daily.yml`** — PR #15에서 추가한 `카테고리 데이터 수신` 단계 제거 (checkout 시 파일이 이미 존재)
- **`output/categories.json`** — `git add -f`로 추적에 추가

#### 영향

- Step 4(sync-daily), Step 5(festival-daily) 모두 checkout만으로 `output/categories.json` 사용 가능
- `output/` 내 다른 파일들은 여전히 `.gitignore`로 무시

---

### 27. festival-daily 워크플로우 카테고리 데이터 선행 수신 추가

Step 5 실행 시 `build_category_map()`이 `output/categories.json`을 필요로 하지만, GitHub Actions 환경에는 이 파일이 존재하지 않아 `FileNotFoundError` 발생. Step 5 실행 전에 `--fetch category_code`로 카테고리 데이터를 먼저 수신하도록 추가.

#### 수정 파일

- **`.github/workflows/festival-daily.yml`** — Step 5 실행 전 `카테고리 데이터 수신` 단계 추가

---

### 26. astral-sh/setup-uv v6 → v7 업그레이드

GitHub Actions에서 `astral-sh/setup-uv@v6`가 Node.js 20 기반이라 deprecation 경고가 발생하여, Node.js 24를 지원하는 `@v7`로 업그레이드.

#### 수정 파일

- **`.github/workflows/sync-daily.yml`** — `astral-sh/setup-uv@v6` → `@v7`
- **`.github/workflows/festival-daily.yml`** — `astral-sh/setup-uv@v6` → `@v7`

---

### 25. Step 5: 행사정보조회 (searchFestival2) 구현

`searchFestival2` API를 통해 행사/축제 데이터를 수집하여 기존 EV 타입 문서를 전량 교체하는 기능 추가. GitHub Actions로 매일 KST 06:00에 자동 실행.

#### 수정 파일

- **`src/config.py`** — `ENDPOINTS`에 `search_festival` (searchFestival2) 엔드포인트 추가
- **`main.py`**
  - `--step 5` / `--eventStartDate` / `--eventEndDate` CLI 인자 추가
  - `--fetch festival` 개별 fetcher 실행 지원
  - `run_step5()`: 행사정보 수신 → EV 문서 삭제 → upsert → 감사 기록 저장

#### 신규 파일

- **`src/fetchers/festival.py`** — Step 5 핵심 fetcher
  - `fetch_festival(event_start_date, event_end_date)`: searchFestival2 호출 → 카테고리 필터링 → transform_item() 변환 → 상세 API 병합
  - 날짜 기본값: 시작일 7일 전, 종료일 3개월 후
  - 최대 5회 재시도, EXCLUDE_LCLS3 필터링 적용
- **`src/storage/mongodb.py`**
  - `delete_event_pois_from_mongodb()` 추가: `source.lcls[0]=="EV"` 조건으로 전량 삭제 + 감사 기록 생성
- **`.github/workflows/festival-daily.yml`** — 매일 KST 06:00 (UTC 21:00) 자동 실행 워크플로우
  - `workflow_dispatch`로 eventStartDate, eventEndDate 수동 입력 지원

#### 데이터 흐름

```
searchFestival2 API (kr/en)
    → fetch_all_pages → 카테고리 필터링 → transform_item() → 상세 API 병합
    → MongoDB EV 문서 전량 삭제 → 신규 행사 POI upsert
    → updated_content에 감사 기록 저장
```

#### MongoDB 컬렉션

| 컬렉션 | 용도 |
|--------|------|
| `pois_kr` / `pois_en` | EV 문서 전량 삭제 후 upsert |
| `updated_content` | 행사 동기화 이력 (festival_updated / festival_deleted) |

---

### 24. Step 4 GitHub Actions 실행 시간 KST 05:00으로 변경

#### 수정 파일

- **`.github/workflows/sync-daily.yml`**
  - `cron`: `0 1 * * *` (KST 10:00) → `0 20 * * *` (KST 05:00, UTC 20:00)
- **`README.md`** — 스케줄 설명 변경

---

### 23. Step 4 areaBasedSyncList2 API 재시도 로직 추가

#### 수정 파일

- **`src/fetchers/sync_update.py`**
  - `fetch_sync_update()`: `fetch_all_pages()` 호출에 재시도 로직 추가
  - 최대 5회 시도 (첫 시도 + 4회 재시도), 실패 시 5초 대기
  - 각 시도마다 진행 상황 로그 출력
  - 5회 모두 실패 시 기존처럼 해당 언어 스킵

---

### 22. Step 4 GitHub Actions 매일 실행으로 변경

#### 수정 파일

- **`.github/workflows/sync-daily.yml`**
  - `cron`: `0 22 * * 1,4` (매주 화/금) → `0 1 * * *` (매일 KST 10:00, UTC 01:00)
  - `modifiedtime` 설명: "기본: 5일 전" → "기본: 2일 전"
- **`main.py`**
  - `run_step4()` 및 `--fetch sync_update`의 `modifiedtime` 기본값: `timedelta(days=5)` → `timedelta(days=2)`
  - 매일 실행 시 1일 간격 + 여유 1일로 누락 방지
- **`README.md`** — 스케줄 및 기본값 설명 변경

---

### 21. Step 4 카테고리 필터링 로그 개선

#### 수정 파일

- **`src/fetchers/sync_update.py`**
  - 제외 카테고리 필터링 시 제외된 카테고리 코드별 분포를 요약 출력
  - 전부 제외된 경우 원인을 명확히 표시하는 로그 메시지 개선
  - 디버그 분석 결과: `modifiedtime=20260301` 기간 수신 2151건 전부 `SH040300`(쇼핑) 카테고리로 정상 제외 확인

---

### 20. GitHub Actions 스케줄 변경 및 modifiedtime 기본값 조정

#### 수정 파일

- **`.github/workflows/sync-daily.yml`**
  - `name`: "관광정보 일일 동기화" → "관광정보 동기화"
  - `cron`: `0 1 * * *` (매일 UTC 01:00) → `0 22 * * 1,4` (매주 화/금 KST 07:00, UTC 월/목 22:00)
- **`main.py`**
  - `run_step4()` 및 `--fetch sync_update`의 `modifiedtime` 기본값: `timedelta(days=2)` → `timedelta(days=5)`
  - 주 2회 실행 시 최대 간격 4일(금→화) + 여유 1일로 누락 방지
- **`README.md`** — GitHub Actions 스케줄 설명 변경

---

### 19. Step 4: 관광정보 동기화 (증분 업데이트) 구현

`modifiedtime` 파라미터를 사용하여 최근 수정/삭제된 관광정보만 수신하고 MongoDB를 업데이트하는 증분 동기화 기능 추가. GitHub Actions로 주 2회 자동 실행 지원.

#### 수정 파일

- **`src/config.py`** — `ENDPOINTS`에 `area_based_sync` (areaBasedSyncList2) 엔드포인트 추가
- **`src/transformers/pois.py`**
  - `_transform_item()` → `transform_item()` 공개화 (Step 4 재사용)
  - `_build_category_map()` → `build_category_map()` 공개화 (Step 4 재사용)
  - 기존 내부 호출부(`transform_pois()`) 함께 수정
- **`src/fetchers/detail_update.py`**
  - `_fetch_detail_for_poi()` → `fetch_detail_for_poi()` 공개화 (Step 4 재사용)
  - `save_raw_data` 키워드 인자 추가 (기본값 `True`): Step 4에서는 `False`로 호출하여 raw 파일 저장 생략
  - 기존 내부 호출부(`fetch_detail_update()`) 함께 수정

#### 신규 파일

- **`src/fetchers/sync_update.py`** — Step 4 핵심 fetcher
  - `fetch_sync_update(modifiedtime)`: areaBasedSyncList2 호출 → showflag 분류 → 삭제/업데이트 처리
  - 삭제 대상: showflag=0 → MongoDB에서 삭제 + output 파일 제거
  - 업데이트 대상: transform_item() 변환 → fetch_detail_for_poi() 상세 수신 → merge_detail_to_poi() 병합
- **`src/storage/mongodb.py`**
  - `save_sync_summary_to_mongodb()` 추가: `updated_content` 컬렉션에 동기화 이력 저장
- **`main.py`**
  - `--step 4` / `--modifiedtime YYYYMMDD` CLI 인자 추가
  - `--fetch sync_update` 개별 fetcher 실행 지원
  - `run_step4()`: 증분 동기화 오케스트레이션 (수신 → MongoDB upsert → 삭제 → 요약 저장)
- **`.github/workflows/sync-daily.yml`** — 매주 화/금 KST 07:00 (UTC 월/목 22:00) 자동 실행 워크플로우

#### MongoDB 컬렉션

| 컬렉션 | 용도 |
|--------|------|
| `pois_kr` / `pois_en` | upsert (업데이트) + delete (삭제) |
| `updated_content` | 동기화 이력 (insert_many, 누적) |

#### `updated_content` 문서 구조

```json
{
    "contentId": "12345",
    "name": "POI 이름",
    "region": "seoul",
    "action": "updated" | "deleted",
    "lang": "kr" | "en",
    "syncDate": "2026-03-14T10:00:00"
}
```

---

### 18. 삭제된 POI 정리 + pois_geo MongoDB 로직 제거

#### Part A: pois_geo MongoDB 로직 제거

사용하지 않는 `pois_geo_kr`, `pois_geo_en` MongoDB 컬렉션 저장 로직을 완전히 제거.

##### 수정 파일

- **`src/storage/mongodb.py`**
  - `save_pois_to_mongodb()`: pois_geo 저장 블록 삭제, docstring에서 pois_geo 관련 설명 제거
  - 입력 구조 변경: `data[lang] = {"pois": [...]}` (geojson 키 제거)
- **`main.py`**
  - `_load_pois_from_output()`: `geo_path` 로드 로직 제거, `geojson` 키 제거

#### Part B: 삭제된 POI 정리 기능

Step 3에서 5개 API 모두 정상 응답이지만 데이터가 없는 POI를 삭제된 데이터로 판단하여 JSON/MongoDB에서 제거.

- **네트워크 오류 vs 삭제 구분**: `had_exception` 플래그로 구분
  - 예외 발생 → "API 호출 오류" 스킵 (삭제 안함)
  - 정상 응답 + 빈 데이터 → 삭제 후보로 수집

##### 수정 파일

- **`src/fetchers/detail_update.py`**
  - `_fetch_detail_for_poi()`: 반환값 5-tuple → 6-tuple (`had_exception` 추가)
  - `fetch_detail_update()`: 삭제 후보 수집, 반환값 `(result, deleted_ids)` tuple로 변경
  - `_remove_deleted_pois()`: `pois_{lang}.json`에서 삭제 ID 제거 후 재저장
  - `_save_deleted_log()`: `pois_deleted_{lang}.json`에 삭제 기록 누적 저장
- **`src/storage/mongodb.py`**
  - `delete_pois_from_mongodb()` 추가: `pois_kr`, `pois_en`에서 `delete_many` 수행, 재시도 로직 포함
- **`main.py`**
  - `run_fetch_detail_update()`: 반환값 `(data, deleted_ids)` 언패킹
  - `_delete_pois_from_mongodb()`: MongoDB 삭제 래퍼 함수 추가
  - `run_step3()`: 삭제된 POI가 있으면 MongoDB에서도 제거

---

## [Unreleased] — 2026-03-12

### 17. Step 3 최대 POI 수 1000 → 5000 확대

각 언어당 기본 최대 POI 수를 1000건에서 5000건으로 변경.

#### 수정 파일

- **`src/config.py`**
  - `DETAIL_UPDATE_MAX_POIS` 값을 `1000` → `5000`으로 변경

---

## [Unreleased] — 2026-03-08

### 16. Step 3 POI 상세 업데이트 중복 수신 버그 수정

`--step 3`에서 `--force` 없이도 이미 처리한 POI를 매번 다시 API에서 받아오는 버그 수정.

#### 원인

- `detailImageUpdated` 플래그가 이미지가 있는 POI에서만 설정됨 → 이미지 없는 POI는 영원히 미완료
- `detailPetUpdated` 플래그가 pet 정보가 있는 POI에서만 설정됨 → pet 정보 없는 kr POI는 영원히 미완료

#### 수정 파일

- **`src/transformers/pois_detail.py`**
  - `detailImageUpdated = True`를 `if image_items:` 블록 밖으로 이동 — API 호출 완료 시 항상 설정
- **`src/fetchers/detail_update.py`**
  - `merge_detail_to_poi` 호출 후 kr에서 `detailPetUpdated`가 없으면 `True`로 설정
  - 기존 데이터 백필: `detailUpdatedAt`이 있지만 플래그가 누락된 항목에 자동 보정

---

## [Unreleased] — 2026-03-07

### 15. regions collection MongoDB 저장 구현

regions 데이터를 `categories_db`와 동일한 `_id`/`name`/`parent` 구조로 변환하여 MongoDB `regions` collection에 저장하는 기능 추가.

#### 수정 파일

- **`src/transformers/regions.py`**
  - `transform_regions_db()` — depth1(시/도) + depth2(시/군/구) 데이터를 MongoDB용 flat 문서로 변환
  - `save_regions_db()` — `output/regions_db.json` 파일 저장
- **`src/storage/mongodb.py`**
  - `save_regions_to_mongodb()` — `regions` collection에 `_id` 기준 upsert 저장
- **`main.py`**
  - `run_transform_regions()` — `regions_db.json` 변환/저장 추가
  - `_save_regions_to_mongodb()` — output 파일 기반 MongoDB 저장 래퍼
  - `run_step1()` — regions MongoDB 저장 호출 추가
  - `--save-mongodb` — regions 저장도 포함

#### 문서 구조

```json
{"_id": "region", "name": {"en": "Region", "kr": "지역"}, "parent": null}
{"_id": "11", "name": {"ko": "서울", "en": "Seoul"}, "parent": "region"}
{"_id": "11_110", "name": {"ko": "종로구", "en": "Jongno-gu"}, "parent": "11"}
```

#### 데이터 규모

1 루트 + 17 시/도 + 264 시/군/구 = 총 282개 문서

---

## [Unreleased] — 2026-03-06

### 14. `--force` 병합 시 기존 상세 데이터 손실 버그 수정

**파일:** `src/fetchers/detail_update.py`

`--force`로 이미 상세 처리된 POI를 재수신할 때, `merge_detail_to_poi()`의 시작점이 BASE POI(`pois_{lang}.json`)여서 기존 `pois_details_{lang}.json`에 누적된 상세 데이터(description, intro, info, images 등)가 무시되는 버그 수정.

#### 변경 내용

- 병합 기반을 `poi`(BASE POI) 대신 `details_map.get(poi["id"], poi)`로 변경
- 기존 상세 데이터가 있으면 그것을 기반으로 새 API 데이터를 덮어써서 기존 데이터 보존
- API 호출이 부분 실패해도 이전에 누적된 데이터가 손실되지 않음

---

### 13. `--force` 옵션 추가 — Step 3 완료 체크 우회

`--step 3` 실행 시 `--force` 플래그를 추가하면 이미 완료된 POI도 재수신할 수 있도록 개선.

#### 수정 파일

- **`main.py`** — argparse에 `--force` 옵션 추가 (`store_true`), `run_step3()` / `run_fetch_detail_update()`에 `force` 전달
- **`src/fetchers/detail_update.py`**
  - `fetch_detail_update()` — `force: bool = False` 파라미터 추가
  - `_filter_pending_pois()` — `force: bool = False` 파라미터 추가, `force=True`일 때 `updated_ids`를 빈 set으로 설정하여 완료 체크 무시

---

## [Unreleased] — 2026-03-05

### 12. detailPetTour2 API 추가 — 반려동물 정보

한글(kr)만 지원하는 `detailPetTour2` API를 step 3에 추가하여 POI에 반려동물 동반 정보(`pet` attribute)를 병합.

#### 수정 파일

- **`src/config.py`** — `ENDPOINTS`에 `detail_pet` (kr만) 추가
- **`src/fetchers/detail_update.py`**
  - `_fetch_detail_for_poi()` 반환: 4-tuple → 5-tuple (`pet_item` 추가, kr만 호출)
  - `_filter_pending_pois()` — `lang` 파라미터 추가, kr에서만 `detailPetUpdated` 체크
  - 호출부: 5-tuple 언패킹 + `merge_detail_to_poi` 6인자 호출
- **`src/transformers/pois_detail.py`**
  - `merge_detail_to_poi()` 시그니처 6인자로 변경 (`pet_item` 추가)
  - 반려동물 병합: 첫 번째 항목을 `_clean_item()` 적용 후 `pet` object로 저장
  - `detailPetUpdated` 플래그 설정 (재호출 방지)
- **`src/storage/mongodb.py`** — `update_fields`에 `pet`, `detailPetUpdated` 추가

---

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
