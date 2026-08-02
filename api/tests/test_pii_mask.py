"""Tests for the mandatory PII-masking layer (CLAUDE.md Decision 4).

These must never regress: if masking silently fails, client-confidential
facts go straight to a third-party LLM.
"""

from app.services.pii_mask import InMemoryMaskStore, MaskMap, mask_text, unmask_text


def test_party_name_and_address_are_masked_with_stable_placeholders():
    mm = MaskMap(matter_id="m1")
    entities = [
        ("PARTY", "Ramesh Kumar"),
        ("PARTY", "Sunita Sharma"),
        ("ADDR", "12, MG Road, New Delhi"),
    ]
    text = "Ramesh Kumar entered into an agreement with Sunita Sharma at 12, MG Road, New Delhi."

    masked = mask_text(text, mm, entities)

    assert "Ramesh Kumar" not in masked
    assert "Sunita Sharma" not in masked
    assert "12, MG Road, New Delhi" not in masked
    assert "PARTY_A" in masked
    assert "PARTY_B" in masked
    assert "ADDR_1" in masked


def test_masking_is_case_insensitive_and_reuses_placeholder_for_repeats():
    mm = MaskMap(matter_id="m1")
    entities = [("PARTY", "Ramesh Kumar")]
    text = "ramesh kumar signed. Later, RAMESH KUMAR confirmed."

    masked = mask_text(text, mm, entities)

    assert masked.count("PARTY_A") == 2
    assert "ramesh" not in masked.lower()


def test_pan_is_masked():
    mm = MaskMap(matter_id="m1")
    text = "The applicant's PAN is ABCDE1234F for verification."

    masked = mask_text(text, mm)

    assert "ABCDE1234F" not in masked
    assert "PAN_1" in masked


def test_aadhaar_is_masked_with_and_without_spaces():
    mm = MaskMap(matter_id="m1")
    text = "Aadhaar: 1234 5678 9012 and also 123456789012 appear here."

    masked = mask_text(text, mm)

    assert "1234 5678 9012" not in masked
    assert "123456789012" not in masked
    assert masked.count("AADHAAR_") == 2


def test_phone_number_is_masked():
    mm = MaskMap(matter_id="m1")
    text = "Call the client at +91 9876543210 or 9876543210."

    masked = mask_text(text, mm)

    assert "9876543210" not in masked
    assert "PHONE_" in masked


def test_email_is_masked():
    mm = MaskMap(matter_id="m1")
    text = "Send the draft to ramesh.kumar@example.com for review."

    masked = mask_text(text, mm)

    assert "ramesh.kumar@example.com" not in masked
    assert "EMAIL_1" in masked


def test_unmask_restores_original_values():
    mm = MaskMap(matter_id="m1")
    entities = [("PARTY", "Ramesh Kumar")]
    original = "Ramesh Kumar's PAN is ABCDE1234F."

    masked = mask_text(original, mm, entities)
    # Simulate an LLM response that echoes the placeholders back.
    llm_response = f"Drafted for {mask_text('Ramesh Kumar', mm, entities)}, PAN on file."
    restored = unmask_text(llm_response, mm)

    assert "Ramesh Kumar" in restored
    assert "PARTY_A" not in restored


def test_full_round_trip_never_leaks_pii_in_outbound_text():
    mm = MaskMap(matter_id="m1")
    entities = [
        ("PARTY", "Ramesh Kumar"),
        ("PARTY", "Sunita Sharma"),
        ("ADDR", "12, MG Road, New Delhi"),
    ]
    original = (
        "Ramesh Kumar (PAN ABCDE1234F, Aadhaar 1234 5678 9012, phone 9876543210, "
        "email ramesh.kumar@example.com) resides at 12, MG Road, New Delhi and is "
        "in dispute with Sunita Sharma."
    )

    masked = mask_text(original, mm, entities)

    for pii in [
        "Ramesh Kumar",
        "Sunita Sharma",
        "12, MG Road, New Delhi",
        "ABCDE1234F",
        "1234 5678 9012",
        "9876543210",
        "ramesh.kumar@example.com",
    ]:
        assert pii not in masked, f"{pii!r} leaked into the outbound (masked) text"

    restored = unmask_text(masked, mm)
    assert restored == original


