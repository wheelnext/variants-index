"""Copy the built index into a checkout of the gh-pages branch."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import textwrap
import tomllib
from pathlib import Path

from bs4 import BeautifulSoup
from packaging.version import Version


def add_release(index: Path, version: Version) -> None:
    html = index.read_text(encoding="utf-8")
    table = BeautifulSoup(html, "html.parser").select_one("table tbody")
    if table is None:
        raise ValueError(f"No release table in {index}")
    href = f"v{version}/"
    if table.find("a", href=href):
        return

    # The landing page lives on gh-pages. Insert just the new row so its
    # formatting and the original publication dates stay intact.
    first = table.find("tr", recursive=False)
    if first is None or first.sourceline is None or first.sourcepos is None:
        raise ValueError(f"No release row in {index}")
    date = dt.datetime.now(dt.UTC).strftime("%Y/%m/%d")
    row = f"""\
<tr>
    <td><pre>v{version}</pre></td>
    <td>{date}</td>
    <td><a href="{href}">Link</a></td>
</tr>
"""
    lines = html.splitlines(keepends=True)
    lines.insert(first.sourceline - 1, textwrap.indent(row, " " * first.sourcepos))
    index.write_text("".join(lines), encoding="utf-8")


def publish(pages: Path, commit: str) -> None:
    if not re.fullmatch("[0-9a-f]{7,40}", commit):
        raise ValueError(f"Expected a commit hash, got {commit!r}")
    with Path("pyproject.toml").open("rb") as f:
        version = Version(tomllib.load(f)["project"]["version"])
    for directory in (pages / commit, pages / f"v{version}"):
        if directory.exists():
            shutil.rmtree(directory)
        shutil.copytree("build", directory)
    add_release(pages / "index.html", version)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pages", type=Path, help="checkout of the gh-pages branch")
    parser.add_argument("commit", help="commit that built the index")
    args = parser.parse_args()
    publish(args.pages, args.commit)
