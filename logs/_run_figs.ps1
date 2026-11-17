# Phase 6 GEV + all paper figures (Fig 3/4/5/6 + Table 1). ASCII only.
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'

$root = 'D:\2607compound'
Set-Location $root
$stepDir = Join-Path $root 'logs\steps'
New-Item -ItemType Directory -Force -Path $stepDir | Out-Null
$master = Join-Path $root 'logs\run_figs.log'

function Write-Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $master -Value $line -Encoding utf8
}

$steps = @(
    @{ name = 'gev_v4';    args = @('python\phase6_cesm.py', 'gev', '--members', '20', '--tag', '_v4', '--compound-def', 'envelope') },
    @{ name = 'fig3';      args = @('python\fig3_attribution.py', '--tag', '_v4') },
    @{ name = 'fig4';      args = @('python\fig4_return_period.py', '--tag', '_v4') },
    @{ name = 'fig5';      args = @('python\fig5_sst_trend.py') },
    @{ name = 'fig6';      args = @('python\fig6_wbt.py') },
    @{ name = 'table1';    args = @('python\table1_attribution.py', '--tag', '_v4') }
)

Write-Log '===== START gev + figures ====='
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
foreach ($r in $results) { Write-Log ("  {0,-10} exit={1}  {2} min" -f $r.step, $r.exit, $r.minutes) }
Write-Log '===== DONE gev + figures ====='
