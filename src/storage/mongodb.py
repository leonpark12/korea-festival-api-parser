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


def update_pois_details_to_mongodb(
    data: dict[str, list[dict]], db_name: str = "korea_tourism"
) -> dict[str, int]:
    """상세 업데이트된 POI를 기존 컬렉션에 부분 업데이트한다.

    기존 pois_kr/pois_en 컬렉션에 $set으로 부분 업데이트만 수행한다.
    upsert=False — 기존 문서만 업데이트, 신규 생성 안함.

    Args:
        data: {"kr": [POI 목록], "en": [POI 목록]}
        db_name: MongoDB 데이터베이스 이름

    Returns:
        컬렉션별 업데이트 건수 {"pois_kr": N, "pois_en": N}
    """
    # 부분 업데이트할 필드 목록
    update_fields = (
        "description", "mlevel", "coordinates", "location",
        "contact", "website", "intro", "info", "detailUpdatedAt",
        "thumbnail", "appCategory", "images", "detailImageUpdated",
        "pet", "detailPetUpdated",
    )

    client = _get_client()
    db = client[db_name]
    stats: dict[str, int] = {}

    try:
        for lang in ("kr", "en"):
            if lang not in data:
                continue

            pois = data[lang]
            # detailUpdatedAt이 있는 항목만 업데이트 대상
            updated_pois = [p for p in pois if p.get("detailUpdatedAt")]
            if not updated_pois:
                continue

            col_name = f"pois_{lang}"
            ops = []
            for doc in updated_pois:
                set_fields = {
                    k: doc[k] for k in update_fields if k in doc
                }
                if set_fields:
                    ops.append(
                        UpdateOne(
                            {"id": doc["id"]},
                            {
                                "$set": set_fields,
                                "$unset": {"details": ""},
                            },
                            upsert=False,
                        )
                    )

            if not ops:
                continue

            print(f"  [MongoDB] {col_name}: {len(ops)}건 상세 업데이트 시작...")
            count = _bulk_write_batched(db[col_name], ops)
            stats[col_name] = count
            print(f"  [MongoDB] {col_name}: {count}건 업데이트 완료")
    finally:
        client.close()

    return stats


def save_regions_to_mongodb(
    docs: list[dict], db_name: str = "korea_tourism"
) -> int:
    """regions_db 문서를 MongoDB regions 컬렉션에 upsert 저장한다.

    Args:
        docs: transform_regions_db()의 반환값
        db_name: MongoDB 데이터베이스 이름

    Returns:
        upsert 건수
    """
    client = _get_client()
    db = client[db_name]

    try:
        ops = [
            UpdateOne({"_id": doc["_id"]}, {"$set": doc}, upsert=True)
            for doc in docs
        ]
        print(f"  [MongoDB] regions: {len(ops)}건 저장 시작...")
        count = _bulk_write_batched(db["regions"], ops)
        print(f"  [MongoDB] regions: {count}건 upsert 완료")
        return count
    finally:
        client.close()


