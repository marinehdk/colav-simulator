# DT 像素流 GStreamer 发送底座(DESIGN: docs/research/2026-10-12-dt-frame-delivery-2k/DESIGN.md M1)
# 构建(在 a4000 上,须 --network host 使构建容器可达宿主 127.0.0.1:7897 代理):
#   bash build.sh
# 基础镜像用全路径(报告一 V2 坑:短名 pull 失败;docker.io/library/ 前缀在本地解析到已 pull 镜像)
FROM docker.io/library/ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# 代理经 build-arg 注入(build.sh 传 http_proxy/https_proxy;预定义 ARG 无需声明,声明为显式化)
ARG http_proxy
ARG https_proxy
ARG no_proxy

# 包清单 = 报告一 V6 已验清单 + 复审必增 gstreamer1.0-nice。
# gstreamer1.0-nice(libnice 的 GStreamer 插件):无它时 gst-inspect webrtcbin 照样通过(验收盲区),
# 但 webrtcbin 一投用即总线报 "missing a plug-in ... libnice elements are not available"
# (gstwebrtcbin.c:154 _have_nice_elements;DESIGN 附录 C1 复审实证)。
# GstWebRTC typelib 在 gir1.2-gst-plugins-bad-1.0(报告一 V6 坑:漏装报 Namespace GstWebRTC not available)。
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      gstreamer1.0-tools \
      gstreamer1.0-plugins-bad \
      gstreamer1.0-plugins-good \
      gstreamer1.0-nice \
      python3-gi \
      gir1.2-gstreamer-1.0 \
      gir1.2-gst-plugins-base-1.0 \
      gir1.2-gst-plugins-bad-1.0 \
      python3-websockets \
    && rm -rf /var/lib/apt/lists/*

# M1 常驻底座:空转待命(编码/探针/基准经 docker exec)。
# M2 起 sender 代码以 volume 挂载(DESIGN §5.1 环境与业务分离),替换本入口。
CMD ["sleep", "infinity"]
