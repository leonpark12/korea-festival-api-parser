import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("DATA_GO_KR_API_KEY", "")

COMMON_PARAMS = {
    "numOfRows": 200,
    "pageNo": 1,
    "MobileOS": "ETC",
    "MobileApp": "AppTest",
    "_type": "json",
}

ENDPOINTS = {
    "ldong_code": {
        "kr": "https://apis.data.go.kr/B551011/KorService2/ldongCode2",
        "en": "https://apis.data.go.kr/B551011/EngService2/ldongCode2",
    },
    "category_code": {
        "kr": "https://apis.data.go.kr/B551011/KorService2/lclsSystmCode2",
        "en": "https://apis.data.go.kr/B551011/EngService2/lclsSystmCode2",
    },
    "area_based": {
        "kr": "https://apis.data.go.kr/B551011/KorService2/areaBasedList2",
        "en": "https://apis.data.go.kr/B551011/EngService2/areaBasedList2",
    },
    "detail_common": {
        "kr": "https://apis.data.go.kr/B551011/KorService2/detailCommon2",
        "en": "https://apis.data.go.kr/B551011/EngService2/detailCommon2",
    },
    "detail_intro": {
        "kr": "https://apis.data.go.kr/B551011/KorService2/detailIntro2",
        "en": "https://apis.data.go.kr/B551011/EngService2/detailIntro2",
    },
    "detail_info": {
        "kr": "https://apis.data.go.kr/B551011/KorService2/detailInfo2",
        "en": "https://apis.data.go.kr/B551011/EngService2/detailInfo2",
    },
}

REQUEST_DELAY = 0.3  # 요청 간 대기 시간 (초)
DETAIL_UPDATE_MAX_POIS = 1000  # 각 언어당 기본 최대 POI 수 (API별 1000건/일/언어)
