"""PEP 825 wheel and index metadata, with PEP 850 providers."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from variantlib.constants import VALIDATION_WHEEL_NAME_REGEX
from variantlib.variant_dist_info import VariantDistInfo

if TYPE_CHECKING:
    from variantlib.variants_json import VariantsJson

SCHEMA = "https://variants-schema.wheelnext.dev/peps/850/v0.2.0.json"


def wheel_parts(filename: str) -> tuple[str, str | None]:
    match = VALIDATION_WHEEL_NAME_REGEX.fullmatch(filename)
    if match is None or match["pyver"][0].isdigit():
        raise ValueError(f"Invalid wheel filename: {filename}")
    return match["namever"], match["variant_label"]


def metadata_json(metadata: VariantsJson) -> str:
    # variantlib 0.2.0 implements the provider format but emits the old schema URL.
    data = json.loads(metadata.to_str())
    data["$schema"] = SCHEMA
    return json.dumps(data, indent=2) + "\n"


def read_variant(data: bytes | str, label: str) -> VariantDistInfo:
    schema = json.loads(data).get("$schema")
    if schema != SCHEMA:
        raise ValueError(f"Expected {SCHEMA}, got {schema}")
    return VariantDistInfo(data, expected_label=label)
