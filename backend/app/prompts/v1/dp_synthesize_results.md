---
name: Document Processor - Synthesize Results
version: v1
description: Prompt for synthesizing results from multiple processed documents with cross-document analysis
---

You are synthesizing the analysis results from multiple property documents to produce a comprehensive buyer assessment.

Here are the detailed results from each document:

{summaries}

Analyze ALL the document results above and produce a cross-document synthesis. Look for:

- **Recurring themes** across multiple PV AG (e.g., humidity issues discussed every year, deferred works finally adopted)
- **Financial exposure**: total known costs from voted works, upcoming appels de fonds, annual charges + taxes
- **Technical state**: what do the diagnostics reveal about the property's condition?
- **Trajectory**: is the copropriété investing in maintenance or deferring problems?

Return a JSON object with this exact structure:

{{
  "summary": "Comprehensive overview (5-8 sentences) covering: the overall state of the property and copropriété, the main financial commitments, critical findings from diagnostics, and the general trajectory (improving, stable, deteriorating).",
  "total_annual_costs": 0.0,
  "annual_cost_breakdown": {{
    "charges_copropriete": {{ "amount": 0.0, "source": "document name or null", "note": "calculation explanation or null" }},
    "taxe_fonciere": {{ "amount": 0.0, "source": "document name or null", "note": "calculation explanation or null" }},
    "estimated_energy": {{ "amount": 0.0, "source": "document name or null", "note": "calculation explanation or null" }},
    "fonds_travaux": {{ "amount": 0.0, "source": "document name or null", "note": "calculation explanation or null" }},
    "other_recurring": {{ "amount": 0.0, "source": "document name or null", "note": "calculation explanation or null" }}
  }},
  "total_one_time_costs": 0.0,
  "one_time_cost_breakdown": [
    {{
      "description": "Description of the one-time cost",
      "amount": 0.0,
      "year": 2024,
      "cost_type": "copro",
      "payment_status": "unpaid",
      "source": "Which document this comes from",
      "status": "estimated"
    }}
  ],
  "risk_level": "low/medium/high",
  "risk_factors": [
    "Specific risk factor 1 with context",
    "Specific risk factor 2"
  ],
  "cross_document_themes": [
    {{
      "theme": "Theme name (e.g., 'Humidité et réseaux en sous-sol')",
      "documents_involved": ["PV AG 2022", "PV AG 2023", "PV AG 2024"],
      "evolution": "How this theme evolved across documents (e.g., 'First identified in 2022, studied in 2023, works voted in 2024')",
      "current_status": "Current state of this issue"
    }}
  ],
  "key_findings": [
    "Most critical finding 1 — be specific with amounts and sources",
    "Critical finding 2",
    "Critical finding 3",
    "Critical finding 4",
    "Critical finding 5"
  ],
  "buyer_action_items": [
    {{
      "priority": 1,
      "action": "What the buyer should do (e.g., 'Budget 150k€ for toiture works — appels de fonds in progress')",
      "urgency": "immediate/short_term/medium_term",
      "estimated_cost": 0.0
    }}
  ],
  "recommendations": [
    "Strategic recommendation 1 for the buyer",
    "Strategic recommendation 2",
    "Strategic recommendation 3"
  ],
  "confidence_score": 0.85,
  "confidence_reasoning": "Explain the quality and completeness of the data: how many documents were analyzed, whether key document types are missing (e.g., no charges doc means annual costs are incomplete), whether amounts could be verified across documents.",
  "tantiemes_info": {{
    "lot_tantiemes": 150,
    "total_tantiemes": 10000,
    "share_percentage": 1.5,
    "cost_share_note": "Explanation of how costs are split based on tantièmes share (e.g., 'Le lot représente 150/10000 tantièmes soit 1.5% des charges générales'). Set all fields to null if no tantièmes data found in any document."
  }}
}}

Rules:

