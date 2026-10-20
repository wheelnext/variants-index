"""Migrate v0.0.2 or v0.0.3 wheels into a separate directory for publication."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from variantlib.variants_json import VariantsJson
from wheel.wheelfile import WheelFile

from src.metadata import metadata_json
from src.metadata import read_variant
from src.metadata import wheel_parts
from src.schemas.v0_0_2 import WheelVariantJSON_V0_0_2
from src.schemas.v0_0_3 import WheelVariantJSON_V0_0_3

LEGACY_SCHEMA = "https://variants-schema.wheelnext.dev/"


def convert_metadata(old: dict[str, Any]) -> VariantsJson:
    if old["$schema"] == LEGACY_SCHEMA:
        old = {**old, "$schema": LEGACY_SCHEMA + "v0.0.2.json"}
    if old["$schema"] == LEGACY_SCHEMA + "v0.0.2.json":
        legacy = WheelVariantJSON_V0_0_2.model_validate(old).to_v0_0_3()
    else:
        legacy = WheelVariantJSON_V0_0_3.model_validate(old)

    static = legacy.static_properties or {}
    priorities = legacy.default_priorities
    providers = {}
    for ns, previous in legacy.providers.items():
        provider = previous.model_dump(include={"optional"}, exclude_none=True)
        if previous.install_time is False:
            provider["static-properties"] = {
                feature: values.root for feature, values in static[ns].items()
            }
            if order := priorities.feature.get(ns):
                provider["feature-order"] = order
        elif ns in static or not previous.requires:
            raise ValueError(f"Expected an install-time provider for {ns}")
        else:
            provider["requires"] = previous.requires
            if previous.plugin_api:
                provider["plugin-api"] = previous.plugin_api
        providers[ns] = provider

    return VariantsJson(
        {
            "default-priorities": {"namespace": priorities.namespace},
            "providers": providers,
            "variants": legacy.variants,
        }
    )


def migrate(wheel: Path, directory: Path, *, metadata: Path | None = None) -> None:
    namever, original_label = wheel_parts(wheel.name)
    if original_label is None:
        raise ValueError(f"Expected a variant label in {wheel}")
    label = original_label
    name = wheel.name
    if original_label == "00000000":
        label = "null"
        name = name.removesuffix("-00000000.whl") + "-null.whl"
    dest = directory / name
    if dest.exists():
        raise FileExistsError(f"Output wheel already exists: {dest}")

    variant_json = f"{namever}.dist-info/variant.json"
    # WheelFile checks the source RECORD hashes and writes the new RECORD.
    with WheelFile(wheel) as src:
        old = json.loads(src.read(variant_json))
        if metadata is not None:
            if metadata.name != f"{namever}-variants.json":
                raise ValueError(f"{metadata.name} does not describe {wheel.name}")
            if set(old["variants"]) != {original_label}:
                raise ValueError(f"{wheel.name} must describe only {original_label}")
            old = json.loads(metadata.read_text(encoding="utf-8"))
            old["variants"] = {original_label: old["variants"][original_label]}
        data = metadata_json(convert_metadata(old))
        read_variant(json.loads(data), label)
        if any(n.endswith(("/RECORD.jws", "/RECORD.p7s")) for n in src.namelist()):
            raise ValueError(f"Cannot migrate signed wheel: {wheel}")
        directory.mkdir(parents=True, exist_ok=True)
        # Only expose the wheel after all source RECORD hashes have been checked.
        with tempfile.TemporaryDirectory(dir=directory) as tmp:
            staged = Path(tmp) / name
            with WheelFile(staged, "w") as out:
                for member in src.infolist():
                    if member.filename == src.record_path:
                        continue
                    content = (
                        data if member.filename == variant_json else src.read(member)
                    )
                    out.writestr(member, content)
            dest.hardlink_to(staged)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Build the index with main.py --wheel-dir OUTPUT. Publish at a new "
            "version or URL, and check that provider plugins implement PEP 850."
        ),
    )
    parser.add_argument("--output", required=True, type=Path, help="write wheels here")
    parser.add_argument(
        "--metadata",
        type=Path,
        help="use the publisher's corrected metadata for this release",
    )
    parser.add_argument("wheels", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.wheels:
        migrate(path, args.output, metadata=args.metadata)
