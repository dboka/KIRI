from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from prepare_grid_municipalities import GRID_SIZE_M, load_municipalities, slugify


BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
FRONTEND_DATA_DIR = BASE_DIR / "frontend" / "data"
GRID_SOURCE_DIR = OUTPUTS_DIR / "municipality_grid_fragments"
GRID_TARGET_DIR = FRONTEND_DATA_DIR / "municipality_grids"
BOUNDARY_TARGET_DIR = FRONTEND_DATA_DIR / "municipality_boundaries"

OVERVIEW_SIMPLIFY_TOLERANCE_M = 250.0
DETAIL_BOUNDARY_SIMPLIFY_TOLERANCE_M = 60.0

RISK_PALETTE = {
    1: "#9ccfb0",
    2: "#f3df83",
    3: "#f3a64d",
    4: "#d9684a",
    5: "#8e3f36",
}


def lks92_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Inverse EPSG:3059 / LKS-92 Latvia TM to WGS84 lon, lat."""
    a = 6378137.0
    inverse_f = 298.257222101
    f = 1 / inverse_f
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)

    lon0 = math.radians(24.0)
    k0 = 0.9996
    false_easting = 500000.0
    false_northing = -6000000.0

    x_norm = x - false_easting
    m = (y - false_northing) / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2**3 / 256))

    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    j1 = 3 * e1 / 2 - 27 * e1**3 / 32
    j2 = 21 * e1 * e1 / 16 - 55 * e1**4 / 32
    j3 = 151 * e1**3 / 96
    j4 = 1097 * e1**4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)

    sin_fp = math.sin(fp)
    cos_fp = math.cos(fp)
    tan_fp = math.tan(fp)
    c1 = ep2 * cos_fp * cos_fp
    t1 = tan_fp * tan_fp
    n1 = a / math.sqrt(1 - e2 * sin_fp * sin_fp)
    r1 = a * (1 - e2) / (1 - e2 * sin_fp * sin_fp) ** 1.5
    d = x_norm / (n1 * k0)

    lat = fp - (n1 * tan_fp / r1) * (
        d * d / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 * c1 - 9 * ep2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 * t1 - 252 * ep2 - 3 * c1 * c1) * d**6 / 720
    )
    lon = lon0 + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 * c1 + 8 * ep2 + 24 * t1 * t1) * d**5 / 120
    ) / cos_fp

    return math.degrees(lon), math.degrees(lat)


def perpendicular_distance(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx = ex - sx
    dy = ey - sy
    if dx == 0 and dy == 0:
        return math.hypot(px - sx, py - sy)
    return abs(dy * px - dx * py + ex * sy - ey * sx) / math.hypot(dx, dy)


def simplify_line(points: list[tuple[float, float]], tolerance: float) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points

    start = points[0]
    end = points[-1]
    max_distance = -1.0
    max_index = 0

    for index, point in enumerate(points[1:-1], start=1):
        distance = perpendicular_distance(point, start, end)
        if distance > max_distance:
            max_distance = distance
            max_index = index

    if max_distance > tolerance:
        left = simplify_line(points[: max_index + 1], tolerance)
        right = simplify_line(points[max_index:], tolerance)
        return left[:-1] + right
    return [start, end]


def simplify_ring(ring: tuple[tuple[float, float], ...], tolerance: float) -> list[tuple[float, float]]:
    points = list(ring)
    if points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 4:
        return []

    simplified = simplify_line(points + [points[0]], tolerance)
    if simplified[0] != simplified[-1]:
        simplified.append(simplified[0])
    if len(simplified) < 4:
        return list(ring)
    return simplified


def ring_to_lonlat(ring: list[tuple[float, float]]) -> list[list[float]]:
    return [[round(lon, 6), round(lat, 6)] for lon, lat in (lks92_to_wgs84(x, y) for x, y in ring)]


def municipality_geometry(municipality: Any, tolerance_m: float) -> dict[str, Any]:
    polygons = []
    for _ring_bbox, ring in municipality.rings:
        simplified = simplify_ring(ring, tolerance_m)
        if len(simplified) >= 4:
            polygons.append([ring_to_lonlat(simplified)])

    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}
    return {"type": "MultiPolygon", "coordinates": polygons}


def demo_risk_level(seed: int, variant: int = 0) -> int:
    # Deterministic UI-only placeholder. This is deliberately not scientific KIRI-LV logic.
    value = (seed * 1103515245 + 12345 + variant * 7919) & 0x7FFFFFFF
    return value % 5 + 1


def demo_reasons(risk_level: int) -> list[str]:
    if risk_level >= 4:
        return ["demo_p30_high", "demo_ssm_high"]
    if risk_level == 3:
        return ["demo_mixed_moisture"]
    return ["demo_low_signal"]


def read_summary() -> dict[str, dict[str, str]]:
    with (OUTPUTS_DIR / "municipality_grid_summary.csv").open("r", encoding="utf-8", newline="") as f:
        return {row["municipality_code"]: row for row in csv.DictReader(f)}


def grid_cell_polygon(lon: float, lat: float, x: float, y: float) -> list[list[float]]:
    half = GRID_SIZE_M / 2
    corners = [
        (x - half, y - half),
        (x + half, y - half),
        (x + half, y + half),
        (x - half, y + half),
        (x - half, y - half),
    ]
    # The CSV lon/lat is used only as source QA; corners are projected exactly.
    del lon, lat
    return [[round(cx_lon, 6), round(cx_lat, 6)] for cx_lon, cx_lat in (lks92_to_wgs84(cx, cy) for cx, cy in corners)]


def write_municipality_grid_geojson(source_csv: Path, target_geojson: Path) -> dict[str, Any]:
    features = []
    risk_counts = {level: 0 for level in range(1, 6)}
    high_risk_count = 0
    municipality_name = ""
    municipality_code = ""
    municipality_atvk = ""

    with source_csv.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            grid_id = int(row["grid_id"])
            x = float(row["centroid_x"])
            y = float(row["centroid_y"])
            lon = float(row["lon"])
            lat = float(row["lat"])
            municipality_name = row["municipality_name"]
            municipality_code = row["municipality_code"]
            municipality_atvk = row["municipality_atvk"]

            risk_level = demo_risk_level(grid_id)
            risk_counts[risk_level] += 1
            if risk_level >= 4:
                high_risk_count += 1

            p30 = demo_risk_level(grid_id, 1)
            p90 = demo_risk_level(grid_id, 2)
            p730 = demo_risk_level(grid_id, 3)
            hsaf = demo_risk_level(grid_id, 4)
            swi = demo_risk_level(grid_id, 5)

            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "grid_id": row["grid_id"],
                        "municipality_code": municipality_code,
                        "municipality_atvk": municipality_atvk,
                        "municipality_name": municipality_name,
                        "risk_level": risk_level,
                        "legal_status": "demo_allowed",
                        "main_reasons": demo_reasons(risk_level),
                        "confidence": 0.72,
                        "p30_risk": p30,
                        "p90_risk": p90,
                        "p730_risk": p730,
                        "hsaf_ssm_risk": hsaf,
                        "swi_risk": swi,
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [grid_cell_polygon(lon, lat, x, y)],
                    },
                }
            )

    target_geojson.parent.mkdir(parents=True, exist_ok=True)
    target_geojson.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    cell_count = len(features)
    high_percent = round((high_risk_count / cell_count) * 100, 1) if cell_count else 0
    overall_risk = max(risk_counts, key=lambda level: (risk_counts[level], level)) if cell_count else 1
    return {
        "municipality_code": municipality_code,
        "municipality_atvk": municipality_atvk,
        "municipality_name": municipality_name,
        "grid_file": f"municipality_grids/{target_geojson.name}",
        "grid_cell_count": cell_count,
        "overall_risk": overall_risk,
        "high_risk_percent": high_percent,
        "risk_counts": risk_counts,
    }


def build_frontend_data() -> None:
    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
    GRID_TARGET_DIR.mkdir(parents=True, exist_ok=True)
    BOUNDARY_TARGET_DIR.mkdir(parents=True, exist_ok=True)

    municipalities = load_municipalities(BASE_DIR / "Novadi.shp", BASE_DIR / "Pilsetas.shp")
    summary = read_summary()

    detail_boundaries = {}
    overview_features = []
    manifest_entries = {}
    grid_stats_by_code = {}

    for municipality in municipalities:
        code = municipality.code
        atvk = municipality.atvk
        source_csv = GRID_SOURCE_DIR / f"{atvk}_{slugify(municipality.label)}.csv"
        target_geojson = GRID_TARGET_DIR / f"{code}.geojson"
        grid_stats = write_municipality_grid_geojson(source_csv, target_geojson)
        grid_stats_by_code[code] = grid_stats

        detail_boundary = {
            "type": "Feature",
            "properties": {
                "municipality_code": code,
                "municipality_atvk": atvk,
                "municipality_name": municipality.label,
                "municipality_source": municipality.source,
            },
            "geometry": municipality_geometry(municipality, DETAIL_BOUNDARY_SIMPLIFY_TOLERANCE_M),
        }
        detail_boundaries[code] = detail_boundary
        (BOUNDARY_TARGET_DIR / f"{code}.geojson").write_text(
            json.dumps(detail_boundary, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

        overview_risk = demo_risk_level(int(code))
        overview_features.append(
            {
                "type": "Feature",
                "properties": {
                    "municipality_code": code,
                    "municipality_atvk": atvk,
                    "municipality_name": municipality.label,
                    "municipality_source": municipality.source,
                    "grid_cell_count": int(summary.get(code, {}).get("grid_cell_count", 0)),
                    "risk_level": overview_risk,
                    "risk_color": RISK_PALETTE[overview_risk],
                    "grid_file": grid_stats["grid_file"],
                },
                "geometry": municipality_geometry(municipality, OVERVIEW_SIMPLIFY_TOLERANCE_M),
            }
        )

        manifest_entries[code] = {
            **grid_stats,
            "boundary_file": f"municipality_boundaries/{code}.geojson",
            "recommendation": "Demo režīms: īstie riska dati vēl nav pieslēgti.",
            "dominant_factors": ["demo_p30", "demo_hsaf_ssm", "demo_swi"],
        }

    (FRONTEND_DATA_DIR / "municipalities.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": overview_features}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (FRONTEND_DATA_DIR / "municipality_manifest.json").write_text(
        json.dumps(manifest_entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (FRONTEND_DATA_DIR / "data_metadata.json").write_text(
        json.dumps(
            {
                "purpose": "KIRI-LV map UI prototype data. Risk fields are deterministic placeholders only.",
                "source_outputs": str(OUTPUTS_DIR),
                "municipality_count": len(municipalities),
                "grid_geojson_count": len(list(GRID_TARGET_DIR.glob("*.geojson"))),
                "boundary_geojson_count": len(list(BOUNDARY_TARGET_DIR.glob("*.geojson"))),
                "overview_simplify_tolerance_m": OVERVIEW_SIMPLIFY_TOLERANCE_M,
                "detail_boundary_simplify_tolerance_m": DETAIL_BOUNDARY_SIMPLIFY_TOLERANCE_M,
                "risk_palette": RISK_PALETTE,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Municipalities written: {len(overview_features)}")
    print(f"Grid GeoJSON files written: {len(list(GRID_TARGET_DIR.glob('*.geojson')))}")
    print(f"Frontend data dir: {FRONTEND_DATA_DIR}")


if __name__ == "__main__":
    build_frontend_data()
