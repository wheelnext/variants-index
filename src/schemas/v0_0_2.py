from __future__ import annotations

from typing import Annotated
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from src.schemas.v0_0_3 import DefaultPriorities as DefaultPriorities_v3
from src.schemas.v0_0_3 import Provider as Provider_v3
from src.schemas.v0_0_3 import StaticFeature as StaticFeature_v3
from src.schemas.v0_0_3 import WheelVariantJSON_V0_0_3

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
    optional: Annotated[bool | None, Field(None)]
    plugin_use: Annotated[str | None, Field(None, alias="plugin-use")]
    requires: Annotated[list[str] | None, Field(default=None)]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


Providers = dict[str, Provider]


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


class WheelVariantJSON_V0_0_2(BaseModel):  # noqa: N801
    json_schema: Annotated[
        Literal["https://variants-schema.wheelnext.dev/v0.0.2.json"],
        Field(description="Schema version URL", alias="$schema"),
    ] = "https://variants-schema.wheelnext.dev/v0.0.2.json"

    default_priorities: Annotated[
        DefaultPriorities, Field(..., alias="default-priorities")
    ]
    providers: Annotated[Providers, Field(...)]
    variants: Annotated[Variants, Field(...)]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def to_v0_0_3(self) -> WheelVariantJSON_V0_0_3:
        """
        Convert a v0.0.2 WheelVariantJSON to v0.0.3
        """
        # Convert default_priorities
        dp_v3 = DefaultPriorities_v3.model_validate(
            self.default_priorities.model_dump()
        )

        # Convert providers
        prov_v3 = {}
        for name, provider in self.providers.items():
            _data = provider.model_dump(exclude_none=True)
            _data["install-time"] = _data.pop("plugin_use", "all") == "all"
            prov_v3[name] = _data

        # Copy variants directly
        variants_v3 = self.variants

        # Build static-properties from default_priorities.property
        static_props = {}
        for namespace, feature_map in self.default_priorities.property.items():
            static_props[namespace] = {}
            for feature_name, prop_list in feature_map.items():
                static_props[namespace][feature_name] = prop_list

        return WheelVariantJSON_V0_0_3.model_validate(
            {
                "default_priorities": dp_v3,
                "providers": prov_v3,
                "static_properties": static_props,
                "variants": variants_v3,
            }
        )


if __name__ == "__main__":
    # Example data matching the schema
    example_data = {
        "$schema": "https://variants-schema.wheelnext.dev/v0.0.2.json",
        "default_priorities": {
            "namespace": ["cpu", "gpu"],
            "feature": {"cpu": ["x86", "arm"], "gpu": ["cuda", "opencl"]},
            "property": {
                "cpu": {"x86": ["sse2", "avx", "avx2"], "arm": ["neon"]},
                "gpu": {"cuda": ["compute_50", "compute_60"], "opencl": ["1.2", "2.0"]},
            },
        },
        "providers": {
            "cpu_provider": {
                "plugin_api": "my_module:CPUProvider",
                "enable_if": "platform_machine == 'x86_64'",
                "optional": False,
                "plugin_use": "build",
                "requires": ["numpy>=1.20"],
            },
            "gpu_provider": {
                "plugin_api": "my_module:GPUProvider",
                "plugin_use": "none",
            },
        },
        "variants": {
            "cpu_opt": {"cpu": {"x86": ["sse2", "avx2"], "arm": ["neon"]}},
            "gpu_cuda": {"gpu": {"cuda": ["compute_60"]}},
        },
    }

    # Validate the example data
    index = WheelVariantJSON_V0_0_2.model_validate(example_data)
    print("Validation successful!")  # noqa: T201
    print(index.model_dump_json(exclude_none=True, indent=2, by_alias=True))  # noqa: T201
