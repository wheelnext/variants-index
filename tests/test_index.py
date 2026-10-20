from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch
from zipfile import ZipFile

from bs4 import BeautifulSoup
from wheel.wheelfile import WheelError
from wheel.wheelfile import WheelFile

from src.build import PkgConfig
from src.build import VariantJson
from src.build import VariantWheel
from src.build import generate_project_index
from src.build import index_local_wheels
from src.build import sha256sum
from src.metadata import SCHEMA
from src.migrate import LEGACY_SCHEMA
from src.migrate import convert_metadata
from src.migrate import migrate


class TestIndex(unittest.TestCase):
    def test_migrate_wheel_and_derive_index_metadata(self) -> None:
        # Old null label and a label longer than the prototype's 16-character limit.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            new = root / "migrated"
            build = root / "build"
            labels = {"00000000": "null", "portable_reference_build": "portable"}
            for label, flavor in labels.items():
                wheel = root / f"example-1-py3-none-any-{label}.whl"
                properties = (
                    {} if flavor == "null" else {"example": {"flavor": [flavor]}}
                )
                old = {
                    "$schema": LEGACY_SCHEMA + "v0.0.2.json",
                    "default-priorities": {
                        "namespace": ["example"],
                        "property": {"example": {"flavor": ["portable"]}},
                    },
                    "providers": {"example": {"plugin-use": "none"}},
                    "variants": {label: properties},
                }
                with WheelFile(wheel, "w") as whl:
                    whl.writestr("example.py", "pass\n")
                    whl.writestr("example-1.dist-info/variant.json", json.dumps(old))
                migrate(wheel, new)

            index_local_wheels(build, new)
            project = build / "example"
            metadata = json.loads((project / "example-1-variants.json").read_text())
            assert metadata["$schema"] == SCHEMA
            assert set(metadata["variants"]) == {"portable_reference_build", "null"}
            page = BeautifulSoup((project / "index.html").read_bytes(), "html.parser")
            links = page.select('a[href*="#sha256="]')
            assert len(links) == 3
            for link in links:
                filename, digest = link["href"].split("#sha256=")
                path = project / filename
                assert sha256sum(path) == digest
                if path.suffix == ".whl":
                    label = path.stem.rsplit("-", 1)[1]
                    with WheelFile(path) as whl:
                        # WheelFile verifies these contents against RECORD.
                        assert whl.read("example.py") == b"pass\n"
                        inside = json.loads(
                            whl.read("example-1.dist-info/variant.json")
                        )
                    expected = {label: metadata["variants"][label]}
                    assert inside == {**metadata, "variants": expected}

            # A failed migration must not leave a partial wheel for the indexer.
            damaged = root / "damaged" / wheel.name
            damaged.parent.mkdir()
            with ZipFile(wheel) as src, ZipFile(damaged, "w") as out:
                for member in src.namelist():
                    data = src.read(member)
                    out.writestr(member, b"corrupt" if member == "example.py" else data)
            destination = root / "incomplete"
            with self.assertRaisesRegex(WheelError, "Hash mismatch"):  # noqa: PT027
                migrate(damaged, destination)
            assert not list(destination.iterdir())

    def test_property_priority_does_not_replace_an_install_time_plugin(self) -> None:
        for version in ("0.0.2", "0.0.3"):
            old = {
                "$schema": f"{LEGACY_SCHEMA}v{version}.json",
                "default-priorities": {
                    "namespace": ["gpu"],
                    "property": {"gpu": {"cuda": ["13"]}},
                },
                "providers": {"gpu": {"requires": ["gpu-provider"]}},
                "variants": {"cuda13": {"gpu": {"cuda": ["13"]}}},
            }
            provider = convert_metadata(old).providers_dict()["gpu"]
            assert provider["requires"] == ["gpu-provider"]
            assert "static-properties" not in provider

    def test_legacy_only_release_stays_on_the_legacy_index(self) -> None:
        wheel = "example-1-py3-none-any-null.whl"
        sidecar = "example-1-variants.json"
        links = [VariantWheel(wheel, wheel, ""), VariantJson(sidecar, sidecar, "")]
        old = {"$schema": LEGACY_SCHEMA + "v0.0.3.json"}
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("src.build.BUILD_DIR", Path(tmp)),
            patch("src.build.fetch_links", return_value=links),
            patch("src.build.requests.get", return_value=Mock(json=lambda: old)),
        ):
            generate_project_index(PkgConfig("example", "https://example.com/"))
            assert not (Path(tmp) / "example").exists()
