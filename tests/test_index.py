from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch


from src.build import PkgConfig
from src.build import VariantJson
from src.build import VariantWheel
from src.build import generate_project_index


class TestIndex(unittest.TestCase):
    def test_legacy_only_release_stays_on_the_legacy_index(self) -> None:
        wheel = "example-1-py3-none-any-null.whl"
        sidecar = "example-1-variants.json"
        links = [VariantWheel(wheel, wheel, ""), VariantJson(sidecar, sidecar, "")]
        old = {"$schema": "https://variants-schema.wheelnext.dev/v0.0.3.json"}
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("src.build.BUILD_DIR", Path(tmp)),
            patch("src.build.fetch_links", return_value=links),
            patch("src.build.requests.get", return_value=Mock(json=lambda: old)),
        ):
            generate_project_index(PkgConfig("example", "https://example.com/"))
            assert not (Path(tmp) / "example").exists()
