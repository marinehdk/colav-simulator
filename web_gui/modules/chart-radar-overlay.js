/**
 * Chart radar overlay — Simrad "Radar overlay" 语义的 2D 海图叠加腿
 * (2026-10-23):把扫描中的雷达 PPI 视频(北上,本船为心)叠在海图上,回波与
 * 海图物标对读。解码与卡片 PPI 同源同法(复用 RadarVideoBuffer),但独立
 * 实例互不干扰;量程=后端真量程(shadow_video.range_m),不由本地视图决定。
 *
 * 观感裁决(20261023 用户验收):叠加走 Simrad 截图同款阈值化视频——无回波
 * 透明、弱杂波(雪花)抑制、只留强回波(岸线/船/障碍);卡片 PPI 的黑底是
 * 其自身语义,海图叠加不带(radarOverlayAlpha 逐像素 alpha 映射)。
 *
 * 光栅缓存键 = 视频代次+尺寸+本船米级位置+0.5s 时间桶:pan 复用,缩放/新
 * chunk/船动/时间窗推进才重算(北上相对显示与船位无关的只有背景,行龄窗
 * 与行原点平移都随船位与时间变,必须进键)。
 */
import { RadarVideoBuffer } from './radar-video.js?v=20261023-radar-card-v4';
import { N_METERS_PER_NM, sweepAzimuthRad } from './radar-ppi.js?v=20261023-radar-card-v4';

// 视频值(绿通道,0-255 LUT 线性功率)→ 叠加透明度:cut 以下全透明(海杂波
// 雪花+无回波黑底),cut..knee 线性爬升,max 封顶——强回波(岸线/船)实心、
// 边缘羽化。默认 cut=90/knee=160/max=0.85 由 20261023 实测分布校准。
export function radarOverlayAlpha(value, { cut = 90, knee = 160, max = 0.85 } = {}) {
  const level = Number(value);
  if (!(level > cut)) return 0;
  const t = Math.min(1, (level - cut) / Math.max(1, knee - cut));
  return Math.round(255 * Math.min(max, 0.12 + t * (max - 0.12)));
}

export function createChartRadarOverlay({ buffer = new RadarVideoBuffer() } = {}) {
  let streamKey = null;
  let lastVideoKey = null;
  let generation = 0;
  let pending = Promise.resolve();
  let canvas = null;
  let cacheKey = null;
  const info = { ready: false, rangeM: 0, status: 'NO_VIDEO' };

  return {
    info: () => ({ ...info }),
    settled: () => pending,
    // 每遥测拍喂最新 shadow_video;换流(run/实例)重建缓冲,同 chunk 去重。
    update(raw) {
      const scan = (Array.isArray(raw?.radar_scans) ? raw.radar_scans : [])
        .find(item => item?.sensor_label === 'radar_x');
      const stream = `${raw?.run_id ?? ''}:${scan?.sensor_instance_id ?? ''}`;
      if (stream !== streamKey) {
        streamKey = stream; lastVideoKey = null; generation++;
        buffer.clear?.();
        info.ready = false; info.rangeM = 0; info.status = 'NO_VIDEO'; cacheKey = null;
      }
      const video = scan?.shadow_video;
      const key = `${scan?.sample_seq}:${video?.chunk?.sha256}`;
      if (!video || video.status === 'INCOMPLETE' || key === lastVideoKey) return;
      lastVideoKey = key;
      const gen = generation;
      pending = pending.then(async () => {
        if (gen !== generation) return;
        try {
          await buffer.apply(video);
          info.status = buffer.status ?? 'NO_VIDEO';
          info.rangeM = Number(buffer.rangeM) > 0 ? Number(buffer.rangeM) : 0;
          info.ready = buffer.status === 'SHADOW' && info.rangeM > 0;
        } catch {
          info.ready = false; info.status = 'INVALID_VIDEO';
        }
      });
    },
    // 北上视频绘制:返回 { drew, rangeM, sweepAzRad };drew=false 表示无可用
    // 视频或无 DOM 画布(调用方回退画量程圈)。船位为绝对会话 NE(行原点平移)。
    drawVideo(ctx, centerX, centerY, pxPerM, ownshipNorth, ownshipEast, simTimeS, scanPeriodS) {
      const sweepAzRad = sweepAzimuthRad(simTimeS, scanPeriodS);
      if (!info.ready || !(pxPerM > 0)) return { drew: false, rangeM: info.rangeM, sweepAzRad };
      if (typeof document === 'undefined' || !ctx) return { drew: false, rangeM: info.rangeM, sweepAzRad };
      const sizePx = Math.max(64, Math.min(512, Math.round(info.rangeM * pxPerM * 2)));
      const key = `${lastVideoKey}|${sizePx}|${Math.round(ownshipNorth)}|${Math.round(ownshipEast)}|${Math.round(simTimeS * 2)}`;
      if (key !== cacheKey || !canvas) {
        if (!canvas) canvas = document.createElement('canvas');
        canvas.width = canvas.height = sizePx;
        const vctx = canvas.getContext('2d');
        const image = vctx.createImageData(sizePx, sizePx);
        image.data.set(buffer.raster(sizePx, { hasOwnship: true, rangeScaleM: info.rangeM,
          ownshipNorth, ownshipEast, simTimeS, scanPeriodS }, {}));
        // 阈值化+着色(20261023 二轮观感):无回波/弱杂波像素转透明;回波色从
        // 绿改量程圈同款亮黄 rgba(245,165,36)(海图底图偏绿,绿回波不显)。
        // 黄 = 视频值×(1,0.673,0.147)(按圈色归一),值满时≈圈色原值。
        for (let i = 0; i < image.data.length; i += 4) {
          const value = image.data[i + 1];
          image.data[i] = value;
          image.data[i + 1] = value * 0.673;
          image.data[i + 2] = value * 0.147;
          image.data[i + 3] = radarOverlayAlpha(value);
        }
        vctx.putImageData(image, 0, 0);
        cacheKey = key;
      }
      const spanPx = info.rangeM * pxPerM * 2;
      ctx.save();
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(canvas, centerX - spanPx / 2, centerY - spanPx / 2, spanPx, spanPx);
      ctx.restore();
      return { drew: true, rangeM: info.rangeM, sweepAzRad };
    },
  };
}

export { N_METERS_PER_NM };
