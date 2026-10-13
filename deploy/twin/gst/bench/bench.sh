#!/usr/bin/env bash
# M1 验收 5:NVENC 基准复测(a4000,容器内,GPU1)。
# 用法(在 a4000 上,容器 gst-base 已起):bash bench/bench.sh [OUT=~/gst-spike/bench] [NAME=gst-base]
# 用例(对齐报告一 §2.2 T 系列,复测 + 锁定参数):
#   b1 全速 1440p 系统内存入编码器(=T4 形态)          门限 fps>=200
#   b2 全速 1440p cudaupload(CUDAMemory 路径,=T2 形态) 信息项
#   b3 1440p60 is-live 60s 实时节拍(=T3 形态)          门限 wall<=61.5s 且 stderr 无 WARNING/ERROR
#   b4 1440p30 CBR 20M 实测码率(=T6 形态)             门限 mbps∈[15,25]
#   b5 同 b4 但 preset=p1 tune=ultra-low-latency(速度上限对拍)信息项
# 输出:$OUT/bench-results-<ts>.txt(汇总)+ 每用例原始输出 $OUT/b*.txt
set -uo pipefail

NAME="${NAME:-gst-base}"
OUT="${OUT:-$HOME/gst-spike/bench}"
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/../enc-params.env"
mkdir -p "$OUT"
TS=$(date +%Y%m%d-%H%M%S)
SUM="$OUT/bench-results-$TS.txt"

log() { echo "$@" | tee -a "$SUM"; }

log "# bench $TS  container=$NAME"
log "# ENC_ARGS=$ENC_ARGS"
log ""

overall=0

# ---- b1 全速 sysmem --------------------------------------------------------
f="$OUT/b1-fullspeed-sysmem.txt"
{
  echo "\$ docker exec $NAME gst-launch-1.0 -e videotestsrc num-buffers=1800 ! video/x-raw,width=2560,height=1440,format=NV12,framerate=60/1 ! nvautogpuh264enc cuda-device-id=1 bitrate=20000 <ENC_ARGS> ! fakesink"
  docker exec "$NAME" bash -c '
    t0=$(date +%s%N)
    gst-launch-1.0 -e videotestsrc num-buffers=1800 \
      ! video/x-raw,width=2560,height=1440,format=NV12,framerate=60/1 \
      ! nvautogpuh264enc cuda-device-id=1 bitrate=20000 '"$ENC_ARGS"' \
      ! fakesink
    rc=$?
    t1=$(date +%s%N)
    echo "WALL_NS=$((t1-t0))"
    exit $rc'
  echo "rc=$?"
} >"$f" 2>&1
ns=$(grep -oE 'WALL_NS=[0-9]+' "$f" | head -1 | cut -d= -f2)
if [ -n "${ns:-}" ]; then
  fps=$(awk -v n="$ns" 'BEGIN{printf "%.1f", 1800/(n/1e9)}')
  verdict=$([ "$(awk -v v="$fps" 'BEGIN{print (v>=200)?1:0}')" = 1 ] && echo PASS || { overall=1; echo FAIL; })
  log "b1 fullspeed-sysmem 1440p: ${fps} fps (1800 frames / ${ns} ns)  target>=200  $verdict"
else
  overall=1; log "b1 fullspeed-sysmem 1440p: NO TIMING (see $f)  FAIL"
fi

# ---- b2 全速 cudaupload ----------------------------------------------------
f="$OUT/b2-fullspeed-cuda.txt"
{
  echo "\$ ... ! cudaupload ! nvautogpuh264enc cuda-device-id=1 ... (same as b1)"
  docker exec "$NAME" bash -c '
    t0=$(date +%s%N)
    gst-launch-1.0 -e videotestsrc num-buffers=1800 \
      ! video/x-raw,width=2560,height=1440,format=NV12,framerate=60/1 \
      ! cudaupload ! nvautogpuh264enc cuda-device-id=1 bitrate=20000 '"$ENC_ARGS"' \
      ! fakesink
    rc=$?
    t1=$(date +%s%N)
    echo "WALL_NS=$((t1-t0))"
    exit $rc'
  echo "rc=$?"
} >"$f" 2>&1
ns=$(grep -oE 'WALL_NS=[0-9]+' "$f" | head -1 | cut -d= -f2)
if [ -n "${ns:-}" ]; then
  fps=$(awk -v n="$ns" 'BEGIN{printf "%.1f", 1800/(n/1e9)}')
  log "b2 fullspeed-cuda 1440p:   ${fps} fps  (info)"
else
  log "b2 fullspeed-cuda 1440p:   NO TIMING (see $f)  (info)"
fi

