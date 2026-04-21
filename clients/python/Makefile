# T033 — Python client Makefile.
# Callable as `make -C clients/python <target>` from any directory.

REPO_ROOT := $(shell cd ../.. && pwd)
PROTO_DIR := $(REPO_ROOT)/proto
PKG_DIR   := $(REPO_ROOT)/clients/python/highbar_client

PYTHON ?= python3
PIP    ?= $(PYTHON) -m pip

.PHONY: help codegen install-dev test clean

help:
	@echo "Targets:"
	@echo "  codegen      regenerate gRPC stubs into highbar_client/highbar/"
	@echo "  install-dev  pip install -e .[dev]"
	@echo "  test         pytest"
	@echo "  clean        remove generated stubs + caches"

codegen:
	@mkdir -p "$(PKG_DIR)/highbar"
	$(PYTHON) -m grpc_tools.protoc \
	    -I "$(PROTO_DIR)" \
	    --python_out="$(PKG_DIR)" \
	    --grpc_python_out="$(PKG_DIR)" \
	    "$(PROTO_DIR)/highbar/"*.proto
	@touch "$(PKG_DIR)/highbar/__init__.py"
	@echo "codegen: stubs in $(PKG_DIR)/highbar/"

install-dev:
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest

clean:
	rm -rf "$(PKG_DIR)/highbar" "$(PKG_DIR).egg-info"
	find . -type d -name __pycache__ -exec rm -rf {} +
