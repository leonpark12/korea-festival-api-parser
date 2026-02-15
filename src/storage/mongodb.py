"""변환된 POI/GeoJSON 데이터를 MongoDB에 upsert 저장한다."""

import os
import time

from pymongo import MongoClient, UpdateOne
from pymongo.errors import AutoReconnect

BATCH_SIZE = 300
BATCH_DELAY = 1.0  # 배치 간 대기 시간 (초)
MAX_RETRIES = 3


def _get_client() -> MongoClient:
    """MONGODB_URI 환경변수로 MongoClient를 생성한다."""
    uri = os.environ.get("MONGODB_URI", "")
    if not uri:
        raise RuntimeError("MONGODB_URI 환경변수가 설정되지 않았습니다.")
    return MongoClient(uri)


def _bulk_write_batched(collection, ops: list, batch_size: int = BATCH_SIZE) -> int:
    """ops를 batch_size 단위로 나눠서 bulk_write하고 총 upsert 건수를 반환한다.

    Atlas Free Tier 제약을 고려하여 배치 간 딜레이와 재시도 로직을 포함한다.
    """
    total = 0
    total_batches = (len(ops) + batch_size - 1) // batch_size

    for batch_num, i in enumerate(range(0, len(ops), batch_size), 1):
        batch = ops[i : i + batch_size]

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = collection.bulk_write(batch)
                total += result.upserted_count + result.modified_count
                break
            except AutoReconnect as e:
                if attempt == MAX_RETRIES:
                    raise
                wait = BATCH_DELAY * attempt * 2
                print(f"    연결 끊김, {wait:.0f}초 후 재시도 ({attempt}/{MAX_RETRIES})...")
                time.sleep(wait)

        print(f"    배치 {batch_num}/{total_batches} 완료 ({len(batch)}건)")

        if batch_num < total_batches:
            time.sleep(BATCH_DELAY)

    return total


def save_pois_to_mongodb(data: dict[str, dict], db_name: str = "korea_tourism") -> dict[str, int]:
    """pois, geojson 데이터를 MongoDB에 upsert 저장한다.

    컬렉션 매핑:
        - pois_kr: data["kr"]["pois"] → id 기준 upsert
        - pois_en: data["en"]["pois"] → id 기준 upsert
        - pois_geo_kr: data["kr"]["geojson"]["features"] → properties.id 기준 upsert
        - pois_geo_en: data["en"]["geojson"]["features"] → properties.id 기준 upsert

    Args:
        data: transform_pois()의 반환값 {"kr": {"pois": [...], "geojson": {...}}, "en": {...}}
        db_name: MongoDB 데이터베이스 이름

    Returns:
        컬렉션별 upsert 건수 {"pois_kr": N, "pois_en": N, ...}
    """
    client = _get_client()
    db = client[db_name]
    stats: dict[str, int] = {}

    try:
        for lang in ("kr", "en"):
            if lang not in data:
                continue

            # pois_{lang}: id 기준 upsert
            pois = data[lang]["pois"]
            if pois:
                col_name = f"pois_{lang}"
                ops = [
                    UpdateOne({"id": doc["id"]}, {"$set": doc}, upsert=True)
                    for doc in pois
                ]
                print(f"  [MongoDB] {col_name}: {len(ops)}건 저장 시작...")
                count = _bulk_write_batched(db[col_name], ops)
                stats[col_name] = count
                print(f"  [MongoDB] {col_name}: {count}건 upsert 완료")

            # pois_geo_{lang}: features 개별 저장, properties.id → id 기준 upsert
            features = data[lang]["geojson"].get("features", [])
            if features:
                col_name = f"pois_geo_{lang}"
                ops = []
                for feature in features:
                    doc = dict(feature)
                    doc["id"] = feature["properties"]["id"]
                    ops.append(
                        UpdateOne({"id": doc["id"]}, {"$set": doc}, upsert=True)
                    )
                print(f"  [MongoDB] {col_name}: {len(ops)}건 저장 시작...")
                count = _bulk_write_batched(db[col_name], ops)
                stats[col_name] = count
                print(f"  [MongoDB] {col_name}: {count}건 upsert 완료")
    finally:
        client.close()

    return stats
