import argparse
import asyncio
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="한국관광공사 공공 API 데이터 수신 및 변환"
    )
    parser.add_argument(
        "--step",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="실행 단계 (1: 코드 데이터, 2: 관광정보, 3: POI 상세 업데이트, 4: 관광정보 동기화, 5: 행사정보조회)",
    )
    parser.add_argument(
        "--fetch",
        choices=["ldong_code", "category_code", "area_based", "detail_update", "sync_update", "festival"],
        help="개별 fetcher 실행",
    )
    parser.add_argument(
        "--modifiedtime",
        type=str,
        default=None,
        help="수정일 기준 (YYYYMMDD 형식). --step 4에서 사용. 기본값: 2일 전",
    )
    parser.add_argument(
        "--transform-only",
        action="store_true",
        help="변환만 실행 (raw 데이터 필요)",
    )
    parser.add_argument(
        "--save-mongodb",
        action="store_true",
        help="output 파일 기반으로 MongoDB 저장만 실행 (regions + pois)",
    )
    parser.add_argument(
        "--save-mongodb-details",
        action="store_true",
        help="output 파일 기반으로 MongoDB 상세 업데이트만 실행",
    )
    parser.add_argument(
        "--eventStartDate",
        type=str,
        default=None,
        help="행사 시작일 (YYYYMMDD 형식). --step 5에서 사용. 기본값: 2일 전",
    )
    parser.add_argument(
        "--eventEndDate",
        type=str,
        default=None,
        help="행사 종료일 (YYYYMMDD 형식). --step 5에서 사용. 기본값: 30일 후",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="완료된 POI도 재수신 (--step 3 전용). 기존 완료 체크를 무시하고 모든 POI를 다시 처리",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help="지역 slug 필터 (예: incheon, seoul). --step 3 또는 --fetch detail_update에서 사용",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="각 언어당 최대 처리 건수 (기본: 1000). --step 3에서 사용",
    )
    return parser.parse_args()


async def run_fetch_ldong_code() -> dict:
    from src.fetchers.ldong_code import fetch_ldong_code

    print("[Fetch] 법정동 코드 수신 시작...")
    data = await fetch_ldong_code()
    print("[Fetch] 법정동 코드 수신 완료")
    return data


async def run_fetch_category_code() -> dict:
    from src.fetchers.category_code import fetch_category_code

    print("[Fetch] 분류체계 코드 수신 시작...")
    data = await fetch_category_code()
    print("[Fetch] 분류체계 코드 수신 완료")
    return data


def run_transform_regions(ldong_data: dict | None = None) -> None:
    from src.transformers.regions import (
        save_regions,
        save_regions_db,
        transform_regions,
        transform_regions_db,
    )

    print("[Transform] regions.json 변환 시작...")
    regions = transform_regions(ldong_data)
    path = save_regions(regions)
    print(f"[Transform] regions.json 저장 완료: {path} ({len(regions)} regions)")

    print("[Transform] regions_db.json 변환 시작...")
    docs = transform_regions_db(ldong_data)
    db_path = save_regions_db(docs)
    print(f"[Transform] regions_db.json 저장 완료: {db_path} ({len(docs)} documents)")


def run_transform_categories(cat_data: dict | None = None) -> None:
    from src.transformers.categories import (
        save_categories,
        save_categories_db,
        transform_categories,
        transform_categories_db,
    )

    print("[Transform] categories.json 변환 시작...")
    categories = transform_categories(cat_data)
    path = save_categories(categories)
    print(f"[Transform] categories.json 저장 완료: {path} ({len(categories)} top-level categories)")

    print("[Transform] categories_db.json 변환 시작...")
    docs = transform_categories_db(cat_data)
    db_path = save_categories_db(docs)
    print(f"[Transform] categories_db.json 저장 완료: {db_path} ({len(docs)} documents)")


