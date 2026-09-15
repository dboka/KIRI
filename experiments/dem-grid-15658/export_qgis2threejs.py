"""Export KIRI grid 27105 as a Qgis2threejs web scene.

Run this script with the Python environment bundled with QGIS. The source DEM
remains the 1 m LĢIA-derived GeoTIFF; the browser mesh is resampled to a smaller
grid so the embedded viewer stays responsive.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[2]
    default_dem = (
        repo_root.parent
        / "test_DEM"
        / "processed"
        / "27105"
        / "grid_27105_dtm_1m.tif"
    )
    default_texture = (
        repo_root
        / "GRID_SAGATAVE"
        / "frontend"
        / "data"
        / "dem"
        / "27105"
        / "dem_combined.png"
    )
    default_output = default_texture.parent / "qgis2threejs" / "grid-27105.html"

    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-dir", type=Path, help="Path to the Qgis2threejs plugin folder")
    parser.add_argument("--dem", type=Path, default=default_dem)
    parser.add_argument("--texture", type=Path, default=default_texture)
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument(
        "--mesh-level",
        type=int,
        default=3,
        choices=range(1, 11),
        help="Qgis2threejs DEM size level; 3 creates an approximately 300 x 300 mesh",
    )
    return parser.parse_args()


def find_plugin_dir(value: Path | None) -> Path:
    candidates = []
    if value:
        candidates.append(value)
    if os.environ.get("QGIS2THREEJS_PLUGIN_DIR"):
        candidates.append(Path(os.environ["QGIS2THREEJS_PLUGIN_DIR"]))
    if os.environ.get("APPDATA"):
        candidates.append(
            Path(os.environ["APPDATA"])
            / "QGIS"
            / "QGIS3"
            / "profiles"
            / "default"
            / "python"
            / "plugins"
            / "Qgis2threejs"
        )

    for candidate in candidates:
        candidate = candidate.resolve()
        if (candidate / "qgis2threejs.py").exists() and candidate.name == "Qgis2threejs":
            return candidate
    raise FileNotFoundError(
        "Qgis2threejs plugin was not found. Install version 2.10.x in QGIS or pass --plugin-dir."
    )


def main() -> int:
    args = parse_args()
    plugin_dir = find_plugin_dir(args.plugin_dir)
    dem_path = args.dem.resolve()
    texture_path = args.texture.resolve()
    output_path = args.output.resolve()

    for source in (dem_path, texture_path):
        if not source.exists():
            raise FileNotFoundError(source)

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(plugin_dir.parent))

    from osgeo import gdal
    from qgis.PyQt.QtCore import QSize
    from qgis.PyQt.QtGui import QColor
    from qgis.core import QgsApplication, QgsMapSettings, QgsProject, QgsRasterLayer

    gdal.UseExceptions()

    qgis_prefix = os.environ.get("QGIS_PREFIX_PATH")
    if qgis_prefix:
        QgsApplication.setPrefixPath(qgis_prefix, True)

    app = QgsApplication([], False)
    app.initQgis()

    try:
        from Qgis2threejs.core.const import DEMMtlType
        from Qgis2threejs.core.export.export import ThreeJSExporter
        from Qgis2threejs.core.exportsettings import ExportSettings

        project = QgsProject.instance()
        project.clear()

        dem_layer = QgsRasterLayer(str(dem_path), "KIRI 27105 · 1 m DTM", "gdal")
        if not dem_layer.isValid():
            raise RuntimeError(f"QGIS could not open DEM: {dem_path}")
        project.addMapLayer(dem_layer)

        extent = dem_layer.extent()
        map_settings = QgsMapSettings()
        map_settings.setDestinationCrs(dem_layer.crs())
        map_settings.setExtent(extent)
        map_settings.setOutputSize(QSize(1200, 1200))
        map_settings.setLayers([dem_layer])
        map_settings.setBackgroundColor(QColor("#07151d"))

        settings = ExportSettings()
        settings.initialize(map_settings)
        settings.setTitle("KIRI · režģa šūna 27105 · 1 m reljefs")
        settings.setTemplate("3DViewer.html")
        settings.setCamera(False)
        settings.setControls("OrbitControls.js")
        settings.setNavigationEnabled(True)
        settings.setWidgetProperties("NorthArrow", {"visible": True, "color": "#63d8c5"})
        settings.setHeaderLabel("")
        settings.setFooterLabel("")
        settings.setSceneProperties(
            {
                "radioButton_FixedExtent": True,
                "checkBox_FixAspectRatio": True,
                "lineEdit_CenterX": str(extent.center().x()),
                "lineEdit_CenterY": str(extent.center().y()),
                "lineEdit_Width": str(extent.width()),
                "lineEdit_Height": str(extent.height()),
                "lineEdit_Rotation": "0",
                "lineEdit_zFactor": "3.2",
                "comboBox_xyShift": True,
                "radioButton_Color": True,
                "colorButton_Color": [7, 21, 29, 255],
                "radioButton_NoCoords": False,
                "radioButton_PtLight": False,
                "groupBox_Fog": False,
            }
        )
        settings.updateLayers()

        dem = settings.getLayer(dem_layer.id())
        if dem is None:
            raise RuntimeError("Qgis2threejs did not register the DEM layer")

        material_id = "kiri-relief"
        dem.visible = True
        dem.properties = {
            "checkBox_Clickable": True,
            "checkBox_Visible": True,
            "radioButton_OriginalValues": False,
            "radioButton_ClipExtent": True,
            "radioButton_ClipPolygon": False,
            "radioButton_NoClip": False,
            "horizontalSlider_DEMSize": args.mesh_level,
            "checkBox_Tiles": False,
            "spinBox_Roughening": 1,
            "spinBox_Size": 1,
            "checkBox_Sides": True,
            "checkBox_Frame": True,
            "checkBox_Wireframe": False,
            "lineEdit_Bottom": "28",
            "colorButton_Side": [19, 55, 63, 255],
            "colorButton_Edge": [105, 225, 205, 255],
            "colorButton_Wireframe": [105, 225, 205, 100],
            "materials": [
                {
                    "id": material_id,
                    "name": "LĢIA 1 m reljefs",
                    "type": DEMMtlType.FILE,
                    "properties": {
                        "lineEdit_ImageFile": str(texture_path),
                        "spinBox_Opacity": 100,
                        "checkBox_Shading": True,
                        "checkBox_TransparentBackground": False,
                    },
                }
            ],
            "mtlId": material_id,
        }
        settings.setLayer(dem)
        settings.localMode = False
        settings.requiresJsonSerializable = False
        settings.setOutputFilename(str(output_path))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        exporter = ThreeJSExporter(settings=settings)
        exporter.export()

        theme_name = "kiri-qgis2threejs.css"
        html = output_path.read_text(encoding="utf-8")
        theme_link = f'<link rel="stylesheet" type="text/css" href="./{theme_name}">'
        html = html.replace("</head>", f"{theme_link}\n</head>")
        output_path.write_text(html, encoding="utf-8")
        (output_path.parent / theme_name).write_text(
            """/* KIRI shell integration for the generated Qgis2threejs viewer. */
html, body, #view { background: #07151d; }
#toolbtns, #popup, #header, #footer { display: none !important; }
#progress { z-index: 1200; }
#progressbar { background: #69cfbb; }
canvas { outline: none; }
""",
            encoding="utf-8",
        )

        license_source = plugin_dir / "LICENSE"
        if license_source.exists():
            shutil.copy2(license_source, output_path.parent / "QGIS2THREEJS-LICENSE.txt")

        print(f"Exported: {output_path}")
        return 0
    finally:
        QgsProject.instance().clear()
        app.exitQgis()


if __name__ == "__main__":
    raise SystemExit(main())
