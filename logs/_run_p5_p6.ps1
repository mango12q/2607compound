# Run Phase 5 full chain, then Phase 6 full 20-member chain, sequentially.
# ASCII only (AGENTS.md: no Chinese inside .ps1 / .bat).
# Each step logs to logs\steps\<name>.log ; a failure does NOT stop later steps.

$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'

$root = 'D:\2607compound'
Set-Location $root
$stepDir = Join-Path $root 'logs\steps'
New-Item -ItemType Directory -Force -Path $stepDir | Out-Null
$master = Join-Path $root 'logs\run_p5_p6.log'

function Write-Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $master -Value $line -Encoding utf8
}

$steps = @(
    @{ name = 'p5_buffer';   args = @('python\coastal_buffer.py') },
    @{ name = 'p5_all';      args = @('python\phase5_humid.py', 'all') },
    @{ name = 'p6_pairs';    args = @('python\phase6_cesm.py', 'pairs') },
    @{ name = 'p6_prepare';  args = @('python\phase6_cesm.py', 'prepare', '--members', '20') },
    @{ name = 'p6_detect';   args = @('python\phase6_cesm.py', 'detect', '--members', '20', '--baseline', 'xghg', '--loo', '--tag', '_v4') },
    @{ name = 'p6_compound'; args = @('python\phase6_cesm.py', 'compound', '--members', '20', '--tag', '_v4', '--compound-def', 'envelope') },
    @{ name = 'p6_attrib';   args = @('python\phase6_cesm.py', 'attrib', '--members', '20', '--tag', '_v4', '--compound-def', 'envelope') }
)

Write-Log '===== START p5+p6 chain ====='
$results = @()

foreach ($s in $steps) {
    $logf = Join-Path $stepDir ($s.name + '.log')
    $cmdline = 'python ' + ($s.args -join ' ')
    Write-Log ("-> {0}  |  {1}" -f $s.name, $cmdline)
    $t0 = Get-Date
    & python @($s.args) *>&1 | Tee-Object -FilePath $logf
    $code = $LASTEXITCODE
    $mins = [math]::Round(((Get-Date) - $t0).TotalMinutes, 1)
    Write-Log ("<- {0}  exit={1}  ({2} min)" -f $s.name, $code, $mins)
    $results += [pscustomobject]@{ step = $s.name; exit = $code; minutes = $mins }
}

Write-Log '===== SUMMARY ====='
foreach ($r in $results) { Write-Log ("  {0,-12} exit={1}  {2} min" -f $r.step, $r.exit, $r.minutes) }
Write-Log '===== DONE p5+p6 chain ====='
