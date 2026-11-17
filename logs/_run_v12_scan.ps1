# _v12 reference-climatology MIXING scan: land threshold moved only in the counterfactual world.
# w = fraction of the ALL-XGHG land climatology difference (delta_t2m = 1.129 degC) that the
# XGHG world's 90th-percentile threshold is shifted toward the ALL world.
#   w = 0  -> _v7/_v10 (each experiment its own climatology)
#   w = 1  -> _v8 land side (thresholds identical in both worlds)
# gev uses --mapping emp. ASCII only (GBK console).
$ErrorActionPreference = "Continue"
$ws  = "D:\2607compound"
$log = "$ws\logs\run_v12_scan.log"
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

Log "=== v12 mixing-weight scan start ==="

$jobs = @(
    @{ tag = "_v12w60"; off = 0.68 },
    @{ tag = "_v12w89"; off = 1.00 }
)

foreach ($j in $jobs) {
    $tag = $j.tag
    $off = $j.off
    Log "--- w*delta_t2m = $off  tag = $tag ---"

    Run-Step "detect" "$steps\v12$tag`_detect.log" @(
        "$ws\python\phase6_cesm.py","detect","--members","20","--baseline","self",
        "--loo","--clim-period","1983-2012","--tag",$tag,"--thresh-offset-xghg-t2m","$off")

    Run-Step "compound" "$steps\v12$tag`_compound.log" @(
        "$ws\python\phase6_cesm.py","compound","--members","20","--tag",$tag,
        "--compound-def","envelope")

    Run-Step "attrib" "$steps\v12$tag`_attrib.log" @(
        "$ws\python\phase6_cesm.py","attrib","--members","20","--tag",$tag,
        "--compound-def","envelope","--agg","med_mean","med_p90","med_max",
        "eur_mean","eur_p90","eur_max")

    Run-Step "gev" "$steps\v12$tag`_gev.log" @(
        "$ws\python\phase6_cesm.py","gev","--members","20","--tag",$tag,
        "--compound-def","envelope","--mapping","emp")

    Run-Step "table1" "$steps\v12$tag`_table1.log" @(
        "$ws\python\table1_attribution.py","--tag",$tag,
        "--out","$ws\results\tables\table1$tag.csv")
}

Log "=== v12 scan done ==="
