#!/usr/bin/env node
/*
 * The catalogue's dead keys: a key no page asks for is a translation that ships to nobody.
 *
 * The copy gate (`qa-i18n-literals.mjs`) answers the other half of the same question. It asks whether
 * every key the source asks for **is** in the catalogue; this gate asks whether every key the
 * catalogue holds is **asked for**. The two are not the same check, and only one of them was ever
 * written — so a catalogue could hold three thousand six hundred keys while the tree read two
 * thousand, and every gate in the suite would have said the catalogue was complete.
 *
 * It matters for three reasons, in this order:
 *
 *  * **A translation is work.** Each key is written three times — English, Chinese, Traditional
 *    Chinese — and every one of them has to be right, and re-read when the message beside it changes.
 *    A key nothing reads is that work, forever, for no reader.
 *  * **A key that names a page is a claim about the page.** `nav.video` says a nav entry called
 *    "Video Analysis" exists. If the nav prints `nav.videoShort` instead, the catalogue holds two
 *    answers to one question, and only one of them is the page's. The nav's own comment says it
 *    plainly: "a catalogue nothing reads is a translation that ships to nobody".
 *  * **A gate that cannot see its own subject cannot be trusted.** The count this file reports is
 *    only worth the resolution behind it, so the resolution is written out and its limits are
 *    reported rather than assumed.
 *
 * How a read is found — the same four shapes the copy gate had to learn, because a translator is
 * identified by its **binding** and not by its name:
 *
 *  * a **named** read — `t("key")`, with the namespace the translator is bound to;
 *  * a **destructured** read — `const [t, td] = await Promise.all([…, getTranslations("home"), …])`,
 *    where each name's namespace is its position in the list;
 *  * a **dynamic** read — `t(band.key)`, where the key is a value in the page's own data, resolved
 *    back to the literals that can reach it;
 *  * a **named-key** read — `t(link.key)`, `labelKey="rowSession"`, `whatKey="…"`: the key is in the
 *    page's data rather than at the call, so it is credited to every namespace that file binds.
 *
 * **Soundness is the whole game here.** A gate that reports a key as dead when a read of it is
 * merely *unresolved* would send someone to delete a key the page needs. So a read whose argument
 * cannot be resolved to literals **exempts its whole namespace**: no key in that namespace is
 * reported, and the gate says how many namespaces it had to leave alone and why.
 *
 * Files only: no server, no browser, no port — which is why it belongs with the other file-only
 * gates in `scripts/check.sh` and in CI.
 */

import { readdirSync, readFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const ts = require("typescript");

const WEB = resolve(process.env.QA_I18N_WEB ? process.env.QA_I18N_WEB : fileURLToPath(new URL("..", import.meta.url)));
const CATALOGUE = JSON.parse(readFileSync(join(WEB, "messages", "en.json"), "utf8"));

/**
 * The ceiling on the keys no page asks for. It may only fall: a slice that wires a key to a page
 * lowers it, and a slice that adds a key no page reads raises it — and the gate says so.
 *
 * The number is the count this gate read on 2026-10-22, with every read in the tree resolved: the
 * catalogue holds 3736 keys and 226 of them are asked for by nothing.
 */
const FLOOR_UNUSED = 226;

/**
 * Keys the catalogue holds on purpose, for a page that does not exist yet or for a door that is
 * refused by name. Each one says why it is held, because a list without reasons is the same as no
 * list at all: it is a place where a dead key goes to stop the gate from noticing.
 */
const HELD = new Map();

/** The whole web tier is the population: a translator can be bound in a component, a page or a lib. */
const files = [];
const walk = (dir) => {
  if (!existsSync(dir)) return;
  for (const entry of readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
    const p = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name.startsWith(".next") || entry.name === ".git" || entry.name === "dist") continue;
      walk(p);
    } else if (/\.tsx?$/.test(entry.name)) files.push(p);
  }
};
walk(WEB);

const relOf = (p) => p.slice(WEB.length + 1).split(sep).join("/");

/**
 * The literals an expression can hold.
 *
 * A dynamic read is `t(band.key)`, and the value it holds is in the page's own data — a module-level
 * array of objects, a record of statuses, a ternary. This walks back from the expression to the
 * literals that can reach it, so "the key this read names" is a set rather than a guess.
 *
 * Three shapes of "where the value came from" are read here, and each is a way a page hands a value
 * to a piece of code that then reads it:
 *
 *  * a **variable** in the file — `const RATING_KEYS = { execution: [...] }`;
 *  * a **callback parameter** — `SUGGESTIONS.map((suggestion) => t(suggestion))`, where the parameter
 *    holds the array's elements;
 *  * a **function parameter** — `function EraseRow({ whatKey }) { … t(whatKey) }`, where the value is
 *    what the caller passed, and the caller is recorded in `parameterSets`.
 */
