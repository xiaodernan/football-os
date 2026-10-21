#!/usr/bin/env node
/*
§81 2c, continued — the count of copy the catalogues do not carry, and a ceiling that may only fall.

The arc's own record is a set of numbers measured at named refs: "A 24 sites, B 168, C 40 — 231 distinct
sites", "the union fell by 14 for 15 wired attributes". A number nobody recomputes is a number nobody
notices falling, and a number that is not gated is a number a new page can raise without anybody saying
so. This file is the gate for that: it walks every `.tsx` under `app/`, finds the copy that is written in
English in the source, and refuses a total above the committed floor.

What it counts, and why each shape is a shape:

* **JSX text** — `>No round played yet<`. The copy the reader sees, standing between two tags.
* **A label-ish attribute** — `title="…"`, `label="…"`, `placeholder="…"`, `aria-label="…"`, and the
  rest of the set a page uses to hand copy to a component. These are the shape a JSX-text scan cannot
  see, because the copy is an argument, not a child.
* **A label-ish object property** — `metadata = { title: "…" }`, `back={{ label: "…" }}`. The fourth
  shape the arc found: a copy inside an object literal, which neither a JSX-text scan nor an attribute
  scan reaches.
* **A string literal that reaches the reader from anywhere else** — a sentence a helper returns, a
  wording a ternary chooses, a note a component builds. The fifth shape, found on 2026-10-21: the scout's
  compare panel prints "A AHEAD" from a helper, so the first three shapes never saw it, and the ceiling
  of zero they reported was true of the three shapes and false of the tree. It has its own floor below,
  because the first floor is a statement about those three shapes and this one is a statement about the
  rest of the source.

What it does not count, because a copy that is not copy is not a finding: class names, hrefs, ids, type
attributes, keys, URLs, paths, camelCase identifiers, `ALL_CAPS` constants, and the technical acronyms a
page prints as itself (RPE, HTTP, xG, API). The allowlist is short and its members are named. The fifth
shape's exclusions are *structural* rather than a list of words — an import specifier, a naming
attribute, a class name held in a variable, a comparison operand, a schema.org type or field, a
snake_case property, a language tag, the framework's own directive, a CSS custom property — so a new
class name or a new API field does not have to be added to an allowlist to keep the gate quiet.

The floor only falls. A slice that wires a page to its catalogue lowers it; a page that adds copy in
English raises the count, and the gate says so. The floor is this file's own `FLOOR_SITES` constant, and
the message names the file and line of every site it found, so the work is a list and not a hunt. The
fifth shape has its own floor, `FLOOR_LITERAL_SITES`, and the same rule: it may only fall.

Files only: no server, no browser, no port — which is why it belongs with the other file-only gates in
`scripts/check.sh` and in CI, and why the script-inventory gate requires a runner to name it.
*/

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { createRequire as createRequireForJson } from "node:module";
import { join, resolve, sep } from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const APP = join(WEB, "app");
/**
 * The components directory carries copy too, and a page is only as localised as the components it
 * renders: `components/CreatorWorkbench.tsx` holds the tier's own buttons and sentences, and no scan
 * of `app/` could see them. The population is therefore both directories.
 */
const COMPONENTS = join(WEB, "components");

/** The committed ceiling on English literal sites. i18n work lowers it; nothing else may. */
/**
 * The ceiling on English literal sites over the whole population: every `.tsx` under `app/` and
 * every `.tsx` under `components/`. A page is only as localised as the components it renders, and
 * the components hold copy — the workbench's buttons, the club and academy tools' sentences, the
 * scout panels' headings. A scan of `app/` alone could not see any of it.
 *
 * It may only fall.
 */
const FLOOR_SITES = 0;

/**
 * The floor on the fourth shape — a string literal that reaches the reader from somewhere the three
 * shapes above do not cover. It starts at the count the gate read when it learned to see the shape,
 * and it may only fall: every site that moves into a catalogue lowers it.
 */
const FLOOR_LITERAL_SITES = 0;

/** The population the walk must find, so a scan that narrows itself cannot pass by finding nothing. */
const FLOOR_FILES = 70;

/** Attributes whose string value is copy the reader sees. */
const LABEL_ATTRIBUTES = new Set([
  "alt", "aria-label", "description", "empty", "error", "eyebrow", "heading", "label",
  "lede", "note", "placeholder", "subtitle", "title",
]);

