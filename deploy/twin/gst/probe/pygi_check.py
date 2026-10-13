#!/usr/bin/env python3
"""M1 验收 4:PYGI 栈自检(报告一 V6 同款)。

GstWebRTC typelib 在 gir1.2-gst-plugins-bad-1.0(漏装即报
"Namespace GstWebRTC not available",报告一 V6 坑)。
用法:docker exec gst-base python3 /gst/probe/pygi_check.py
"""
import sys

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstWebRTC", "1.0")
gi.require_version("GstSdp", "1.0")
from gi.repository import Gst, GstWebRTC, GstSdp  # noqa: E402

Gst.init(None)
print("PYGI_STACK_OK", Gst.version_string())

fail = False
# nvcodec 系元素需 GPU 容器内才注册(DESIGN C5),本脚本也必须在带 GPU 容器内跑
for name in ("webrtcbin", "nvh264enc", "nvautogpuh264enc", "cudaupload", "cudaipcsrc", "rtph264pay"):
    el = Gst.ElementFactory.make(name, None)
    ok = el is not None
    print(f"{name}: {'OK' if ok else 'FAIL'}")
    fail = fail or not ok

if fail:
    sys.exit(1)
print("PYGI_INSTANTIATE_OK")
