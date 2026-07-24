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