def save_pois_to_mongodb(data: dict[str, dict], db_name: str = "korea_tourism") -> dict[str, int]:
    """pois 데이터를 MongoDB에 upsert 저장한다.

    컬렉션 매핑:
        - pois_kr: data["kr"]["pois"] → id 기준 upsert
        - pois_en: data["en"]["pois"] → id 기준 upsert

    Args:
        data: {"kr": {"pois": [...]}, "en": {"pois": [...]}}
        db_name: MongoDB 데이터베이스 이름

    Returns:
        컬렉션별 upsert 건수 {"pois_kr": N, "pois_en": N}
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
    finally:
        client.close()

    return stats


def save_sync_summary_to_mongodb(
    summaries: list[dict], db_name: str = "korea_tourism"
) -> int:
    """동기화 결과를 updated_content 컬렉션에 저장한다.

    문서 구조:
    {
        "contentId": "12345",
        "name": "POI 이름",
        "region": "seoul",
        "action": "updated" | "deleted",
        "lang": "kr" | "en",
        "syncDate": "2026-03-14T10:00:00"
    }

    누적 이력 기록 목적으로 insert_many를 사용한다.

    Args:
        summaries: 동기화 요약 문서 리스트
        db_name: MongoDB 데이터베이스 이름

    Returns:
        저장된 문서 수
    """
    if not summaries:
        return 0

    client = _get_client()
    db = client[db_name]

    try:
        collection = db["updated_content"]
        total = 0
        total_batches = (len(summaries) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_num, i in enumerate(range(0, len(summaries), BATCH_SIZE), 1):
            batch = summaries[i : i + BATCH_SIZE]

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    result = collection.insert_many(batch)
                    total += len(result.inserted_ids)
                    break
                except AutoReconnect:
                    if attempt == MAX_RETRIES:
                        raise
                    wait = BATCH_DELAY * attempt * 2
                    print(f"    연결 끊김, {wait:.0f}초 후 재시도 ({attempt}/{MAX_RETRIES})...")
                    time.sleep(wait)

            print(f"    배치 {batch_num}/{total_batches} 완료 ({len(batch)}건)")

            if batch_num < total_batches:
                time.sleep(BATCH_DELAY)

        return total
    finally:
        client.close()


def delete_old_sync_summaries(db_name: str = "korea_tourism", days: int = 4) -> int:
    """updated_content 컬렉션에서 오래된 동기화 요약을 삭제한다.

    syncDate 기준으로 days일 이전 데이터를 삭제한다.
    syncDate는 ISO 문자열 형식이므로 문자열 비교로 처리한다.

    Args:
        db_name: MongoDB 데이터베이스 이름
        days: 삭제 기준 일수 (기본값: 4일)

    Returns:
        삭제된 문서 수
    """
    from datetime import datetime, timedelta

    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")

    client = _get_client()
    db = client[db_name]

    try:
        collection = db["updated_content"]
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = collection.delete_many({"syncDate": {"$lt": cutoff}})
                return result.deleted_count
            except AutoReconnect:
                if attempt == MAX_RETRIES:
                    raise
                wait = BATCH_DELAY * attempt * 2
                print(f"    연결 끊김, {wait:.0f}초 후 재시도 ({attempt}/{MAX_RETRIES})...")
                time.sleep(wait)
    finally:
        client.close()

    return 0


def delete_event_pois_from_mongodb(
    db_name: str = "korea_tourism",
) -> tuple[dict[str, int], list[dict]]:
    """EV(행사) 타입 POI를 MongoDB에서 전량 삭제한다.

    source.lcls 배열의 첫 번째 요소가 "EV"인 문서를 대상으로 한다.

    Args:
        db_name: MongoDB 데이터베이스 이름

    Returns:
        (stats, summaries)
        - stats: 컬렉션별 삭제 건수 {"pois_kr": N, "pois_en": N}
        - summaries: 삭제된 POI 감사 기록 리스트
    """
    from datetime import datetime

    client = _get_client()
    db = client[db_name]
    stats: dict[str, int] = {}
    summaries: list[dict] = []
    sync_date = datetime.now().isoformat(timespec="seconds")

    query = {"source.lcls.0": "EV"}

    try:
        for lang in ("kr", "en"):
            col_name = f"pois_{lang}"
            collection = db[col_name]

            # 삭제 전 감사 기록용 조회
            docs = list(collection.find(query, {"id": 1, "name": 1, "region": 1, "_id": 0}))
            for doc in docs:
                summaries.append({
                    "contentId": doc.get("id", ""),
                    "name": doc.get("name", ""),
                    "region": doc.get("region", ""),
                    "action": "festival_deleted",
                    "lang": lang,
                    "syncDate": sync_date,
                })

            if not docs:
                print(f"  [MongoDB] {col_name}: 삭제 대상 EV 문서 없음")
                continue

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    result = collection.delete_many(query)
                    stats[col_name] = result.deleted_count
                    print(f"  [MongoDB] {col_name}: EV 문서 {result.deleted_count}건 삭제 완료")
                    break
                except AutoReconnect:
                    if attempt == MAX_RETRIES:
                        raise
                    wait = BATCH_DELAY * attempt * 2
                    print(f"    연결 끊김, {wait:.0f}초 후 재시도 ({attempt}/{MAX_RETRIES})...")
                    time.sleep(wait)
    finally:
        client.close()

    return stats, summaries


def delete_pois_from_mongodb(
    deleted_ids: dict[str, list[str]], db_name: str = "korea_tourism"
) -> dict[str, int]:
    """삭제된 POI를 MongoDB에서 제거한다.

    대상 컬렉션: pois_kr, pois_en

    Args:
        deleted_ids: {"kr": [삭제할 ID 목록], "en": [...]}
        db_name: MongoDB 데이터베이스 이름

    Returns:
        컬렉션별 삭제 건수 {"pois_kr": N, "pois_en": N}
    """
    client = _get_client()
    db = client[db_name]
    stats: dict[str, int] = {}

    try:
        for lang in ("kr", "en"):
            ids = deleted_ids.get(lang, [])
            if not ids:
                continue

            col_name = f"pois_{lang}"
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    result = db[col_name].delete_many({"id": {"$in": ids}})
                    stats[col_name] = result.deleted_count
                    print(f"  [MongoDB] {col_name}: {result.deleted_count}건 삭제 완료")
                    break
                except AutoReconnect as e:
                    if attempt == MAX_RETRIES:
                        raise
                    wait = BATCH_DELAY * attempt * 2
                    print(f"    연결 끊김, {wait:.0f}초 후 재시도 ({attempt}/{MAX_RETRIES})...")
                    time.sleep(wait)
    finally:
        client.close()

    return stats
