# Diagnostic: prove this machine has no Clash Verge / 127.0.0.1:7897 dependency.
# Run in a NEW PowerShell window (old processes keep the environment they started with).
$ErrorActionPreference = 'SilentlyContinue'
$fail = 0
Write-Host '=== Windows system proxy ==='
$ie = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
Write-Host ("ProxyEnable = {0}" -f $ie.ProxyEnable)
Write-Host ("ProxyServer = '{0}'" -f $ie.ProxyServer)
if ($ie.ProxyEnable -ne 0) { Write-Host 'FAIL system proxy is enabled'; $fail++ }
if ($ie.ProxyServer -match '7897') { Write-Host 'FAIL stale Clash ProxyServer'; $fail++ }

Write-Host '=== process environment ==='
foreach ($n in 'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy') {
  $v = [Environment]::GetEnvironmentVariable($n)
  Write-Host ("{0} = '{1}'" -f $n, $v)
  if ($v -match '7897') { Write-Host "FAIL $n still points at Clash"; $fail++ }
}

Write-Host '=== direct egress (no proxy) ==='
foreach ($url in 'https://api.github.com/', 'https://xiaodernan.github.io/') {
  try {
    # curl.exe is present on Windows 10+; --noproxy '*' proves egress without any proxy.
    $body = & curl.exe --noproxy '*' -s -o NUL -w '%{http_code}' --max-time 15 $url
    Write-Host ("{0} -> {1}" -f $url, $body)
    if ($body -ne '200') { $fail++ }
  } catch {
    Write-Host ("{0} -> FAIL {1}" -f $url, $_.Exception.Message)
    $fail++
  }
}

if ($fail -eq 0) { Write-Host 'OK: normal network, no Clash dependency' }
exit $fail
