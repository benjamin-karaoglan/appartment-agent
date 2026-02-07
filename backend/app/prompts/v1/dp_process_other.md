---
name: Document Processor - Process Other
version: v1
description: Prompt for processing miscellaneous property documents in the document processor pipeline
---

Analyze this property-related document: {filename}

This document does not fit standard categories (PV AG, diagnostics, tax, charges). It may be a règlement de copropriété, insurance policy, contract, loan agreement, or other property-related document.

Extract JSON:
{{
  "summary": "Brief summary of the document content and purpose",
  "key_insights": ["insight1", "insight2"],
  "document_type_detail": "Specific type (e.g. règlement de copropriété, contrat, assurance, etc.)",
  "financial_obligations": ["obligation1", "obligation2"],
  "legal_implications": ["implication1", "implication2"],
  "estimated_annual_cost": 0.0,
  "one_time_costs": 0.0
}}

IMPORTANT: Generate all text output (summary, key_insights, financial_obligations, legal_implications) in {output_language}.
