from __future__ import annotations

import datetime
import hashlib
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import jinja2
import requests
from bs4 import BeautifulSoup
from packaging.utils import canonicalize_name
from packaging.version import Version
from variantlib.constants import VALIDATION_WHEEL_NAME_REGEX
from variantlib.variants_json import VariantsJson

from src.metadata import SCHEMA
from src.metadata import metadata_json
from src.metadata import read_variant
from src.metadata import wheel_parts

if TYPE_CHECKING:
    from collections.abc import Iterable

BUILD_DIR = Path("build")
BUILD_DATE = datetime.datetime.now(tz=ZoneInfo("America/New_York")).strftime(
    "%Y-%m-%d %H:%M"
)

VARIANT_JSON_FILE_REGEX = re.compile(r"\S*-(.*)-variants\.json")


def sha256sum(path: Path, chunk_size: int = 8192) -> str:
    """Compute the SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class PkgConfig:
    name: str
    registry: str


@dataclass(frozen=True)
class Artifact:
    name: str
    link: str
    checksum: str

    def re_match(self, regex: re.Pattern[str]) -> re.Match[str]:
        match = regex.fullmatch(self.name)
        if match is None:
            raise ValueError(f"Impossible to match the regex with `{self.name}`")

        return match


@dataclass(frozen=True)
class VariantJson(Artifact):
    @property
    def version(self) -> str:
        return self.re_match(VARIANT_JSON_FILE_REGEX).group(1)

    @classmethod
    def from_file(cls, fp: Path) -> VariantJson:
        return VariantJson(name=fp.name, link=fp.name, checksum=sha256sum(fp))


@dataclass(frozen=True)
class VariantWheel(Artifact):
    vprops: list[str] | None = None

    @property
    def version(self) -> str:
        return self.re_match(VALIDATION_WHEEL_NAME_REGEX).group("ver")

    @property
    def variant_alias(self) -> str | None:
        return self.re_match(VALIDATION_WHEEL_NAME_REGEX).group("variant_label")


def safe_urljoin(base: str, path: str) -> str:
    if not base.endswith("/"):
        base += "/"
    return urljoin(base, path)


def generate_main_index(packages: list[str]) -> None:
    # Load template
    current_dir = Path(__file__).parent
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(current_dir / "templates"),
        autoescape=True,
    )
    template = jinja_env.get_template("main_page.j2")

    filtered_packages = [pkg for pkg in packages if (BUILD_DIR / pkg).is_dir()]

    # Render template
    output = template.render(
        directories=sorted(filtered_packages),
        build_date=BUILD_DATE,
    )

    with (BUILD_DIR / "index.html").open(mode="w") as f:
        f.write(output)


def fetch_links(url: str) -> list[VariantWheel | VariantJson]:
    # Fetch the content of the URL
    response = requests.get(url, timeout=10)
    response.raise_for_status()  # Ensure we notice bad responses

    # Parse the HTML content
    soup = BeautifulSoup(response.text, "html.parser")

    # Find all <a> tags with href attribute ending with .json or .whl
    artifacts: list[VariantWheel | VariantJson] = []
    for a_tag in soup.find_all("a", href=True):
        href: str = a_tag["href"]  # pyright: ignore[reportUnknownVariableType, reportAssignmentType, reportArgumentType, reportIndexIssue]

        if href.split("#", maxsplit=1)[0].endswith((".json", ".whl")):  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType, reportAttributeAccessIssue]
            checksum = ""

            absolute_link = safe_urljoin(response.url, href)
            if "#" not in href:
                # WheelNext indexes sometimes put a hex digest in this attribute.
                integrity = a_tag.get("integrity", "")
                if match := re.fullmatch(r"sha256-([0-9a-fA-F]{64})", integrity):
                    checksum = match[1]

            filename: str = a_tag.text.strip()

            if filename.endswith(".json"):
                artifacts.append(
                    VariantJson(name=filename, link=absolute_link, checksum=checksum)  # pyright: ignore[reportUnknownArgumentType]
                )

            elif filename.endswith(".whl"):
                artifacts.append(
                    VariantWheel(name=filename, link=absolute_link, checksum=checksum)  # pyright: ignore[reportUnknownArgumentType]
                )

            else:
                raise ValueError(f"Unknown file extension: `{filename}` ...")

    return artifacts


def pkg_name_to_version(pkg_name: str) -> Version:
    return Version(pkg_name.split("-", maxsplit=2)[1])


def generate_project_index(pkgconfig: PkgConfig) -> None:
    artifacts = fetch_links(safe_urljoin(pkgconfig.registry, pkgconfig.name + "/"))

    releases = {}
    for artifact in artifacts:
        if not isinstance(artifact, VariantJson):
            continue
        response = requests.get(artifact.link, timeout=10)
        response.raise_for_status()
        data = response.json()
        # The publisher must update the wheels and their release metadata together.
        if data.get("$schema") != SCHEMA:
            continue
        if artifact.version in releases:
            raise ValueError(f"Duplicate variant metadata for {artifact.name}")
        releases[artifact.version] = VariantsJson(data)

    wheels = [
        a
        for a in artifacts
        if isinstance(a, VariantWheel)
        and (not a.variant_alias or a.version in releases)
    ]
    if not wheels:
        return
    variant_versions: set[Version] = {
        pkg_name_to_version(artifact.name) for artifact in wheels
    }

    # Also add the packages published on PyPI
    try:
        pypi = fetch_links(
            safe_urljoin("https://pypi.org/simple", pkgconfig.name + "/")
        )
    except requests.HTTPError as err:
        if err.response.status_code != requests.codes.not_found:
            raise
    else:
        wheels.extend(
            a
            for a in pypi
            if isinstance(a, VariantWheel)
            and not a.variant_alias
            and pkg_name_to_version(a.name) not in variant_versions
        )

    write_project_index(BUILD_DIR / pkgconfig.name, wheels, releases)


def write_project_index(
    project_dir: Path, wheels: list[VariantWheel], releases: dict[str, VariantsJson]
) -> None:
    # Load template
    current_dir = Path(__file__).parent
    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(current_dir / "templates"),
        autoescape=True,
    )
    template = jinja_env.get_template("project_page.j2")

    project_dir.mkdir(exist_ok=True, parents=True)
    labels = defaultdict(set)

    def augment_wheel_variant(artifact: VariantWheel) -> VariantWheel:
        label = artifact.variant_alias
        if label is None:
            return artifact
        labels[artifact.version].add(label)
        variant = releases[artifact.version].variants[label]
        return replace(artifact, vprops=[p.to_str() for p in variant.properties])

    wheel_files = sorted(
        (augment_wheel_variant(w) for w in wheels),
        key=lambda x: (Version(x.name.split("-", maxsplit=2)[1]), x.name),
        reverse=True,
    )
    # Describe exactly the labels present on this index, across all wheel tags.
    for version, published in labels.items():
        release = releases[version]
        release.variants = {
            label: release.variants[label] for label in sorted(published)
        }
        name = wheels[0].name.split("-", 1)[0]
        path = project_dir / f"{name}-{version}-variants.json"
        path.write_text(metadata_json(release), encoding="utf-8")

    # Render template
    output = template.render(
        project_name=project_dir.name,
        variants_json_files=sorted(
            [VariantJson.from_file(fp) for fp in project_dir.glob("*.json")],
            key=lambda vf: (Version(vf.name.split("-", maxsplit=2)[1]), vf.name),
            reverse=True,
        ),
        wheel_variant_files=wheel_files,
        build_date=BUILD_DATE,
    )

    with (project_dir / "index.html").open(mode="w") as f:
        f.write(output)


def index_local_wheels(build: Path, wheels: Iterable[Path]) -> None:
    """Build the index metadata from variant.json in the wheels we host."""
    packages = defaultdict(list)
    releases: dict[str, dict[str, VariantsJson]] = defaultdict(dict)
    for wheel in sorted(wheels):
        namever, label = wheel_parts(wheel.name)
        name, version = namever.split("-", 1)
        package = canonicalize_name(name)
        if label is not None:
            with ZipFile(wheel) as archive:
                data = archive.read(f"{namever}.dist-info/variant.json")
            variant = read_variant(data, label)
            if version in releases[package]:
                releases[package][version].merge(variant)
            else:
                releases[package][version] = variant
        project = build / package
        project.mkdir(exist_ok=True, parents=True)
        destination = project / wheel.name
        if destination.exists():
            raise ValueError(f"Duplicate wheel: {wheel.name}")
        digest = sha256sum(shutil.copyfile(wheel, destination))
        packages[package].append(VariantWheel(wheel.name, wheel.name, digest))

    for package, artifacts in packages.items():
        write_project_index(build / package, artifacts, releases[package])
