// Sango URS Spike browser page (P2-S2 decision gate, spec #89).
// Mirrors the official receiver sample (video + native input channel) and adds:
//  - "spike-echo" data channel (Unity-local): JSON echo RTT + control commands
//  - getStats polling -> window.__ursStats (rtt/jitter/fps/decodeMs)
//  - timeline of lifecycle events -> window.__ursTimeline (reconnection evidence)
import { getServerConfig, getRTCConfiguration } from "../../js/config.js";
import { VideoPlayer } from "../../js/videoplayer.js";
import { RenderStreaming } from "../../module/renderstreaming.js";
import { Signaling, WebSocketSignaling } from "../../module/signaling.js";

const statusDiv = document.getElementById('spikeStatus');
const playerDiv = document.getElementById('player');
const lockMouseCheck = document.getElementById('lockMouseCheck');
const videoPlayer = new VideoPlayer();

const timeline = [];
function mark(event) {
  const entry = { t: performance.now(), wall: new Date().toISOString(), event };
  timeline.push(entry);
  statusDiv.textContent = timeline.map(e => `${e.wall} +${(e.t / 1000).toFixed(2)}s ${e.event}`).join('\n');
  console.log('[URS-SPIKE]', JSON.stringify(entry));
}
window.__ursTimeline = timeline;

let renderstreaming = null;
let echoChannel = null;
let connectionId = null;
const echoRttMs = [];
const pendingPings = new Map(); // sendTs -> performance.now()
window.__ursDcRttMs = echoRttMs;

async function run() {
  mark('page-load');
  const res = await getServerConfig();
  videoPlayer.createPlayer(playerDiv, lockMouseCheck);
  if (videoPlayer.videoElement) videoPlayer.videoElement.muted = true;
  const signaling = res.useWebSocket ? new WebSocketSignaling() : new Signaling();
  renderstreaming = new RenderStreaming(signaling, getRTCConfiguration());
  renderstreaming.onConnect = (id) => {
    connectionId = id;
    mark(`onConnect ${id}`);
    const inputChannel = renderstreaming.createDataChannel('input');
    videoPlayer.setupInput(inputChannel);
    mark('input-channel-created');
  };
  renderstreaming.onDisconnect = async (id) => {
    mark(`onDisconnect ${id}`);
    await renderstreaming.stop();
    renderstreaming = null;
    videoPlayer.deletePlayer();
  };
  renderstreaming.onTrackEvent = (data) => {
    videoPlayer.addTrack(data.track);
    // WebRTC 视频轨无音轨，muted 播放绕过 autoplay 策略
    if (videoPlayer.videoElement) { videoPlayer.videoElement.muted = true; }
    mark(`onTrack ${data.track.kind} ${data.track.label}`);
  };
  renderstreaming.onAddChannel = (data) => {
    mark(`onAddChannel label=${data.channel && data.channel.label}`);
    if (data.channel && data.channel.label === 'spike-echo') {
      echoChannel = data.channel;
      echoChannel.onmessage = (e) => onEchoMessage(e.data);
      echoChannel.onopen = () => { mark('spike-echo OPEN'); startEchoPing(); };
    }
  };
  mark('signaling-start');
  await renderstreaming.start();
  await renderstreaming.createConnection();
  mark('createConnection-done');
}

function onEchoMessage(data) {
  let msg;
  try { msg = JSON.parse(data); } catch (err) { mark(`echo-parse-fail`); return; }
  if (msg.type === 'pong') {
    const echo = msg.echo || {};
    const key = String(echo.sendTs);
    if (pendingPings.has(key)) {
      const sentAt = pendingPings.get(key);
      pendingPings.delete(key);
      const rtt = performance.now() - sentAt;
      echoRttMs.push(rtt);
      console.log('[URS-SPIKE] dc-rtt', rtt.toFixed(1), 'ms; unityRecv-skew', (msg.unityRecvUnixMs - (window.__unixAtSend || 0)));
    }
  } else if (msg.type === 'clock') {
    // Unity 墙钟单向到达：到页时差（含编码+网络+抖动，不含解码后渲染）
    window.__ursLastClock = msg;
  }
}

function startEchoPing() {
  setInterval(() => {
    if (!echoChannel || echoChannel.readyState !== 'open') return;
    const sendTs = performance.now();
    window.__unixAtSend = Date.now();
    pendingPings.set(String(sendTs), sendTs);
    echoChannel.send(JSON.stringify({ type: 'ping', cmd: 'ping', sendTs }));
  }, 2000);
}

// getStats 轮询 → window.__ursStats（rtt/jitter/fps/decodeMs/分辨率/编解码器）
async function pollStats() {
  if (!renderstreaming) return;
  try {
    const stats = await renderstreaming.getStats();
    if (!stats) return;
    const out = { ts: performance.now() };
    stats.forEach(r => {
      if (r.type === 'inbound-rtp' && r.kind === 'video') {
        out.jitterMs = (r.jitter || 0) * 1000;
        out.fps = r.framesPerSecond;
        out.framesDecoded = r.framesDecoded;
        out.totalDecodeMs = (r.totalDecodeTime || 0) * 1000;
        out.decodeMsPerFrame = r.framesDecoded ? ((r.totalDecodeTime || 0) / r.framesDecoded) * 1000 : null;
        out.interFrameMsAvg = r.totalInterFrameDelay && r.framesDecoded ? (r.totalInterFrameDelay * 1000) / r.framesDecoded : null;
        out.width = r.frameWidth; out.height = r.frameHeight;
        out.bytes = r.bytesReceived;
        out.nackCount = r.nackCount; out.pliCount = r.pliCount;
        out.jitterBufferMs = r.jitterBufferDelay && r.jitterBufferEmittedCount ? (r.jitterBufferDelay * 1000) / r.jitterBufferEmittedCount : null;
      }
      if (r.type === 'candidate-pair' && r.state === 'succeeded' && r.currentRoundTripTime != null) {
        out.iceRttMs = r.currentRoundTripTime * 1000;
      }
      if (r.type === 'outbound-rtp' && r.kind === 'video') {
        out.outFps = r.framesPerSecond; out.outBitrateBps = r.targetBitrate;
      }
    });
    window.__ursStats = out;
    console.log('[URS-SPIKE] stats', JSON.stringify(out));
  } catch (err) { /* peer gone during reconnect; ignore */ }
}
setInterval(pollStats, 1000);

// 键盘证据：页面 keydown 记录（原生输入链路由 VideoPlayer.setupInput 序列化上行）
document.addEventListener('keydown', (e) => {
  console.log('[URS-SPIKE] keydown', e.code);
  mark(`keydown ${e.code}`);
});

// 控制命令便捷入口（console 可调）：window.ursCmd('view','TopDown') 等
window.ursCmd = (cmd, param) => {
  if (!echoChannel || echoChannel.readyState !== 'open') return 'echo channel not open';
  echoChannel.send(JSON.stringify({ type: 'cmd', cmd, view: param, key: param, hours: typeof param === 'number' ? param : -1, name: param }));
  return 'sent';
};
window.ursKey = (code) => document.dispatchEvent(new KeyboardEvent('keydown', { code, bubbles: true }));

run();
