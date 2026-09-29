#!/usr/bin/env bash
# =============================================================================
# M6 正式批·数据段 —— 新加坡海峡地形 + S2 底图正式管线
#
# 输入（全部已在盘、只读；绝不写 tmp/m6-spike-data/）：
#   tmp/m6-spike-data/tiles/*.tif                Copernicus GLO-30 六 tile（30 m, EPSG:4326）
#   tmp/m6-spike-data/gebco/gebco_strait.tif     GEBCO 子集（15″, 4326, Int16, nodata=-32767,
#                                                432×864, 103.0–104.8E / 1.8S–1.8N）
#   tmp/m6-spike-data/s2/TCI_UG_2026_3_S2B_48NUG_20260320_0_L2A.tif
#                                                Sentinel-2 L2A TCI（10980²@10 m, EPSG:32648,
#                                                origin (300000,200040), 3×Byte sRGB, nodata 0）
# 输出：tmp/m6-data/{manifest.json, tiles/, basemap/, dem/}（work/ 用毕即删）
# 判据图（入库）：docs/research/2026-09-29-m6-terrain-pipeline/*.png + notes.md
#
# 固定规格（C2 双档裁决=定案，勿改；本段常量与 manifest.json 一一对应）：
#   区域中心 (103.80E, 1.28N) --gdaltransform--> UTM 48N ≈ (366493.3, 141509.9)
#       = Unity 世界原点（浮点原点约定）
#   近景带 中心±12 km = 24×24 km，2×2 tile × 12 km，高度 2049²（-tr 12000/2048 = 5.859375 m/px）
#   远景带 中心±30 km = 60×60 km，5×5 tile × 12 km，高度 513²（-tr 12000/512  = 23.4375  m/px）
#   tile 命名 {tier}_r{row}c{col}_{px}；row 0 = 最北行（与图像行序一致）
#   切片口径（采样格/vertex-grid 约定）：整带先 warp 到 (grid*px-(grid-1))² 单文件
#   （近 4097²/远 2561²，-tr 取精确值 12000/2048|512），再 gdal_translate -srcwin 按
#   step=px-1 切 tile → 相邻 tile 共享 1 px 行/列（同源像元直拷，缝隙零差异，VERIFY
#   有 checksum 断言）。带光栅 origin=逻辑域西北角（xmin,ymax），宽=4097×res = 逻辑带宽
#   24 km + 东/南各 1 共享 px；逻辑 tile 域 = 西北角起 2048 格 = 12 km（manifest
#   utm_bounds/extent_utm 均为逻辑域，Unity terrain size=12000，2049 采样跨 2048 格）。
#
# 陆海合并口径（替代 spike 的海面钳平）：
#   陆 = GLO-30 ≥ 0.5 m 用 GLO；海 = GEBCO 水深（海面下为负值）；海岸带 ~2 km feather
#   （numpy 距离场权重 w = clip(dist/2000m, 0, 1)，merged = (1-w)*GLO + w*GEBCO）平滑过渡。
#   重采样后亚米级海面残差渗入（spike 已知问题）二次清理：合并源 30 m 海陆掩膜（陆=1）
#   以 nearest 重采样到各带格网后：陆像元 max(v,0)、海像元 min(v,0)——海永不高于海平面、
#   陆永不低于海平面；feather 带的主体在海上（负值），不受 min(v,0) 影响，过渡仍平滑。
#
# u16 归一：每带单独 min/max scale（带内全域统计、带内所有 tile 共用一对参数）；
#   GTiff + ENVI RAW 双副本；字节序=小端、行序=北上（spike 实测约定，VERIFY 字节探针复核）。
# S2 底图：只用 UG 单景（60×60 km 窗在其覆盖内，边界余量 ≥10 km 脚本内断言）；
#   近景 tile 2048² / 远景 tile 512² JPG quality 90，sRGB 原色不变换。
#   VG 两景（48NVG 2026-03-20 / 2026-04-23）云量高不入管线，留作将来补丁/扩展（manifest 记）。
#
# 幂等：产物全部覆盖重生成，重跑不报错；无任何下载步骤。
# 自测：bash tools/terrain/m6_pipeline.sh 跑到 VERIFY 段全过（任一断言失败即非零退出）。
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/../.."   # 一律从仓库根执行

# ---------- 固定规格常量（改动=改规格，须同步 manifest 与 docs notes） ----------
CENTER_LON=103.80
CENTER_LAT=1.28
TARGET_EPSG=EPSG:32648          # UTM 48N（spike 勘误定案：北纬新加敞 ≠ 32748）

# DEM 全域裁剪窗（经纬度，沿用 spike）：103.40–104.40E, 1.45S–1.45N
WIN_LON_MIN=103.40; WIN_LAT_MIN=-1.45; WIN_LON_MAX=104.40; WIN_LAT_MAX=1.45
TR_M=30                         # DEM 合并格网 30 m ≈ GLO-30 原生
FEATHER_M=2000                  # 海岸 feather 宽度（约 67 个 30 m 像元）

NEAR_HALF_M=12000               # 近景带 ±12 km → 24×24 km
NEAR_PX=2049                    # 2^11+1，Unity 高度图合法尺寸
NEAR_GRID=2                     # 2×2 tile
NEAR_STEP=2048                  # srcwin 步长 = px-1（共享 1 px 边）
NEAR_TR=5.859375                # 12000/2048 精确值
NEAR_BAND_PX=4097               # 2*2049-1

FAR_HALF_M=30000                # 远景带 ±30 km → 60×60 km
FAR_PX=513                      # 2^9+1
FAR_GRID=5                      # 5×5 tile
FAR_STEP=512
FAR_TR=23.4375                  # 12000/512 精确值
FAR_BAND_PX=2561                # 5*513-4

TILE_M=12000                    # 每 tile 12×12 km
NEAR_BMP_PX=2048                # S2 底图 tile（纹理 2 的幂，无需共享边）
FAR_BMP_PX=512
S2_QUALITY=90

