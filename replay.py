#!/usr/bin/env python3
"""Inspect an explicit attempt history locally. No model, network, or Hebbrix API calls."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

STATUS = {"failure", "success", "unknown"}
MAX_INPUT_BYTES = 100_000
ROOT = Path(__file__).resolve().parent

class CaseError(ValueError):
    pass

def text_value(value, location):
    if not isinstance(value, str) or not any(not (c.isspace() or c == "\ufeff") for c in value) or len(value) > 12_000:
        raise CaseError(f"{location} must be a nonempty string of at most 12000 characters")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise CaseError(f"{location} contains invalid Unicode") from error
    if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
        raise CaseError(f"{location} contains a control character")
    return value

def object_fields(value, required, optional, location):
    if not isinstance(value, dict):
        raise CaseError(f"{location} must be an object")
    missing, extra = set(required) - set(value), set(value) - set(required) - set(optional)
    if missing or extra:
        raise CaseError(f"{location}: missing fields {sorted(missing)}; unexpected fields {sorted(extra)}")

def declared_boolean(value, location):
    if value is not None and type(value) is not bool:
        raise CaseError(f"{location} must be true, false, or null")

def validate_case(case):
    if not isinstance(case, dict) or type(case.get("schema_version")) is not int or case.get("schema_version") != 1:
        raise CaseError("Expected a case object with schema_version 1")
    object_fields(case, ("schema_version", "id", "title", "provenance", "initial", "later", "correction"), ("guard", "comparison"), "case")
    for name in ("id", "title"):
        text_value(case.get(name), name)
    if not isinstance(case.get("provenance"), str) or case["provenance"] not in {"synthetic", "user_supplied"}:
        raise CaseError("provenance must be synthetic or user_supplied")
    for name in ("initial", "later"):
        attempt = case.get(name)
        object_fields(attempt, ("decision_id", "action", "context", "outcome"), (), name)
        for key in ("decision_id", "action"):
            text_value(attempt.get(key), f"{name}.{key}")
        context = attempt.get("context")
        if not isinstance(context, dict) or not 1 <= len(context) <= 30:
            raise CaseError(f"{name}.context must contain 1 to 30 named string fields")
        for key in context:
            text_value(key, f"{name}.context key")
            text_value(context[key], f"{name}.context.{key}")
        outcome = attempt.get("outcome")
        object_fields(outcome, ("status", "evidence"), (), f"{name}.outcome")
        if not isinstance(outcome.get("status"), str) or outcome["status"] not in STATUS:
            raise CaseError(f"{name}.outcome.status must be failure, success, or unknown")
        text_value(outcome.get("evidence"), f"{name}.outcome.evidence")
    if case["initial"]["decision_id"] == case["later"]["decision_id"]:
        raise CaseError("The initial and later decisions must have distinct IDs")
    correction = case.get("correction")
    object_fields(correction, ("after_decision_id", "content", "intended_action", "visible_to_later"), (), "correction")
    if correction.get("after_decision_id") != case["initial"]["decision_id"]:
        raise CaseError("Correction must refer to the initial decision ID")
    for key in ("content", "intended_action"):
        text_value(correction.get(key), f"correction.{key}")
    declared_boolean(correction["visible_to_later"], "correction.visible_to_later")
    comparison = case.get("comparison")
    if comparison is not None:
        object_fields(comparison, ("comparable", "basis"), (), "comparison")
        declared_boolean(comparison["comparable"], "comparison.comparable")
        text_value(comparison["basis"], "comparison.basis")
    guard = case.get("guard")
    if guard is not None:
        object_fields(guard, ("allowed_actions", "basis"), (), "guard")
        allowed = guard.get("allowed_actions")
        if not isinstance(allowed, list) or not 1 <= len(allowed) <= 20:
            raise CaseError("guard.allowed_actions must have 1 to 20 explicit actions")
        for item in allowed:
            text_value(item, "guard.allowed_actions entry")
        if len(set(allowed)) != len(allowed):
            raise CaseError("guard.allowed_actions contains duplicate entries")
        text_value(guard.get("basis"), "guard.basis")
    return case

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CaseError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result

def parse_case(raw):
    if not isinstance(raw, (str, bytes, bytearray)):
        raise CaseError("Input must be UTF-8 bytes or JSON text")
    if isinstance(raw, str):
        try:
            raw = raw.encode("utf-8")
        except UnicodeError as error:
            raise CaseError("Input contains invalid Unicode") from error
    if len(raw) > MAX_INPUT_BYTES:
        raise CaseError("Input exceeds the 100 KB local case limit")
    try:
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        if raw.startswith("\ufeff"):
            raw = raw[1:]
        parsed = json.loads(raw, object_pairs_hook=unique_object, parse_constant=lambda value: (_ for _ in ()).throw(CaseError(f"Invalid JSON constant: {value}")))
    except CaseError:
        raise
    except (ValueError, RecursionError) as error:
        raise CaseError(f"Input is not valid UTF-8 JSON: {error}") from error
    return validate_case(parsed)

def load_case(path):
    path = Path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise CaseError("Input must be a regular local JSON file")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise CaseError("Input must be a regular local JSON file")
        with os.fdopen(descriptor, "rb") as source:
            descriptor = None
            raw = source.read(MAX_INPUT_BYTES + 1)
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return parse_case(raw)

def console(message, stream=None):
    """Keep non-ASCII record IDs, paths and errors safe on restricted terminals."""
    stream = sys.stdout if stream is None else stream
    encoding = getattr(stream, "encoding", None) or "utf-8"
    printable = str(message).encode(encoding, errors="backslashreplace").decode(encoding)
    print(printable, file=stream)

RULES = [{'when': 'context_changed', 'code': 'context_changed', 'conclusion': 'The supplied context fields differ. Their relevance needs review.', 'next_check': "Decide whether these differences change the task or the correction's applicability. A text difference alone does not establish that."}, {'when': 'not_comparable', 'code': 'declared_not_comparable', 'conclusion': 'The record declares these attempts unsuitable for comparison.', 'next_check': 'Review the supplied comparison basis before drawing a recurrence conclusion.'}, {'when': 'missing_outcome', 'code': 'insufficient_outcome_evidence', 'conclusion': 'The recorded outcomes do not establish a repeated failure.', 'next_check': 'Record the missing result and its source. Missing feedback is not failure.'}, {'when': 'initial_not_failure', 'code': 'initial_success', 'conclusion': 'The initial attempt is reported as successful, so this is not a repeat of an initial failure.', 'next_check': 'Review the later result separately and verify that both outcome labels are justified.'}, {'when': 'different_action', 'code': 'different_action', 'conclusion': 'The later attempt has different action text.', 'next_check': 'Investigate its result separately. Different text does not prove a semantically different action.'}, {'when': 'later_not_failure', 'code': 'repeat_without_repeat_failure', 'conclusion': 'The action repeated, but the recorded failure did not.', 'next_check': 'Check whether the first failure was transient before banning the action.'}, {'when': 'comparability_unknown', 'code': 'comparability_unknown', 'conclusion': 'The same action and two failures are reported. Comparable task conditions have not been established.', 'next_check': 'Add an explicit comparison basis. Matching context strings cannot establish equivalent task conditions.'}, {'when': 'same_intended_action', 'code': 'correction_preserves_action', 'conclusion': 'Two failures are reported, but the correction names the same action that was repeated.', 'next_check': 'Inspect parameters or other required changes. An action label alone cannot show whether the correction was followed.'}, {'when': 'correction_unavailable', 'code': 'correction_unavailable', 'conclusion': 'The record reports the same action failing twice and declares the correction unavailable.', 'next_check': 'Inspect how the correction is scoped, retrieved, and included in the later decision.'}, {'when': 'correction_available', 'code': 'correction_available', 'conclusion': 'The record reports the same action failing twice and declares the correction visible.', 'next_check': 'Check the actual supplied context, interpretation and execution. Visibility does not prove the correction was understood or applicable.'}, {'when': 'always', 'code': 'visibility_unknown', 'conclusion': 'The record reports two failures of the same action, but correction visibility is unknown.', 'next_check': 'Capture the evidence actually supplied to the later decision.'}]

def diagnose(case):
    validate_case(case)
    first, later, correction = case["initial"], case["later"], case["correction"]
    differences = sorted(key for key in set(first["context"]) | set(later["context"]) if first["context"].get(key) != later["context"].get(key))
    same_action = first["action"] == later["action"]
    first_failure = first["outcome"]["status"] == "failure"
    later_failure = later["outcome"]["status"] == "failure"
    visible = correction["visible_to_later"]
    comparable = (case.get("comparison") or {}).get("comparable")
    facts = {
        "context_changed": bool(differences), "not_comparable": comparable is False,
        "missing_outcome": first["outcome"]["status"] == "unknown" or later["outcome"]["status"] == "unknown",
        "initial_not_failure": not first_failure, "different_action": not same_action,
        "later_not_failure": not later_failure, "comparability_unknown": comparable is not True,
        "same_intended_action": correction["intended_action"] == first["action"],
        "correction_unavailable": visible is False, "correction_available": visible is True, "always": True,
    }
    rule = next(rule for rule in RULES if facts[rule["when"]])
    code, conclusion, next_check = (rule[key] for key in ("code", "conclusion", "next_check"))
    guard = case.get("guard")
    guard_report = {"available": guard is not None}
    if guard:
        guard_report.update({
            "later_action_allowed": later["action"] in guard["allowed_actions"],
            "correction_action_allowed": correction["intended_action"] in guard["allowed_actions"],
            "allowed_actions": guard["allowed_actions"],
            "basis": guard["basis"],
            "limit": "This checks a declared allowlist. It does not execute an agent, choose a repair, or prove task success.",
        })
    else:
        guard_report["limit"] = "No allowlist was supplied. No rule result is inferred."
    return {
        "id": case["id"], "title": case["title"], "provenance": case["provenance"],
        "diagnosis": code, "conclusion": conclusion, "next_check": next_check,
        "scope_differences": differences, "same_action": same_action,
        "declared_comparable_repeat_failure": not differences and comparable is True and first_failure and later_failure and same_action,
        "reported_failure_pattern": first_failure and later_failure and same_action,
        "comparison_declared": comparable,
        "evidence_limit": "All fields are supplied declarations. This tool cannot verify their truth, causal explanation, action equivalence or outcome quality.",
        "recorded_correction": {
            "intended_action": correction["intended_action"],
            "visible_in_recorded_later_attempt": visible,
            "limit": "The intended action is read from the authored correction. No model was tested for following it, and no counterfactual outcome was measured.",
        },
        "declared_allowlist_check": guard_report,
        "claim_boundary": "This inspects a supplied record. It does not run an agent, test Hebbrix, establish causality, or compare model or product performance.",
        "case": case,
    }

def markdown_report(reports):
    # A fenced JSON payload cannot turn input Markdown or HTML into active content.
    payload = json.dumps({"reports": reports}, indent=2, ensure_ascii=True)
    longest = max((len(part) for part in __import__("re").findall(r"`+", payload)), default=0)
    fence = "`" * max(3, longest + 1)
    return "# Supplied record inspection\n\nNo model or Hebbrix API calls were made. All trace fields are supplied declarations.\n\n" + fence + "json\n" + payload + "\n" + fence + "\n"

CSS = """
:root{color-scheme:light;--ink:#182b29;--muted:#50615e;--line:#dce5dc;--paper:#f4f5ed;--green:#dcebd0}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 system-ui,sans-serif}
main{max-width:1040px;margin:auto;padding:50px 28px 75px}.brand{font-size:14px;letter-spacing:.12em;text-transform:uppercase}
h1{font-size:clamp(36px,6vw,65px);line-height:1.05;max-width:800px;margin:24px 0}h2{font-size:28px;line-height:1.2}
p{max-width:76ch}.note{border-left:4px solid #476b3e;background:#e8eddf;padding:15px 20px}.muted{color:var(--muted)}
nav{display:flex;gap:8px;flex-wrap:wrap;margin:28px 0}a{color:inherit;text-underline-offset:4px}nav a{padding:8px 12px;border:1px solid var(--line);border-radius:6px;text-decoration:none;background:white}
article{background:#fff;border:1px solid var(--line);border-radius:12px;padding:26px;margin:24px 0}
.tag{font:12px/1.5 ui-monospace,monospace;padding:5px 9px;border-radius:4px;background:var(--green);display:inline-block}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.control{background:#f5f6f2;border:1px solid var(--line);padding:18px;border-radius:6px}
h3{font-size:17px;margin:0 0 8px}.control p{font-size:15px;margin:8px 0}code{background:#edf1e8;padding:2px 5px;overflow-wrap:anywhere}
table{width:100%;border-collapse:collapse;font-size:15px;margin:20px 0}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid var(--line)}th{width:22%}
details{margin-top:20px}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f6f2;padding:18px;font:13px/1.5 ui-monospace,monospace}
footer{margin-top:35px;font-size:14px;color:var(--muted)}@media(max-width:700px){.grid{grid-template-columns:1fr}main{padding:30px 18px}article{padding:18px}th{width:28%}}
"""

def html_report(reports):
    esc = lambda value: html.escape(str(value), quote=True)
    sections = []
    for index, report in enumerate(reports):
        case = report["case"]
        guard = report["declared_allowlist_check"]
        guard_text = ("The supplied later action is " + ("inside" if guard["later_action_allowed"] else "outside") +
            " the declared allowlist. The correction action is " + ("inside." if guard["correction_action_allowed"] else "outside.")) if guard["available"] else "No allowlist was supplied."
        guard_basis = "<p>" + esc(guard["basis"]) + "</p>" if guard["available"] else ""
        rows = []
        for label, a, b in [
            ("Decision",case["initial"]["decision_id"],case["later"]["decision_id"]),
            ("Action",case["initial"]["action"],case["later"]["action"]),
            ("Outcome",case["initial"]["outcome"]["status"],case["later"]["outcome"]["status"]),
            ("Evidence",case["initial"]["outcome"]["evidence"],case["later"]["outcome"]["evidence"]),
        ]:
            rows.append(f"<tr><th>{esc(label)}</th><td>{esc(a)}</td><td>{esc(b)}</td></tr>")
        for key in sorted(set(case["initial"]["context"]) | set(case["later"]["context"])):
            rows.append(f"<tr><th>Context: {esc(key)}</th><td>{esc(case['initial']['context'].get(key, '(not supplied)'))}</td><td>{esc(case['later']['context'].get(key, '(not supplied)'))}</td></tr>")
        comparison = case.get("comparison") or {}
        declaration = lambda value: "unknown" if value is None else ("yes" if value else "no")
        sections.append(f"""
<article id="case-{index}"><span class="tag">{esc(report['provenance'])} case / {esc(report['diagnosis'])}</span>
<h2>{esc(report['title'])}</h2><p>{esc(report['conclusion'])}</p>
<table><thead><tr><th>Recorded trace</th><th>Initial attempt</th><th>Later attempt</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p><strong>Correction:</strong> {esc(case['correction']['content'])}</p>
<p><strong>Declared visible:</strong> {declaration(case['correction']['visible_to_later'])}. <strong>Declared comparable:</strong> {declaration(comparison.get('comparable'))}.</p>
<p><strong>Comparison basis:</strong> {esc(comparison.get('basis', 'Not supplied.'))}</p>
<p>{esc(report['evidence_limit'])}</p>
<p><strong>Next check:</strong> {esc(report['next_check'])}</p>
<div class="grid"><div class="control"><h3>Recorded correction</h3>
<p>Intended action: <code>{esc(case['correction']['intended_action'])}</code></p>
<p>{esc(report['recorded_correction']['limit'])}</p></div>
<div class="control"><h3>Declared allowlist check</h3><p>{esc(guard_text)}</p>{guard_basis}<p>{esc(guard['limit'])}</p></div></div>
<details><summary>Inspect the complete input</summary><pre>{esc(json.dumps(case, indent=2))}</pre></details>
</article>""")
    style_hash = hashlib.sha256(CSS.encode()).digest()
    import base64
    csp = "default-src 'none'; style-src 'sha256-" + base64.b64encode(style_hash).decode() + "'; base-uri 'none'; form-action 'none'"
    nav = "".join(f'<a href="#case-{i}">{i + 1}. {esc(r["id"])}</a>' for i, r in enumerate(reports))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}"><title>Repeated mistake replay</title><style>{CSS}</style></head>
<body><main><div class="brand">Hebbrix / supplied record inspection</div>
<h1>What happened after the correction?</h1>
<p>Inspect an attempted action, its reported result, a correction, and a later attempt. All fields are supplied declarations, not independently verified evidence.</p>
<div class="note"><strong>Supplied record inspection.</strong> Records labeled synthetic were authored for teaching. Other provenance labels are supplied declarations.
This report inspects supplied fields. It is not a live agent run or a Hebbrix performance result. It cannot verify declarations or demonstrate that a model follows advice.</div>
<nav aria-label="Cases">{nav}</nav>{''.join(sections)}
<footer>This local report needs no sign-up, API key or model call. Opening this file does not upload a trace.
For a real investigation, replace the fixture with an authorized redacted trace and preserve what is known, unknown, and independently observed.
Hebbrix is in private beta. Applications record a decision and attach its later result; Hebbrix uses those results to guide later decisions.</footer>
</main></body></html>"""

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--case", default=None, help="A bundled case ID, or all (default)")
    source.add_argument("--input", type=Path, help="Inspect one local JSON case. No content is uploaded.")
    parser.add_argument("--output", type=Path, default=None, help="Local output directory. Required for your own input.")
    args = parser.parse_args(argv)
    try:
        if args.input and args.output is None:
            raise CaseError("Supply --output for your own record so bundled public reports are not replaced")
        if args.output is None:
            args.output = ROOT / "output"
        if args.input:
            input_paths = [args.input]
        else:
            selection = args.case or "all"
            paths = sorted((ROOT / "cases").glob("*.json"), key=lambda path: path.stem)
            if selection != "all":
                paths = [path for path in paths if path.stem == selection]
            if not paths:
                raise CaseError("Unknown bundled case. Choose all or a file stem under cases/.")
            input_paths = paths
        cases = [load_case(path) for path in input_paths]
        reports = [diagnose(case) for case in cases]
        # Resolve every destination first. Never overwrite an input or follow an output symlink.
        destinations = [args.output / ("report." + suffix) for suffix in ("json", "md", "html")]
        for destination in destinations:
            if destination.is_symlink():
                raise CaseError("Output report paths must not be symbolic links")
            if destination.exists() and not destination.is_file():
                raise CaseError("Every report destination must be a regular file or absent")
            if any(destination.resolve() == path.resolve() or (destination.exists() and destination.samefile(path)) for path in input_paths):
                raise CaseError("Output would overwrite the input case")
        args.output.mkdir(parents=True, exist_ok=True)
        payloads = {
            "report.json": json.dumps({"mode":"local_trace_inspection","live_calls":0,"reports":reports}, indent=2) + "\n",
            "report.md": markdown_report(reports), "report.html": html_report(reports),
        }
        write_bundle(args.output, payloads)
        for report in reports:
            console(f"{report['id']}: {report['diagnosis']}")
            console("  " + report["next_check"])
        console(f"Local HTML: {(args.output / 'report.html').resolve()}")
        console("No model or Hebbrix API calls were made.")
        return 0
    except (CaseError, OSError) as error:
        console(f"Cannot inspect case: {error}", sys.stderr)
        return 2

def write_bundle(output, payloads):
    """Render first, stage all files, and restore prior reports on a replacement error."""
    encoded = {name: value.encode("utf-8") for name, value in payloads.items()}
    stage = Path(tempfile.mkdtemp(prefix=".replay-stage-", dir=output))
    replaced = []
    preserve = False
    try:
        for name, data in encoded.items():
            target = output / name
            mode = 0o600
            if target.exists():
                mode &= stat.S_IMODE(target.stat().st_mode)
            descriptor = os.open(stage / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
            with os.fdopen(descriptor, "wb") as staged:
                staged.write(data)
            os.chmod(stage / name, mode)
            if target.exists():
                backup = stage / (name + ".backup")
                shutil.copyfile(target, backup)
                os.chmod(backup, stat.S_IMODE(target.stat().st_mode))
        try:
            for name in encoded:
                os.replace(stage / name, output / name)
                replaced.append(name)
        except OSError as original:
            for name in reversed(replaced):
                backup = stage / (name + ".backup")
                try:
                    if backup.exists():
                        os.replace(backup, output / name)
                    else:
                        (output / name).unlink()
                except OSError as rollback:
                    preserve = True
                    raise CaseError(f"Report replacement failed; recovery files preserved at {stage}: {rollback}") from original
            raise
    finally:
        if not preserve:
            shutil.rmtree(stage)

if __name__ == "__main__":
    raise SystemExit(main())

