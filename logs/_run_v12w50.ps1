# _v12 single point: w = 0.50 of the ALL-XGHG land climatology difference applied to the
# XGHG world's land 90th-percentile threshold (w*delta_t2m = 0.50*1.129 = 0.5645 degC).
# Same chain as _run_v12_scan.ps1, plus fig4 so the panel figure lands with the tag.
# gev uses --mapping emp. ASCII only (GBK console).
$ErrorActionPreference = "Continue"
$ws  = "D:\2607compound"
$log = "$ws\logs\run_v12w50.log"
$steps = "$ws\logs\steps"
if (!(Test-Path $steps)) { New-Item -ItemType Directory -Path $steps | Out-Null }

function Log($m) {
    $line = "[{0}] {1}" -f ([DateTime]::Now.ToString("HH:mm:ss")), $m
    $line | Out-File -FilePath $log -Append -Encoding utf8
    Write-Host $line
}

function Run-Step($name, $stepLog, $argv) {
    Log "$name start -> $stepLog"
    $sw = [Diagnostics.Stopwatch]::StartNew()
    & python $argv *> $stepLog
    $sw.Stop()
    $code = $LASTEXITCODE
    Log ("{0,-10} exit={1} {2:N2} min" -f $name, $code, $sw.Elapsed.TotalMinutes)
}

Log "=== v12w50 single point start ==="

$tag = "_v12w50"
$off = 0.5645
Log "--- w*delta_t2m = $off  tag = $tag ---"

Run-Step "detect" "$steps\v12w50_detect.log" @(
    "$ws\python\phase6_cesm.py","detect","--members","20","--baseline","self",
    "--loo","--clim-period","1983-2012","--tag",$tag,"--thresh-offset-xghg-t2m","$off")

Run-Step "compound" "$steps\v12w50_compound.log" @(
    "$ws\python\phase6_cesm.py","compound","--members","20","--tag",$tag,
    "--compound-def","envelope")

Run-Step "attrib" "$steps\v12w50_attrib.log" @(
    "$ws\python\phase6_cesm.py","attrib","--members","20","--tag",$tag,
    "--compound-def","envelope","--agg","med_mean","med_p90","med_max",
    "eur_mean","eur_p90","eur_max")

Run-Step "gev" "$steps\v12w50_gev.log" @(
    "$ws\python\phase6_cesm.py","gev","--members","20","--tag",$tag,
    "--compound-def","envelope","--mapping","emp")

Run-Step "fig4" "$steps\v12w50_fig4.log" @(
    "$ws\python\fig4_return_period.py","--tag",$tag)

Run-Step "table1" "$steps\v12w50_table1.log" @(
    "$ws\python\table1_attribution.py","--tag",$tag,
    "--out","$ws\results\tables\table1$tag.csv")

Log "=== v12w50 done ==="