def _save_regions_to_mongodb(docs: list[dict] | None = None) -> None:
    """변환된 regions_db 데이터를 MongoDB에 저장한다.

    docs가 None이면 output/regions_db.json에서 로드한다.
    """
    import os

    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("MONGODB_URI"):
        print("[MongoDB] MONGODB_URI 미설정, MongoDB 저장 건너뜀")
        return

    if docs is None:
        import json
        from pathlib import Path

        regions_db_path = Path(__file__).resolve().parent / "output" / "regions_db.json"
        if not regions_db_path.exists():
            print(f"[MongoDB] {regions_db_path} 파일 없음, 건너뜀")
            return
        docs = json.loads(regions_db_path.read_text(encoding="utf-8"))

    from src.storage.mongodb import save_regions_to_mongodb

    print("[MongoDB] regions 저장 시작...")
    count = save_regions_to_mongodb(docs)
    print(f"[MongoDB] regions 저장 완료: {count}건")


async def run_step1() -> None:
    """Phase 1: 코드 데이터 수신 + 변환"""
    ldong_data = await run_fetch_ldong_code()
    cat_data = await run_fetch_category_code()
    run_transform_regions(ldong_data)
    run_transform_categories(cat_data)
    _save_regions_to_mongodb()


async def run_fetch_area_based() -> dict:
    from src.fetchers.area_based import fetch_area_based

    print("[Fetch] 지역기반 관광정보 수신 시작...")
    data = await fetch_area_based()
    print("[Fetch] 지역기반 관광정보 수신 완료")
    return data


def run_transform_pois() -> None:
    from src.transformers.pois import save_pois, transform_pois

    print("[Transform] pois 변환 시작...")
    data = transform_pois()
    paths = save_pois(data)
    for p in paths:
        print(f"[Transform] 저장 완료: {p}")


def _save_pois_to_mongodb(data: dict | None = None) -> None:
    """변환된 POI 데이터를 MongoDB에 저장한다.

    data가 None이면 output 파일에서 로드한다.
    """
    import os

    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("MONGODB_URI"):
        print("[MongoDB] MONGODB_URI 미설정, MongoDB 저장 건너뜀")
        return

    if data is None:
        data = _load_pois_from_output()
        if not data:
            return

    from src.storage.mongodb import save_pois_to_mongodb

    print("[MongoDB] pois 저장 시작...")
    stats = save_pois_to_mongodb(data)
    total = sum(stats.values())
    print(f"[MongoDB] 저장 완료: 총 {total}건 ({stats})")


def _load_pois_from_output() -> dict | None:
    """output 디렉토리에서 pois 파일을 로드한다."""
    import json
    from pathlib import Path

    output_dir = Path(__file__).resolve().parent / "output"
    data: dict[str, dict] = {}

    for lang in ("kr", "en"):
        pois_path = output_dir / f"pois_{lang}.json"

        if not pois_path.exists():
            print(f"[MongoDB] {pois_path} 파일 없음, 건너뜀")
            continue

        data[lang] = {
            "pois": json.loads(pois_path.read_text(encoding="utf-8")),
        }

    if not data:
        print("[MongoDB] 저장할 output 파일이 없습니다.")
        return None

    return data


async def run_step2() -> None:
    """Phase 2: 관광정보 수신 + 변환 + MongoDB 저장"""
    await run_fetch_area_based()
    run_transform_pois()
    _save_pois_to_mongodb()


async def run_fetch_detail_update(
    region: str | None = None, limit: int | None = None, force: bool = False
) -> tuple[dict, dict[str, list[str]]]:
    from src.config import DETAIL_UPDATE_MAX_POIS
    from src.fetchers.detail_update import fetch_detail_update

    effective_limit = limit if limit is not None else DETAIL_UPDATE_MAX_POIS
    region_label = region or "전체"
    print(f"[Fetch] POI 상세 업데이트 수신 시작 (지역: {region_label}, 제한: {effective_limit}건)...")
    data, deleted_ids = await fetch_detail_update(region=region, limit=effective_limit, force=force)
    print("[Fetch] POI 상세 업데이트 수신 완료")
    return data, deleted_ids


def _delete_pois_from_mongodb(deleted_ids: dict[str, list[str]]) -> None:
    """삭제된 POI를 MongoDB에서 제거한다."""
    import os

    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("MONGODB_URI"):
        print("[MongoDB] MONGODB_URI 미설정, MongoDB 삭제 건너뜀")
        return

    from src.storage.mongodb import delete_pois_from_mongodb

    total = sum(len(ids) for ids in deleted_ids.values())
    print(f"[MongoDB] 삭제된 POI {total}건 제거 시작...")
    stats = delete_pois_from_mongodb(deleted_ids)
    total_deleted = sum(stats.values())
    print(f"[MongoDB] 삭제 완료: 총 {total_deleted}건 ({stats})")


