# Development Guidelines

## 프로젝트 개요

- **프로젝트:** korea-festival-api-parser
- **목적:** 한국관광공사 공공 API(data.go.kr)에서 축제/관광 데이터를 수신하고 변환하는 CLI 파서
- **기술 스택:** Python 3.11+, httpx (async), pymongo, python-dotenv
- **패키지 매니저:** uv
- **실행:** `uv run python main.py [옵션]`

## 프로젝트 아키텍처

### 디렉토리 구조

| 경로 | 역할 | git 추적 |
|------|------|----------|
| `main.py` | CLI 진입점 (argparse 기반) | O |
| `src/config.py` | API 설정, 엔드포인트, 공통 파라미터 | O |
| `src/client.py` | HTTP 클라이언트, 페이지네이션, raw 저장/로드 | O |
| `src/utils.py` | 유틸리티 함수 (slugify 등) | O |
| `src/fetchers/` | API 데이터 수신 (async) | O |
| `src/transformers/` | 데이터 변환 (sync) | O |
| `src/storage/` | MongoDB 저장 (sync) | O |
| `raw/` | API 원본 응답 캐시 | **X** |
| `output/` | 변환 결과 JSON | **X** |

### 데이터 흐름

```
[data.go.kr API] → fetcher (async) → [raw/] → transformer (sync) → [output/] → MongoDB (선택)
```

- 각 단계는 독립 실행 가능: `--fetch`, `--transform-only`, `--save-mongodb`

### 모듈 구조

| 모듈 | 파일 | 핵심 함수 |
|------|------|-----------|
| fetchers | `ldong_code.py` | `fetch_ldong_code()` — 행정구역 수신 |
| fetchers | `category_code.py` | `fetch_category_code()` — 분류체계 수신 (3-depth) |
| fetchers | `area_based.py` | `fetch_area_based()` — 관광정보 수신 |
| transformers | `regions.py` | `transform_regions()`, `save_regions()` |
| transformers | `categories.py` | `transform_categories()`, `transform_categories_db()`, `save_categories()`, `save_categories_db()` |
| transformers | `pois.py` | `transform_pois()`, `save_pois()` |
| storage | `mongodb.py` | `save_pois_to_mongodb()` |

## 코드 표준

### 네이밍 규칙

- **함수/변수:** `snake_case` 사용
- **내부(비공개) 함수:** `_` 접두사 필수 (예: `_build_params()`, `_parse_response()`, `_transform_item()`)
- **상수:** `UPPER_SNAKE_CASE` 사용 (예: `REGION_CODE_MAP`, `EXCLUDE_LCLS3_KR`)
- **파일명:** `snake_case.py`

### 타입 힌트

- Python 3.11+ 빌트인 타입 힌트 사용 (`dict`, `list`, `tuple` — `typing.Dict` 사용 금지)
- 함수 시그니처에 반드시 타입 힌트 명시
- 반환값 타입 명시 (예: `-> list[dict]`, `-> Path`, `-> None`)

```python
# O — 올바른 예시
def fetch_depth1(client: httpx.AsyncClient, lang: str) -> list[dict]:

# X — 잘못된 예시
def fetch_depth1(client, lang):
```

### 경로 처리

- **`pathlib.Path` 필수 사용** — `str` 경로 사용 금지
- 프로젝트 루트 기준 상대 경로: `Path(__file__).resolve().parent.parent / "raw"`

```python
# O — 올바른 예시
RAW_DIR = Path(__file__).resolve().parent.parent / "raw"
output_path = OUTPUT_DIR / f"pois_{lang}.json"

# X — 잘못된 예시
RAW_DIR = "raw"
output_path = f"output/pois_{lang}.json"
```

### JSON 파일 저장

- **모든 JSON 저장 시 다음 설정 필수:**

```python
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

- `ensure_ascii=False` — 한글 유니코드 이스케이프 방지
- `indent=2` — 가독성 확보
- `encoding="utf-8"` — UTF-8 인코딩 명시

### 주석 및 문서

- **모든 소스코드 주석은 한글로 작성**
- **모든 문서(README, CHANGELOG 등)는 한글로 작성**
- 불필요한 주석 지양 — 코드가 자명할 경우 주석 생략

## 기능 구현 표준

### Fetcher 구현 규칙

- **반드시 async로 구현** (`httpx.AsyncClient` 사용)
- `src/client.py`의 `fetch_all_pages()` 또는 `fetch_single()` 활용
- 각 API 요청 사이에 `REQUEST_DELAY` (0.3초) 적용
- 결과를 `save_raw()`로 `raw/{category}/{lang}/` 경로에 저장
- kr/en 양쪽 언어 모두 수신

```python
# fetcher 구현 패턴
async def fetch_something() -> dict:
    async with create_client() as client:
        for lang in ("kr", "en"):
            items = await fetch_all_pages(client, ENDPOINTS["something"][lang])
            save_raw(items, "something", lang, "filename")
    return {"kr": kr_data, "en": en_data}
```

### Transformer 구현 규칙

- **반드시 sync로 구현** (async 사용 금지)
- raw 파일 또는 fetcher 반환값을 입력으로 받음
- 변환 결과를 `output/` 디렉토리에 JSON으로 저장
- `transform_*()` 함수와 `save_*()` 함수를 분리

```python
# transformer 구현 패턴
def transform_something(data: dict | None) -> list[dict]:
    # data가 None이면 raw 파일에서 로드
    ...
    return result

