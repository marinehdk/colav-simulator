#!/usr/bin/env python3
"""M2 信令握手:GStreamer webrtcbin 演 URS answerer(python gi + websockets)。
M5 增补:twin-bridge DataChannel ↔ Unity 本地回环通道(127.0.0.1:--bridge-port)双向转发,
echo 退役;stream_profile 在此拦截并映射编码档(1080p=16000/1440p=20000 kbps),不转发 Unity。

剧本(DESIGN §7,信封复刻 a4000 signaling.log 实测 Unity 样例):
  1. WS 连 8081 第二 webapp 实例,不注册 connect(Unity 同款),静默等浏览器 offer#1(仅 m=application)。
  2. SRD → create-answer → SLD → answer:{from:浏览器id, to:'', type:'answer', data:{connectionId:浏览器id, sdp}}。
  3. on-ice-candidate → candidate:{from:浏览器id, to:'', type:'candidate',
     data:{connectionId:浏览器id, candidate, sdpMid:'<str>', sdpMLineIndex:<int>}}(Unity 样例同型)。
  4. ice connected → create-data-channel('twin-bridge')(offer#2 之前,随同一 offer 协商)
     → 接编码支线(videotestsrc WxH@fps → nvautogpuh264enc GPU1 → h264parse → rtph264pay PT)
     → 该 transceiver direction=sendonly → create-offer → SLD → offer#2(同 answer 信封形状)。
  5. 浏览器 answer → SRD → 视频流。twin-bridge 消息:浏览器→(拦截 stream_profile)→回环 TCP→Unity;
     Unity→回环 TCP→DataChannel send-string。player 掉线(EOF)→ 拆浏览器 PC(web 侧自动重连收敛)。
  容错:重复 offer 幂等 SRD+再 answer(--suppress-answer-ms 抑制首个 answer 验证浏览器 5s 重发);
        浏览器断开(disconnect/WS close)→ 整管线拆除等新 offer(Page.reload 场景)。
  探针:encoder sink 上行 GstForceKeyUnit 事件计数/日志(PLI→IDR 链);encoder src 非 delta 帧=IDR 计数;
        h264parse src SPS profile_idc 提取(R10 台账);周期状态行。

用法(容器内):python3 sender.py --label main [--source x11] [--suppress-answer-ms 6000] [--width 2560 --height 1440 --fps 30]
日志:/out/spike/sender-<label>.log 由外层重定向;WS 帧 JSONL → /out/spike/wslog-<label>.jsonl;
      四份 SDP → /out/spike/sdp/<label>-{offer1,answer1,offer2,answer2}.sdp
"""
import argparse
import asyncio
import json
import os
import queue
import socket
import threading
import time

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstSdp", "1.0")
gi.require_version("GstWebRTC", "1.0")
from gi.repository import Gst, GstSdp, GstWebRTC, GLib  # noqa: E402

try:
    import websockets
except ImportError as e:  # pragma: no cover
    raise SystemExit(f"missing python3-websockets: {e}")


def monotonic() -> float:
    return time.monotonic()


# M5③(DESIGN §2):stream_profile → 编码码率档映射(kbps)。窗口尺寸随 player 窗口定死,
# 档位语义在 gst 路由下=码率;1440p 档沿用 M3 达标值 20000。
STREAM_PROFILE_BITRATE_KBPS = {"1080p": 16000, "1440p": 20000}


