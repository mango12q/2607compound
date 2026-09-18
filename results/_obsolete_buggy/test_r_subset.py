import subprocess
import os
import sys

RSCRIPT = r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe"
SCRIPT = r"D:\2607compound\python\detect_thw_subset.R"
EOBS = r"E:\2607compound\data\E-OBS\EOBS_tg_1983_2023.nc"
OUT = r"D:\2607compound\results\intermediate\thw_events_subset.csv"

cmd = [RSCRIPT, SCRIPT, EOBS, OUT, "1983", "2012"]
print("Running:", " ".join(cmd))
res = subprocess.run(cmd, capture_output=True, text=True)
print(res.stdout)
if res.stderr:
    print("STDERR:", res.stderr)
print("Return code:", res.returncode)

if os.path.exists(OUT):
    import pandas as pd
    df = pd.read_csv(OUT)
    print(f"Output rows: {len(df)}")
    print(df.head())
