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
        choices=[1, 2],
        help="실행 단계 (1: 코드 데이터, 2: 관광정보)",
    )
    parser.add_argument(
        "--fetch",
        choices=["ldong_code", "category_code", "area_based"],
        help="개별 fetcher 실행",
    )
    parser.add_argument(
        "--transform-only",
        action="store_true",
        help="변환만 실행 (raw 데이터 필요)",
    )
    parser.add_argument(
        "--save-mongodb",
        action="store_true",
        help="output 파일 기반으로 MongoDB 저장만 실행",
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
    from src.transformers.regions import save_regions, transform_regions

    print("[Transform] regions.json 변환 시작...")
    regions = transform_regions(ldong_data)
    path = save_regions(regions)
    print(f"[Transform] regions.json 저장 완료: {path} ({len(regions)} regions)")


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


async def run_step1() -> None:
    """Phase 1: 코드 데이터 수신 + 변환"""
    ldong_data = await run_fetch_ldong_code()
    cat_data = await run_fetch_category_code()
    run_transform_regions(ldong_data)
    run_transform_categories(cat_data)


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
    """output 디렉토리에서 pois/geojson 파일을 로드한다."""
    import json
    from pathlib import Path

    output_dir = Path(__file__).resolve().parent / "output"
    data: dict[str, dict] = {}

    for lang in ("kr", "en"):
        pois_path = output_dir / f"pois_{lang}.json"
        geo_path = output_dir / f"pois_geo_{lang}.json"

        if not pois_path.exists() or not geo_path.exists():
            print(f"[MongoDB] {pois_path} 또는 {geo_path} 파일 없음, 건너뜀")
            continue

        data[lang] = {
            "pois": json.loads(pois_path.read_text(encoding="utf-8")),
            "geojson": json.loads(geo_path.read_text(encoding="utf-8")),
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


async def main() -> None:
    args = parse_args()

    if args.save_mongodb:
        print("=== MongoDB 저장만 실행 ===")
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
        return

    if args.step:
        if args.step == 1:
            await run_step1()
        elif args.step == 2:
            await run_step2()
        return

    # 인자 없으면 전체 실행 (현재는 step 1만)
    await run_step1()


if __name__ == "__main__":
    asyncio.run(main())
