from __future__ import annotations

import argparse
import csv
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


GRID_SIZE_M = 1000.0
SPATIAL_INDEX_BUCKET_M = 10000.0


@dataclass(frozen=True)
class Municipality:
    code: str
    atvk: str
    label: str
    source: str
    bbox: tuple[float, float, float, float]
    rings: tuple[tuple[tuple[float, float, float, float], tuple[tuple[float, float], ...]], ...]


def read_dbf(path: Path, encoding: str = "utf-8") -> list[dict[str, str]]:
    data = path.read_bytes()
    record_count = struct.unpack("<I", data[4:8])[0]
    header_length = struct.unpack("<H", data[8:10])[0]
    record_length = struct.unpack("<H", data[10:12])[0]

    fields: list[tuple[str, int]] = []
    pos = 32
    while data[pos] != 0x0D:
        name = data[pos : pos + 11].split(b"\x00", 1)[0].decode("ascii")
        length = data[pos + 16]
        fields.append((name, length))
        pos += 32

    records: list[dict[str, str]] = []
    for i in range(record_count):
        start = header_length + i * record_length
        record = data[start : start + record_length]
        if not record or record[0:1] == b"*":
            continue

        offset = 1
        values: dict[str, str] = {}
        for name, length in fields:
            raw = record[offset : offset + length]
            values[name] = raw.decode(encoding, errors="replace").strip()
            offset += length
        records.append(values)

    return records


def iter_shp_polygons(path: Path) -> Iterable[tuple[tuple[float, float, float, float], list[list[tuple[float, float]]]]]:
    data = path.read_bytes()
    offset = 100
    while offset < len(data):
        if offset + 8 > len(data):
            break

        content_words = struct.unpack(">i", data[offset + 4 : offset + 8])[0]
        content_start = offset + 8
        content_end = content_start + content_words * 2
        content = data[content_start:content_end]
        offset = content_end

        shape_type = struct.unpack("<i", content[0:4])[0]
        if shape_type == 0:
            continue
        if shape_type != 5:
            raise ValueError(f"Unsupported shape type {shape_type} in {path}")

        bbox = struct.unpack("<4d", content[4:36])
        part_count = struct.unpack("<i", content[36:40])[0]
        point_count = struct.unpack("<i", content[40:44])[0]
        parts = list(struct.unpack(f"<{part_count}i", content[44 : 44 + 4 * part_count]))
        points_start = 44 + 4 * part_count

        points: list[tuple[float, float]] = []
        for i in range(point_count):
            point_start = points_start + i * 16
            points.append(struct.unpack("<2d", content[point_start : point_start + 16]))

        rings: list[list[tuple[float, float]]] = []
        for i, start in enumerate(parts):
            end = parts[i + 1] if i + 1 < len(parts) else len(points)
            ring = points[start:end]
            if len(ring) >= 4:
                rings.append(ring)

        yield bbox, rings


def load_municipalities(novadi_shp: Path, pilsetas_shp: Path) -> list[Municipality]:
    municipalities: list[Municipality] = []

    novadi_records = read_dbf(novadi_shp.with_suffix(".dbf"))
    for record, (bbox, rings) in zip(novadi_records, iter_shp_polygons(novadi_shp), strict=True):
        municipalities.append(
            Municipality(
                code=record["CODE"],
                atvk=record["ATVK"],
                label=record["LABEL"],
                source="Novadi",
                bbox=bbox,
                rings=prepare_rings(rings),
            )
        )

    pilsetas_records = read_dbf(pilsetas_shp.with_suffix(".dbf"))
    for record, (bbox, rings) in zip(pilsetas_records, iter_shp_polygons(pilsetas_shp), strict=True):
        if record.get("CITY_TYPE") != "2":
            continue
        municipalities.append(
            Municipality(
                code=record["CODE"],
                atvk=record["ATVK"],
                label=record["LABEL"],
                source="Valstspilseta",
                bbox=bbox,
                rings=prepare_rings(rings),
            )
        )

    municipalities.sort(key=lambda item: item.label)
    return municipalities