SRC_TILES_DIR="tmp/m6-spike-data/tiles"
SRC_GEBCO="tmp/m6-spike-data/gebco/gebco_strait.tif"
SRC_S2="tmp/m6-spike-data/s2/TCI_UG_2026_3_S2B_48NUG_20260320_0_L2A.tif"

OUT="tmp/m6-data"
DOCS="docs/research/2026-09-29-m6-terrain-pipeline"

export GDAL_PAM_ENABLED=NO      # 不生成 .aux.xml（.wld worldfile 非 PAM，不受影响）
export MPLBACKEND=Agg

mkdir -p "$OUT/dem" "$OUT/tiles" "$OUT/basemap" "$OUT/work" "$DOCS"

# 中心点 → UTM 48N（脚本实算为准；spike 实测 ≈ 366493.3, 141509.9）
read -r CX CY <<<"$(echo "$CENTER_LON $CENTER_LAT" | gdaltransform -s_srs EPSG:4326 -t_srs "$TARGET_EPSG" | awk '{printf "%.3f %.3f", $1, $2}')"
echo "[0] center ($CENTER_LON, $CENTER_LAT) -> UTM48N ($CX, $CY)  = Unity 世界原点"

NEAR_TE="$(awk -v cx="$CX" -v cy="$CY" 'BEGIN{printf "%.3f %.3f %.3f %.3f", cx-12000, cy-12000, cx+12000, cy+12000}')"
FAR_TE="$(awk -v cx="$CX" -v cy="$CY"  'BEGIN{printf "%.3f %.3f %.3f %.3f", cx-30000, cy-30000, cx+30000, cy+30000}')"
NEAR_XMIN="$(awk -v cx="$CX" 'BEGIN{printf "%.3f", cx-12000}')"; NEAR_YMIN="$(awk -v cy="$CY" 'BEGIN{printf "%.3f", cy-12000}')"
NEAR_XMAX="$(awk -v cx="$CX" 'BEGIN{printf "%.3f", cx+12000}')"; NEAR_YMAX="$(awk -v cy="$CY" 'BEGIN{printf "%.3f", cy+12000}')"
FAR_XMIN="$(awk -v cx="$CX" 'BEGIN{printf "%.3f", cx-30000}')";  FAR_YMIN="$(awk -v cy="$CY" 'BEGIN{printf "%.3f", cy-30000}')"
FAR_XMAX="$(awk -v cx="$CX" 'BEGIN{printf "%.3f", cx+30000}')";  FAR_YMAX="$(awk -v cy="$CY" 'BEGIN{printf "%.3f", cy+30000}')"

# 带光栅 -te（采样格约定，见文件头）：origin 对齐逻辑域 xmin/ymax（西北角），向东/南
# 各延 n×res（n=格数+1 → 光栅 = 逻辑带宽 + 东南各 1 共享 px）
NEAR_TE_WIDE="$(awk -v x="$NEAR_XMIN" -v y="$NEAR_YMAX" -v n="$NEAR_BAND_PX" -v r="$NEAR_TR" 'BEGIN{printf "%.6f %.6f %.6f %.6f", x, y-n*r, x+n*r, y}')"
FAR_TE_WIDE="$(awk -v x="$FAR_XMIN" -v y="$FAR_YMAX" -v n="$FAR_BAND_PX" -v r="$FAR_TR" 'BEGIN{printf "%.6f %.6f %.6f %.6f", x, y-n*r, x+n*r, y}')"

