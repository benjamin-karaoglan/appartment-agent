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
  RefreshCw,
  Sparkles,
  Clock,
  CheckCircle2
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

interface PropertySynthesis {
  id: number;
  property_id: number;
  overall_summary: string;
  risk_level: string;
  total_annual_cost: number;
  total_one_time_cost: number;
  key_findings: string[];
  recommendations: string[];
  last_updated: string;
}

interface BulkUploadStatus {
  workflow_id: string;
  property_id: number;
  status: string;
  progress: {
    total: number;
    completed: number;
    failed: number;
    processing: number;
    percentage: number;
  };
  documents: Array<{
    id: number;
    filename: string;
    document_category: string;
    document_subcategory?: string;
    processing_status: string;
    is_analyzed: boolean;
    processing_error?: string;
  }>;
  synthesis?: {
    summary: string;
    total_annual_cost: number;
    total_one_time_cost: number;
    risk_level: string;
    key_findings: string[];
    recommendations: string[];
  };
}

const DOCUMENT_CATEGORIES = [
  {
    id: 'pv_ag',
    label: "PV d'AG",
    description: 'Assembly meeting minutes',
    icon: FileText,
    acceptedTypes: '.pdf',
  },
  {
    id: 'diags',
    label: 'Diagnostics',
    description: 'Diagnostic documents',
    icon: FileText,
    acceptedTypes: '.pdf',
  },
  {
    id: 'taxe_fonciere',
    label: 'Taxe Foncière',
    description: 'Property tax documents',
    icon: FileText,
    acceptedTypes: '.pdf',
  },
  {
    id: 'charges',
    label: 'Charges',
    description: 'Condominium charges',
    icon: FileText,
    acceptedTypes: '.pdf',
  },
];

