#!/usr/bin/env bash
# M1 验收 6:起常驻底座容器并预热 GPU1。
# 容器参数 = DESIGN §5.1(验收 2 指定的完整参数):
#   --gpus all(仅可见性;编码定向 GPU1 由 nvautogpuh264enc cuda-device-id=1 决定)
#   NVIDIA_DRIVER_CAPABILITIES 含 video 才注入 libnvidia-encode(报告一 V3)
#   --network host:ICE 候选为宿主网卡(报告一 §1.4);--ipc=host:XShm 跨容器(DESIGN C6)
#   挂载 X93 socket + DISPLAY:供 M3 ximagesrc 采集
# 重复执行幂等(先移除旧容器再起)。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
GST_DIR="$HERE"                            # = ~/gst-spike/gst(部署树本身;M2 起 sender/ 也在此)
BENCH_DIR="${BENCH_DIR:-$HOME/gst-spike/bench}"
NAME="${NAME:-gst-base}"
IMAGE="${IMAGE:-gst-base:v1}"

mkdir -p "$BENCH_DIR"

docker rm -f "$NAME" 2>/dev/null || true
docker run -d --name "$NAME" \
  --restart unless-stopped \
  --gpus all \
  --network host \
  --ipc=host \
  -e NVIDIA_DRIVER_CAPABILITIES=utility,compute,video \
  -e XDG_RUNTIME_DIR=/tmp \
  -e DISPLAY=:93 \
  -v /tmp/.X11-unix:/tmp/.X11-unix:ro \
  -v "$GST_DIR":/gst:ro \
  -v "$BENCH_DIR":/out \
  "$IMAGE"

# GPU1 冷启动预热(T4 坑:首跑 CUDA 上下文初始化可达 ~30s)
bash "$HERE/warmup.sh"

echo "== container =="
docker ps --filter "name=$NAME" --format '{{.Names}}  {{.Status}}'
docker inspect -f 'restart-policy={{.HostConfig.RestartPolicy.Name}}' "$NAME"