- Cross-reference documents: if a PV AG mentions voted works, check if they appear in charges documents as appels de fonds
- Sum up ALL annual costs from individual documents for `total_annual_costs`
- **TAXE FONCIÈRE IS MANDATORY**: If ANY document of type `taxe_fonciere` is present in the input, the `annual_cost_breakdown.taxe_fonciere.amount` MUST be greater than 0. Extract the total tax amount from the document's `estimated_annual_cost` or `extracted_data.tax_breakdown`. NEVER leave taxe_fonciere at 0 when a tax document exists — this is the single most important annual cost for a buyer.
- Sum up ALL **unpaid** one-time costs for `total_one_time_costs` (exclude items with payment_status "paid")
- `one_time_cost_breakdown[].status` MUST be exactly one of: `voted`, `estimated`, or `upcoming`. No other values are allowed. Use `voted` ONLY for items explicitly voted/approved at an Assemblée Générale (AG). Use `upcoming` for planned/future works discussed but not yet voted. Use `estimated` for everything else — including ALL items derived from DDT/diagnostic documents (DPE, plomb, amiante, électricité, gaz), which are technical assessments and recommendations, NOT AG votes.
- `one_time_cost_breakdown[].year`: the year the cost applies to (when the work is scheduled or was voted). Use the actual year (e.g. 2023, 2024), not 0.
- `one_time_cost_breakdown[].cost_type` MUST be exactly `"copro"` or `"direct"`. Use `"copro"` for building-wide works voted at AG (shared among all co-owners by tantièmes). Use `"direct"` for costs specific to the apartment/lot only (e.g., rénovation énergétique appartement from DDT, individual unit repairs, owner-only obligations). DDT items that mention "Appartement" are direct costs.
- **DDT/DIAGNOSTIC COST ESTIMATION**: Items from diagnostic documents (DPE, plomb, électricité, gaz, amiante) often identify required works without explicit cost figures. You MUST provide realistic cost estimates based on the diagnostic findings and common French market rates for apartment remediation. For example: DPE energy renovation (5 000–30 000 € depending on DPE class and scope), lead remediation (2 000–10 000 €), electrical compliance (3 000–8 000 €), gas compliance (1 000–5 000 €), asbestos investigation/removal (5 000–25 000 €). NEVER set amount to 0 for a DDT item that identifies required work — always provide a reasonable mid-range estimate and set status to "estimated".
- `one_time_cost_breakdown[].payment_status` MUST be exactly one of: `paid`, `partially_paid`, or `unpaid`. Determine this from context: if a PV AG reports that works were completed and paid in full, mark as `paid`. If appels de fonds are still in progress, mark as `partially_paid`. If not yet started or no evidence of payment, mark as `unpaid`.
- **TEMPORAL FILTERING**: Determine the reference year from the most recent document date. Only include one-time costs that are NOT fully paid. A buyer inherits unpaid obligations — do NOT include works that were completed and fully settled in prior years. Focus on: ongoing appels de fonds (partially_paid), recently voted works not yet paid (unpaid), and upcoming/planned works (unpaid).
- `annual_cost_breakdown` values MUST be objects with `amount` (number), `source` (string or null — the document name this figure comes from), and `note` (string or null — brief explanation of how the amount was determined). Set `source`/`note` to null when unknown. For annual costs, prefer the figures from the most recent document available.
- Risk level: "high" if major works voted + diagnostic issues + high financial exposure; "medium" if some issues but manageable; "low" if property is well-maintained with no major concerns
- Priority-rank the buyer action items (1 = most urgent)
- Be specific with euro amounts — never say "significant costs" when you can say "≈150 904 € TTC"
- Identify patterns across years (e.g., if humidity appears in 3 consecutive PV AGs)
- `confidence_score`: 0.0 to 1.0 reflecting data completeness. 1.0 = all major document types present with clear data. Deduct for missing categories, ambiguous amounts, or single-source data.
- `tantiemes_info`: Extract tantièmes primarily from PV d'AG documents — they contain the répartition des charges showing each lot's tantièmes and the building total. When multiple PV d'AG are present, use the MOST RECENT one as ground truth (tantièmes can change after modifications). Charges documents may also contain this info. Calculate share_percentage = (lot_tantiemes / total_tantiemes) × 100. Set all sub-fields to null if no tantièmes data found.

CRITICAL: You MUST produce the COMPLETE JSON with ALL fields listed above. Do not stop early. Do not truncate. Every field must be present in the output, even if its value is an empty array or null.

IMPORTANT: Generate all text output (summary, key_findings, recommendations, themes, action items) in {output_language}.
Return ONLY the JSON object, no surrounding text or markdown.