function DocumentsPageContent() {
  const params = useParams();
  const router = useRouter();
  const propertyId = params.id as string;

  const [documents, setDocuments] = useState<Record<string, Document[]>>({});
  const [summaries, setSummaries] = useState<Record<string, DocumentSummary>>({});
  const [synthesis, setSynthesis] = useState<PropertySynthesis | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [regenerating, setRegenerating] = useState<string | null>(null);

  // Smart upload states
  const [bulkUploading, setBulkUploading] = useState(false);
  const [bulkStatus, setBulkStatus] = useState<BulkUploadStatus | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    loadDocuments();
    loadSummaries();
    loadSynthesis();
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

  const loadSynthesis = async () => {
    try {
      const response = await api.get(`/api/documents/synthesis/${propertyId}`);
      setSynthesis(response.data);
    } catch (error) {
      console.error('Failed to load synthesis:', error);
      setSynthesis(null);
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
      await loadSynthesis();
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
      await loadSynthesis();
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
      await loadSynthesis();
    } catch (err: any) {
      console.error('Delete error:', err);
      setError(err.response?.data?.detail || 'Failed to delete document');
    }
  };

  // Bulk upload handlers
  const handleBulkUpload = async (files: FileList) => {
    setBulkUploading(true);
    setError('');
    setBulkStatus(null);

    try {
      const formData = new FormData();
      Array.from(files).forEach(file => {
        formData.append('files', file);
      });
      formData.append('property_id', propertyId);

      const response = await api.post('/api/documents/bulk-upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const { workflow_id } = response.data;

      // Start polling for status
      pollBulkStatus(workflow_id);
    } catch (err: any) {
      console.error('Bulk upload error:', err);
      setError(err.response?.data?.detail || 'Failed to upload documents');
      setBulkUploading(false);
    }
  };

  const pollBulkStatus = async (workflowId: string) => {
    const maxPolls = 300; // Poll for up to 10 minutes (300 x 2s = 600s)
    let pollCount = 0;

    const poll = async () => {
      try {
        const response = await api.get(`/api/documents/bulk-status/${workflowId}`);
        const status: BulkUploadStatus = response.data;
        setBulkStatus(status);

        // Check if workflow is complete
        if (status.status === 'completed' || status.progress.percentage === 100) {
          // Continue polling for synthesis (takes ~30s to generate)
          // Poll every 2 seconds for up to 20 attempts (40 seconds total)
          let currentStatus = status;
          let synthesisAttempts = 0;
          const maxSynthesisAttempts = 20;

          while (!currentStatus.synthesis && synthesisAttempts < maxSynthesisAttempts) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            try {
              const synthResponse = await api.get(`/api/documents/bulk-status/${workflowId}`);
              currentStatus = synthResponse.data;
              setBulkStatus(currentStatus);

              if (currentStatus.synthesis) {
                break; // Synthesis found!
              }
              synthesisAttempts++;
            } catch (err) {
              console.error('Synthesis poll error:', err);
              break;
            }
          }

          setBulkUploading(false);
          await loadDocuments();
          await loadSummaries();
          await loadSynthesis();
          return;
        }

        // Check if workflow failed
        if (status.status === 'failed') {
          setBulkUploading(false);
          setError('Bulk processing failed. Check individual document errors.');
          return;
        }

        // Continue polling if still processing
        pollCount++;
        if (pollCount < maxPolls && (status.status === 'running' || status.status === 'processing')) {
          setTimeout(poll, 2000); // Poll every 2 seconds
        } else if (pollCount >= maxPolls) {
          setBulkUploading(false);
          setError('Processing is taking longer than expected. Please check back later.');
        }
      } catch (err: any) {
        console.error('Status poll error:', err);
        pollCount++;
        if (pollCount < maxPolls) {
          setTimeout(poll, 2000);
        } else {
          setBulkUploading(false);
          setError('Failed to check processing status');
        }
      }
    };

    poll();
  };

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleBulkUpload(files);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleBulkUpload(files);
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

          {/* Smart Upload Section */}
          <div className="mb-8 bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 rounded-xl shadow-lg overflow-hidden border-2 border-purple-200">
            <div className="bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-4">
              <div className="flex items-center">
                <Sparkles className="h-6 w-6 text-yellow-300 mr-3" />
                <div>
                  <h2 className="text-xl font-bold text-white">Smart Upload - AI Agent</h2>
                  <p className="text-sm text-indigo-100">
                    Drop all your documents at once. AI will automatically classify, analyze, and summarize everything!
                  </p>
                </div>
              </div>
            </div>

            <div className="p-6">
              {!bulkUploading && !bulkStatus && (
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`relative border-3 border-dashed rounded-lg p-12 text-center transition-all ${
                    isDragging
                      ? 'border-purple-500 bg-purple-100 scale-105'
                      : 'border-purple-300 bg-white hover:border-purple-400 hover:bg-purple-50'
                  }`}
                >
                  <input
                    type="file"
                    multiple
                    accept=".pdf"
                    onChange={handleFileSelect}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                    id="bulk-upload-input"
                  />
                  <Sparkles className="h-16 w-16 mx-auto mb-4 text-purple-500" />
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    Drop all your documents here
                  </h3>
                  <p className="text-sm text-gray-600 mb-4">
                    or click to browse files
                  </p>
                  <div className="flex items-center justify-center gap-2 text-xs text-gray-500">
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span>Auto-classification</span>
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span>Parallel processing</span>
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span>Smart synthesis</span>
                  </div>
                </div>
              )}

              {bulkUploading && bulkStatus && (
                <div className="bg-white rounded-lg p-6 border border-purple-200">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center">
                      <Loader2 className="h-6 w-6 text-purple-600 animate-spin mr-3" />
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">Processing Documents</h3>
                        <p className="text-sm text-gray-600">
                          AI agent is classifying and analyzing your documents...
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-3xl font-bold text-purple-600">
                        {bulkStatus.progress.percentage}%
                      </div>
                      <div className="text-xs text-gray-500">
                        {bulkStatus.progress.completed} / {bulkStatus.progress.total} complete
                      </div>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="mb-6">
                    <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-purple-500 to-pink-500 h-3 rounded-full transition-all duration-500"
                        style={{ width: `${bulkStatus.progress.percentage}%` }}
                      />
                    </div>
                  </div>

                  {/* Document list */}
                  <div className="space-y-2">
                    {bulkStatus.documents.map((doc) => (
                      <div
                        key={doc.id}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                      >
                        <div className="flex items-center flex-1">
                          <FileText className="h-4 w-4 text-gray-400 mr-3" />
                          <div className="flex-1">
                            <p className="text-sm font-medium text-gray-900">{doc.filename}</p>
                            <div className="flex items-center gap-2 mt-1">
                              {doc.document_category && doc.document_category !== 'pending_classification' && (
                                <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
                                  {doc.document_category}
                                </span>
                              )}
                              {doc.document_subcategory && (
                                <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded">
                                  {doc.document_subcategory}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center">
                          {doc.processing_status === 'completed' && (
                            <CheckCircle className="h-5 w-5 text-green-500" />
                          )}
                          {doc.processing_status === 'processing' && (
                            <Loader2 className="h-5 w-5 text-purple-500 animate-spin" />
                          )}
                          {doc.processing_status === 'failed' && (
                            <AlertCircle className="h-5 w-5 text-red-500" />
                          )}
                          {doc.processing_status === 'pending' && (
                            <Clock className="h-5 w-5 text-gray-400" />
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {!bulkUploading && bulkStatus && (
                <div className="bg-white rounded-lg p-6 border border-green-200">
                  <div className="flex items-center mb-4">
                    <CheckCircle className="h-8 w-8 text-green-500 mr-3" />
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900">Processing Complete!</h3>
                      <p className="text-sm text-gray-600">
                        {bulkStatus.progress.completed} documents analyzed successfully
                      </p>
                    </div>
                  </div>

                  {bulkStatus.synthesis && (
                    <div className="mt-4 p-4 bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg border border-purple-200">
                      <h4 className="text-md font-semibold text-gray-900 mb-3 flex items-center">
                        <Sparkles className="h-5 w-5 text-purple-500 mr-2" />
                        AI Synthesis
                      </h4>

                      {bulkStatus.synthesis.summary && (
                        <p className="text-sm text-gray-700 mb-4">{bulkStatus.synthesis.summary}</p>
                      )}

                      {bulkStatus.synthesis.risk_level && (
                        <div className="mb-3">
                          <span className="text-xs font-medium text-gray-700">Risk Level: </span>
                          <span className={`text-xs px-2 py-1 rounded ${
                            bulkStatus.synthesis.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                            bulkStatus.synthesis.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-green-100 text-green-700'
                          }`}>
                            {bulkStatus.synthesis.risk_level.toUpperCase()}
                          </span>
                        </div>
                      )}

                      {bulkStatus.synthesis.key_findings && bulkStatus.synthesis.key_findings.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs font-medium text-gray-700 mb-2">Key Findings:</p>
                          <ul className="space-y-1">
                            {bulkStatus.synthesis.key_findings.map((finding, idx) => (
                              <li key={idx} className="text-sm text-gray-700 flex items-start">
                                <span className="text-purple-500 mr-2">•</span>
                                {finding}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {bulkStatus.synthesis.recommendations && bulkStatus.synthesis.recommendations.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs font-medium text-gray-700 mb-2">Recommendations:</p>
                          <ul className="space-y-1">
                            {bulkStatus.synthesis.recommendations.map((rec, idx) => (
                              <li key={idx} className="text-sm text-gray-700 flex items-start">
                                <span className="text-pink-500 mr-2">→</span>
                                {rec}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {(bulkStatus.synthesis.total_annual_cost || bulkStatus.synthesis.total_one_time_cost) && (
                        <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-purple-200">
                          {bulkStatus.synthesis.total_annual_cost && (
                            <div>
                              <dt className="text-xs font-medium text-gray-500">Total Annual Costs</dt>
                              <dd className="mt-1 text-lg font-semibold text-gray-900">
                                {new Intl.NumberFormat('fr-FR', {
                                  style: 'currency',
                                  currency: 'EUR',
                                  maximumFractionDigits: 0,
                                }).format(bulkStatus.synthesis.total_annual_cost)}
                              </dd>
                            </div>
                          )}
                          {bulkStatus.synthesis.total_one_time_cost && (
                            <div>
                              <dt className="text-xs font-medium text-gray-500">Total One-Time Costs</dt>
                              <dd className="mt-1 text-lg font-semibold text-gray-900">
                                {new Intl.NumberFormat('fr-FR', {
                                  style: 'currency',
                                  currency: 'EUR',
                                  maximumFractionDigits: 0,
                                }).format(bulkStatus.synthesis.total_one_time_cost)}
                              </dd>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  <button
                    onClick={() => setBulkStatus(null)}
                    className="mt-4 w-full px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                  >
                    Upload More Documents
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Overall Property Synthesis */}
          {synthesis && (
            <div className="mb-8 bg-gradient-to-br from-purple-50 via-pink-50 to-indigo-50 rounded-xl p-6 border-2 border-purple-200 shadow-lg">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold text-gray-900 flex items-center">
                  <svg className="w-8 h-8 mr-3 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  AI Property Analysis
                </h2>
                <span className={`px-4 py-2 rounded-full text-sm font-semibold ${
                  synthesis.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                  synthesis.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-green-100 text-green-700'
                }`}>
                  Risk: {synthesis.risk_level.toUpperCase()}
                </span>
              </div>

              <p className="text-gray-700 mb-6 leading-relaxed">{synthesis.overall_summary}</p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div className="bg-white rounded-lg p-4 shadow">
                  <dt className="text-sm font-medium text-gray-500">Total Annual Costs</dt>
                  <dd className="mt-2 text-3xl font-bold text-gray-900">
                    {new Intl.NumberFormat('fr-FR', {
                      style: 'currency',
                      currency: 'EUR',
                      maximumFractionDigits: 0,
                    }).format(synthesis.total_annual_cost)}
                  </dd>
                </div>
                <div className="bg-white rounded-lg p-4 shadow">
                  <dt className="text-sm font-medium text-gray-500">Total One-Time Costs</dt>
                  <dd className="mt-2 text-3xl font-bold text-gray-900">
                    {new Intl.NumberFormat('fr-FR', {
                      style: 'currency',
                      currency: 'EUR',
                      maximumFractionDigits: 0,
                    }).format(synthesis.total_one_time_cost)}
                  </dd>
                </div>
              </div>

              {synthesis.key_findings && synthesis.key_findings.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Key Findings</h3>
                  <ul className="space-y-2">
                    {synthesis.key_findings.map((finding, idx) => (
                      <li key={idx} className="flex items-start text-gray-700">
                        <svg className="w-5 h-5 text-purple-500 mr-2 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        {finding}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {synthesis.recommendations && synthesis.recommendations.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Recommendations</h3>
                  <ul className="space-y-2">
                    {synthesis.recommendations.map((rec, idx) => (
                      <li key={idx} className="flex items-start text-gray-700">
                        <svg className="w-5 h-5 text-pink-500 mr-2 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                        </svg>
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Manual Upload Section Divider */}
          <div className="mb-6 flex items-center">
            <div className="flex-1 border-t border-gray-300"></div>
            <div className="px-4 text-sm text-gray-500 font-medium">Or upload manually by category</div>
            <div className="flex-1 border-t border-gray-300"></div>
          </div>

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
                        <div className="flex-1">
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Upload Documents
                          </label>
                          <label className="relative cursor-pointer">
                            <input
                              type="file"
                              accept={category.acceptedTypes}
                              multiple
                              onChange={(e) => handleFileUpload(category.id, e.target.files)}
                              disabled={uploading === category.id}
                              className="hidden"
                            />
                            <div className={`flex items-center justify-center px-4 py-2 border-2 border-dashed rounded-md ${
                              uploading === category.id
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
                                    Choose {category.acceptedTypes} files
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
