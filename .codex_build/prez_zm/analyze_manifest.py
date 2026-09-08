from pathlib import Path
import json
from statistics import mean

path = Path(r"C:/Users/deniss.boka/MESLI_PROJECT/KIRI/GRID_SAGATAVE/frontend/data/calendar_manifest.json")
data = json.loads(path.read_text(encoding="utf-8"))
rows = []
for item in data["dates"]:
    total = sum(int(v) for v in item["risk_counts"].values())
    rows.append({
        "date": item["date"],
        "total": total,
        "r3": item["risk_counts"].get("3", 0),
        "r4": item["risk_counts"].get("4", 0),
        "r5": item["risk_counts"].get("5", 0),
        "r45_pct": round((item["risk_counts"].get("4", 0) + item["risk_counts"].get("5", 0)) / total * 100, 1),
        "r5_pct": round(item["risk_counts"].get("5", 0) / total * 100, 1),
        "swi_missing": item.get("swi_missing"),
        "hsaf_missing": item.get("hsaf_missing"),
        "top_reasons": item.get("validation_summary", {}).get("top_active_reasons", {}),
        "confidence": item.get("validation_summary", {}).get("confidence_distribution", {}),
    })
latest = rows[-1]
top_r45 = sorted(rows, key=lambda r: r["r45_pct"], reverse=True)[:5]
top_r5 = sorted(rows, key=lambda r: r["r5_pct"], reverse=True)[:5]
sample_dates = [rows[0], rows[len(rows)//4], rows[len(rows)//2], rows[(len(rows)*3)//4], latest]
summary = {
    "date_range": data.get("dates", [{}])[0].get("date") + " to " + data.get("dates", [{}])[-1].get("date"),
    "date_count": data.get("date_count"),
    "default_date": data.get("default_date"),
    "municipality_count": data.get("dates", [{}])[-1].get("municipality_count"),
    "row_count_latest": latest["total"],
    "latest": latest,
    "top_r45": top_r45,
    "top_r5": top_r5,
    "sample_dates": sample_dates,
    "avg_r45_pct": round(mean(r["r45_pct"] for r in rows), 1),
}
out = Path(r"C:/Users/deniss.boka/MESLI_PROJECT/KIRI/.codex_build/prez_zm/manifest_analysis.json")
out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
