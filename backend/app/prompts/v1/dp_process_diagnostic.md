---
name: Document Processor - Process Diagnostic
version: v1
description: Prompt for processing DDT/diagnostic documents with per-diagnostic breakdown and detailed findings
---

You are analyzing a Dossier de Diagnostic Technique (DDT) or diagnostic report for a French property: {filename}

This PDF may contain MULTIPLE diagnostics bundled together (DPE, plomb/CREP, amiante, électricité, gaz, termites, ERP, mesurage Carrez/loi Boutin). Read the entire document and extract findings for EACH diagnostic present.

For each diagnostic found, extract:

- The specific type and date of the diagnostic
- Key findings and measurements
- Anomalies, risks, or issues identified
- Validity date for the "vente" context
- Whether works are required, recommended, or informational only

Return a JSON object with this exact structure:

{{
  "summary": "Overview of the DDT (3-5 sentences). Mention which diagnostics are included, the property address, surface area, and the most critical findings.",
  "subcategory": "DDT (if multiple diagnostics) or specific type if single (DPE/amiante/plomb/electricite/gaz/termites)",
  "property_address": "Full address if found, or null",
  "property_surface": "Surface in m² (Carrez or habitable) if found, or null",
  "diagnostic_date": "YYYY-MM-DD (main date or earliest date) or null",
  "key_insights": [
    "Most important finding 1 — be specific with numbers/ratings",
    "Most important finding 2",
    "Most important finding 3"
  ],
  "diagnostics": [
    {{
      "type": "DPE",
      "date": "YYYY-MM-DD or null",
      "validity_date": "YYYY-MM-DD or null",
      "energy_rating": "A-G letter or null",
      "energy_consumption_kwh": 0.0,
      "ghg_rating": "A-G letter or null",
      "ghg_emissions_kg": 0.0,
      "estimated_annual_energy_cost": "Range or amount in € if available, or null",
      "findings": ["Key finding 1", "Key finding 2"],
      "status": "satisfactory/anomalies/not_performed"
    }},
    {{
      "type": "plomb_CREP",
      "date": "YYYY-MM-DD or null",
      "validity_date": "YYYY-MM-DD or null",
      "lead_presence": true,
      "class_3_count": 0,
      "class_2_count": 0,
      "class_1_count": 0,
      "total_units_tested": 0,
      "risk_situation": false,
      "findings": ["e.g., '30 unités en classe 3 sur 141 — situation de risque signalée'"],
      "status": "satisfactory/anomalies/risk_situation"
    }},
    {{
      "type": "electricite",
      "date": "YYYY-MM-DD or null",
      "validity_date": "YYYY-MM-DD or null",
      "anomalies_count": 0,
      "anomalies_list": ["Specific anomaly 1", "Specific anomaly 2"],
      "findings": ["Summary of electrical state"],
      "status": "satisfactory/anomalies"
    }},
    {{
      "type": "gaz",
      "date": "YYYY-MM-DD or null",
      "validity_date": "YYYY-MM-DD or null",
      "anomalies_list": ["Specific anomaly 1"],
      "danger_immediat": false,
      "findings": ["Summary of gas installation state"],
      "status": "satisfactory/anomalies/danger_immediat"
    }},
    {{
      "type": "amiante",
      "date": "YYYY-MM-DD or null",
      "validity_date": "YYYY-MM-DD or null (illimité si absence)",
      "asbestos_presence": false,
      "materials_found": ["Material 1 if any"],
      "findings": ["Summary"],
      "status": "satisfactory/presence/not_accessible"
    }},
    {{
      "type": "termites",
      "date": "YYYY-MM-DD or null",
      "validity_date": "YYYY-MM-DD or null",
      "termite_presence": false,
      "findings": ["Summary"],
      "status": "satisfactory/presence"
    }},
    {{
      "type": "ERP",
      "date": "YYYY-MM-DD or null",
      "seismic_zone": "1-5 or null",
      "findings": ["Summary of natural/technological risks"],
      "status": "satisfactory/risks_identified"
    }},
    {{
      "type": "mesurage",
      "date": "YYYY-MM-DD or null",
      "surface_carrez_m2": 0.0,
      "surface_non_counted_m2": 0.0,
      "findings": ["Surface details"],
      "status": "completed"
    }}
  ],
  "required_works": [
    {{
      "diagnostic_source": "plomb/electricite/gaz/etc.",
      "description": "What must be done (regulatory obligation)",
      "urgency": "immediate/before_sale/within_period",
      "estimated_cost_range": "Estimated cost range if inferrable, or null"
    }}
  ],
  "recommended_works": [
    {{
      "diagnostic_source": "DPE/electricite/etc.",
      "description": "What is recommended but not mandatory",
      "estimated_cost_range": "Estimated cost range if inferrable, or null"
    }}
  ],
  "buyer_perspective": "What does this DDT mean for a buyer? What are the priority items to budget for? Which findings could affect ability to rent the property (e.g., indecent housing criteria, DPE F/G rental ban)?",
  "issues_found": ["Consolidated list of all issues across all diagnostics"],
  "recommendations": ["Consolidated list of recommended actions"],
  "estimated_annual_cost": 0.0,
  "one_time_costs": 0.0,
  "confidence_score": 0.85,
  "confidence_reasoning": "Explain data quality: how many diagnostics were present? Were any 'not performed'? Were measurement values clear? Were any parts of the property inaccessible? Were validity dates still current?"
}}

Rules:

- Only include diagnostic types that are actually present in the document
- If a diagnostic was "not performed" (mission non réalisée), include it with status "not_performed" and note why
- For plomb, count the actual class 3/2/1 units from the detailed tables if available
- For DPE, extract the exact kWh/m²/an and kg CO₂/m²/an values
- For electricity, list each specific anomaly type (terre, différentiel, liaison équipotentielle, etc.)
- `estimated_annual_cost` should reflect any energy cost estimates from the DPE
- `one_time_costs` should estimate total remediation costs if the document provides enough data, otherwise 0.0
- Note any parts of the property that were not accessible during diagnostics

IMPORTANT: Generate all text output (summary, key_insights, findings, buyer_perspective, etc.) in {output_language}.
Return ONLY the JSON object, no surrounding text or markdown.
