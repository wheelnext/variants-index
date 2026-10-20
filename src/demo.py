"""Build a small, installable example that works without a provider plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING

from variantlib.variants_json import VariantsJson
from wheel.wheelfile import WheelFile

from src.metadata import metadata_json

if TYPE_CHECKING:
    from pathlib import Path

DEMO = "wheelnext-variant-demo"


def build_demo(directory: Path) -> None:
    namever = DEMO.replace("-", "_") + "-1.0"
    dist_info = f"{namever}.dist-info"
    for label, properties in (
        ("portable", {"demo": {"flavor": ["portable"]}}),
        ("null", {}),
    ):
        metadata = VariantsJson(
            {
                "default-priorities": {"namespace": ["demo"]},
                "providers": {"demo": {"static-properties": {"flavor": ["portable"]}}},
                "variants": {label: properties},
            }
        )
        with WheelFile(directory / f"{namever}-py3-none-any-{label}.whl", "w") as whl:
            whl.writestr("wheelnext_variant_demo.py", f'variant = "{label}"\n')
            whl.writestr(
                f"{dist_info}/METADATA",
                f"Metadata-Version: 2.4\nName: {DEMO}\nVersion: 1.0\n",
            )
            whl.writestr(
                f"{dist_info}/WHEEL",
                "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
            )
            whl.writestr(f"{dist_info}/variant.json", metadata_json(metadata))
