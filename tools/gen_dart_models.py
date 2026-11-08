"""Generate Dart model classes for the Flutter app from the API's OpenAPI spec.

Usage: python tools/gen_dart_models.py   (writes docs/openapi.json and apps/mobile/lib/api/models.g.dart)
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def dart_name(name: str) -> str:
    name = re.sub(r"[^0-9A-Za-z]+", " ", name)
    return "".join(w[:1].upper() + w[1:] for w in name.split())


def field_name(name: str) -> str:
    parts = name.split("_")
    out = parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
    return out + "_" if out in {"in", "is", "default", "class", "new", "enum"} else out


def resolve(schema: dict) -> tuple[str, str, bool]:
    """Return (dart type, parse expression template with {v}, nullable)."""
    if "anyOf" in schema:
        opts = [s for s in schema["anyOf"] if s.get("type") != "null"]
        nullable = len(opts) < len(schema["anyOf"])
        t, e, _ = resolve(opts[0]) if opts else ("dynamic", "{v}", True)
        return t, e, nullable
    if "$ref" in schema:
        n = dart_name(schema["$ref"].split("/")[-1])
        return n, f"{n}.fromJson(({{v}}) as Map<String, dynamic>)", False
    t = schema.get("type")
    fmt = schema.get("format")
    if t == "string" and fmt in ("date", "date-time"):
        return "DateTime", "DateTime.parse({v} as String)", False
    if t == "string":
        return "String", "{v} as String", False
    if t == "integer":
        return "int", "({v} as num).toInt()", False
    if t == "number":
        return "double", "({v} as num).toDouble()", False
    if t == "boolean":
        return "bool", "{v} as bool", False
    if t == "array":
        it, ie, _ = resolve(schema.get("items", {}))
        inner = ie.replace("{v}", "e")
        return f"List<{it}>", f"(({{v}}) as List).map((e) => {inner}).toList()", False
    if t == "object" or "additionalProperties" in schema:
        return "Map<String, dynamic>", "Map<String, dynamic>.from({v} as Map)", False
    return "dynamic", "{v}", True


def to_json_expr(t: str, name: str, nullable: bool) -> str:
    q = "?" if nullable else ""
    if t == "DateTime":
        return f"{name}{q}.toIso8601String().substring(0, 10)" if name in DATE_ONLY else f"{name}{q}.toIso8601String()"
    if t.startswith("List<") and t[5:-1] in CLASSES:
        return f"{name}{q}.map((e) => e.toJson()).toList()"
    if t in CLASSES:
        return f"{name}{q}.toJson()"
    return name


DATE_ONLY: set[str] = set()
CLASSES: set[str] = set()


def main() -> None:
    from examradar_api.main import app

    spec = app.openapi()
    (ROOT / "docs" / "openapi.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    schemas = spec["components"]["schemas"]
    CLASSES.update(dart_name(n) for n in schemas)
    out = ["// GENERATED from docs/openapi.json by tools/gen_dart_models.py. Do not edit by hand.",
           "// ignore_for_file: non_constant_identifier_names, prefer_null_aware_operators", ""]
    for raw_name, sch in sorted(schemas.items()):
        if sch.get("type") != "object" and "properties" not in sch:
            continue
        cls = dart_name(raw_name)
        req = set(sch.get("required", []))
        props = sch.get("properties", {})
        fields = []
        for pname, ps in props.items():
            t, expr, nullable = resolve(ps)
            nullable = nullable or (pname not in req and "default" not in ps)
            if ps.get("format") == "date" or any(o.get("format") == "date" for o in ps.get("anyOf", [])):
                DATE_ONLY.add(field_name(pname))
            nullable = nullable and t != "dynamic"
            fields.append((pname, field_name(pname), t, expr, nullable, ps.get("default")))
        out.append(f"class {cls} {{")
        for _, fn, t, _, nullable, _ in fields:
            out.append(f"  final {t}{'?' if nullable else ''} {fn};")
        args = ", ".join(f"{'' if n else 'required '}this.{fn}" for _, fn, _, _, n, _ in fields)
        out.append(f"  const {cls}({{{args}}});" if fields else f"  const {cls}();")
        out.append(f"  factory {cls}.fromJson(Map<String, dynamic> j) => {cls}(")
        for pname, fn, t, expr, nullable, _default in fields:
            v = f"j['{pname}']"
            parsed = expr.replace("{v}", v)
            if nullable:
                out.append(f"        {fn}: {v} == null ? null : {parsed},")
            else:
                fallback = {"String": "''", "int": "0", "double": "0", "bool": "false"}.get(t)
                if t.startswith("List<"):
                    fallback = "const []"
                elif t.startswith("Map<"):
                    fallback = "const {}"
                out.append(f"        {fn}: {v} == null ? {fallback} : {parsed}," if fallback else f"        {fn}: {parsed},")
        out.append("      );")
        out.append("  Map<String, dynamic> toJson() => {")
        for pname, fn, t, _, nullable, _ in fields:
            out.append(f"        '{pname}': {to_json_expr(t, fn, nullable)},")
        out.append("      };")
        out.append("}")
        out.append("")
    target = ROOT / "apps" / "mobile" / "lib" / "api" / "models.g.dart"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {target} with {len(CLASSES)} classes")


if __name__ == "__main__":
    main()
