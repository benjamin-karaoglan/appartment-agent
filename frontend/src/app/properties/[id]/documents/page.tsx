"use client";

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/ProtectedRoute';
import Header from '@/components/Header';
import { api } from '@/lib/api';
import {
  ArrowLeft,
  Upload,
  FileText,
  Loader2,
  Trash2,
  CheckCircle,
  AlertCircle,
  RefreshCw
} from 'lucide-react';
import Link from 'next/link';

interface Document {
  id: number;
  filename: string;
  file_type: string;
  document_category: string;
  document_subcategory?: string;
  document_date?: string;
  is_analyzed: boolean;
  analysis_summary?: string;
  key_insights?: string[];
  estimated_annual_cost?: number;
  one_time_costs?: Array<{item: string; amount: number; timeline?: string}>;
  upload_date: string;
  parsed_at?: string;
  file_size: number;
}

interface DocumentSummary {
  id: number;
  property_id: number;
  category: string;
  summary?: string;
  key_findings?: string[];
  total_estimated_annual_cost?: number;
  total_one_time_costs?: number;
  cost_breakdown?: Record<string, number>;
  copropriete_insights?: any;
  diagnostic_issues?: any;
  created_at: string;
  updated_at: string;
  document_count: number;
}

const DOCUMENT_CATEGORIES = [
  {
    id: 'pv_ag',
    label: "PV d'AG",
    description: 'Assembly meeting minutes',
    icon: FileText,
    acceptedTypes: '.pdf',
    hasSubcategory: false,
  },
  {
    id: 'diags',
    label: 'Diagnostics',
    description: 'Diagnostic documents',
    icon: FileText,
    acceptedTypes: '.pdf',
    hasSubcategory: true,
    subcategories: [
      { value: 'dpe', label: 'DPE (Energy Performance)' },
      { value: 'amiante', label: 'Amiante (Asbestos)' },
      { value: 'plomb', label: 'Plomb (Lead)' },
      { value: 'termite', label: 'Termite' },
      { value: 'electric', label: 'Electrical' },
      { value: 'gas', label: 'Gas' },
    ],
  },
  {
    id: 'taxe_fonciere',
    label: 'Taxe Foncière',
    description: 'Property tax documents',
    icon: FileText,
    acceptedTypes: '.pdf',
    hasSubcategory: false,
  },
  {
    id: 'charges',
    label: 'Charges',
    description: 'Condominium charges',
    icon: FileText,
    acceptedTypes: '.pdf',
    hasSubcategory: false,
  },
];

