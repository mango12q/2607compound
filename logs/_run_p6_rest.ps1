# Resume Phase 6 full chain from 'detect' (detect -> compound -> attrib).
# ASCII only (AGENTS.md: no Chinese inside .ps1 / .bat).
# Launched detached (Start-Process -WindowStyle Hidden) so it survives agent-session restarts.

$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'

$root = 'D:\2607compound'
Set-Location $root
$stepDir = Join-Path $root 'logs\steps'
New-Item -ItemType Directory -Force -Path $stepDir | Out-Null
$master = Join-Path $root 'logs\run_p6_rest.log'

function Write-Log($msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $master -Value $line -Encoding utf8
}

$steps = @(
    @{ name = 'p6_detect';   args = @('python\phase6_cesm.py', 'detect', '--members', '20', '--baseline', 'xghg', '--loo', '--tag', '_v4') },
    @{ name = 'p6_compound'; args = @('python\phase6_cesm.py', 'compound', '--members', '20', '--tag', '_v4', '--compound-def', 'envelope') },
    @{ name = 'p6_attrib';   args = @('python\phase6_cesm.py', 'attrib', '--members', '20', '--tag', '_v4', '--compound-def', 'envelope') }
)

Write-Log '===== START p6 rest (detect/compound/attrib) ====='
$results = @()

foreach ($s in $steps) {
    $logf = Join-Path $stepDir ($s.name + '.log')
    Write-Log ("-> {0}  |  python {1}" -f $s.name, ($s.args -join ' '))
    $t0 = Get-Date
    & python @($s.args) *>&1 | Tee-Object -FilePath $logf
    $code = $LASTEXITCODE
    $mins = [math]::Round(((Get-Date) - $t0).TotalMinutes, 1)
    Write-Log ("<- {0}  exit={1}  ({2} min)" -f $s.name, $code, $mins)
    $results += [pscustomobject]@{ step = $s.name; exit = $code; minutes = $mins }
}

Write-Log '===== SUMMARY ====='
foreach ($r in $results) { Write-Log ("  {0,-12} exit={1}  {2} min" -f $r.step, $r.exit, $r.minutes) }
Write-Log '===== DONE p6 rest ====='
