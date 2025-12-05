.PHONY: clean build install install-dev venv

# ============================================================================ #
# CLEAN COMMANDS
# ============================================================================ #

clean: clean-build clean-pyc ## remove all build, test, coverage and Python artifacts

clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	mkdir -p build/

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +
# ============================================================================ #
# INSTALL COMMANDS
# ============================================================================ #

venv:
	uv venv --clear --python python3.14

install: venv
	uv sync

install-dev: venv
	uv sync --dev

# ============================================================================ #
# BUILD COMMANDS
# ============================================================================ #

build: clean
	uv run main.py
