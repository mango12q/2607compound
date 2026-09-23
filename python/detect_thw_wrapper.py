"""
detect_thw_wrapper.py — 陆地热浪检测入口
调用 R heatwaveR 脚本，读取输出 CSV。

R 侧 detector = heatwaveR::ts2clm + detect_event（Hobday et al. 2016）：
  * 阈值  : 11 天滑动窗口的 90th 分位数（windowHalfWidth = 5, pctile = 90）
  * 事件  : 连续 >= 5 天超过阈值，允许 <= 2 天间隙
  * 参考期: 1983-2012

与 python/detect_thw.py（纯 Python 手写）的**已知差异**（详见
results/方法与证据.md §4）：
  1) 阈值：Python 用逐 dayofyear 单日分位数，无滑动窗口
  2) 最小持续时间口径：Python 用"事件跨度(含间隙) >= 5"，
     heatwaveR 用"超标日游程(不含间隙) >= 5"
  第 2 点是 R 事件数约为 Python 一半的主因（消融实验：-45%）。
  本 wrapper 调用的是方法学上更规范的 heatwaveR 版本。
"""
import os
import subprocess
from typing import Optional

import pandas as pd

from config import (
    EOBS_MERGED_FILE, THW_EVENTS_CSV, CLIM_PERIOD,
    RSCRIPT_PATH, DETECT_THW_R_SCRIPT,
    HW_MIN_DURATION, HW_MAX_GAP, R_WORKERS,
)


def detect_thw(
    eobs_filepath: Optional[str] = None,
    output_csv: Optional[str] = None,
    clim_period: tuple = CLIM_PERIOD,
    min_duration: int = HW_MIN_DURATION,
    max_gap: int = HW_MAX_GAP,
    workers: int = R_WORKERS,
    work_dir: Optional[str] = None,
) -> pd.DataFrame:
    if eobs_filepath is None:
        eobs_filepath = EOBS_MERGED_FILE
    if output_csv is None:
        output_csv = THW_EVENTS_CSV
    if work_dir is None:
        work_dir = output_csv + ".work"

    if not os.path.exists(eobs_filepath):
        raise FileNotFoundError(
            f"E-OBS file not found: {eobs_filepath}\n"
            f"Run preprocess.merge_eobs() first."
        )

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    cmd = [
        RSCRIPT_PATH,
        DETECT_THW_R_SCRIPT,
        eobs_filepath,
        output_csv,
        str(clim_period[0]),
        str(clim_period[1]),
        str(min_duration),
        str(max_gap),
        str(workers),
        work_dir,
        eobs_filepath,   # 全局参考网格（与输入同一文件时无需子集映射）
    ]

    print(f"Running R heatwaveR detection: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )
    print(result.stdout)
    if result.stderr:
        print("R stderr:", result.stderr)

    if not os.path.exists(output_csv):
        raise RuntimeError(f"R script did not produce output: {output_csv}")

    print(f"Loading THW events from: {output_csv}")
    thw_df = pd.read_csv(output_csv)

    # Normalize column names to match downstream code
    rename_map = {}
    if 'date_start' in thw_df.columns:
        rename_map['date_start'] = 'event_start'
    if 'date_end' in thw_df.columns:
        rename_map['date_end'] = 'event_end'
    if rename_map:
        thw_df = thw_df.rename(columns=rename_map)

    for col in ('event_start', 'event_end'):
        if col in thw_df.columns:
            thw_df[col] = pd.to_datetime(thw_df[col])

    print(f"Loaded {len(thw_df)} THW events")
    return thw_df


def load_thw_events(csv_path: Optional[str] = None) -> pd.DataFrame:
    if csv_path is None:
        csv_path = THW_EVENTS_CSV

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"THW events CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    rename_map = {}
    if 'date_start' in df.columns:
        rename_map['date_start'] = 'event_start'
    if 'date_end' in df.columns:
        rename_map['date_end'] = 'event_end'
    if rename_map:
        df = df.rename(columns=rename_map)

    if 'event_start' in df.columns:
        df['event_start'] = pd.to_datetime(df['event_start'])
    if 'event_end' in df.columns:
        df['event_end'] = pd.to_datetime(df['event_end'])

    print(f"Loaded {len(df)} THW events from {csv_path}")
    return df