const resolveStrings = (expr, source, depth = 0, parameterSets = new Map()) => {
  if (!expr || depth > 5) return [];
  if (ts.isStringLiteral(expr) || ts.isNoSubstitutionTemplateLiteral(expr)) return [expr.text];
  if (ts.isAsExpression(expr) || ts.isParenthesizedExpression(expr) || ts.isSatisfiesExpression(expr)) {
    return resolveStrings(expr.expression, source, depth + 1, parameterSets);
  }
  if (ts.isIdentifier(expr)) {
    // A function parameter: the value is what the caller passed, and the caller is recorded.
    if (parameterSets.has(expr.text)) return [...parameterSets.get(expr.text)];
    // A variable in the file.
    const out = [];
    const declarations = (node) => {
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === expr.text) {
        out.push(...resolveStrings(node.initializer, source, depth + 1, parameterSets));
      }
      ts.forEachChild(node, declarations);
    };
    declarations(source);
    if (out.length > 0) return [...new Set(out)];
    // A callback parameter: `ARRAY.map((item) => t(item))` — the parameter holds the array's elements.
    return resolveCallbackParameter(expr, source, depth);
  }
  if (ts.isArrayLiteralExpression(expr)) {
    return [...new Set(expr.elements.flatMap((element) => resolveStrings(element, source, depth + 1, parameterSets)))];
  }
  if (ts.isObjectLiteralExpression(expr)) {
    return [...new Set(expr.properties.flatMap((property) => {
      if (ts.isPropertyAssignment(property)) return resolveStrings(property.initializer, source, depth + 1, parameterSets);
      if (ts.isShorthandPropertyAssignment(property)) return resolveStrings(property.name, source, depth + 1, parameterSets);
      return [];
    }))];
  }
  if (ts.isConditionalExpression(expr)) {
    return [...new Set([
      ...resolveStrings(expr.whenTrue, source, depth + 1, parameterSets),
      ...resolveStrings(expr.whenFalse, source, depth + 1, parameterSets),
    ])];
  }
  if (ts.isBinaryExpression(expr) && expr.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken) {
    return [...new Set([
      ...resolveStrings(expr.left, source, depth + 1, parameterSets),
      ...resolveStrings(expr.right, source, depth + 1, parameterSets),
    ])];
  }
  if (ts.isPropertyAccessExpression(expr)) {
    // `band.key` — the holder is an array of objects, and each object's `key` is a candidate.
    const out = [];
    const holders = (node) => {
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
        // The table is often written `as const`, which wraps the literal.
        const init = ts.isAsExpression(node.initializer) ? node.initializer.expression : node.initializer;
        const elements = ts.isArrayLiteralExpression(init) ? init.elements : ts.isObjectLiteralExpression(init) ? [init] : [];
        for (const element of elements) {
          if (!ts.isObjectLiteralExpression(element)) continue;
          for (const property of element.properties) {
            if (!ts.isPropertyAssignment(property)) continue;
            const name = ts.isIdentifier(property.name) ? property.name.text : ts.isStringLiteral(property.name) ? property.name.text : null;
            if (name !== expr.name.text) continue;
            out.push(...resolveStrings(property.initializer, source, depth + 1, parameterSets));
          }
        }
      }
      ts.forEachChild(node, holders);
    };
    holders(source);
    return [...new Set(out)];
  }
  if (ts.isElementAccessExpression(expr)) {
    // `RECORD[kind]` — the value may be any of the record's values, so every one of them is a candidate.
    // The record may itself be indexed (`RATING_KEYS[kind]?.[n]`), so the holder is looked through.
    const holder = ts.isIdentifier(expr.expression)
      ? expr.expression
      : ts.isElementAccessExpression(expr.expression) && ts.isIdentifier(expr.expression.expression)
        ? expr.expression.expression
        : null;
    if (!holder) return [];
    const out = [];
    const holders = (node) => {
      if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === holder.text && node.initializer) {
        const init = ts.isAsExpression(node.initializer) ? node.initializer.expression : node.initializer;
        if (!ts.isObjectLiteralExpression(init)) {
          ts.forEachChild(node, holders);
          return;
        }
        for (const property of init.properties) {
          if (!ts.isPropertyAssignment(property)) continue;
          out.push(...resolveStrings(property.initializer, source, depth + 1, parameterSets));
        }
      }
      ts.forEachChild(node, holders);
    };
    holders(source);
    return [...new Set(out)];
  }
  return [];
};

