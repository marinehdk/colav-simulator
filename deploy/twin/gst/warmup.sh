#!/usr/bin/env bash
# GPU1 冷启动预热:空转编码若干帧,触发 CUDA/NVENC 上下文首次初始化
# (报告一 T4 坑:GPU1 首跑出现过一次 30.3s,复跑正常)。随 run.sh 在容器启动后执行。
set -euo pipefail
NAME="${NAME:-gst-base}"

echo "[warmup] GPU1 nvenc 空转 300 帧(冷启动时首次可达 ~30s,属预期)..."
time docker exec "$NAME" gst-launch-1.0 -e \
  videotestsrc num-buffers=300 \
  ! video/x-raw,width=640,height=360,format=NV12,framerate=30/1 \
  ! cudaupload ! nvautogpuh264enc cuda-device-id=1 \
  ! fakesink
echo "[warmup] done"
