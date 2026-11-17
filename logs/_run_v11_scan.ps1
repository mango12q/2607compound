# _v11 per-variable threshold offset scan (land only).
# baseline=self (each experiment its own 1983-2012 climatology) + theta_t2m degC on the
# terrestrial threshold only, theta_sst = 0.  Rationale: measured model warm bias
# beta_t2m(Med box) = +1.17 degC vs beta_sst = +0.07 degC, so an "observed thresholds"
# reading demands a land-only offset.
# gev uses --mapping emp (empirical quantile mapping = _v10 kernel).
# ASCII only (GBK console).
$ErrorActionPreference = "Continue"
$ws  = "D:\2607compound"
$log = "$ws\logs\run_v11_scan.log"
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

Log "=== v11 per-variable (land-only) offset scan start ==="

$jobs = @(
    @{ tag = "_v11t06"; off = 0.60 },
    @{ tag = "_v11t11"; off = 1.10 }
)

foreach ($j in $jobs) {
    $tag = $j.tag
    $off = $j.off
    Log "--- theta_t2m = $off  tag = $tag ---"

    Run-Step "detect" "$steps\v11$tag`_detect.log" @(
        "$ws\python\phase6_cesm.py","detect","--members","20","--baseline","self",
        "--loo","--clim-period","1983-2012","--tag",$tag,"--thresh-offset-t2m","$off")

    Run-Step "compound" "$steps\v11$tag`_compound.log" @(
        "$ws\python\phase6_cesm.py","compound","--members","20","--tag",$tag,
        "--compound-def","envelope")

    Run-Step "attrib" "$steps\v11$tag`_attrib.log" @(
        "$ws\python\phase6_cesm.py","attrib","--members","20","--tag",$tag,
        "--compound-def","envelope","--agg","med_mean","med_p90","med_max",
        "eur_mean","eur_p90","eur_max")

    Run-Step "gev" "$steps\v11$tag`_gev.log" @(
        "$ws\python\phase6_cesm.py","gev","--members","20","--tag",$tag,
        "--compound-def","envelope","--mapping","emp")

    Run-Step "table1" "$steps\v11$tag`_table1.log" @(
        "$ws\python\table1_attribution.py","--tag",$tag,
        "--out","$ws\results\tables\table1$tag.csv")
}

Log "=== v11 scan done ==="
