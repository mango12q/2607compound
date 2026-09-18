"""show_stats.py — 打印 fig_stats_new.json 关键值。"""
import json

d = json.load(open(r"D:\2607compound\results\tables\fig_stats_new.json"))
for k, v in d.items():
    if "years" not in v:
        print(f"{k:26s} {v}")
        continue
    yrs = v["years"]
    vals = v["values"]
    sel = {y: round(x, 2) for y, x in zip(yrs, vals)
           if y in (1990, 1995, 2003, 2018, 2022, 2023)}
    print(f"{k:26s} {sel}  max={round(v['max'], 2)}  mean={round(v['mean'], 2)}")
print("\n论文锚点: fig1j 80s/90s<20, 2022~78, 2023~72 | fig2c 80s/90s~1, 2023~3.5")