/**
 * The literals a callback parameter can hold: the elements of the array it iterates.
 */
const resolveCallbackParameter = (identifier, source, depth) => {
  for (let up = identifier.parent; up; up = up.parent) {
    if (!ts.isFunctionLike(up)) continue;
    const binds = parameterNames(up).includes(identifier.text);
    if (!binds) continue;
    const call = up.parent;
    if (!call || !ts.isCallExpression(call)) return [];
    const callee = call.expression;
    if (!ts.isPropertyAccessExpression(callee) || !ts.isIdentifier(callee.expression)) return [];
    const method = callee.name.text;
    if (!["map", "forEach", "filter", "flatMap", "some", "every", "find"].includes(method)) return [];
    const values = resolveStrings(callee.expression, source, depth + 1);
    return values;
  }
  return [];
};

/**
 * The namespaces a translator declaration binds, as `[name, namespace]` pairs.
 *
 * Two shapes: the ordinary named one (`const t = useTranslations("nav")`) and the destructured one
 * (`const [t, td, tc] = await Promise.all([…, getTranslations("home"), …])`), where each name's
 * namespace is its **position** in the list.
 */
const translatorBindingsOf = (node) => {
  const pairs = [];
  if (!ts.isVariableDeclaration(node) || !node.initializer) return pairs;
  const initializer = ts.isAwaitExpression(node.initializer) ? node.initializer.expression : node.initializer;
  const namespaceOf = (expression) => {
    const call = ts.isAwaitExpression(expression) ? expression.expression : expression;
    if (!ts.isCallExpression(call) || !ts.isIdentifier(call.expression)) return null;
    const callee = call.expression.text;
    if (callee !== "useTranslations" && callee !== "getTranslations") return null;
    return ts.isStringLiteral(call.arguments[0]) ? call.arguments[0].text : null;
  };
  if (ts.isIdentifier(node.name)) {
    const namespace = namespaceOf(initializer);
    if (namespace) pairs.push([node.name.text, namespace]);
    return pairs;
  }
  if (ts.isArrayBindingPattern(node.name)) {
    const isPromiseAll =
      ts.isCallExpression(initializer) &&
      ts.isPropertyAccessExpression(initializer.expression) &&
      ts.isIdentifier(initializer.expression.expression) &&
      initializer.expression.expression.text === "Promise" &&
      initializer.expression.name.text === "all";
    const list = isPromiseAll && ts.isArrayLiteralExpression(initializer.arguments[0])
      ? initializer.arguments[0].elements
      : ts.isArrayLiteralExpression(initializer)
        ? initializer.elements
        : null;
    if (!list) return pairs;
    node.name.elements.forEach((element, index) => {
      if (!ts.isIdentifier(element.name)) return;
      const namespace = namespaceOf(list[index]);
      if (namespace) pairs.push([element.name.text, namespace]);
    });
  }
  return pairs;
};

/** The names a function's parameters bind. */
const parameterNames = (fn) => {
  const names = [];
  const collect = (node) => {
    if (!node) return;
    if (ts.isIdentifier(node)) { names.push(node.text); return; }
    if (ts.isObjectBindingPattern(node) || ts.isArrayBindingPattern(node)) {
      for (const element of node.elements) collect(element.name);
      return;
    }
    if (ts.isBindingElement(node)) collect(node.name);
  };
  for (const parameter of fn.parameters ?? []) collect(parameter.name);
  return names;
};

