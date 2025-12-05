from __future__ import annotations

import contextlib
import shutil
from pathlib import Path

import tomlkit

from src.build import BUILD_DIR
from src.build import PkgConfig
from src.build import generate_main_index
from src.build import generate_project_index

CONFIG_FILEPATH = Path("index.toml")


if __name__ == "__main__":
    with CONFIG_FILEPATH.open(mode="r", encoding="utf-8") as f:
        config = tomlkit.parse(f.read())

    packages: dict[str, PkgConfig] = {}

    # Validate no 2 indexes are declared to
    # be authoritative for the same package:
    for index_cfg in config["index"]:
        for package_name in index_cfg["packages"]:
            if (package_name) in packages:
                raise ValueError(
                    f"Package `{package_name}` is declared for two indexes:"
                    f"\n\t- {packages[package_name].registry}"
                    f"\n\t- {index_cfg['registry']}"
                )

            packages[package_name] = PkgConfig(
                name=package_name,
                registry=index_cfg["registry"],
            )

    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(exist_ok=True, parents=True)

    generate_main_index(packages=list(packages.keys()))

    for package in sorted(packages.values(), key=lambda x: x.name):
        generate_project_index(package)
