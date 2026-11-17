$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location 'D:\2607compound'
$log = 'D:\2607compound\logs\run_v6.log'
"[{0}] === v6 self-baseline chain start ===" -f (Get-Date -Format 'HH:mm:ss') | Out-File $log -Encoding utf8
New-Item -ItemType Directory -Force -Path 'D:\2607compound\logs\steps' | Out-Null

$steps = @(
  @('detect',    @('python\phase6_cesm.py','detect','--members','20','--baseline','self','--loo','--clim-period','2000-2021','--tag','_v6')),
  @('compound',  @('python\phase6_cesm.py','compound','--members','20','--tag','_v6','--compound-def','envelope')),
  @('attrib',    @('python\phase6_cesm.py','attrib','--members','20','--tag','_v6','--compound-def','envelope','--agg','med_mean','med_p90','med_max','eur_mean','eur_p90','eur_max')),
  @('gev',       @('python\phase6_cesm.py','gev','--members','20','--tag','_v6','--compound-def','envelope')),
  @('fig3',      @('python\fig3_attribution.py','--tag','_v6')),
  @('fig4',      @('python\fig4_return_period.py','--tag','_v6')),
  @('table1',    @('python\table1_attribution.py','--tag','_v6'))
)

foreach ($s in $steps) {
  $name = $s[0]
  $argv = $s[1]
  $t0 = Get-Date
  $sl = "D:\2607compound\logs\steps\v6_$name.log"
  $exe = 'python'
  $rest = $argv
  & $exe $rest *> $sl
  $rc = $LASTEXITCODE
  $dt = ((Get-Date) - $t0).TotalMinutes
  "[{0}] {1,-9} exit={2} {3:N2} min  -> {4}" -f (Get-Date -Format 'HH:mm:ss'), $name, $rc, $dt, $sl | Out-File $log -Append -Encoding utf8
  if ($rc -ne 0) { break }
}
"[{0}] === v6 done ===" -f (Get-Date -Format 'HH:mm:ss') | Out-File $log -Append -Encoding utf8