def prepare_rings(
    rings: list[list[tuple[float, float]]],
) -> tuple[tuple[tuple[float, float, float, float], tuple[tuple[float, float], ...]], ...]:
    prepared = []
    for ring in rings:
        xs = [point[0] for point in ring]
        ys = [point[1] for point in ring]
        prepared.append(((min(xs), min(ys), max(xs), max(ys)), tuple(ring)))
    return tuple(prepared)


def point_on_segment(x: float, y: float, ax: float, ay: float, bx: float, by: float) -> bool:
    cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
    if abs(cross) > 1e-7:
        return False
    return min(ax, bx) - 1e-7 <= x <= max(ax, bx) + 1e-7 and min(ay, by) - 1e-7 <= y <= max(ay, by) + 1e-7


def point_in_ring(x: float, y: float, ring: tuple[tuple[float, float], ...]) -> bool:
    inside = False
    previous_x, previous_y = ring[-1]

    for current_x, current_y in ring:
        if point_on_segment(x, y, previous_x, previous_y, current_x, current_y):
            return True

        crosses_y = (current_y > y) != (previous_y > y)
        if crosses_y:
            x_intersection = (previous_x - current_x) * (y - current_y) / (previous_y - current_y) + current_x
            if x < x_intersection:
                inside = not inside

        previous_x, previous_y = current_x, current_y

    return inside


def municipality_contains_point(municipality: Municipality, x: float, y: float) -> bool:
    min_x, min_y, max_x, max_y = municipality.bbox
    if not (min_x <= x <= max_x and min_y <= y <= max_y):
        return False

    # Shapefile polygon parts include outer rings and holes. Even/odd parity across
    # all rings correctly excludes holes while keeping multipart polygons simple.
    inside = False
    for ring_bbox, ring in municipality.rings:
        ring_min_x, ring_min_y, ring_max_x, ring_max_y = ring_bbox
        if not (ring_min_x <= x <= ring_max_x and ring_min_y <= y <= ring_max_y):
            continue
        if point_in_ring(x, y, ring):
            inside = not inside
    return inside


def find_municipality(municipalities: list[Municipality], x: float, y: float) -> Municipality | None:
    for municipality in municipalities:
        if municipality_contains_point(municipality, x, y):
            return municipality
    return None