/** Object-literal properties whose string value is copy the reader sees. */
const LABEL_PROPERTIES = new Set([
  "description", "empty", "error", "eyebrow", "heading", "label", "lede", "subtitle", "title",
]);

/**
 * Words a page prints as themselves: a rating scale, a protocol, a file format, a product name.
 * Short and closed — every member is a thing the product prints in English on purpose.
 */
/**
 * Values that are not copy, and the reason each one is not.
 *
 * A field name is not copy. `data_origin: synthetic` is the provenance envelope the API prints, and
 * translating it would break the one string an operator greps for; the same holds for the cap names
 * `max_depth` / `max_edges` / `max_nodes`, the parameter `identity_retained=`, the example address
 * `you@example.com`, the export file name, and the product's own name.
 */
const TECHNICAL_PATTERNS = [
  /^data_origin\b/,
  /^is_demo_data\b/,
  /^(max_depth|max_edges|max_nodes)\b/,
  /^identity_retained=/,
  // A field's own name, printed as itself: `role_fit: null` is the API saying that the field is
  // null, and translating the field's name would break the one string an operator greps for.
  /^role_fit:/,
  /^team_fit:/,
  /^comparison:/,
  /^you@example\.com$/,
  /^footballos-export\.json$/,
  /^FOOTBALL OS$/,
];

const TECHNICAL = new Set([
  "AI", "API", "CV", "DRI", "FM", "GB", "GPS", "HTML", "HTTP", "ID", "JSON", "MB", "MVP", "PDF",
  "PM", "RPE", "SQL", "TBD", "URL", "UTC", "U19", "U21", "VS", "X", "XGD", "xG", "xT",
]);

/**
 * The catalogue the keys are checked against. The English file is the one that must hold every key:
 * a locale may lag, but the fallback must not, or a page renders an error instead of a sentence.
 */
const CATALOGUE = JSON.parse(readFileSync(join(WEB, "messages", "en.json"), "utf8"));

const files = [];
const walk = (dir) => {
  if (!existsSync(dir)) return;
  for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) walk(p);
    else if (entry.name.endsWith(".tsx")) files.push(p);
  }
};
walk(APP);
walk(COMPONENTS);

const relOf = (p) => p.slice(WEB.length + 1).split(sep).join("/");

/**
 * Whether a string is copy in English.
 *
 * The test is deliberately conservative: a value that could be a key, a path, an identifier or a
 * technical word is not a finding, because a gate that cries wolf gets switched off.
 */