# --- Automatic detection (no caller-supplied entities) ---------------------
# These are the gap that let "Ramesh Kumar" leak in the live hello-matter
# test: PARTY/ADDR were only ever masked when explicitly passed in via
# `entities`. Nothing upstream registers free-text names automatically.


def test_person_name_is_auto_masked_without_explicit_entities():
    mm = MaskMap(matter_id="m1")
    text = "Ramesh Kumar (PAN ABCDE1234F) signed the agreement."

    masked = mask_text(text, mm)

    assert "Ramesh Kumar" not in masked
    assert "PARTY_A" in masked
    assert "PAN_1" in masked


def test_postal_address_is_auto_masked_without_explicit_entities():
    mm = MaskMap(matter_id="m1")
    text = "The property is located at 12, MG Road, New Delhi 110001."

    masked = mask_text(text, mm)

    assert "12, MG Road, New Delhi" not in masked
    assert "ADDR_1" in masked


def test_company_with_pvt_ltd_suffix_is_auto_masked():
    mm = MaskMap(matter_id="m1")
    text = "The vendor, Sharma Enterprises Pvt Ltd, failed to deliver on time."

    masked = mask_text(text, mm)

    assert "Sharma Enterprises Pvt Ltd" not in masked
    assert "PARTY_A" in masked


def test_company_with_private_limited_suffix_is_auto_masked():
    mm = MaskMap(matter_id="m1")
    text = "Kumar Textiles Private Limited is the registered owner."

    masked = mask_text(text, mm)

    assert "Kumar Textiles Private Limited" not in masked


def test_company_with_llp_suffix_is_auto_masked():
    mm = MaskMap(matter_id="m1")
    text = "ABC Solutions LLP was engaged as a consultant."

    masked = mask_text(text, mm)

    assert "ABC Solutions LLP" not in masked


def test_company_with_ltd_suffix_is_auto_masked():
    mm = MaskMap(matter_id="m1")
    text = "Payment was received from Acme Traders Ltd last week."

    masked = mask_text(text, mm)

    assert "Acme Traders Ltd" not in masked


def test_mobile_number_hyphenated_5_5_grouping_is_masked():
    mm = MaskMap(matter_id="m1")
    text = "Reach the client on 98765-43210 anytime."

    masked = mask_text(text, mm)

    assert "98765-43210" not in masked
    assert "PHONE_" in masked


def test_mobile_number_space_5_5_grouping_is_masked():
    mm = MaskMap(matter_id="m1")
    text = "Reach the client on 98765 43210 anytime."

    masked = mask_text(text, mm)

    assert "98765 43210" not in masked
    assert "PHONE_" in masked


def test_mobile_number_plus91_no_separator_is_masked():
    mm = MaskMap(matter_id="m1")
    text = "WhatsApp: +919876543210."

    masked = mask_text(text, mm)

    assert "9876543210" not in masked
    assert "PHONE_" in masked


def test_reported_bug_ramesh_kumar_pan_case():
    """Exact scenario from the live hello-matter test: masked_prompt showed
    'Ramesh Kumar (PAN PAN_1)' instead of 'PARTY_A (PAN PAN_1)'."""
    mm = MaskMap(matter_id="m1")
    text = "Ramesh Kumar (PAN ABCDE1234F)"

    masked = mask_text(text, mm)

    assert masked == "PARTY_A (PAN PAN_1)"
    # This is what SupabaseMaskStore.save() persists to pii_masks.
    assert mm.reverse["PARTY_A"] == "Ramesh Kumar"


