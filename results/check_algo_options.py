"""check_algo_options.py — 确认立即可用的合规热浪检测实现。"""
import importlib

print("=== 算法库可用性 ===")
for m in ["marineHeatWaves", "heatwaveR", "rpy2", "xarray", "numpy", "pandas"]:
    try:
        mod = importlib.import_module(m)
        ver = getattr(mod, "__version__", "(no __version__)")
        print(f"  {m:18s} OK       {ver}")
    except Exception as e:
        print(f"  {m:18s} MISSING  ({type(e).__name__})")

print("\n=== MHW 检测是否与 THW 共用同一套事件逻辑 ===")
import sys
sys.path.insert(0, r"D:\2607compound\python")
import inspect
import detect_mhw
import detect_events

src_mhw = inspect.getsource(detect_mhw)
print("  detect_mhw.py 导入 detect_events_from_exceed:",
      "detect_events_from_exceed" in src_mhw)
print("  detect_mhw.py 使用 DURATION_THRESH/GAP_TOLERANCE:",
      "DURATION_THRESH" in src_mhw and "GAP_TOLERANCE" in src_mhw)

# 事件终止判据对比
lines = [l.strip() for l in src_mhw.splitlines()]
for crit in ["end_idx - self.start_idx >= self.min_dur",
             "end_idx - start_idx >= min_duration"]:
    hits = [i + 1 for i, l in enumerate(lines) if crit in l]
    print(f"  '{crit}' 出现在 detect_mhw.py 行 {hits}")

print("\n  detect_events.py 判据:")
src_ev = inspect.getsource(detect_events)
for crit in ["end_idx - start_idx >= min_duration",
             "end_idx = i - gap_count + 1",
             "end_idx = last_true_idx + 1"]:
    print(f"    {'有' if crit in src_ev else '无'}  {crit}")
