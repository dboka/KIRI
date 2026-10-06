from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import struct
import threading
import time
import warnings
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, wait
from datetime import date, datetime, time as datetime_time, timezone
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.transform import rowcol
from rasterio.windows import Window


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
MESLI_DIR = PROJECT_DIR.parent
DEFAULT_SWI_PROJECT = MESLI_DIR / "COPERNICUS_SWI"
DEFAULT_ENV_FILE = DEFAULT_SWI_PROJECT / ".env"
DEFAULT_GRID = DEFAULT_SWI_PROJECT / "1x1_LV_grid_2024_xy2.csv"
DEFAULT_ASSIGNMENTS = BASE_DIR / "outputs" / "grid_1km_municipalities_centroid.csv"
DEFAULT_WORK_DIR = DEFAULT_SWI_PROJECT / "data" / "climatology" / "swi010_2015_2024"
DEFAULT_FRONTEND_DIR = BASE_DIR / "frontend" / "data" / "swi_climatology"

DATASET_IDENTIFIER = "swi_europe_1km_daily_v1"
BAND = "SWI010"
REFERENCE_START = "2015-01-01"
REFERENCE_END = "2024-12-31"
RAW_NODATA = np.uint8(255)
RAW_MAX = 200
RAW_SCALE = 0.5
CLIMATOLOGY_DAYS = 366
QUANTILES = [10, 25, 50, 75, 90]
FIELDS = ["p10", "p25", "p50", "p75", "p90", "mean", "count"]
HEADER = struct.Struct("<4sBBHI")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Stream CLMS SWI010 v1 COG windows for Latvia, build a memory-bounded "
            "2015-2024 grid-cell climatology, and export compact frontend payloads."
        )
    )
    parser.add_argument("command", choices=["catalog", "harvest", "build", "export", "validate", "all"])
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--grid", type=Path, default=DEFAULT_GRID)
    parser.add_argument("--assignments", type=Path, default=DEFAULT_ASSIGNMENTS)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--frontend-dir", type=Path, default=DEFAULT_FRONTEND_DIR)
    parser.add_argument("--start-date", default=REFERENCE_START)
    parser.add_argument("--end-date", default=REFERENCE_END)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--block-cells", type=int, default=512)
    parser.add_argument("--window-radius-days", type=int, default=7)
    parser.add_argument("--minimum-samples", type=int, default=60)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--limit-products", type=int, default=None, help="Development-only catalog prefix limit.")
    return parser.parse_args()


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment value: {name}")
    return value


