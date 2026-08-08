from __future__ import annotations

from typing import Any

# Externalized Pecuniary Jurisdiction Threshold Rules by State
STATE_PECUNIARY_LIMITS: dict[str, list[dict[str, Any]]] = {
    "Delhi": [
        {
            "forum_name": "Civil Judge Court, Delhi",
            "court_category": "District Courts",
            "max_val": 20_00_000,  # Up to 20 Lakhs
            "min_val": 0,
            "provisions": ["Section 6 CPC 1908", "Delhi Civil Courts Act, 1912"],
            "notes": "Pecuniary jurisdiction up to INR 20 Lakhs.",
        },
        {
            "forum_name": "District Court / Addl. District Judge, Delhi",
            "court_category": "District Courts",
            "max_val": 2_00_00_000,  # 20 Lakhs to 2 Crores
            "min_val": 20_00_001,
            "provisions": ["Delhi High Court (Amendment) Act, 2015", "Delhi Civil Courts Act, 1912"],
            "notes": "Pecuniary jurisdiction between INR 20 Lakhs and INR 2 Crores.",
        },
        {
            "forum_name": "High Court of Delhi (Ordinary Original Civil Jurisdiction)",
            "court_category": "High Court",
            "max_val": float("inf"),
            "min_val": 2_00_00_001,  # Above 2 Crores
            "provisions": ["Section 5(2) Delhi High Court Act, 1966", "Delhi High Court (Amendment) Act, 2015"],
            "notes": "Ordinary Original Civil Jurisdiction for suits valued above INR 2 Crores.",
        },
    ],
    "Maharashtra": [
        {
            "forum_name": "Civil Judge Junior Division (CJJD), Maharashtra",
            "court_category": "District Courts",
            "max_val": 5_00_000,  # Up to 5 Lakhs
            "min_val": 0,
            "provisions": ["Section 24 Maharashtra Civil Courts Act"],
            "notes": "Suits valued up to INR 5 Lakhs.",
        },
        {
            "forum_name": "Civil Judge Senior Division (CJSD) / District Court, Maharashtra",
            "court_category": "District Courts",
            "max_val": float("inf"),
            "min_val": 5_00_001,
            "provisions": ["Section 24 Maharashtra Civil Courts Act"],
            "notes": "Unlimited pecuniary jurisdiction for suits exceeding INR 5 Lakhs.",
        },
    ],
    "Karnataka": [
        {
            "forum_name": "Civil Judge Junior Division, Karnataka",
            "court_category": "District Courts",
            "max_val": 5_00_000,
            "min_val": 0,
            "provisions": ["Karnataka Civil Courts Act, 1964"],
            "notes": "Pecuniary jurisdiction up to INR 5 Lakhs.",
        },
        {
            "forum_name": "Civil Judge Senior Division, Karnataka",
            "court_category": "District Courts",
            "max_val": 10_00_000,
            "min_val": 5_00_001,
            "provisions": ["Karnataka Civil Courts Act, 1964"],
            "notes": "Pecuniary jurisdiction between INR 5 Lakhs and INR 10 Lakhs.",
        },
        {
            "forum_name": "District Court, Karnataka",
            "court_category": "District Courts",
            "max_val": float("inf"),
            "min_val": 10_00_001,
            "provisions": ["Karnataka Civil Courts Act, 1964"],
            "notes": "Pecuniary jurisdiction above INR 10 Lakhs.",
        },
    ],
    "DEFAULT": [
        {
            "forum_name": "Civil Judge Junior Division",
            "court_category": "District Courts",
            "max_val": 5_00_000,
            "min_val": 0,
            "provisions": ["Section 6, Code of Civil Procedure, 1908"],
            "notes": "General pecuniary jurisdiction up to INR 5 Lakhs.",
        },
        {
            "forum_name": "Civil Judge Senior Division",
            "court_category": "District Courts",
            "max_val": 20_00_000,
            "min_val": 5_00_001,
            "provisions": ["Section 15, Code of Civil Procedure, 1908"],
            "notes": "General pecuniary jurisdiction between INR 5 Lakhs and INR 20 Lakhs.",
        },
        {
            "forum_name": "District Court",
            "court_category": "District Courts",
            "max_val": float("inf"),
            "min_val": 20_00_001,
            "provisions": ["Section 15, Code of Civil Procedure, 1908"],
            "notes": "General pecuniary jurisdiction exceeding INR 20 Lakhs.",
        },
    ],
}


