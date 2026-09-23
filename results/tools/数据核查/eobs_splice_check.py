"""eobs_splice_check.py — E-OBS v33.0e/v29.0e 拼接断点（2010/2011）风险量化

背景
    data/E-OBS/EOBS_tg_1983_2023.nc 由三段合并：
        tg_ens_mean_0.25deg_reg_1980-1994_v33.0e.nc
        tg_ens_mean_0.25deg_reg_1995-2010_v33.0e.nc
        tg_ens_mean_0.25deg_reg_2011-2023_v29.0e.nc   ← 版本从 v33.0e 变为 v29.0e
    E-OBS 不同版本使用的站点网不同，版本切换可能在序列上引入**非气候的台阶**，
    而论文结论（2003 后加速）恰依赖该时段。

四个检验（全部只用本地数据，无需下载）：
    T1 覆盖核对：三段文件的真实时间范围（是否有重叠可做直接版本对照）
    T2 台阶检验 + 安慰剂：对区域年均序列在每个候选断点年做同样的
       anomaly ~ a + c·t [+ q·t²] + d·1[t>=b] 拟合，看 b=2011 是否异常
    T3 平滑度检验：站点网变稀疏 → 插值场更平滑。比较 2011 前后
       逐日空间粗糙度（相邻**且都有效**格点对的平均绝对差）
    T4 季节/分区一致性：站点网变更应在所有季节、所有区域留下同号台阶

性能：每个区域只读一次 NetCDF，之后全部在 numpy 上聚合（避免反复整幅 .where）。
"""
import os
import sys

import numpy as np
import xarray as xr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "python"))
from config import EOBS_DIR, EOBS_MERGED_FILE  # noqa: E402

SEG3 = os.path.join(EOBS_DIR, "tg_ens_mean_0.25deg_reg_2011-2023_v29.0e.nc")
SEG2 = os.path.join(EOBS_DIR, "tg_ens_mean_0.25deg_reg_1995-2010_v33.0e.nc")
SEG1 = os.path.join(EOBS_DIR, "tg_ens_mean_0.25deg_reg_1980-1994_v33.0e.nc")
SPLICE = 2011

REGIONS = {
    "地中海&黑海": ((30, 47), (5, 42)),
    "西地中海": ((35, 45), (-5, 15)),
    "中地中海": ((35, 45), (15, 25)),
    "东地中海": ((30, 42), (25, 36)),
    "波罗的海": ((53, 66), (10, 30)),
    "大西洋岸": ((36, 55), (-12, -2)),
}
SEASONS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8),
           "SON": (9, 10, 11), "JAS": (7, 8, 9)}


def _var(ds):
    return ds["tg"] if "tg" in ds else ds[list(ds.data_vars)[0]]


def t1_coverage():
    print("=" * 72)
    print("T1 三段文件的真实时间覆盖（是否有重叠可做直接版本对照）")
    print("=" * 72)
    rows = []
    for lbl, p in (("seg1 v33.0e", SEG1), ("seg2 v33.0e", SEG2), ("seg3 v29.0e", SEG3)):
        ds = xr.open_dataset(p)
        t = ds["time"].values.astype("datetime64[D]")
        rows.append((lbl, str(t.min()), str(t.max()), t.size))
        print(f"  {lbl:14s} {t.min()} .. {t.max()}   n={t.size}")
        ds.close()
    ov = str(rows[1][2]) >= str(rows[2][1])
    print(f"\n  seg2 与 seg3 是否重叠: {ov}")
    if not ov:
        print("  → 无重叠期，无法对同一时段做直接版本对照，只能做统计检验")


def load_box(da, lat_range, lon_range):
    """读一个小区域，返回 (values[nt,ny,nx] float32, years[nt], months[nt])。"""
    sub = da.sel(lat=slice(*lat_range), lon=slice(*lon_range))
    v = np.asarray(sub.values, dtype=np.float32)
    t = sub.time.values
    years = t.astype("datetime64[Y]").astype(int) + 1970
    months = t.astype("datetime64[M]").astype(int) % 12 + 1
    return v, years, months


def series_from_box(v, years, months, sel_months=None):
    """区域内日值平均（nan 忽略）→ 逐日序列。"""
    with np.errstate(invalid="ignore"):
        ts = np.nanmean(v.reshape(v.shape[0], -1), axis=1)
    if sel_months is not None:
        m = np.isin(months, sel_months)
        return ts[m], years[m]
    return ts, years


def annual(ts, years):
    uy = np.unique(years)
    return uy, np.array([np.nanmean(ts[years == y]) for y in uy])


def step_test(uy, ann, b, quad=False):
    """anomaly ~ a + c·t [+ q·t²] + d·1[t>=b] → (d, t值)。"""
    t = uy - 1983.0
    cols = [np.ones_like(t), t]
    if quad:
        cols.append(t ** 2)
    cols.append((uy >= b).astype(float))
    X = np.column_stack(cols)
    y = np.asarray(ann, float)
    ok = np.isfinite(y)
    X, y = X[ok], y[ok]
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(X.shape[0] - X.shape[1], 1)
    s2 = float((resid ** 2).sum() / dof)
    se = np.sqrt(np.diag(s2 * np.linalg.pinv(X.T @ X)))
    d, sed = float(beta[-1]), float(se[-1])
    return d, (d / sed if sed > 0 else np.nan)


