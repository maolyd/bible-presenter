# PyInstaller build recipe for Bible Presenter.  Build with:  scripts\build_windows.ps1
# Produces a portable folder: dist\BiblePresenter\BiblePresenter.exe
from PyInstaller.utils.hooks import collect_submodules

datas = [
    ("web", "web"),                          # OBS output page (HTML/CSS/JS)
    ("app/resources", "app/resources"),      # window icon
    ("data/bibles", "data/bibles"),          # bundled public-domain Bibles + catalog.json
    ("data/sample", "data/sample"),
    ("LICENSES.md", "."),
    ("README.md", "."),
    ("docs", "docs"),
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=collect_submodules("app") + ["PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore"],
    excludes=["tkinter", "PySide6.Qt3DCore", "PySide6.QtQuick3D", "PySide6.QtCharts", "PySide6.QtDataVisualization",
              "PySide6.QtMultimedia", "PySide6.QtBluetooth", "PySide6.QtSensors", "PySide6.QtSerialPort"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BiblePresenter",
    console=False,          # no black console window
    icon="app/resources/bible-presenter.ico",
    upx=False,              # UPX-compressed files trigger more antivirus false positives
)
coll = COLLECT(exe, a.binaries, a.datas, name="BiblePresenter", upx=False)
