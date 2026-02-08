---
name: Classify Document
version: v1
description: Prompt for classifying French property documents by type
---

Classify this French property document: {filename}

Look at the content and structure of the document to determine its category.

Return ONLY ONE of these categories:

- pv_ag: Procès-verbal d'assemblée générale (AG meeting minutes — contains resolutions, votes, attendees list, syndic reports)
- diags: Dossier de diagnostic technique (DDT) or individual diagnostic reports (DPE, amiante, plomb, termites, gaz, électricité, ERP, mesurage Carrez). A single PDF may contain multiple diagnostics bundled together.
- taxe_fonciere: Property tax notice (taxe foncière — contains tax amounts, cadastral references, due dates)
- charges: Copropriété charges / appels de fonds / relevé de charges (quarterly or annual fee statements with category breakdowns)
- other: Any other property-related document (règlement de copropriété, contracts, insurance, loan agreements, état daté, etc.)

Respond with ONLY the category name, nothing else.