# ---------- Step 1: GLO-30 六 tile 合并 → UTM 30 m f32（沿用 spike 窗口） ----------
echo "[1] gdalwarp GLO-30 x6 -> $OUT/dem/glo_30m.tif (win $WIN_LON_MIN-$WIN_LON_MAX E / $WIN_LAT_MIN-$WIN_LAT_MAX, 30 m)"
rm -f "$OUT/dem/glo_30m.tif"
gdalwarp -q -overwrite "$SRC_TILES_DIR"/*.tif \
  -te "$WIN_LON_MIN" "$WIN_LAT_MIN" "$WIN_LON_MAX" "$WIN_LAT_MAX" -te_srs EPSG:4326 \
  -t_srs "$TARGET_EPSG" -tr $TR_M $TR_M -ot Float32 "$OUT/dem/glo_30m.tif"

# ---------- Step 2: GEBCO 子集 → 同一 30 m 格网（bilinear；nodata=-32767 → NaN） ----------
echo "[2] gdalwarp GEBCO -> $OUT/dem/gebco_30m.tif (bilinear, srcnodata -32767 -> dstnodata nan)"
rm -f "$OUT/dem/gebco_30m.tif"
gdalwarp -q -overwrite "$SRC_GEBCO" \
  -te "$WIN_LON_MIN" "$WIN_LAT_MIN" "$WIN_LON_MAX" "$WIN_LAT_MAX" -te_srs EPSG:4326 \
  -t_srs "$TARGET_EPSG" -tr $TR_M $TR_M -ot Float32 -r bilinear \
  -srcnodata -32767 -dstnodata nan "$OUT/dem/gebco_30m.tif"

# ---------- Step 3: 陆海合并（陆 GLO ≥0.5 m / 海 GEBCO / 2 km feather，numpy 距离场） ----------
echo "[3] merge land+sea -> $OUT/dem/merged_bathy_30m.tif (+ landmask_30m.tif)"
GLO30="$OUT/dem/glo_30m.tif" GEBCO30="$OUT/dem/gebco_30m.tif" \
OUT_MERGED="$OUT/dem/merged_bathy_30m.tif" OUT_MASK="$OUT/dem/landmask_30m.tif" \
FEATHER_M="$FEATHER_M" TR_M="$TR_M" python3 <<'PY'
import os
import numpy as np
from osgeo import gdal
gdal.UseExceptions()

glo_ds = gdal.Open(os.environ['GLO30']); geb_ds = gdal.Open(os.environ['GEBCO30'])
assert (glo_ds.RasterXSize, glo_ds.RasterYSize) == (geb_ds.RasterXSize, geb_ds.RasterYSize), "GLO/GEBCO 格网不一致"
assert glo_ds.GetGeoTransform() == geb_ds.GetGeoTransform(), "GLO/GEBCO geotransform 不一致"

glo = glo_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
geb = geb_ds.GetRasterBand(1).ReadAsArray().astype(np.float32)

# 陆 = GLO 有效且 ≥0.5 m（spike 钳平阈，兼滤海面插值噪声 ±数 m）
land = np.isfinite(glo) & (glo >= 0.5)
# 窗口 ⊂ GEBCO 子集范围（103–104.8E/1.8S–1.8N），NaN 仅作防御：海 NaN→0、陆 NaN→GEBCO
geb0 = np.where(np.isfinite(geb), geb, 0.0).astype(np.float32)
glo0 = np.where(np.isfinite(glo), glo, geb0).astype(np.float32)

from scipy.ndimage import distance_transform_edt
dist_m = distance_transform_edt(~land).astype(np.float32) * float(os.environ['TR_M'])
w = np.clip(dist_m / float(os.environ['FEATHER_M']), 0.0, 1.0).astype(np.float32)  # 陆=0 → ≥2km 海=1
merged = ((1.0 - w) * glo0 + w * geb0).astype(np.float32)   # 陆=GLO；远海=GEBCO；2 km 内线性过渡

drv = gdal.GetDriverByName('GTiff')
for path, arr, gdt in ((os.environ['OUT_MERGED'], merged, gdal.GDT_Float32),
                       (os.environ['OUT_MASK'], land.astype(np.uint8), gdal.GDT_Byte)):
    if os.path.exists(path): os.remove(path)
    ds = drv.Create(path, glo_ds.RasterXSize, glo_ds.RasterYSize, 1, gdt, options=['COMPRESS=DEFLATE'])
    ds.SetGeoTransform(glo_ds.GetGeoTransform()); ds.SetProjection(glo_ds.GetProjection())
    ds.GetRasterBand(1).WriteArray(arr); ds.FlushCache(); ds = None

print("  land px = %d (%.2f%%)  merged min=%.3f m  max=%.3f m" %
      (land.sum(), 100.0*land.mean(), float(merged.min()), float(merged.max())))
PY

# ---------- Step 4: 分带整带重采样 + 海面残差二次清理 + 带内 min/max ----------
# 近景 30→5.859375 m 为 5.1× 上采样（bilinear，spike 约定）；远景 30→23.4375 m 为 1.28×
# 下采样（average，防混叠）。掩膜一律 nearest（保类不造值）。-tr 精确值 + 宽=整数倍 res
# 的 -te → 4097²/2561² 且分辨率严格无偏差（V5 断言）。
echo "[4] band resample + sea-residual cleanup + per-tier stats"
for TIER in near far; do
  if [ "$TIER" = near ]; then TE="$NEAR_TE_WIDE"; TRR="$NEAR_TR"; RES=bilinear; else TE="$FAR_TE_WIDE"; TRR="$FAR_TR"; RES=average; fi
  rm -f "$OUT/dem/${TIER}_band_f32.tif" "$OUT/dem/${TIER}_band_mask.tif"
  # shellcheck disable=SC2086  # $TE 需按空格拆成 4 个参数
  gdalwarp -q -overwrite "$OUT/dem/merged_bathy_30m.tif" -te $TE -tr "$TRR" "$TRR" -r $RES -ot Float32 "$OUT/dem/${TIER}_band_f32.tif"
  gdalwarp -q -overwrite "$OUT/dem/landmask_30m.tif"     -te $TE -tr "$TRR" "$TRR" -r near -ot Byte "$OUT/dem/${TIER}_band_mask.tif"
done
BAND_DIR="$OUT/dem" python3 <<'PY'
import os
import numpy as np
from osgeo import gdal
gdal.UseExceptions()
for tier in ('near', 'far'):
    p = os.path.join(os.environ['BAND_DIR'], f'{tier}_band_f32.tif')
    m = os.path.join(os.environ['BAND_DIR'], f'{tier}_band_mask.tif')
    # 注意保持 dataset 引用存活到读完（链式 gdal.Open().GetRasterBand().ReadAsArray()
    # 会让临时 dataset 被 GC、SWIG band 代理失效报 TypeError）
    mds = gdal.Open(m); ds = gdal.Open(p, gdal.GA_Update)
    v = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    mask = mds.GetRasterBand(1).ReadAsArray()
    # 二次清理（spike 已知残差渗入）：陆 max(v,0)、海 min(v,0)。重采样不会产生新极值，
    # 故带内 min/max 清理前后不变（清理只切号）；feather 主体在海上（负值）不受影响。
    v2 = np.where(mask == 1, np.maximum(v, 0.0), np.minimum(v, 0.0)).astype(np.float32)
    b = ds.GetRasterBand(1)
    b.WriteArray(v2); b.FlushCache(); b.ComputeStatistics(False)
    ds = None; mds = None
    tmin, tmax = float(v2.min()), float(v2.max())
    with open(os.path.join(os.environ['BAND_DIR'], f'{tier}_stats.txt'), 'w') as f:
        f.write("%.4f %.4f\n" % (tmin, tmax))
    print("  %s band: %dx%d px, land %.2f%%, elev min=%.3f max=%.3f m" %
          (tier, v2.shape[1], v2.shape[0], 100.0*mask.mean(), tmin, tmax))
PY
read -r NMIN NMAX < "$OUT/dem/near_stats.txt"
read -r FMIN FMAX < "$OUT/dem/far_stats.txt"
echo "[4] near scale [$NMIN,$NMAX]  far scale [$FMIN,$FMAX]（每带一对，带内共用）"

# ---------- Step 5: DEM 切 tile（-srcwin，共享 1 px 边）→ u16 GTiff + ENVI RAW ----------
# 行序：row 0 = 最北（srcwin yoff=row*step 自带北起行序）；ENVI=小端（byte order=0）。
echo "[5] DEM tiles: near 2x2 @2049, far 5x5 @513 (u16 tif + envi raw)"
tile_dem() {  # $1=tier $2=grid $3=px $4=step $5=min $6=max
  local TIER=$1 GRID=$2 PX=$3 STEP=$4 TMIN=$5 TMAX=$6 R C XOFF YOFF NAME
  for ((R=0; R<GRID; R++)); do
    for ((C=0; C<GRID; C++)); do
      XOFF=$((C*STEP)); YOFF=$((R*STEP))
      NAME="${TIER}_r${R}c${C}_${PX}"
      rm -f "$OUT/tiles/${NAME}.tif" "$OUT/tiles/${NAME}.raw" "$OUT/tiles/${NAME}.hdr"
      gdal_translate -q -ot UInt16 -scale "$TMIN" "$TMAX" 0 65535 \
        -srcwin "$XOFF" "$YOFF" "$PX" "$PX" \
        "$OUT/dem/${TIER}_band_f32.tif" "$OUT/tiles/${NAME}.tif"
      gdal_translate -q -of ENVI "$OUT/tiles/${NAME}.tif" "$OUT/tiles/${NAME}.raw"
    done
  done
}
tile_dem near "$NEAR_GRID" "$NEAR_PX" "$NEAR_STEP" "$NMIN" "$NMAX"
tile_dem far  "$FAR_GRID"  "$FAR_PX"  "$FAR_STEP"  "$FMIN" "$FMAX"
echo "[5] dem tiles done: $(ls "$OUT"/tiles/near_*.tif | wc -l | tr -d ' ') near + $(ls "$OUT"/tiles/far_*.tif | wc -l | tr -d ' ') far"

# ---------- Step 6: S2 底图（UG 单景；边界余量断言 + tile JPG） ----------
echo "[6] S2 coverage assert + basemap tiles"
SRC_S2="$SRC_S2" FAR_XMIN="$FAR_XMIN" FAR_YMIN="$FAR_YMIN" FAR_XMAX="$FAR_XMAX" FAR_YMAX="$FAR_YMAX" \
CX="$CX" CY="$CY" python3 <<'PY'
import os
from osgeo import gdal
gdal.UseExceptions()
ds = gdal.Open(os.environ['SRC_S2'])
assert ds.GetSpatialRef().GetAuthorityCode(None) == '32648', "S2 景 CRS 非 32648"
gt = ds.GetGeoTransform(); sx, sy = ds.RasterXSize, ds.RasterYSize
cov = (gt[0], gt[3] + sy*gt[5], gt[0] + sx*gt[1], gt[3])          # xmin,ymin,xmax,ymax
win = tuple(float(os.environ[k]) for k in ('FAR_XMIN','FAR_YMIN','FAR_XMAX','FAR_YMAX'))
m = (win[0]-cov[0], cov[2]-win[2], win[1]-cov[1], cov[3]-win[3])  # L,R,B,T 余量 m
print("  S2 coverage=%s far-window=%s margin L/R/B/T=%d/%d/%d/%d m" %
      (tuple(round(v,1) for v in cov), tuple(round(v,1) for v in win), *[round(v) for v in m]))
assert min(m) >= 10000, "60km 窗在 UG 景内边界余量 <10 km: %s" % (m,)
print("  margin>=10000 m OK")
PY

s2_tile() {  # $1=tier $2=grid $3=px $4=bmp_px $5=resample $6=band_half_m
  local TIER=$1 GRID=$2 PX=$3 BMP=$4 RES=$5 HALF=$6 R C XMIN YMAX XMAX YMIN NAME
  for ((R=0; R<GRID; R++)); do
    for ((C=0; C<GRID; C++)); do
      NAME="${TIER}_r${R}c${C}_${PX}"
      XMIN="$(awk -v cx="$CX" -v half="$HALF" -v c="$C" 'BEGIN{printf "%.3f", cx-half+c*12000}')"
      YMAX="$(awk -v cy="$CY" -v half="$HALF" -v r="$R" 'BEGIN{printf "%.3f", cy+half-r*12000}')"
      XMAX="$(awk -v xmin="$XMIN" 'BEGIN{printf "%.3f", xmin+12000}')"
      YMIN="$(awk -v ymax="$YMAX" 'BEGIN{printf "%.3f", ymax-12000}')"
      rm -f "$OUT/work/${NAME}_s2.tif" "$OUT/basemap/${NAME}.jpg" "$OUT/basemap/${NAME}.wld"
      # 近景 10→5.86 m 上采样 bilinear（保色不过冲）；远景 10→23.4 m 下采样 average（防混叠）
      # JPG 覆盖 tile 逻辑域（12 km，2048|512 px×res），与 DEM tile 采样格原点对齐（V6 断言）
      gdalwarp -q -overwrite "$SRC_S2" -te "$XMIN" "$YMIN" "$XMAX" "$YMAX" -ts "$BMP" "$BMP" \
        -r "$RES" -ot Byte "$OUT/work/${NAME}_s2.tif"
      gdal_translate -q -of JPEG -co QUALITY="$S2_QUALITY" -co WORLDFILE=YES \
        "$OUT/work/${NAME}_s2.tif" "$OUT/basemap/${NAME}.jpg"
      rm -f "$OUT/work/${NAME}_s2.tif"
    done
  done
}
s2_tile near "$NEAR_GRID" "$NEAR_PX" "$NEAR_BMP_PX" bilinear 12000
s2_tile far  "$FAR_GRID"  "$FAR_PX"  "$FAR_BMP_PX"  average  30000
echo "[6] basemap tiles done: $(ls "$OUT"/basemap/near_*.jpg | wc -l | tr -d ' ') near + $(ls "$OUT"/basemap/far_*.jpg | wc -l | tr -d ' ') far"

# S2 近景整带 @4097²（与 DEM 带同 -te/-tr → 网格逐像元对齐；VERIFY 陆/海色抽查 + 判据图叠加共用；work/ 用毕删）
# shellcheck disable=SC2086
gdalwarp -q -overwrite "$SRC_S2" -te $NEAR_TE_WIDE -tr "$NEAR_TR" "$NEAR_TR" -r bilinear -ot Byte "$OUT/work/s2_near_band.tif"

# ---------- Step 7: manifest.json（Unity 段直接消费；字段名即契约，见 docs notes.md） ----------
echo "[7] manifest -> $OUT/manifest.json"
OUT="$OUT" CX="$CX" CY="$CY" \
NEAR_XMIN="$NEAR_XMIN" NEAR_YMIN="$NEAR_YMIN" NEAR_XMAX="$NEAR_XMAX" NEAR_YMAX="$NEAR_YMAX" \
FAR_XMIN="$FAR_XMIN" FAR_YMIN="$FAR_YMIN" FAR_XMAX="$FAR_XMAX" FAR_YMAX="$FAR_YMAX" \
NMIN="$NMIN" NMAX="$NMAX" FMIN="$FMIN" FMAX="$FMAX" FEATHER_M="$FEATHER_M" \
python3 <<'PY'
import json, os, subprocess

def tiles(tier, grid, px, xmin, ymax):
    out = []
    for r in range(grid):
        for c in range(grid):
            name = f"{tier}_r{r}c{c}_{px}"
            x0 = xmin + c*12000.0; y1 = ymax - r*12000.0
            out.append({
                "name": name,
                "utm_bounds": [round(x0, 2), round(y1-12000.0, 2), round(x0+12000.0, 2), round(y1, 2)],  # [xmin,ymin,xmax,ymax]
                "path_raw": f"tiles/{name}.raw",     # ENVI 裸 u16，小端/北上行序，同目录 .hdr
                "path_jpg": f"basemap/{name}.jpg",   # S2 sRGB 底图，同目录 .wld worldfile
            })
    return out

man = {
    "epsg": 32648,
    "center_lonlat": [103.80, 1.28],
    "center_utm": [float(os.environ['CX']), float(os.environ['CY'])],   # Unity 世界原点（浮点原点约定）
    "feather_m": int(os.environ['FEATHER_M']),
    "near": {
        "extent_utm": [float(os.environ['NEAR_XMIN']), float(os.environ['NEAR_YMIN']),
                       float(os.environ['NEAR_XMAX']), float(os.environ['NEAR_YMAX'])],
        "tile_px": 2049, "tile_size_m": 12000, "grid": [2, 2], "m_per_px": 5.859375,
        "basemap_px": 2048,
        "elev_min": float(os.environ['NMIN']), "elev_max": float(os.environ['NMAX']),
        "tiles": tiles('near', 2, 2049, float(os.environ['NEAR_XMIN']), float(os.environ['NEAR_YMAX'])),
    },
    "far": {
        "extent_utm": [float(os.environ['FAR_XMIN']), float(os.environ['FAR_YMIN']),
                       float(os.environ['FAR_XMAX']), float(os.environ['FAR_YMAX'])],
        "tile_px": 513, "tile_size_m": 12000, "grid": [5, 5], "m_per_px": 23.4375,
        "basemap_px": 512,
        "elev_min": float(os.environ['FMIN']), "elev_max": float(os.environ['FMAX']),
        "tiles": tiles('far', 5, 513, float(os.environ['FAR_XMIN']), float(os.environ['FAR_YMAX'])),
    },
    "s2": {
        "scene": "S2B_48NUG_20260320_0_L2A",
        "date": "2026-03-20",
        "res_m": 10,
        "srgb": True,
        "source": "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/48/N/UG/2026/3/S2B_48NUG_20260320_0_L2A/TCI.tif",
        "note": "仅用 UG 单景（60km 窗余量>=10km 已断言）；VG 两景（48NVG 2026-03-20 云12.5%、2026-04-23 云8.2%）云量高不入管线，留作将来补丁/扩展",
    },
    "generated_by": "tools/terrain/m6_pipeline.sh (GDAL 3.13.0) @ commit 见 git log; 2026-09-29",
}
with open(os.path.join(os.environ['OUT'], 'manifest.json'), 'w') as f:
    json.dump(man, f, indent=2, ensure_ascii=False)
    f.write('\n')
print("  manifest.json: near=%d far=%d tiles" % (len(man['near']['tiles']), len(man['far']['tiles'])))
PY

# ---------- Step 8: 判据图（入库 docs/…/，每张 ≤1400 px） ----------
echo "[8] preview PNGs -> $DOCS/"
# 色表（含水深负值档）：深海蓝 → 浅海青 → 滩沙 → 植被绿 → 山地棕 → 白
cat > "$OUT/work/colormap.txt" <<'EOF'
-200   6 24 54
-100   9 36 72
-50   14 58 102
-20   22 92 140
-5    52 132 176
0    150 200 220
0.5  194 178 128
2    110 158  78
40    78 132  60
120  140 128  72
165  168 158 142
250  200 196 190
500  255 255 255
EOF
gdal_translate -q -outsize 1400 0 -r average "$OUT/dem/near_band_f32.tif" "$OUT/work/near_prev.tif"
gdal_translate -q -outsize 1400 0 -r average "$OUT/dem/far_band_f32.tif"  "$OUT/work/far_prev.tif"
gdal_translate -q -outsize 1400 1400 -r average "$OUT/work/s2_near_band.tif" "$OUT/work/s2_near_prev.tif"

rm -f "$DOCS"/*.png
gdaldem hillshade -z 3 -compute_edges "$OUT/work/near_prev.tif" "$DOCS/01_near_hillshade.png"
gdaldem color-relief "$OUT/work/far_prev.tif" "$OUT/work/colormap.txt" "$DOCS/03_far_color_relief.png"

# 02：近景 S2×hillshade 叠加（同 1400² 格网；暗部压暗提立体感，色彩不失真偏移）
WORK="$OUT/work" DOCS="$DOCS" python3 <<'PY'
import os
import numpy as np
from osgeo import gdal
from PIL import Image
gdal.UseExceptions()
gdalwarp_hs = gdal.Open(os.path.join(os.environ['WORK'], 'near_prev.tif'))
hs_ds = gdal.DEMProcessing(os.path.join(os.environ['WORK'], 'near_hs.tif'), gdalwarp_hs, 'hillshade', zFactor=3, computeEdges=True)  # 直接返回 Dataset
hs = hs_ds.GetRasterBand(1).ReadAsArray().astype(np.float32) / 255.0
s2 = gdal.Open(os.path.join(os.environ['WORK'], 's2_near_prev.tif'))
rgb = np.dstack([s2.GetRasterBand(i).ReadAsArray() for i in (1, 2, 3)]).astype(np.float32)
comp = np.clip(rgb * (0.45 + 0.55 * hs[..., None]), 0, 255).astype(np.uint8)     # 0.45 保底不压黑
Image.fromarray(comp).save(os.path.join(os.environ['DOCS'], '02_near_s2_hillshade_overlay.png'))
PY

# 04：陆海合并 feather 带剖面（y=center 行，x=center±15 km；GLO/GEBCO/merged 三线对比）
DEMDIR="$OUT/dem" DOCS="$DOCS" CX="$CX" CY="$CY" TR_M="$TR_M" python3 <<'PY'
import os
import numpy as np
from osgeo import gdal
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
gdal.UseExceptions()
cx, cy, tr = float(os.environ['CX']), float(os.environ['CY']), float(os.environ['TR_M'])
ds = gdal.Open(os.path.join(os.environ['DEMDIR'], 'glo_30m.tif')); gt = ds.GetGeoTransform()
row = int(round((gt[3] - cy) / (-gt[5])))
def line(path):
    bds = gdal.Open(path)                       # 引用保活（链式调用会 GC 失效，见 Step4 注）
    return bds.GetRasterBand(1).ReadAsArray().astype(np.float32)[row, :]
x0 = int(round((cx - 15000 - gt[0]) / gt[1])); x1 = int(round((cx + 15000 - gt[0]) / gt[1]))
sl = slice(x0, x1 + 1)
glo = line(os.path.join(os.environ['DEMDIR'], 'glo_30m.tif'))[sl]
geb = np.nan_to_num(line(os.path.join(os.environ['DEMDIR'], 'gebco_30m.tif'))[sl], nan=0.0)
mer = line(os.path.join(os.environ['DEMDIR'], 'merged_bathy_30m.tif'))[sl]
msk = line(os.path.join(os.environ['DEMDIR'], 'landmask_30m.tif'))[sl]
km = (np.arange(len(glo)) + x0) * tr / 1000.0 + gt[0] / 1000.0
fig, ax = plt.subplots(figsize=(14, 5), dpi=100)
ax.plot(km, geb, lw=1.0, alpha=0.8, label='GEBCO (warped 30m)')
ax.plot(km, glo, lw=1.0, alpha=0.8, label='GLO-30 (30m)')
ax.plot(km, mer, lw=2.2, color='k', label='merged (2km feather)')
ax.axhline(0, color='b', ls=':', lw=0.8)
inland = False; start = 0
for i in range(len(msk) + 1):     # 陆段底色条带（GLO 生效区）
    v = msk[i] if i < len(msk) else 0
    if v and not inland: inland, start = True, i
    elif not v and inland:
        inland = False
        if i - start > 2: ax.axvspan(km[start], km[i-1], color='tan', alpha=0.25)
ax.set_xlabel('UTM48N E (km)'); ax.set_ylabel('elevation (m)')
ax.set_title('land/sea merge feather profile @ y=center (%.3f m N, row %d) — tan = land (GLO)' % (cy, row))
ax.legend(loc='lower right'); fig.tight_layout()
fig.savefig(os.path.join(os.environ['DOCS'], '04_feather_profile.png'))
print("  profile row=%d land px in span=%d" % (row, int(msk.sum())))
PY
rm -f "$DOCS"/*.png.aux.xml "$OUT/work"/*.png.aux.xml
DOCS="$DOCS" python3 -c "
import os
from PIL import Image
for f in sorted(os.listdir(os.environ['DOCS'])):
    if f.endswith('.png'):
        w, h = Image.open(os.path.join(os.environ['DOCS'], f)).size
        assert max(w, h) <= 1400, f'{f} {w}x{h} >1400px'
        print('  %s %dx%d OK' % (f, w, h))
"

# =============================================================================
# VERIFY（任一断言失败 → 非零退出）
# =============================================================================
echo "===== VERIFY ====="
fail() { echo "VERIFY-FAIL: $*"; exit 1; }

echo "-- [V1] tile 计数（RAW/HDR/u16-TIF/JPG × near/far）："
for TIER in near far; do
  if [ "$TIER" = near ]; then WANT=4; PX=2049; else WANT=25; PX=513; fi
  for KIND in raw hdr tif jpg; do
    if [ "$KIND" = jpg ]; then SUB=basemap; else SUB=tiles; fi
    N=$(ls "$OUT/$SUB"/${TIER}_*_${PX}.${KIND} 2>/dev/null | wc -l | tr -d ' ')
    [ "$N" -eq "$WANT" ] || fail "$TIER $KIND count=$N != $WANT"
    printf "   %-5s %-4s = %d OK\n" "$TIER" "$KIND" "$N"
  done
done
JPG_WLD=$(ls "$OUT"/basemap/*.wld 2>/dev/null | wc -l | tr -d ' ')
[ "$JPG_WLD" -eq 29 ] || fail "wld count=$JPG_WLD != 29"; echo "   basemap .wld = $JPG_WLD OK"

echo "-- [V2] RAW ↔ GTiff checksum 相等（逐 tile，29 对）："
BAD=0
for T in "$OUT"/tiles/*.tif; do
  C1=$(gdalinfo -checksum "$T" | grep -o 'Checksum=[0-9]*')
  C2=$(gdalinfo -checksum "${T%.tif}.raw" | grep -o 'Checksum=[0-9]*')
  if [ "$C1" != "$C2" ]; then echo "   MISMATCH $(basename "$T"): $C1 vs $C2"; BAD=1; fi
done
[ "$BAD" -eq 0 ] || fail "RAW/GTiff checksum 有Mismatch"
echo "   29/29 checksum 一致 OK"

echo "-- [V3] RAW 字节序 = 小端（.hdr 声明 + 数据字节探针）："
for TIER in near far; do
  if [ "$TIER" = near ]; then H="$OUT/tiles/near_r0c0_2049.hdr"; T="$OUT/tiles/near_r0c0_2049.tif"; R="$OUT/tiles/near_r0c0_2049.raw"
  else H="$OUT/tiles/far_r0c0_513.hdr"; T="$OUT/tiles/far_r0c0_513.tif"; R="$OUT/tiles/far_r0c0_513.raw"; fi
  grep -i "^byte order *= *0" "$H" >/dev/null || fail "$TIER .hdr byte order != 0（小端）"
  V=$(gdallocationinfo "$T" 0 0 | awk -F: '/Value:/ {gsub(/ /,"",$2); print $2}')
  HEX2=$(xxd -p -l 2 "$R")
  REV="${HEX2:2:2}${HEX2:0:2}"
  [ "$((16#$REV))" -eq "$V" ] || fail "$TIER 探针非小端 (value=$V bytes=$HEX2)"
  echo "   $TIER: hdr byte order=0, pixel(0,0)=$V ↔ bytes $HEX2 → LITTLE-endian OK"
done

echo "-- [V4] 相邻 tile 共享边 checksum 相等（缝隙零差异）："
TILES_DIR="$OUT/tiles" python3 <<'PY'
import os
from osgeo import gdal
gdal.UseExceptions()
def strip_ck(path, xoff, yoff, xsize, ysize):
    # /vsimem 仅进程内有效 → 提条带+checksum 全在一个 python 进程里做
    ds = gdal.Translate('/vsimem/s.tif', path, srcWin=[xoff, yoff, xsize, ysize])
    ck = ds.GetRasterBand(1).Checksum()
    ds = None; gdal.Unlink('/vsimem/s.tif')
    return ck
n = bad = 0
for tier, g, p, s in (('near', 2, 2049, 2048), ('far', 5, 513, 512)):
    for r in range(g):
        for c in range(g):
            t = os.path.join(os.environ['TILES_DIR'], f'{tier}_r{r}c{c}_{p}.tif')
            if c + 1 < g:   # 纵缝：左 tile 末列 vs 右 tile 首列（tile 内坐标，整列高）
                tr = os.path.join(os.environ['TILES_DIR'], f'{tier}_r{r}c{c+1}_{p}.tif')
                a = strip_ck(t, p-1, 0, 1, p); b = strip_ck(tr, 0, 0, 1, p)
                if a != b: print(f"   V-SEAM MISMATCH {tier} r{r} c{c}|c{c+1}: {a} vs {b}"); bad += 1
                n += 1
            if r + 1 < g:   # 横缝：上 tile 末行 vs 下 tile 首行（tile 内坐标，整行宽）
                tb = os.path.join(os.environ['TILES_DIR'], f'{tier}_r{r+1}c{c}_{p}.tif')
                a = strip_ck(t, 0, p-1, p, 1); b = strip_ck(tb, 0, 0, p, 1)
                if a != b: print(f"   H-SEAM MISMATCH {tier} r{r}|r{r+1} c{c}: {a} vs {b}"); bad += 1
                n += 1
assert bad == 0, f"{bad} 条共享边 checksum 不等"
print(f"   {n} 条共享边（near 4 + far 40）checksum 全等 OK")
PY

echo "-- [V5] gdalinfo 规格（尺寸/EPSG/分辨率，29 tile + 2 band）："
TILES_DIR="$OUT/tiles" DEM_DIR="$OUT/dem" NEAR_TR="$NEAR_TR" FAR_TR="$FAR_TR" python3 <<'PY'
import glob, os
from osgeo import gdal
gdal.UseExceptions()
def chk(path, px, tr):
    ds = gdal.Open(path); gt = ds.GetGeoTransform()
    assert (ds.RasterXSize, ds.RasterYSize) == (px, px), f"{path} size {ds.RasterXSize}x{ds.RasterYSize}"
    assert ds.GetSpatialRef().GetAuthorityCode(None) == '32648', f"{path} CRS"
    assert abs(gt[1] - tr) < 1e-9 and abs(gt[5] + tr) < 1e-9, f"{path} res {gt[1]},{gt[5]}"
    return gt
n = 0
for f in sorted(glob.glob(os.path.join(os.environ['TILES_DIR'], '*.tif'))):
    px, tr = (2049, float(os.environ['NEAR_TR'])) if '_2049' in f else (513, float(os.environ['FAR_TR']))
    chk(f, px, tr); n += 1
chk(os.path.join(os.environ['DEM_DIR'], 'near_band_f32.tif'), 4097, float(os.environ['NEAR_TR']))
chk(os.path.join(os.environ['DEM_DIR'], 'far_band_f32.tif'), 2561, float(os.environ['FAR_TR']))
print(f"   {n} tiles + 2 band: size/EPSG:32648/res OK (near {os.environ['NEAR_TR']} / far {os.environ['FAR_TR']} m/px)")
PY

echo "-- [V6] S2/DEM 同 tile 范围一致（jpg geotransform/wld ↔ dem tif gt）："
BASEMAP="$OUT/basemap" TILES_DIR="$OUT/tiles" python3 <<'PY'
import glob, os
from osgeo import gdal
gdal.UseExceptions()
n = 0
for t in sorted(glob.glob(os.path.join(os.environ['TILES_DIR'], '*.tif'))):
    name = os.path.basename(t)[:-4]
    jpg = os.path.join(os.environ['BASEMAP'], name + '.jpg')
    gt_j = gdal.Open(jpg).GetGeoTransform()          # .wld 自动读取（GDAL，非 PAM）
    assert gt_j[0] != 0.0 or gt_j[3] != 0.0, f"{jpg} 无 geotransform（wld 未生效）"
    gt_d = gdal.Open(t).GetGeoTransform()
    ds_j = gdal.Open(jpg)
    # 逻辑域比较（采样格约定，见脚本头）：DEM tile 逻辑域 = 前 2048|512 格 = 12 km；
    # JPG 2048|512 px × 同 res 恰好覆盖同一 12 km 逻辑域 → 原点/Extent/分辨率三者全等
    assert abs(gt_j[0] - gt_d[0]) < 1e-4 and abs(gt_j[3] - gt_d[3]) < 1e-4, f"{name} origin {gt_j} vs {gt_d}"
    ex_j = (gt_j[0] + ds_j.RasterXSize*gt_j[1], gt_j[3] + ds_j.RasterYSize*gt_j[5])
    dem_grid_n = 2048 if '_2049' in name else 512
    ex_d = (gt_d[0] + dem_grid_n*gt_d[1], gt_d[3] + dem_grid_n*gt_d[5])
    assert abs(ex_j[0] - ex_d[0]) < 1e-4 and abs(ex_j[1] - ex_d[1]) < 1e-4, f"{name} extent {ex_j} vs {ex_d}"
    assert abs(gt_j[1] - gt_d[1]) < 1e-9, f"{name} res {gt_j[1]} vs {gt_d[1]}"
    n += 1
print(f"   {n}/29 tile: S2 jpg 与 DEM 逻辑域（原点/12km Extent/分辨率）一致（tol 1e-4 m）OK")
PY

echo "-- [V7] manifest.json 可解析 + tile 数 + 契约字段："
OUT="$OUT" python3 <<'PY'
import json, os
m = json.load(open(os.path.join(os.environ['OUT'], 'manifest.json')))
assert m['epsg'] == 32648 and m['center_lonlat'] == [103.80, 1.28]
for tier, cnt, px in (('near', 4, 2049), ('far', 25, 513)):
    b = m[tier]
    assert len(b['tiles']) == cnt, f"{tier} tiles {len(b['tiles'])} != {cnt}"
    assert b['tile_px'] == px
    for k in ('extent_utm', 'tile_size_m', 'grid', 'm_per_px', 'elev_min', 'elev_max'):
        assert k in b, f"{tier}.{k} missing"
    for t in b['tiles']:
        for k in ('name', 'utm_bounds', 'path_raw', 'path_jpg'):
            assert k in t and t[k], f"{tier} tile missing {k}"
        assert os.path.exists(os.path.join(os.environ['OUT'], t['path_raw']))
        assert os.path.exists(os.path.join(os.environ['OUT'], t['path_jpg']))
for k in ('scene', 'date', 'res_m', 'srgb', 'source'):
    assert k in m['s2'], f"s2.{k} missing"
print("   manifest OK: near=%d far=%d, near elev [%.3f, %.3f], far elev [%.3f, %.3f]" % (
    len(m['near']['tiles']), len(m['far']['tiles']),
    m['near']['elev_min'], m['near']['elev_max'], m['far']['elev_min'], m['far']['elev_max']))
PY

echo "-- [V8] S2 底图数值抽查（陆绿/棕 vs 海深蓝；近景带陆面云斑占比）："
WORK="$OUT/work" DEM_DIR="$OUT/dem" python3 <<'PY'
import os
import numpy as np
from osgeo import gdal
gdal.UseExceptions()
s2 = gdal.Open(os.path.join(os.environ['WORK'], 's2_near_band.tif'))
rgb = np.dstack([s2.GetRasterBand(i).ReadAsArray() for i in (1, 2, 3)]).astype(np.float32)
mask_ds = gdal.Open(os.path.join(os.environ['DEM_DIR'], 'near_band_mask.tif'))   # 引用保活（链式 GC 坑）
dem_ds = gdal.Open(os.path.join(os.environ['DEM_DIR'], 'near_band_f32.tif'))
mask = mask_ds.GetRasterBand(1).ReadAsArray()
dem = dem_ds.GetRasterBand(1).ReadAsArray()
land = mask == 1
sea_deep = (mask == 0) & (dem < -20)
if sea_deep.sum() < 1000: sea_deep = (mask == 0) & (dem < -10)   # 深水样本不足时放宽阈值
lm, sm = rgb[land].mean(axis=0), rgb[sea_deep].mean(axis=0)
print("   land  px=%7d  mean RGB = %.0f/%.0f/%.0f" % (land.sum(), *lm))
print("   sea   px=%7d  mean RGB = %.0f/%.0f/%.0f (deep, %s)" % (sea_deep.sum(), *sm, '<-20m' if (dem < -20).any() else '<-10m'))
assert sm[2] > sm[0], "海面均值非蓝占优: %s" % sm          # 深海须蓝>红
assert not (lm[2] > lm[0] and lm[2] > lm[1]), "陆面均值蓝占优（异常）: %s" % lm  # 陆不蓝占优
bright = (rgb.min(axis=2) >= 180) & ((rgb.max(axis=2) - rgb.min(axis=2)) <= 30)
frac = float(bright[land].mean())
print("   云斑判据（陆面 高亮低饱和 px 占比）= %.3f%%  %s" % (frac*100, "[WARN]>3%" if frac > 0.03 else "OK"))
PY

rm -rf "$OUT/work"
echo "===== ALL VERIFY PASSED ====="
