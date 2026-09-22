#!/bin/bash
# Serve the CURRENT production build on the throwaway verification port, prove the browser will be
# talking to it, run the visual QA walk, then release the port.
#
# Why the proving step exists: a `next start` left over from an earlier run keeps owning the port,
# the new one dies on EADDRINUSE, and the walk silently drives the stale build — which shows up only
# as HTTP 400s for /_next/static/chunks/*.js after the build directory was rebuilt.
#
#   apps/web/scripts/verify-production.sh            # build + serve + QA
#   SKIP_BUILD=1 apps/web/scripts/verify-production.sh   # reuse .next-ci as-is
set -u

PORT="${QA_PORT:-3211}"
WEB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WEB_DIR" || exit 1

release_port() {
  powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction SilentlyContinue | ForEach-Object { \$p = Get-CimInstance Win32_Process -Filter \"ProcessId=\$(\$_.OwningProcess)\"; if (\$p.CommandLine -match 'next.*start -p $PORT') { Write-Output ('release ' + \$p.ProcessId); Stop-Process -Id \$p.ProcessId -Force } }"
}

if [ "${SKIP_BUILD:-}" != "1" ]; then
  npx tsc --noEmit || exit 1
  npm run lint || exit 1
  NEXT_DIST_DIR=.next-ci SITE_URL="http://127.0.0.1:$PORT" npx next build || exit 1
fi

release_port
sleep 2
NEXT_DIST_DIR=.next-ci SITE_URL="http://127.0.0.1:$PORT" node node_modules/next/dist/bin/next start -p "$PORT" > /tmp/next-$PORT.log 2>&1 &

# The wait loop polls the one fact the walk depends on, not a health endpoint: /healthz is an app route
# that proxies the API, so it can answer 500 while the server is perfectly fine, and the walk needs
# instead to see the webpack chunk of THIS build in the HTML of a rendered page.
ON_DISK=$(ls .next-ci/static/chunks/ 2>/dev/null | grep '^webpack-.*\.js$' | head -1)
SERVED=""
CODE=000
for _ in $(seq 1 60); do
  BODY=$(curl -s -w '\n%{http_code}' "http://127.0.0.1:$PORT/world")
  CODE=$(printf '%s\n' "$BODY" | tail -1)
  SERVED=$(printf '%s\n' "$BODY" | grep -o 'webpack-[a-f0-9]*\.js' | head -1)
  [ -n "$ON_DISK" ] && [ "$SERVED" = "$ON_DISK" ] && break
  sleep 1
done

echo "served chunk: ${SERVED:-none} (HTTP $CODE) · build chunk: ${ON_DISK:-missing}"
if [ -z "$SERVED" ] || [ "$SERVED" != "$ON_DISK" ]; then
  echo "ABORT: port $PORT is not serving the build in .next-ci"
  tail -5 "/tmp/next-$PORT.log"
  release_port
  exit 3
fi

QA_BASE="http://127.0.0.1:$PORT" node scripts/visual-qa.mjs
QA_EXIT=$?
release_port
exit $QA_EXIT