/** The functions a file can call, by name. */
const callableNames = (source) => {
  const names = new Map();
  const visit = (node) => {
    if (ts.isFunctionDeclaration(node) && node.name) names.set(node.name.text, node);
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      const init = ts.isAwaitExpression(node.initializer) ? node.initializer.expression : node.initializer;
      if ((ts.isArrowFunction(init) || ts.isFunctionExpression(init)) && node.name.text) names.set(node.name.text, init);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return names;
};

const bindingName = (nameNode) => (ts.isIdentifier(nameNode) ? nameNode.text : null);

/** The prop a component's parameter destructures to, and the local name it binds. */
const propToLocal = (fn) => {
  const map = new Map();
  const parameter = fn.parameters?.[0];
  if (!parameter || !ts.isObjectBindingPattern(parameter.name)) return map;
  for (const element of parameter.name.elements) {
    if (!ts.isBindingElement(element) || !ts.isIdentifier(element.name)) continue;
    map.set(element.propertyName ? element.propertyName.getText() : element.name.text, element.name.text);
  }
  return map;
};

/**
 * The reads the tree makes, by namespace.
 *
 * `asked` holds the keys each namespace is asked for by name. `named` holds the keys a page names in
 * its **own data** (`t(link.key)`, `labelKey="rowSession"`) — those have no namespace of their own,
 * so they are credited to every namespace the file binds, which is the conservative direction.
 * `unresolved` holds the reads whose argument could not be resolved to literals; each one exempts
 * its whole namespace from being judged, because a key that cannot be shown to be dead is not dead.
 */
const asked = new Map();
const named = new Map();
const unresolved = [];
/** The namespaces a file binds — used to credit a named key. */
const fileNamespaces = new Map();
/** The file-wide translator bindings, kept between the two passes. */
const fileBindings = new Map();

/**
 * The namespace each callable's translator parameter is handed, keyed by the callee's own node.
 *
 * The map is **global**: a component is called from another file (`EraseRow` is used by the club
 * page and by the plan page, neither of which is the file that declares it), and a fact about a
 * parameter is a fact about the component, not about the file that mentions it.
 */
const parameterBindings = new Map();
/**
 * The literals each callable's parameter is handed at its call sites.
 *
 * `EraseRow` reads `t(whatKey)`, and `whatKey` is a prop the caller passes — `whatKey="rowSession"`.
 * The call site is the fact, so it is recorded here and used to resolve the read inside the callee.
 */
const parameterValues = new Map();
const recordValue = (fn, name, values) => {
  if (values.length === 0) return;
  if (!parameterValues.has(fn)) parameterValues.set(fn, new Map());
  if (!parameterValues.get(fn).has(name)) parameterValues.get(fn).set(name, new Set());
  for (const value of values) parameterValues.get(fn).get(name).add(value);
};
const recordBinding = (fn, name, namespace) => {
  if (!parameterBindings.has(fn)) parameterBindings.set(fn, new Map());
  parameterBindings.get(fn).set(name, namespace);
};

const scopes = [];
const translatorOf = (name) => {
  for (let index = scopes.length - 1; index >= 0; index -= 1) {
    if (scopes[index].has(name)) return scopes[index].get(name);
  }
  return undefined;
};
const bindTranslator = (name, namespace) => {
  if (scopes.length === 0) scopes.push(new Map());
  scopes[scopes.length - 1].set(name, namespace);
};

let parsed = 0;
let diagnostics = 0;

/* --- the tree is parsed once, and the components it exports are indexed --- */
const sources = files.map((file) => {
  const source = ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  if (source.parseDiagnostics?.length) diagnostics += source.parseDiagnostics.length;
  parsed += 1;
  return { file, source, rel: relOf(file) };
});

/**
 * The components the tree exports, by name.
 *
 * A component is used from another file, so the call sites that say what it is handed are in files
 * the component does not know about. The index is the whole tree's, and it is why the gate can
 * resolve a prop a component reads (`t(whatKey)`) to the literals its callers pass.
 */
const exportedComponents = new Map();
for (const { source } of sources) {
  const visit = (node) => {
    const isExported = node.modifiers?.some((modifier) => modifier.kind === ts.SyntaxKind.ExportKeyword);
    if (ts.isFunctionDeclaration(node) && node.name && isExported) exportedComponents.set(node.name.text, node);
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && isExported) {
      const init = ts.isAwaitExpression(node.initializer) ? node.initializer.expression : node.initializer;
      if (ts.isArrowFunction(init) || ts.isFunctionExpression(init)) exportedComponents.set(node.name.text, init);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
}

for (const { source, rel } of sources) {
  const position = (node) => source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;

  const bindingsByName = new Map();
  const namespaces = new Set();
  const callables = callableNames(source);
  /* --- pass 1: the file-wide bindings, and what each call site hands over --- */
  const prePass = (node) => {
    for (const [name, namespace] of translatorBindingsOf(node)) {
      namespaces.add(namespace);
      if (!bindingsByName.has(name)) bindingsByName.set(name, new Set());
      bindingsByName.get(name).add(namespace);
    }
    ts.forEachChild(node, prePass);
  };
  prePass(source);

  scopes.length = 0;
  scopes.push(new Map());
  const pass1 = (node) => {
    const isScope = ts.isFunctionLike(node) && node.body !== undefined;
    if (isScope) {
      scopes.push(new Map());
      for (const name of parameterNames(node)) {
        const inherited = translatorOf(name);
        if (inherited !== undefined) bindTranslator(name, inherited);
      }
    }
    for (const [name, namespace] of translatorBindingsOf(node)) bindTranslator(name, namespace);

    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
      const fn = callables.get(node.expression.text) ?? exportedComponents.get(node.expression.text);
      if (fn) {
        node.arguments.forEach((argument, index) => {
          const parameter = fn.parameters?.[index];
          const name = parameter ? bindingName(parameter.name) : null;
          let namespace = undefined;
          if (ts.isIdentifier(argument)) namespace = translatorOf(argument.text);
          if (name && namespace) recordBinding(fn, name, namespace);
          // The literal the caller passes, for a read of a parameter's value.
          const values = ts.isStringLiteral(argument) ? [argument.text] : [];
          if (name) recordValue(fn, name, values);
        });
      }
    }
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = node.tagName;
      if (ts.isIdentifier(tag)) {
        const fn = callables.get(tag.text) ?? exportedComponents.get(tag.text);
        if (fn) {
          const locals = propToLocal(fn);
          for (const attribute of node.attributes.properties) {
            if (!ts.isJsxAttribute(attribute) || !attribute.initializer) continue;
            const local = locals.get(attribute.name.getText());
            if (!local) continue;
            if (ts.isStringLiteral(attribute.initializer)) {
              recordValue(fn, local, [attribute.initializer.text]);
              continue;
            }
            if (!ts.isJsxExpression(attribute.initializer)) continue;
            const value = attribute.initializer.expression;
            let namespace = undefined;
            if (ts.isIdentifier(value)) namespace = translatorOf(value.text);
            if (namespace) recordBinding(fn, local, namespace);
          }
        }
      }
    }
    ts.forEachChild(node, pass1);
    if (isScope) scopes.pop();
  };
  pass1(source);
  scopes.length = 0;
  fileBindings.set(rel, bindingsByName);
}