def _save_details_to_mongodb(data: dict | None = None) -> None:
    """상세 업데이트된 POI를 MongoDB에 부분 업데이트한다."""
    import os

    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("MONGODB_URI"):
        print("[MongoDB] MONGODB_URI 미설정, MongoDB 저장 건너뜀")
        return

    if data is None:
        data = _load_details_from_output()
        if not data:
            return

    from src.storage.mongodb import update_pois_details_to_mongodb

    print("[MongoDB] POI 상세 업데이트 저장 시작...")
    stats = update_pois_details_to_mongodb(data)
    total = sum(stats.values())
    print(f"[MongoDB] 저장 완료: 총 {total}건 ({stats})")


def _load_details_from_output() -> dict | None:
    """output 디렉토리에서 pois_details 파일을 로드한다."""
    import json
    from pathlib import Path

    output_dir = Path(__file__).resolve().parent / "output"
    data: dict[str, list[dict]] = {}

    for lang in ("kr", "en"):
        details_path = output_dir / f"pois_details_{lang}.json"
        if not details_path.exists():
            print(f"[MongoDB] {details_path} 파일 없음, 건너뜀")
            continue
        data[lang] = json.loads(details_path.read_text(encoding="utf-8"))

    if not data:
        print("[MongoDB] 저장할 pois_details 파일이 없습니다.")
        return None

    return data


def _save_sync_summary_to_mongodb(summaries: list[dict]) -> None:
    """동기화 요약을 MongoDB updated_content 컬렉션에 저장한다."""
    import os

    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("MONGODB_URI"):
        print("[MongoDB] MONGODB_URI 미설정, MongoDB 요약 저장 건너뜀")
        return

    from src.storage.mongodb import save_sync_summary_to_mongodb

    print("[MongoDB] 동기화 요약 저장 시작...")
    count = save_sync_summary_to_mongodb(summaries)
    print(f"[MongoDB] 동기화 요약 저장 완료: {count}건")


async def run_fetch_sync_update(modifiedtime: str) -> tuple[dict, dict, list]:
    from src.fetchers.sync_update import fetch_sync_update

    print(f"[Fetch] 관광정보 동기화 수신 시작 (modifiedtime={modifiedtime})...")
    upserted, deleted_ids, summaries = await fetch_sync_update(modifiedtime)
    print("[Fetch] 관광정보 동기화 수신 완료")
    return upserted, deleted_ids, summaries


async def run_step4(modifiedtime: str | None = None) -> None:
    """Phase 4: 관광정보 동기화 (증분 업데이트)"""
    from datetime import date, timedelta

    # modifiedtime 기본값: 2일 전 (매일 실행 시 1일 + 여유 1일)
    if modifiedtime is None:
        modifiedtime = (date.today() - timedelta(days=2)).strftime("%Y%m%d")

    # 1. 수정된 POI 수신 + 변환 + 상세 업데이트
    upserted, deleted_ids, summaries = await run_fetch_sync_update(modifiedtime)

    # 2. MongoDB upsert (기존 save_pois_to_mongodb 재사용)
    if any(upserted.values()):
        _save_pois_to_mongodb({
            lang: {"pois": pois} for lang, pois in upserted.items() if pois
        })

    # 3. MongoDB 삭제
    if any(deleted_ids.values()):
        _delete_pois_from_mongodb(deleted_ids)

    # 4. 동기화 요약 저장
    if summaries:
        _save_sync_summary_to_mongodb(summaries)


def _delete_old_sync_summaries() -> None:
    """updated_content 컬렉션에서 오래된 동기화 요약을 삭제한다."""
    import os

    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("MONGODB_URI"):
        print("[MongoDB] MONGODB_URI 미설정, 오래된 요약 삭제 건너뜀")
        return

    from src.storage.mongodb import delete_old_sync_summaries

    print("[MongoDB] 오래된 동기화 요약 삭제 시작 (4일 이전)...")
    count = delete_old_sync_summaries()
    print(f"[MongoDB] 오래된 동기화 요약 삭제 완료: {count}건")


