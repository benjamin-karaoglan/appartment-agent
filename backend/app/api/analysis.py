"""Analysis API routes for comprehensive property evaluation."""

import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.better_auth_security import get_current_user_hybrid as get_current_user
from app.core.database import get_db
from app.models.analysis import Analysis
from app.models.document import Document
from app.models.property import Property
from app.services.ai import get_document_analyzer
from app.services.dvf_service import DVFService

# Initialize services (lazy for Cloud Run compatibility)
get_gemini_llm_service = get_document_analyzer
_dvf_service = None


def get_dvf_service():
    """Get or create DVF service (lazy initialization)."""
    global _dvf_service
    if _dvf_service is None:
        _dvf_service = DVFService()
    return _dvf_service


router = APIRouter()


@router.post("/{property_id}/comprehensive")
async def generate_comprehensive_analysis(
    property_id: int, db: Session = Depends(get_db), current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Generate comprehensive property analysis combining all data sources:
    - Price analysis from DVF
    - Document analysis results
    - Overall investment score and recommendation
    """
    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    # Get price analysis
    price_analysis = {}
    if property.asking_price and property.surface_area:
        comparable_sales = get_dvf_service().get_comparable_sales(
            db=db,
            postal_code=property.postal_code or "",
            property_type=property.property_type or "Appartement",
            surface_area=property.surface_area,
        )
        price_analysis = get_dvf_service().calculate_price_analysis(
            asking_price=property.asking_price,
            surface_area=property.surface_area,
            comparable_sales=comparable_sales,
        )

    # Get all analyzed documents for this property
    documents = (
        db.query(Document)
        .filter(Document.property_id == property_id, Document.is_analyzed == True)
        .all()
    )

    # Aggregate document analysis
    documents_analysis = []
    annual_costs = 0
    risk_flags = []

    for doc in documents:
        if doc.extracted_data:
            try:
                data = json.loads(doc.extracted_data)
                documents_analysis.append(
                    {"document_id": doc.id, "category": doc.document_category, "data": data}
                )

                # Aggregate costs
                if doc.document_category in ["tax", "charges"]:
                    annual_costs += data.get("annual_amount", 0)

                # Aggregate risks
                if doc.risk_flags:
                    risk_flags.extend(json.loads(doc.risk_flags))

                # Add upcoming works costs
                if doc.document_category == "PV_AG":
                    for work in data.get("upcoming_works", []):
                        annual_costs += work.get("estimated_cost", 0) / 5  # Amortize over 5 years

            except json.JSONDecodeError:
                continue

    # Calculate investment score
    investment_metrics = get_dvf_service().calculate_investment_score(
        property_data=property,
        price_analysis=price_analysis,
        annual_costs=annual_costs,
        risk_factors=risk_flags,
    )

    # Generate AI report
    property_dict = {
        "address": property.address,
        "asking_price": property.asking_price,
        "surface_area": property.surface_area,
        "rooms": property.rooms,
        "property_type": property.property_type,
    }

    gemini_service = get_gemini_llm_service()
    ai_report = await gemini_service.generate_property_report(
        property_data=property_dict,
        price_analysis=price_analysis,
        documents_analysis=documents_analysis,
    )

    # Create or update analysis record
    analysis = db.query(Analysis).filter(Analysis.property_id == property_id).first()

    if not analysis:
        analysis = Analysis(property_id=property_id)
        db.add(analysis)

    # Update analysis fields
    analysis.investment_score = investment_metrics["investment_score"]
    analysis.value_score = investment_metrics["value_score"]
    analysis.risk_score = investment_metrics["risk_score"]
    analysis.overall_recommendation = investment_metrics["overall_recommendation"]

    if price_analysis:
        analysis.estimated_fair_price = price_analysis.get("estimated_value")
        analysis.price_deviation_percent = price_analysis.get("price_deviation_percent")
        analysis.comparable_properties_count = price_analysis.get("comparables_count")

    analysis.annual_charges = annual_costs
    analysis.estimated_annual_cost = annual_costs
    analysis.summary = ai_report

    # Extract risk factors from documents
    for doc_analysis in documents_analysis:
        if doc_analysis["category"] == "diagnostic":
            data = doc_analysis["data"]
            analysis.has_amiante = data.get("has_amiante", False)
            analysis.has_plomb = data.get("has_plomb", False)
            analysis.dpe_rating = data.get("dpe_rating")
            analysis.ges_rating = data.get("ges_rating")

    db.commit()
    db.refresh(analysis)

    return {
        "analysis_id": analysis.id,
        "property_id": property_id,
        "investment_score": analysis.investment_score,
        "value_score": analysis.value_score,
        "risk_score": analysis.risk_score,
        "overall_recommendation": analysis.overall_recommendation,
        "price_analysis": price_analysis,
        "annual_costs": annual_costs,
        "risk_flags": list(set(risk_flags)),  # Remove duplicates
        "ai_report": ai_report,
        "created_at": analysis.created_at,
        "updated_at": analysis.updated_at,
    }


@router.get("/{property_id}/latest")
async def get_latest_analysis(
    property_id: int, db: Session = Depends(get_db), current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get the latest comprehensive analysis for a property."""
    # Verify property ownership
    property = (
        db.query(Property)
        .filter(Property.id == property_id, Property.user_id == int(current_user))
        .first()
    )

    if not property:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    analysis = (
        db.query(Analysis)
        .filter(Analysis.property_id == property_id)
        .order_by(Analysis.created_at.desc())
        .first()
    )

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No analysis found for this property"
        )

    return {
        "analysis_id": analysis.id,
        "property_id": property_id,
        "investment_score": analysis.investment_score,
        "value_score": analysis.value_score,
        "risk_score": analysis.risk_score,
        "overall_recommendation": analysis.overall_recommendation,
        "estimated_fair_price": analysis.estimated_fair_price,
        "price_deviation_percent": analysis.price_deviation_percent,
        "annual_costs": analysis.annual_charges,
        "has_amiante": analysis.has_amiante,
        "has_plomb": analysis.has_plomb,
        "dpe_rating": analysis.dpe_rating,
        "ges_rating": analysis.ges_rating,
        "summary": analysis.summary,
        "created_at": analysis.created_at,
        "updated_at": analysis.updated_at,
    }
