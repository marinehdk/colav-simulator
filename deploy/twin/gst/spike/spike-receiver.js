// M2 spike receiver:复刻 web_gui twin-view.js#createTwinStreamClient 的精确接收流程
// (connect → createDataChannel('input') → offer#1(仅 m=application)→ onTrack → video),
// 信令指向 8081 第二 webapp 实例;对端为 GStreamer webrtcbin sender(sender.py)。
// 计数器/采样暴露在 window.__spike 供 CDP 读取(口径:web_gui/modules/twin-stream-quality.js)。
import { WebSocketSignaling } from './vendor/urs/signaling.js';
import { RenderStreaming } from './vendor/urs/renderstreaming.js';
import { sampleTwinVideoStats } from './twin-stream-quality.js';

const params = new URLSearchParams(location.search);
const SIGNALING_URL = params.get('signaling') || 'ws://127.0.0.1:8081';

const video = document.getElementById('spikeVideo');
const statusEl = document.getElementById('status');

const spike = window.__spike = {
  signalingUrl: SIGNALING_URL,
  startedAt: performance.now(),
  phase: 'boot',           // boot → ws-open → connecting → streaming → dead
  connectionId: null,
  offersSent: [], answersSent: 0, offersReceived: 0, answersReceived: 0,
  candidatesSent: 0, candidatesReceived: 0,
  offerTimes: [],          // performance.now() of each sendOffer(含重发)
  answer1At: null, answer2At: null, iceConnectedAt: null,
  trackAdded: false, trackAt: null,
  channelOpen: false, channelOpenedAt: null, echoRtts: [],
  firstFrameAt: null,      // 首帧 decode(framesDecoded>0)
  errors: [], samples: [],
  videoSize: null,
};

function setStatus(line) {
  statusEl.textContent =
    `${spike.phase} | ${line}\n` +
    `offersSent=${spike.offersSent.length} offersReceived=${spike.offersReceived} ` +
    `answersSent=${spike.answersSent} answersReceived=${spike.answersReceived} ` +
    `ice=${spike.iceConnectedAt ? 'connected' : '…'} track=${spike.trackAdded} ` +
    `dc=${spike.channelOpen} echo=${spike.echoRtts.length} first=${spike.firstFrameAt ? 'Y' : 'N'}`;
}

