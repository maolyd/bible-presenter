import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT))

# Run Qt widgets without opening windows during tests.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox")

from app.bible.importers import read_bible_file  # noqa: E402
from app.core import AppCore  # noqa: E402


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def mini_core(tmp_path):
    """An AppCore with the small English + French test excerpts installed."""
    core = AppCore(data_dir=tmp_path / "data", web_root=ROOT / "web", bundled_dir=tmp_path / "none")
    core.import_bible(read_bible_file(FIXTURES / "mini_en.usfx.xml"), name="Mini WEB", code="TWEB", language="en")
    core.import_bible(read_bible_file(FIXTURES / "mini_fr.beblia.xml"), name="Mini LSG", code="TLSG", language="fr")
    yield core
    core.close()


@pytest.fixture
def range_core(mini_core):
    """mini_core showing the whole selected passage on one slide, full screen."""
    mini_core.update_style(verses_per_slide=0, display_mode="fullscreen")
    return mini_core


@pytest.fixture(scope="session")
def full_core(tmp_path_factory):
    """AppCore with the complete bundled KJV and LSG Bibles (skipped if the files are absent)."""
    bundled = ROOT / "data" / "bibles"
    if not (bundled / "catalog.json").is_file():
        pytest.skip("bundled Bible files not present")
    core = AppCore(data_dir=tmp_path_factory.mktemp("full"), web_root=ROOT / "web", bundled_dir=bundled)
    for entry in core.bundled_catalog():
        core.import_bundled(entry)
    yield core
    core.close()
