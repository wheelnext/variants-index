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
