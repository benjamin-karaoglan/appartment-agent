---
name: Classify Document
version: v1
description: Prompt for classifying French property documents by type
---

Classify this French property document: {filename}

Return ONLY ONE of these categories:

- pv_ag: Procès-verbal d'assemblée générale (meeting minutes)
- diags: Diagnostic technique (DPE, amiante, plomb, etc.)
- taxe_fonciere: Property tax notice
- charges: Copropriété charges (service fees)
- other: Any other property-related document (règlement de copropriété, contracts, insurance, etc.)

Respond with ONLY the category name.