def determine_forum(
    suit_type: str,
    claim_value_inr: float,
    jurisdiction_state: str,
    defendant_residence_state: str | None = None,
    cause_of_action_location: str | None = None,
    property_location_state: str | None = None,
) -> dict[str, Any]:
    """Deterministically calculate recommended forum, territorial & pecuniary jurisdiction under CPC 1908 and State Rules."""

    viable_options: list[dict[str, Any]] = []
    assumptions: list[str] = []
    is_unambiguous = True

    # 1. Specialized Forum Evaluation (RERA / Commercial Courts)
    if suit_type == "RERA" or suit_type == "Real Estate":
        viable_options.append(
            {
                "forum_name": f"Real Estate Regulatory Authority (RERA), {jurisdiction_state}",
                "court_category": "Special Tribunal",
                "territorial_basis": f"Real estate project location in {property_location_state or jurisdiction_state}",
                "pecuniary_basis": "No pecuniary limit for statutory real estate developer/allottee disputes",
                "governing_provisions": ["Section 31, Real Estate (Regulation and Development) Act, 2016"],
                "confidence": "Deterministic",
                "assumptions": ["Assumes real estate project is registered or registrable under RERA Act."],
            }
        )

    commercial_court_added = False
    if suit_type == "Commercial Dispute" and claim_value_inr >= 3_00_000:
        viable_options.append(
            {
                "forum_name": f"Designated Commercial Court / Commercial Division, {jurisdiction_state}",
                "court_category": "Commercial Court",
                "territorial_basis": f"Cause of action or commercial transaction in {cause_of_action_location or jurisdiction_state}",
                "pecuniary_basis": f"Specified Value INR {claim_value_inr:,.2f} meets minimum threshold of INR 3 Lakhs",
                "governing_provisions": ["Section 2(1)(i) & Section 6, Commercial Courts Act, 2015"],
                "confidence": "Deterministic",
                "assumptions": ["Assumes dispute qualifies as a Commercial Dispute under Section 2(1)(c) Commercial Courts Act."],
            }
        )
        commercial_court_added = True

    # 2. General Civil Forum Evaluation via Pecuniary Rules
    state_rules = STATE_PECUNIARY_LIMITS.get(jurisdiction_state, STATE_PECUNIARY_LIMITS["DEFAULT"])
    matching_pecuniary_rule = None
    for rule in state_rules:
        if rule["min_val"] <= claim_value_inr <= rule["max_val"]:
            matching_pecuniary_rule = rule
            break

    if not matching_pecuniary_rule:
        matching_pecuniary_rule = state_rules[-1]

    # Territorial Basis Logic
    territorial_basis = ""
    provisions: list[str] = list(matching_pecuniary_rule["provisions"])

    if suit_type in ("Property Dispute", "Possession"):
        prop_state = property_location_state or jurisdiction_state
        territorial_basis = f"Immovable property situated within local limits of {prop_state}"
        provisions.append("Section 16(a)-(d), Code of Civil Procedure, 1908")
        if property_location_state and defendant_residence_state and property_location_state != defendant_residence_state:
            assumptions.append(f"Property is located in {property_location_state} while defendant resides in {defendant_residence_state}. Section 16 CPC mandates suit at property location.")
    else:
        territorial_basis = f"Cause of action arose in {cause_of_action_location or jurisdiction_state}"
        provisions.append("Section 20(c), Code of Civil Procedure, 1908")

        if defendant_residence_state and defendant_residence_state != jurisdiction_state:
            is_unambiguous = False
            assumptions.append(
                f"Defendant resides in {defendant_residence_state} whereas cause of action arose in {jurisdiction_state}. "
                "Plaintiff may elect to file under Section 20(a) CPC at defendant's residence or Section 20(c) CPC at cause of action location."
            )
            # Add secondary forum option at defendant's residence
            def_state_rules = STATE_PECUNIARY_LIMITS.get(defendant_residence_state, STATE_PECUNIARY_LIMITS["DEFAULT"])
            def_pec_rule = def_state_rules[0]
            for r in def_state_rules:
                if r["min_val"] <= claim_value_inr <= r["max_val"]:
                    def_pec_rule = r
                    break
            viable_options.append(
                {
                    "forum_name": f"{def_pec_rule['forum_name']} ({defendant_residence_state})",
                    "court_category": def_pec_rule["court_category"],
                    "territorial_basis": f"Defendant resides or carries on business in {defendant_residence_state}",
                    "pecuniary_basis": f"Claim value INR {claim_value_inr:,.2f} under {defendant_residence_state} state rules",
                    "governing_provisions": list(def_pec_rule["provisions"]) + ["Section 20(a), Code of Civil Procedure, 1908"],
                    "confidence": "Manual Review Required",
                    "assumptions": ["Alternative forum based on defendant residence."],
                }
            )

    civil_option = {
        "forum_name": matching_pecuniary_rule["forum_name"],
        "court_category": matching_pecuniary_rule["court_category"],
        "territorial_basis": territorial_basis,
        "pecuniary_basis": f"Claim value INR {claim_value_inr:,.2f} evaluated under {jurisdiction_state} pecuniary thresholds",
        "governing_provisions": provisions,
        "confidence": "Deterministic" if is_unambiguous else "Manual Review Required",
        "assumptions": assumptions if assumptions else ["Assumes cause of action arose within specified court jurisdiction."],
    }

    if suit_type in ("RERA", "Real Estate") or commercial_court_added:
        # A specialized forum (RERA tribunal, or a Commercial Court once the
        # Commercial Courts Act threshold is met) takes precedence over the
        # general civil option — append rather than insert-at-0, so the
        # specialized forum stays index 0 / recommended (TICKET-6: this
        # branch previously excluded the Commercial Court case, so
        # civil_option was inserted ahead of an already-qualifying
        # Commercial Court and always won the recommendation; see
        # docs/30_Implementation/Acceptance_Testing/Sprint_3.5.3_Acceptance_Testing_Guide.md
        # scenarios COM-01/COM-02/COM-03/IA-03).
        viable_options.append(civil_option)
    else:
        # No specialized forum in play — civil option is primary.
        viable_options.insert(0, civil_option)

    recommended_forum = viable_options[0]

    return {
        "recommended_forum": recommended_forum,
        "viable_options": viable_options,
        "is_unambiguous": is_unambiguous,
        "notice": "Rule-based statutory jurisdiction calculation under CPC 1908 & State Rules. Advocate vetting required.",
    }
