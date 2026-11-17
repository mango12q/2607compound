# Phase 6 re-run with the PAPER baseline: threshold climatology = 1983-2012.
# Tag _v5. ASCII only.
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'

$root = 'D:\2607compound'
Set-Location $root
$stepDir = Join-Path $root 'logs\steps'
New-Item -ItemType Directory -Force -Path $stepDir | Out-Null
$master = Join-Path $root 'logs\run_v5.log'

function Write-Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $master -Value $line -Encoding utf8
}

$steps = @(
    @{ name = 'detect_v5';  args = @('python\phase6_cesm.py', 'detect', '--members', '20', '--baseline', 'xghg', '--loo', '--tag', '_v5', '--clim-period', '1983-2012') },
    @{ name = 'compound_v5';args = @('python\phase6_cesm.py', 'compound', '--members', '20', '--tag', '_v5', '--compound-def', 'envelope') },
    @{ name = 'attrib_v5';  args = @('python\phase6_cesm.py', 'attrib', '--members', '20', '--tag', '_v5', '--compound-def', 'envelope', '--agg', 'med_mean', 'med_p90', 'med_max', 'eur_mean', 'eur_p90', 'eur_max') },
    @{ name = 'gev_v5';     args = @('python\phase6_cesm.py', 'gev', '--members', '20', '--tag', '_v5', '--compound-def', 'envelope') },
    @{ name = 'fig3_v5';    args = @('python\fig3_attribution.py', '--tag', '_v5', '--agg-eur', 'eur_p90', '--agg-med', 'med_p90') },
    @{ name = 'fig4_v5';    args = @('python\fig4_return_period.py', '--tag', '_v5') },
    @{ name = 'table1_v5';  args = @('python\table1_attribution.py', '--tag', '_v5') }
)

Write-Log '===== START v5 clim 1983-2012 ====='
$results = @()
foreach ($s in $steps) {
    $logf = Join-Path $stepDir ($s.name + '.log')
    Write-Log ("-> {0}  |  python {1}" -f $s.name, ($s.args -join ' '))
    $t0 = Get-Date
    & python @($s.args) *>&1 | Tee-Object -FilePath $logf
    $code = $LASTEXITCODE
    $mins = [math]::Round(((Get-Date) - $t0).TotalMinutes, 2)
    Write-Log ("<- {0}  exit={1}  ({2} min)" -f $s.name, $code, $mins)
    $results += [pscustomobject]@{ step = $s.name; exit = $code; minutes = $mins }
}
Write-Log '===== SUMMARY ====='
foreach ($r in $results) { Write-Log ("  {0,-12} exit={1}  {2} min" -f $r.step, $r.exit, $r.minutes) }
Write-Log '===== DONE v5 ====='