# ---- b3 1440p60 live 60s ---------------------------------------------------
f="$OUT/b3-live60.txt"
(
  {
    echo "\$ docker exec $NAME gst-launch-1.0 -e videotestsrc is-live=true num-buffers=3600 ! video/x-raw,width=2560,height=1440,format=NV12,framerate=60/1 ! nvautogpuh264enc cuda-device-id=1 bitrate=20000 <ENC_ARGS_60> ! fakesink"
    docker exec "$NAME" bash -c '
      t0=$(date +%s%N)
      gst-launch-1.0 -e videotestsrc is-live=true num-buffers=3600 \
        ! video/x-raw,width=2560,height=1440,format=NV12,framerate=60/1 \
        ! nvautogpuh264enc cuda-device-id=1 bitrate=20000 '"$ENC_ARGS_60"' \
        ! fakesink
      rc=$?
      t1=$(date +%s%N)
      echo "WALL_NS=$((t1-t0))"
      exit $rc'
    echo "rc=$?"
  } >"$f" 2>&1
) &
b3pid=$!
sleep 12
{ echo "== GPU snapshot @+12s of b3 =="; nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader; nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader; } | tee -a "$SUM" | tee -a "$f"
wait $b3pid
ns=$(grep -oE 'WALL_NS=[0-9]+' "$f" | head -1 | cut -d= -f2)
alerts=$(grep -cE '^(WARNING|ERROR)' "$f" || true)
if [ -n "${ns:-}" ]; then
  wall=$(awk -v n="$ns" 'BEGIN{printf "%.2f", n/1e9}')
  verdict=PASS
  [ "$(awk -v w="$wall" 'BEGIN{print (w<=61.5)?1:0}')" = 1 ] || { verdict=FAIL; overall=1; }
  [ "${alerts:-0}" = 0 ] || { verdict=FAIL; overall=1; }
  log "b3 live 1440p60 60s: wall=${wall}s (nominal 60) alerts=${alerts}  target wall<=61.5 & no WARNING/ERROR  $verdict"
else
  overall=1; log "b3 live 1440p60 60s: NO TIMING (see $f)  FAIL"
fi

# ---- b4 CBR 20M @1440p30 ---------------------------------------------------
raw="/out/b4-cbr30.h264"; hostraw="$OUT/b4-cbr30.h264"
rm -f "$hostraw"
f="$OUT/b4-cbr30.txt"
{
  echo "\$ ... is-live=true num-buffers=1800 ! ...framerate=30/1 ! nvautogpuh264enc cuda-device-id=1 bitrate=20000 <ENC_ARGS> ! h264parse ! filesink location=$raw"
  docker exec "$NAME" bash -c '
    t0=$(date +%s%N)
    gst-launch-1.0 -e videotestsrc is-live=true num-buffers=1800 \
      ! video/x-raw,width=2560,height=1440,format=NV12,framerate=30/1 \
      ! nvautogpuh264enc cuda-device-id=1 bitrate=20000 '"$ENC_ARGS"' \
      ! h264parse ! filesink location='"$raw"'
    rc=$?
    t1=$(date +%s%N)
    echo "WALL_NS=$((t1-t0))"
    exit $rc'
  echo "rc=$?"
} >"$f" 2>&1
ns=$(grep -oE 'WALL_NS=[0-9]+' "$f" | head -1 | cut -d= -f2)
if [ -n "${ns:-}" ] && [ -s "$hostraw" ]; then
  bytes=$(stat -c%s "$hostraw")
  mbps=$(awk -v b="$bytes" -v n="$ns" 'BEGIN{printf "%.2f", b*8/(n/1e9)/1e6}')
  verdict=$([ "$(awk -v v="$mbps" 'BEGIN{print (v>=15&&v<=25)?1:0}')" = 1 ] && echo PASS || { overall=1; echo FAIL; })
  log "b4 cbr30 1440p: ${mbps} Mbps (${bytes} bytes / ${ns} ns, locked ENC_ARGS)  target∈[15,25]  $verdict"
  rm -f "$hostraw"
else
  overall=1; log "b4 cbr30 1440p: NO OUTPUT (see $f, $hostraw)  FAIL"
fi

# ---- b5 同 b4 但 preset=p1 tune=ultra-low-latency(速度上限对拍,信息项)------
raw="/out/b5-cbr30-p1ull.h264"; hostraw="$OUT/b5-cbr30-p1ull.h264"
rm -f "$hostraw"
f="$OUT/b5-cbr30-p1ull.txt"
{
  echo "\$ ... preset=p1 tune=ultra-low-latency ... num-buffers=900 (30s)"
  docker exec "$NAME" bash -c '
    t0=$(date +%s%N)
    gst-launch-1.0 -e videotestsrc is-live=true num-buffers=900 \
      ! video/x-raw,width=2560,height=1440,format=NV12,framerate=30/1 \
      ! nvautogpuh264enc cuda-device-id=1 bitrate=20000 preset=p1 tune=ultra-low-latency rate-control=cbr b-frames=0 zero-reorder-delay=true rc-lookahead=0 gop-size=60 repeat-sequence-header=true qos=true \
      ! h264parse ! filesink location='"$raw"'
    rc=$?
    t1=$(date +%s%N)
    echo "WALL_NS=$((t1-t0))"
    exit $rc'
  echo "rc=$?"
} >"$f" 2>&1
ns=$(grep -oE 'WALL_NS=[0-9]+' "$f" | head -1 | cut -d= -f2)
if [ -n "${ns:-}" ] && [ -s "$hostraw" ]; then
  bytes=$(stat -c%s "$hostraw")
  mbps=$(awk -v b="$bytes" -v n="$ns" 'BEGIN{printf "%.2f", b*8/(n/1e9)/1e6}')
  log "b5 cbr30 1440p p1+ull: ${mbps} Mbps (${bytes} bytes / ${ns} ns, preset=p1 tune=ultra-low-latency)  (info)"
  rm -f "$hostraw"
else
  log "b5 cbr30 1440p p1+ull: NO OUTPUT (see $f)  (info)"
fi

log ""
log "OVERALL: $([ $overall = 0 ] && echo PASS || echo FAIL)"
exit $overall
