---
name: Document Processor - Process Tax
version: v1
description: Prompt for processing taxe foncière documents with detailed breakdown
---

You are analyzing a Taxe Foncière (property tax notice) for a French property: {filename}

Read the entire document carefully and extract all financial details, property references, and tax breakdown components.

Return a JSON object with this exact structure:

{{
  "summary": "Summary of the tax notice (2-3 sentences). Include the tax year, property identification, total amount, and any notable changes or exemptions.",
  "key_insights": [
    "Key insight 1 — e.g., total tax amount and year-over-year trend if visible",
    "Key insight 2 — e.g., any exemptions or special situations",
    "Key insight 3"
  ],
  "tax_year": "YYYY or null",
  "property_reference": "Cadastral reference if available, or null",
  "property_address": "Address from the tax notice, or null",
  "total_amount": 0.0,
  "tax_breakdown": {{
    "commune": 0.0,
    "intercommunalite": 0.0,
    "departement": 0.0,
    "taxe_ordures_menageres": 0.0,
    "taxes_speciales": 0.0,
    "frais_gestion": 0.0
  }},
  "valeur_locative_cadastrale": 0.0,
  "due_date": "YYYY-MM-DD or null",
  "payment_schedule": [
    {{
      "date": "YYYY-MM-DD",
      "amount": 0.0,
      "type": "acompte/solde"
    }}
  ],
  "exemptions_or_reductions": ["Any exemptions, abatements, or reductions noted"],
  "buyer_perspective": "What this means for a buyer: annual tax burden, any temporary exemptions about to expire, comparison context if available.",
  "estimated_annual_cost": 0.0,
  "one_time_costs": 0.0,
  "confidence_score": 0.85,
  "confidence_reasoning": "Explain data quality: was the tax notice clearly readable? Were all breakdown components visible? Was the valeur locative cadastrale present? Is this a recent year?"
}}

Rules:

- `estimated_annual_cost` should equal the total tax amount (this is a recurring annual cost)
- `one_time_costs` should be 0.0 (taxes are recurring)
- Extract all breakdown components visible on the notice
- If some breakdown components are not visible, only include those that are
- Note the valeur locative cadastrale if shown (useful for estimating future tax changes)

IMPORTANT: Generate all text output (summary, key_insights, buyer_perspective, etc.) in {output_language}.
Return ONLY the JSON object, no surrounding text or markdown.
