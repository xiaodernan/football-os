<#
.SYNOPSIS
  M14 service-plane live walk — reads every claim back from a running process.

.DESCRIPTION
  Sixteen checks against a locally running plane; when the world-check citizen (services/worldcheck) is also up,
  five more land — live invariants, eureka registration, and the config server serving the worldcheck properties file;
  the jobs-observer citizen adds its own five (live ledger door, consumer-group wiring, eureka registration,
  config server serving the jobs-observer properties file). The exact count is printed at the bottom of the run;
  do not pin it in prose.

  The walk is a *witness*, not a test suite: it answers "does the plane behave as the
  document claims, on this host, right now?" — trace minted, trace echoed, gateway
  transparency, route table read from the running gateway, registry membership, and
  the config server serving the edge's route from the file in this repository.

  Exit code 0 when every check reads true; 1 otherwise, with the per-check map printed.

.PARAMETER Edge
  Base URL of the running edge gateway. Default http://127.0.0.1:18080 (8080 is commonly
  bound elsewhere on Windows dev hosts; the M14 doc shows EDGE_PORT as the knob).

.PARAMETER Core
  Base URL of the running FastAPI core. Default http://127.0.0.1:8100.

.PARAMETER Registry
  Base URL of the Eureka registry. Default http://127.0.0.1:18760 — the football registry publishes 8761 to 18760 on the dev host (this host's 8761 belongs to the Docker backend proxy), container-to-container they still speak 8761, so only the host-side publish moved.

.PARAMETER Config
  Base URL of the Spring Cloud Config server. Default http://127.0.0.1:8888.

.PARAMETER WorldCheck
  Base URL of the world-check service. Default http://127.0.0.1:8870. Pass a $null value to skip.

.PARAMETER JobsObserver
  Base URL of the jobs-observer service. Default http://127.0.0.1:8871. Pass a $null value to skip.

.PARAMETER OutFile
  Where the JSON witness lands. Default: .scratch/plane-walk.json (untracked by design —
  witnesses are run artifacts, not source).

.EXAMPLE
  pwsh -File services/plane-walk.ps1

.EXAMPLE
  pwsh -File services/plane-walk.ps1 -Edge http://127.0.0.1:18080 -OutFile $env:TEMP\plane-walk.json
#>
[CmdletBinding()]
param(
  [string]$Edge     = 'http://127.0.0.1:18080',
  [string]$Core     = 'http://127.0.0.1:8100',
  [string]$Registry = 'http://127.0.0.1:18760',
  [string]$Config   = 'http://127.0.0.1:8888',
  [string]$WorldCheck = 'http://127.0.0.1:8870',
  [string]$JobsObserver = 'http://127.0.0.1:8871',
  [string]$OutFile  = '.scratch\plane-walk.json'
)

$ErrorActionPreference = 'Stop'
$checks = [ordered]@{}

function Get-Body($uri, $headers = @{}) {
  $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 15 -Headers $headers
  return @{ status = [int]$response.StatusCode; body = $response.Content; headers = $response.Headers }
}

# 1. the routed health read arrives, and the edge mints an id for a caller that brought none
$health = Get-Body "$Edge/api/v1/healthz"
$trace = $health.headers['X-Trace-Id']
$checks['health_through_edge_200'] = ($health.status -eq 200)
$checks['health_body_is_the_cores'] = ($health.body -match '"status":"ok"')
$checks['trace_minted'] = [bool]($trace -and $trace.Count -ge 1)

# 2. an id the caller supplied is the id that comes back
$supplied = 'plane-walk-0001'
$traced = Get-Body "$Edge/api/v1/healthz" @{ 'X-Trace-Id' = $supplied }
$checks['trace_supplied_echoed'] = ($traced.headers['X-Trace-Id'] -eq $supplied)

# 3. the gateway is transparent: a data read is byte-identical to the core's own answer
$direct = Get-Body "$Core/api/v1/world/competitions"
$routed = Get-Body "$Edge/api/v1/world/competitions"
$checks['competitions_identical'] = ($direct.body -eq $routed.body)
$checks['competitions_have_rows'] = ($routed.body -match 'Ravhurst|Lyndera|Thornford')
$checks['competitions_content_length_matches'] = ($direct.body.Length -eq $routed.body.Length)

# 4. the route table is the running gateway's, not the YAML's
$routes = (Get-Body "$Edge/edge/routes").body | ConvertFrom-Json
$coreRoute = $routes | Where-Object { $_.id -eq 'core-api' } | Select-Object -First 1
$webRoute = $routes | Where-Object { $_.id -eq 'web' } | Select-Object -First 1
$checks['two_routes'] = ($routes.Count -eq 2)
$checks['route_id'] = ($null -ne $coreRoute)
$checks['web_route_present'] = ($null -ne $webRoute -and ("$($webRoute.uri)") -match 'localhost:3000|127\.0\.0\.1:3000')
$coreTarget = "$($coreRoute.uri)"
$checks['route_target_is_the_core'] = (($coreTarget -eq $Core) -or ($coreTarget -match '(?i)^https?://(host\.docker\.internal|127\.0\.0\.1|localhost|edge):8100$') -or ($coreTarget -eq 'lb://football-core'))
$checks['route_predicate'] = ($routes[0].predicates -join ' ') -match '/api/v1/\*\*'
$checks['route_filter'] = ($routes[0].filters -join ' ') -match 'CircuitBreaker'

