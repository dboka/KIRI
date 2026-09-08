from pathlib import Path
import shutil
import zipfile
from tempfile import TemporaryDirectory

workspace = Path(r"C:/Users/deniss.boka/MESLI_PROJECT/KIRI")
pptx = workspace / "outputs" / "zm_prez_20260909" / "PREZ_ZM_KIRI_2026-09-09.pptx"
root_pptm = workspace / "PREZ.pptm"
backup = workspace / "PREZ_original_before_ZM_20260907.pptm"
named_pptm = workspace / "PREZ_ZM_KIRI_2026-09-09.pptm"

if root_pptm.exists() and not backup.exists():
    shutil.copy2(root_pptm, backup)

with TemporaryDirectory() as td:
    tmp = Path(td)
    with zipfile.ZipFile(pptx, "r") as zin:
        zin.extractall(tmp)

    content_types = tmp / "[Content_Types].xml"
    xml = content_types.read_text(encoding="utf-8")
    xml = xml.replace(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
        "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml",
    )
    content_types.write_text(xml, encoding="utf-8")

    for target in [named_pptm, root_pptm]:
        if target.exists():
            target.unlink()
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for file in tmp.rglob("*"):
                if file.is_file():
                    zout.write(file, file.relative_to(tmp).as_posix())

print({
    "backup": str(backup),
    "updated_pptm": str(root_pptm),
    "named_pptm": str(named_pptm),
})