def test_short_contextless_sentence_still_masks_the_name():
    """en_core_web_sm's PERSON NER missed this sentence entirely in
    testing (no PAN/other entity nearby for context) — the fix must not
    depend on spaCy actually tagging PERSON to catch a plain two-word
    proper name."""
    mm = MaskMap(matter_id="m1")
    text = "Ramesh Kumar signed the notice."

    masked = mask_text(text, mm)

    assert "Ramesh Kumar" not in masked
    assert "PARTY_A" in masked


# --- Legal-terminology false positives / false negatives -------------------
# Regression tests for the two bugs found on 2026-07-24: a single
# mistagged token vetoing a whole legitimate name (false negative), and
# spaCy's poor recall on statute names letting them slip through as
# PARTY (false positive).


def test_court_names_are_never_masked():
    mm = MaskMap(matter_id="m1")
    text = (
        "The Supreme Court in Kesavananda Bharati v. State of Kerala held "
        "that the basic structure is inviolable."
    )

    masked = mask_text(text, mm)

    assert "The Supreme Court" in masked
    assert "State of Kerala" in masked


def test_partially_mistagged_case_name_still_gets_fully_masked():
    """spaCy tags only "Kesavananda" (not "Kesavananda Bharati") as GPE —
    that single-word mistag must not veto the whole two-word name."""
    mm = MaskMap(matter_id="m1")
    text = (
        "The Supreme Court in Kesavananda Bharati v. State of Kerala held "
        "that the basic structure is inviolable."
    )

    masked = mask_text(text, mm)

    assert "Kesavananda Bharati" not in masked
    assert "PARTY_A" in masked
    assert mm.reverse["PARTY_A"] == "Kesavananda Bharati"


def test_statute_name_with_year_is_never_masked():
    mm = MaskMap(matter_id="m1")
    text = "Section 18 of the Consumer Protection Act 2019 provides for District Commission jurisdiction."

    masked = mask_text(text, mm)

    assert masked == text
    assert mm.reverse == {}


def test_statute_name_without_year_is_never_masked():
    mm = MaskMap(matter_id="m1")
    text = "This falls under the Indian Contract Act, and also the Carriage by Road Act."

    masked = mask_text(text, mm)

    assert "Indian Contract Act" in masked
    assert "Carriage by Road Act" in masked


def test_indian_legal_abbreviations_are_never_masked():
    mm = MaskMap(matter_id="m1")
    text = (
        "This is punishable under IPC and BNS provisions, and also attracts "
        "GST and RERA compliance. CrPC, CPC, BNSS, BSA, NI Act, CGST, SGST, "
        "IGST, TDS, SEBI, RBI, FEMA and DPDP all apply too."
    )

    masked = mask_text(text, mm)

    assert masked == text
    assert mm.reverse == {}


# --- TICKET-1 (Sprint 2 postmortem, 2026-08-01): auto_detect_names=False ---
# Found live in the NDA E2E run: a Contracts clause-fill prompt is a mix of
# this codebase's own static instruction wording and user-supplied data.
# Scanning the whole assembled string with the Title-Case-run heuristic
# false-positived on ordinary two-word capitalized legal drafting phrases
# ("NOW THEREFORE", "Governing Law") that are the caller's own boilerplate,
# not client data — and it wasn't just noise: the corrupted placeholder
# ended up inside the literal instruction sent to the LLM ("Draft the
# PARTY_D and Dispute Resolution clause..."). auto_detect_names=False lets
# a caller that has ALREADY masked its user-supplied values individually
# (see app/services/contracts.py::generate_draft) skip re-scanning its own
# prose, without losing PAN/phone/Aadhaar/email detection (still regex,
# still precise, still always on) or explicit entity masking.


