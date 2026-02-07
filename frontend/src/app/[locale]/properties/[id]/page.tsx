"use client";

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useRouter } from '@/i18n/navigation';
import { useTranslations } from 'next-intl';
import ProtectedRoute from '@/components/ProtectedRoute';
import Header from '@/components/Header';
import InfoTooltip from '@/components/InfoTooltip';
import MarketTrendChart from '@/components/MarketTrendChart';
import { api } from '@/lib/api';
import { ArrowLeft, TrendingUp, FileText, Upload, Loader2, Trash2, ChevronDown, ChevronUp, Building2, ShieldCheck, AlertTriangle, ShieldAlert, Sparkles } from 'lucide-react';
import { Link } from '@/i18n/navigation';
import type { Property } from '@/types';

function PropertyDetailContent() {
  const t = useTranslations('property');
  const tc = useTranslations('common');
  const params = useParams();
  const router = useRouter();
  const propertyId = params.id as string;

  const [property, setProperty] = useState<Property | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [priceAnalysis, setPriceAnalysis] = useState<any>(null);
  const [error, setError] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showNeighboringSales, setShowNeighboringSales] = useState(false);
  const [excludedOutliers, setExcludedOutliers] = useState<Set<number>>(new Set());
  const [excludedNeighboringOutliers, setExcludedNeighboringOutliers] = useState<Set<number>>(new Set());
  const [expandedSales, setExpandedSales] = useState<Set<number>>(new Set());
  const [synthesis, setSynthesis] = useState<any>(null);
  const [synthesisLoading, setSynthesisLoading] = useState(true);

  useEffect(() => {
    loadProperty();
    loadSynthesis();
  }, [propertyId]);

  const loadProperty = async () => {
    try {
      const response = await api.get(`/api/properties/${propertyId}`);
      setProperty(response.data);
    } catch (error) {
      console.error('Failed to load property:', error);
      setError(t('loadFailed'));
    } finally {
      setLoading(false);
    }
  };

  const loadSynthesis = async () => {
    setSynthesisLoading(true);
    try {
      const response = await api.get(`/api/documents/synthesis/${propertyId}`);
      setSynthesis(response.data);
    } catch (error) {
      console.error('Failed to load synthesis:', error);
      setSynthesis(null);
    } finally {
      setSynthesisLoading(false);
    }
  };

  const analyzePrice = async (analysisType: 'simple' | 'trend' = 'simple') => {
    setAnalyzing(true);
    setError('');

    try {
      const response = await api.post(
        `/api/properties/${propertyId}/analyze-price?analysis_type=${analysisType}`
      );
      setPriceAnalysis(response.data);

      // Initialize excluded outliers set (outliers are excluded by default)
      const outlierIndices = new Set<number>();
      response.data.comparable_sales?.forEach((sale: any, index: number) => {
        if (sale.is_outlier) {
          outlierIndices.add(index);
        }
      });
      setExcludedOutliers(outlierIndices);

      // Initialize excluded neighboring outliers for trend analysis
      const neighboringOutlierIndices = new Set<number>();
      response.data.trend_projection?.neighboring_sales?.forEach((sale: any, index: number) => {
        if (sale.is_outlier) {
          neighboringOutlierIndices.add(index);
        }
      });
      setExcludedNeighboringOutliers(neighboringOutlierIndices);

      // Reload property to get updated values
      await loadProperty();
    } catch (err: any) {
      console.error('Price analysis error:', err);
      setError(err.response?.data?.detail || t('analyzeFailed'));
    } finally {
      setAnalyzing(false);
    }
  };

  const toggleOutlierInclusion = async (index: number) => {
    const newExcluded = new Set(excludedOutliers);
    if (newExcluded.has(index)) {
      newExcluded.delete(index);
    } else {
      newExcluded.add(index);
    }
    setExcludedOutliers(newExcluded);

    // Recalculate analysis with new exclusions
    await recalculateAnalysis(newExcluded);
  };

  const toggleSaleExpansion = (index: number) => {
    const newExpanded = new Set(expandedSales);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSales(newExpanded);
  };

  const recalculateAnalysis = async (excluded: Set<number>) => {
    if (!priceAnalysis?.comparable_sales) return;

    try {
      // Get IDs of excluded sales
      const excludedSaleIds = Array.from(excluded).map(
        index => priceAnalysis.comparable_sales[index]?.id
      ).filter(id => id !== undefined);

      const response = await api.post(
        `/api/properties/${propertyId}/recalculate-analysis`,
        excludedSaleIds
      );

      console.log('📊 Recalculate API Response:', response.data);
      console.log('📊 Current priceAnalysis.estimated_value:', priceAnalysis.estimated_value);
      console.log('📊 New estimated_value from API:', response.data.estimated_value);

      // Update the analysis results in place
      setPriceAnalysis({
        ...priceAnalysis,
        estimated_value: response.data.estimated_value,
        price_per_sqm: response.data.price_per_sqm,
        market_avg_price_per_sqm: response.data.market_avg_price_per_sqm,
        market_median_price_per_sqm: response.data.market_median_price_per_sqm,
        price_deviation_percent: response.data.price_deviation_percent,
        recommendation: response.data.recommendation,
        confidence_score: response.data.confidence_score,
        comparables_count: response.data.comparables_count,
        market_trend_annual: response.data.market_trend_annual,
      });
    } catch (err) {
      console.error('Failed to recalculate:', err);
      setError(t('recalculateFailed'));
    }
  };

  const toggleNeighboringOutlierInclusion = async (index: number) => {
    const newExcluded = new Set(excludedNeighboringOutliers);
    if (newExcluded.has(index)) {
      newExcluded.delete(index);
    } else {
      newExcluded.add(index);
    }
    setExcludedNeighboringOutliers(newExcluded);

    // Trigger trend analysis recalculation
    await recalculateTrendAnalysis(newExcluded);
  };

  const recalculateTrendAnalysis = async (excludedNeighboring: Set<number>) => {
    if (!priceAnalysis?.trend_projection?.neighboring_sales) return;

    try {
      // Get IDs of excluded neighboring sales
      const excludedSaleIds = Array.from(excludedNeighboring).map(
        index => priceAnalysis.trend_projection.neighboring_sales[index]?.id
      ).filter((id: any) => id !== undefined);

      const response = await api.post(
        `/api/properties/${propertyId}/recalculate-trend`,
        excludedSaleIds
      );

      // Update only the trend projection data
      setPriceAnalysis({
        ...priceAnalysis,
        trend_projection: {
          ...priceAnalysis.trend_projection,
          ...response.data.trend_projection,
        },
        neighboring_sales_count: response.data.neighboring_sales_count,
      });
    } catch (err) {
      console.error('Failed to recalculate trend:', err);
      setError(t('recalculateTrendFailed'));
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    setError('');

    try {
      await api.delete(`/api/properties/${propertyId}`);
      // Redirect to dashboard after successful deletion
      router.push('/dashboard');
    } catch (err: any) {
      console.error('Delete error:', err);
      setError(err.response?.data?.detail || t('deleteFailed'));
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="flex items-center justify-center h-96">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      </div>
    );
  }

  if (!property) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Header />
        <div className="max-w-7xl mx-auto py-6 px-4">
          <p className="text-red-600">{t('notFound')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Back button */}
          <Link
            href="/dashboard"
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-6"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            {t('backToDashboard')}
          </Link>

          {/* Header */}
          <div className="mb-8 flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">{property.address}</h1>
              <p className="mt-2 text-sm text-gray-600">
                {property.city} {property.postal_code}
              </p>
            </div>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="inline-flex items-center px-3 py-2 border border-red-300 text-sm font-medium rounded-md text-red-700 bg-white hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              {tc('delete')}
            </button>
          </div>

          {error && (
            <div className="mb-6 rounded-md bg-red-50 p-4">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Property Details Grid */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 mb-8">
            {/* Property Info Card */}
            <div className="bg-white shadow rounded-lg p-6 lg:col-span-2">
              <h2 className="text-lg font-medium text-gray-900 mb-4">{t('info.title')}</h2>
              <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
                {property.property_type && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">{t('info.type')}</dt>
                    <dd className="mt-1 text-sm text-gray-900">{property.property_type}</dd>
                  </div>
                )}
                {property.asking_price && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">{t('info.askingPrice')}</dt>
                    <dd className="mt-1 text-sm text-gray-900 font-semibold">
                      {new Intl.NumberFormat('fr-FR', {
                        style: 'currency',
                        currency: 'EUR',
                      }).format(property.asking_price)}
                    </dd>
                  </div>
                )}
                {property.surface_area && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">{t('info.surfaceArea')}</dt>
                    <dd className="mt-1 text-sm text-gray-900">{property.surface_area} m²</dd>
                  </div>
                )}
                {property.rooms && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">{t('info.rooms')}</dt>
                    <dd className="mt-1 text-sm text-gray-900">{property.rooms} pièces</dd>
                  </div>
                )}
                {property.floor !== null && property.floor !== undefined && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">{t('info.floor')}</dt>
                    <dd className="mt-1 text-sm text-gray-900">{property.floor}</dd>
                  </div>
                )}
                {property.building_year && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">{t('info.buildingYear')}</dt>
                    <dd className="mt-1 text-sm text-gray-900">{property.building_year}</dd>
                  </div>
                )}
                {property.price_per_sqm && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">{t('info.pricePerSqm')}</dt>
                    <dd className="mt-1 text-sm text-gray-900">
                      {new Intl.NumberFormat('fr-FR', {
                        style: 'currency',
                        currency: 'EUR',
                      }).format(property.price_per_sqm)}
                    </dd>
                  </div>
                )}
              </dl>
            </div>

            {/* Market Analysis Card */}
            <div className="space-y-6">
              <div className="bg-white shadow rounded-lg p-6">
                <h2 className="text-lg font-medium text-gray-900 mb-4">{t('analysis.title')}</h2>
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => analyzePrice('simple')}
                      disabled={analyzing || !property.asking_price || !property.surface_area}
                      className="flex-1 inline-flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {analyzing ? (
                        <>
                          <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                          {t('analysis.analyzing')}
                        </>
                      ) : (
                        <>
                          <TrendingUp className="h-5 w-5 mr-2" />
                          {t('analysis.simpleAnalysis')}
                        </>
                      )}
                    </button>
                    <InfoTooltip
                      title={t('analysis.simpleTooltip.title')}
                      content={
                        <div className="space-y-2">
                          <p><strong>{t('analysis.simpleTooltip.whatItDoes')}</strong></p>
                          <p><strong>{t('analysis.simpleTooltip.howItWorks')}</strong></p>
                          <ul className="list-disc pl-4 space-y-1 text-xs">
                            <li>{t('analysis.simpleTooltip.steps.findSales')}</li>
                            <li>{t('analysis.simpleTooltip.steps.groupTransactions')}</li>
                            <li>{t('analysis.simpleTooltip.steps.detectOutliers')}</li>
                            <li>{t('analysis.simpleTooltip.steps.calculateAverage')}</li>
                            <li>{t('analysis.simpleTooltip.steps.rawPrices')}</li>
                          </ul>
                          <p className="text-xs text-gray-600 mt-2">
                            <strong>{t('analysis.simpleTooltip.bestFor')}</strong>
                          </p>
                        </div>
                      }
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => analyzePrice('trend')}
                      disabled={analyzing || !property.asking_price || !property.surface_area}
                      className="flex-1 inline-flex items-center justify-center px-4 py-2 border border-blue-600 text-sm font-medium rounded-md text-blue-600 bg-white hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {analyzing ? (
                        <>
                          <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                          {t('analysis.analyzing')}
                        </>
                      ) : (
                        <>
                          <TrendingUp className="h-5 w-5 mr-2" />
                          {t('analysis.trendAnalysis')}
                        </>
                      )}
                    </button>
                    <InfoTooltip
                      title={t('analysis.trendTooltip.title')}
                      content={
                        <div className="space-y-2">
                          <p><strong>{t('analysis.trendTooltip.whatItDoes')}</strong></p>
                          <p><strong>{t('analysis.trendTooltip.howItWorks')}</strong></p>
                          <ul className="list-disc pl-4 space-y-1 text-xs">
                            <li>{t('analysis.trendTooltip.steps.takeSale')}</li>
                            <li>{t('analysis.trendTooltip.steps.analyzeSales')}</li>
                            <li>{t('analysis.trendTooltip.steps.calculateTrend')}</li>
                            <li>{t('analysis.trendTooltip.steps.projectPrice')}</li>
                            <li>{t('analysis.trendTooltip.steps.accountTime')}</li>
                          </ul>
                          <p className="text-xs text-gray-600 mt-2">
                            <strong>{t('analysis.trendTooltip.bestFor')}</strong>
                          </p>
                        </div>
                      }
                    />
                  </div>
                </div>
              </div>

              {/* Property Tools Card */}
              <div className="bg-white shadow rounded-lg p-6">
                <h2 className="text-lg font-medium text-gray-900 mb-4">{t('analysis.toolsTitle')}</h2>
                <div className="space-y-3">
                  <button
                    onClick={() => router.push(`/properties/${propertyId}/documents`)}
                    className="w-full inline-flex items-center justify-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <FileText className="h-5 w-5 mr-2" />
                    {t('analysis.manageDocuments')}
                  </button>

                  <button
                    onClick={() => router.push(`/properties/${propertyId}/redesign-studio`)}
                    className="w-full inline-flex items-center justify-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    <Upload className="h-5 w-5 mr-2" />
                    {t('analysis.redesignStudio')}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* AI Property Analysis Card */}
          <div className="bg-white shadow rounded-lg p-6 mb-8">
            <h2 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
              <Sparkles className="h-5 w-5 mr-2 text-purple-500" />
              {t('aiAnalysis.title')}
            </h2>
            {synthesisLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-purple-500" />
              </div>
            ) : synthesis ? (
              <div className="space-y-4">
                {/* Risk badge */}
                {synthesis.risk_level && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-500">{t('aiAnalysis.riskLevel')}:</span>
                    <span className={`inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-full ${
                      synthesis.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                      synthesis.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {synthesis.risk_level === 'high' ? (
                        <ShieldAlert className="h-3.5 w-3.5 mr-1" />
                      ) : synthesis.risk_level === 'medium' ? (
                        <AlertTriangle className="h-3.5 w-3.5 mr-1" />
                      ) : (
                        <ShieldCheck className="h-3.5 w-3.5 mr-1" />
                      )}
                      {synthesis.risk_level.toUpperCase()}
                    </span>
                  </div>
                )}

                {/* Summary */}
                {synthesis.overall_summary && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-1">{t('aiAnalysis.summary')}</h3>
                    <p className="text-sm text-gray-600 leading-relaxed">{synthesis.overall_summary}</p>
                  </div>
                )}

                {/* Key findings */}
                {synthesis.key_findings && synthesis.key_findings.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">{t('aiAnalysis.keyFindings')}</h3>
                    <ul className="space-y-1">
                      {synthesis.key_findings.map((finding: string, idx: number) => (
                        <li key={idx} className="text-sm text-gray-600 flex items-start">
                          <span className="text-gray-400 mr-2">&bull;</span>
                          {finding}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Recommendations */}
                {synthesis.recommendations && synthesis.recommendations.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">{t('aiAnalysis.recommendations')}</h3>
                    <ul className="space-y-1">
                      {synthesis.recommendations.map((rec: string, idx: number) => (
                        <li key={idx} className="text-sm text-gray-600 flex items-start">
                          <span className="text-gray-400 mr-2">&bull;</span>
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Costs */}
                {(synthesis.total_annual_cost > 0 || synthesis.total_one_time_cost > 0) && (
                  <div className="grid grid-cols-2 gap-4 pt-3 border-t border-gray-100">
                    {synthesis.total_annual_cost > 0 && (
                      <div>
                        <dt className="text-xs font-medium text-gray-500">{t('aiAnalysis.annualCosts')}</dt>
                        <dd className="mt-1 text-lg font-semibold text-gray-900">
                          {new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(synthesis.total_annual_cost)}
                        </dd>
                      </div>
                    )}
                    {synthesis.total_one_time_cost > 0 && (
                      <div>
                        <dt className="text-xs font-medium text-gray-500">{t('aiAnalysis.oneTimeCosts')}</dt>
                        <dd className="mt-1 text-lg font-semibold text-gray-900">
                          {new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(synthesis.total_one_time_cost)}
                        </dd>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-6">
                <p className="text-sm text-gray-500 mb-3">{t('aiAnalysis.noData')}</p>
                <button
                  onClick={() => router.push(`/properties/${propertyId}/documents`)}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                >
                  <FileText className="h-4 w-4 mr-2" />
                  {t('aiAnalysis.viewDocuments')}
                </button>
              </div>
            )}
          </div>

          {/* Market Trend Visualization */}
          {priceAnalysis && (
            <div className="mb-8">
              <MarketTrendChart propertyId={propertyId} />
            </div>
          )}

          {/* Price Analysis Results */}
          {priceAnalysis && (
            <div className="bg-white shadow rounded-lg p-6 mb-8">
              <h2 className="text-lg font-medium text-gray-900 mb-4">{t('analysis.title')}</h2>

              <div className="grid grid-cols-1 gap-6 sm:grid-cols-3 mb-6">
                {priceAnalysis.estimated_value && (
                  <div className="border-l-4 border-blue-500 pl-4">
                    <dt className="text-sm font-medium text-gray-500">{t('analysis.estimatedValue')}</dt>
                    <dd className="mt-1 text-2xl font-semibold text-gray-900">
                      {new Intl.NumberFormat('fr-FR', {
                        style: 'currency',
                        currency: 'EUR',
                      }).format(priceAnalysis.estimated_value)}
                    </dd>
                  </div>
                )}

                {priceAnalysis?.price_deviation_percent !== undefined && (
                  <div className="border-l-4 border-yellow-500 pl-4">
                    <dt className="text-sm font-medium text-gray-500">{t('analysis.priceDeviation')}</dt>
                    <dd className={`mt-1 text-2xl font-semibold ${
                      priceAnalysis.price_deviation_percent > 0 ? 'text-red-600' : 'text-green-600'
                    }`}>
                      {priceAnalysis.price_deviation_percent > 0 ? '+' : ''}
                      {priceAnalysis.price_deviation_percent.toFixed(1)}%
                    </dd>
                  </div>
                )}

                {priceAnalysis?.comparable_sales && (
                  <div className="border-l-4 border-green-500 pl-4">
                    <dt className="text-sm font-medium text-gray-500">{t('analysis.comparableSales')}</dt>
                    <dd className="mt-1 text-2xl font-semibold text-gray-900">
                      {priceAnalysis.comparables_count || priceAnalysis.comparable_sales.length}
                    </dd>
                  </div>
                )}
              </div>

              {priceAnalysis?.recommendation && (
                <div className="bg-blue-50 border-l-4 border-blue-400 p-4">
                  <p className="text-sm text-blue-800">
                    <span className="font-medium">{t('analysis.recommendation')}</span> {priceAnalysis.recommendation}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Trend Projection Results */}
          {priceAnalysis?.trend_projection && (
            <div className="bg-gradient-to-r from-purple-50 to-indigo-50 shadow rounded-lg p-6 mb-8">
              <h2 className="text-lg font-medium text-gray-900 mb-4">{t('trend.title')}</h2>

              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 mb-6">
                <div className="border-l-4 border-purple-500 pl-4 bg-white p-4 rounded">
                  <dt className="text-sm font-medium text-gray-500">{t('trend.projectedValue')}</dt>
                  <dd className="mt-1 text-2xl font-semibold text-purple-600">
                    {new Intl.NumberFormat('fr-FR', {
                      style: 'currency',
                      currency: 'EUR',
                      maximumFractionDigits: 0,
                    }).format(priceAnalysis.trend_projection.estimated_value_2025)}
                  </dd>
                  <dd className="mt-1 text-sm text-gray-500">
                    {new Intl.NumberFormat('fr-FR', {
                      style: 'currency',
                      currency: 'EUR',
                      maximumFractionDigits: 0,
                    }).format(priceAnalysis.trend_projection.projected_price_per_sqm)}/m²
                  </dd>
                </div>

                <div className="border-l-4 border-indigo-500 pl-4 bg-white p-4 rounded">
                  <dt className="text-sm font-medium text-gray-500">{t('trend.marketTrend')}</dt>
                  <dd className={`mt-1 text-2xl font-semibold ${
                    priceAnalysis.trend_projection.trend_used > 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {priceAnalysis.trend_projection.trend_used > 0 ? '+' : ''}
                    {priceAnalysis.trend_projection.trend_used.toFixed(2)}% /year
                  </dd>
                  <dd className="mt-1">
                    <button
                      onClick={() => setShowNeighboringSales(!showNeighboringSales)}
                      className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
                    >
                      {t('trend.basedOnSales', { count: priceAnalysis.trend_projection.trend_sample_size })}
                      {showNeighboringSales ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                  </dd>
                </div>
              </div>

              {showNeighboringSales && priceAnalysis.trend_projection.neighboring_sales && (
                <div className="bg-white p-4 rounded mb-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">
                    {t('trend.neighboringSalesTitle', { count: priceAnalysis.trend_projection.neighboring_sales.length })}
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-2 py-2 text-left text-xs font-medium text-gray-500 uppercase">{t('comparables.include')}</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">{t('comparables.saleDate')}</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">{t('comparables.address')}</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">{t('comparables.surface')}</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">{t('comparables.salePrice')}</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">{t('comparables.pricePerSqm')}</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {priceAnalysis.trend_projection.neighboring_sales.map((sale: any, idx: number) => (
                          <tr
                            key={idx}
                            className={`hover:bg-gray-50 ${sale.is_outlier ? 'bg-yellow-50' : ''} ${excludedNeighboringOutliers.has(idx) ? 'opacity-50' : ''}`}
                          >
                            <td className="px-2 py-2 whitespace-nowrap text-center">
                              <input
                                type="checkbox"
                                checked={!excludedNeighboringOutliers.has(idx)}
                                onChange={() => toggleNeighboringOutlierInclusion(idx)}
                                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded cursor-pointer"
                                title={sale.is_outlier ? t('comparables.outlierDetected') : t('comparables.includeInTrend')}
                              />
                              {sale.is_outlier && (
                                <div className="text-xs text-yellow-600 mt-1">{t('comparables.outlier')}</div>
                              )}
                            </td>
                            <td className="px-3 py-2 whitespace-nowrap text-gray-900">
                              {new Date(sale.sale_date).toLocaleDateString('fr-FR')}
                            </td>
                            <td className="px-3 py-2 text-gray-900">{sale.address}</td>
                            <td className="px-3 py-2 whitespace-nowrap text-gray-900">{sale.surface_area} m²</td>
                            <td className="px-3 py-2 whitespace-nowrap text-gray-900">
                              {new Intl.NumberFormat('fr-FR', {
                                style: 'currency',
                                currency: 'EUR',
                                maximumFractionDigits: 0,
                              }).format(sale.sale_price)}
                            </td>
                            <td className="px-3 py-2 whitespace-nowrap text-gray-900">
                              {new Intl.NumberFormat('fr-FR', {
                                style: 'currency',
                                currency: 'EUR',
                                maximumFractionDigits: 0,
                              }).format(sale.price_per_sqm)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="bg-white p-4 rounded">
                <h3 className="text-sm font-medium text-gray-700 mb-2">{t('trend.baseSale')}</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">{t('trend.date')}</span>
                    <span className="ml-2 font-medium text-gray-900">
                      {new Date(priceAnalysis.trend_projection.base_sale_date).toLocaleDateString('fr-FR')}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">{t('trend.pricePerSqm')}</span>
                    <span className="ml-2 font-medium text-gray-900">
                      {new Intl.NumberFormat('fr-FR', {
                        style: 'currency',
                        currency: 'EUR',
                        maximumFractionDigits: 0,
                      }).format(priceAnalysis.trend_projection.base_price_per_sqm)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Comparable Sales List */}
          {priceAnalysis?.comparable_sales && priceAnalysis.comparable_sales.length > 0 && (
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">
                {t('comparables.title', { total: priceAnalysis.comparable_sales.length, included: priceAnalysis.comparables_count || priceAnalysis.comparable_sales.length })}
              </h2>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('comparables.include')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('comparables.saleDate')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('comparables.address')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('comparables.surface')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('comparables.salePrice')}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('comparables.pricePerSqm')}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {priceAnalysis.comparable_sales.map((sale: any, index: number) => {
                      const isMultiUnit = sale.unit_count && sale.unit_count > 1;
                      const isExpanded = expandedSales.has(index);
                      // All sales from grouped view use total_* and grouped_* fields
                      const displaySurface = sale.total_surface_area || sale.surface_area;
                      const displayRooms = sale.total_rooms || sale.rooms;
                      const displayPricePerSqm = sale.grouped_price_per_sqm || sale.price_per_sqm;

                      return (
                        <>
                          <tr
                            key={index}
                            className={`hover:bg-gray-50 ${sale.is_outlier ? 'bg-yellow-50' : ''} ${excludedOutliers.has(index) ? 'opacity-50' : ''} ${isMultiUnit ? 'border-l-4 border-l-blue-500' : ''}`}
                          >
                            <td className="px-3 py-4 whitespace-nowrap text-center">
                              <input
                                type="checkbox"
                                checked={!excludedOutliers.has(index)}
                                onChange={() => toggleOutlierInclusion(index)}
                                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded cursor-pointer"
                                title={sale.is_outlier ? t('comparables.outlierDetected') : t('comparables.includeInAnalysis')}
                              />
                              {sale.is_outlier && (
                                <div className="text-xs text-yellow-600 mt-1">{t('comparables.outlier')}</div>
                              )}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {new Date(sale.sale_date).toLocaleDateString('fr-FR')}
                            </td>
                            <td className="px-6 py-4 text-sm text-gray-900">
                              <div className="flex items-start gap-2">
                                <div className="flex-1">
                                  {sale.address || '-'}<br />
                                  <span className="text-gray-500">{sale.city} {sale.postal_code}</span>
                                </div>
                                {isMultiUnit && (
                                  <button
                                    onClick={() => toggleSaleExpansion(index)}
                                    className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-700 bg-blue-50 rounded hover:bg-blue-100"
                                    title="Multi-unit sale - click to see details"
                                  >
                                    <Building2 className="h-3 w-3" />
                                    {t('comparables.units', { count: sale.unit_count })}
                                    {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                                  </button>
                                )}
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {displaySurface?.toFixed(2)} m²
                              {isMultiUnit && displayRooms && (
                                <div className="text-xs text-gray-500">{t('comparables.rooms')}: {displayRooms}</div>
                              )}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                              {new Intl.NumberFormat('fr-FR', {
                                style: 'currency',
                                currency: 'EUR',
                                maximumFractionDigits: 0,
                              }).format(sale.sale_price)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {new Intl.NumberFormat('fr-FR', {
                                style: 'currency',
                                currency: 'EUR',
                                maximumFractionDigits: 0,
                              }).format(displayPricePerSqm)}
                              {isMultiUnit && (
                                <div className="text-xs text-blue-600 font-medium">{t('comparables.grouped')}</div>
                              )}
                            </td>
                          </tr>
                          {/* Expandable drill-down for multi-unit sales */}
                          {isMultiUnit && isExpanded && sale.lots_detail && (
                            <tr key={`${index}-detail`} className="bg-blue-50">
                              <td colSpan={6} className="px-6 py-4">
                                <div className="text-xs font-medium text-gray-700 mb-2 uppercase">{t('comparables.individualUnits', { count: sale.unit_count })}</div>
                                <div className="bg-white rounded border border-blue-200 overflow-hidden">
                                  <table className="min-w-full text-xs">
                                    <thead className="bg-gray-50">
                                      <tr>
                                        <th className="px-3 py-2 text-left font-medium text-gray-500">{t('comparables.unit')}</th>
                                        <th className="px-3 py-2 text-left font-medium text-gray-500">{t('comparables.surface')}</th>
                                        <th className="px-3 py-2 text-left font-medium text-gray-500">{t('comparables.rooms')}</th>
                                        <th className="px-3 py-2 text-left font-medium text-gray-500">{t('comparables.individualPricePerSqm')}</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-200">
                                      {sale.lots_detail.map((lot: any, lotIdx: number) => (
                                        <tr key={lotIdx} className="hover:bg-gray-50">
                                          <td className="px-3 py-2 text-gray-700">{t('comparables.unit')} {lotIdx + 1}</td>
                                          <td className="px-3 py-2 text-gray-900">{lot.surface_area} m²</td>
                                          <td className="px-3 py-2 text-gray-900">{lot.rooms || '-'}</td>
                                          <td className="px-3 py-2 text-gray-900">
                                            {lot.price_per_sqm ? new Intl.NumberFormat('fr-FR', {
                                              style: 'currency',
                                              currency: 'EUR',
                                              maximumFractionDigits: 0,
                                            }).format(lot.price_per_sqm) : '-'}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                  <div className="px-3 py-2 bg-gray-50 text-xs text-gray-600 border-t border-gray-200">
                                    {t('comparables.groupedNote', { price: new Intl.NumberFormat('fr-FR', {
                                      style: 'currency',
                                      currency: 'EUR',
                                      maximumFractionDigits: 0,
                                    }).format(displayPricePerSqm) })}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Summary statistics */}
              {priceAnalysis.market_avg_price_per_sqm && (
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    <div>
                      <dt className="text-sm font-medium text-gray-500">{t('comparables.marketAvgPrice')}</dt>
                      <dd className="mt-1 text-lg font-semibold text-gray-900">
                        {new Intl.NumberFormat('fr-FR', {
                          style: 'currency',
                          currency: 'EUR',
                          maximumFractionDigits: 0,
                        }).format(priceAnalysis.market_avg_price_per_sqm)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">{t('comparables.yourPrice')}</dt>
                      <dd className="mt-1 text-lg font-semibold text-gray-900">
                        {new Intl.NumberFormat('fr-FR', {
                          style: 'currency',
                          currency: 'EUR',
                          maximumFractionDigits: 0,
                        }).format(priceAnalysis.price_per_sqm)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">{t('comparables.marketMedianPrice')}</dt>
                      <dd className="mt-1 text-lg font-semibold text-gray-900">
                        {new Intl.NumberFormat('fr-FR', {
                          style: 'currency',
                          currency: 'EUR',
                          maximumFractionDigits: 0,
                        }).format(priceAnalysis.market_median_price_per_sqm)}
                      </dd>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Delete Confirmation Modal */}
          {showDeleteConfirm && (
            <div className="fixed z-10 inset-0 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
              <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
                {/* Background overlay */}
                <div
                  className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
                  aria-hidden="true"
                  onClick={() => !deleting && setShowDeleteConfirm(false)}
                ></div>

                {/* Center modal */}
                <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

                {/* Modal panel */}
                <div className="relative inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
                  <div className="sm:flex sm:items-start">
                    <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                      <Trash2 className="h-6 w-6 text-red-600" aria-hidden="true" />
                    </div>
                    <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                      <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                        {t('deleteTitle')}
                      </h3>
                      <div className="mt-2">
                        <p className="text-sm text-gray-500">
                          {t('deleteMessage')}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                    <button
                      type="button"
                      disabled={deleting}
                      onClick={handleDelete}
                      className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {deleting ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          {tc('deleting')}
                        </>
                      ) : (
                        tc('delete')
                      )}
                    </button>
                    <button
                      type="button"
                      disabled={deleting}
                      onClick={() => setShowDeleteConfirm(false)}
                      className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:mt-0 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {tc('cancel')}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default function PropertyDetailPage() {
  return (
    <ProtectedRoute>
      <PropertyDetailContent />
    </ProtectedRoute>
  );
}
