"use client";

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/ProtectedRoute';
import Header from '@/components/Header';
import { api } from '@/lib/api';
import { ArrowLeft, TrendingUp, FileText, Upload, Loader2, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import Link from 'next/link';
import type { Property } from '@/types';

function PropertyDetailContent() {
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

  useEffect(() => {
    loadProperty();
  }, [propertyId]);

  const loadProperty = async () => {
    try {
      const response = await api.get(`/api/properties/${propertyId}`);
      setProperty(response.data);
    } catch (error) {
      console.error('Failed to load property:', error);
      setError('Failed to load property details');
    } finally {
      setLoading(false);
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
      setError(err.response?.data?.detail || 'Failed to analyze price');
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
      setError('Failed to recalculate analysis');
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
      setError('Failed to recalculate trend analysis');
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
      setError(err.response?.data?.detail || 'Failed to delete property');
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
          <p className="text-red-600">Property not found</p>
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
            Back to Dashboard
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
              Delete Property
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
              <h2 className="text-lg font-medium text-gray-900 mb-4">Property Information</h2>
              <dl className="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
                {property.property_type && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Type</dt>
                    <dd className="mt-1 text-sm text-gray-900">{property.property_type}</dd>
                  </div>
                )}
                {property.asking_price && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Asking Price</dt>
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
                    <dt className="text-sm font-medium text-gray-500">Surface Area</dt>
                    <dd className="mt-1 text-sm text-gray-900">{property.surface_area} m²</dd>
                  </div>
                )}
                {property.rooms && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Rooms</dt>
                    <dd className="mt-1 text-sm text-gray-900">{property.rooms} pièces</dd>
                  </div>
                )}
                {property.floor !== null && property.floor !== undefined && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Floor</dt>
                    <dd className="mt-1 text-sm text-gray-900">{property.floor}</dd>
                  </div>
                )}
                {property.building_year && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Building Year</dt>
                    <dd className="mt-1 text-sm text-gray-900">{property.building_year}</dd>
                  </div>
                )}
                {property.price_per_sqm && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Price per m²</dt>
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

            {/* Quick Actions Card */}
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Price Analysis</h2>
              <div className="space-y-3">
                <button
                  onClick={() => analyzePrice('simple')}
                  disabled={analyzing || !property.asking_price || !property.surface_area}
                  className="w-full inline-flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {analyzing ? (
                    <>
                      <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <TrendingUp className="h-5 w-5 mr-2" />
                      Simple Analysis
                    </>
                  )}
                </button>

                <button
                  onClick={() => analyzePrice('trend')}
                  disabled={analyzing || !property.asking_price || !property.surface_area}
                  className="w-full inline-flex items-center justify-center px-4 py-2 border border-blue-600 text-sm font-medium rounded-md text-blue-600 bg-white hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {analyzing ? (
                    <>
                      <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <TrendingUp className="h-5 w-5 mr-2" />
                      Trend Analysis (2025 Projection)
                    </>
                  )}
                </button>

                <button
                  onClick={() => router.push(`/properties/${propertyId}/documents`)}
                  className="w-full inline-flex items-center justify-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <FileText className="h-5 w-5 mr-2" />
                  Manage Documents
                </button>

                <button
                  onClick={() => router.push(`/properties/${propertyId}/photos`)}
                  className="w-full inline-flex items-center justify-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <Upload className="h-5 w-5 mr-2" />
                  Upload Photos
                </button>
              </div>
            </div>
          </div>

          {/* Price Analysis Results */}
          {priceAnalysis && (
            <div className="bg-white shadow rounded-lg p-6 mb-8">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Price Analysis</h2>

              <div className="grid grid-cols-1 gap-6 sm:grid-cols-3 mb-6">
                {priceAnalysis.estimated_value && (
                  <div className="border-l-4 border-blue-500 pl-4">
                    <dt className="text-sm font-medium text-gray-500">Estimated Value</dt>
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
                    <dt className="text-sm font-medium text-gray-500">Price Deviation</dt>
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
                    <dt className="text-sm font-medium text-gray-500">Comparable Sales</dt>
                    <dd className="mt-1 text-2xl font-semibold text-gray-900">
                      {priceAnalysis.comparables_count || priceAnalysis.comparable_sales.length}
                    </dd>
                  </div>
                )}
              </div>

              {priceAnalysis?.recommendation && (
                <div className="bg-blue-50 border-l-4 border-blue-400 p-4">
                  <p className="text-sm text-blue-800">
                    <span className="font-medium">Recommendation:</span> {priceAnalysis.recommendation}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Trend Projection Results */}
          {priceAnalysis?.trend_projection && (
            <div className="bg-gradient-to-r from-purple-50 to-indigo-50 shadow rounded-lg p-6 mb-8">
              <h2 className="text-lg font-medium text-gray-900 mb-4">2025 Trend Projection</h2>

              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 mb-6">
                <div className="border-l-4 border-purple-500 pl-4 bg-white p-4 rounded">
                  <dt className="text-sm font-medium text-gray-500">Projected 2025 Value</dt>
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
                  <dt className="text-sm font-medium text-gray-500">Market Trend</dt>
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
                      Based on {priceAnalysis.trend_projection.trend_sample_size} neighboring sales
                      {showNeighboringSales ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                  </dd>
                </div>
              </div>

              {showNeighboringSales && priceAnalysis.trend_projection.neighboring_sales && (
                <div className="bg-white p-4 rounded mb-4">
                  <h3 className="text-sm font-medium text-gray-700 mb-3">
                    Neighboring Sales Used for Trend ({priceAnalysis.trend_projection.neighboring_sales.length})
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-2 py-2 text-left text-xs font-medium text-gray-500 uppercase">Include</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Address</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Surface</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Price/m²</th>
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
                                title={sale.is_outlier ? 'Outlier detected (IQR method)' : 'Include in trend analysis'}
                              />
                              {sale.is_outlier && (
                                <div className="text-xs text-yellow-600 mt-1">Outlier</div>
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
                <h3 className="text-sm font-medium text-gray-700 mb-2">Base Sale</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Date:</span>
                    <span className="ml-2 font-medium text-gray-900">
                      {new Date(priceAnalysis.trend_projection.base_sale_date).toLocaleDateString('fr-FR')}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-500">Price/m²:</span>
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
                Comparable Sales ({priceAnalysis.comparable_sales.length} total, {priceAnalysis.comparables_count || priceAnalysis.comparable_sales.length} included)
              </h2>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Include
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Date
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Address
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Surface
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Sale Price
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Price/m²
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {priceAnalysis.comparable_sales.map((sale: any, index: number) => (
                      <tr
                        key={index}
                        className={`hover:bg-gray-50 ${sale.is_outlier ? 'bg-yellow-50' : ''} ${excludedOutliers.has(index) ? 'opacity-50' : ''}`}
                      >
                        <td className="px-3 py-4 whitespace-nowrap text-center">
                          <input
                            type="checkbox"
                            checked={!excludedOutliers.has(index)}
                            onChange={() => toggleOutlierInclusion(index)}
                            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded cursor-pointer"
                            title={sale.is_outlier ? 'Outlier detected (IQR method)' : 'Include in analysis'}
                          />
                          {sale.is_outlier && (
                            <div className="text-xs text-yellow-600 mt-1">Outlier</div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {new Date(sale.sale_date).toLocaleDateString('fr-FR')}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900">
                          {sale.address || '-'}<br />
                          <span className="text-gray-500">{sale.city} {sale.postal_code}</span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {sale.surface_area} m²
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
                          }).format(sale.price_per_sqm)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Summary statistics */}
              {priceAnalysis.market_avg_price_per_sqm && (
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Market Average Price/m²</dt>
                      <dd className="mt-1 text-lg font-semibold text-gray-900">
                        {new Intl.NumberFormat('fr-FR', {
                          style: 'currency',
                          currency: 'EUR',
                          maximumFractionDigits: 0,
                        }).format(priceAnalysis.market_avg_price_per_sqm)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Your Price/m²</dt>
                      <dd className="mt-1 text-lg font-semibold text-gray-900">
                        {new Intl.NumberFormat('fr-FR', {
                          style: 'currency',
                          currency: 'EUR',
                          maximumFractionDigits: 0,
                        }).format(priceAnalysis.price_per_sqm)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Market Median Price/m²</dt>
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
                        Delete Property
                      </h3>
                      <div className="mt-2">
                        <p className="text-sm text-gray-500">
                          Are you sure you want to delete this property? This action cannot be undone. All associated documents, analyses, and photos will be permanently deleted.
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
                          Deleting...
                        </>
                      ) : (
                        'Delete'
                      )}
                    </button>
                    <button
                      type="button"
                      disabled={deleting}
                      onClick={() => setShowDeleteConfirm(false)}
                      className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 sm:mt-0 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Cancel
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
