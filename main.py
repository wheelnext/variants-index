from __future__ import annotations

import argparse
import contextlib
import shutil
import tempfile
from pathlib import Path

import tomlkit

from src.build import BUILD_DIR
from src.build import PkgConfig
from src.build import generate_main_index
from src.build import generate_project_index
from src.build import index_local_wheels
from src.demo import build_demo

CONFIG_FILEPATH = Path("index.toml")


def configured_packages() -> dict[str, PkgConfig]:
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
    return packages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the PEP 825 / 850 demo index")
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument("--demo-only", action="store_true", help="only build the demo")
    sources.add_argument(
        "--wheel-dir", type=Path, help="add local wheels and skip upstream indexes"
    )
    args = parser.parse_args()
    if (source := args.wheel_dir) is not None:
        if not source.is_dir():
            parser.error(f"--wheel-dir must be an existing directory: {source}")
        if source.resolve().is_relative_to(BUILD_DIR.resolve()):
            parser.error(f"--wheel-dir must be outside the build directory: {source}")

    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(BUILD_DIR)

    BUILD_DIR.mkdir(exist_ok=True, parents=True)

    with tempfile.TemporaryDirectory() as tmp:
        build_demo(Path(tmp))
        index_local_wheels(BUILD_DIR, Path(tmp))
    if source is not None:
        index_local_wheels(BUILD_DIR, source)
    elif not args.demo_only:
        for package in configured_packages().values():
            generate_project_index(package)

    generate_main_index(packages=[p.name for p in BUILD_DIR.iterdir()])