/**
 * The reads — the second pass, over every file again.
 *
 * It is a second pass because a fact about a component is a fact about the **tree**: `EraseRow` is
 * declared in one file and called from two others, so what it is handed is only known once every
 * file has been read.
 */
for (const { source, rel } of sources) {
  const position = (node) => source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
  const bindingsByName = fileBindings.get(rel) ?? new Map();

  scopes.push(new Map());
  /** The literals each parameter of the function being entered was handed at its call sites. */
  const parameterStack = [];
  const visit = (node) => {
    const isScope = ts.isFunctionLike(node) && node.body !== undefined;
    if (isScope) {
      scopes.push(new Map());
      const handed = parameterBindings.get(node);
      if (handed) for (const [name, namespace] of handed) bindTranslator(name, namespace);
      for (const name of parameterNames(node)) {
        if (handed && handed.has(name)) continue;
        const inherited = translatorOf(name);
        if (inherited !== undefined) bindTranslator(name, inherited);
      }
      const values = parameterValues.get(node);
      parameterStack.push(values ? new Map([...values].map(([name, set]) => [name, [...set]])) : new Map());
    }
    for (const [name, namespace] of translatorBindingsOf(node)) bindTranslator(name, namespace);

    if (ts.isCallExpression(node) && node.arguments.length > 0) {
      const callee = ts.isIdentifier(node.expression)
        ? node.expression.text
        : ts.isPropertyAccessExpression(node.expression) && ts.isIdentifier(node.expression.expression) &&
            node.expression.name.text === "rich"
          ? node.expression.expression.text
          : null;
      const scoped = callee ? translatorOf(callee) : undefined;
      const candidates = scoped ? [scoped] : callee && bindingsByName.has(callee) ? [...bindingsByName.get(callee)] : [];
      if (candidates.length > 0) {
        const first = node.arguments[0];
        if (ts.isStringLiteral(first)) {
          for (const namespace of candidates) {
            if (!asked.has(namespace)) asked.set(namespace, new Set());
            asked.get(namespace).add(first.text);
          }
        } else {
          const values = resolveStrings(first, source, 0, parameterStack[parameterStack.length - 1] ?? new Map());
          if (values.length === 0) {
            // An unresolved read exempts its namespace: a key that cannot be shown dead is not dead.
            unresolved.push({ file: rel, line: position(node), namespace: candidates[0], snippet: first.getText(source).slice(0, 60) });
            for (const namespace of candidates) if (!asked.has(namespace)) asked.set(namespace, new Set());
          } else {
            for (const namespace of candidates) {
              if (!asked.has(namespace)) asked.set(namespace, new Set());
              for (const value of values) asked.get(namespace).add(value);
            }
          }
        }
      }
    }

    /**
     * A key the page names in its **own data** — `t(link.key)`, `labelKey="rowSession"`,
     * `whatKey="…"`. It has no namespace of its own, so it is credited to every namespace the file
     * binds: the conservative direction, because a key credited too widely is a key that cannot be
     * reported as dead.
     */
    const creditNamedKey = (key) => {
      if (!named.has(key)) named.set(key, []);
      named.get(key).push(rel);
    };
    if (ts.isPropertyAssignment(node) && node.name && ts.isIdentifier(node.name) && ts.isStringLiteral(node.initializer)) {
      const name = node.name.text;
      if (name === "key" || name === "msg" || name.endsWith("Key")) creditNamedKey(node.initializer.text.trim());
    }
    if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer)) {
      if (node.name.getText().endsWith("Key")) creditNamedKey(node.initializer.text.trim());
    }

    ts.forEachChild(node, visit);
    if (isScope) {
      scopes.pop();
      parameterStack.pop();
    }
  };
  visit(source);
  scopes.length = 0;
}

