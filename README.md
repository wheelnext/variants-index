# WheelNext variant demo index

[v0.2.0](https://wheelnext.github.io/variants-index/v0.2.0/) demonstrates the
[PEP 825 wheel format](https://peps.python.org/pep-0825/) and
[PEP 850 providers](https://peps.python.org/pep-0850/).
The [v0.0.3 index](https://wheelnext.github.io/variants-index/v0.0.3/) remains available.

## Try it locally

Build and serve the demo, then follow the install command at <http://localhost:8000/>.
With a version of uv that supports wheel variants, it prints `portable`.
The demo uses a static provider and works without a GPU or provider plugin.

```sh
uv run --locked main.py --demo-only
python3 -m http.server 8000 --directory build
```

## Migrate an existing release

The index lists variant wheels when the publisher's release metadata declares
the PEP 850 v0.2.0 schema. Publishers must update the wheels and metadata together.

```sh
uv run --locked python -m src.migrate --output migrated path/to/old/*.whl
uv run --locked main.py --wheel-dir migrated
```

This updates `variant.json` and `RECORD` in copies of the wheels, then derives the
index metadata from those copies. Publish them at a new version or URL. Provider
plugins must implement PEP 850 and handle unsupported platforms themselves.

If the publisher corrected the metadata after building the wheels, pass
`--metadata path/to/name-version-variants.json` with only the wheels from that release.