function DocumentsPageContent() {
  const params = useParams();
  const router = useRouter();
  const propertyId = params.id as string;

  const [documents, setDocuments] = useState<Record<string, Document[]>>({});
  const [summaries, setSummaries] = useState<Record<string, DocumentSummary>>({});
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [selectedSubcategory, setSelectedSubcategory] = useState<Record<string, string>>({});
  const [regenerating, setRegenerating] = useState<string | null>(null);

  useEffect(() => {
    loadDocuments();
    loadSummaries();
  }, [propertyId]);

  const loadDocuments = async () => {
    try {
      const response = await api.get(`/api/documents?property_id=${propertyId}`);

      // Group documents by category
      const grouped: Record<string, Document[]> = {};
      response.data.forEach((doc: Document) => {
        if (!grouped[doc.document_category]) {
          grouped[doc.document_category] = [];
        }
        grouped[doc.document_category].push(doc);
      });

      setDocuments(grouped);
    } catch (error) {
      console.error('Failed to load documents:', error);
      setError('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const loadSummaries = async () => {
    try {
      const response = await api.get(`/api/documents/summaries/${propertyId}`);

      // Convert array to object keyed by category
      const summariesByCategory: Record<string, DocumentSummary> = {};
      response.data.forEach((summary: DocumentSummary) => {
        summariesByCategory[summary.category] = summary;
      });

      setSummaries(summariesByCategory);
    } catch (error) {
      console.error('Failed to load summaries:', error);
    }
  };

  const handleFileUpload = async (category: string, files: FileList | null) => {
    if (!files || files.length === 0) return;

    setUploading(category);
    setError('');

    try {
      // Upload each file
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('property_id', propertyId);
        formData.append('document_category', category);

        // Add subcategory if required
        if (category === 'diags' && selectedSubcategory[category]) {
          formData.append('document_subcategory', selectedSubcategory[category]);
        }

        formData.append('auto_parse', 'true');

        await api.post('/api/documents/upload', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        });
      }

      // Reload documents and summaries
      await loadDocuments();
      await loadSummaries();
    } catch (err: any) {
      console.error('Upload error:', err);
      setError(err.response?.data?.detail || 'Failed to upload document');
    } finally {
      setUploading(null);
    }
  };

  const handleRegenerateSummary = async (category: string) => {
    setRegenerating(category);
    setError('');

    try {
      await api.post(`/api/documents/summaries/${propertyId}/regenerate?category=${category}`);
      await loadSummaries();
    } catch (err: any) {
      console.error('Regenerate error:', err);
      setError(err.response?.data?.detail || 'Failed to regenerate summary');
    } finally {
      setRegenerating(null);
    }
  };

  const handleDeleteDocument = async (documentId: number, category: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
      await api.delete(`/api/documents/${documentId}`);
      await loadDocuments();
      await loadSummaries();
    } catch (err: any) {
      console.error('Delete error:', err);
      setError(err.response?.data?.detail || 'Failed to delete document');
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

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <Link
            href={`/properties/${propertyId}`}
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-6"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Property
          </Link>

          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">Document Management</h1>
            <p className="mt-2 text-sm text-gray-600">
              Upload and manage property documents. Documents are automatically analyzed using AI.
            </p>
          </div>

          {error && (
            <div className="mb-6 rounded-md bg-red-50 p-4">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          <div className="space-y-8">
            {DOCUMENT_CATEGORIES.map((category) => {
              const categoryDocs = documents[category.id] || [];
              const categorySummary = summaries[category.id];
              const Icon = category.icon;

              return (
                <div key={category.id} className="bg-white shadow rounded-lg overflow-hidden">
                  <div className="bg-gradient-to-r from-blue-500 to-blue-600 px-6 py-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center">
                        <Icon className="h-6 w-6 text-white mr-3" />
                        <div>
                          <h2 className="text-xl font-semibold text-white">{category.label}</h2>
                          <p className="text-sm text-blue-100">{category.description}</p>
                        </div>
                      </div>
                      <div className="text-white text-sm">
                        {categoryDocs.length} document{categoryDocs.length !== 1 ? 's' : ''}
                      </div>
                    </div>
                  </div>

                  <div className="p-6">
                    <div className="mb-6">
                      <div className="flex items-start gap-4">
                        {category.hasSubcategory && (
                          <div className="flex-1">
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                              Diagnostic Type
                            </label>
                            <select
                              value={selectedSubcategory[category.id] || ''}
                              onChange={(e) => setSelectedSubcategory({
                                ...selectedSubcategory,
                                [category.id]: e.target.value
                              })}
                              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                            >
                              <option value="">Select diagnostic type...</option>
                              {category.subcategories?.map((sub) => (
                                <option key={sub.value} value={sub.value}>
                                  {sub.label}
                                </option>
                              ))}
                            </select>
                          </div>
                        )}

                        <div className={category.hasSubcategory ? 'flex-1' : 'flex-1'}>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Upload Document{!category.hasSubcategory && 's'}
                          </label>
                          <label className="relative cursor-pointer">
                            <input
                              type="file"
                              accept={category.acceptedTypes}
                              multiple={!category.hasSubcategory}
                              onChange={(e) => handleFileUpload(category.id, e.target.files)}
                              disabled={uploading === category.id || (category.hasSubcategory && !selectedSubcategory[category.id])}
                              className="hidden"
                            />
                            <div className={`flex items-center justify-center px-4 py-2 border-2 border-dashed rounded-md ${
                              uploading === category.id || (category.hasSubcategory && !selectedSubcategory[category.id])
                                ? 'border-gray-300 bg-gray-50 cursor-not-allowed'
                                : 'border-blue-300 hover:border-blue-500 bg-blue-50 hover:bg-blue-100'
                            }`}>
                              {uploading === category.id ? (
                                <>
                                  <Loader2 className="h-5 w-5 mr-2 animate-spin text-blue-600" />
                                  <span className="text-sm text-blue-600">Uploading & Analyzing...</span>
                                </>
                              ) : (
                                <>
                                  <Upload className="h-5 w-5 mr-2 text-blue-600" />
                                  <span className="text-sm text-blue-600">
                                    {category.hasSubcategory && !selectedSubcategory[category.id]
                                      ? 'Select type first'
                                      : `Choose ${category.acceptedTypes} file${!category.hasSubcategory ? 's' : ''}`
                                    }
                                  </span>
                                </>
                              )}
                            </div>
                          </label>
                        </div>
                      </div>
                    </div>

                    {(category.id === 'pv_ag' || category.id === 'diags') && categorySummary && (
                      <div className="mb-6 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg p-4 border border-purple-200">
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-lg font-semibold text-gray-900">
                            {category.id === 'pv_ag' ? 'Comprehensive Summary' : 'Diagnostic Summary'}
                          </h3>
                          <button
                            onClick={() => handleRegenerateSummary(category.id)}
                            disabled={regenerating === category.id}
                            className="inline-flex items-center px-3 py-1 border border-purple-300 text-xs font-medium rounded text-purple-700 bg-white hover:bg-purple-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:opacity-50"
                          >
                            {regenerating === category.id ? (
                              <>
                                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                                Regenerating...
                              </>
                            ) : (
                              <>
                                <RefreshCw className="h-3 w-3 mr-1" />
                                Regenerate
                              </>
                            )}
                          </button>
                        </div>

                        {categorySummary.summary && (
                          <div className="mb-4">
                            <p className="text-sm text-gray-700">{categorySummary.summary}</p>
                          </div>
                        )}

                        {categorySummary.key_findings && categorySummary.key_findings.length > 0 && (
                          <div className="mb-4">
                            <h4 className="text-sm font-medium text-gray-900 mb-2">Key Findings</h4>
                            <ul className="space-y-1">
                              {categorySummary.key_findings.map((finding, idx) => (
                                <li key={idx} className="text-sm text-gray-700 flex items-start">
                                  <span className="text-purple-500 mr-2">•</span>
                                  {finding}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {(categorySummary.total_estimated_annual_cost || categorySummary.total_one_time_costs) && (
                          <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-purple-200">
                            {categorySummary.total_estimated_annual_cost && (
                              <div>
                                <dt className="text-xs font-medium text-gray-500">Annual Costs</dt>
                                <dd className="mt-1 text-lg font-semibold text-gray-900">
                                  {new Intl.NumberFormat('fr-FR', {
                                    style: 'currency',
                                    currency: 'EUR',
                                    maximumFractionDigits: 0,
                                  }).format(categorySummary.total_estimated_annual_cost)}
                                </dd>
                              </div>
                            )}
                            {categorySummary.total_one_time_costs && (
                              <div>
                                <dt className="text-xs font-medium text-gray-500">One-Time Costs</dt>
                                <dd className="mt-1 text-lg font-semibold text-gray-900">
                                  {new Intl.NumberFormat('fr-FR', {
                                    style: 'currency',
                                    currency: 'EUR',
                                    maximumFractionDigits: 0,
                                  }).format(categorySummary.total_one_time_costs)}
                                </dd>
                              </div>
                            )}
                          </div>
                        )}

                        {category.id === 'pv_ag' && categorySummary.copropriete_insights && (
                          <div className="mt-4 pt-4 border-t border-purple-200">
                            <h4 className="text-sm font-medium text-gray-900 mb-2">Copropriété Insights</h4>
                            {categorySummary.copropriete_insights.payment_issues && (
                              <div className="mb-2">
                                <p className="text-xs font-medium text-gray-700">Payment Issues:</p>
                                <p className="text-sm text-gray-600">{categorySummary.copropriete_insights.payment_issues}</p>
                              </div>
                            )}
                            {categorySummary.copropriete_insights.upcoming_works && (
                              <div className="mb-2">
                                <p className="text-xs font-medium text-gray-700">Upcoming Works:</p>
                                <p className="text-sm text-gray-600">{categorySummary.copropriete_insights.upcoming_works}</p>
                              </div>
                            )}
                          </div>
                        )}

                        {category.id === 'diags' && categorySummary.diagnostic_issues && (
                          <div className="mt-4 pt-4 border-t border-purple-200">
                            <h4 className="text-sm font-medium text-gray-900 mb-2">Critical Issues</h4>
                            {categorySummary.diagnostic_issues.critical_issues && (
                              <ul className="space-y-1">
                                {categorySummary.diagnostic_issues.critical_issues.map((issue: string, idx: number) => (
                                  <li key={idx} className="text-sm text-red-700 flex items-start">
                                    <AlertCircle className="h-4 w-4 mr-2 mt-0.5 flex-shrink-0" />
                                    {issue}
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {categoryDocs.length > 0 ? (
                      <div className="space-y-3">
                        {categoryDocs.map((doc) => (
                          <div
                            key={doc.id}
                            className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
                          >
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <div className="flex items-center">
                                  <FileText className="h-5 w-5 text-gray-400 mr-2" />
                                  <h4 className="text-sm font-medium text-gray-900">{doc.filename}</h4>
                                  {doc.is_analyzed ? (
                                    <CheckCircle className="h-4 w-4 text-green-500 ml-2" />
                                  ) : (
                                    <Loader2 className="h-4 w-4 text-blue-500 ml-2 animate-spin" />
                                  )}
                                </div>

                                <div className="mt-1 flex items-center text-xs text-gray-500 space-x-3">
                                  {doc.document_subcategory && (
                                    <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded">
                                      {doc.document_subcategory.toUpperCase()}
                                    </span>
                                  )}
                                  <span>Uploaded {new Date(doc.upload_date).toLocaleDateString('fr-FR')}</span>
                                  <span>{(doc.file_size / 1024).toFixed(1)} KB</span>
                                </div>

                                {doc.is_analyzed && doc.analysis_summary && (
                                  <div className="mt-3 bg-gray-50 rounded p-3">
                                    <p className="text-sm text-gray-700">{doc.analysis_summary}</p>

                                    {doc.key_insights && doc.key_insights.length > 0 && (
                                      <div className="mt-2">
                                        <p className="text-xs font-medium text-gray-700 mb-1">Key Insights:</p>
                                        <ul className="space-y-1">
                                          {doc.key_insights.map((insight, idx) => (
                                            <li key={idx} className="text-xs text-gray-600 flex items-start">
                                              <span className="text-blue-500 mr-1">•</span>
                                              {insight}
                                            </li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}

                                    {doc.one_time_costs && doc.one_time_costs.length > 0 && (
                                      <div className="mt-2">
                                        <p className="text-xs font-medium text-gray-700 mb-1">Costs:</p>
                                        <ul className="space-y-1">
                                          {doc.one_time_costs.map((cost, idx) => (
                                            <li key={idx} className="text-xs text-gray-600">
                                              {cost.item}: {new Intl.NumberFormat('fr-FR', {
                                                style: 'currency',
                                                currency: 'EUR',
                                              }).format(cost.amount)}
                                              {cost.timeline && ` (${cost.timeline})`}
                                            </li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>

                              <button
                                onClick={() => handleDeleteDocument(doc.id, category.id)}
                                className="ml-4 text-red-600 hover:text-red-800"
                              >
                                <Trash2 className="h-5 w-5" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-8 text-gray-500">
                        <FileText className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                        <p className="text-sm">No documents uploaded yet</p>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}

export default function DocumentsPage() {
  return (
    <ProtectedRoute>
      <DocumentsPageContent />
    </ProtectedRoute>
  );
}
