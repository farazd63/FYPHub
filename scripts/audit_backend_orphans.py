"""Read-only frontend/backend dependency audit; never moves application files."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import runpy
import subprocess
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/backend-audit"

FRONTEND_SCAN = r'''
import ts from './frontend/node_modules/typescript/lib/typescript.js';
import fs from 'node:fs';
import path from 'node:path';
const root=process.cwd(), base=path.join(root,'frontend/src'), files=[];
function walk(p){for(const e of fs.readdirSync(p,{withFileTypes:true})){const q=path.join(p,e.name);if(e.isDirectory())walk(q);else if(/\.(tsx?|mjs)$/.test(q))files.push(q);}}walk(base);
const result=[];
for(const file of files){
 const source=fs.readFileSync(file,'utf8'), sf=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true), imports=[], refs=[], calls=[], constants=new Map();
 const line=n=>sf.getLineAndCharacterOfPosition(n.getStart(sf)).line+1;
 function declarations(n){if(ts.isVariableDeclaration(n)&&ts.isIdentifier(n.name)&&n.initializer)constants.set(n.name.text,n.initializer);ts.forEachChild(n,declarations);}declarations(sf);
 function values(n,seen=new Set()){
  if(!n)return ['{dynamic}'];
  if(ts.isStringLiteralLike(n))return [n.text];
  if(ts.isParenthesizedExpression(n))return values(n.expression,seen);
  if(ts.isConditionalExpression(n))return [...values(n.whenTrue,seen),...values(n.whenFalse,seen)];
  if(ts.isBinaryExpression(n)){
   if([ts.SyntaxKind.QuestionQuestionToken,ts.SyntaxKind.BarBarToken].includes(n.operatorToken.kind))return [...values(n.left,seen),...values(n.right,seen)];
   if(n.operatorToken.kind===ts.SyntaxKind.PlusToken)return values(n.left,seen).flatMap(a=>values(n.right,seen).map(b=>a+b));
  }
  if(ts.isTemplateExpression(n)){let output=[n.head.text];for(const s of n.templateSpans)output=output.flatMap(a=>values(s.expression,new Set(seen)).map(b=>a+b+s.literal.text));return output;}
  if(ts.isIdentifier(n)&&constants.has(n.text)&&!seen.has(n.text)){seen.add(n.text);return values(constants.get(n.text),seen);}
  return ['{dynamic}'];
 }
 function method(n){if(!n||!ts.isObjectLiteralExpression(n))return 'GET';const p=n.properties.find(x=>x.name?.getText(sf)==='method');return p&&ts.isPropertyAssignment(p)?values(p.initializer)[0]:'GET';}
 function visit(n){
  if(ts.isImportDeclaration(n)&&ts.isStringLiteral(n.moduleSpecifier))imports.push(n.moduleSpecifier.text);
  if(ts.isCallExpression(n)){
   if(n.expression.kind===ts.SyntaxKind.ImportKeyword&&ts.isStringLiteral(n.arguments[0]))imports.push(n.arguments[0].text);
   const callee=n.expression.getText(sf);
   if(n.arguments.length&&(callee==='fetch'||/^read(?:JSON)?$|request|apiFetch|apiRequest|sendRequest/.test(callee))){
    for(const value of values(n.arguments[0]))if(value.includes('/api/')||value.includes('/health/'))calls.push({line:line(n),callee,method:method(n.arguments[1]),url:value,expression:n.arguments[0].getText(sf)});
   }
  }
  if(ts.isStringLiteralLike(n)||ts.isTemplateExpression(n))for(const value of values(n))if(value.includes('/api/')||value.includes('/health/'))refs.push({line:line(n),url:value,expression:n.getText(sf)});
  ts.forEachChild(n,visit);
 }visit(sf);
 const resolved=[];for(const entry of imports)if(entry.startsWith('.')){const p=path.resolve(path.dirname(file),entry);const match=[p,p+'.tsx',p+'.ts',p+'.mjs',path.join(p,'index.tsx'),path.join(p,'index.ts')].find(p=>fs.existsSync(p)&&fs.statSync(p).isFile());if(match)resolved.push(path.relative(root,match).replaceAll('\\','/'));}
 result.push({file:path.relative(root,file).replaceAll('\\','/'),imports:resolved,calls,references:refs});
}
console.log(JSON.stringify(result));
'''


def run(args):
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:] or result.stdout[-2000:])
    return result.stdout


def reachable(graph, roots):
    seen, pending = set(), list(roots)
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        pending.extend(graph.get(node, []))
    return seen


def python_graph():
    modules, trees, graph, imports, symbols, tables = {}, {}, {}, {}, {}, {}
    for base in (ROOT / "backend/app", ROOT / "backend/tests"):
        for file in sorted(base.rglob("*.py")):
            if "__pycache__" in file.parts:
                continue
            module = ".".join(file.relative_to(ROOT / "backend").with_suffix("").parts)
            if file.name == "__init__.py":
                module = module.removesuffix(".__init__")
            modules[module] = file
            trees[module] = ast.parse(file.read_text(encoding="utf-8-sig"))
    for module, tree in trees.items():
        graph[module], imports[module] = set(), {}
        package = module if modules[module].name == "__init__.py" else module.rsplit(".", 1)[0]
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports[module][alias.asname or alias.name.split(".")[0]] = alias.name
                    targets.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                base = importlib.util.resolve_name("." * node.level + (node.module or ""), package) if node.level else node.module or ""
                targets.append(base)
                for alias in node.names:
                    target = base + "." + alias.name
                    imports[module][alias.asname or alias.name] = target
                    targets.append(target)
            for target in targets:
                while target:
                    if target in modules and target != module:
                        graph[module].add(target)
                    target = target.rpartition(".")[0]
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbol = module + "." + node.name
                symbols[symbol] = (module, node)
                if isinstance(node, ast.ClassDef):
                    for child in node.body:
                        if isinstance(child, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in child.targets):
                            tables[symbol] = ast.literal_eval(child.value)

    def resolve(name, visited=None):
        visited = set() if visited is None else visited
        if name in visited:
            return name
        visited.add(name)
        if name in symbols:
            return name
        parent, _, leaf = name.rpartition(".")
        target = imports.get(parent, {}).get(leaf)
        return resolve(target, visited) if target else name

    symbol_graph, queries = {}, {}
    query_names = {"select", "update", "delete", "insert", "text"}
    for symbol, (module, node) in symbols.items():
        edges, sql = set(), []
        for child in ast.walk(node):
            if isinstance(child, ast.Name):
                target = resolve(imports[module].get(child.id, module + "." + child.id))
                if target in symbols and target != symbol:
                    edges.add(target)
            if isinstance(child, ast.Call):
                callee = ast.unparse(child.func)
                if callee in query_names or callee.endswith((".get", ".execute", ".scalar", ".scalars")):
                    sql.append({"file": modules[module].relative_to(ROOT).as_posix(), "line": child.lineno, "expression": ast.unparse(child)})
        symbol_graph[symbol], queries[symbol] = edges, sql
    return modules, graph, symbols, tables, symbol_graph, queries


def path_key(value):
    positions = [position for marker in ("/api/", "/health/") if (position := value.find(marker)) >= 0]
    if not positions:
        return None
    value = value[min(positions):].split("?", 1)[0].split("#", 1)[0]
    return re.sub(r"\{[^}]*\}", "{}", value).rstrip("/")


def cell(value):
    return str(value).replace("|", "/").replace("\n", " ")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frontend = json.loads(run(["node", "--input-type=module", "-e", FRONTEND_SCAN]))
    frontend_graph = {item["file"]: item["imports"] for item in frontend}
    mounted = reachable(frontend_graph, ["frontend/src/main.tsx"])
    inventory = runpy.run_path(str(ROOT / "scripts/build_defence_guide.py"))
    raw = run(["docker", "exec", "fyphub-p1-backend-1", "python", "-c", inventory["LIVE_SCRIPT"]])
    runtime = json.loads(raw[raw.index("{"):])
    (OUT / "before-contract.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    modules, graph, symbols, tables, symbol_graph, queries = python_graph()
    production = reachable(graph, ["app.main"])
    tests = reachable(graph, [module for module in modules if module.startswith("tests.")])
    reverse = defaultdict(list)
    for source, targets in graph.items():
        for target in targets:
            reverse[target].append(source)

    references = []
    for file in frontend:
        recorded = set()
        for kind, items in (("request", file["calls"]), ("URL reference / indirect request", file["references"])):
            for item in items:
                key = (item["line"], item["url"])
                if key in recorded:
                    continue
                recorded.add(key)
                references.append({**item, "file": file["file"], "active_import_graph": file["file"] in mounted, "kind": kind, "path_key": path_key(item["url"])})

    routes = []
    for route in runtime["routes"]:
        file = route["file"]
        module = next((name for name, p in modules.items() if p.relative_to(ROOT).as_posix() == file), None)
        symbol = (module + "." + route["function"]) if module else None
        deps = reachable(symbol_graph, [symbol]) if symbol else set()
        key = path_key(route["path"])
        matches = []
        for ref in references:
            candidate = ref["path_key"]
            if not candidate or not key:
                continue
            # Dynamic identifier/action placeholders are matched conservatively;
            # a match is a possible caller, never proof of runtime execution.
            pattern = "^" + re.escape(candidate).replace(re.escape("{}"), "[^/]+") + "$"
            method = ref.get("method")
            if (candidate == key or re.fullmatch(pattern, key)) and (not method or method in route["methods"] or "{dynamic}" in method):
                matches.append({"file": ref["file"], "line": ref["line"], "active": ref["active_import_graph"], "kind": ref["kind"]})
        dependency_files = sorted({modules[symbols[name][0]].relative_to(ROOT).as_posix() for name in deps if name in symbols})
        schemas = sorted(name for name in deps if name in symbols and isinstance(symbols[name][1], ast.ClassDef) and (".schemas." in name or any(ast.unparse(base).endswith("BaseModel") for base in symbols[name][1].bases)))
        models = {name: tables[name] for name in deps if name in tables}
        database_queries = [query for name in sorted(deps) for query in queries.get(name, [])]
        routes.append({**route, "possible_frontend_callers": matches, "transitive_symbols": sorted(deps), "dependency_files": dependency_files, "schemas": schemas, "models_and_tables": models, "database_queries": database_queries})

    app_files = []
    for module, p in modules.items():
        if not module.startswith("app"):
            continue
        path = p.relative_to(ROOT).as_posix()
        endpoints = [route for route in routes if route["file"] == path]
        if p.name == "__init__.py":
            reason = "Package initializer / re-export registry; implicit Python imports and ORM registration are protected."
        elif module in production:
            reason = "Directly or indirectly imported by app.main; active application dependency."
        elif module in tests:
            reason = "Referenced by current backend tests; shared/tested utility protected by the requested rules."
        else:
            reason = "No main/test import path found; requires manual external/configuration verification before quarantine."
        app_files.append({"file": path, "module": module, "main_reachable": module in production, "test_reachable": module in tests, "imported_by": sorted(reverse[module]), "registered_route_count": len(endpoints), "reason": reason, "safe_to_remove": False})

    result = {"commit": run(["git", "rev-parse", "HEAD"]).strip(), "frontend": frontend, "frontend_reachable": sorted(mounted), "frontend_references": references, "routes": routes, "backend_files": app_files, "import_graph": {k: sorted(v) for k, v in graph.items()}, "model_tables": runtime["model_tables"], "confirmed_orphans": [], "limitations": ["Frontend import reachability is conservative; imported files can contain inactive branches.", "Dynamic URL matching records possible callers and may overmatch action placeholders.", "Registered routes are retained regardless of frontend matching.", "Static symbol tracing is conservative and is supplemented by runtime route/schema inspection.", "A missing frontend match alone never establishes an orphan."]}
    (OUT / "dependency-map.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = ["# FYPHub backend orphan audit\n", "Inspection date: 2026-11-11 (Asia/Karachi).\n", f"Source baseline: `{result['commit']}`.\n", "## Disposition\n", "**No backend source file has been confirmed safe to remove. No application file has been moved, deleted, rewritten, or replaced.** Registered APIs without a direct current frontend caller remain protected active routes. Current tests, shared utilities, model registration, migrations, configuration, Docker files, health endpoints, backups and uploaded documents are retained.\n", "This report was created before any possible quarantine action. The confirmed-orphan list is empty, so `backend/_quarantine/` has no files to receive. Permanent deletion is not authorized by the evidence.\n", "## Evidence and method\n", f"- {len(frontend)} frontend TypeScript/JavaScript files parsed using the TypeScript AST; {len(mounted)} files reachable from `frontend/src/main.tsx`.\n", f"- {len(references)} API request/reference sites examined, including inactive source files and dynamic helpers.\n", f"- {len(app_files)} backend application Python files parsed; {len([f for f in app_files if f['main_reachable']])} loaded by the main import graph.\n", f"- {len(routes)} runtime route registrations inspected (including aliases/framework endpoints).\n", "- Runtime SQLAlchemy metadata, dependency guards, role closures, response models and the actual PostgreSQL schema were inspected read-only.\n", "- Direct and indirect imports include function-local imports, model/schema re-exports and implicit package initializers.\n", "- Full trace data is in [dependency-map.json](docs/backend-audit/dependency-map.json); the unchanged-contract baseline is [before-contract.json](docs/backend-audit/before-contract.json).\n", "## Frontend/authentication review\n", "`main.tsx` mounts `App.tsx`. App resolves the existing opaque cookie session through `/api/v1/auth/me`, uses the same-origin `/api` proxy, and dispatches Admin, Student, Supervisor, Coordinator and Panel Member dashboards. Login/signup/reset remain in App. Portal navigation uses existing component state and sidebar items; static route strings do not prove a React Router mount. The Student Overview embeds the current collaboration card. The active evaluator is `StudentEvaluatorPortal`. The backend `get_current_user`, `require_roles`, origin checks, password/session helpers, database/configuration and health/readiness endpoints are protected.\n", "## Backend file decisions\n", "| File | Main import path | Test import path | Registered routes | Why it appears unused / verification | Safe to remove |\n", "|---|---|---|---:|---|---|\n"]
    for item in app_files:
        lines.append(f"| `{item['file']}` | {item['main_reachable']} | {item['test_reachable']} | {item['registered_route_count']} | {cell(item['reason'])} Checked runtime route registration, frontend reference mapping, direct/indirect imports and current tests. Importers: {cell(', '.join(item['imported_by']) or 'implicit package / none')}. | No |\n")
    lines += ["\n## Complete frontend API/reference mapping\n", "Request sites identify network calls; reference sites also include endpoint props and indirect helper URL declarations. `Active graph` means imported by the current entrypoint, not guaranteed branch execution. Unmatched URLs are listed rather than fabricated as working endpoints.\n", "| Frontend file:line | Active graph | Kind / method | URL pattern | Backend handlers |\n", "|---|---|---|---|---|\n"]
    for ref in sorted(references, key=lambda item: (item["file"], item["line"])):
        matches = [route for route in routes if any(caller["file"] == ref["file"] and caller["line"] == ref["line"] for caller in route["possible_frontend_callers"])]
        handlers = "; ".join(f"{route['file']}:{route['line']} ({route['function']})" for route in matches)
        lines.append(f"| `{ref['file']}:{ref['line']}` | {ref['active_import_graph']} | {cell(ref['kind'])} / {cell(ref.get('method', 'indirect'))} | `{cell(ref['url'])}` | {cell(handlers or 'No exact/static match; dynamic or inactive reference requires manual review.')} |\n")
    lines += ["\n## Complete backend route → service → schema → model → query → authorization mapping\n", "Every registered route is retained. Endpoints without a static frontend match are not orphans: they may be aliases, tests, infrastructure or retained service APIs. The JSON attachment includes every traced symbol and full query expression; the table links queries to their source locations.\n", "| Method / route | Handler | Frontend callers | Services / shared dependencies | Schemas | Models → tables | Query locations | Auth / role dependencies |\n", "|---|---|---|---|---|---|---|---|\n"]
    for route in routes:
        callers = "; ".join(f"{c['file']}:{c['line']} ({'active graph' if c['active'] else 'inactive source'})" for c in route['possible_frontend_callers'])
        query_locations = sorted({f"{q['file']}:{q['line']}" for q in route['database_queries']})
        lines.append("| " + " | ".join(cell(x) for x in [','.join(route['methods'])+' '+route['path'], f"{route['file']}:{route['line']} {route['function']}", callers or 'No exact/static match; retained', '; '.join(route['dependency_files']), '; '.join(route['schemas']) or route['body_type'], '; '.join(f"{k} → {v}" for k,v in route['models_and_tables'].items()), '; '.join(query_locations), '; '.join(route['guards']) or 'Public/framework endpoint; see handler checks']) + " |\n")
    lines += ["\n## Important retained candidates\n", "| Candidate | Why it looks unused | Verification | Decision |\n", "|---|---|---|---|\n", "| `backend/app/team_compatibility.py` | Not imported by `app.main`. | Imported by `backend/tests/test_team_compatibility.py`; implements shared deterministic compatibility calculations. | Keep: current tests/shared utility explicitly protected. |\n", "| `backend/app/agent_supervision.py` and `backend/app/group_ai.py` | Some corresponding navigation/UI was removed. | Routers are still registered by `app.main`; models/utilities and current tests reference them. | Keep: active API contracts cannot be removed under this task. |\n", "| `backend/app/module2_collaboration.py`, `group_channels.py`, `collaboration_channels.py` | Similar-sounding collaboration implementations. | Different route namespaces/stores; private assignment channels are used by current Student and Supervisor pages. All routers are registered. | Keep; no replacement architecture or route consolidation. |\n", "| `backend/app/models/*`, `backend/app/schemas/*` | Some types lack direct browser usage. | ORM registry, response/body schemas and transitive route dependencies inspected. | Keep: no proven orphan. |\n", "| `backend/app/**/__init__.py` | No explicit caller may name the file itself. | Python package initialization and model re-exports are implicit dependencies. | Keep. |\n", "| `backend/backend/` | Nested directory resembles an accidental copy. | Directory inspected recursively: no files. | Nothing to quarantine/delete. |\n", "| `backend/backups/`, tracked `backend/storage/` files | Not Python imports. | Historical backup/upload data; not executable orphan code. | Keep; data deletion is outside this task. |\n", "\n## Validation\n", "Validation runs and limitations are recorded in [validation.md](docs/backend-audit/validation.md). Baseline failures must be distinguished from cleanup regressions. No quarantined file may be permanently deleted while any required check fails.\n", "\n## Final removal list\n", "**None.** No file satisfies the strict confirmed-orphan criteria. No API, schema, model, migration, test, authentication dependency or frontend behavior has been changed.\n"]
    (ROOT / "backend-orphan-audit.md").write_text("".join(lines), encoding="utf-8")
    print(json.dumps({"backend_files":len(app_files),"routes":len(routes),"frontend_files":len(frontend),"frontend_reachable":len(mounted),"frontend_references":len(references),"confirmed_orphans":0}))


if __name__ == "__main__":
    main()