def t2_placebo(da):
    print("\n" + "=" * 72)
    print("T2 台阶检验 + 安慰剂（每个候选断点年都做同样的检验）")
    print("=" * 72)
    v, years, months = load_box(da, *REGIONS["地中海&黑海"])
    ts, yrs = series_from_box(v, years, months)
    uy, ann = annual(ts, yrs)
    print(f"  区域: 地中海&黑海   年数 {len(uy)} ({uy.min()}–{uy.max()})")
    print(f"  年均 tg: 1983–1990 {ann[uy < 1991].mean():.2f}  "
          f"2001–2010 {ann[(uy >= 2001) & (uy <= 2010)].mean():.2f}  "
          f"2011–2020 {ann[(uy >= 2011) & (uy <= 2020)].mean():.2f} °C")

    for quad in (False, True):
        print(f"\n  --- 趋势设定: {'线性 + 二次' if quad else '仅线性'} ---")
        res = [(int(b), *_step(uy, ann, b, quad)) for b in uy[(uy >= 1988) & (uy <= 2018)]]
        res_sorted = sorted(res, key=lambda r: -abs(r[2]))
        print(f"  {'断点年':>6} {'台阶(°C)':>10} {'t':>8}")
        for b, d, t in res_sorted[:8]:
            mark = "   ← 版本切换年" if b == SPLICE else ""
            print(f"  {b:>6} {d:>10.3f} {t:>8.2f}{mark}")
        rank = [i for i, r in enumerate(res_sorted, 1) if r[0] == SPLICE][0]
        d11 = [r for r in res if r[0] == SPLICE][0]
        print(f"  ⇒ 2011 在 {len(res)} 个候选年里按 |t| 排第 {rank}"
              f"；台阶 {d11[1]:+.3f} °C, t={d11[2]:+.2f}")


def _step(uy, ann, b, quad):
    return step_test(uy, ann, b, quad)


def t3_roughness(da):
    print("\n" + "=" * 72)
    print("T3 平滑度检验（站点网变稀疏 → 插值场更平滑 → 空间粗糙度下降）")
    print("=" * 72)
    v, years, months = load_box(da, *REGIONS["地中海&黑海"])
    nt = v.shape[0]

    def _rough(a, b):
        m = np.isfinite(a) & np.isfinite(b)
        d = np.where(m, np.abs(a - b), np.nan).reshape(nt, -1)
        with np.errstate(invalid="ignore"):
            return np.nanmean(d, axis=1)

    r_lat = _rough(v[:, :-1, :], v[:, 1:, :])
    r_lon = _rough(v[:, :, :-1], v[:, :, 1:])
    rough = np.nanmean(np.vstack([r_lat, r_lon]), axis=0)

    pre = rough[(years >= 2001) & (years <= 2010)]
    post = rough[(years >= 2011) & (years <= 2020)]
    print(f"  粗糙度 2001–2010: 均值 {np.nanmean(pre):.4f}   中位 {np.nanmedian(pre):.4f}")
    print(f"  粗糙度 2011–2020: 均值 {np.nanmean(post):.4f}   中位 {np.nanmedian(post):.4f}")
    print(f"  相对变化: {(np.nanmean(post) - np.nanmean(pre)) / np.nanmean(pre) * 100:+.2f}%")
    uy, ann = annual(rough, years)
    d, tt = step_test(uy, ann, SPLICE, quad=True)
    print(f"  粗糙度序列在 2011 的台阶: {d:+.5f} (t={tt:+.2f})")
    print("\n  逐年粗糙度（看 2011 是否突变）:")
    for y, r in zip(uy, ann):
        if 2005 <= y <= 2016:
            print(f"    {y}: {r:.4f}" + ("   ← 版本切换" if y == SPLICE else ""))


def t4_seasonal_spatial(da):
    print("\n" + "=" * 72)
    print("T4 季节/分区一致性（站点网变更应在所有季节留下同号台阶；气候信号不会）")
    print("=" * 72)
    v, years, months = load_box(da, *REGIONS["地中海&黑海"])
    print("  地中海&黑海，分季节（2011 台阶，趋势含二次项）:")
    for name, mm in SEASONS.items():
        ts, yrs = series_from_box(v, years, months, sel_months=mm)
        uy, ann = annual(ts, yrs)
        d, t = step_test(uy, ann, SPLICE, quad=True)
        print(f"    {name:4s} {d:+.3f} °C  (t={t:+.2f})")

    print("\n  JJA，分区域（2011 台阶，趋势含二次项）:")
    for rname, box in REGIONS.items():
        v2, y2, m2 = load_box(da, *box)
        ts, yrs = series_from_box(v2, y2, m2, sel_months=(6, 7, 8))
        uy, ann = annual(ts, yrs)
        d, t = step_test(uy, ann, SPLICE, quad=True)
        print(f"    {rname:10s} {d:+.3f} °C  (t={t:+.2f})")


def main():
    t1_coverage()
    ds = xr.open_dataset(EOBS_MERGED_FILE)
    da = _var(ds)
    t2_placebo(da)
    t3_roughness(da)
    t4_seasonal_spatial(da)
    ds.close()


if __name__ == "__main__":
    main()
