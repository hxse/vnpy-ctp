#!/usr/bin/env bash
# 在相同的断网构建镜像中执行本机和 CI 的原生制品门禁。
set -euo pipefail
root=$(cd -- "$(dirname -- "$0")/.." && pwd -P)
if [ "$#" -ne 3 ]; then
    printf '%s\n' '用法：go_native_container.sh 输出目录 完整提交SHA 仓库名' >&2
    exit 2
fi
mkdir -p -- "$1"
output=$(cd -- "$1" && pwd -P)
engine=${CONTAINER_ENGINE:-podman}
case "$engine" in
    podman) container_user=() ;;
    docker) container_user=(--user "$(id -u):$(id -g)") ;;
    *) printf '%s\n' 'CONTAINER_ENGINE 必须为 podman 或 docker' >&2; exit 2 ;;
esac
toolchain=$(GOTOOLCHAIN=local GOTELEMETRY=off go env GOROOT)
image=$(cat "$root/native/go/builder.lock")
"$engine" run --rm --pull=missing --network=none "${container_user[@]}" \
    --cap-drop=ALL --security-opt=no-new-privileges \
    --volume "$root:/src:ro" --volume "$output:/out:rw" --volume "$toolchain:/go-toolchain:ro" \
    --workdir /src "$image" bash /src/scripts/build_go_native.sh "$2" "$3"
