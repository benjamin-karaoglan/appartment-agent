---
name: Document Processor - Process Charges
version: v1
description: Prompt for processing copropriété charges documents with detailed category breakdown
---

You are analyzing a copropriété charges document (appel de fonds, relevé de charges, décompte annuel) for a French property: {filename}

Read the entire document carefully. Extract every charge category, the period covered, and all financial details.

Return a JSON object with this exact structure:

{{
  "summary": "Summary of the charges document (2-3 sentences). Include the period, total amount, and main cost categories.",
  "key_insights": [
    "Key insight 1 — e.g., largest cost category and its amount",
    "Key insight 2 — e.g., notable charges or changes",
    "Key insight 3"
  ],
  "period": "Period covered (e.g., 'T1 2024', 'Année 2024', '01/01/2024 - 31/03/2024')",
  "period_type": "quarterly/annual/other",
  "total_amount": 0.0,
  "lot_reference": "Lot number(s) or tantièmes if mentioned, or null",
  "breakdown": [
    {{
      "category": "Category name (e.g., 'Entretien parties communes', 'Chauffage', 'Ascenseur', 'Eau froide', 'Gardiennage', 'Assurance', 'Honoraires syndic')",
      "amount": 0.0,
      "type": "general/special"
    }}
  ],
  "charges_generales": 0.0,
  "charges_speciales": 0.0,
  "fonds_travaux_alur": 0.0,
  "provisions_called": 0.0,
  "actual_expenses": 0.0,
  "balance": 0.0,
  "annualized_total": 0.0,
  "buyer_perspective": "What this means for a buyer: expected monthly/quarterly charges, any unusually high categories, trend indicators.",
  "estimated_annual_cost": 0.0,
  "one_time_costs": 0.0,
  "tantiemes_info": {{
    "lot_tantiemes": null,
    "total_tantiemes": null,
    "share_percentage": null,
    "cost_share_note": "Extract tantièmes from the charges document header or breakdown (e.g., 'Lot 12 — 250/10000 tantièmes généraux'). Charges documents almost always include tantièmes. Set all to null if not found."
  }},
  "confidence_score": 0.85,
  "confidence_reasoning": "Explain data quality: was the breakdown complete? Were amounts clearly stated? Could you distinguish provisions from actual expenses? Was the period clearly identified?"
}}

Rules:

- If the document covers a quarter, calculate `annualized_total` = total × 4. If it covers a semester, × 2. If annual, use as-is.
- `estimated_annual_cost` should be the annualized total charges amount
- `one_time_costs` should be 0.0 unless there are exceptional one-time charges listed
- Separate charges générales from charges spéciales if the document distinguishes them
- Include the fonds travaux (Alur) contribution if shown separately
- If the document shows both provisions (called) and actual expenses (dépensées), include both and calculate the balance (surplus or deficit)
- List every category visible in the breakdown, even small ones

IMPORTANT: Generate all text output (summary, key_insights, buyer_perspective, etc.) in {output_language}.
Return ONLY the JSON object, no surrounding text or markdown.
