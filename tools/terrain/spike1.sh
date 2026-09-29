#!/usr/bin/env bash
# =============================================================================
# M6 地形 spike —— 新加坡海峡 DEM 管线（Copernicus GLO-30, AWS 公开镜像）
#
# 目的（数据侧判据）：
#   1. 证明免费数据能做出"岛屿有起伏"的海峡地形；
#   2. 产出近景窗 2049² vs 513² 双分辨率 16-bit RAW，供分块口径（C2）裁决。
#
# 可重跑：脚本幂等（tile 已存在且可读则跳过下载，其余产物覆盖重生成）。
# 大文件纪律：tile/.tif/.raw 全部落 tmp/m6-spike-data/（仓库约定不入库），
#             入库产物仅：脚本本身 + docs/research/2026-09-29-m6-terrain-spike/ 判据 PNG。
#
# 勘误记录（EPSG）：调研 dive_04（docs/research/2026-09-24-scene-ship-fidelity/
#   dive_04.md:12 与 00-REPORT.md:84）写 "UTM 48N（EPSG:32748）"——32748 实为
#   UTM 48S（南半球）。新加坡主体在北纬，正确代号 = EPSG:32648（UTM 48N，中央
#   经线 105E）。本脚本用 32648，规格见 gdalinfo 输出。
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/../.."   # 一律从仓库根执行

# ---------- 变量（顶部集中，便于调窗） ----------
TILE_IDS="N01_00_E103_00 N01_00_E104_00 N00_00_E103_00 N00_00_E104_00 S01_00_E103_00 S01_00_E104_00"
S3_BASE="https://copernicus-dem-30m.s3.amazonaws.com"

# 全域裁剪窗（经纬度）：103.40–104.40E, 1.45S–1.45N —— 覆盖新加坡+海峡岛屿+巴淡/宾坦
WIN_LON_MIN=103.40; WIN_LAT_MIN=-1.45; WIN_LON_MAX=104.40; WIN_LAT_MAX=1.45

# 投影：EPSG:32648（UTM 48N；勘误见文件头）
TARGET_EPSG=EPSG:32648
TR_M=30            # 输出格网 30 m ≈ GLO-30 原生分辨率（0.000277…° ≈ 30.8 m 赤道）

# 近景窗（主岛航道）：中心 (103.80E, 1.28N) = 新加坡南岸+海峡岛屿，12×12 km
NEAR_LON=103.80; NEAR_LAT=1.28; NEAR_SIZE_M=12000

# 分块口径（C2 裁决材料）
SIZE_A=2049        # 2^11+1，Unity 高度图合法尺寸；12000/2049 ≈ 5.86 m/格
SIZE_B=513         # 2^9+1 同上；             12000/513  ≈ 23.4 m/格

OUT="tmp/m6-spike-data"
DOCS="docs/research/2026-09-29-m6-terrain-spike"

export GDAL_PAM_ENABLED=NO   # 不生成 .aux.xml，保持目录干净

mkdir -p "$OUT/tiles" "$DOCS"

# ---------- Step 1: 下载 6 个 GLO-30 tile（匿名 S3，已验 200） ----------
# 幂等：文件存在且 gdalinfo 可解析 → 跳过；否则 curl（-f 遇 4xx/5xx 报错，--retry 3 应对 S3 限流）。
for T in $TILE_IDS; do
  F="$OUT/tiles/${T}.tif"
  URL="$S3_BASE/Copernicus_DSM_COG_10_${T}_DEM/Copernicus_DSM_COG_10_${T}_DEM.tif"
  if [ -s "$F" ] && gdalinfo "$F" >/dev/null 2>&1; then
    echo "[1] skip (exists+valid): $F"
  else
    echo "[1] download: $URL"
    curl -fL --retry 3 --retry-delay 2 -o "$F" "$URL"
  fi
done