def build_bbox_index(municipalities: list[Municipality]) -> dict[tuple[int, int], list[Municipality]]:
    index: dict[tuple[int, int], list[Municipality]] = {}
    for municipality in municipalities:
        min_x, min_y, max_x, max_y = municipality.bbox
        min_bucket_x = int(min_x // SPATIAL_INDEX_BUCKET_M)
        max_bucket_x = int(max_x // SPATIAL_INDEX_BUCKET_M)
        min_bucket_y = int(min_y // SPATIAL_INDEX_BUCKET_M)
        max_bucket_y = int(max_y // SPATIAL_INDEX_BUCKET_M)

        for bucket_x in range(min_bucket_x, max_bucket_x + 1):
            for bucket_y in range(min_bucket_y, max_bucket_y + 1):
                index.setdefault((bucket_x, bucket_y), []).append(municipality)
    return index


def find_municipality_indexed(
    bbox_index: dict[tuple[int, int], list[Municipality]], x: float, y: float
) -> Municipality | None:
    bucket = (int(x // SPATIAL_INDEX_BUCKET_M), int(y // SPATIAL_INDEX_BUCKET_M))
    candidates = bbox_index.get(bucket, [])
    return find_municipality(candidates, x, y)


def slugify(value: str) -> str:
    replacements = {
        "ā": "a",
        "č": "c",
        "ē": "e",
        "ģ": "g",
        "ī": "i",
        "ķ": "k",
        "ļ": "l",
        "ņ": "n",
        "š": "s",
        "ū": "u",
        "ž": "z",
    }
    value = "".join(replacements.get(ch, replacements.get(ch.lower(), ch)) for ch in value.lower())
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "municipality"


def cell_polygon_wkt(x: float, y: float, size_m: float = GRID_SIZE_M) -> str:
    half = size_m / 2
    coords = [
        (x - half, y - half),
        (x + half, y - half),
        (x + half, y + half),
        (x - half, y + half),
        (x - half, y - half),
    ]
    coord_text = ", ".join(f"{cx:.3f} {cy:.3f}" for cx, cy in coords)
    return f"POLYGON(({coord_text}))"


def write_outputs(
    rows: list[dict[str, str]],
    municipalities: list[Municipality],
    output_dir: Path,
    fragment_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fragment_dir.mkdir(parents=True, exist_ok=True)

    assigned_rows = [row for row in rows if row["municipality_code"]]
    unassigned_rows = [row for row in rows if not row["municipality_code"]]

    main_csv = output_dir / "grid_1km_municipalities_centroid.csv"
    with main_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary: dict[str, dict[str, object]] = {}
    for municipality in municipalities:
        summary[municipality.code] = {
            "municipality_code": municipality.code,
            "municipality_atvk": municipality.atvk,
            "municipality_name": municipality.label,
            "municipality_source": municipality.source,
            "grid_cell_count": 0,
        }

    for row in assigned_rows:
        summary[row["municipality_code"]]["grid_cell_count"] += 1

    summary_csv = output_dir / "municipality_grid_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "municipality_code",
            "municipality_atvk",
            "municipality_name",
            "municipality_source",
            "grid_cell_count",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary.values())

    unassigned_csv = output_dir / "grid_unassigned_centroids.csv"
    with unassigned_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(unassigned_rows)

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in assigned_rows:
        grouped.setdefault(row["municipality_code"], []).append(row)

    for municipality in municipalities:
        municipality_rows = grouped.get(municipality.code, [])
        fragment_csv = fragment_dir / f"{municipality.atvk}_{slugify(municipality.label)}.csv"
        with fragment_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(municipality_rows)

    metadata = {
        "method": "centroid",
        "grid_size_m": GRID_SIZE_M,
        "municipality_sources": {
            "Novadi.shp": "all 36 novadi",
            "Pilsetas.shp": "CITY_TYPE=2 only, i.e. valstspilsetas",
        },
        "total_grid_cells": len(rows),
        "assigned_grid_cells": len(assigned_rows),
        "unassigned_grid_cells": len(unassigned_rows),
        "outputs": {
            "grid_with_municipalities": str(main_csv),
            "municipality_summary": str(summary_csv),
            "unassigned_centroids": str(unassigned_csv),
            "municipality_fragments_dir": str(fragment_dir),
        },
    }
    (output_dir / "grid_assignment_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def assign_grid(grid_csv: Path, municipalities: list[Municipality]) -> list[dict[str, str]]:
    bbox_index = build_bbox_index(municipalities)
    rows: list[dict[str, str]] = []
    with grid_csv.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{grid_csv} has no header")

        for row in reader:
            x = float(row["x"])
            y = float(row["y"])
            municipality = find_municipality_indexed(bbox_index, x, y)
            row["grid_id"] = row.get("ID", "")
            row["centroid_x"] = f"{x:.4f}"
            row["centroid_y"] = f"{y:.4f}"
            row["cell_size_m"] = f"{GRID_SIZE_M:.0f}"
            row["municipality_code"] = municipality.code if municipality else ""
            row["municipality_atvk"] = municipality.atvk if municipality else ""
            row["municipality_name"] = municipality.label if municipality else ""
            row["municipality_source"] = municipality.source if municipality else ""
            row["cell_polygon_lks92_wkt"] = cell_polygon_wkt(x, y)
            rows.append(row)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assign Latvia 1x1 km grid cells to municipalities using the centroid method."
    )
    parser.add_argument("--grid", type=Path, default=Path("1x1_LV_grid_2024_xy2.csv"))
    parser.add_argument("--novadi", type=Path, default=Path("Novadi.shp"))
    parser.add_argument("--pilsetas", type=Path, default=Path("Pilsetas.shp"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--fragment-dir",
        type=Path,
        default=Path("outputs") / "municipality_grid_fragments",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    municipalities = load_municipalities(args.novadi, args.pilsetas)
    rows = assign_grid(args.grid, municipalities)
    write_outputs(rows, municipalities, args.output_dir, args.fragment_dir)

    assigned = sum(1 for row in rows if row["municipality_code"])
    print(f"Municipalities loaded: {len(municipalities)}")
    print(f"Grid cells total: {len(rows)}")
    print(f"Grid cells assigned: {assigned}")
    print(f"Grid cells unassigned: {len(rows) - assigned}")
    print(f"Outputs written to: {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