def test_template_boilerplate_passes_through_unchanged_with_auto_detect_off():
    mm = MaskMap(matter_id="m1")
    text = (
        "Draft the recitals for this Non-Disclosure Agreement, ending with "
        "'NOW THEREFORE, in consideration of the mutual covenants contained "
        "herein, the Parties agree as follows:'. Draft the Governing Law and "
        "Dispute Resolution clause, numbered '9. Governing Law and "
        "Jurisdiction'."
    )

    masked = mask_text(text, mm, auto_detect_names=False)

    assert masked == text
    assert mm.reverse == {}


def test_auto_detect_off_still_masks_explicit_entities_and_regex_pii():
    """The flag only gates the fuzzy Title-Case-run/company/address
    heuristics — explicit entities and structural regex (PAN/phone/
    Aadhaar/email) must still fire, since those are exactly what a caller
    relies on when it passes auto_detect_names=False for its own text."""
    mm = MaskMap(matter_id="m1")
    entities = [("PARTY", "Ramesh Kumar")]
    text = (
        "Client contact: Ramesh Kumar (PAN ABCDE1234F, mobile 9876543210). "
        "Draft the Governing Law clause for this Agreement."
    )

    masked = mask_text(text, mm, entities, auto_detect_names=False)

    assert "Ramesh Kumar" not in masked
    assert "ABCDE1234F" not in masked
    assert "9876543210" not in masked
    assert "Governing Law" in masked  # not caught by fuzzy detection — correct, it's boilerplate


def test_auto_detect_true_still_default_and_unchanged_for_existing_callers():
    """Backward-compatibility guard: omitting auto_detect_names must behave
    exactly as before this ticket — Litigation's chat messages and every
    other existing caller are entirely user-authored text and must keep
    full fuzzy detection."""
    mm = MaskMap(matter_id="m1")
    text = "Ramesh Kumar signed the notice."

    masked = mask_text(text, mm)

    assert "Ramesh Kumar" not in masked
    assert "PARTY_A" in masked


# --- Permanent regressions for the 2026-07-24 Q1 hand-traces ---------------


def test_case_name_masks_despite_partial_spacy_veto():
    mm = MaskMap(matter_id="m1")
    text = (
        "The Supreme Court in Kesavananda Bharati v. State of Kerala held "
        "that the basic structure is inviolable."
    )

    masked = mask_text(text, mm)

    assert "Kesavananda Bharati" not in masked
    assert any(v == "Kesavananda Bharati" for v in mm.reverse.values())
    placeholder = next(p for p, v in mm.reverse.items() if v == "Kesavananda Bharati")
    assert placeholder.startswith("PARTY_")
    assert "Supreme Court" in masked
    assert "State of Kerala" in masked


def test_statute_name_not_masked():
    mm = MaskMap(matter_id="m1")
    text = "Section 18 of the Consumer Protection Act 2019 provides for District Commission jurisdiction."

    masked = mask_text(text, mm)

    for phrase in ("Consumer Protection Act", "District Commission", "Section 18"):
        assert phrase in masked


def test_statute_abbreviations_not_masked():
    mm = MaskMap(matter_id="m1")
    text = "Governed by the Indian Contract Act, subject to CrPC section 91 and NI Act section 138."

    masked = mask_text(text, mm)

    for phrase in ("CrPC", "NI Act", "Indian Contract Act"):
        assert phrase in masked


def test_mask_store_round_trips_across_save_and_load():
    store = InMemoryMaskStore()
    mm = store.load("matter-123")
    mask_text("Ramesh Kumar signed.", mm, [("PARTY", "Ramesh Kumar")])
    store.save(mm)

    reloaded = store.load("matter-123")
    assert reloaded.forward["ramesh kumar"] == "PARTY_A"

    # A second mask call against the reloaded map reuses the same placeholder.
    masked_again = mask_text("Ramesh Kumar again.", reloaded, [("PARTY", "Ramesh Kumar")])
    assert "PARTY_A" in masked_again
    assert "PARTY_B" not in masked_again