/* --- the judgement --- */

/** The namespaces a read could not be resolved in, so no key in them can be called dead. */
const exempt = new Set();
for (const read of unresolved) exempt.add(read.namespace);

const orphans = [];
let total = 0;
for (const [namespace, block] of Object.entries(CATALOGUE)) {
  if (!block || typeof block !== "object") continue;
  for (const key of Object.keys(block)) {
    total += 1;
    const path = `${namespace}.${key}`;
    if (exempt.has(namespace)) continue;
    if (HELD.has(path)) continue;
    const askedHere = asked.get(namespace)?.has(key) ?? false;
    // A named key has no namespace, so it is credited to every namespace of the files that name it.
    const namedSomewhere = named.has(key);
    if (!askedHere && !namedSomewhere) orphans.push(path);
  }
}

const checks = [];
const check = (name, ok, detail) => {
  checks.push({ name, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
};

check(
  "the walk finds the population",
  files.length > 0 && parsed === files.length && diagnostics === 0,
  `${files.length} file(s), ${parsed} parsed, ${diagnostics} parse diagnostic(s)`,
);

check(
  "every catalogue key is asked for by a page, or held for a named reason",
  orphans.length <= FLOOR_UNUSED,
  `${orphans.length} key(s) asked for by nothing, against a floor of ${FLOOR_UNUSED}`,
);

check(
  "every read that could not be resolved left its namespace unjudged",
  exempt.size === 0 || unresolved.length > 0,
  `${unresolved.length} unresolved read(s) across ${exempt.size} namespace(s) left unjudged`,
);

const byNamespace = new Map();
for (const path of orphans) {
  const namespace = path.split(".")[0];
  if (!byNamespace.has(namespace)) byNamespace.set(namespace, []);
  byNamespace.get(namespace).push(path);
}
for (const [namespace, list] of [...byNamespace.entries()].sort((a, b) => b[1].length - a[1].length)) {
  console.log(`      ${String(list.length).padStart(3)}  ${namespace}`);
}

const failed = checks.filter((entry) => !entry.ok);
console.log(`CHECKS passed=${checks.length - failed.length} total=${checks.length} failed=${failed.length}`);

if (orphans.length || unresolved.length || process.env.QA_UNUSED_VERBOSE) {
  if (orphans.length) {
    console.log("");
    console.log("Every key below is in the catalogue and asked for by nothing. Wire it, or hold it with a reason:");
    for (const path of orphans) console.log(`  ${path}`);
  }
  if (unresolved.length) {
    console.log("");
    console.log("Every read below could not be resolved to a literal, so its namespace was left unjudged:");
    for (const read of unresolved) console.log(`  ${read.file}:${read.line} [${read.namespace}] ${read.snippet}`);
  }
}
if (failed.length) process.exitCode = 1;
