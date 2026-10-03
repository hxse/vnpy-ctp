set shell := ["bash", "-euc"]

default:
    @just --list

# 准备独立开发环境；不读取账户配置。
setup:
    uv venv --allow-existing --python=3.13
    uv pip install --python=.venv/bin/python -r requirements-dev.txt

# 单元检查不编译 SDK、不连接外部交易服务。
[positional-arguments]
test *args:
    uv run --no-sync python -m pytest tests/unit "$@"

check:
    uv run --no-sync ruff check scripts tests src
    uv run --no-sync python scripts/check_source.py

# 本机 wheel 用于验证；公开的跨平台 wheel 由 Actions 构建。
build:
    uv run --no-sync python -m build --wheel --no-isolation --outdir .wheelhouse

# 明确指定已生成的 wheel，验证其真实原生扩展。
[positional-arguments]
test-native wheel:
    uv run --no-sync python -m scripts.test_wheel "$1"
