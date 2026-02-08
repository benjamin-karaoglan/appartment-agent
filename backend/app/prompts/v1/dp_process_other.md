---
name: Document Processor - Process Other
version: v1
description: Prompt for processing miscellaneous property documents with structured extraction
---

You are analyzing a property-related document that doesn't fit the standard categories (PV AG, diagnostics, tax, charges): {filename}

This may be a règlement de copropriété, état descriptif de division, contrat de syndic, assurance MRH, état daté, contrat de vente, prêt immobilier, or any other property-related document.

Read the entire document carefully and extract all relevant information.

Return a JSON object with this exact structure:

{{
  "summary": "Detailed summary of the document content and purpose (3-5 sentences). What is this document, what does it cover, and what are the key takeaways?",
  "document_type_detail": "Specific type (e.g., 'Règlement de copropriété', 'État daté', 'Contrat de syndic', 'Assurance multirisque habitation', 'Compromis de vente', etc.)",
  "key_insights": [
    "Key insight 1 — most important takeaway from this document",
    "Key insight 2",
    "Key insight 3"
  ],
  "dates": {{
    "document_date": "YYYY-MM-DD or null",
    "effective_date": "YYYY-MM-DD or null",
    "expiry_date": "YYYY-MM-DD or null"
  }},
  "financial_obligations": [
    {{
      "description": "Description of the financial obligation",
      "amount": 0.0,
      "frequency": "one-time/monthly/quarterly/annual/other",
      "notes": "Additional context"
    }}
  ],
  "legal_implications": [
    "Legal implication 1 — e.g., servitudes, restrictions on use, obligations",
    "Legal implication 2"
  ],
  "property_details": {{
    "address": "Property address if mentioned, or null",
    "lot_numbers": ["Lot numbers if mentioned"],
    "tantièmes": "Tantièmes share if mentioned, or null",
    "usage_restrictions": ["Any usage restrictions noted"]
  }},
  "buyer_perspective": "What does this document mean for a potential buyer? Any obligations, restrictions, or financial commitments to be aware of?",
  "estimated_annual_cost": 0.0,
  "one_time_costs": 0.0,
  "confidence_score": 0.85,
  "confidence_reasoning": "Explain data quality: was the document type clearly identifiable? Were financial amounts unambiguous? Was the document complete or were pages missing?"
}}

Rules:

- Identify the exact type of document and set `document_type_detail` accordingly
- Extract all financial amounts mentioned, categorized by frequency
- Note any legal restrictions, servitudes, or obligations that would affect a buyer
- `estimated_annual_cost` should reflect any recurring costs identified in the document
- `one_time_costs` should reflect any one-time payments or fees identified
- For règlement de copropriété: focus on usage rules, répartition des charges, and any special clauses
- For état daté: focus on charges arrears, ongoing travaux, and litigation

IMPORTANT: Generate all text output (summary, key_insights, financial_obligations, legal_implications, buyer_perspective) in {output_language}.
Return ONLY the JSON object, no surrounding text or markdown.
