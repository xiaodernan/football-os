#!/usr/bin/env node
/*
 * A gateway's three doors, on demand, with numbers that never move.
 *
 * The service plane page (`app/plane/page.tsx`) reads `/edge/lb`, `/edge/breaker` and `/edge/limits` from
 * whatever `EDGE_URL` the web server was started with. The page is the thing under test here, not the edge:
 * the edge has its own 66-test suite and answers with whatever the load really did a moment ago, which is
 * fine for looking at and useless for asserting on. So the walk gets a fixture instead — one that can be
 * told to answer, to answer badly, or to stop answering, and whose numbers are chosen so that a wrong
 * rendering is visible rather than merely different.
 *
 * The numbers are not arbitrary:
 *
 *   * `10.0.0.11:8080` answered 4 s ago at 12.5 ms. Inside the 30 s window, so its score **is** its average
 *     and it must carry no decay mark.
 *   * `10.0.0.12:8080` answered 143 s ago. Past the window, so its score has faded to the 60 ms target while
 *     its average stays 240.5 ms — the two numbers must disagree here, on purpose, because they are two
 *     different facts. This row is the whole reason the console was rebuilt: on a live edge those two columns
 *     disagreed by 200 ms and nothing on the page said why.
 *   * With a 30 s window and a 60 ms target in the payload, the page must print those *from the payload*. A
 *     page that hardcoded its own defaults would pass on this fixture and describe a gateway nobody deployed.
 *
 * Modes, switched over HTTP so the walk can drive them against a web tier it did not start:
 *
 *   GET  /control/mode          → {mode}
 *   POST /control/mode/up       → all three doors answer, breaker CLOSED, nothing degraded
 *   POST /control/mode/degraded → breaker OPEN, three distributed degradations, half the traffic refused
 *   POST /control/mode/down     → all three doors answer 503, the way an edge that is gone does
 *
 * Usage:
 *
 *   node scripts/edge-stub.mjs                       # 127.0.0.1:8799
 *   node scripts/edge-stub.mjs 8811                  # another port
 *   EDGE_STUB_PORT=8811 node scripts/edge-stub.mjs
 *
 * It prints `edge-stub listening on ...` once, and one line per mode change, so a run that quietly failed to
 * bind is visible in the log rather than as a page that says "unreachable" for no stated reason.
 */

import { createServer } from 'node:http';

const PORT = Number(process.argv[2] ?? process.env.EDGE_STUB_PORT ?? 8799);
const HOST = '127.0.0.1';

/** The two instances, and the one fact about each that matters: how old its last answer is. */
const FRESH = {
  score: 12.5,
  ewmaMillis: 12.5,
  failStreak: 0,
  observations: 412,
  failures: 0,
  lastMillis: 12.5,
  ageMillis: 4_000,
};
const AGED = {
  score: 60,
  ewmaMillis: 240.5,
  failStreak: 0,
  observations: 390,
  failures: 2,
  lastMillis: 240.5,
  ageMillis: 143_000,
};

/** The window and the target the page must read out of the payload rather than assume. */
const TARGET_MS = 60;
const STALE_AFTER_MS = 30_000;

const BREAKER = (state, overrides = {}) => ({
  name: 'coreBreaker',
  present: true,
  state,
  slidingWindowSize: 10,
  failureRateThreshold: 50,
  minimumNumberOfCalls: 8,
  permittedCallsInHalfOpenState: 3,
  bufferedCalls: 10,
  failedCalls: state === 'OPEN' ? 7 : 0,
  successfulCalls: state === 'OPEN' ? 3 : 10,
  notPermittedCalls: state === 'OPEN' ? 21 : 0,
  failureRate: state === 'OPEN' ? 70 : 0,
  ...overrides,
});

const LIMITS = (overrides = {}) => ({
  enabled: true,
  requestsPerSecond: 50,
  burst: 100,
  trackedClients: 7,
  distributed: true,
  distributedChecks: 1_284,
  distributedDegradations: 0,
  ...overrides,
});

/**
 * The three answers per mode. `down` answers 503 rather than refusing the connection: a connection refusal
 * and a 503 are the same answer to the page (`readEdge` treats any non-2xx as nothing), and a 503 keeps it
 * one fixture instead of two.
 */
const MODES = {
  up: {
    status: 200,
    body: {
      '/edge/lb': {
        strategy: 'p2c',
        targetMillis: TARGET_MS,
        staleAfterMillis: STALE_AFTER_MS,
        instances: { '10.0.0.11:8080': FRESH, '10.0.0.12:8080': AGED },
      },
      '/edge/breaker': BREAKER('CLOSED'),
      '/edge/limits': LIMITS(),
    },
  },
  degraded: {
    status: 200,
    body: {
      '/edge/lb': {
        strategy: 'p2c',
        targetMillis: TARGET_MS,
        staleAfterMillis: STALE_AFTER_MS,
        instances: { '10.0.0.11:8080': FRESH, '10.0.0.12:8080': AGED },
      },
      '/edge/breaker': BREAKER('OPEN'),
      '/edge/limits': LIMITS({ distributedDegradations: 3 }),
    },
  },
  down: { status: 503, body: {} },
};

let mode = 'up';

const json = (response, status, body) => {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'content-length': Buffer.byteLength(payload),
  });
  response.end(payload);
};

const server = createServer((request, response) => {
  const path = new URL(request.url, `http://${HOST}:${PORT}`).pathname;

  if (path === '/control/mode') {
    return json(response, 200, { mode, modes: Object.keys(MODES) });
  }
  const control = path.match(/^\/control\/mode\/([a-z]+)$/u);
  if (control) {
    if (!MODES[control[1]]) return json(response, 400, { error: `no mode ${control[1]}`, modes: Object.keys(MODES) });
    mode = control[1];
    console.log(`edge-stub: mode ${mode}`);
    return json(response, 200, { mode });
  }

  const table = MODES[mode];
  if (table.status !== 200) return json(response, table.status, { error: 'the edge is gone' });
  const answer = table.body[path];
  if (!answer) return json(response, 404, { error: `no door ${path}` });
  return json(response, 200, answer);
});

server.on('error', (error) => {
  console.error(`edge-stub: ${error.code ?? error.message} on ${HOST}:${PORT}`);
  process.exit(1);
});

server.listen(PORT, HOST, () => {
  console.log(`edge-stub listening on http://${HOST}:${PORT} (mode ${mode})`);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => server.close(() => process.exit(0)));
}
