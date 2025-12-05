from __future__ import annotations

from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import RootModel

# ---------------------------------------------------------------------------
# Default Priorities
# ---------------------------------------------------------------------------


class DefaultPriorities(BaseModel):
    namespace: Annotated[list[str], Field(min_length=1)]
    feature: Annotated[dict[str, list[str]], Field(default_factory=dict)]
    property: Annotated[dict[str, dict[str, list[str]]], Field(default_factory=dict)]

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class Provider(BaseModel):
    plugin_api: Annotated[str | None, Field(None, alias="plugin-api")]
    enable_if: Annotated[str | None, Field(None, alias="enable-if")]
    install_time: Annotated[bool | None, Field(None, alias="install-time")]
    optional: Annotated[bool | None, Field(None)]
    requires: Annotated[list[str] | None, Field(default=None)]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


Providers = dict[str, Provider]


# ---------------------------------------------------------------------------
# Static Properties
# ---------------------------------------------------------------------------


class StaticFeature(RootModel[list[str]]):
    """Each feature is a list of possible values"""


StaticProperties = dict[
    str, dict[str, StaticFeature]
]  # namespace -> feature -> RootModel[list[str]]


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------

VariantFeatureValues = list[str]
VariantFeatureMap = dict[str, VariantFeatureValues]
VariantNamespaceMap = dict[str, VariantFeatureMap]
Variants = dict[str, VariantNamespaceMap]


# ---------------------------------------------------------------------------
# Root Model
# ---------------------------------------------------------------------------


class WheelVariantJSON_V0_0_3(BaseModel):  # noqa: N801
    json_schema: Annotated[
        Literal["https://variants-schema.wheelnext.dev/v0.0.3.json"],
        Field(description="Schema version URL", alias="$schema"),
    ] = "https://variants-schema.wheelnext.dev/v0.0.3.json"

    default_priorities: Annotated[
        DefaultPriorities, Field(..., alias="default-priorities")
    ]
    providers: Annotated[Providers, Field(...)]
    static_properties: Annotated[
        StaticProperties | None, Field(default=None, alias="static-properties")
    ]
    variants: Annotated[Variants, Field(...)]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ---------------------------------------------------------------------------
# Example Usage
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    example_data = {
        "$schema": "https://variants-schema.wheelnext.dev/v0.0.3.json",
        "default-priorities": {"namespace": ["x86_64", "aarch64", "blas_lapack"]},
        "providers": {
            "aarch64": {
                "enable-if": "platform_machine == 'aarch64' or 'arm' in platform_machine",  # noqa: E501
                "plugin-api": "provider_variant_aarch64.plugin:AArch64Plugin",
                "requires": ["provider-variant-aarch64"],
            },
            "blas_lapack": {
                "install-time": False,
                "requires": ["blas-lapack-variant-provider"],
            },
            "x86_64": {
                "enable-if": "platform_machine == 'x86_64' or platform_machine == 'AMD64'",  # noqa: E501
                "plugin-api": "provider_variant_x86_64.plugin:X8664Plugin",
                "requires": ["provider-variant-x86-64"],
            },
        },
        "static-properties": {
            "blas_lapack": {"provider": ["accelerate", "openblas", "mkl"]}
        },
        "variants": {
            "accelerate": {"blas_lapack": {"provider": ["accelerate"]}},
            "openblas": {"blas_lapack": {"provider": ["openblas"]}},
            "x8664v4_mkl": {
                "blas_lapack": {"provider": ["mkl"]},
                "x86_64": {"level": ["v4"]},
            },
        },
    }

    instance = WheelVariantJSON_V0_0_3.model_validate(example_data)
    print("Validation OK")  # noqa: T201
    print(instance.model_dump_json(indent=2, exclude_none=True, by_alias=True))  # noqa: T201
