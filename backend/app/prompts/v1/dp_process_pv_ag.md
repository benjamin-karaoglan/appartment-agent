---
name: Document Processor - Process PV AG
version: v1
description: Prompt for processing PV d'AG documents with detailed extraction of resolutions, costs, and buyer-perspective analysis
---

You are analyzing a Procès-Verbal d'Assemblée Générale (PV AG) for a French copropriété: {filename}

Read the entire document carefully. Extract every resolution (résolution) discussed, including its number, topic, financial amount if any, and whether it was adopted or rejected.

Pay special attention to:

- **Financial decisions**: exact euro amounts (TTC when available), payment schedules, appels de fonds
- **Major works** (gros travaux): toiture, ravalement, réseaux, ascenseur, etc.
- **Recurring issues**: humidity, plumbing, security, common areas maintenance
- **Syndic management**: fees, contract renewal, special honoraires for works
- **Fonds travaux (Alur)**: annual contribution amounts and any special allocations

Return a JSON object with this exact structure:

{{
  "summary": "Detailed summary of the AG (3-5 sentences). Include the date, type (AGO/AGE), number of resolutions, and main themes discussed.",
  "meeting_date": "YYYY-MM-DD or null",
  "meeting_type": "AGO/AGE/AGO+AGE",
  "attendance": "Quorum information if available (e.g., '65% des tantièmes représentés')",
  "key_insights": [
    "Key insight 1 — include specific euro amounts where relevant",
    "Key insight 2",
    "Key insight 3"
  ],
  "decisions": [
    {{
      "resolution_number": "1 (or the resolution identifier)",
      "topic": "Description of what was voted on",
      "amount_ttc": 0.0,
      "status": "adopted/rejected/deferred",
      "vote_details": "majority info if available (e.g., 'unanimité', 'majorité art.24')",
      "payment_schedule": "Description of appels de fonds schedule if applicable, or null"
    }}
  ],
  "major_works": [
    {{
      "description": "Nature of the major work",
      "amount_ttc": 0.0,
      "status": "adopted/rejected/deferred/completed",
      "timeline": "Expected or actual timeline",
      "funding": "How it's financed (fonds travaux, appels de fonds, emprunt collectif, etc.)"
    }}
  ],
  "recurring_issues": [
    "Issue that appears to be ongoing or mentioned as previously discussed (e.g., 'Humidité en sous-sol — suivi depuis AG précédente')"
  ],
  "buyer_perspective": "Analysis from a potential buyer's perspective: what financial exposure does this AG create? Are there upcoming appels de fonds? Major works that will impact charges? Issues that suggest future costs?",
  "estimated_annual_cost": 0.0,
  "one_time_costs": [
    {{
      "description": "Description of the one-time cost",
      "amount": 0.0
    }}
  ],
  "tantiemes_info": {{
    "lot_tantiemes": null,
    "total_tantiemes": null,
    "share_percentage": null,
    "cost_share_note": "Extract tantièmes data if present in the convocation or feuille de présence (e.g., 'Lot 42: 150/10000 tantièmes'). Set all to null if not found."
  }},
  "confidence_score": 0.85,
  "confidence_reasoning": "Explain data quality: was the PDF readable? Were all resolutions clearly listed? Were amounts unambiguous? Were any pages missing or illegible?"
}}

Rules:

- For `estimated_annual_cost`, include only recurring annual impacts (e.g., increased charges, fonds travaux contributions)
- For `one_time_costs`, list each significant voted expenditure separately with its amount TTC
- If amounts are given HT, convert to TTC (×1.20 for 20% TVA) and note "estimé TTC"
- Always prefer exact amounts from the document over estimates
- If a resolution has no financial impact, set amount_ttc to 0.0
- Include ALL resolutions, not just financial ones

IMPORTANT: Generate all text output (summary, key_insights, decisions, buyer_perspective, etc.) in {output_language}.
Return ONLY the JSON object, no surrounding text or markdown.