def save_something(items: list[dict]) -> Path:
    path = OUTPUT_DIR / "something.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return path
```

### Storage 구현 규칙

- **sync로 구현** (pymongo 사용)
- batch 단위로 `bulk_write` 실행 (`BATCH_SIZE = 300`)
- `AutoReconnect` 에러 시 지수 백오프 재시도
- upsert 키는 `id` 필드 기반

### 다국어 처리 규칙

- **모든 API 호출은 kr/en 양쪽 수행**
- 이름 필드는 `{"ko": "...", "en": "..."}` 형태로 병합
- 언어별 output 파일: `{name}_kr.json`, `{name}_en.json`

## 프레임워크/라이브러리 사용 표준

| 라이브러리 | 용도 | 사용 규칙 |
|-----------|------|-----------|
| `httpx` | HTTP 클라이언트 | `AsyncClient`만 사용, `requests` 금지 |
| `pymongo` | MongoDB 드라이버 | sync만 사용, `motor` 금지 |
| `python-dotenv` | 환경 변수 | `src/config.py`에서만 로드 |
| `asyncio` | 비동기 런타임 | fetcher에서만 사용 |
| `pathlib` | 경로 처리 | 모든 파일 경로에 필수 사용 |
| `argparse` | CLI 파싱 | `main.py`에서만 사용 |

### 의존성 추가 규칙

- `pyproject.toml`의 `dependencies`에 추가
- `uv add {패키지명}`으로 설치
- 최소 의존성 원칙 유지

## 워크플로우 표준

### CLI 실행 흐름

```
main.py
├── --save-mongodb    → _save_pois_to_mongodb() → 종료
├── --transform-only  → regions + categories + pois 변환 → 종료
├── --fetch {name}    → 개별 fetch → 종료
├── --step 1          → fetch(ldong_code + category_code) → transform(regions + categories)
├── --step 2          → fetch(area_based) → transform(pois) → MongoDB 저장
└── (기본)            → --step 1과 동일
```

### 새로운 데이터 소스 추가 워크플로우

1. `src/config.py` — `ENDPOINTS`에 새 엔드포인트 추가
2. `src/fetchers/{name}.py` — async fetcher 생성
3. `src/transformers/{name}.py` — sync transformer 생성
4. `main.py` — CLI 옵션 및 호출 로직 추가
5. `src/storage/mongodb.py` — MongoDB 컬렉션 추가 (필요 시)
6. `CHANGELOG.md` — 변경사항 기록
7. `README.md` — 사용법/구조 업데이트

## 핵심 파일 상호작용 표준

### 반드시 함께 수정해야 하는 파일 조합

| 변경 대상 | 함께 수정해야 하는 파일 |
|-----------|----------------------|
| fetcher 추가/수정 | `main.py`, `src/config.py` (ENDPOINTS) |
| transformer 추가/수정 | `main.py` |
| 출력 포맷 변경 | 해당 `transformer`, `README.md` (출력 포맷 섹션) |
| CLI 옵션 추가 | `main.py`, `README.md` (사용법 섹션) |
| MongoDB 컬렉션 추가 | `src/storage/mongodb.py`, `README.md` (MongoDB 섹션) |
| **모든 코드 수정** | **`CHANGELOG.md` 필수 업데이트** |
| **README 관련 변경** | **`README.md` 자동 업데이트** |

### CHANGELOG.md 작성 규칙

```markdown
## [Unreleased] — YYYY-MM-DD

### 변경 내용 제목

- **파일명:** 변경 내용 설명
```

## AI 의사결정 표준

### 새 파일 생성 vs 기존 파일 수정

1. 새로운 데이터 소스 → 새 fetcher/transformer 파일 생성
2. 기존 데이터 소스의 변환 로직 변경 → 기존 transformer 수정
3. 유틸리티 함수 → `src/utils.py`에 추가
4. API 설정 → `src/config.py`에 추가

### 비동기 vs 동기 결정

- **외부 API 호출** → 반드시 async (fetcher)
- **파일 I/O, 데이터 변환** → sync (transformer)
- **DB 저장** → sync (storage)

### raw 파일 vs output 파일

- **raw/**: API 원본 응답 그대로 저장 — 재변환 시 활용
- **output/**: 변환된 최종 결과 — MongoDB 저장 및 외부 소비용

## 금지 사항

- **`.env` 파일 읽기/접근 절대 금지** (API 키, 시크릿 포함)
- `str` 경로 사용 금지 → `pathlib.Path` 사용
- `requests` 라이브러리 사용 금지 → `httpx.AsyncClient` 사용
- `ensure_ascii=True`로 JSON 저장 금지
- `output/`, `raw/` 디렉토리를 git에 추가 금지
- 영어로 주석/문서 작성 금지 → **한글 필수**
- `typing.Dict`, `typing.List` 등 레거시 타입 힌트 사용 금지 → 빌트인 타입 사용
- fetcher에서 동기 HTTP 호출 금지
- transformer/storage에서 비동기 사용 금지
- `dotenv` 로드를 `src/config.py` 외부에서 수행 금지
