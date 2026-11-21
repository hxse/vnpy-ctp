#!/usr/bin/env bash
# 仅使用锁定厂商输入，打包后从实际归档运行 cgo 探针。
set -euo pipefail
if [ "$(uname -m)" != x86_64 ] || [ "$(getconf GNU_LIBC_VERSION)" != 'glibc 2.28' ]; then
    printf '%s\n' 'Go 制品需要锁定的 Linux x86_64/glibc 2.28 构建环境' >&2
    exit 2
fi

export PATH="/go-toolchain/bin:$PATH"
export GOTOOLCHAIN=local GOTELEMETRY=off GOPROXY=off PYTHONDONTWRITEBYTECODE=1
test "$(go env GOVERSION)" = "go$(cat native/go/.go-version)"
python=/opt/python/cp313-cp313/bin/python
"$python" scripts/check_source.py
work=$(mktemp -d /out/.go-native.XXXXXXXX)
trap 'rm -r -- "$work"' EXIT

bundle="$work/bundle"
mkdir -p "$bundle/include/ctp" "$bundle/lib" "$work/release"
cp native/go/vnctp_go.h "$bundle/include/"
cp native/include/ctp/ThostFtdcUserApiStruct.h native/include/ctp/ThostFtdcUserApiDataType.h "$bundle/include/ctp/"
cp vendor/ctp/linux-x86_64/libthosttraderapi_se.so vendor/assessment/linux-x86_64/libthostmduserapi_se.so "$bundle/lib/"
cp LICENSE NOTICE "$bundle/"

compiler_flags=(-std=c++17 -O2 -Wall -Wextra -Werror -isystem native/include -pthread)
g++ "${compiler_flags[@]}" -fPIC -fvisibility=hidden -shared -static-libstdc++ -static-libgcc \
    -Wl,-z,defs -Wl,--exclude-libs,ALL -Wl,-soname,libvnctp_go.so -Wl,-rpath,'$ORIGIN' \
    native/go/td.cpp native/go/md.cpp -L"$bundle/lib" -lthosttraderapi_se -lthostmduserapi_se \
    -o "$bundle/lib/libvnctp_go.so"
g++ "${compiler_flags[@]}" -Inative/go tests/native/go_mailbox.cpp -o "$work/mailbox"
timeout 10 "$work/mailbox"

"$python" -m scripts.release.go_native "$work/release" "$1" "$2" --pack "$bundle"
mkdir -p "$work/consumer" "$work/flow"
tar -xzf "$work/release/vnpy-ctp-go-native-linux-amd64.tar.gz" -C "$work/consumer"
readelf -h "$work/consumer/lib/libvnctp_go.so" | grep -Eq 'Machine:.*X86-64$'
if readelf -d "$work/consumer/lib/libvnctp_go.so" | grep -i python; then
    printf '%s\n' 'Go 动态库包含 Python 依赖' >&2
    exit 1
fi
"$python" - "$work/consumer/lib" <<'PYELF'
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(sys.argv[1])
for library in sorted(root.glob("*.so")):
    versions = subprocess.check_output(["readelf", "--version-info", library], text=True)
    targets = {tuple(map(int, item.split("."))) for item in re.findall(r"\bGLIBC_([0-9.]+)", versions)}
    if any(version > (2, 28) for version in targets) or "GLIBC_PRIVATE" in versions:
        raise SystemExit(f"{library.name} 超出 glibc 2.28 ABI")
loader = subprocess.check_output(["readelf", "-d", root / "libvnctp_go.so"], text=True)
if not {"libthosttraderapi_se.so", "libthostmduserapi_se.so"} <= set(re.findall(r"NEEDED.*?\[(.*?)\]", loader)):
    raise SystemExit("适配器未直接链接归档中的两个厂商库")
if "(RUNPATH)" not in loader or "[$ORIGIN]" not in loader:
    raise SystemExit("适配器缺少同目录运行时加载路径")
PYELF
export GOCACHE="$work/go-cache" GO111MODULE=off CGO_ENABLED=1
export CGO_CFLAGS="-I$work/consumer/include"
export CGO_LDFLAGS="-L$work/consumer/lib -lvnctp_go -Wl,-rpath-link,$work/consumer/lib"
go build -trimpath -o "$work/probe" tests/native/go_probe/main.go
build=$("$python" -c 'import json;print(json.load(open("vendor/sdk.json"))["builds"]["linux_x86_64"]["api_version"])')
LD_LIBRARY_PATH="$work/consumer/lib" timeout 30 "$work/probe" "$work/flow" "$build"
install -m 0644 "$work/release/"* /out/
