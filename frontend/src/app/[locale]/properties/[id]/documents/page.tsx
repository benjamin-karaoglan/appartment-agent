"use client";

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/ProtectedRoute';
import Header from '@/components/Header';
import { api } from '@/lib/api';
import {
  ArrowLeft,
  FileText,
  Loader2,
  Trash2,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Sparkles,
  Clock,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Pencil,
  Check,
  X,
} from 'lucide-react';
import { Link } from '@/i18n/navigation';
import { useTranslations } from 'next-intl';

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
  processing_status?: string;
  workflow_id?: string;
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

const CATEGORY_ORDER = ['pv_ag', 'diags', 'taxe_fonciere', 'charges', 'other'] as const;

function getCategoryLabel(category: string, t: (key: string) => string): string {
  const known = ['pv_ag', 'diags', 'taxe_fonciere', 'charges', 'other'];
  if (known.includes(category)) {
    return t(`categories.${category}.label`);
  }
  return category;
}

function getCategoryColor(_category: string): string {
  return 'bg-blue-100 text-blue-700';
}

function DocumentsPageContent() {
  const t = useTranslations('documents');
  const tc = useTranslations('common');
  const params = useParams();
  const router = useRouter();
  const propertyId = params.id as string;

  const [documents, setDocuments] = useState<Document[]>([]);
  const [synthesis, setSynthesis] = useState<PropertySynthesis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Smart upload states
  const [bulkUploading, setBulkUploading] = useState(false);
  const [bulkStatus, setBulkStatus] = useState<BulkUploadStatus | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Document list states
  const [expandedDoc, setExpandedDoc] = useState<number | null>(null);
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());
  const [regenerating, setRegenerating] = useState(false);

  // Rename states
  const [renamingDocId, setRenamingDocId] = useState<number | null>(null);
  const [renameValue, setRenameValue] = useState('');

  // Multi-select / bulk delete states
  const [selectedDocs, setSelectedDocs] = useState<Set<number>>(new Set());
  const [showBulkDeleteConfirm, setShowBulkDeleteConfirm] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  useEffect(() => {
    const init = async () => {
      try {
        const response = await api.get(`/api/documents?property_id=${propertyId}`);
        setDocuments(response.data);

        // Detect documents still being processed and resume polling
        const processingDocs = (response.data as Document[]).filter(
          (d) => d.processing_status === 'processing' || d.processing_status === 'pending'
        );
        if (processingDocs.length > 0) {
          const workflowId = processingDocs.find((d) => d.workflow_id)?.workflow_id;
          if (workflowId) {
            setBulkUploading(true);
            pollBulkStatus(workflowId);
          }
        }
      } catch (error) {
        console.error('Failed to load documents:', error);
        setError('Failed to load documents');
      } finally {
        setLoading(false);
      }
    };

    init();
    loadSynthesis();
  }, [propertyId]);

  const loadDocuments = async () => {
    try {
      const response = await api.get(`/api/documents?property_id=${propertyId}`);
      setDocuments(response.data);
    } catch (error) {
      console.error('Failed to load documents:', error);
      setError('Failed to load documents');
    } finally {
      setLoading(false);
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

  const handleDeleteDocument = async (documentId: number) => {
    if (!confirm(t('confirmDelete'))) return;

    try {
      await api.delete(`/api/documents/${documentId}`);
      await loadDocuments();
      await loadSynthesis();
    } catch (err: any) {
      console.error('Delete error:', err);
      setError(err.response?.data?.detail || 'Failed to delete document');
    }
  };

  const handleRegenerateSynthesis = async () => {
    setRegenerating(true);
    setError('');

    try {
      const response = await api.post(`/api/documents/synthesis/${propertyId}/regenerate-overall`);
      setSynthesis(response.data);
    } catch (err: any) {
      console.error('Regenerate error:', err);
      setError(err.response?.data?.detail || 'Failed to regenerate synthesis');
    } finally {
      setRegenerating(false);
    }
  };

  // Rename handlers
  const handleStartRename = (doc: Document) => {
    const ext = doc.filename.substring(doc.filename.lastIndexOf('.'));
    const nameWithoutExt = doc.filename.substring(0, doc.filename.lastIndexOf('.'));
    setRenamingDocId(doc.id);
    setRenameValue(nameWithoutExt);
  };

  const handleSaveRename = async (doc: Document) => {
    if (!renameValue.trim()) return;
    const ext = doc.filename.substring(doc.filename.lastIndexOf('.'));
    try {
      const response = await api.patch(`/api/documents/${doc.id}`, { filename: renameValue.trim() + ext });
      setDocuments(prev => prev.map(d => d.id === doc.id ? { ...d, filename: response.data.filename } : d));
      setRenamingDocId(null);
      setRenameValue('');
    } catch (err: any) {
      console.error('Rename error:', err);
      setError(err.response?.data?.detail || 'Failed to rename document');
    }
  };

  const handleCancelRename = () => {
    setRenamingDocId(null);
    setRenameValue('');
  };

  // Multi-select handlers
  const toggleDocSelection = (docId: number) => {
    setSelectedDocs(prev => {
      const next = new Set(prev);
      if (next.has(docId)) {
        next.delete(docId);
      } else {
        next.add(docId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedDocs.size === documents.length) {
      setSelectedDocs(new Set());
    } else {
      setSelectedDocs(new Set(documents.map(d => d.id)));
    }
  };

  const handleBulkDelete = async () => {
    setBulkDeleting(true);
    try {
      await api.post('/api/documents/bulk-delete', { document_ids: Array.from(selectedDocs) });
      setSelectedDocs(new Set());
      setShowBulkDeleteConfirm(false);
      await loadDocuments();
      await loadSynthesis();
    } catch (err: any) {
      console.error('Bulk delete error:', err);
      setError(err.response?.data?.detail || 'Failed to delete documents');
    } finally {
      setBulkDeleting(false);
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
      pollBulkStatus(workflow_id);
    } catch (err: any) {
      console.error('Bulk upload error:', err);
      setError(err.response?.data?.detail || 'Failed to upload documents');
      setBulkUploading(false);
    }
  };

  const pollBulkStatus = async (workflowId: string) => {
    const maxPolls = 300;
    let pollCount = 0;

    const poll = async () => {
      try {
        const response = await api.get(`/api/documents/bulk-status/${workflowId}`);
        const status: BulkUploadStatus = response.data;
        setBulkStatus(status);

        if (status.status === 'completed' || status.progress.percentage === 100) {
          let currentStatus = status;
          let synthesisAttempts = 0;
          const maxSynthesisAttempts = 20;

          while (!currentStatus.synthesis && synthesisAttempts < maxSynthesisAttempts) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            try {
              const synthResponse = await api.get(`/api/documents/bulk-status/${workflowId}`);
              currentStatus = synthResponse.data;
              setBulkStatus(currentStatus);
              if (currentStatus.synthesis) break;
              synthesisAttempts++;
            } catch (err) {
              console.error('Synthesis poll error:', err);
              break;
            }
          }

          setBulkUploading(false);
          await loadDocuments();
          await loadSynthesis();
          return;
        }

        if (status.status === 'failed') {
          setBulkUploading(false);
          setError(t('bulkFailed'));
          return;
        }

        pollCount++;
        if (pollCount < maxPolls && (status.status === 'running' || status.status === 'processing')) {
          setTimeout(poll, 2000);
        } else if (pollCount >= maxPolls) {
          setBulkUploading(false);
          setError(t('processingTimeout'));
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

  const toggleCategory = (category: string) => {
    setCollapsedCategories(prev => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  // Group documents by category
  const groupedDocs = documents.reduce<Record<string, Document[]>>((acc, doc) => {
    const cat = doc.document_category || 'other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(doc);
    return acc;
  }, {});

  // Sort categories in defined order, with any unknown categories at the end
  const sortedCategories = [
    ...CATEGORY_ORDER.filter(c => groupedDocs[c]),
    ...Object.keys(groupedDocs).filter(c => !(CATEGORY_ORDER as readonly string[]).includes(c)),
  ];

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
            {t('backToProperty')}
          </Link>

          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">{t('title')}</h1>
            <p className="mt-2 text-sm text-gray-600">{t('subtitle')}</p>
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
                  <h2 className="text-xl font-bold text-white">{t('smartUpload.title')}</h2>
                  <p className="text-sm text-indigo-100">{t('smartUpload.subtitle')}</p>
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
                    {t('smartUpload.dropzone')}
                  </h3>
                  <p className="text-sm text-gray-600 mb-4">{t('smartUpload.browse')}</p>
                  <div className="flex items-center justify-center gap-2 text-xs text-gray-500">
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span>{t('smartUpload.autoClassification')}</span>
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span>{t('smartUpload.parallelProcessing')}</span>
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span>{t('smartUpload.smartSynthesis')}</span>
                  </div>
                </div>
              )}

              {bulkUploading && (
                <div className="bg-white rounded-lg p-6 border border-purple-200">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center">
                      <Loader2 className="h-6 w-6 text-purple-600 animate-spin mr-3" />
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">{t('smartUpload.processing')}</h3>
                        <p className="text-sm text-gray-600">{t('smartUpload.processingSubtitle')}</p>
                      </div>
                    </div>
                    {bulkStatus && (
                      <div className="text-right">
                        <div className="text-3xl font-bold text-purple-600">
                          {bulkStatus.progress.percentage}%
                        </div>
                        <div className="text-xs text-gray-500">
                          {t('smartUpload.complete', { completed: bulkStatus.progress.completed, total: bulkStatus.progress.total })}
                        </div>
                      </div>
                    )}
                  </div>

                  {bulkStatus && (
                    <div className="mb-6">
                      <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-purple-500 to-pink-500 h-3 rounded-full transition-all duration-500"
                          style={{ width: `${bulkStatus.progress.percentage}%` }}
                        />
                      </div>
                    </div>
                  )}

                  <div className="space-y-2">
                    {(bulkStatus?.documents ?? []).map((doc) => (
                      <div key={doc.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-center flex-1">
                          <FileText className="h-4 w-4 text-gray-400 mr-3" />
                          <div className="flex-1">
                            <p className="text-sm font-medium text-gray-900">{doc.filename}</p>
                            <div className="flex items-center gap-2 mt-1">
                              {doc.document_category && doc.document_category !== 'pending_classification' && (
                                <span className={`text-xs px-2 py-0.5 rounded ${getCategoryColor(doc.document_category)}`}>
                                  {getCategoryLabel(doc.document_category, t)}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center">
                          {doc.processing_status === 'completed' && <CheckCircle className="h-5 w-5 text-green-500" />}
                          {doc.processing_status === 'processing' && <Loader2 className="h-5 w-5 text-purple-500 animate-spin" />}
                          {doc.processing_status === 'failed' && <AlertCircle className="h-5 w-5 text-red-500" />}
                          {doc.processing_status === 'pending' && <Clock className="h-5 w-5 text-gray-400" />}
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
                      <h3 className="text-lg font-semibold text-gray-900">{t('smartUpload.processingComplete')}</h3>
                      <p className="text-sm text-gray-600">
                        {t('smartUpload.documentsAnalyzed', { count: bulkStatus.progress.completed })}
                      </p>
                    </div>
                  </div>

                  {bulkStatus.synthesis && (
                    <div className="mt-4 p-4 bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg border border-purple-200">
                      <h4 className="text-md font-semibold text-gray-900 mb-3 flex items-center">
                        <Sparkles className="h-5 w-5 text-purple-500 mr-2" />
                        {t('synthesis.title')}
                      </h4>

                      {bulkStatus.synthesis.summary && (
                        <p className="text-sm text-gray-700 mb-4">{bulkStatus.synthesis.summary}</p>
                      )}

                      {bulkStatus.synthesis.risk_level && (
                        <div className="mb-3">
                          <span className="text-xs font-medium text-gray-700">{t('synthesis.riskLevel')} </span>
                          <span className={`text-xs px-2 py-1 rounded ${
                            bulkStatus.synthesis.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                            bulkStatus.synthesis.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                            'bg-green-100 text-green-700'
                          }`}>
                            {bulkStatus.synthesis.risk_level === 'high' ? t('synthesis.high') :
                             bulkStatus.synthesis.risk_level === 'medium' ? t('synthesis.medium') :
                             t('synthesis.low')}
                          </span>
                        </div>
                      )}

                      {bulkStatus.synthesis.key_findings && bulkStatus.synthesis.key_findings.length > 0 && (
                        <div className="mb-3">
                          <p className="text-xs font-medium text-gray-700 mb-2">{t('synthesis.keyFindings')}</p>
                          <ul className="space-y-1">
                            {bulkStatus.synthesis.key_findings.map((finding, idx) => (
                              <li key={idx} className="text-sm text-gray-700 flex items-start">
                                <span className="text-purple-500 mr-2">&bull;</span>
                                {finding}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {(bulkStatus.synthesis.total_annual_cost || bulkStatus.synthesis.total_one_time_cost) && (
                        <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-purple-200">
                          {bulkStatus.synthesis.total_annual_cost !== undefined && bulkStatus.synthesis.total_annual_cost > 0 && (
                            <div>
                              <dt className="text-xs font-medium text-gray-500">{t('synthesis.totalAnnualCosts')}</dt>
                              <dd className="mt-1 text-lg font-semibold text-gray-900">
                                {new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(bulkStatus.synthesis.total_annual_cost)}
                              </dd>
                            </div>
                          )}
                          {bulkStatus.synthesis.total_one_time_cost !== undefined && bulkStatus.synthesis.total_one_time_cost > 0 && (
                            <div>
                              <dt className="text-xs font-medium text-gray-500">{t('synthesis.totalOneTimeCosts')}</dt>
                              <dd className="mt-1 text-lg font-semibold text-gray-900">
                                {new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(bulkStatus.synthesis.total_one_time_cost)}
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
                    {t('smartUpload.uploadMore')}
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
                  {t('propertySynthesis.title')}
                </h2>
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleRegenerateSynthesis}
                    disabled={regenerating}
                    className="inline-flex items-center px-3 py-1.5 border border-purple-300 text-xs font-medium rounded-lg text-purple-700 bg-white hover:bg-purple-50 disabled:opacity-50"
                  >
                    {regenerating ? (
                      <><Loader2 className="h-3 w-3 mr-1 animate-spin" />{t('documentList.resynthesizing')}</>
                    ) : (
                      <><RefreshCw className="h-3 w-3 mr-1" />{t('documentList.resynthesize')}</>
                    )}
                  </button>
                  <span className={`px-4 py-2 rounded-full text-sm font-semibold ${
                    synthesis.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                    synthesis.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-green-100 text-green-700'
                  }`}>
                    {t('propertySynthesis.risk', { level: synthesis.risk_level?.toUpperCase() || '' })}
                  </span>
                </div>
              </div>

              <p className="text-gray-700 mb-6 leading-relaxed">{synthesis.overall_summary}</p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div className="bg-white rounded-lg p-4 shadow">
                  <dt className="text-sm font-medium text-gray-500">{t('synthesis.totalAnnualCosts')}</dt>
                  <dd className="mt-2 text-3xl font-bold text-gray-900">
                    {new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(synthesis.total_annual_cost || 0)}
                  </dd>
                </div>
                <div className="bg-white rounded-lg p-4 shadow">
                  <dt className="text-sm font-medium text-gray-500">{t('synthesis.totalOneTimeCosts')}</dt>
                  <dd className="mt-2 text-3xl font-bold text-gray-900">
                    {new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(synthesis.total_one_time_cost || 0)}
                  </dd>
                </div>
              </div>

              {synthesis.key_findings && synthesis.key_findings.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">{t('propertySynthesis.keyFindings')}</h3>
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
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">{t('propertySynthesis.recommendations')}</h3>
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

          {/* Document List */}
          <div className="bg-white shadow rounded-lg overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">{t('documentList.title')}</h2>
              {documents.length > 0 && (
                <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedDocs.size === documents.length && documents.length > 0}
                    onChange={toggleSelectAll}
                    className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                  />
                  {selectedDocs.size === documents.length ? t('deselectAll') : t('selectAll')}
                </label>
              )}
            </div>

            {documents.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <FileText className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                <p className="text-sm">{t('documentList.emptyState')}</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-200">
                {sortedCategories.map((category) => {
                  const docs = groupedDocs[category];
                  const isCollapsed = collapsedCategories.has(category);

                  return (
                    <div key={category}>
                      {/* Category header */}
                      <button
                        onClick={() => toggleCategory(category)}
                        className="w-full flex items-center justify-between px-6 py-3 bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          {isCollapsed ? (
                            <ChevronRight className="h-4 w-4 text-gray-500" />
                          ) : (
                            <ChevronDown className="h-4 w-4 text-gray-500" />
                          )}
                          <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${getCategoryColor(category)}`}>
                            {getCategoryLabel(category, t)}
                          </span>
                          <span className="text-sm text-gray-500">
                            {t('documentCount', { count: docs.length })}
                          </span>
                        </div>
                      </button>

                      {/* Documents in category */}
                      {!isCollapsed && (
                        <div className="divide-y divide-gray-100">
                          {docs.map((doc) => {
                            const isExpanded = expandedDoc === doc.id;
                            return (
                              <div key={doc.id} className="px-6 py-3 hover:bg-gray-50 transition-colors">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center flex-1 min-w-0">
                                    <input
                                      type="checkbox"
                                      checked={selectedDocs.has(doc.id)}
                                      onChange={() => toggleDocSelection(doc.id)}
                                      className="h-4 w-4 text-blue-600 border-gray-300 rounded mr-3 flex-shrink-0"
                                    />
                                    <FileText className="h-4 w-4 text-gray-400 mr-3 flex-shrink-0" />
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2">
                                        {renamingDocId === doc.id ? (
                                          <div className="flex items-center gap-1">
                                            <input
                                              type="text"
                                              value={renameValue}
                                              onChange={(e) => setRenameValue(e.target.value)}
                                              onKeyDown={(e) => {
                                                if (e.key === 'Enter') handleSaveRename(doc);
                                                if (e.key === 'Escape') handleCancelRename();
                                              }}
                                              className="text-sm font-medium text-gray-900 border border-gray-300 rounded px-2 py-0.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
                                              autoFocus
                                            />
                                            <span className="text-xs text-gray-400">{doc.filename.substring(doc.filename.lastIndexOf('.'))}</span>
                                            <button onClick={() => handleSaveRename(doc)} className="text-green-600 hover:text-green-800 p-0.5">
                                              <Check className="h-4 w-4" />
                                            </button>
                                            <button onClick={handleCancelRename} className="text-gray-400 hover:text-gray-600 p-0.5">
                                              <X className="h-4 w-4" />
                                            </button>
                                          </div>
                                        ) : (
                                          <>
                                            <h4 className="text-sm font-medium text-gray-900 truncate">{doc.filename}</h4>
                                            <button
                                              onClick={() => handleStartRename(doc)}
                                              className="text-gray-400 hover:text-gray-600 p-0.5 flex-shrink-0"
                                              title={t('renameDocument')}
                                            >
                                              <Pencil className="h-3.5 w-3.5" />
                                            </button>
                                          </>
                                        )}
                                        {doc.is_analyzed ? (
                                          <CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0" />
                                        ) : (
                                          <Loader2 className="h-4 w-4 text-blue-500 animate-spin flex-shrink-0" />
                                        )}
                                      </div>
                                      <div className="flex items-center text-xs text-gray-500 gap-3 mt-0.5">
                                        {doc.document_subcategory && (
                                          <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                                            {doc.document_subcategory.toUpperCase()}
                                          </span>
                                        )}
                                        <span>{t('uploaded', { date: new Date(doc.upload_date).toLocaleDateString('fr-FR') })}</span>
                                      </div>
                                    </div>
                                  </div>

                                  <div className="flex items-center gap-2 ml-4">
                                    {doc.is_analyzed && doc.analysis_summary && (
                                      <button
                                        onClick={() => setExpandedDoc(isExpanded ? null : doc.id)}
                                        className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100"
                                      >
                                        {isExpanded ? t('documentList.collapseDetails') : t('documentList.expandDetails')}
                                      </button>
                                    )}
                                    <button
                                      onClick={() => handleDeleteDocument(doc.id)}
                                      className="text-red-400 hover:text-red-600 p-1"
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </button>
                                  </div>
                                </div>

                                {/* Expanded analysis details */}
                                {isExpanded && doc.is_analyzed && doc.analysis_summary && (
                                  <div className="mt-3 ml-7 bg-gray-50 rounded-lg p-3">
                                    <p className="text-sm text-gray-700">{doc.analysis_summary}</p>

                                    {doc.key_insights && doc.key_insights.length > 0 && (
                                      <div className="mt-2">
                                        <p className="text-xs font-medium text-gray-700 mb-1">{t('keyInsights')}</p>
                                        <ul className="space-y-1">
                                          {doc.key_insights.map((insight, idx) => (
                                            <li key={idx} className="text-xs text-gray-600 flex items-start">
                                              <span className="text-gray-400 mr-1">&bull;</span>
                                              {insight}
                                            </li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}

                                    {doc.one_time_costs && doc.one_time_costs.length > 0 && (
                                      <div className="mt-2">
                                        <p className="text-xs font-medium text-gray-700 mb-1">{t('costs')}</p>
                                        <ul className="space-y-1">
                                          {doc.one_time_costs.map((cost, idx) => (
                                            <li key={idx} className="text-xs text-gray-600">
                                              {cost.item}: {new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(cost.amount)}
                                              {cost.timeline && ` (${cost.timeline})`}
                                            </li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          {/* Floating action bar for multi-select */}
          {selectedDocs.size > 0 && (
            <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-20 bg-white shadow-lg rounded-full px-6 py-3 border border-gray-200 flex items-center gap-4">
              <span className="text-sm font-medium text-gray-700">
                {t('selectedCount', { count: selectedDocs.size })}
              </span>
              <button
                onClick={() => setShowBulkDeleteConfirm(true)}
                className="inline-flex items-center px-4 py-1.5 bg-red-600 text-white text-sm font-medium rounded-full hover:bg-red-700 transition-colors"
              >
                <Trash2 className="h-4 w-4 mr-1.5" />
                {t('deleteSelected')}
              </button>
              <button
                onClick={() => setSelectedDocs(new Set())}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                {t('deselectAll')}
              </button>
            </div>
          )}

          {/* Bulk delete confirmation modal */}
          {showBulkDeleteConfirm && (
            <div className="fixed z-30 inset-0 overflow-y-auto" aria-labelledby="bulk-delete-title" role="dialog" aria-modal="true">
              <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
                <div
                  className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
                  aria-hidden="true"
                  onClick={() => !bulkDeleting && setShowBulkDeleteConfirm(false)}
                ></div>
                <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
                <div className="relative inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
                  <div className="sm:flex sm:items-start">
                    <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                      <Trash2 className="h-6 w-6 text-red-600" aria-hidden="true" />
                    </div>
                    <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                      <h3 className="text-lg leading-6 font-medium text-gray-900" id="bulk-delete-title">
                        {t('bulkDeleteTitle')}
                      </h3>
                      <div className="mt-2">
                        <p className="text-sm text-gray-500">
                          {t('bulkDeleteMessage', { count: selectedDocs.size })}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                    <button
                      type="button"
                      disabled={bulkDeleting}
                      onClick={handleBulkDelete}
                      className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {bulkDeleting ? (
                        <><Loader2 className="h-4 w-4 mr-2 animate-spin" />{tc('deleting')}</>
                      ) : (
                        tc('delete')
                      )}
                    </button>
                    <button
                      type="button"
                      disabled={bulkDeleting}
                      onClick={() => setShowBulkDeleteConfirm(false)}
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

export default function DocumentsPage() {
  return (
    <ProtectedRoute>
      <DocumentsPageContent />
    </ProtectedRoute>
  );
}