# ---------- Step 2: 合并 + 裁剪 + 重投影 → float32 GeoTIFF ----------
# -te 用经纬度给定（-te_srs EPSG:4326），由 gdalwarp 换算到目标 UTM；
# -tr 30 30 统一格网；默认 nearest 重采样（同量级分辨率近似 1:1 取值，不造值）。
echo "[2] gdalwarp merge -> $OUT/straits_merged.tif"
rm -f "$OUT/straits_merged.tif"
gdalwarp -overwrite \
  $OUT/tiles/*.tif \
  -te "$WIN_LON_MIN" "$WIN_LAT_MIN" "$WIN_LON_MAX" "$WIN_LAT_MAX" -te_srs EPSG:4326 \
  -t_srs "$TARGET_EPSG" -tr $TR_M $TR_M -ot Float32 \
  "$OUT/straits_merged.tif"
echo "[2] straits_merged.tif 规格（尺寸/分辨率/范围/统计）："
gdalinfo -json -stats "$OUT/straits_merged.tif" | python3 -c '
import json,sys
d=json.load(sys.stdin); b=d["bands"][0]; gt=d["geoTransform"]; g=d["size"]
mn=b.get("minimum"); mx=b.get("maximum")
print("  size=%dx%dpx  res_x=%.4fm res_y=%.4fm" % (g[0],g[1],gt[1],abs(gt[5])))
if "wgs84Extent" in d:
    ring=d["wgs84Extent"]["coordinates"][0]
    lons=[p[0] for p in ring]; lats=[p[1] for p in ring]
    print("  bbox_wgs84: lon %.4f..%.4f  lat %.4f..%.4f" % (min(lons),max(lons),min(lats),max(lats)))
print("  min=%s max=%s (m)" % (mn,mx))'

# ---------- Step 3: 海面处理（spike 边界，记录在案） ----------
# GLO-30 海面 ≈0 带插值噪声（残差可到数米）；本 spike 把 <0.5 m 钳到 0 → 平坦海面。
# bathymetry（真实水深）留 GEBCO 正式批处理——本步仅为 spike 观感边界，不进 M6 正式口径。
# 注意用 where()：A*(A>=0.5) 在 A=NaN 时 NaN*0=NaN 会把海面 NaN 保留下来；where 则可靠置 0。
echo "[3] clamp <0.5m -> 0 （海面钳平）"
gdal_calc.py -A "$OUT/straits_merged.tif" \
  --outfile="$OUT/straits_clamped.tif" --overwrite \
  --calc="where(A>=0.5, A, 0.0)" --quiet
gdal_edit.py -unsetnodata "$OUT/straits_clamped.tif"   # 统计/色带须包含海面 0 值
echo "[3] straits_clamped.tif:"
gdalinfo "$OUT/straits_clamped.tif" | grep -E "Size is|Pixel Size|Origin" | sed 's/^/   /'

# ---------- Step 4: 近景窗裁切（12×12 km，UTM 坐标精确盒） ----------
# 中心经纬度 → UTM（gdaltransform），±6000 m 取盒 → 30 m 原生约 400×400 px。
read CX CY <<<"$(echo "$NEAR_LON $NEAR_LAT" | gdaltransform -s_srs EPSG:4326 -t_srs "$TARGET_EPSG" | awk '{print $1, $2}')"
NEAR_TE="$(awk -v cx="$CX" -v cy="$CY" -v h=$((NEAR_SIZE_M/2)) 'BEGIN{printf "%.1f %.1f %.1f %.1f", cx-h, cy-h, cx+h, cy+h}')"
echo "[4] near window center ($NEAR_LON,$NEAR_LAT) -> UTM ($CX,$CY); -te $NEAR_TE"
rm -f "$OUT/near_window_f32.tif"
gdalwarp -overwrite "$OUT/straits_clamped.tif" -te $NEAR_TE \
  -tr $TR_M $TR_M -ot Float32 "$OUT/near_window_f32.tif"

# 全窗 min/max（归一基准，两档分辨率共用同一对 scale 参数 → 灰度可比）
read NMIN NMAX <<<"$(gdalinfo -json -stats "$OUT/near_window_f32.tif" | python3 -c '
import json,sys; b=json.load(sys.stdin)["bands"][0]; print(b["minimum"], b["maximum"])')"
echo "[4] near window native: $(gdalinfo "$OUT/near_window_f32.tif" | grep 'Size is')  min=$NMIN max=$NMAX"

# ---------- Step 5: 双分辨率分块导出（C2 材料） ----------
# 2049 档：bilinear 上采样（30 m 原生 → 5.86 m/格 = 5.1× 过采样，平滑插值非新增细节）
echo "[5] resample $SIZE_A (bilinear): 12000/$SIZE_A = $(awk -v s=$SIZE_A 'BEGIN{printf "%.2f", 12000/s}') m/px"
rm -f "$OUT/near_${SIZE_A}_f32.tif"
gdalwarp -overwrite "$OUT/near_window_f32.tif" -ts $SIZE_A $SIZE_A -r bilinear "$OUT/near_${SIZE_A}_f32.tif"
# 513 档：average 下采样（30 m 原生 → 23.4 m/格，接近原生密度）
echo "[5] resample $SIZE_B (average) : 12000/$SIZE_B = $(awk -v s=$SIZE_B 'BEGIN{printf "%.2f", 12000/s}') m/px"
rm -f "$OUT/near_${SIZE_B}_f32.tif"
gdalwarp -overwrite "$OUT/near_window_f32.tif" -ts $SIZE_B $SIZE_B -r average "$OUT/near_${SIZE_B}_f32.tif"

for S in $SIZE_A $SIZE_B; do
  # 16-bit 归一：全窗 [$NMIN,$NMAX] -> [0,65535]，两档共用同一 scale（脚本/notes 均记录）
  rm -f "$OUT/near_${S}_u16.tif" "$OUT/near_${S}.raw" "$OUT/near_${S}.hdr"
  gdal_translate -ot UInt16 -scale "$NMIN" "$NMAX" 0 65535 \
    "$OUT/near_${S}_f32.tif" "$OUT/near_${S}_u16.tif"
  # RAW 副本（ENVI 裸二进制 + .hdr 头；字节序以 Step 7 实测为准）
  gdal_translate -of ENVI "$OUT/near_${S}_u16.tif" "$OUT/near_${S}.raw"
done

# ---------- Step 6: 判据 PNG（入库 docs/…/，hillshade + color-relief 各≥2 张） ----------
# 色表：海蓝-低地绿-山地棕（简易 cpt，脚本内生成 → tmp，不入库）
cat > "$OUT/colormap.txt" <<'EOF'
0    18  60 105
0.4  30  90 140
1    70 130 175
3   140 190 210
6   200 215 220
8   194 178 128
15  110 158  78
40   78 132  60
80  140 128  72
120 150 128  92
165 168 158 142
250 200 196 190
500 255 255 255
EOF

# 全域预览：降采样 1200 px 宽（PNG 体积红线）；-z 2 垂直夸张（海峡地形起伏温和）
# 注意 color-relief 参数序：gdaldem color-relief <dem> <色表> <输出>（首跑曾写反报
# "Could not identify driver for output colormap.txt"，此处已修正）
gdal_translate -outsize 1200 0 -r average "$OUT/straits_clamped.tif" "$OUT/full_preview.tif"
gdaldem hillshade    -z 2 "$OUT/full_preview.tif" "$DOCS/01_full_hillshade.png"     -compute_edges
gdaldem color-relief       "$OUT/full_preview.tif"    "$OUT/colormap.txt" "$DOCS/02_full_color_relief.png"
# 近景窗预览（2049 f32 源；-z 3 夸张突显岛屿起伏）
gdaldem hillshade    -z 3 "$OUT/near_${SIZE_A}_f32.tif" "$DOCS/03_near_hillshade.png" -compute_edges
gdaldem color-relief       "$OUT/near_${SIZE_A}_f32.tif" "$OUT/colormap.txt" "$DOCS/04_near_color_relief.png"
# 2049 vs 513 对比：统一画布 1024×1024、同 -z（2049 双线性降采样 / 513 nearest 放大保留格感）
gdal_translate -outsize 1024 1024 -r bilinear "$OUT/near_${SIZE_A}_f32.tif" "$OUT/cmp_${SIZE_A}.tif"
gdal_translate -outsize 1024 1024 -r near     "$OUT/near_${SIZE_B}_f32.tif" "$OUT/cmp_${SIZE_B}.tif"
gdaldem hillshade -z 3 "$OUT/cmp_${SIZE_A}.tif" "$DOCS/05_near2049_hillshade_1024px.png" -compute_edges
gdaldem hillshade -z 3 "$OUT/cmp_${SIZE_B}.tif" "$DOCS/06_near513_hillshade_1024px.png"  -compute_edges
rm -f "$DOCS"/*.png.aux.xml

# ---------- Step 7: 自验（幂等重跑后执行同样成立） ----------
echo "===== VERIFY ====="
echo "-- RAW 字节序实测（.hdr 声明 + 数据字节探针）："
grep -i "byte order" "$OUT/near_${SIZE_A}.hdr" | sed 's/^/   /' || true
V=$(gdallocationinfo "$OUT/near_${SIZE_A}_u16.tif" 0 0 | awk -F: '/Value:/ {gsub(/ /,"",$2); print $2}')
HEX2=$(xxd -p -l 2 "$OUT/near_${SIZE_A}.raw")
REV="${HEX2:2:2}${HEX2:0:2}"
if   [ "$((16#$HEX2))" -eq "$V" ]; then echo "   probe: pixel(0,0)=$V first_bytes=$HEX2 -> BIG-endian（大端）"
elif [ "$((16#$REV))"  -eq "$V" ]; then echo "   probe: pixel(0,0)=$V first_bytes=$HEX2 -> LITTLE-endian（小端）"
else echo "   probe: INCONCLUSIVE (value=$V bytes=$HEX2)"; fi

echo "-- u16 GTiff vs RAW 内容一致性（checksum 相等才算过）："
for S in $SIZE_A $SIZE_B; do
  C1=$(gdalinfo -checksum "$OUT/near_${S}_u16.tif" | grep -o "Checksum=[0-9]*")
  C2=$(gdalinfo -checksum "$OUT/near_${S}.raw"      | grep -o "Checksum=[0-9]*")
  if [ "$C1" = "$C2" ]; then echo "   near_${S}: $C1 == $C2 OK"; else echo "   near_${S}: MISMATCH $C1 vs $C2"; exit 1; fi
done

echo "-- RAW 文件大小："
for S in $SIZE_A $SIZE_B; do
  B=$(stat -f%z "$OUT/near_${S}.raw")
  echo "   near_${S}.raw = $B B ($(awk -v b="$B" 'BEGIN{printf "%.1f MiB",b/1048576}'))"
done

echo "-- 近景 u16 规格（gdalinfo）："
for S in $SIZE_A $SIZE_B; do
  gdalinfo "$OUT/near_${S}_u16.tif" | grep -E "Size is|Pixel Size|Origin" | sed "s/^/   [${S}] /"
done

echo "-- px/m 表（C2 裁决材料）："
awk -v a=$SIZE_A -v b=$SIZE_B 'BEGIN{
  printf "   %-6s %-9s %-9s %-16s %s\n","tile","px","m/px","RAW 字节","R16 显存(估)";
  printf "   %-6s %-9s %-9.2f %-16s %.1f MiB\n","2049",a,12000/a,a*a*2" B",a*a*2/1048576;
  printf "   %-6s %-9s %-9.2f %-16s %.1f MiB\n","513", b,12000/b,b*b*2" B",b*b*2/1048576}'
echo "===== DONE ====="
