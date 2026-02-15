# korea-festival-api-parser

한국관광공사 공공 API([data.go.kr](https://www.data.go.kr/))에서 관광 분류체계 및 행정구역 데이터를 수신하고, 다국어(한/영) JSON으로 변환하는 파서입니다.

## 요구사항

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) 패키지 매니저
- [data.go.kr](https://www.data.go.kr/) API 인증키
- MongoDB (선택 — MongoDB 저장 기능 사용 시)

## 설치

```bash
git clone <repository-url>
cd korea-festival-api-parser
uv sync
```

## 환경 변수 설정

`.env.example`을 복사하여 `.env`를 생성하고 API 키를 입력합니다.

```bash
cp .env.example .env
```

```dotenv
DATA_GO_KR_API_KEY=your_api_key_here
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/dbname
```

> - API 키는 [공공데이터포털](https://www.data.go.kr/)에서 "한국관광공사_관광정보서비스" 활용 신청 후 발급받을 수 있습니다.
> - `MONGODB_URI`는 선택사항입니다. 미설정 시 MongoDB 저장을 건너뛰고 파일 저장만 수행합니다.

## 사용법

### 전체 실행 (데이터 수신 + 변환)

```bash
uv run python main.py
```

### 단계별 실행

```bash
# Step 1: 코드 데이터 수신 + 변환 (행정구역, 분류체계)
uv run python main.py --step 1

# Step 2: 관광정보 수신 + 변환 + MongoDB 저장
uv run python main.py --step 2
```

### 개별 fetcher 실행

```bash
uv run python main.py --fetch ldong_code      # 행정구역 코드만 수신
uv run python main.py --fetch category_code   # 분류체계 코드만 수신
uv run python main.py --fetch area_based      # 지역기반 관광정보만 수신
```

### 변환만 실행 (raw 데이터 필요)

이미 수신된 `raw/` 데이터를 기반으로 변환만 재실행합니다.

```bash
uv run python main.py --transform-only
```

### MongoDB 저장만 실행

이미 변환된 `output/` 파일을 기반으로 MongoDB 저장만 재실행합니다.

```bash
uv run python main.py --save-mongodb
```

## 프로젝트 구조

```
korea-festival-api-parser/
├── main.py                         # 진입점
├── src/
│   ├── config.py                   # API 설정, 엔드포인트 정의
│   ├── client.py                   # HTTP 클라이언트, 페이지네이션, raw 저장/로드
│   ├── utils.py                    # 유틸리티 (slugify 등)
│   ├── fetchers/                   # API 데이터 수신
│   │   ├── ldong_code.py           # 행정구역(법정동) 코드
│   │   ├── category_code.py        # 관광 분류체계 코드 (3-depth)
│   │   └── area_based.py           # 지역기반 관광정보 (totalCount 기반 전체 페이지 순회)
│   ├── transformers/               # 데이터 변환
│   │   ├── categories.py           # 분류체계 → categories.json
│   │   ├── regions.py              # 행정구역 → regions.json
│   │   └── pois.py                 # 관광정보 → pois_{lang}.json + pois_geo_{lang}.json
│   └── storage/                    # 데이터 저장
│       └── mongodb.py              # MongoDB upsert 저장
├── raw/                            # API 원본 응답 캐시 (git 미추적)
├── output/                         # 변환 결과 JSON (git 미추적)
├── pyproject.toml
└── .env
```

## 데이터 흐름

```
data.go.kr API
      │
      ▼
  Fetchers (수신)
      │  depth1, depth2를 언어별(kr/en) 수신
      │  area_based: totalCount 기반 전체 페이지 순회
      │  raw/{category}/{lang}/*.json 저장
      ▼
  Transformers (변환)
      │  kr/en 병합 → 다국어 구조
      │  output/*.json 저장
      ▼
  Output JSON
      │
      ▼
  MongoDB (선택)
      │  pois_kr, pois_en: id 기준 upsert
      │  pois_geo_kr, pois_geo_en: properties.id 기준 upsert
      ▼
  MongoDB Collections
```

## 출력 포맷

### `output/categories.json`

관광 분류체계를 2-depth 배열로 출력합니다. 대분류 코드는 API depth1 수신 데이터에 의해 결정됩니다.

```json
[
  {
    "code": "AC",
    "name": { "ko": "숙박", "en": "Accommodation" },
    "list": [
      { "code": "AC01", "name": { "ko": "호텔", "en": "Hotels" } },
      { "code": "AC02", "name": { "ko": "콘도미니엄", "en": "Condominiums" } }
    ]
  }
]
```

| 코드 | 한국어 | English |
|------|--------|---------|
| AC | 숙박 | Accommodation |
| C01 | 추천코스 | - |
| EV | 축제/공연/행사 | Festivals/Performances/Events |
| EX | 체험관광 | Experiential Tourism |
| FD | 음식 | Food |
| HS | 역사관광 | Historical Tourism |
| LS | 레저스포츠 | Leisure Sports |
| NA | 자연관광 | Nature Tourism |
| SH | 쇼핑 | Shopping |
| VE | 문화관광 | Cultural Tourism |

### `output/regions.json`

17개 시/도를 slug 기반 코드와 다국어 이름으로 출력합니다.

```json
[
  { "code": "seoul", "name": { "ko": "서울", "en": "Seoul" } },
  { "code": "busan", "name": { "ko": "부산", "en": "Busan" } }
]
```

### `output/pois_{lang}.json`

지역기반 관광정보를 언어별(kr/en)로 출력합니다.

```json
[
  {
    "id": "2733967",
    "slug": "2733967",
    "category": "역사관광",
    "coordinates": { "lat": 37.5820858828, "lng": 126.9846616856 },
    "name": "가회동성당",
    "address": "서울특별시 종로구 북촌로 57 (가회동)",
    "description": "가회동성당",
    "region": "seoul",
    "images": ["http://...image2_1.jpg"],
    "contact": "",
    "website": "",
    "tags": ["역사관광", "종교성지"],
    "updatedAt": "2025-03-12"
  }
]
```

### `output/pois_geo_{lang}.json`

GeoJSON FeatureCollection 포맷으로 출력합니다.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [126.9846616856, 37.5820858828]
      },
      "properties": {
        "id": "2733967",
        "slug": "2733967",
        "category": "역사관광",
        "name": "가회동성당",
        "region": "seoul"
      }
    }
  ]
}
```

### MongoDB 컬렉션

`MONGODB_URI` 설정 시 `korea_tourism` 데이터베이스에 아래 4개 컬렉션으로 upsert 저장됩니다.

| 컬렉션 | upsert 키 | 저장 단위 |
|--------|-----------|----------|
| `pois_kr` | `id` | POI document |
| `pois_en` | `id` | POI document |
| `pois_geo_kr` | `id` (properties.id 추출) | GeoJSON Feature document |
| `pois_geo_en` | `id` (properties.id 추출) | GeoJSON Feature document |

## 의존성

| 패키지 | 용도 |
|--------|------|
| [httpx](https://www.python-httpx.org/) | 비동기 HTTP 클라이언트 |
| [pymongo](https://pymongo.readthedocs.io/) | MongoDB 드라이버 |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 환경 변수 로드 |

## 라이선스

MIT
