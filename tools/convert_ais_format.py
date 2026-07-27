#!/usr/bin/env python3
"""
AIS 格式转换脚本
将 USCG 格式 AIS CSV (逗号分隔) 转换为 colav-simulator 期望格式 (分号分隔)

colav-simulator 期望格式:
  分隔符: 分号 (;)
  必须列: date_time_utc, lat, lon, mmsi, sog, cog
  可选列: heading, length, width, draft, nav_status

用法:
  python3 tools/convert_ais_format.py [input.csv] [output.csv]
"""
import sys
import pandas as pd
from pathlib import Path

# 挪威 More og Romsdal (Ålesund) 大致范围
NORWAY_LAT_RANGE = (62.0, 63.5)
NORWAY_LON_RANGE = (5.0, 8.0)

def check_geographic_compatibility(df):
    lat_min, lat_max = df['LAT'].min(), df['LAT'].max()
    lon_min, lon_max = df['LON'].min(), df['LON'].max()
    print(f"  输入数据地理范围: 纬度 {lat_min:.3f}~{lat_max:.3f}°, 经度 {lon_min:.3f}~{lon_max:.3f}°")
    in_norway = (
        lat_min >= NORWAY_LAT_RANGE[0] and lat_max <= NORWAY_LAT_RANGE[1] and
        lon_min >= NORWAY_LON_RANGE[0] and lon_max <= NORWAY_LON_RANGE[1]
    )
    if in_norway:
        print("  ✅ 坐标与挪威 Ålesund ENC 数据匹配")
    else:
        print("  ❌ 坐标不在挪威区域（需 lat≈62~63.5°N, lon≈5~8°E）")
        print("     当前数据无法与 More_og_Romsdal ENC 海图配合使用")
    return in_norway

def convert(input_path, output_path):
    print(f"\n读取: {input_path}")
    df = pd.read_csv(input_path)
    print(f"  {len(df)} 行, 列: {list(df.columns)}")

    print("\n地理兼容性检查:")
    compatible = check_geographic_compatibility(df)

    # 列名映射
    mapping = {
        'MMSI': 'mmsi', 'BaseDateTime': 'date_time_utc',
        'LAT': 'lat', 'LON': 'lon', 'SOG': 'sog', 'COG': 'cog',
        'Heading': 'heading', 'Length': 'length', 'Width': 'width',
        'Draft': 'draft', 'Status': 'nav_status',
        'VesselName': 'name', 'IMO': 'imo', 'CallSign': 'callsign',
        'VesselType': 'ship_type',
    }
    df_out = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
    keep = [c for c in ['mmsi','date_time_utc','lat','lon','sog','cog',
                         'heading','length','width','draft','nav_status',
                         'name','imo','callsign','ship_type'] if c in df_out.columns]
    df_out = df_out[keep]
    df_out.to_csv(output_path, sep=';', index=False)
    print(f"\n✅ 已保存: {output_path} ({len(df_out)} 行)")
    if not compatible:
        print("\n⚠️  注意: 因地理坐标不匹配, 此文件在挪威海域仿真中会报错。")
        print("   请从 https://kartkatalog.geonorge.no 获取挪威真实 AIS 数据。")

if __name__ == "__main__":
    inp = sys.argv[1] if len(sys.argv) > 1 else "data/ais_datasets/AIS_synthetic_1h.csv"
    out = sys.argv[2] if len(sys.argv) > 2 else inp.replace(".csv", "_converted.csv")
    convert(inp, out)