async function main() {
  const signaling = new WebSocketSignaling(1000, SIGNALING_URL);
  const rs = new RenderStreaming(signaling, { sdpSemantics: 'unified-plan', iceServers: [] });

  // 计数钩子(信封行为不改动,仅旁路计数)
  const origSendOffer = signaling.sendOffer.bind(signaling);
  signaling.sendOffer = (id, sdp) => {
    spike.offersSent.push(sdp.length);
    spike.offerTimes.push(performance.now());
    return origSendOffer(id, sdp);
  };
  const origSendAnswer = signaling.sendAnswer.bind(signaling);
  signaling.sendAnswer = (id, sdp) => { spike.answersSent++; return origSendAnswer(id, sdp); };
  const origSendCandidate = signaling.sendCandidate.bind(signaling);
  signaling.sendCandidate = (id, c, mid, mline) => {
    spike.candidatesSent++; return origSendCandidate(id, c, mid, mline);
  };

  rs.onConnect = id => {
    spike.connectionId = id;
    spike.phase = 'connecting';
    // twin-view.js 同款:connect 后即建 input 通道,其 negotiationneeded 产生 offer#1(仅 m=application)
    try { rs.createDataChannel('input'); } catch (e) { spike.errors.push('dc:' + e); }
    setStatus(`connected id=${id}`);
  };
  rs.onDisconnect = _id => {
    spike.phase = 'dead';
    video.srcObject = null;
    setStatus('disconnected');
  };
  rs.onTrackEvent = data => {
    spike.trackAdded = true;
    spike.trackAt = performance.now();
    video.srcObject = new MediaStream([data.track]);
    video.play?.().catch(() => {});
    setStatus('track');
  };
  rs.onAddChannel = data => {
    const ch = data.channel;
    if (ch.label !== 'twin-bridge') return;
    ch.onopen = () => {
      spike.channelOpen = true;
      spike.channelOpenedAt = performance.now();
      // echo 探针×3(1s 间隔):字符串往返验证 SCTP 文本帧语义
      for (let i = 0; i < 3; i++) {
        setTimeout(() => {
          if (ch.readyState !== 'open') return;
          try {
            ch.send(JSON.stringify({ type: 'echo', seq: i, t: performance.now() }));
          } catch (e) { spike.errors.push('echo-send:' + e); }
        }, i * 1000);
      }
    };
    ch.onmessage = ev => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === 'echo') spike.echoRtts.push(Math.round((performance.now() - m.t) * 10) / 10);
      } catch { spike.echoRtts.push(-1); }
    };
    setStatus(`channel:${ch.label}`);
  };
  rs.onGotOffer = _id => { spike.offersReceived++; setStatus('gotOffer'); };
  rs.onGotAnswer = _id => {
    spike.answersReceived++;
    if (spike.answersReceived === 1) spike.answer1At = performance.now();
    if (spike.answersReceived === 2) spike.answer2At = performance.now();
    setStatus('gotAnswer');
  };

  await rs.start();
  spike.phase = 'ws-open';
  setStatus('ws open');
  await rs.createConnection();

  // ICE 状态(peer 内部 pc 不直接暴露,经 transceivers/ice state 轮询近似)
  setInterval(() => {
    const pc = rs._peer && rs._peer.pc;
    if (pc && pc.iceConnectionState === 'connected' && !spike.iceConnectedAt) {
      spike.iceConnectedAt = performance.now();
      setStatus('ice connected');
    }
  }, 100);

  // 同口径采样:1s 轮询 getStats → sampleTwinVideoStats(与产品同款)
  // M3 增补:丢包/NACK/PLI/解码 fps/冻结时长 + ICE 选中路径(坍塌归因取证)
  let prev = null;
  setInterval(async () => {
    try {
      const report = await rs.getStats();
      if (!report) return;
      const s = sampleTwinVideoStats(report, prev);
      prev = s || prev;
      if (!s) return;
      const rows = Array.from(report.values ? report.values() : report);
      const vrow = rows.find(r => r.type === 'inbound-rtp' && (r.kind ?? r.mediaType) === 'video');
      if (!spike.netPath) {
        const pair = rows.find(r => r.type === 'candidate-pair' && r.state === 'succeeded' && r.nominated);
        const rem = pair && rows.find(r => r.id === pair.remoteCandidateId);
        const loc = pair && rows.find(r => r.id === pair.localCandidateId);
        if (rem && loc) spike.netPath = {
          remote: `${rem.address ?? rem.ip}:${rem.port} ${rem.candidateType}/${rem.protocol}`,
          local: `${loc.address ?? loc.ip}:${loc.port} ${loc.candidateType}/${loc.protocol}`,
        };
      }
      if (s.framesDecoded > 0 && spike.firstFrameAt === null) {
        spike.firstFrameAt = performance.now();
        spike.phase = 'streaming';
      }
      if (s.width) spike.videoSize = `${s.width}x${s.height}`;
      spike.samples.push({
        t: Math.round(performance.now()), fps: s.fps, dropRatio: s.dropRatio,
        bitrateMbps: s.bitrateMbps, decodeMs: s.decodeMs, jitterBufferMs: s.jitterBufferMs,
        freezeCount: s.freezeCount, framesDecoded: s.framesDecoded, framesDropped: s.framesDropped,
        width: s.width, height: s.height, codec: s.codec, rttMs: s.rttMs,
        packetsLost: vrow ? (vrow.packetsLost ?? null) : null,
        lossRatio: s.lossRatio, nackCount: vrow ? (vrow.nackCount ?? null) : null,
        pliCount: vrow ? (vrow.pliCount ?? null) : null,
        framesPerSecond: vrow ? (vrow.framesPerSecond ?? null) : null,
        totalFreezeDuration: vrow ? (vrow.totalFreezeDuration ?? null) : null,
      });
    } catch (e) { spike.errors.push('stats:' + e); }
  }, 1000);
}

main().catch(e => { spike.errors.push('' + e); spike.phase = 'dead'; setStatus('FATAL ' + e); });