# 5. the edge said so to the registry — per-app read (the wire truth on this host).
#    This dev registry's aggregate listing serves a FIXED document (one BACKEND instance) and
#    never surfaces peers that register correctly; the footprint of the aggregate is recorded
#    as information, not as a gate. The per-app document is the read that reflects live state.
$agg = (Invoke-WebRequest -Uri "$Registry/eureka/apps" -UseBasicParsing -TimeoutSec 15 -Headers @{ Accept = 'application/json' }).Content | ConvertFrom-Json
$aggNames = @($agg.applications.application | ForEach-Object { $_.name })

$edgeDoc = $null
try { $edgeDoc = (Invoke-WebRequest -Uri "$Registry/eureka/apps/FOOTBALL-EDGE" -UseBasicParsing -TimeoutSec 15 -Headers @{ Accept = 'application/json' }).Content | ConvertFrom-Json } catch {}
$checks['edge_registered'] = ($null -ne $edgeDoc)
$checks['edge_instance_up'] = ($null -ne $edgeDoc -and (@($edgeDoc.application.instance | Select-Object -ExpandProperty status) -contains 'UP'))

# 6. the config server serves the edge's route, from the file in this repository
$served = (Get-Body "$Config/football-edge/default").body | ConvertFrom-Json
$edgeSource = ($served.propertySources | Where-Object { $_.name -match 'football-edge' } | Select-Object -First 1).source
$checks['config_serves_core_api_route'] = ($edgeSource.'spring.cloud.gateway.server.webflux.routes[0].id' -eq 'core-api')
$checks['config_serves_fallback'] = ("$($edgeSource.'spring.cloud.gateway.server.webflux.routes[0].filters[0].args.fallbackUri')" -eq 'forward:/edge/fallback')

# 7. the fourth citizen speaks arithmetic only: live check + eureka registration + config serving
if ($WorldCheck -ne '') {
  try {
    $wc = Get-Body "$WorldCheck/world/check" -Headers @{ 'Accept' = 'application/json' }
    $checks['worldcheck_live_200'] = ($wc.status -eq 200)
    $checks['worldcheck_has_invariants'] = ($wc.body -match '"invariants"')
    $checks['worldcheck_invariants_aligned'] = ($wc.body -match '"world_aligned":\s*true')
  } catch {
    $checks['worldcheck_live_200'] = $false
    $checks['worldcheck_has_invariants'] = $false
    $checks['worldcheck_invariants_aligned'] = $false
  }

  $wcDoc = $null
  try { $wcDoc = (Invoke-WebRequest -Uri "$Registry/eureka/apps/FOOTBALL-WORLDCHECK" -UseBasicParsing -TimeoutSec 15 -Headers @{ Accept = 'application/json' }).Content | ConvertFrom-Json } catch {}
  $checks['worldcheck_registered'] = ($null -ne $wcDoc)

  try {
    $wcServed = (Get-Body "$Config/football-worldcheck/default").body | ConvertFrom-Json
    $wcSource = ($wcServed.propertySources | Where-Object { $_.name -match 'football-worldcheck' } | Select-Object -First 1).source
    $checks['config_serves_worldcheck_min_competitions'] = ($wcSource.'worldcheck.min.competitions' -eq '10')
  } catch {
    $checks['config_serves_worldcheck_min_competitions'] = $false
  }
}

# 7b. the fifth citizen speaks arithmetic only: live ledger + eureka registration + config serving
if ($JobsObserver -ne '') {
  try {
    $jo = Get-Body "$JobsObserver/jobs/observer" -Headers @{ 'Accept' = 'application/json' }
    $checks['jobsobserver_live_200'] = ($jo.status -eq 200)
    $checks['jobsobserver_has_ledger'] = ($jo.body -match '"total_observed"')
    $checks['jobsobserver_connection_present'] = ($jo.body -match '"connection"')
  } catch {
    $checks['jobsobserver_live_200'] = $false
    $checks['jobsobserver_has_ledger'] = $false
    $checks['jobsobserver_connection_present'] = $false
  }

  $joDoc = $null
  try { $joDoc = (Invoke-WebRequest -Uri "$Registry/eureka/apps/FOOTBALL-JOBS-OBSERVER" -UseBasicParsing -TimeoutSec 15 -Headers @{ Accept = 'application/json' }).Content | ConvertFrom-Json } catch {}
  $checks['jobsobserver_registered'] = ($null -ne $joDoc)

  try {
    $joServed = (Get-Body "$Config/football-jobs-observer/default").body | ConvertFrom-Json
    $joSource = ($joServed.propertySources | Where-Object { $_.name -match 'football-jobs-observer' } | Select-Object -First 1).source
    $checks['config_serves_jobsobserver_group'] = ($joSource.'jobsobserver.group' -eq 'football_os:jobs:observers')
  } catch {
    $checks['config_serves_jobsobserver_group'] = $false
  }
}

$result = [ordered]@{
  at = (Get-Date).ToString('o')
  edge = $Edge
  core = $Core
  registry = $Registry
  config = $Config
  worldcheck = $WorldCheck
  jobsobserver = $JobsObserver
  aggregate_apps_seen = ($aggNames -join ',')
  checks = $checks
  passed = (@($checks.Values | Where-Object { $_ -ne $true }).Count -eq 0)
  count = $checks.Count
}
$outDir = Split-Path -Parent $OutFile
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
$result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $OutFile -Encoding utf8
if (-not $result.passed) { $result | ConvertTo-Json -Depth 5; exit 1 }
Write-Output "PLANE WALK OK $($result.count)/$($result.count) (witness -> $OutFile)"
