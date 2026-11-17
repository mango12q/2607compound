# _v9 theta calibration scan: shared XGHG-pool threshold + theta degC offset.
# theta=0 is the _v5/v7 XGHG-side endpoint; theta=delta(1.13 T2m / 0.80 SST) is _v8.
# ASCII only (GBK console).
$ErrorActionPreference = "Continue"
$ws  = "D:\2607compound"
$log = "$ws\logs\run_v9_scan.log"
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

Log "=== v9 theta scan start ==="

$jobs = @(
    @{ tag = "_v9o40"; off = 0.40 },
    @{ tag = "_v9o70"; off = 0.70 }
)

foreach ($j in $jobs) {
    $tag = $j.tag
    $off = $j.off
    Log "--- theta = $off  tag = $tag ---"

    Run-Step "detect" "$steps\v9$tag`_detect.log" @(
        "$ws\python\phase6_cesm.py","detect","--members","20","--baseline","xghg",
        "--loo","--clim-period","1983-2012","--tag",$tag,"--thresh-offset","$off")

    Run-Step "compound" "$steps\v9$tag`_compound.log" @(
        "$ws\python\phase6_cesm.py","compound","--members","20","--tag",$tag,
        "--compound-def","envelope")

    Run-Step "attrib" "$steps\v9$tag`_attrib.log" @(
        "$ws\python\phase6_cesm.py","attrib","--members","20","--tag",$tag,
        "--compound-def","envelope","--agg","med_mean","med_p90","med_max",
        "eur_mean","eur_p90","eur_max")

    Run-Step "gev" "$steps\v9$tag`_gev.log" @(
        "$ws\python\phase6_cesm.py","gev","--members","20","--tag",$tag,
        "--compound-def","envelope")

    Run-Step "table1" "$steps\v9$tag`_table1.log" @(
        "$ws\python\table1_attribution.py","--tag",$tag,
        "--out","$ws\results\tables\table1$tag.csv")
}

Log "=== v9 theta scan done ==="
