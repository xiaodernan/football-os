/**
 * §74's web half, gated: the shipped reader is fed the answers the shipped API produces.
 *
 * Nothing asserted `normalizeError` before this file. That function is *why* the handlers' second shape
 * stayed invisible for as long as it did — it looks for `payload.detail`, and a `{"error": {…}}` answer gave
 * it no code, no message and no field list, so the page printed its own fallback string while the API had
 * already written a sentence naming the box and the rule.
 *
 * How this is a gate and not a rehearsal of the source:
 *   - the module under test is `lib/api.ts`'s own bytes, transpiled by this repo's TypeScript and imported;
 *     the export list is parsed out of that same text and compared with what the import yielded, so "the
 *     reader was loaded" cannot mean "some reader was loaded";
 *   - the payloads come from `fixtures/refusals.json`, and every one of the handler/door entries is checked
 *     against the API tree by `apps/api/tests/test_error_answer_shape.py` — this file never claims a body is
 *     something the backend answers;
 *   - what the reader must yield is *derived* from the payload for those entries (code, message, the key
 *     names beside them), not written beside them. Only the four reader-tolerance entries carry an `expect`,
 *     because there is no backend source for those.
 *
 *   node scripts/qa-error-shape.mjs
 *   TS_ENTRY=<path to typescript.js> node scripts/qa-error-shape.mjs   # when run from a `git archive` plane
 *
 * Env overrides: TS_ENTRY, API_TS (a different lib/api.ts to load — used by nothing but an arm).
 */

import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = resolve(HERE, '..');
const API_TS_PATH = process.env.API_TS ?? resolve(WEB_ROOT, 'lib', 'api.ts');
const FIXTURE_PATH = resolve(WEB_ROOT, 'fixtures', 'refusals.json');

const results = [];
function check(name, ok, detail = '') {
  results.push({ name, ok });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${String(detail).slice(0, 200)}` : ''}`);
}

async function loadReader() {
  const require_ = createRequire(import.meta.url);
  const tsPath = process.env.TS_ENTRY ?? require_.resolve('typescript');
  const ts = (await import(pathToFileURL(tsPath).href)).default;
  const source = readFileSync(API_TS_PATH, 'utf8');
  // The claim §74 is about, pinned in the text before anything is imported: the reader unwraps a `detail` key.
  // (It spells that as `"detail" in payload ? payload.detail : payload` — an earlier version of this line
  // searched for `payload.detail` and went red on correct production code, which is a broken witness, not a bug.)
  check('the file under test unwraps a `detail` key from the payload', source.includes('"detail" in payload'), API_TS_PATH);
  check('the file under test declares normalizeError', /function normalizeError\(/.test(source), '');
  const js = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.ESNext, isolatedModules: true },
  }).outputText;
  const module = await import(`data:text/javascript;base64,${Buffer.from(js, 'utf8').toString('base64')}`);
  // Identity: the value exports the text declares must be exactly what the import handed back.
  const declared = source
    .split('\n')
    .map((line) => /^export (?:async )?(?:function|const) (\w+)/.exec(line)?.[1])
    .filter((name) => name !== undefined);
  const exported = Object.keys(module).filter((key) => typeof module[key] !== 'undefined').sort();
  const missing = declared.filter((name) => !exported.includes(name));
  const unexpected = exported.filter((name) => !declared.includes(name) && name !== 'default');
  check(
    `the imported module is the file that was read (${declared.length} declared value exports)`,
    declared.length >= 5 && missing.length === 0 && unexpected.length === 0,
    `declared=${declared.join(',')} loaded=${exported.join(',')}`,
  );
  return module;
}

function responseFor(entry) {
  const body = entry.body;
  const text = body.content_type === 'application/json' ? JSON.stringify(body.json) : body.text;
  return new Response(text, { status: entry.status, headers: { 'content-type': body.content_type } });
}

