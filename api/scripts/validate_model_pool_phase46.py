"""Phase 4.6: real-workload validation harness for the 3 enabled
LEGAL_DRAFTING model-pool candidates (model_pool.py's _REGISTRY,
priority 1-3).

DO NOT RUN THIS IN CI OR AS PART OF `pytest api/tests/`. It makes real,
paid/quota-consuming HTTP calls to Gemini/Groq using the application's
real .env credentials, and force-selects a single fixed candidate per
run (bypassing model_pool.select_model()'s real priority ordering) --
exactly the kind of call this project's test suite is built to NEVER
make (see test_contracts.py's FAKE_SELECTED_MODEL / _fake_generate()
docstrings). It is a standalone, manually-invoked local validation tool
only, same category as api/scripts/live_verify*.py and
diagnose_legal_grounds*.py.

Safety, mirroring those existing scripts:
  - FakeDB only (api/tests/test_contracts.py's in-memory double) -- zero
    real Supabase reads/writes.
  - DRAFTS_DIR redirected to a throwaway dir under REPO_ROOT (must stay
    under REPO_ROOT -- contracts.py's docx_path.relative_to(REPO_ROOT)
    requirement), never the real generated_drafts/, cleaned up after.
  - Never runs on Oracle; never touches Docker/Render/Vercel state.
  - Never prints API key values -- only provider/model names and
    sanitized error text (llm_gateway.ProviderError messages already
    strip the raw response beyond a 300-char preview, no header/key
    values ever pass through them).

Usage:
    api/.venv/bin/python api/scripts/validate_model_pool_phase46.py \
        <candidate_letter: A|B|C> <c_repeats:int> <out.json>

Candidates (matches model_pool._REGISTRY priority 1-3 exactly):
    A = gemini:gemini-3.1-flash-lite  (tight daily quota -- keep c_repeats=1)
    B = groq:openai/gpt-oss-120b
    C = groq:openai/gpt-oss-20b

Each run executes, in order, and STOPS EARLY (recording a sanitized
failure) the first time any call raises a quota/rate-limit/billing/
availability-shaped error -- it never silently retries indefinitely and
never substitutes a different model:
    TEST A (simple clause)      -- NDA template, 2 llm_fillable clauses, x1
    TEST B (PII masking)        -- NDA template w/ synthetic PII, x1
    TEST C (structured 5-clause)-- Consultancy template, x c_repeats
    TEST D (instruction-following amendment) -- one amendment redraft
                                    per TEST C run, x c_repeats
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))

from app.services import contracts  # noqa: E402
from app.services.llm_gateway import generate as real_generate  # noqa: E402
from app.services.model_pool import Capability, ModelSpec  # noqa: E402
from app.services.model_pool_validation_checks import (  # noqa: E402
    contains_raw_value,
    distinct_value_to_placeholder_ratio,
    has_leftover_placeholder,
    has_reasoning_leakage,
)
from tests.test_contracts import (  # noqa: E402
    BASE_FORM,
    CONSULTANCY_FORM,
    FakeDB,
    _seed_consultancy,
    _seed_matter,
    _seed_template,
)

CANDIDATES = {
    "A": ModelSpec(provider="gemini", model="gemini-3.1-flash-lite",
                    capability=Capability.LEGAL_DRAFTING, priority=1, enabled=True),
    "B": ModelSpec(provider="groq", model="openai/gpt-oss-120b",
                    capability=Capability.LEGAL_DRAFTING, priority=2, enabled=True),
    "C": ModelSpec(provider="groq", model="openai/gpt-oss-20b",
                    capability=Capability.LEGAL_DRAFTING, priority=3, enabled=True),
}

# Distinct from the real api/generated_drafts and from Phase 4.6's
# earlier (already-deleted) benchmark dir -- must stay under REPO_ROOT.
BENCH_DIR = API_ROOT / "_phase46_validation_drafts_tmp"

_HARD_STOP_MARKERS = ("429", "402", "503", "rate limited", "payment_required")

# Synthetic values only, per the phase's explicit instruction -- these are
# not any real person's/entity's data.
PII_NAME = "Rohan Mehta"
PII_ADDRESS = "12 Example Road, Hyderabad"
PII_PAN = "ABCDE1234F"

D_CONSTRAINT_AMENDMENT = (
    "For this revision: use a formal Indian legal drafting style; be concise; "
    "do not include any conversational explanation, preamble, or meta-commentary; "
    "do not invent or cite any statute, section number, or case name; rely only on "
    "the facts explicitly given above; do not add any legal conclusion beyond what "
    "those facts support."
)


def _install_selected_model(model_spec: ModelSpec) -> None:
    contracts.select_model = lambda capability, settings=None, _m=model_spec: _m


def _timed_generate(call_log):
    def wrapped(*args, **kwargs):
        t0 = time.monotonic()
        try:
            result = real_generate(*args, **kwargs)
            call_log.append({
                "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                "provider": result.provider, "model": result.model,
                "degraded": result.degraded, "success": True,
            })
            return result
        except Exception as e:
            call_log.append({
                "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                "success": False, "error": f"{type(e).__name__}: {e}",
            })
            raise
    return wrapped


def _is_hard_stop(error_str: str) -> bool:
    return any(marker in error_str for marker in _HARD_STOP_MARKERS)


def _cleanup_drafts():
    if BENCH_DIR.exists():
        for f in BENCH_DIR.iterdir():
            f.unlink()


# Groq's free-tier RPM burst limit: firing 5 concurrent clause calls for
# one draft immediately followed by 5 more for the next draft (no gap)
# self-inflicted a 429 the first time this harness ran against Groq --
# not a real daily-quota signal, just an avoidable burst. A short pause
# between successive generate_draft() calls keeps this a genuine
# reliability/quota measurement instead of a self-caused rate limit.
INTER_DRAFT_PAUSE_S = 8.0


def _run_draft(model_spec, db, template_id, matter_id, form_data, amendment_note=None):
    """One real generate_draft() call against an already-seeded `db`
    (template + matter rows must already be present). Returns a result
    dict; never raises -- errors are captured so the harness can decide
    whether to hard-stop."""
    time.sleep(INTER_DRAFT_PAUSE_S)
    _install_selected_model(model_spec)
    call_log = []
    contracts.generate = _timed_generate(call_log)

    t0 = time.monotonic()
    error = None
    clause_records = None
    pii_rows = None
    try:
        result = contracts.generate_draft(matter_id, template_id, form_data,
                                           amendment_note=amendment_note, db=db)
        clause_records = [
            {"clause_key": f.clause_key, "prompt": f.prompt, "generated_text": f.generated_text,
             "model_used": f.model_used}
            for f in result.clause_fills
        ]
        pii_rows = db.table("pii_masks").rows
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    total_ms = round((time.monotonic() - t0) * 1000, 1)
    _cleanup_drafts()
    return {
        "total_ms": total_ms,
        "clause_records": clause_records,
        "pii_rows": pii_rows,
        "error": error,
        "calls": call_log,
    }


def _score_masking(run_result, raw_values):
    if run_result["error"] or not run_result["clause_records"]:
        return None
    findings = {"prompt_leaks": {}, "output_leftover_placeholders": {},
                "output_missing_real_values": {}, "collision_check": None}
    for rec in run_result["clause_records"]:
        leak = contains_raw_value(rec["prompt"], raw_values)
        if leak:
            findings["prompt_leaks"][rec["clause_key"]] = leak
        leftover = has_leftover_placeholder(rec["generated_text"])
        if leftover:
            findings["output_leftover_placeholders"][rec["clause_key"]] = leftover
        missing = [v for v in raw_values if v not in rec["generated_text"]]
        if missing:
            findings["output_missing_real_values"][rec["clause_key"]] = missing
    findings["collision_check"] = distinct_value_to_placeholder_ratio(run_result["pii_rows"] or [])
    return findings


def _score_reasoning_leakage(run_result):
    if run_result["error"] or not run_result["clause_records"]:
        return None
    out = {}
    for rec in run_result["clause_records"]:
        leak = has_reasoning_leakage(rec["generated_text"])
        if leak:
            out[rec["clause_key"]] = leak
    return out


def main():
    label_id = sys.argv[1]
    c_repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    out_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    model_spec = CANDIDATES[label_id]
    report: dict = {
        "model": f"{model_spec.provider}:{model_spec.model}",
        "c_repeats": c_repeats,
        "hard_stopped": False,
        "hard_stop_reason": None,
        "tests": {},
    }

    def _record(name, run_result):
        report["tests"].setdefault(name, []).append(run_result)
        if run_result["error"] and _is_hard_stop(run_result["error"]):
            report["hard_stopped"] = True
            report["hard_stop_reason"] = f"{name}: {run_result['error']}"
        return report["hard_stopped"]

    try:
        # TEST A -- simple clause (NDA, 2 llm_fillable clauses), x1
        nda_form = dict(BASE_FORM)
        db_a = FakeDB()
        template_id = _seed_template(db_a)
        _seed_matter(db_a, matter_id="matter-A")
        r = _run_draft(model_spec, db_a, template_id, "matter-A", nda_form)
        r["reasoning_leakage"] = _score_reasoning_leakage(r)
        if _record("A_simple_clause", r):
            return report

        # TEST B -- PII masking (NDA template, synthetic PII values)
        pii_form = dict(BASE_FORM)
        pii_form["party_a_name"] = PII_NAME
        pii_form["party_a_address"] = PII_ADDRESS
        pii_form["purpose"] = (
            f"advising on tax matters; correspondence PAN reference {PII_PAN}"
        )
        db_b = FakeDB()
        template_id2 = _seed_template(db_b)
        _seed_matter(db_b, matter_id="matter-B")
        r = _run_draft(model_spec, db_b, template_id2, "matter-B", pii_form)
        r["reasoning_leakage"] = _score_reasoning_leakage(r)
        r["masking_findings"] = _score_masking(r, [PII_NAME, PII_ADDRESS, PII_PAN])
        if _record("B_pii_masking", r):
            return report

        # TEST C + D -- Consultancy 5-clause structured draft, x c_repeats,
        # each followed immediately by one instruction-following amendment.
        for i in range(c_repeats):
            db_c = FakeDB()
            template_id3 = _seed_consultancy(db_c)
            matter_id_c = f"matter-C-{i}"
            _seed_matter(db_c, matter_id=matter_id_c)
            r = _run_draft(model_spec, db_c, template_id3, matter_id_c, CONSULTANCY_FORM)
            r["reasoning_leakage"] = _score_reasoning_leakage(r)
            if _record("C_structured_multiclause", r):
                return report

            r_d = _run_draft(model_spec, db_c, template_id3, matter_id_c, CONSULTANCY_FORM,
                              amendment_note=D_CONSTRAINT_AMENDMENT)
            r_d["reasoning_leakage"] = _score_reasoning_leakage(r_d)
            if _record("D_instruction_following_amendment", r_d):
                return report
    finally:
        _cleanup_drafts()
        shutil.rmtree(BENCH_DIR, ignore_errors=True)
        if out_path:
            out_path.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