async def run_fetch_festival(
    event_start_date: str | None = None, event_end_date: str | None = None
) -> tuple[dict, list]:
    from src.fetchers.festival import fetch_festival

    print("[Fetch] 행사정보 수신 시작...")
    festival_data, summaries = await fetch_festival(event_start_date, event_end_date)
    print("[Fetch] 행사정보 수신 완료")
    return festival_data, summaries


def _delete_event_pois_from_mongodb() -> tuple[dict, list]:
    """EV 타입 POI를 MongoDB에서 전량 삭제한다."""
    import os

    from dotenv import load_dotenv

    load_dotenv()

    if not os.environ.get("MONGODB_URI"):
        print("[MongoDB] MONGODB_URI 미설정, MongoDB EV 삭제 건너뜀")
        return {}, []

    from src.storage.mongodb import delete_event_pois_from_mongodb

    print("[MongoDB] EV(행사) 문서 삭제 시작...")
    stats, delete_summaries = delete_event_pois_from_mongodb()
    total = sum(stats.values())
    print(f"[MongoDB] EV 삭제 완료: 총 {total}건 ({stats})")
    return stats, delete_summaries


async def run_step5(
    event_start_date: str | None = None, event_end_date: str | None = None
) -> None:
    """Phase 5: 행사정보조회 (전량 교체)"""
    # 1. 행사정보 수신 + 변환 + 상세
    festival_data, summaries = await run_fetch_festival(event_start_date, event_end_date)

    # 2. 데이터가 있을 때만 기존 EV 문서 삭제 후 upsert
    if any(len(pois) > 0 for pois in festival_data.values()):
        delete_stats, delete_summaries = _delete_event_pois_from_mongodb()
        summaries.extend(delete_summaries)
        _save_pois_to_mongodb({
            lang: {"pois": pois} for lang, pois in festival_data.items() if pois
        })

    # 3. 감사 요약 저장
    if summaries:
        _save_sync_summary_to_mongodb(summaries)

    # 4. updated_content 오래된 데이터 정리 (4일 이전)
    _delete_old_sync_summaries()


async def run_step3(region: str | None = None, limit: int | None = None, force: bool = False) -> None:
    """Phase 3: POI 상세 업데이트 수신 + MongoDB 저장 + 삭제된 POI 정리"""
    data, deleted_ids = await run_fetch_detail_update(region=region, limit=limit, force=force)
    _save_details_to_mongodb(data)
    if any(deleted_ids.values()):
        _delete_pois_from_mongodb(deleted_ids)


async def main() -> None:
    args = parse_args()

    if args.save_mongodb_details:
        print("=== MongoDB 상세 업데이트만 실행 ===")
        _save_details_to_mongodb()
        return

    if args.save_mongodb:
        print("=== MongoDB 저장만 실행 ===")
        _save_regions_to_mongodb()
        _save_pois_to_mongodb()
        return

    if args.transform_only:
        print("=== 변환만 실행 (raw 데이터 사용) ===")
        run_transform_regions()
        run_transform_categories()
        run_transform_pois()
        return

    if args.fetch:
        if args.fetch == "ldong_code":
            await run_fetch_ldong_code()
        elif args.fetch == "category_code":
            await run_fetch_category_code()
        elif args.fetch == "area_based":
            await run_fetch_area_based()
        elif args.fetch == "detail_update":
            await run_fetch_detail_update(region=args.region, limit=args.limit)
        elif args.fetch == "sync_update":
            from datetime import date, timedelta
            mt = args.modifiedtime or (date.today() - timedelta(days=2)).strftime("%Y%m%d")
            await run_fetch_sync_update(mt)
        elif args.fetch == "festival":
            await run_fetch_festival(args.eventStartDate, args.eventEndDate)
        return

    if args.step:
        if args.step == 1:
            await run_step1()
        elif args.step == 2:
            await run_step2()
        elif args.step == 3:
            await run_step3(region=args.region, limit=args.limit, force=args.force)
        elif args.step == 4:
            await run_step4(modifiedtime=args.modifiedtime)
        elif args.step == 5:
            await run_step5(
                event_start_date=args.eventStartDate,
                event_end_date=args.eventEndDate,
            )
        return

    # 인자 없으면 전체 실행 (현재는 step 1만)
    await run_step1()


if __name__ == "__main__":
    asyncio.run(main())
