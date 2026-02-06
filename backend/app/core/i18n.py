"""
Internationalization (i18n) module for the AppArt Agent backend.

Provides locale detection from Accept-Language header and bilingual
error messages / user-facing strings.
"""

from fastapi import Request

SUPPORTED_LOCALES = ("fr", "en")
DEFAULT_LOCALE = "fr"


def get_local(request: Request) -> str:
    """
    FastAPI dependency that reads the Accept-Language header and returns
    the best matching locale ('fr' or 'en'). Defaults to 'fr'.
    """
    accept = request.headers.get("accept-language", "")
    # Simple parsing: look for 'en' anywhere in the header
    for part in accept.split(","):
        lang = part.strip().split(";")[0].strip().lower()
        if lang.startswith("en"):
            return "en"
        if lang.startswith("fr"):
            return "fr"
    return DEFAULT_LOCALE


def get_output_language(locale: str) -> str:
    """Return the full language name for LLM prompt instructions."""
    return "English" if locale == "en" else "French"


# ---------------------------------------------------------------------------
# Bilingual message catalogue
# ---------------------------------------------------------------------------
MESSAGES: dict[str, dict[str, str]] = {
    # ── Auth / Users ──────────────────────────────────────────────────────
    "email_already_registered": {
        "fr": "Cette adresse email est déjà enregistrée",
        "en": "Email already registered",
    },
    "incorrect_credentials": {
        "fr": "Email ou mot de passe incorrect",
        "en": "Incorrect email or password",
    },
    "inactive_user": {
        "fr": "Compte utilisateur inactif",
        "en": "Inactive user",
    },
    "user_not_found": {
        "fr": "Utilisateur non trouvé",
        "en": "User not found",
    },
    "invalid_credentials": {
        "fr": "Impossible de valider les identifiants",
        "en": "Could not validate credentials",
    },
    "not_authenticated": {
        "fr": "Non authentifié",
        "en": "Not authenticated",
    },
    # ── Properties ────────────────────────────────────────────────────────
    "property_not_found": {
        "fr": "Bien non trouvé",
        "en": "Property not found",
    },
    "property_needs_price_surface": {
        "fr": "Le bien doit avoir un prix demandé et une surface pour l'analyse",
        "en": "Property must have asking_price and surface_area for analysis",
    },
    "no_comparable_sales": {
        "fr": (
            "Aucune vente comparable trouvée pour ce bien. "
            "Cela peut être dû à : (1) L'adresse n'est pas dans la base DVF, "
            "(2) Les données DVF sont incomplètes ou obsolètes, "
            "ou (3) Il n'y a pas de ventes récentes dans le secteur correspondant aux critères. "
            "Note : Les données DVF peuvent ne pas inclure toutes les ventes."
        ),
        "en": (
            "No comparable sales found for this property. "
            "This may be due to: (1) The property address is not in the DVF database, "
            "(2) The DVF data file is incomplete or outdated, "
            "or (3) There are no recent sales in the area matching the property criteria. "
            "Please note: DVF data may not include all sales and may lag behind official sources."
        ),
    },
    "no_exact_address_sales": {
        "fr": (
            "Aucune vente trouvée à l'adresse exacte {address}. "
            "Cela peut signifier : (1) Pas de vente récente à ce numéro, "
            "(2) L'adresse n'est pas dans la base DVF, ou (3) Les données sont incomplètes. "
            "Essayez l'« Analyse tendance » pour voir les ventes voisines et les projections."
        ),
        "en": (
            "No sales found at the exact address {address}. "
            "This could mean: (1) No recent sales at this specific building number, "
            "(2) The address is not in the DVF database, or (3) Sales data is incomplete. "
            "Try using 'Trend Analysis' instead to see neighboring sales and projected values. "
            "You can also import more recent DVF data from "
            "https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres/"
        ),
    },
    "no_comparable_sales_short": {
        "fr": "Aucune vente comparable trouvée",
        "en": "No comparable sales found",
    },
    "no_trend_sales": {
        "fr": "Aucune vente trouvée pour l'analyse tendance",
        "en": "No sales found for trend analysis",
    },
    # ── Documents ─────────────────────────────────────────────────────────
    "file_type_not_allowed": {
        "fr": "Le type de fichier {ext} n'est pas autorisé",
        "en": "File type {ext} not allowed",
    },
    "failed_read_file": {
        "fr": "Échec de la lecture du fichier : {error}",
        "en": "Failed to read file: {error}",
    },
    "failed_extract_pdf": {
        "fr": "Échec de l'extraction du texte du PDF : {error}",
        "en": "Failed to extract text from PDF: {error}",
    },
    "user_uuid_not_found": {
        "fr": "UUID utilisateur non trouvé",
        "en": "User UUID not found",
    },
    "failed_create_document": {
        "fr": "Échec de la création du document : {error}",
        "en": "Failed to create document record: {error}",
    },
    "document_not_found": {
        "fr": "Document non trouvé",
        "en": "Document not found",
    },
    "only_pdf_supported": {
        "fr": "Seuls les fichiers PDF sont supportés",
        "en": "Only PDF files are supported",
    },
    "only_pdf_pvag": {
        "fr": "Seuls les fichiers PDF sont supportés pour l'analyse PV d'AG",
        "en": "Only PDF files are supported for PV d'AG analysis",
    },
    "no_files_provided": {
        "fr": "Aucun fichier fourni",
        "en": "No files provided",
    },
    "max_files_exceeded": {
        "fr": "Maximum 50 fichiers par téléchargement groupé",
        "en": "Maximum 50 files per bulk upload",
    },
    "failed_start_processing": {
        "fr": "Échec du démarrage du traitement : {error}",
        "en": "Failed to start processing: {error}",
    },
    "bulk_upload_failed": {
        "fr": "Le téléchargement groupé a échoué : {error}",
        "en": "Bulk upload failed: {error}",
    },
    "workflow_not_found": {
        "fr": "Workflow non trouvé ou aucun document associé",
        "en": "Workflow not found or no documents associated",
    },
    "aggregation_not_supported": {
        "fr": "Agrégation non supportée pour la catégorie : {category}",
        "en": "Aggregation not supported for category: {category}",
    },
    "no_documents_to_aggregate": {
        "fr": "Aucun document trouvé à agréger",
        "en": "No documents found to aggregate",
    },
    "failed_regenerate_summary": {
        "fr": "Échec de la régénération du résumé : {error}",
        "en": "Failed to regenerate summary: {error}",
    },
    "failed_upload_document": {
        "fr": "Échec du téléchargement du document : {error}",
        "en": "Failed to upload document: {error}",
    },
    # ── Photos ────────────────────────────────────────────────────────────
    "file_must_be_image": {
        "fr": "Le fichier doit être une image (JPEG, JPG, PNG ou WebP)",
        "en": "File must be an image (JPEG, JPG, PNG, or WebP)",
    },
    "style_or_prompt_required": {
        "fr": "Un style prédéfini ou un prompt personnalisé est requis",
        "en": "Either style_preset or custom_prompt must be provided",
    },
    "failed_upload_photo": {
        "fr": "Échec du téléchargement de la photo : {error}",
        "en": "Failed to upload photo: {error}",
    },
    "photo_not_found": {
        "fr": "Photo non trouvée",
        "en": "Photo not found",
    },
    "failed_generate_redesign": {
        "fr": "Échec de la génération du redesign : {error}",
        "en": "Failed to generate redesign: {error}",
    },
    "failed_delete_photo": {
        "fr": "Échec de la suppression de la photo : {error}",
        "en": "Failed to delete photo: {error}",
    },
    # ── DVF Recommendations ──────────────────────────────────────────────
    "excellent_deal": {
        "fr": "Excellente affaire - En dessous du prix du marché",
        "en": "Excellent deal - Below market price",
    },
    "good_deal": {
        "fr": "Bonne affaire - Légèrement en dessous du marché",
        "en": "Good deal - Slightly below market",
    },
    "fair_price": {
        "fr": "Prix correct - Au prix du marché",
        "en": "Fair price - At market value",
    },
    "slightly_overpriced": {
        "fr": "Légèrement surévalué - Marge de négociation possible",
        "en": "Slightly overpriced - Room for negotiation",
    },
    "overpriced": {
        "fr": "Surévalué - Négociation importante nécessaire",
        "en": "Overpriced - Significant negotiation needed",
    },
    "heavily_overpriced": {
        "fr": "Très surévalué - À reconsidérer ou négocier fortement",
        "en": "Heavily overpriced - Reconsider or negotiate heavily",
    },
    "insufficient_data": {
        "fr": "Données insuffisantes",
        "en": "Insufficient data",
    },
    "insufficient_data_excluded": {
        "fr": "Données insuffisantes (toutes les ventes exclues)",
        "en": "Insufficient data (all sales excluded)",
    },
    # ── Style Presets ────────────────────────────────────────────────────
    "preset_modern_norwegian_name": {
        "fr": "Norvégien Moderne",
        "en": "Modern Norwegian",
    },
    "preset_modern_norwegian_desc": {
        "fr": "Lignes épurées, tons bois naturel, lumière nordique, élégance minimaliste",
        "en": "Clean lines, natural wood tones, Nordic light, minimalist elegance",
    },
    "preset_minimalist_scandinavian_name": {
        "fr": "Scandinave Minimaliste",
        "en": "Minimalist Scandinavian",
    },
    "preset_minimalist_scandinavian_desc": {
        "fr": "Philosophie lagom, blancs et gris monochromes, design fonctionnel",
        "en": "Lagom philosophy, monochromatic whites and grays, functional design",
    },
    "preset_cozy_hygge_name": {
        "fr": "Hygge Cocooning",
        "en": "Cozy Hygge",
    },
    "preset_cozy_hygge_desc": {
        "fr": "Chaleur enveloppante, textiles doux, éclairage d'ambiance, confort intimiste",
        "en": "Warm embrace, soft textiles, ambient lighting, intimate comfort",
    },
    # ── Style Preset Prompt Templates ────────────────────────────────────
    "preset_modern_norwegian_prompt": {
        "fr": (
            "Tu es un architecte d'intérieur.\n"
            "Redesigne ce {room_type} d'appartement dans un style norvégien moderne :\n"
            "- Conserve la géométrie de la pièce et les fenêtres\n"
            "- Utilise des lignes épurées avec des tons bois naturels et chaleureux (chêne clair ou bouleau)\n"
            "- Sol : parquet chêne chaleureux\n"
            "- Murs : blancs et crème avec des touches de vert forêt profond, bleu nuit ou gris anthracite\n"
            "- Ajoute des textiles cosy comme des plaids en laine et des coussins en lin\n"
            "- Éclairage : chaleureux et accueillant avec des suspensions design ou des lampadaires\n"
            "- Inclus une décoration minimale mais percutante : une plante statement, des vases en céramique ou de l'art contemporain norvégien\n"
            "- L'atmosphère générale doit sembler spacieuse, aérée et connectée à la nature tout en conservant une élégance moderne sophistiquée\n"
            "Retourne uniquement l'image modifiée."
        ),
        "en": (
            "You are an interior architect.\n"
            "Redesign this apartment {room_type} in a modern Norwegian style:\n"
            "- Keep room geometry and windows unchanged\n"
            "- Use clean lines with warm, natural wood tones (light oak or birch)\n"
            "- Flooring: warm oak wood\n"
            "- Walls: white and cream with accents of deep forest green, midnight blue, or charcoal gray\n"
            "- Add cozy textiles like wool throws and linen cushions\n"
            "- Lighting: warm and inviting with designer pendant lights or floor lamps\n"
            "- Include minimal but impactful decor: a single statement plant, ceramic vases, or contemporary Norwegian art\n"
            "- The overall atmosphere should feel spacious, airy, and connected to nature while maintaining sophisticated modern elegance\n"
            "Return only the edited image."
        ),
    },
    "preset_minimalist_scandinavian_prompt": {
        "fr": (
            "Tu es un architecte d'intérieur.\n"
            "Redesigne ce {room_type} d'appartement en un sanctuaire scandinave minimaliste :\n"
            "- Conserve la géométrie de la pièce et les fenêtres\n"
            "- Utilise une base monochromatique blanche et gris clair avec des accents de bois pâle\n"
            "- Le mobilier doit être composé de pièces fonctionnelles et sculpturales aux formes géométriques épurées\n"
            "- Inclus une chaleur subtile à travers des matériaux naturels : tapis en jute, textiles en lin\n"
            "- Ajoute une ou deux plantes vertes dans des pots en céramique simples\n"
            "- L'espace doit avoir un espace négatif généreux, mettant l'accent sur l'ouverture et la tranquillité\n"
            "- Chaque objet a un but tout en contribuant à l'harmonie esthétique globale\n"
            "- Ambiance : calme, épurée et d'une sophistication naturelle\n"
            "Retourne uniquement l'image modifiée."
        ),
        "en": (
            "You are an interior architect.\n"
            "Redesign this apartment {room_type} as a minimalist Scandinavian sanctuary:\n"
            "- Keep room geometry and windows unchanged\n"
            "- Use monochromatic white and light gray base with pale wood accents\n"
            "- Furniture should be functional, sculptural pieces with clean geometric forms\n"
            "- Include subtle warmth through natural materials: jute rug, linen textiles\n"
            "- Add one or two green plants in simple ceramic pots\n"
            "- The space should have generous negative space, emphasizing openness and tranquility\n"
            "- Every object serves a purpose while contributing to the overall aesthetic harmony\n"
            "- Mood: calm, uncluttered, and effortlessly sophisticated\n"
            "Return only the edited image."
        ),
    },
    "preset_cozy_hygge_prompt": {
        "fr": (
            "Tu es un architecte d'intérieur.\n"
            "Transforme ce {room_type} d'appartement en un refuge hygge ultime :\n"
            "- Conserve la géométrie de la pièce et les fenêtres\n"
            "- Un canapé généreux et moelleux avec des couches de couvertures douces et de coussins dans des tons neutres chaleureux\n"
            "- Ajoute un éclairage ambiant chaleureux provenant de multiples sources : bougies, lampadaire style vintage\n"
            "- Inclus des éléments en bois naturel avec une qualité patinée et vécue\n"
            "- Un plaid en tricot épais drapé sur un fauteuil\n"
            "- Palette de couleurs : chaleureuse et accueillante - caramel, terre cuite, rose poudré et crème\n"
            "- Ajoute des livres empilés nonchalamment, une tasse fumante sur une table d'appoint\n"
            "- L'atmosphère doit évoquer la sécurité, le confort et la convivialité intimiste\n"
            "- Éclairage : soirée cosy et chaleureuse\n"
            "Retourne uniquement l'image modifiée."
        ),
        "en": (
            "You are an interior architect.\n"
            "Transform this apartment {room_type} into the ultimate hygge retreat:\n"
            "- Keep room geometry and windows unchanged\n"
            "- Feature a plush, oversized sofa with layers of soft blankets and cushions in warm neutrals\n"
            "- Add warm, ambient lighting from multiple sources: candles, vintage-style floor lamp\n"
            "- Include natural wood elements with a weathered, lived-in quality\n"
            "- A chunky knit throw drapes over a chair\n"
            "- Color palette: warm and inviting - caramel, terracotta, dusty rose, and cream\n"
            "- Add books stacked casually, a steaming mug on a side table\n"
            "- The atmosphere should evoke safety, comfort, and intimate togetherness\n"
            "- Lighting: cozy warm evening\n"
            "Return only the edited image."
        ),
    },
}


def translate(key: str, locale: str = DEFAULT_LOCALE, **kwargs) -> str:
    """
    Translate a message key to the given locale.

    Args:
        key: Message key from the MESSAGES dict
        locale: 'fr' or 'en'
        **kwargs: Format variables (e.g. address=..., error=...)

    Returns:
        Translated and formatted string
    """
    if locale not in SUPPORTED_LOCALES:
        locale = DEFAULT_LOCALE

    entry = MESSAGES.get(key)
    if entry is None:
        return key  # Fallback to the key itself

    message = entry.get(locale, entry.get(DEFAULT_LOCALE, key))

    if kwargs:
        try:
            message = message.format(**kwargs)
        except (KeyError, IndexError):
            pass

    return message
