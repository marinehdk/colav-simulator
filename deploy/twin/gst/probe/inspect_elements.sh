#!/usr/bin/env bash
# M1 验收 2:元素与库自检。
# 必须在带 GPU 的容器内执行(裸容器里 nvcodec 系元素运行时探测不到 GPU,全部 MISSING,
# 会误判镜像缺件 —— DESIGN 附录 C5 双容器对照)。
# 用法:docker exec gst-base bash /gst/probe/inspect_elements.sh
set -uo pipefail

echo "== GStreamer 版本 =="
gst-inspect-1.0 --version

echo
echo "== gstreamer1.0-nice(包 + 插件;gst-inspect webrtcbin 检不出此缺件)=="
dpkg-query -W -f='${Package} ${Version}\n' gstreamer1.0-nice || echo "gstreamer1.0-nice: NOT INSTALLED"
if gst-inspect-1.0 nicesrc >/dev/null 2>&1; then echo "nicesrc: PRESENT"; else echo "nicesrc: MISSING"; fi

echo
echo "== 验收元素清单 =="
fail=0
for e in webrtcbin nvh264enc nvautogpuh264enc cudaupload ximagesrc cudaipcsrc h264parse rtph264pay videotestsrc videoconvert; do
  if gst-inspect-1.0 "$e" >/dev/null 2>&1; then
    printf '%-18s PRESENT\n' "$e"
  else
    printf '%-18s MISSING\n' "$e"; fail=1
  fi
done

echo
echo "== libnvidia-encode 注入(报告一 V3 同款检查;须 NVIDIA_DRIVER_CAPABILITIES 含 video)=="
ls -l /usr/lib/x86_64-linux-gnu/libnvidia-encode.so.1 || fail=1

exit $fail
