export interface User {
  id: number
  email: string
  full_name: string
  is_active: boolean
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  full_name: string
}

export interface Property {
  id: number
  user_id: number
  address: string
  postal_code?: string
  city?: string
  department?: string
  asking_price?: number
  surface_area?: number
  rooms?: number
  property_type?: string
  floor?: number
  building_floors?: number
  building_year?: number
  estimated_value?: number
  price_per_sqm?: number
  market_comparison_score?: number
  recommendation?: string
  created_at: string
  updated_at: string
}

export interface Document {
  id: number
  user_id: number
  property_id?: number
  filename: string
  file_type: string
  document_category: string
  is_analyzed: boolean
  analysis_summary?: string
  upload_date: string
  file_size: number
}

export interface PriceAnalysis {
  estimated_value: number
  price_per_sqm: number
  market_avg_price_per_sqm: number
  price_deviation_percent: number
  comparable_sales: DVFRecord[]
  recommendation: string
  confidence_score: number
}

export interface DVFRecord {
  id: number
  sale_date: string
  sale_price: number
  address: string
  postal_code: string
  city: string
  property_type: string
  surface_area?: number
  rooms?: number
  price_per_sqm?: number
}

export interface Analysis {
  analysis_id: number
  property_id: number
  investment_score: number
  value_score: number
  risk_score: number
  overall_recommendation: string
  estimated_fair_price?: number
  price_deviation_percent?: number
  annual_costs: number
  has_amiante: boolean
  has_plomb: boolean
  dpe_rating?: string
  ges_rating?: string
  summary: string
  created_at: string
  updated_at: string
}

export interface PVAGAnalysis {
  document_id: number
  summary: string
  upcoming_works: Array<{
    description: string
    estimated_cost: number
    timeline: string
  }>
  estimated_costs: {
    upcoming_works: number
    total: number
  }
  risk_level: 'low' | 'medium' | 'high'
  key_findings: string[]
  recommendations: string[]
}

export interface DiagnosticAnalysis {
  document_id: number
  dpe_rating?: string
  ges_rating?: string
  energy_consumption?: number
  has_amiante: boolean
  has_plomb: boolean
  risk_flags: string[]
  estimated_renovation_cost?: number
  summary: string
  recommendations: string[]
}

export interface PropertySynthesisPreview {
  risk_level?: string
  total_annual_cost?: number
  total_one_time_cost?: number
  key_findings?: string[]
  document_count: number
  redesign_count: number
}

export interface PropertyWithSynthesis extends Property {
  synthesis?: PropertySynthesisPreview | null
}

export interface TaxChargesAnalysis {
  document_id: number
  document_type: string
  period_covered: string
  total_amount: number
  annual_amount: number
  breakdown: Record<string, number>
  summary: string
}
