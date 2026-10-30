# CESM1-LE download monitor (ASCII only -- cmd/powershell reads UTF-8 without BOM as GBK)
# Refreshes every 5 s. Ctrl+C or close the window to stop (downloads keep running).
$root = "D:\2607compound"
$logs = Join-Path $root "logs"
$proc = Join-Path $root "data\CESM1-LE\proc"

while ($true) {
    Clear-Host
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*download_cesm1le*" })
    $atmAlive = @($procs | Where-Object { $_.CommandLine -like "*only-comp atm*" })
    $ocnAlive = @($procs | Where-Object { $_.CommandLine -like "*only-comp ocn*" })

    $atmFiles = @(Get-ChildItem $proc -Filter "trefht_*_2000-2021.nc" -ErrorAction SilentlyContinue)
    $ocnFiles = @(Get-ChildItem $proc -Filter "sst_*_2000-2021.nc" -ErrorAction SilentlyContinue)
    $atmMb = 0; if ($atmFiles.Count -gt 0) { $atmMb = [int](($atmFiles | Measure-Object Length -Sum).Sum / 1MB) }
    $ocnMb = 0; if ($ocnFiles.Count -gt 0) { $ocnMb = [int](($ocnFiles | Measure-Object Length -Sum).Sum / 1MB) }

    Write-Host "=== CESM1-LE download monitor ===  $now" -ForegroundColor Cyan
    Write-Host ""
    Write-Host ("shards alive : atm {0} / ocn {1}   (expect 6 + 6)" -f $atmAlive.Count, $ocnAlive.Count) -ForegroundColor Yellow
    Write-Host ("groups done  : atm {0}/40 ({1} MB)   ocn {2}/40 ({3} MB)" -f $atmFiles.Count, $atmMb, $ocnFiles.Count, $ocnMb) -ForegroundColor Green
    Write-Host ""
    foreach ($c in @("atm", "ocn")) {
        Write-Host ("--- " + $c + " shards ---") -ForegroundColor Gray
        foreach ($i in 0..6) {
            $f = Join-Path $logs ("_cesm_dap2_" + $c + "_shard" + $i + ".log")
            if (Test-Path $f) {
                $tail = ""
                $last = Get-Content $f -Tail 1 -ErrorAction SilentlyContinue
                if ($last) { $tail = $last.Trim() }
                $age = 9999
                if (Test-Path $f) { $age = [int]((Get-Date) - (Get-Item $f).LastWriteTime).TotalMinutes }
                $state = "idle"
                if ($age -lt 3) { $state = "RUN " }
                Write-Host ("  " + $c + $i + "  " + $state + "  (" + $age + "m)  " + $tail)
            }
        }
    }
    Write-Host ""
    Write-Host "refreshing every 5 s ..." -ForegroundColor DarkGray
    Start-Sleep -Seconds 5
}