def write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temp_path.replace(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: object) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def iso_day_start(value: str) -> str:
    parsed = datetime.combine(date.fromisoformat(value), datetime_time.min, timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def iso_day_end(value: str) -> str:
    parsed = datetime.combine(date.fromisoformat(value), datetime_time.max, timezone.utc)
    return parsed.strftime("%Y-%m-%dT%H:%M:%S.999Z")


def attr_filter(name: str, value: str) -> str:
    return (
        "Attributes/OData.CSC.StringAttribute/any("
        f"att:att/Name eq '{name}' and att/OData.CSC.StringAttribute/Value eq '{value}'"
        ")"
    )


def build_catalog_url(start_date: str, end_date: str) -> str:
    filters = [
        "Collection/Name eq 'CLMS'",
        attr_filter("datasetIdentifier", DATASET_IDENTIFIER),
        attr_filter("fileFormat", "cog"),
        f"ContentDate/Start ge {iso_day_start(start_date)}",
        f"ContentDate/Start le {iso_day_end(end_date)}",
    ]
    encoded_filter = quote(" and ".join(filters), safe="'()/=:,. ")
    endpoint = env("CDSE_CATALOGUE_ODATA_ENDPOINT", "https://catalogue.dataspace.copernicus.eu/odata/v1")
    return (
        f"{endpoint.rstrip('/')}/Products?$count=true&$top=1000&$select=Id,Name,ContentDate,S3Path"
        f"&$orderby=ContentDate/Start asc&$filter={encoded_filter}"
    )


def derive_band_node(product_name: str, band: str = BAND) -> str:
    prefix = "c_gls_SWI1km_"
    suffix = "_cog"
    if not product_name.startswith(prefix) or not product_name.endswith(suffix):
        raise ValueError(f"Unexpected SWI v1 COG product name: {product_name}")
    middle = product_name[len(prefix) : -len(suffix)]
    return f"c_gls_SWI1km-{band}_{middle}.tiff"


def node_value_url(product: dict) -> str:
    endpoint = env("CDSE_DOWNLOAD_ODATA_ENDPOINT", "https://download.dataspace.copernicus.eu/odata/v1")
    product_name = product["name"]
    node_name = derive_band_node(product_name)
    return (
        f"{endpoint.rstrip('/')}/Products({product['id']})/Nodes({product_name})/"
        f"Nodes({node_name})/%24value"
    )


def fetch_catalog(args: argparse.Namespace) -> list[dict]:
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    products: list[dict] = []
    for year in range(start.year, end.year + 1):
        year_start = max(start, date(year, 1, 1)).isoformat()
        year_end = min(end, date(year, 12, 31)).isoformat()
        response = requests.get(build_catalog_url(year_start, year_end), timeout=90)
        response.raise_for_status()
        payload = response.json()
        found = payload.get("value", [])
        expected_count = int(payload.get("@odata.count", len(found)))
        if len(found) != expected_count:
            raise RuntimeError(f"Catalog result truncated for {year}: {len(found)} of {expected_count}")
        for product in found:
            products.append(
                {
                    "date": str(product["ContentDate"]["Start"])[:10],
                    "id": product["Id"],
                    "name": product["Name"],
                    "s3_path": product.get("S3Path"),
                }
            )
        print(f"Catalog {year}: {len(found)} products", flush=True)

    deduplicated = {product["date"]: product for product in products}
    products = [deduplicated[key] for key in sorted(deduplicated)]
    if args.limit_products:
        products = products[: args.limit_products]
    catalog_path = args.work_dir / "catalog.json"
    write_json_atomic(
        catalog_path,
        {
            "version": 1,
            "dataset_identifier": DATASET_IDENTIFIER,
            "band": BAND,
            "reference_start": args.start_date,
            "reference_end": args.end_date,
            "product_count": len(products),
            "products": products,
        },
    )
    print(f"Catalog saved: {catalog_path} ({len(products)} products)")
    return products


class TokenProvider:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at = 0.0

    def get(self, force: bool = False) -> str:
        with self._lock:
            if not force and self._token and time.monotonic() < self._expires_at - 90:
                return self._token
            response = requests.post(
                env(
                    "CDSE_TOKEN_ENDPOINT",
                    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
                ),
                data={
                    "grant_type": "password",
                    "username": env("CDSE_USER"),
                    "password": env("CDSE_PASSWORD"),
                    "client_id": env("CDSE_CLIENT_ID", "cdse-public"),
                },
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            self._token = payload["access_token"]
            self._expires_at = time.monotonic() + int(payload.get("expires_in", 600))
            return self._token


def load_grid(path: Path) -> pd.DataFrame:
    grid = pd.read_csv(path, usecols=["ID", "lon", "lat"], low_memory=False)
    grid = grid.rename(columns={"ID": "grid_id"})
    grid["grid_id"] = pd.to_numeric(grid["grid_id"], errors="raise").astype("uint32")
    if grid["grid_id"].duplicated().any():
        raise ValueError("Grid IDs must be unique")
    return grid


def sample_remote_cog(product: dict, token_provider: TokenProvider, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    last_error: Exception | None = None
    for attempt in range(3):
        token = token_provider.get(force=attempt > 0)
        try:
            with rasterio.Env(
                GDAL_HTTP_HEADERS=f"Authorization: Bearer {token}",
                GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                CPL_VSIL_CURL_USE_HEAD="NO",
                GDAL_HTTP_MAX_RETRY="3",
                GDAL_HTTP_RETRY_DELAY="1",
                VSI_CACHE="TRUE",
                VSI_CACHE_SIZE="5000000",
            ):
                with rasterio.open(f"/vsicurl/{node_value_url(product)}") as src:
                    rows, cols = rowcol(src.transform, lon, lat)
                    rows = np.asarray(rows, dtype=np.int32)
                    cols = np.asarray(cols, dtype=np.int32)
                    row_min = max(0, int(rows.min()))
                    row_max = min(src.height, int(rows.max()) + 1)
                    col_min = max(0, int(cols.min()))
                    col_max = min(src.width, int(cols.max()) + 1)
                    window = Window(col_min, row_min, col_max - col_min, row_max - row_min)
                    data = src.read(1, window=window)
                    values = data[rows - row_min, cols - col_min].astype(np.uint8, copy=True)
                    nodata = int(src.nodata) if src.nodata is not None else int(RAW_NODATA)
                    values[(values == nodata) | (values > RAW_MAX)] = RAW_NODATA
                    return values
        except Exception as exc:  # network/GDAL errors are retried with a fresh token
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"Failed to sample {product['date']} after 3 attempts: {last_error}")


def initialize_matrix(
    matrix_path: Path,
    shape: tuple[int, int],
    rebuild: bool,
) -> np.memmap:
    expected_size = math.prod(shape)
    if rebuild and matrix_path.exists():
        matrix_path.unlink()
    if not matrix_path.exists():
        matrix_path.parent.mkdir(parents=True, exist_ok=True)
        matrix = np.memmap(matrix_path, dtype="uint8", mode="w+", shape=shape)
        matrix[:] = RAW_NODATA
        matrix.flush()
        return matrix
    if matrix_path.stat().st_size != expected_size:
        raise RuntimeError(f"Matrix size mismatch; rerun with --rebuild: {matrix_path}")
    return np.memmap(matrix_path, dtype="uint8", mode="r+", shape=shape)


def harvest(args: argparse.Namespace, products: list[dict] | None = None) -> Path:
    catalog = read_json(args.work_dir / "catalog.json")
    products = products or catalog["products"]
    grid = load_grid(args.grid)
    lon = grid["lon"].to_numpy(dtype="float64")
    lat = grid["lat"].to_numpy(dtype="float64")
    grid_ids = grid["grid_id"].to_numpy(dtype="uint32")
    matrix_path = args.work_dir / "daily_swi010_uint8.dat"
    matrix = initialize_matrix(matrix_path, (len(products), len(grid)), args.rebuild)

    catalog_hash = sha256_json(products)
    grid_hash = sha256_file(args.grid)
    progress_path = args.work_dir / "harvest_progress.json"
    if args.rebuild and progress_path.exists():
        progress_path.unlink()
    if progress_path.exists():
        progress = read_json(progress_path)
        if progress.get("catalog_hash") != catalog_hash or progress.get("grid_hash") != grid_hash:
            raise RuntimeError("Harvest inputs changed; rerun with --rebuild")
    else:
        progress = {
            "version": 1,
            "catalog_hash": catalog_hash,
            "grid_hash": grid_hash,
            "completed": [],
        }
    completed = {int(value) for value in progress.get("completed", [])}
    remaining = [index for index in range(len(products)) if index not in completed]
    token_provider = TokenProvider()

    def worker(index: int) -> tuple[int, np.ndarray]:
        return index, sample_remote_cog(products[index], token_provider, lon, lat)

    workers = max(1, min(args.workers, 8))
    queue_limit = workers * 2
    submitted: dict = {}
    next_position = 0
    processed_this_run = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        while next_position < len(remaining) or submitted:
            while next_position < len(remaining) and len(submitted) < queue_limit:
                index = remaining[next_position]
                submitted[executor.submit(worker, index)] = index
                next_position += 1
            done, _ = wait(submitted, return_when=FIRST_COMPLETED)
            for future in done:
                submitted.pop(future)
                index, values = future.result()
                matrix[index, :] = values
                matrix.flush()
                completed.add(index)
                processed_this_run += 1
                progress["completed"] = sorted(completed)
                progress["last_date"] = products[index]["date"]
                write_json_atomic(progress_path, progress)
                if processed_this_run == 1 or processed_this_run % 25 == 0 or len(completed) == len(products):
                    valid = int(np.count_nonzero(values != RAW_NODATA))
                    print(
                        f"Harvest {len(completed)}/{len(products)}: {products[index]['date']} "
                        f"({valid}/{len(values)} valid)",
                        flush=True,
                    )

    manifest = {
        "version": 1,
        "dataset_identifier": DATASET_IDENTIFIER,
        "band": BAND,
        "scale": RAW_SCALE,
        "nodata": int(RAW_NODATA),
        "shape": [len(products), len(grid)],
        "dates": [product["date"] for product in products],
        "grid_ids": grid_ids.tolist(),
        "catalog_hash": catalog_hash,
        "grid_hash": grid_hash,
        "complete": len(completed) == len(products),
        "matrix_file": matrix_path.name,
    }
    manifest_path = args.work_dir / "matrix_manifest.json"
    write_json_atomic(manifest_path, manifest)
    print(f"Daily matrix ready: {matrix_path} ({matrix_path.stat().st_size / 1024**2:.1f} MiB)")
    return manifest_path


def climatology_day(date_text: str) -> int:
    parsed = date.fromisoformat(date_text)
    return (date(2000, parsed.month, parsed.day) - date(2000, 1, 1)).days


def calculate_climatology_block(
    matrix_path: str,
    matrix_shape: tuple[int, int],
    sample_rows: list[np.ndarray],
    block_start: int,
    block_end: int,
    minimum_samples: int,
) -> tuple[int, int, np.ndarray]:
    matrix = np.memmap(matrix_path, dtype="uint8", mode="r", shape=matrix_shape)
    values = np.asarray(matrix[:, block_start:block_end], dtype=np.float32)
    values[values == RAW_NODATA] = np.nan
    result = np.full(
        (block_end - block_start, CLIMATOLOGY_DAYS, len(FIELDS)),
        RAW_NODATA,
        dtype=np.uint8,
    )
    for day_index, rows in enumerate(sample_rows):
        samples = values[rows, :]
        counts = np.count_nonzero(~np.isnan(samples), axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            quantile_values = np.nanpercentile(samples, QUANTILES, axis=0, method="linear")
            mean_values = np.nanmean(samples, axis=0)
        valid = counts >= minimum_samples
        if np.any(valid):
            result[valid, day_index, : len(QUANTILES)] = np.rint(
                np.clip(quantile_values[:, valid].T, 0, RAW_MAX)
            ).astype(np.uint8)
            result[valid, day_index, FIELDS.index("mean")] = np.rint(
                np.clip(mean_values[valid], 0, RAW_MAX)
            ).astype(np.uint8)
        count_values = np.minimum(counts, 254).astype(np.uint8)
        count_values[~valid] = RAW_NODATA
        result[:, day_index, FIELDS.index("count")] = count_values
    return block_start, block_end, result


def build_climatology(args: argparse.Namespace) -> Path:
    manifest = read_json(args.work_dir / "matrix_manifest.json")
    if not manifest.get("complete"):
        raise RuntimeError("Daily matrix is incomplete; finish the harvest first")
    shape = tuple(int(value) for value in manifest["shape"])
    matrix_path = args.work_dir / manifest["matrix_file"]
    matrix = np.memmap(matrix_path, dtype="uint8", mode="r", shape=shape)
    climate_path = args.work_dir / "swi010_climatology_uint8.dat"
    climate_shape = (shape[1], CLIMATOLOGY_DAYS, len(FIELDS))
    expected_size = math.prod(climate_shape)
    if args.rebuild and climate_path.exists():
        climate_path.unlink()
    if not climate_path.exists():
        climate = np.memmap(climate_path, dtype="uint8", mode="w+", shape=climate_shape)
        climate[:] = RAW_NODATA
        climate.flush()
    else:
        if climate_path.stat().st_size != expected_size:
            raise RuntimeError(f"Climatology size mismatch; rerun with --rebuild: {climate_path}")
        climate = np.memmap(climate_path, dtype="uint8", mode="r+", shape=climate_shape)

    progress_path = args.work_dir / "climatology_progress.json"
    if args.rebuild and progress_path.exists():
        progress_path.unlink()
    progress = read_json(progress_path) if progress_path.exists() else {"version": 1, "completed_until": 0}
    start_cell = int(progress.get("completed_until", 0))
    date_bins = np.asarray([climatology_day(value) for value in manifest["dates"]], dtype=np.int16)
    radius = int(args.window_radius_days)
    sample_rows = []
    for day_index in range(CLIMATOLOGY_DAYS):
        distance = np.abs(date_bins - day_index)
        circular_distance = np.minimum(distance, CLIMATOLOGY_DAYS - distance)
        sample_rows.append(np.flatnonzero(circular_distance <= radius))

    block_size = max(32, int(args.block_cells))
    ranges = [
        (block_start, min(shape[1], block_start + block_size))
        for block_start in range(start_cell, shape[1], block_size)
    ]
    workers = max(1, min(int(args.workers), 6))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                calculate_climatology_block,
                str(matrix_path),
                shape,
                sample_rows,
                block_start,
                block_end,
                int(args.minimum_samples),
            )
            for block_start, block_end in ranges
        ]
        for future in futures:
            block_start, block_end, encoded = future.result()
            climate[block_start:block_end, :, :] = encoded
            climate.flush()
            progress = {
                "version": 2,
                "completed_until": block_end,
                "block_cells": block_size,
                "cell_count": shape[1],
                "window_radius_days": radius,
                "minimum_samples": int(args.minimum_samples),
            }
            write_json_atomic(progress_path, progress)
            print(f"Climatology cells {block_end}/{shape[1]}", flush=True)

    progress["completed_until"] = shape[1]
    write_json_atomic(progress_path, progress)

    climate_manifest = {
        "version": 1,
        "matrix_manifest": "matrix_manifest.json",
        "climatology_file": climate_path.name,
        "shape": list(climate_shape),
        "fields": FIELDS,
        "quantiles": QUANTILES,
        "scale": RAW_SCALE,
        "nodata": int(RAW_NODATA),
        "day_count": CLIMATOLOGY_DAYS,
        "window_radius_days": radius,
        "minimum_samples": int(args.minimum_samples),
        "complete": int(progress["completed_until"]) == shape[1],
    }
    manifest_path = args.work_dir / "climatology_manifest.json"
    write_json_atomic(manifest_path, climate_manifest)
    print(f"Climatology matrix ready: {climate_path} ({climate_path.stat().st_size / 1024**2:.1f} MiB)")
    return manifest_path


def gzip_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as target:
            target.write(payload)
    temp_path.replace(path)


def export_frontend(args: argparse.Namespace) -> Path:
    matrix_manifest = read_json(args.work_dir / "matrix_manifest.json")
    climate_manifest = read_json(args.work_dir / "climatology_manifest.json")
    if not climate_manifest.get("complete"):
        raise RuntimeError("Climatology matrix is incomplete")
    climate_shape = tuple(int(value) for value in climate_manifest["shape"])
    climate = np.memmap(
        args.work_dir / climate_manifest["climatology_file"],
        dtype="uint8",
        mode="r",
        shape=climate_shape,
    )
    grid_ids = np.asarray(matrix_manifest["grid_ids"], dtype=np.uint32)
    grid_index = {int(grid_id): index for index, grid_id in enumerate(grid_ids)}
    assignments = pd.read_csv(
        args.assignments,
        usecols=["grid_id", "municipality_code"],
        dtype={"grid_id": "uint32", "municipality_code": "string"},
        low_memory=False,
    ).dropna(subset=["municipality_code"])
    assignments["municipality_code"] = assignments["municipality_code"].str.replace(r"\.0$", "", regex=True)

    files = {}
    expected_names = set()
    for code, group in assignments.groupby("municipality_code", sort=True):
        municipality_grid_ids = np.sort(group["grid_id"].unique().astype(np.uint32))
        indices = np.asarray([grid_index[int(grid_id)] for grid_id in municipality_grid_ids], dtype=np.int64)
        header = HEADER.pack(b"SWIC", 1, len(FIELDS), CLIMATOLOGY_DAYS, len(indices))
        payload = header + municipality_grid_ids.astype("<u4", copy=False).tobytes() + climate[indices].tobytes()
        path = args.frontend_dir / f"{code}.bin.gz"
        gzip_bytes_atomic(path, payload)
        expected_names.add(path.name)
        files[str(code)] = {
            "path": path.name,
            "cell_count": len(indices),
            "compressed_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        print(f"Exported SWI climatology: {code} ({len(indices)} cells, {path.stat().st_size / 1024:.1f} KiB)")

    for path in args.frontend_dir.glob("*.bin.gz"):
        if path.name not in expected_names:
            path.unlink()

    index = {
        "version": 1,
        "dataset_identifier": DATASET_IDENTIFIER,
        "product_title": "CLMS Daily Soil Water Index Europe 1 km v1",
        "band": BAND,
        "reference_start": args.start_date,
        "reference_end": args.end_date,
        "reference_years": "2015–2024",
        "source_product_count": len(matrix_manifest["dates"]),
        "day_count": CLIMATOLOGY_DAYS,
        "window_radius_days": int(climate_manifest["window_radius_days"]),
        "window_days": int(climate_manifest["window_radius_days"]) * 2 + 1,
        "minimum_samples": int(climate_manifest["minimum_samples"]),
        "quantiles": QUANTILES,
        "fields": FIELDS,
        "scale": RAW_SCALE,
        "nodata": int(RAW_NODATA),
        "binary_layout": {
            "endianness": "little",
            "header": "magic[4], version[u8], field_count[u8], day_count[u16], cell_count[u32]",
            "body": "grid_ids[cell_count,u32], values[cell_count,day_count,field_count,u8]",
        },
        "municipality_count": len(files),
        "files": files,
    }
    index_path = args.frontend_dir / "index.json"
    write_json_atomic(index_path, index)
    total_bytes = sum(row["compressed_bytes"] for row in files.values())
    print(f"Frontend climatology: {index_path} ({total_bytes / 1024**2:.1f} MiB compressed)")
    return index_path


def validate_frontend(args: argparse.Namespace) -> None:
    index_path = args.frontend_dir / "index.json"
    index = read_json(index_path)
    if index.get("fields") != FIELDS:
        raise RuntimeError(f"Unexpected field schema in {index_path}")
    if int(index.get("day_count", 0)) != CLIMATOLOGY_DAYS:
        raise RuntimeError(f"Unexpected climatology day count in {index_path}")

    minimum_samples = int(index["minimum_samples"])
    seen_grid_ids: set[int] = set()
    total_cells = 0
    total_valid_profiles = 0
    for code, metadata in sorted(index["files"].items()):
        path = args.frontend_dir / metadata["path"]
        if sha256_file(path) != metadata["sha256"]:
            raise RuntimeError(f"Checksum mismatch: {path}")
        with gzip.open(path, "rb") as source:
            payload = source.read()
        magic, version, field_count, day_count, cell_count = HEADER.unpack_from(payload)
        if magic != b"SWIC" or version != 1:
            raise RuntimeError(f"Unsupported binary header: {path}")
        if field_count != len(FIELDS) or day_count != CLIMATOLOGY_DAYS:
            raise RuntimeError(f"Binary dimensions do not match schema: {path}")
        if cell_count != int(metadata["cell_count"]):
            raise RuntimeError(f"Cell count does not match index: {path}")
        expected_bytes = HEADER.size + cell_count * 4 + cell_count * day_count * field_count
        if len(payload) != expected_bytes:
            raise RuntimeError(f"Binary payload size mismatch: {path}")

        ids_offset = HEADER.size
        values_offset = ids_offset + cell_count * 4
        grid_ids = np.frombuffer(payload, dtype="<u4", count=cell_count, offset=ids_offset)
        if cell_count > 1 and np.any(grid_ids[1:] <= grid_ids[:-1]):
            raise RuntimeError(f"Grid IDs are not strictly sorted: {path}")
        duplicates = seen_grid_ids.intersection(int(value) for value in grid_ids)
        if duplicates:
            raise RuntimeError(f"Grid IDs occur in multiple municipalities: {path}")
        seen_grid_ids.update(int(value) for value in grid_ids)

        values = np.frombuffer(payload, dtype=np.uint8, offset=values_offset).reshape(
            cell_count, day_count, field_count
        )
        quantiles = values[:, :, : len(QUANTILES)]
        means = values[:, :, FIELDS.index("mean")]
        counts = values[:, :, FIELDS.index("count")]
        any_quantile = np.any(quantiles != RAW_NODATA, axis=2)
        all_quantiles = np.all(quantiles != RAW_NODATA, axis=2)
        if np.any(any_quantile != all_quantiles):
            raise RuntimeError(f"Partially missing quantile profiles: {path}")
        if np.any((counts != RAW_NODATA) != all_quantiles):
            raise RuntimeError(f"Sample counts and quantiles disagree: {path}")
        if np.any((means != RAW_NODATA) != all_quantiles):
            raise RuntimeError(f"Means and quantiles disagree: {path}")
        if np.any(means[all_quantiles] > RAW_MAX):
            raise RuntimeError(f"Mean outside the SWI value domain: {path}")
        if np.any(counts[all_quantiles] < minimum_samples):
            raise RuntimeError(f"Climatology profile below minimum sample count: {path}")
        valid_quantiles = quantiles[all_quantiles].astype(np.int16)
        if valid_quantiles.size and np.any(np.diff(valid_quantiles, axis=1) < 0):
            raise RuntimeError(f"Non-monotonic quantiles: {path}")

        total_cells += cell_count
        total_valid_profiles += int(np.count_nonzero(all_quantiles))

    if len(index["files"]) != int(index["municipality_count"]):
        raise RuntimeError("Municipality count does not match the exported file index")
    print(
        f"Validated {len(index['files'])} municipalities, {total_cells} grid cells, "
        f"{total_valid_profiles} valid cell-day profiles; checksums and quantiles are consistent."
    )


def main() -> None:
    args = parse_args()
    load_env(args.env_file)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    if args.command in {"catalog", "all"}:
        fetch_catalog(args)
    if args.command in {"harvest", "all"}:
        harvest(args)
    if args.command in {"build", "all"}:
        build_climatology(args)
    if args.command in {"export", "all"}:
        export_frontend(args)
    if args.command in {"validate", "all"}:
        validate_frontend(args)


if __name__ == "__main__":
    main()