class Sender:
    def __init__(self, args):
        self.args = args
        self.t0 = monotonic()
        self.loop = None  # asyncio loop (ws thread)
        self.ws = None
        self.pipeline = None
        self.webrtc = None
        self.peer_id = None  # 浏览器 connectionId(整个连接的唯一标识,§7 身份规则)
        self.video_linked = False
        self.video_transport_ready = False
        self.offer2_sent = False
        self._pending_answer_text = None
        self._pending_offer_text = None
        self._srd_retried_text = None
        self.answer1_sent = False
        self.remote_set = False
        self.pending_candidates = []  # SRD 前缓冲(suppress 窗口内到达的浏览器候选)
        self.suppress_done = args.suppress_answer_ms <= 0
        self.suppress_active = False
        self.offer_queue = []
        self.channel = None
        self.channel_open = False
        self.offers_in = 0
        self.answers_in = 0
        self.cands_in = 0
        self.cands_out = 0
        self.fku_events = 0
        self.keyframes = 0
        self.frames_encoded = 0
        self.sps_profile = None
        self.sps_level = None
        self.last_keyframe_ts = None
        self.last_fku_ts = None
        self.wslog_path = os.path.join(args.log_dir, f"wslog-{args.label}.jsonl")
        self.sdp_dir = os.path.join(args.log_dir, "sdp")
        os.makedirs(self.sdp_dir, exist_ok=True)
        self._wslog = open(self.wslog_path, "a", buffering=1)
        # M5 twin-bridge 转发(DESIGN §2 M5①/③):回环链 + 出站队列 + 生命周期
        self.bridge_sock = None
        self._bridge_lock = threading.Lock()
        self._bridge_queue = queue.Queue()
        self._bridge_stop = threading.Event()
        self.profile_applied = None

    def log(self, msg):
        print(f"[{monotonic() - self.t0:8.3f}] {msg}", flush=True)

    # ---------- WS 桥(GLib 线程 ↔ asyncio 线程) ----------
    def ws_send(self, obj):
        self._wslog.write(json.dumps({"dir": "out", "t": round(monotonic() - self.t0, 3), "msg": obj}) + "\n")
        if self.ws is not None and self.loop is not None:
            fut = asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps(obj)), self.loop)
            fut.add_done_callback(lambda f: f.exception() and self.log(f"WS SEND ERROR: {f.exception()}"))

    def on_ws_message(self, raw):
        msg = json.loads(raw)
        self._wslog.write(json.dumps({"dir": "in", "t": round(monotonic() - self.t0, 3), "msg": msg}) + "\n")
        mtype = msg.get("type")
        if mtype == "connect":
            self.log(f"WS connect echo: {msg}")
            return
        if mtype == "disconnect":
            self.log(f"WS disconnect (connectionId={msg.get('connectionId')}): teardown")
            GLib.idle_add(self.teardown)
            return
        if mtype == "offer":
            self.offers_in += 1
            new_peer = msg.get("from")
            if self.peer_id is not None and new_peer != self.peer_id:
                # M5 生产语义:同室换浏览器(旧页被杀/游魂 peer 不发 disconnect)→ 拆旧 epoch
                # 再收养新 peer;否则 webrtcbin 带着脏协商态 SRD 必败(实测 offer#12+ 全 not ok)。
                self.log(f"offer from NEW peer {new_peer} (was {self.peer_id}) — teardown stale epoch")
                self.teardown()
            self.peer_id = new_peer
            self.log(f"offer#{self.offers_in} in from={self.peer_id} sdp_len={len(msg['data']['sdp'])}")
            self._dump_sdp("offer1" if self.offers_in == 1 else f"offer-dup{self.offers_in}", msg["data"]["sdp"])
            self.handle_offer(msg["data"]["sdp"])
            return
        if mtype == "answer":
            self.answers_in += 1
            self.log(f"answer#{self.answers_in} in sdp_len={len(msg['data']['sdp'])}")
            self._dump_sdp("answer2" if self.answers_in == 1 else f"answer-dup{self.answers_in}", msg["data"]["sdp"])
            self.srd_answer(msg["data"]["sdp"])
            return
        if mtype == "candidate":
            self.cands_in += 1
            d = msg["data"]
            # 产品怪癖(实证):peer.js/renderstreaming.js 参数顺序使 data 内 sdpMid 与
            # sdpMLineIndex 互换 —— 视频 m-line 收到 sdpMLineIndex='video0'/sdpMid=1。
            # BUNDLE 下全部候选同 transport:int 解析失败即落到 mline 0。
            mline = d.get("sdpMLineIndex", 0)
            try:
                mline = int(mline)
            except (TypeError, ValueError):
                try:
                    mline = int(d.get("sdpMid"))
                except (TypeError, ValueError):
                    mline = 0
                self.log(f"  sdpMLineIndex={d.get('sdpMLineIndex')!r} not int -> mid-fallback mline={mline}")
            self.log(f"candidate#{self.cands_in} in mline={mline} cand={d.get('candidate', '')[:60]}")
            self.add_candidate(mline, d.get("candidate"))
            return
        self.log(f"unhandled WS message type={mtype}")

    # ---------- 信令状态机(GLib 线程) ----------
    def handle_offer(self, sdp):
        if self.suppress_active:
            self.offer_queue.append(sdp)
            self.log(f"  queued while suppressed (queue={len(self.offer_queue)})")
            return
        if not self.suppress_done:
            self.suppress_done = True
            self.suppress_active = True
            self.offer_queue.append(sdp)
            self.log(f"  SUPPRESS first offer {self.args.suppress_answer_ms}ms (browser loopResendOffer=5s)")
            GLib.timeout_add(self.args.suppress_answer_ms, self._drain_suppressed)
            return
        self.process_offer(sdp)

    def _drain_suppressed(self):
        self.suppress_active = False
        q, self.offer_queue = self.offer_queue, []
        self.log(f"suppression window over: draining {len(q)} queued offer(s) in order")
        for s in q:
            self.process_offer(s)
        return False

    def process_offer(self, sdp):
        if self.pipeline is None:
            self.build_pipeline()
        self._pending_offer_text = sdp
        res, msg = GstSdp.SDPMessage.new_from_text(sdp)
        assert res == GstSdp.SDPResult.OK, f"SDP parse failed: {res}"
        self._log_setup_attr(msg.as_text(), "browser offer")
        desc = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER, msg)
        promise = Gst.Promise.new_with_change_func(self._on_srd_offer_done, None, None)
        self.webrtc.emit("set-remote-description", desc, promise)

    def _on_srd_offer_done(self, promise, *_):
        reply = promise.get_reply()
        if reply and not reply.get_value("ok"):
            # M5 生产容错:脏协商态(游魂 peer 残留/前一 epoch 中断)下 SRD 会拒——
            # 重建管线后对同一 offer 重试一次(每 offer 只重试一回,防环;仍败等浏览器
            # 5s loopResendOffer 再来)。promise 回调(流线程)不直接动管线 → idle 派发。
            text = self._pending_offer_text
            self.log(f"SRD offer reply not ok — {'retrying once after rebuild' if text != self._srd_retried_text else 'retry already spent, waiting browser resend'}")
            if text and text != self._srd_retried_text:
                self._srd_retried_text = text
                GLib.idle_add(self._srd_retry, text)
            return
        self.remote_set = True
        self.log("SRD(offer) ok — flushing buffered candidates")
        for mline, cand in self.pending_candidates:
            self.add_candidate(mline, cand)
        self.pending_candidates = []
        promise2 = Gst.Promise.new_with_change_func(self._on_answer_created, None, None)
        self.webrtc.emit("create-answer", None, promise2)

    def _srd_retry(self, text):
        self.teardown()
        self.process_offer(text)
        return False
        self.remote_set = True
        self.log("SRD(offer) ok — flushing buffered candidates")
        for mline, cand in self.pending_candidates:
            self.add_candidate(mline, cand)
        self.pending_candidates = []
        promise2 = Gst.Promise.new_with_change_func(self._on_answer_created, None, None)
        self.webrtc.emit("create-answer", None, promise2)

    def _on_answer_created(self, promise, *_):
        reply = promise.get_reply()
        answer = reply.get_value("answer")
        # pygi 坑:get_value 返回非持有引用,promise 回调返回后底层对象可能释放
        # → 立即取出文本副本保存,后续回调只用文本。
        self._pending_answer_text = answer.sdp.as_text()
        self._log_setup_attr(self._pending_answer_text, "our answer")
        promise3 = Gst.Promise.new_with_change_func(self._on_sld_answer, None, None)
        self.webrtc.emit("set-local-description", answer, promise3)

    def _on_sld_answer(self, promise, *_):
        promise.get_reply()
        text = self._pending_answer_text
        self.answer1_sent = True
        self._dump_sdp("answer1", text)
        self.log(f"answer#1 out (sdp_len={len(text)}) envelope=Unity-shape from={self.peer_id}")
        self.ws_send({
            "from": self.peer_id, "to": "", "type": "answer",
            "data": {"connectionId": self.peer_id, "sdp": text,
                     "type": "answer", "polite": False},  # 现役 Unity 样例同款尾字段
        })

    def srd_answer(self, sdp):
        if self.pipeline is None:
            self.log("answer without pipeline — ignoring (stale after teardown?)")
            return
        res, msg = GstSdp.SDPMessage.new_from_text(sdp)
        assert res == GstSdp.SDPResult.OK
        desc = GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.ANSWER, msg)
        promise = Gst.Promise.new_with_change_func(self._on_srd_answer_done, None, None)
        self.webrtc.emit("set-remote-description", desc, promise)

    def _on_srd_answer_done(self, promise, *_):
        reply = promise.get_reply()
        if reply and not reply.get_value("ok"):
            self.log(f"SRD answer reply not ok: {reply}")
            return
        self.log("SRD(answer#2) ok — video transport up, starting encode branch flow")
        self.video_transport_ready = True
        if self.video_linked:
            # 从 promise 回调(流线程)直接做状态迁移有死锁风险 → 打到主循环线程执行
            GLib.idle_add(self._sync_branch_playing)
        else:
            self.log("WARNING: answer#2 arrived before video branch linked")

    def _sync_branch_playing(self):
        if self.pipeline is None:
            return False
        for name in ("vsrc", "cf_raw", "vconv", "cf_nv12", "enc", "parse", "pay", "cf_rtp"):
            el = self.pipeline.get_by_name(name)
            if el is not None:
                el.sync_state_with_parent()
        self.log("encode branch synced to PLAYING")
        return False

    def add_candidate(self, mline, candidate):
        if candidate is None:
            return
        if not self.remote_set:
            self.pending_candidates.append((mline, candidate))
            self.log("  buffered (no remote description yet)")
            return
        try:
            self.webrtc.emit("add-ice-candidate", mline, candidate)
        except Exception as e:  # noqa: BLE001
            self.log(f"add-ice-candidate error: {e}")

    # ---------- 管线 ----------
    def build_pipeline(self):
        # 只建 webrtcbin(编码支线若提前 PLAYING 而 pay.src 无处可推,会以流错误杀死
        # 源元素——实测 not-negotiated/-4;支线延到 ICE connected 后再建再链)。
        self.pipeline = Gst.Pipeline.new("spike-pipeline")
        self.webrtc = Gst.ElementFactory.make("webrtcbin", "wb")
        # Unity 对拍:a=group:BUNDLE 全捆绑(实测默认 none 时 offer#2 的各 m-line 独立
        # transport,视频 transport ICE 不通 → 首帧后发送侧阻塞)。
        self.webrtc.set_property("bundle-policy", "max-bundle")
        self.pipeline.add(self.webrtc)
        self.webrtc.connect("on-ice-candidate", self._on_ice_candidate)
        self.webrtc.connect("on-negotiation-needed", self._on_negotiation_needed)
        # 实测 1.24.2:notify::ice-connection-state 不触发(属性停在 new)而
        # notify::connection-state 会到 connected —— 双轨监听,任一 connected 即挂视频。
        self.webrtc.connect("notify::ice-connection-state", self._on_ice_state)
        self.webrtc.connect("notify::connection-state", self._on_conn_state)
        self.webrtc.connect("on-data-channel", self._on_remote_data_channel)
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_msg)
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        self.log(f"pipeline PLAYING (ret={ret.value_nick}) — waiting offer")

    def _build_video_branch(self):
        """ICE connected 后建编码支线并链入 webrtcbin(带 transport 前丢帧探针)。"""
        a = self.args
        if a.source == "x11":
            # M3 真画面:Xvfb :93 屏幕旁路采集(DESIGN §2 M3/§5.2)。
            # use-damage=false 走 XShmGetImage 全幅(报告二 §1.3);caps 钉 framerate 作采集钟;
            # 其后必接 videoconvert→NV12(Xvfb 24 位屏 BGRx 不在 nvh264enc sink 集,复审 C4)。
            vsrc = Gst.ElementFactory.make("ximagesrc", "vsrc")
            vsrc.set_property("display-name", a.display)
            vsrc.set_property("use-damage", False)
            vsrc.set_property("show-pointer", False)
            vsrc.set_property("startx", 0)
            vsrc.set_property("starty", 0)
            vsrc.set_property("endx", a.width - 1)
            vsrc.set_property("endy", a.height - 1)
        else:
            vsrc = Gst.ElementFactory.make("videotestsrc", "vsrc")
            vsrc.set_property("is-live", True)
            vsrc.set_property("pattern", a.pattern)
        vconv = Gst.ElementFactory.make("videoconvert", "vconv")
        cf_raw = Gst.ElementFactory.make("capsfilter", "cf_raw")
        cf_raw.set_property("caps", Gst.Caps.from_string(
            f"video/x-raw,width={a.width},height={a.height},framerate={a.fps}/1"))
        cf_nv12 = Gst.ElementFactory.make("capsfilter", "cf_nv12")
        cf_nv12.set_property("caps", Gst.Caps.from_string("video/x-raw,format=NV12"))
        enc = Gst.ElementFactory.make("nvautogpuh264enc", "enc")
        for k, v in [
            ("cuda-device-id", 1), ("preset", "p4"), ("tune", "ultra-low-latency"),
            ("rate-control", "cbr"), ("b-frames", 0), ("zero-reorder-delay", True),
            ("rc-lookahead", 0), ("gop-size", a.gop_size or (60 if a.fps <= 30 else a.fps * 2)),
            ("repeat-sequence-header", True), ("qos", True), ("bitrate", a.bitrate),
        ]:
            enc.set_property(k, v)
        parse = Gst.ElementFactory.make("h264parse", "parse")
        pay = Gst.ElementFactory.make("rtph264pay", "pay")
        pay.set_property("config-interval", -1)
        pay.set_property("pt", a.payload)
        cf_rtp = Gst.ElementFactory.make("capsfilter", "cf_rtp")
        # 注意:profile-level-id=42e033 会被 caps 解析器当科学计数法 double(4.2e34,实测
        # webrtcbin:6 调试抓到)→ 与浏览器 answer 的 (string) 型 ptmap 不匹配 → 推流
        # not-negotiated。RTP 侧 caps 只保留经典四字段,profile 差异交由功能解码判据。
        cf_rtp.set_property("caps", Gst.Caps.from_string(
            "application/x-rtp,media=video,encoding-name=H264,payload=%d,clock-rate=90000" % a.payload))
        els = [vsrc, cf_raw, vconv, cf_nv12, enc, parse, pay, cf_rtp]
        for el in els:
            self.pipeline.add(el)
        ok = True
        for src, dst in [
            (vsrc, cf_raw), (cf_raw, vconv), (vconv, cf_nv12),
            (cf_nv12, enc), (enc, parse), (parse, pay), (pay, cf_rtp),
        ]:
            ok = ok and src.link(dst)
        assert ok, "encode branch link failed"
        # 探针:PLI→GstForceKeyUnit(上行事件)、IDR(非 delta 帧)、SPS profile
        enc.get_static_pad("sink").add_probe(Gst.PadProbeType.EVENT_UPSTREAM, self._fku_probe)
        enc.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, self._keyframe_probe)
        parse.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, self._sps_probe)
        self.pay = pay
        # 可选丢包窗(PLI→FKU→IDR 直证):--drop-window <start_s>:<dur_s> 在窗口内丢弃
        # 发出的 RTP 包,浏览器解码器丢包 → PLI → webrtcbin GstForceKeyUnit → 编码器 IDR。
        if self.args.drop_window:
            ds, dd = self.args.drop_window.split(":")
            self._drop_at = float(ds)
            self._drop_until = float(ds) + float(dd)
            cf_rtp.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, self._loss_probe)
            self.log(f"drop window armed: [{self._drop_at}s, {self._drop_until}s) of wallclock")
        return cf_rtp

    def _loss_probe(self, pad, info):
        now = monotonic() - self.t0
        if self._drop_at <= now < self._drop_until:
            self._dropped_pkts = getattr(self, "_dropped_pkts", 0) + 1
            if self._dropped_pkts <= 3 or self._dropped_pkts % 50 == 0:
                self.log(f"loss-inject: dropped RTP pkt #{self._dropped_pkts} @ {now:.3f}")
            return Gst.PadProbeReturn.DROP
        return Gst.PadProbeReturn.OK

    def _on_bus_msg(self, _bus, msg):
        if msg.type == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            self.log(f"BUS ERROR {err.message} debug={dbg}")
        elif msg.type == Gst.MessageType.WARNING:
            err, dbg = msg.parse_warning()
            self.log(f"BUS WARN {err.message}")

    def _fku_probe(self, pad, info):
        ev = info.get_event()
        if ev and ev.type == Gst.EventType.CUSTOM_UPSTREAM:
            st = ev.get_structure()
            if st and st.get_name() == "GstForceKeyUnit":
                self.fku_events += 1
                self.last_fku_ts = monotonic() - self.t0
                self.log(f"FKU event #{self.fku_events} (PLI/FIR from browser) @ {self.last_fku_ts:.3f}")
        return Gst.PadProbeReturn.OK

    def _keyframe_probe(self, pad, info):
        buf = info.get_buffer()
        if buf is not None and not buf.has_flags(Gst.BufferFlags.DELTA_UNIT):
            self.keyframes += 1
            self.frames_encoded += 1
            self.last_keyframe_ts = monotonic() - self.t0
            if self.keyframes <= 5 or self.keyframes % 300 == 0:
                self.log(f"IDR/keyframe #{self.keyframes} @ {self.last_keyframe_ts:.3f}")
        else:
            self.frames_encoded += 1
        return Gst.PadProbeReturn.OK

    def _sps_probe(self, pad, info):
        buf = info.get_buffer()
        if buf is None or self.sps_profile is not None:
            return Gst.PadProbeReturn.OK
        caps = pad.get_current_caps() or pad.query_caps(None)
        sf = caps.get_structure(0).get_value("stream-format") if caps.get_size() else None
        data = None
        if buf.get_size() > 8:
            okc, mapinfo = buf.map(Gst.MapFlags.READ)
            if okc:
                data = bytes(mapinfo.data)
                buf.unmap(mapinfo)
        if data is None:
            return Gst.PadProbeReturn.OK
        if sf == "avc":
            cd = caps.get_structure(0).get_value("codec_data")
            if cd is not None:
                okm, mi = cd.map(Gst.MapFlags.READ)
                if okm:
                    cdb = bytes(mi.data)
                    cd.unmap(mi)
                    self.sps_profile, self.sps_level = cdb[1], cdb[3]
        else:  # byte-stream: 找起始码后的 SPS NAL(类型 7)
            for sc in (b"\x00\x00\x00\x01", b"\x00\x00\x01"):
                idx = data.find(sc)
                while idx != -1:
                    nal_start = idx + len(sc)
                    if nal_start < len(data) and (data[nal_start] & 0x1F) == 7:
                        self.sps_profile = data[nal_start + 1]
                        self.sps_level = data[nal_start + 3]
                        break
                    idx = data.find(sc, idx + 1)
                if self.sps_profile is not None:
                    break
        if self.sps_profile is not None:
            names = {66: "Baseline", 77: "Main", 100: "High", 88: "Extended", 244: "Constrained-High?!"}
            self.log(f"H264 SPS profile_idc={self.sps_profile} ({names.get(self.sps_profile,'?')}) "
                     f"level_idc={self.sps_level} (caps stream-format={sf})")
        return Gst.PadProbeReturn.OK

    # ---------- ICE/协商 ----------
    def _on_ice_candidate(self, webrtc, mline, candidate):
        self.cands_out += 1
        # Unity 信封:sdpMid 为字符串,sdpMLineIndex 为 int(实测样例)
        self.ws_send({
            "from": self.peer_id, "to": "", "type": "candidate",
            "data": {
                "connectionId": self.peer_id,
                "candidate": candidate,
                "sdpMid": str(mline),
                "sdpMLineIndex": mline,
            },
        })

    def _on_ice_state(self, webrtc, pspec):
        state = webrtc.get_property("ice-connection-state")
        self.log(f"ice-connection-state -> {state.value_nick}")
        if state == GstWebRTC.WebRTCICEConnectionState.CONNECTED and not self.video_linked:
            GLib.idle_add(self.attach_video_and_offer2)

    def _on_conn_state(self, webrtc, pspec):
        state = webrtc.get_property("connection-state")
        self.log(f"connection-state -> {state.value_nick}")
        if state == GstWebRTC.WebRTCPeerConnectionState.CONNECTED and not self.video_linked:
            GLib.idle_add(self.attach_video_and_offer2)

    def _drop_until_transport(self, pad, info):
        if self.video_transport_ready and self.pipeline is not None:
            return Gst.PadProbeReturn.OK
        return Gst.PadProbeReturn.DROP

    def _on_negotiation_needed(self, webrtc):
        self.log("on-negotiation-needed fired "
                 f"(offer2_sent={self.offer2_sent}, video_linked={self.video_linked})")

    def _on_remote_data_channel(self, webrtc, channel):
        self.log(f"on-data-channel (remote created): label={channel.get_property('label')}")

    def attach_video_and_offer2(self):
        if self.video_linked or self.pipeline is None:
            return False
        a = self.args
        self.log("ICE connected — creating data channel 'twin-bridge' (before offer#2)")
        try:
            self.channel = self.webrtc.emit("create-data-channel", "twin-bridge", None)
            self.channel.connect("on-open", lambda ch: self._on_channel_open(ch))
            self.channel.connect("on-message-string", lambda ch, s: self._on_channel_string(ch, s))
            self.log(f"create-data-channel('twin-bridge') -> {self.channel}")
        except Exception as e:  # noqa: BLE001
            self.log(f"create-data-channel failed: {e}")
        cf_rtp = self._build_video_branch()
        sinkpad = self.webrtc.request_pad_simple("sink_%u")
        assert sinkpad is not None, "no sink pad from webrtcbin"
        # sendonly:pad 自带 transceiver 属性(pygi 的 get-transceivers 返回 GLib.Array
        # 不可迭代,走 pad.transceiver 直取;实测 add-transceiver 会另造一条 m-line,弃用)
        try:
            trans = sinkpad.get_property("transceiver")
            trans.set_property("direction", GstWebRTC.WebRTCRTPTransceiverDirection.SENDONLY)
            self.log(f"sink pad transceiver -> SENDONLY ({trans})")
        except Exception as e:  # noqa: BLE001
            self.log(f"transceiver direction set failed: {e}")
        if cf_rtp.get_static_pad("src").link(sinkpad) != Gst.PadLinkReturn.OK:
            self.log("FATAL: link branch->webrtcbin failed")
            return False
        self.video_linked = True
        self.log("video branch linked (elements READY until answer#2 transport)")
        self.do_offer2()
        return False

    def do_offer2(self):
        if self.offer2_sent or self.pipeline is None:
            return
        self.offer2_sent = True
        promise = Gst.Promise.new_with_change_func(self._on_offer2_created, None, None)
        self.webrtc.emit("create-offer", None, promise)
        self.log("create-offer#2 emitted")

    def _on_offer2_created(self, promise, *_):
        reply = promise.get_reply()
        offer = reply.get_value("offer")
        self._pending_offer_text = offer.sdp.as_text()  # 同 pygi 坑:只留文本
        promise2 = Gst.Promise.new_with_change_func(self._on_sld_offer2, None, None)
        self.webrtc.emit("set-local-description", offer, promise2)

    def _on_sld_offer2(self, promise, *_):
        promise.get_reply()
        text = self._pending_offer_text
        self._dump_sdp("offer2", text)
        self._log_setup_attr(text, "our offer#2")
        self.log(f"offer#2 out (sdp_len={len(text)}) from={self.peer_id}")
        self.ws_send({
            "from": self.peer_id, "to": "", "type": "offer",
            "data": {"connectionId": self.peer_id, "sdp": text,
                     "type": "offer", "polite": False},  # Unity offer 样例变体之一
        })

    # ---------- datachannel ----------
    def _on_channel_open(self, channel):
        self.channel_open = True
        self.log("twin-bridge channel OPEN")

    def _on_channel_string(self, channel, s):
        self.log(f"twin-bridge << {s[:120]}")
        if self._maybe_apply_stream_profile(s):
            return
        self._bridge_queue.put(s)  # 浏览器 → Unity(回环转发;单写线程保序)

    def _maybe_apply_stream_profile(self, s):
        """stream_profile 拦截(DESIGN §2 M5③):映射编码档位,不转发 Unity。

        返回 True = 已拦截。编码支线未建时也拦截(Unity 不再消费该 type,转发了也是死信)。
        """
        try:
            msg = json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return False
        if not isinstance(msg, dict) or msg.get("type") != "stream_profile":
            return False
        value = msg.get("value")
        kbps = STREAM_PROFILE_BITRATE_KBPS.get(value)
        if kbps is None:
            self.log(f"stream_profile: unknown value {value!r} — forwarding to Unity")
            return False
        enc = self.pipeline.get_by_name("enc") if self.pipeline is not None else None
        if enc is not None:
            enc.set_property("bitrate", kbps)
        self.profile_applied = value
        self.log(f"stream_profile {value} -> encoder bitrate {kbps} kbps"
                 f"{' (encoder not built yet)' if enc is None else ''} [intercepted]")
        return True

    # ---------- twin-bridge ↔ Unity 本地回环转发(M5) ----------
    def start_bridge(self):
        threading.Thread(target=self._bridge_loop, daemon=True, name="bridge-link").start()
        threading.Thread(target=self._bridge_writer, daemon=True, name="bridge-writer").start()

    def _bridge_loop(self):
        """连接 Unity TwinBridgeLocalChannel(127.0.0.1:bridge_port),读侧循环 + 断线重连。"""
        while not self._bridge_stop.is_set():
            try:
                sock = socket.create_connection(("127.0.0.1", self.args.bridge_port), timeout=5)
            except OSError:
                self._bridge_stop.wait(1.0)  # player 未起/重启窗口:1s 退避重试
                continue
            sock.settimeout(None)
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass
            with self._bridge_lock:
                self.bridge_sock = sock
            self.log(f"bridge: connected to Unity local channel 127.0.0.1:{self.args.bridge_port}")
            try:
                for raw in sock.makefile("rb"):
                    if self._bridge_stop.is_set():
                        break
                    GLib.idle_add(self._on_bridge_line, raw)
            except OSError:
                pass
            with self._bridge_lock:
                if self.bridge_sock is sock:
                    self.bridge_sock = None
            try:
                sock.close()
            except OSError:
                pass
            if self.channel_open:
                # player 掉线:浏览器 PC 已成死链,拆掉让 web 侧 watchdog 重连收敛
                self.log("bridge: Unity link lost with browser attached — tearing down stale PC")
                GLib.idle_add(self.teardown)
            else:
                self.log("bridge: Unity link lost — reconnecting")
            self._bridge_stop.wait(1.0)

    def _bridge_writer(self):
        while not self._bridge_stop.is_set():
            try:
                s = self._bridge_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            with self._bridge_lock:
                sock = self.bridge_sock
            if sock is None:
                continue  # 无链:丢弃(与 Unity 侧未连接丢弃语义一致;web 会随重连重发关键消息)
            try:
                sock.sendall((s + "\n").encode("utf-8"))
            except OSError:
                pass  # 断链由读线程判定触发重连

    def _on_bridge_line(self, raw):
        """Unity → 浏览器(GLib 主线程,idle 单发)。"""
        line = raw.decode("utf-8", "replace").rstrip("\n")
        if line and self.channel is not None and self.channel_open:
            self.channel.emit("send-string", line)
        return False

    def stop_bridge(self):
        self._bridge_stop.set()
        with self._bridge_lock:
            sock = self.bridge_sock
            self.bridge_sock = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    # ---------- 拆除/杂项 ----------
    def teardown(self):
        if self.pipeline is not None:
            self.log("teardown: pipeline -> NULL")
            self.pipeline.set_state(Gst.State.NULL)
        self.pipeline = None
        self.webrtc = None
        self.peer_id = None
        self.video_linked = False
        self.video_transport_ready = False
        self.offer2_sent = False
        self.answer1_sent = False
        self.remote_set = False
        self.channel = None
        self.channel_open = False
        self.suppress_done = self.args.suppress_answer_ms <= 0
        self.log("teardown done — ready for next offer")

    def _dump_sdp(self, name, text):
        path = os.path.join(self.sdp_dir, f"{self.args.label}-{name}.sdp")
        with open(path, "w") as f:
            f.write(text)

    def _log_setup_attr(self, sdp_text, tag):
        for line in sdp_text.splitlines():
            if line.startswith("a=setup:") or line.startswith("a=send") or line.startswith("a=recv"):
                self.log(f"  [{tag}] {line}")

    def status_line(self):
        ice = conn = "n/a"
        if self.webrtc is not None:
            ice = self.webrtc.get_property("ice-connection-state").value_nick
            conn = self.webrtc.get_property("connection-state").value_nick
        self.log(
            f"STATUS ice={ice} conn={conn} offers_in={self.offers_in} answers_in={self.answers_in} "
            f"cands={self.cands_in}/{self.cands_out} enc_frames={self.frames_encoded} "
            f"keyframes={self.keyframes} fku={self.fku_events} dc={self.channel_open} "
            f"bridge={'up' if self.bridge_sock is not None else 'down'} profile={self.profile_applied} "
            f"sps={self.sps_profile}/{self.sps_level}")

    # ---------- asyncio 线程 ----------
    async def ws_loop(self):
        self.loop = asyncio.get_running_loop()  # 必须取真正在跑的 loop(asyncio.run 内建)
        url = self.args.ws_url
        self.log(f"connecting signaling WS {url}")
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            self.ws = ws
            self.log("WS connected — silent wait for browser offer (no connect registration, Unity-style)")
            async for raw in ws:
                GLib.idle_add(self.on_ws_message, raw)
            self.log("WS closed by server")
        self.ws = None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ws-url", default="ws://127.0.0.1:8081")
    ap.add_argument("--width", type=int, default=2560)
    ap.add_argument("--height", type=int, default=1440)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--gop-size", type=int, default=0,
                    help="0=自动(30fps 档 60 / 60fps 档 2x);显式覆盖(如丢包恢复上界需 1s 时 gop=30)")
    ap.add_argument("--bitrate", type=int, default=20000)  # kbps
    ap.add_argument("--payload", type=int, default=123)
    ap.add_argument("--source", choices=["test", "x11"], default="test",
                    help="test=videotestsrc 测试图;x11=Xvfb 屏幕采集(M3 真画面)")
    ap.add_argument("--display", default=":93", help="x11 源的 X display")
    ap.add_argument("--pattern", default="smpte")  # videotestsrc 图案(带滚动计数条,肉眼可辨动/静)
    ap.add_argument("--label", default="spike")
    ap.add_argument("--log-dir", default="/out/spike")
    ap.add_argument("--suppress-answer-ms", type=int, default=0)
    ap.add_argument("--drop-window", default="", help="start_s:dur_s — 定时丢弃发出 RTP(PLI 直证)")
    ap.add_argument("--duration-s", type=int, default=0)
    ap.add_argument("--bridge-port", type=int, default=18020,
                    help="M5 twin-bridge 转发目标:Unity TwinBridgeLocalChannel 回环端口")
    args = ap.parse_args()
    os.makedirs(args.log_dir, exist_ok=True)

    sender = Sender(args)
    Gst.init(None)
    ml = GLib.MainLoop()

    def watchdog():
        sender.status_line()
        return True

    def quit_after():
        sender.log("duration reached — exiting")
        ml.quit()
        return False

    GLib.timeout_add_seconds(10, watchdog)
    if args.duration_s > 0:
        GLib.timeout_add_seconds(args.duration_s, quit_after)

    ws_thread = threading.Thread(target=lambda: asyncio.run(sender.ws_loop()), daemon=True)

    def on_bus(bus, msg):
        if msg.type == Gst.MessageType.ERROR:
            err, dbg = msg.parse_error()
            sender.log(f"BUS ERROR {err.message} debug={dbg}")
        elif msg.type == Gst.MessageType.WARNING:
            err, dbg = msg.parse_warning()
            sender.log(f"BUS WARN {err.message}")

    # 总线挂接在 build_pipeline 内(_on_bus_msg)

    ws_thread.start()
    sender.start_bridge()  # M5:Unity 本地回环转发(读+写线程,断线自愈)
    try:
        ml.run()
    except KeyboardInterrupt:
        pass
    sender.teardown()
    sender.stop_bridge()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