const isEnglishCopy = (value) => {
  const text = value.trim();
  if (!text || text.length < 2) return false;
  if (text.includes("{") || text.includes("}") || text.includes("<")) return false;
  if (/^https?:\/\//i.test(text) || text.startsWith("/")) return false;
  if (/^[a-z0-9-]+$/.test(text)) return false; // kebab-case, or a key
  if (/^[A-Z0-9_]+$/.test(text)) return false; // a constant
  if (/^[a-z][A-Za-z0-9_]*$/.test(text)) return false; // an identifier: a key, a field name, an enum value
  if (/^[a-z]+[A-Z]/.test(text)) return false; // camelCase identifier
  if (/[^\x00-\x7F]/.test(text)) return false; // already translated
  if (TECHNICAL_PATTERNS.some((pattern) => pattern.test(text))) return false; // a field name, not copy
  const words = text.match(/[A-Za-z][A-Za-z'’-]*/g) ?? [];
  if (words.length === 0) return false;
  if (words.length === 1) {
    const only = words[0];
    // A single capitalised word is copy ("Players", "Close"); a lowercase one is usually a value.
    if (!/^[A-Z]/.test(only)) return false;
    if (TECHNICAL.has(only)) return false;
    return only.length > 2;
  }
  // Two or more words: it is a sentence unless every word is technical.
  return !words.every((word) => TECHNICAL.has(word));
};

/**
 * Whether a string literal is a *token* rather than copy.
 *
 * A token is a name, a class, a field the tier owns, a technical value — something the reader never
 * reads as a sentence. Every rule here is structural rather than a list of words, so a new class name
 * or a new API field does not have to be added to an allowlist to keep the gate quiet:
 *
 *  * an import or export specifier — a module's name;
 *  * a naming attribute, a class name (written in an expression or held in a variable), a style — a
 *    name, not a sentence;
 *  * a comparison operand — the tier's own enum value, which the page quotes rather than writes;
 *  * a schema.org type or field, and a schema.org vocabulary value — the language of a JSON-LD block;
 *  * a snake_case property — a field the API owns, printed as itself;
 *  * a language tag, the framework's own directive, a CSS custom property, a colour, a measurement — tokens;
 *  * a locale's own name — the switcher writes "English" and "简体中文" on purpose;
 *  * a marker that matches the tier's own wording — `line.startsWith("not in this build")` matches the
 *    API's sentence rather than writing one.
 */
const literalIsToken = (node, parent) => {
  const literal = node.text.trim();
  if (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent)) return true;
  if (ts.isJsxExpression(parent) && parent.expression === node) return true;
  if (ts.isJsxAttribute(parent) && parent.initializer === node) {
    const name = parent.name.getText();
    if (NAMING_ATTRIBUTES.has(name) || name === "className" || name === "style") return true;
    // A `data-` attribute is a hook the page and its tests read, not copy a reader sees.
    if (name.startsWith("data-")) return true;
  }
  const comparison =
    ts.isBinaryExpression(parent) &&
    (parent.operatorToken.kind === ts.SyntaxKind.EqualsEqualsToken ||
      parent.operatorToken.kind === ts.SyntaxKind.EqualsEqualsEqualsToken ||
      parent.operatorToken.kind === ts.SyntaxKind.ExclamationEqualsEqualsToken);
  if (comparison) return true;
  const schemaType =
    ts.isPropertyAssignment(parent) &&
    ((ts.isIdentifier(parent.name) && parent.name.text === "type") ||
      (ts.isStringLiteral(parent.name) && parent.name.text === "@type"));
  if (schemaType) return true;
  if (ts.isPropertyAssignment(parent) && ts.isStringLiteral(parent.name) && /^[a-z]+(-[a-z]+)+$/.test(parent.name.text)) return true;
  if (ts.isPropertyAssignment(parent) && ts.isIdentifier(parent.name) && SCHEMA_VOCABULARY.has(parent.name.text)) return true;
  if (
    ts.isPropertyAssignment(parent) &&
    ((ts.isIdentifier(parent.name) && isApiFieldName(parent.name.text)) ||
      (ts.isStringLiteral(parent.name) && isApiFieldName(parent.name.text)))
  ) {
    return true;
  }
  if (ts.isPropertyAssignment(parent) && ts.isIdentifier(parent.name) && /^(en|zh)(-TW)?$/.test(parent.name.text)) return true;
  const matchMarker =
    ts.isCallExpression(parent) &&
    ts.isPropertyAccessExpression(parent.expression) &&
    ["startsWith", "endsWith", "includes", "match"].includes(parent.expression.name.text);
  if (matchMarker) return true;
  if (literal === "use client" || literal.startsWith("var(--")) return true;
  if (/^url\(/.test(literal)) return true;
  if (/^[a-z]{2}(-[A-Za-z0-9]{2,8})+$/.test(literal)) return true;
  if (/^#[0-9a-f]{3,8}$/i.test(literal)) return true;
  if (/^\d+(\.\d+)?\s?[A-Za-z%]+$/.test(literal)) return true;
  for (let up = parent; up; up = up.parent) {
    if (ts.isJsxAttribute(up) && (up.name.getText() === "className" || up.name.getText() === "style")) return true;
    if (ts.isVariableDeclaration(up) && ts.isIdentifier(up.name) && /classname$/i.test(up.name.text)) return true;
    if (ts.isFunctionLike(up)) break;
  }
  return false;
};

/**
 * Whether a template is a token rather than a sentence: it sits in a class name, a style or a naming
 * attribute, or every one of its parts is technical — a query parameter, a date format, a unit.
 */
const templateIsToken = (node, parts) => {
  for (let up = node.parent; up; up = up.parent) {
    if (ts.isJsxAttribute(up)) {
      const name = up.name.getText();
      if (NAMING_ATTRIBUTES.has(name) || name === "className" || name === "style") return true;
    }
    if (ts.isVariableDeclaration(up) && ts.isIdentifier(up.name) && /classname$/i.test(up.name.text)) return true;
    if (ts.isFunctionLike(up)) break;
  }
  return parts
    .map((part) => part.text.trim())
    .filter((text) => text.length > 0)
    .every((text) => {
      const bare = text.replace(/^[;,·\s]+/, "");
      return (
        /^[?&#]?[A-Za-z_][A-Za-z0-9_]*=/.test(bare) || // a name=value pair: a query parameter, a cookie
        /^\//.test(bare) || // a path
        /^url\(/.test(bare) || // an SVG reference
        /^\d{4}-\d{2}-\d{2}T/.test(bare) || // a date format
        /^T\d{2}:\d{2}:\d{2}Z?$/.test(bare) || // a time format
        /^\d+(\.\d+)?\s?[A-Za-z%]+$/.test(bare) || // a measurement
        /^[KMGT]i?B$/.test(bare) || // a byte unit
        /^[a-z][A-Za-z0-9_]*:/.test(bare) // a field name
      );
    });
};

/**
 * The placeholders a message needs.
 *
 * ICU's own syntax is read the way next-intl reads it: `{name}` is a placeholder, `{name, plural, one
 * {…} other {…}}` is a placeholder whose *branches* are the literal words the reader sees — "reply" and
 * "replies" in `{comments, plural, one {reply} other {replies}}` are text, not values. A parser that
 * took the branch contents for placeholders would report a page as broken when it is not.
 */
const messagePlaceholders = (message) => {
  const found = [];
  let index = 0;
  while (index < message.length) {
    const open = message.indexOf("{", index);
    if (open === -1) break;
    let depth = 1;
    let close = open + 1;
    while (close < message.length && depth > 0) {
      if (message[close] === "{") depth += 1;
      else if (message[close] === "}") depth -= 1;
      close += 1;
    }
    const inner = message.slice(open + 1, close - 1);
    const comma = inner.indexOf(",");
    const name = (comma === -1 ? inner : inner.slice(0, comma)).trim();
    if (/^\w+$/.test(name)) found.push(name);
    index = close;
  }
  return [...new Set(found)];
};

/**
 * Whether a string literal reads like a **catalogue key** rather than a field the tier owns.
 *
 * The two kinds share a property: `labelKey: "attrFirstTouch"` is a key, while `key: "first_touch"` is the
 * API's own attribute name. The copy gate's heuristic cannot tell them apart — a key *is* an identifier,
 * and an identifier is exactly what that heuristic reads as "not copy" — so this rule says it plainly: a
 * snake_case value is a field, and a camelCase one (or a single capitalised word) is a key.
 */
const looksLikeKey = (value) => {
  const text = value.trim();
  if (!text) return false;
  if (/^[a-z][a-z0-9]*(_[a-z0-9]+)+$/.test(text)) return false; // a field the tier owns
  if (!/^[A-Za-z][A-Za-z0-9]*$/.test(text)) return false; // punctuation, a path, a sentence
  return /^[A-Z]/.test(text) || /[A-Z]/.test(text.slice(1)); // a key: camelCase, or a capitalised word
};

const sites = [];
/** The keys a page asks for by name — `t(link.key)` — which the key-existence check cannot read. */
const namedKeys = [];
/**
 * The fourth shape: a string literal that reaches the reader from somewhere the three shapes above do
 * not cover — a sentence a helper returns, a wording a ternary chooses, a note a component builds.
 *
 * The three shapes are where copy is *written*; this one is where copy is *assembled*, and the arc that
 * wired the interface to its catalogues found the difference the hard way: the scout's compare panel
 * prints "A AHEAD" from a helper, so no JSX text, no label attribute and no label property ever saw it,
 * and the ceiling of zero the three shapes report was true of the three shapes and false of the tree.
 */
const literalSites = [];
/** Per file: the namespaces it binds and the keys it asks for. */
const keyCalls = new Map();
/** Which namespace each translator variable reads — `const tb = useTranslations("tactics")`. */
const translatorNamespaces = new Map();
/** Key reads that left a placeholder of the message unsupplied. */
const missingValues = [];
let parsed = 0;
let diagnostics = 0;

/**
 * Attributes that *name* a thing rather than say it. A class, an id, a hook, a route: the reader never
 * sees them, so a literal in one is not copy.
 */
const NAMING_ATTRIBUTES = new Set([
  "className", "id", "name", "type", "key", "href", "src", "role", "method", "rel", "target",
  "autoComplete", "inputMode", "form", "slot", "lang", "dir", "width", "height", "viewBox", "d",
  "fill", "stroke", "xmlns", "colSpan", "rowSpan", "pattern", "accept", "encType", "formAction",
  "formMethod", "download", "sandbox", "srcDoc", "loading", "decoding", "referrerPolicy", "as",
  "data-testid", "data-note", "data-axis", "data-formula", "data-review", "data-slot",
]);

/**
 * A property whose name is a *field* the tier owns is not copy: `data_origin: "synthetic"` is the API
 * saying what it is, and a snake_case name is how this project spells those. A camelCase name is a
 * local, and a local's value is whatever the author wrote.
 */
const isApiFieldName = (name) => /^[a-z][a-z0-9]*(_[a-z0-9]+)+$/.test(name);

/**
 * The schema.org fields whose value is a *vocabulary* rather than a sentence: the sport a competition
 * belongs to, the kind of thing a page is about. They are named here rather than inferred, because a
 * value the crawler reads is metadata, and metadata is not the reader's copy.
 */
const SCHEMA_VOCABULARY = new Set(["sport", "genre"]);

/**
 * The units a page prints beside a figure. A unit is a measurement, not a sentence, and a unit is the
 * same word in every language — which is why it is named here rather than translated.
 */
const UNITS = new Set([
  "s", "ms", "m", "h", "km", "cm", "mm", "kg", "g", "k", "b", "n", "x", "y", "v", "sha", "xp",
  "min", "yrs", "yr", "mb", "kb", "gb", "tb", "mib", "gib", "tib", "sqm", "hz", "w", "kw",
]);

for (const file of files) {
  const text = readFileSync(file, "utf8");
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  if (source.parseDiagnostics?.length) diagnostics += source.parseDiagnostics.length;
  parsed += 1;
  const rel = relOf(file);
  const position = (node) => source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;

  translatorNamespaces.clear();
  const namespaces = new Set();
  const keys = new Set();
  /** The literal nodes the three shapes already counted, so the fourth shape does not count them twice. */
  const counted = new Set();

  const visit = (node) => {
    // Which namespace a translator variable reads: `const tb = useTranslations("tactics")`.
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      const initializer = ts.isAwaitExpression(node.initializer) ? node.initializer.expression : node.initializer;
      if (ts.isCallExpression(initializer) && ts.isIdentifier(initializer.expression)) {
        const callee = initializer.expression.text;
        const first = initializer.arguments[0];
        if ((callee === "useTranslations" || callee === "getTranslations") && ts.isStringLiteral(first)) {
          translatorNamespaces.set(node.name.text, first.text);
        }
      }
    }
    if (ts.isCallExpression(node) && node.arguments.length > 0) {
      const first = node.arguments[0];
      /**
       * A translator read, in both of its forms: `t("key")` and the rich-text form `t.rich("key")`.
       * Rich text is the same read of the same catalogue — next-intl throws MISSING_MESSAGE for a
       * rich key it does not hold, exactly as it does for a plain one — so a check that only saw the
       * identifier form would stop counting the moment a sentence needed a tag inside it.
       */
      const callee = ts.isIdentifier(node.expression)
        ? node.expression.text
        : ts.isPropertyAccessExpression(node.expression) &&
            ts.isIdentifier(node.expression.expression) &&
            node.expression.name.text === "rich"
          ? node.expression.expression.text
          : null;
      if ((callee === "useTranslations" || callee === "getTranslations") && ts.isStringLiteral(first)) {
        namespaces.add(first.text);
      } else if (callee && /^t[a-z]{0,2}$/.test(callee) && ts.isStringLiteral(first) && /^[A-Za-z0-9_]+$/.test(first.text)) {
        /**
         * The key is recorded **with the namespace it was asked of** — `tc("yes")` asks the `common`
         * namespace, not whichever namespace the file happens to bind. Checking the union of a file's
         * namespaces was too coarse: the plan page asked the `club` namespace for `yes` and `no` (which
         * live in `common`), the gate could not see it, and the page threw MISSING_MESSAGE at runtime.
         */
        const bound = translatorNamespaces.get(callee);
        keys.add(bound ? `${bound}.${first.text}` : first.text);
        /**
         * Every placeholder a message needs must be supplied with it. A key read without its values is
         * a message printed with its own placeholders in it — `{default} by default, {max} at most` in a
         * column that should say "Search limits" — and next-intl's own answer to a missing value is a
         * page that throws where it should read.
         */
        const namespace = translatorNamespaces.get(callee);
        const message = namespace ? CATALOGUE[namespace]?.[first.text] : undefined;
        if (typeof message === "string") {
          const needed = messagePlaceholders(message);
          if (needed.length > 0) {
            const supplied = new Set();
            const values = node.arguments[1];
            // A call whose values are not a literal object (a spread, a variable) is not judged here: the
            // gate cannot see what it passes, and a guess would be a false red.
            if (values && ts.isObjectLiteralExpression(values) && values.properties.every((property) => ts.isPropertyAssignment(property))) {
              for (const property of values.properties) {
                if (ts.isIdentifier(property.name)) supplied.add(property.name.text);
              }
              const missing = needed.filter((name) => !supplied.has(name));
              if (missing.length > 0) {
                missingValues.push({ file: rel, line: position(node), key: first.text, namespace, missing });
              }
            } else if (!values) {
              missingValues.push({ file: rel, line: position(node), key: first.text, namespace, missing: needed });
            }
          }
        }
      }
    }
    if (ts.isPropertyAssignment(node) && ts.isIdentifier(node.name) && ts.isStringLiteral(node.initializer)) {
      /**
       * A **named key**: a string literal in a `key`, `labelKey` or `msg` property that reads like a
       * catalogue key. These are the keys a page asks for *by name* rather than by a literal call —
       * `t(link.key)`, `t(option.labelKey)` — so the key-existence check above cannot see them, and a
       * key the catalogue does not hold is a runtime error nobody sees.
       *
       * The filter is the gate's own copy heuristic, and it is what separates the two kinds of value
       * that share a property: `labelKey: "attrFirstTouch"` is a key, while `key: "first_touch"` is the
       * API's own field name — a snake_case value, which the heuristic has always read as a field and not
       * as a sentence.
       */
      if (["key", "labelKey", "msg"].includes(node.name.text) && looksLikeKey(node.initializer.text)) {
        namedKeys.push({ file: rel, line: position(node), key: node.initializer.text.trim() });
      }
    }
    if (ts.isJsxText(node)) {
      const copy = node.text.replace(/\s+/g, " ").trim();
      /**
       * A lone lowercase word is copy in JSX text — a reader sees it standing between two tags — unless
       * it is a **unit** ("min", "ms", "yrs", "x") or a **field name printed as itself** ("integrity:").
       * The general rule cannot tell those apart from a word, but the shape can: text standing between
       * tags is read by a person, and a measurement or a field name is not a sentence.
       */
      const word = copy.replace(/[·:,.;—–-]\s*$/, "").trim();
      const loneWord = /^[a-z][a-z'-]*$/.test(word);
      const unit = UNITS.has(word);
      // A field name printed as itself: the word stands alone and the colon after it says so — either
      // inside the same element or in the element that follows it.
      const nextSibling = (() => {
        const parent = node.parent;
        if (!ts.isJsxElement(parent) || !ts.isJsxElement(parent.parent)) return "";
        const siblings = parent.parent.children;
        const index = siblings.indexOf(parent);
        const next = siblings[index + 1];
        return next && ts.isJsxText(next) ? next.text.trim() : "";
      })();
      const fieldName = copy.endsWith(":") || nextSibling.startsWith(":");
      if (loneWord ? !unit && !fieldName : isEnglishCopy(copy)) {
        sites.push({ file: rel, line: position(node), shape: "jsx", copy });
      }
    }
    if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer)) {
      const name = node.name.getText().replace(/^aria-/, "aria-");
      if (LABEL_ATTRIBUTES.has(name) && isEnglishCopy(node.initializer.text)) {
        sites.push({ file: rel, line: position(node), shape: `attr:${name}`, copy: node.initializer.text.trim() });
        counted.add(node.initializer.getStart(source));
      }
    }
    if (ts.isPropertyAssignment(node) && node.name && ts.isIdentifier(node.name) && ts.isStringLiteral(node.initializer)) {
      const name = node.name.text;
      if (LABEL_PROPERTIES.has(name) && isEnglishCopy(node.initializer.text)) {
        sites.push({ file: rel, line: position(node), shape: `object:${name}`, copy: node.initializer.text.trim() });
        counted.add(node.initializer.getStart(source));
      }
    }
    /**
     * The fourth shape. A string literal is copy when it is a sentence the reader will see, and it is
     * not copy when it is a name, a token or a value the tier owns. Each exclusion below is structural
     * rather than a list of words, so a new class name or a new API field does not need to be added to
     * an allowlist to keep the gate quiet:
     *
     *  * an import or export specifier — a module's name;
     *  * a naming attribute, or a class name written inside an expression or held in a variable — a
     *    name, not a sentence;
     *  * a comparison operand — the tier's own enum value, which the page quotes rather than writes;
     *  * a schema.org type or field — the vocabulary of a JSON-LD block;
     *  * a snake_case property — a field the API owns, printed as itself;
     *  * a language tag, the framework's own directive and a CSS custom property — tokens.
     */
    /**
     * A template is **one** site, not one per part: a sentence assembled from a template's pieces is one
     * sentence, and it belongs in one catalogue key with placeholders rather than five fragments.
     */
    if (ts.isTemplateExpression(node)) {
      const parts = [node.head, ...node.templateSpans.map((span) => span.literal)].filter(Boolean);
      const copyParts = parts.filter((part) => isEnglishCopy(part.text));
      if (copyParts.length > 0 && !templateIsToken(node, parts)) {
        literalSites.push({
          file: rel,
          line: position(node),
          shape: "template",
          copy: parts.map((part) => part.text.trim()).filter(Boolean).join(" ").slice(0, 120),
        });
      }
    }
    if (ts.isStringLiteral(node) && !counted.has(node.getStart(source))) {
      if (isEnglishCopy(node.text) && !literalIsToken(node, node.parent)) {
        literalSites.push({ file: rel, line: position(node), shape: "literal", copy: node.text.trim() });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  keyCalls.set(rel, { namespaces, keys });
}

const byFile = new Map();
for (const site of sites) byFile.set(site.file, (byFile.get(site.file) ?? 0) + 1);

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  const mark = ok ? "PASS" : "FAIL";
  console.log(`${mark}  ${name}${detail ? ` — ${detail}` : ""}`);
};

check(
  "the walk finds the population",
  files.length >= FLOOR_FILES && parsed === files.length && diagnostics === 0,
  `${files.length} .tsx files, ${parsed} parsed, ${diagnostics} parse diagnostics (floor ${FLOOR_FILES})`,
);

check(
  "the English literal count is at or below the committed floor",
  sites.length <= FLOOR_SITES,
  `${sites.length} site(s) against a floor of ${FLOOR_SITES}`,
);

/**
 * The fourth shape, with its own floor. The three shapes above report zero, and this one reports what
 * they cannot see: a sentence a helper returns, a wording a ternary chooses, a note a component builds.
 * It may only fall, like the other floor — a page that moves such a sentence into its catalogue lowers
 * it, and a page that adds one in the source raises it.
 */
check(
  "the copy the three shapes do not reach is at or below its floor",
  literalSites.length <= FLOOR_LITERAL_SITES,
  `${literalSites.length} literal site(s) against a floor of ${FLOOR_LITERAL_SITES}`,
);

/**
 * A key the catalogue does not hold is a runtime error, not a build error: next-intl throws
 * MISSING_MESSAGE the first time the page renders that string. The copy gate counts English
 * literals; this check is the other half — every key the source asks for is in the catalogue.
 */
const missingKeys = [];
for (const [file, { namespaces, keys }] of keyCalls) {
  for (const key of keys) {
    const [namespace, plain] = key.includes(".") && key.split(".").length === 2 ? [key.split(".")[0], key.split(".")[1]] : [null, key];
    const held = namespace
      ? Object.prototype.hasOwnProperty.call(CATALOGUE[namespace] ?? {}, plain)
      : [...namespaces].some((each) => Object.prototype.hasOwnProperty.call(CATALOGUE[each] ?? {}, plain));
    if (!held) missingKeys.push({ file, key: plain, namespaces: namespace ? [namespace] : [...namespaces].sort() });
  }
}

check(
  "every key the source asks for is in the catalogue",
  missingKeys.length === 0,
  missingKeys.length === 0
    ? `${[...keyCalls.values()].reduce((total, entry) => total + entry.keys.size, 0)} key call(s) checked`
    : `${missingKeys.length} key(s) the catalogue does not hold`,
);

/**
 * The keys a page asks for **by name** — `t(link.key)`, `t(option.labelKey)` — which the check above
 * cannot read, because the key is a value in the page's own data rather than a literal at the call.
 */
const missingNamedKeys = [];
for (const named of namedKeys) {
  const { namespaces } = keyCalls.get(named.file) ?? { namespaces: new Set() };
  const held = [...namespaces].some((namespace) => Object.prototype.hasOwnProperty.call(CATALOGUE[namespace] ?? {}, named.key));
  if (!held) missingNamedKeys.push(named);
}

check(
  "every key the source names in its own data is in the catalogue",
  missingNamedKeys.length === 0,
  missingNamedKeys.length === 0
    ? `${namedKeys.length} named key(s) checked`
    : `${missingNamedKeys.length} named key(s) the catalogue does not hold`,
);

/**
 * A key read without the values its message needs prints the placeholders themselves, and next-intl
 * answers a missing value with an error rather than a sentence. The scout's search-limits row is the
 * case this check was written for: the label was wired to a key that holds a *pattern*, so the column
 * read `{default} by default, {max} at most` where it should read "Search limits".
 */
check(
  "every placeholder a key needs is supplied with it",
  missingValues.length === 0,
  missingValues.length === 0
    ? `${[...keyCalls.values()].reduce((total, entry) => total + entry.keys.size, 0)} key call(s) checked for their values`
    : `${missingValues.length} key read(s) left a placeholder unsupplied`,
);

for (const [file, count] of [...byFile.entries()].sort((a, b) => (b[1] - a[1]) || (a[0] < b[0] ? -1 : 1))) {
  console.log(`      ${String(count).padStart(3)}  ${file}`);
}

const failed = checks.filter((c) => !c.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);
if (literalSites.length) {
  const literalByFile = new Map();
  for (const site of literalSites) literalByFile.set(site.file, (literalByFile.get(site.file) ?? 0) + 1);
  console.log("");
  console.log("The copy the three shapes do not reach, by file:");
  for (const [file, count] of [...literalByFile.entries()].sort((a, b) => (b[1] - a[1]) || (a[0] < b[0] ? -1 : 1))) {
    console.log(`      ${String(count).padStart(3)}  ${file}`);
  }
}
if (failed.length) {
  console.log("");
  console.log("Every site above is copy the catalogues do not carry. Wire it to a key, or say why it stays in English.");
  for (const site of sites) console.log(`  ${site.file}:${site.line} [${site.shape}] ${site.copy.slice(0, 90)}`);
  for (const site of literalSites) console.log(`  ${site.file}:${site.line} [${site.shape}] ${site.copy.slice(0, 90)}`);
  if (missingKeys.length) {
    console.log("");
    console.log("Every key below is asked for and not in the catalogue. next-intl throws MISSING_MESSAGE for it.");
    for (const missing of missingKeys) {
      console.log(`  ${missing.file}: ${missing.namespaces.join("/")} has no key ${JSON.stringify(missing.key)}`);
    }
  }
  if (missingNamedKeys.length) {
    console.log("");
    console.log("Every key below is named in the page's own data and not in the catalogue. next-intl throws MISSING_MESSAGE for it.");
    for (const missing of missingNamedKeys) {
      console.log(`  ${missing.file}:${missing.line}: ${JSON.stringify(missing.key)}`);
    }
  }
  if (missingValues.length) {
    console.log("");
    console.log("Every key below was read without the values its message needs. The page prints the placeholders.");
    for (const missing of missingValues) {
      console.log(`  ${missing.file}:${missing.line}: ${missing.namespace}.${missing.key} is missing ${missing.missing.join(", ")}`);
    }
  }
  process.exitCode = 1;
}
