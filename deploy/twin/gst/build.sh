#!/usr/bin/env bash
# M1 验收 1:在 a4000 上构建 gst-base 镜像。
# 前提:docker.io/library/ubuntu:24.04 已在本地(design R7:短名 pull 失败);
#       --network host 使 apt 可达宿主 127.0.0.1:7897 代理(报告一 §1.4)。
set -euo pipefail
cd "$(dirname "$0")"

PROXY="${PROXY:-http://127.0.0.1:7897}"
IMAGE="${IMAGE:-gst-base:v1}"

docker build --network host \
  --build-arg http_proxy="$PROXY" \
  --build-arg https_proxy="$PROXY" \
  --build-arg no_proxy="localhost,127.0.0.1" \
  -t "$IMAGE" .

docker images "$IMAGE"