async function main() {
  const reader = await loadReader();
  if (typeof reader.browserFetch !== 'function') {
    check('browserFetch is callable', false, 'the reader did not export browserFetch — every case below would be vacuous');
    return finish();
  }
  const fixtures = JSON.parse(readFileSync(FIXTURE_PATH, 'utf8'));
  const entries = fixtures.entries ?? [];
  const produced = entries.filter((entry) => entry.producer.kind === 'handler' || entry.producer.kind === 'door');
  const tolerant = entries.filter((entry) => entry.producer.kind === 'reader-tolerance');
  // Floors from the same parsed list, so an emptied fixture file cannot read as "nothing to check".
  check(`the fixture population is real (${entries.length} entries, ${produced.length} from this API, ${tolerant.length} tolerances)`,
    entries.length >= 8 && produced.length >= 6 && tolerant.length <= 5, '');

  for (const entry of entries) {
    globalThis.fetch = async () => responseFor(entry);
    const result = await reader.browserFetch('/shape-probe');
    const error = result?.error ?? {};
    check(`${entry.name}: the call is reported as a refusal at ${entry.status}`, result?.ok === false && result?.status === entry.status, JSON.stringify(result).slice(0, 160));
    // An answer the API named carries its sentence; the tier's own generic answer does not, because
    // the reader's sentence is the call site's fallback and the localiser fills the rest.
    const named = entry.producer.kind === 'handler' || entry.producer.kind === 'door';
    check(`${entry.name}: a code is always present${named ? ', and a message when the API named one' : ''}`,
      typeof error.code === 'string' && error.code.length > 0 && (!named || (typeof error.message === 'string' && error.message.length > 0)),
      JSON.stringify(error));

    if (named) {
      const detail = entry.body.json.detail;
      const figures = Object.keys(detail).filter((key) => key !== 'code' && key !== 'message');
      check(`${entry.name}: the code the API spelled is the code the page is given`, error.code === detail.code, `got ${JSON.stringify(error.code)}`);
      check(`${entry.name}: the API's own sentence is what the page prints`, error.message === detail.message, `got ${JSON.stringify(error.message)}`);
      check(`${entry.name}: the reader never falls back on an answer that named itself`, error.code !== 'error' && error.message !== 'Request failed', JSON.stringify(error));
      if (figures.length > 0) {
        const isList = Array.isArray(error.details);
        const carried = isList ? null : Object.keys(error.details ?? {});
        // `key in array` tests indices, so the object case has to ask the key list. An earlier version used
        // `in`, went red on a reader that was carrying the figures correctly, and proved nothing either way.
        const kept = isList
          ? JSON.stringify(error.details) === JSON.stringify(detail[figures[0]])
          : figures.every((key) => carried.includes(key));
        check(`${entry.name}: the figures beside the sentence survive the trip (${figures.join(',')})`, kept, JSON.stringify(error.details));
      }
    } else {
      for (const [field, expected] of Object.entries(entry.expect)) {
        if (field === 'figure_keys') {
          const carried = Array.isArray(error.details) ? error.details : Object.keys(error.details ?? {});
          check(`${entry.name}: figures carried as ${expected.join(',')}`, expected.every((key) => carried.includes(key)), JSON.stringify(error.details));
        } else {
          check(`${entry.name}: ${field} is ${JSON.stringify(expected)}`, error[field] === expected, `got ${JSON.stringify(error[field])}`);
        }
      }
    }
  }

  // One case cannot be reached from a fixture: a transport failure, where fetch itself rejects.
  globalThis.fetch = async () => {
    throw new TypeError('connection refused');
  };
  const offline = await reader.browserFetch('/shape-probe');
  // The tier's own answers carry a code and no sentence: the reader's sentence is the call site's
  // fallback, and the localiser fills the rest on the paths that can read the catalogue.
  check('a refusal to connect answers network_error', offline?.ok === false && offline?.status === 502
    && offline?.error?.code === 'network_error', JSON.stringify(offline));

  return finish();
}

function finish() {
  const failed = results.filter((row) => !row.ok);
  console.log(`CHECKS passed=${results.length - failed.length} total=${results.length} failed=${failed.length}`);
  if (failed.length > 0) console.log('FAILED: ' + failed.map((row) => row.name).join(' | '));
  return failed.length === 0 ? 0 : 1;
}

process.exitCode = await main();
