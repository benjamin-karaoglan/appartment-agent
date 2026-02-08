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
  Undo2,
  Save,
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

interface FullSynthesisData {
  summary: string;
  total_annual_costs: number;
  annual_cost_breakdown: {
    [key: string]: number | { amount: number; source?: string | null; note?: string | null };
  };
  total_one_time_costs: number;
  one_time_cost_breakdown: Array<{
    description: string;
    amount: number;
    year?: number;
    cost_type?: string;
    payment_status?: string;
    source: string;
    status: string;
  }>;
  risk_level: string;
  risk_factors: string[];
  cross_document_themes: Array<{
    theme: string;
    documents_involved: string[];
    evolution: string;
    current_status: string;
  }>;
  key_findings: string[];
  buyer_action_items: Array<{
    priority: number;
    action: string;
    urgency: string;
    estimated_cost: number;
  }>;
  recommendations: string[];
  confidence_score: number;
  confidence_reasoning: string;
  tantiemes_info?: {
    lot_tantiemes: number | null;
    total_tantiemes: number | null;
    share_percentage: number | null;
    cost_share_note: string | null;
  };
  user_overrides?: {
    lot_tantiemes?: number | null;
    total_tantiemes?: number | null;
  };
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
  synthesis_data?: FullSynthesisData;
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
    synthesis_data?: FullSynthesisData;
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

const DIRECT_COST_KEYS = ['taxe_fonciere', 'estimated_energy'];

function normalizeStatus(raw: string): 'voted' | 'estimated' | 'upcoming' {
  const lower = raw.toLowerCase();
  if (/vot|paid|approved|confirmed|adopté|approuvé/.test(lower)) return 'voted';
  if (/upcom|planned|future|à venir|prévu/.test(lower)) return 'upcoming';
  return 'estimated';
}

function getAnnualCostEntry(value: number | { amount: number; source?: string | null; note?: string | null }): { amount: number; source?: string | null; note?: string | null } {
  if (typeof value === 'number') return { amount: value };
  return value;
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
  const [uploadPhase, setUploadPhase] = useState<'idle' | 'uploading' | 'processing' | 'synthesizing'>('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadFileCount, setUploadFileCount] = useState(0);

  // Document list states
  const [expandedDoc, setExpandedDoc] = useState<number | null>(null);
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());
  const [regenerating, setRegenerating] = useState(false);

  // Drill-down toggles for synthesis display
  const [showAnnualBreakdown, setShowAnnualBreakdown] = useState(false);
  const [showOneTimeBreakdown, setShowOneTimeBreakdown] = useState(false);
  const [showThemes, setShowThemes] = useState(false);
  const [showActionItems, setShowActionItems] = useState(false);

  // Editable amounts state
  const [annualOverrides, setAnnualOverrides] = useState<Record<string, number>>({});
  const [oneTimeOverrides, setOneTimeOverrides] = useState<Record<number, number>>({});
  const [editingAnnualKey, setEditingAnnualKey] = useState<string | null>(null);
  const [editingOneTimeIdx, setEditingOneTimeIdx] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');

  // Tantièmes state
  const [userLotTantiemes, setUserLotTantiemes] = useState<number | null>(null);
  const [userTotalTantiemes, setUserTotalTantiemes] = useState<number | null>(null);
  const [editingTantiemes, setEditingTantiemes] = useState(false);
  const [savingTantiemes, setSavingTantiemes] = useState(false);

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

  const loadSynthesis = async (retries = 0) => {
    try {
      const response = await api.get(`/api/documents/synthesis/${propertyId}`);
      if (response.data) {
        setSynthesis(response.data);
        // Restore user tantièmes overrides from saved synthesis_data
        const overrides = response.data.synthesis_data?.user_overrides;
        if (overrides) {
          if (overrides.lot_tantiemes != null) setUserLotTantiemes(overrides.lot_tantiemes);
          if (overrides.total_tantiemes != null) setUserTotalTantiemes(overrides.total_tantiemes);
        }
        return;
      }
    } catch (error) {
      console.error('Failed to load synthesis:', error);
    }
    if (retries > 0) {
      await new Promise(r => setTimeout(r, 2000));
      return loadSynthesis(retries - 1);
    }
    // Only clear synthesis on initial load — never overwrite existing data with null
    // (preserves synthesis set from bulk status fallback)
    setSynthesis(prev => prev ? prev : null);
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

  const handleSaveTantiemes = async () => {
    setSavingTantiemes(true);
    try {
      await api.patch(`/api/documents/synthesis/${propertyId}/overrides`, {
        lot_tantiemes: userLotTantiemes,
        total_tantiemes: userTotalTantiemes,
      });
      setEditingTantiemes(false);
    } catch (err: any) {
      console.error('Save tantièmes error:', err);
      setError(err.response?.data?.detail || 'Failed to save tantièmes');
    } finally {
      setSavingTantiemes(false);
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
    setUploadPhase('uploading');
    setUploadProgress(0);
    setUploadFileCount(files.length);

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
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const pct = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setUploadProgress(pct);
          }
        },
      });

      setUploadPhase('processing');
      const { workflow_id } = response.data;
      pollBulkStatus(workflow_id);
    } catch (err: any) {
      console.error('Bulk upload error:', err);
      setError(err.response?.data?.detail || 'Failed to upload documents');
      setBulkUploading(false);
      setUploadPhase('idle');
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
          setUploadPhase('synthesizing');
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

          // Load fresh data BEFORE transitioning out of the active UI,
          // so synthesis and documents are ready when the completion card renders.
          await loadDocuments();

          // Set synthesis immediately from bulk status data so it shows
          // without waiting for a separate API call.
          if (currentStatus.synthesis) {
            const bs = currentStatus.synthesis;
            setSynthesis({
              id: 0,
              property_id: Number(propertyId),
              overall_summary: bs.summary || '',
              risk_level: bs.risk_level || 'unknown',
              total_annual_cost: bs.total_annual_cost || 0,
              total_one_time_cost: bs.total_one_time_cost || 0,
              key_findings: bs.key_findings || [],
              recommendations: bs.recommendations || [],
              last_updated: new Date().toISOString(),
              synthesis_data: bs.synthesis_data,
            });
          }

          // Also load from the main endpoint in background (has user_overrides)
          loadSynthesis(2);

          setBulkUploading(false);
          setUploadPhase('idle');
          return;
        }

        if (status.status === 'failed') {
          setBulkUploading(false);
          setUploadPhase('idle');
          setError(t('bulkFailed'));
          return;
        }

        pollCount++;
        if (pollCount < maxPolls && (status.status === 'running' || status.status === 'processing')) {
          setTimeout(poll, 2000);
        } else if (pollCount >= maxPolls) {
          setBulkUploading(false);
          setUploadPhase('idle');
          setError(t('processingTimeout'));
        }
      } catch (err: any) {
        console.error('Status poll error:', err);
        pollCount++;
        if (pollCount < maxPolls) {
          setTimeout(poll, 2000);
        } else {
          setBulkUploading(false);
          setUploadPhase('idle');
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
                  {/* Step indicators */}
                  <div className="flex items-center gap-3 mb-6">
                    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
                      uploadPhase === 'uploading' ? 'bg-purple-100 text-purple-700' : 'bg-green-100 text-green-700'
                    }`}>
                      {uploadPhase === 'uploading' ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <CheckCircle className="h-3 w-3" />
                      )}
                      {t('smartUpload.stepUpload')}
                    </div>
                    <div className="h-px flex-1 bg-gray-200" />
                    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
                      uploadPhase === 'processing' ? 'bg-purple-100 text-purple-700' :
                      (uploadPhase === 'synthesizing') ? 'bg-green-100 text-green-700' :
                      'bg-gray-100 text-gray-400'
                    }`}>
                      {uploadPhase === 'processing' ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (uploadPhase === 'synthesizing') ? (
                        <CheckCircle className="h-3 w-3" />
                      ) : (
                        <Clock className="h-3 w-3" />
                      )}
                      {t('smartUpload.stepAnalysis')}
                    </div>
                    <div className="h-px flex-1 bg-gray-200" />
                    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
                      uploadPhase === 'synthesizing' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-400'
                    }`}>
                      {uploadPhase === 'synthesizing' ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Sparkles className="h-3 w-3" />
                      )}
                      {t('smartUpload.stepSynthesis')}
                    </div>
                  </div>

                  {/* Phase 1: Uploading files */}
                  {uploadPhase === 'uploading' && (
                    <>
                      <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center">
                          <Loader2 className="h-6 w-6 text-purple-600 animate-spin mr-3" />
                          <div>
                            <h3 className="text-lg font-semibold text-gray-900">{t('smartUpload.uploading')}</h3>
                            <p className="text-sm text-gray-600">
                              {t('smartUpload.uploadingSubtitle', { count: uploadFileCount })}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-3xl font-bold text-purple-600">
                            {uploadProgress}%
                          </div>
                        </div>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                        <div
                          className="bg-gradient-to-r from-indigo-500 to-purple-500 h-3 rounded-full transition-all duration-300"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                    </>
                  )}

                  {/* Phase 3: Synthesizing — show synthesis message + keep document list visible */}
                  {uploadPhase === 'synthesizing' && (
                    <>
                      <div className="flex items-center justify-center py-6 mb-4 bg-purple-50 rounded-lg">
                        <div className="text-center">
                          <Sparkles className="h-10 w-10 text-purple-500 mx-auto mb-3 animate-pulse" />
                          <h3 className="text-lg font-semibold text-gray-900">{t('smartUpload.synthesizing')}</h3>
                          <p className="text-sm text-gray-600 mt-1">{t('smartUpload.synthesizingSubtitle')}</p>
                        </div>
                      </div>

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
                    </>
                  )}

                  {/* Phase 2: AI Processing */}
                  {uploadPhase === 'processing' && (
                    <>
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
                    </>
                  )}
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
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-md font-semibold text-gray-900 flex items-center">
                          <Sparkles className="h-5 w-5 text-purple-500 mr-2" />
                          {t('synthesis.title')}
                        </h4>
                        <div className="flex items-center gap-2">
                          {bulkStatus.synthesis.risk_level && bulkStatus.synthesis.risk_level !== 'unknown' && (
                            <span className={`text-xs px-2 py-1 rounded font-medium ${
                              bulkStatus.synthesis.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                              bulkStatus.synthesis.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                              'bg-green-100 text-green-700'
                            }`}>
                              {bulkStatus.synthesis.risk_level === 'high' ? t('synthesis.high') :
                               bulkStatus.synthesis.risk_level === 'medium' ? t('synthesis.medium') :
                               t('synthesis.low')}
                            </span>
                          )}
                          {bulkStatus.synthesis.synthesis_data?.confidence_score != null && (
                            <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700 font-medium">
                              {t('propertySynthesis.confidence', { score: Math.round(bulkStatus.synthesis.synthesis_data.confidence_score * 100) })}
                            </span>
                          )}
                        </div>
                      </div>

                      {bulkStatus.synthesis.summary && (
                        <p className="text-sm text-gray-700 mb-4">{bulkStatus.synthesis.summary}</p>
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
          {synthesis && (() => {
            const sd = synthesis.synthesis_data;
            const fmt = (n: number) => new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(n);

            // Tantièmes computation
            const lotTantiemes = userLotTantiemes ?? sd?.tantiemes_info?.lot_tantiemes ?? null;
            const totalTantiemes = userTotalTantiemes ?? sd?.tantiemes_info?.total_tantiemes ?? null;
            const shareRatio = (lotTantiemes != null && totalTantiemes != null && totalTantiemes > 0)
              ? lotTantiemes / totalTantiemes
              : null;

            // Computed annual total (deterministic)
            const computedAnnualTotal = sd?.annual_cost_breakdown
              ? Object.entries(sd.annual_cost_breakdown).reduce((sum, [key, value]) => {
                  const entry = getAnnualCostEntry(value);
                  const effectiveAmount = annualOverrides[key] ?? entry.amount;
                  const isDirect = DIRECT_COST_KEYS.includes(key);
                  const buyerAmount = (!isDirect && shareRatio != null) ? effectiveAmount * shareRatio : effectiveAmount;
                  return sum + buyerAmount;
                }, 0)
              : null;

            // Computed one-time total (deterministic)
            const computedOneTimeTotal = sd?.one_time_cost_breakdown?.length
              ? sd.one_time_cost_breakdown.reduce((sum, item, idx) => {
                  const effectiveAmount = oneTimeOverrides[idx] ?? item.amount;
                  const isDirectItem = item.cost_type === 'direct';
                  const buyerAmount = (!isDirectItem && shareRatio != null) ? effectiveAmount * shareRatio : effectiveAmount;
                  return sum + buyerAmount;
                }, 0)
              : null;

            const displayAnnualTotal = computedAnnualTotal ?? synthesis.total_annual_cost ?? 0;
            const displayOneTimeTotal = computedOneTimeTotal ?? synthesis.total_one_time_cost ?? 0;

            // Copro totals (before tantièmes) for display
            const coproAnnualTotal = sd?.annual_cost_breakdown
              ? Object.entries(sd.annual_cost_breakdown).reduce((sum, [key, value]) => {
                  const entry = getAnnualCostEntry(value);
                  return sum + (annualOverrides[key] ?? entry.amount);
                }, 0)
              : null;
            const coproOneTimeTotal = sd?.one_time_cost_breakdown?.length
              ? sd.one_time_cost_breakdown.reduce((sum, item, idx) => sum + (oneTimeOverrides[idx] ?? item.amount), 0)
              : null;

            return (
            <div className="mb-8 bg-gradient-to-br from-purple-50 via-pink-50 to-indigo-50 rounded-xl p-6 border-2 border-purple-200 shadow-lg">
              {/* Header: Title + regenerate + risk badge + confidence badge */}
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
                  {synthesis.risk_level && synthesis.risk_level !== 'unknown' && (
                    <span className={`px-4 py-2 rounded-full text-sm font-semibold ${
                      synthesis.risk_level === 'high' ? 'bg-red-100 text-red-700' :
                      synthesis.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {t('propertySynthesis.risk', { level: synthesis.risk_level?.toUpperCase() || '' })}
                    </span>
                  )}
                  {sd?.confidence_score != null && (
                    <span className="px-3 py-2 rounded-full text-sm font-semibold bg-blue-100 text-blue-700">
                      {t('propertySynthesis.confidence', { score: Math.round(sd.confidence_score * 100) })}
                    </span>
                  )}
                </div>
              </div>

              {/* Summary */}
              <p className="text-gray-700 mb-6 leading-relaxed">{synthesis.overall_summary}</p>

              {/* Tantièmes card */}
              <div className="mb-6 bg-white rounded-lg p-4 shadow">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-gray-900">{t('propertySynthesis.tantiemes')}</h3>
                  {!editingTantiemes && (
                    <button
                      onClick={() => setEditingTantiemes(true)}
                      className="inline-flex items-center text-xs text-purple-600 hover:text-purple-800"
                    >
                      <Pencil className="h-3 w-3 mr-1" />
                      {t('propertySynthesis.editTantiemes')}
                    </button>
                  )}
                </div>
                {editingTantiemes ? (
                  <div className="flex items-center gap-4 text-sm">
                    <div>
                      <label className="text-xs text-gray-500 block mb-1">{t('propertySynthesis.lotTantiemes')}</label>
                      <input
                        type="number"
                        value={userLotTantiemes ?? sd?.tantiemes_info?.lot_tantiemes ?? ''}
                        onChange={(e) => setUserLotTantiemes(e.target.value ? Number(e.target.value) : null)}
                        className="w-28 border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-purple-500"
                        placeholder="150"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 block mb-1">{t('propertySynthesis.totalTantiemes')}</label>
                      <input
                        type="number"
                        value={userTotalTantiemes ?? sd?.tantiemes_info?.total_tantiemes ?? ''}
                        onChange={(e) => setUserTotalTantiemes(e.target.value ? Number(e.target.value) : null)}
                        className="w-28 border border-gray-300 rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-purple-500"
                        placeholder="10000"
                      />
                    </div>
                    {shareRatio != null && (
                      <div className="ml-2">
                        <label className="text-xs text-gray-500 block mb-1">{t('propertySynthesis.sharePercentage')}</label>
                        <span className="font-medium text-gray-900">{(shareRatio * 100).toFixed(2)}%</span>
                      </div>
                    )}
                    <button
                      onClick={handleSaveTantiemes}
                      disabled={savingTantiemes}
                      className="ml-auto inline-flex items-center gap-1 px-3 py-1.5 bg-purple-600 text-white text-xs font-medium rounded-lg hover:bg-purple-700 disabled:opacity-50"
                    >
                      {savingTantiemes ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                      {tc('save')}
                    </button>
                    <button
                      onClick={() => setEditingTantiemes(false)}
                      className="text-gray-400 hover:text-gray-600 p-1"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : lotTantiemes != null && totalTantiemes != null ? (
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <dt className="text-xs text-gray-500">{t('propertySynthesis.lotTantiemes')}</dt>
                      <dd className="font-medium text-gray-900">{lotTantiemes}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-gray-500">{t('propertySynthesis.totalTantiemes')}</dt>
                      <dd className="font-medium text-gray-900">{totalTantiemes}</dd>
                    </div>
                    {shareRatio != null && (
                      <div>
                        <dt className="text-xs text-gray-500">{t('propertySynthesis.sharePercentage')}</dt>
                        <dd className="font-medium text-gray-900">{(shareRatio * 100).toFixed(2)}%</dd>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">
                    <span className="font-medium">{t('propertySynthesis.notDetected')}</span>
                    <p className="text-xs mt-1 text-gray-400">{t('propertySynthesis.tantiemesHint')}</p>
                  </div>
                )}
                {!editingTantiemes && sd?.tantiemes_info?.cost_share_note && (
                  <p className="mt-2 text-xs text-gray-500">{sd.tantiemes_info.cost_share_note}</p>
                )}
              </div>

              {/* Cost cards: Annual + One-time */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div
                  className={`bg-white rounded-lg p-4 shadow ${sd?.annual_cost_breakdown ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
                  onClick={() => sd?.annual_cost_breakdown && setShowAnnualBreakdown(!showAnnualBreakdown)}
                >
                  <div className="flex items-center justify-between">
                    <dt className="text-sm font-medium text-gray-500">{t('propertySynthesis.annualTotal')}</dt>
                    {sd?.annual_cost_breakdown && (
                      showAnnualBreakdown ? <ChevronDown className="h-4 w-4 text-gray-400" /> : <ChevronRight className="h-4 w-4 text-gray-400" />
                    )}
                  </div>
                  <dd className="mt-2 text-3xl font-bold text-gray-900">
                    {fmt(displayAnnualTotal)}
                  </dd>
                  {shareRatio != null && coproAnnualTotal != null && Math.abs(coproAnnualTotal - displayAnnualTotal) > 1 && (
                    <p className="text-xs text-gray-400 mt-1">{t('propertySynthesis.coproTotalLabel')}: {fmt(coproAnnualTotal)}</p>
                  )}
                </div>
                <div
                  className={`bg-white rounded-lg p-4 shadow ${sd?.one_time_cost_breakdown?.length ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}
                  onClick={() => sd?.one_time_cost_breakdown?.length && setShowOneTimeBreakdown(!showOneTimeBreakdown)}
                >
                  <div className="flex items-center justify-between">
                    <dt className="text-sm font-medium text-gray-500">{t('propertySynthesis.oneTimeTotal')}</dt>
                    {sd?.one_time_cost_breakdown && sd.one_time_cost_breakdown.length > 0 && (
                      showOneTimeBreakdown ? <ChevronDown className="h-4 w-4 text-gray-400" /> : <ChevronRight className="h-4 w-4 text-gray-400" />
                    )}
                  </div>
                  <dd className="mt-2 text-3xl font-bold text-gray-900">
                    {fmt(displayOneTimeTotal)}
                  </dd>
                  {shareRatio != null && coproOneTimeTotal != null && Math.abs(coproOneTimeTotal - displayOneTimeTotal) > 1 && (
                    <p className="text-xs text-gray-400 mt-1">{t('propertySynthesis.coproTotalLabel')}: {fmt(coproOneTimeTotal)}</p>
                  )}
                </div>
              </div>

              {/* Annual cost breakdown table (expandable) */}
              {showAnnualBreakdown && sd?.annual_cost_breakdown && (
                <div className="mb-6 bg-white rounded-lg p-4 shadow">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">{t('propertySynthesis.annualBreakdown')}</h3>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="py-2 text-left text-xs font-medium text-gray-500">{t('propertySynthesis.category')}</th>
                        {shareRatio != null && (
                          <th className="py-2 text-right text-xs font-medium text-gray-500" style={{ minWidth: '130px' }}>{t('propertySynthesis.coproTotal')}</th>
                        )}
                        <th className="py-2 text-right text-xs font-medium text-gray-500" style={{ minWidth: '130px' }}>
                          {shareRatio != null ? t('propertySynthesis.yourShare') : t('propertySynthesis.amount')}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {Object.entries(sd.annual_cost_breakdown).map(([key, value]) => {
                        const entry = getAnnualCostEntry(value);
                        const effectiveAmount = annualOverrides[key] ?? entry.amount;
                        if (effectiveAmount <= 0 && !(key in annualOverrides)) return null;
                        const isDirect = DIRECT_COST_KEYS.includes(key);
                        const buyerAmount = (!isDirect && shareRatio != null) ? effectiveAmount * shareRatio : effectiveAmount;
                        const isOverridden = key in annualOverrides;
                        // Copro items: edit on copro total column; Direct items: edit on amount/your-share column
                        const editOnCoproCol = !isDirect && shareRatio != null;

                        const editInlineUI = (
                          <div className="inline-flex items-center gap-1">
                            <input
                              type="number"
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  const v = parseFloat(editValue);
                                  if (!isNaN(v)) setAnnualOverrides(prev => ({ ...prev, [key]: v }));
                                  setEditingAnnualKey(null);
                                }
                                if (e.key === 'Escape') setEditingAnnualKey(null);
                              }}
                              className="w-24 border border-gray-300 rounded px-2 py-0.5 text-sm text-right focus:outline-none focus:ring-1 focus:ring-blue-500"
                              autoFocus
                            />
                            <button
                              onClick={() => {
                                const v = parseFloat(editValue);
                                if (!isNaN(v)) setAnnualOverrides(prev => ({ ...prev, [key]: v }));
                                setEditingAnnualKey(null);
                              }}
                              className="text-green-600 hover:text-green-800 p-0.5"
                            >
                              <Check className="h-3.5 w-3.5" />
                            </button>
                            <button onClick={() => setEditingAnnualKey(null)} className="text-gray-400 hover:text-gray-600 p-0.5">
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        );

                        return (
                          <tr key={key}>
                            <td className="py-2">
                              <div className="flex items-center gap-2">
                                <span className="text-gray-600">{t(`propertySynthesis.costCategories.${key}`)}</span>
                                {!isDirect && (
                                  <span className="text-xs px-1.5 py-0.5 rounded bg-purple-100 text-purple-600">{t('propertySynthesis.coproCost')}</span>
                                )}
                                {isDirect && (
                                  <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{t('propertySynthesis.directCost')}</span>
                                )}
                                {isOverridden && (
                                  <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-600">{t('propertySynthesis.userAdjusted')}</span>
                                )}
                              </div>
                              {entry.source && (
                                <p className="text-xs text-gray-400 mt-0.5">{entry.source}</p>
                              )}
                              {entry.note && (
                                <p className="text-xs text-gray-400">{entry.note}</p>
                              )}
                            </td>
                            {shareRatio != null && (
                              <td className="py-2 text-right pr-6 whitespace-nowrap group/copro">
                                {isDirect ? (
                                  <span className="text-gray-300">—</span>
                                ) : editingAnnualKey === key && editOnCoproCol ? (
                                  editInlineUI
                                ) : (
                                  <span className="relative whitespace-nowrap">
                                    {isOverridden && editOnCoproCol && (
                                      <span className="text-xs text-gray-400 line-through mr-1">{fmt(entry.amount)}</span>
                                    )}
                                    <span className={`font-medium ${isOverridden ? 'text-blue-600' : 'text-gray-500'}`}>
                                      {fmt(effectiveAmount)}
                                    </span>
                                    {isOverridden && editOnCoproCol && (
                                      <button
                                        onClick={() => setAnnualOverrides(prev => { const next = { ...prev }; delete next[key]; return next; })}
                                        className="ml-1 inline-flex items-center text-gray-400 hover:text-gray-600 p-0.5 align-middle"
                                        title="Revert"
                                      >
                                        <Undo2 className="h-3 w-3" />
                                      </button>
                                    )}
                                    {editOnCoproCol && (
                                      <button
                                        onClick={(e) => { e.stopPropagation(); setEditingAnnualKey(key); setEditValue(String(effectiveAmount)); }}
                                        className="absolute left-full top-1/2 -translate-y-1/2 ml-1 opacity-0 group-hover/copro:opacity-100 text-gray-400 hover:text-gray-600 p-0.5 transition-opacity"
                                        title={t('propertySynthesis.editAmount')}
                                      >
                                        <Pencil className="h-3 w-3" />
                                      </button>
                                    )}
                                  </span>
                                )}
                              </td>
                            )}
                            <td className="py-2 text-right pr-6 whitespace-nowrap group/share">
                              {editingAnnualKey === key && !editOnCoproCol ? (
                                editInlineUI
                              ) : (
                                <span className="relative whitespace-nowrap">
                                  {isOverridden && !editOnCoproCol && (
                                    <span className="text-xs text-gray-400 line-through mr-1">{fmt(entry.amount)}</span>
                                  )}
                                  <span className={`font-medium ${isOverridden && !editOnCoproCol ? 'text-blue-600' : 'text-gray-900'}`}>
                                    {fmt(shareRatio != null ? buyerAmount : effectiveAmount)}
                                  </span>
                                  {isOverridden && !editOnCoproCol && (
                                    <button
                                      onClick={() => setAnnualOverrides(prev => { const next = { ...prev }; delete next[key]; return next; })}
                                      className="ml-1 inline-flex items-center text-gray-400 hover:text-gray-600 p-0.5 align-middle"
                                      title="Revert"
                                    >
                                      <Undo2 className="h-3 w-3" />
                                    </button>
                                  )}
                                  {!editOnCoproCol && (
                                    <button
                                      onClick={(e) => { e.stopPropagation(); setEditingAnnualKey(key); setEditValue(String(effectiveAmount)); }}
                                      className="absolute left-full top-1/2 -translate-y-1/2 ml-1 opacity-0 group-hover/share:opacity-100 text-gray-400 hover:text-gray-600 p-0.5 transition-opacity"
                                      title={t('propertySynthesis.editAmount')}
                                    >
                                      <Pencil className="h-3 w-3" />
                                    </button>
                                  )}
                                </span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* One-time cost breakdown table (expandable) */}
              {showOneTimeBreakdown && sd?.one_time_cost_breakdown && sd.one_time_cost_breakdown.length > 0 && (
                <div className="mb-6 bg-white rounded-lg p-4 shadow">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">{t('propertySynthesis.oneTimeBreakdown')}</h3>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="py-2 text-left text-xs font-medium text-gray-500">{t('propertySynthesis.description')}</th>
                        {shareRatio != null && (
                          <th className="py-2 text-right text-xs font-medium text-gray-500" style={{ minWidth: '120px' }}>{t('propertySynthesis.coproTotal')}</th>
                        )}
                        <th className="py-2 text-right text-xs font-medium text-gray-500" style={{ minWidth: '120px' }}>
                          {shareRatio != null ? t('propertySynthesis.yourShare') : t('propertySynthesis.amount')}
                        </th>
                        <th className="py-2 text-left text-xs font-medium text-gray-500 pl-6" style={{ minWidth: '160px' }}>{t('propertySynthesis.source')}</th>
                        <th className="py-2 text-right text-xs font-medium text-gray-500 pl-4" style={{ minWidth: '80px' }}>{t('propertySynthesis.status')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {sd.one_time_cost_breakdown.map((item, idx) => {
                        const effectiveAmount = oneTimeOverrides[idx] ?? item.amount;
                        const isDirectItem = item.cost_type === 'direct';
                        const buyerAmount = (!isDirectItem && shareRatio != null) ? effectiveAmount * shareRatio : effectiveAmount;
                        const isOverridden = idx in oneTimeOverrides;
                        const status = normalizeStatus(item.status);
                        // Copro items: edit on copro column; Direct items: edit on amount/your-share column
                        const editOnCoproCol = !isDirectItem && shareRatio != null;

                        const editInlineUI = (
                          <div className="inline-flex items-center gap-1">
                            <input
                              type="number"
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  const v = parseFloat(editValue);
                                  if (!isNaN(v)) setOneTimeOverrides(prev => ({ ...prev, [idx]: v }));
                                  setEditingOneTimeIdx(null);
                                }
                                if (e.key === 'Escape') setEditingOneTimeIdx(null);
                              }}
                              className="w-24 border border-gray-300 rounded px-2 py-0.5 text-sm text-right focus:outline-none focus:ring-1 focus:ring-blue-500"
                              autoFocus
                            />
                            <button
                              onClick={() => {
                                const v = parseFloat(editValue);
                                if (!isNaN(v)) setOneTimeOverrides(prev => ({ ...prev, [idx]: v }));
                                setEditingOneTimeIdx(null);
                              }}
                              className="text-green-600 hover:text-green-800 p-0.5"
                            >
                              <Check className="h-3.5 w-3.5" />
                            </button>
                            <button onClick={() => setEditingOneTimeIdx(null)} className="text-gray-400 hover:text-gray-600 p-0.5">
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        );

                        // Direct/DDT items should never show "voted" — force to "estimated"
                        const effectiveStatus = isDirectItem && status === 'voted' ? 'estimated' : status;

                        return (
                          <tr key={idx}>
                            <td className="py-2 text-gray-700">
                              <span>{item.description}</span>
                              {isDirectItem && (
                                <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{t('propertySynthesis.directCost')}</span>
                              )}
                            </td>
                            {shareRatio != null && (
                              <td className="py-2 text-right pr-6 whitespace-nowrap group/copro">
                                {isDirectItem ? (
                                  <span className="text-gray-300">—</span>
                                ) : editingOneTimeIdx === idx && editOnCoproCol ? (
                                  editInlineUI
                                ) : (
                                  <span className="relative whitespace-nowrap">
                                    {isOverridden && (
                                      <span className="text-xs text-gray-400 line-through mr-1">{fmt(item.amount)}</span>
                                    )}
                                    <span className={`font-medium ${isOverridden ? 'text-blue-600' : 'text-gray-500'}`}>
                                      {fmt(effectiveAmount)}
                                    </span>
                                    {isOverridden && (
                                      <button
                                        onClick={() => setOneTimeOverrides(prev => { const next = { ...prev }; delete next[idx]; return next; })}
                                        className="ml-1 inline-flex items-center text-gray-400 hover:text-gray-600 p-0.5 align-middle"
                                        title="Revert"
                                      >
                                        <Undo2 className="h-3 w-3" />
                                      </button>
                                    )}
                                    {editOnCoproCol && (
                                      <button
                                        onClick={(e) => { e.stopPropagation(); setEditingOneTimeIdx(idx); setEditValue(String(effectiveAmount)); }}
                                        className="absolute left-full top-1/2 -translate-y-1/2 ml-1 opacity-0 group-hover/copro:opacity-100 text-gray-400 hover:text-gray-600 p-0.5 transition-opacity"
                                        title={t('propertySynthesis.editAmount')}
                                      >
                                        <Pencil className="h-3 w-3" />
                                      </button>
                                    )}
                                  </span>
                                )}
                              </td>
                            )}
                            <td className="py-2 text-right pr-6 whitespace-nowrap group/share">
                              {editingOneTimeIdx === idx && !editOnCoproCol ? (
                                editInlineUI
                              ) : (
                                <span className="relative whitespace-nowrap">
                                  {isOverridden && !editOnCoproCol && (
                                    <span className="text-xs text-gray-400 line-through mr-1">{fmt(item.amount)}</span>
                                  )}
                                  <span className={`font-medium ${isOverridden && !editOnCoproCol ? 'text-blue-600' : 'text-gray-900'}`}>
                                    {fmt(shareRatio != null ? buyerAmount : effectiveAmount)}
                                  </span>
                                  {isOverridden && !editOnCoproCol && (
                                    <button
                                      onClick={() => setOneTimeOverrides(prev => { const next = { ...prev }; delete next[idx]; return next; })}
                                      className="ml-1 inline-flex items-center text-gray-400 hover:text-gray-600 p-0.5 align-middle"
                                      title="Revert"
                                    >
                                      <Undo2 className="h-3 w-3" />
                                    </button>
                                  )}
                                  {!editOnCoproCol && (
                                    <button
                                      onClick={(e) => { e.stopPropagation(); setEditingOneTimeIdx(idx); setEditValue(String(effectiveAmount)); }}
                                      className="absolute left-full top-1/2 -translate-y-1/2 ml-1 opacity-0 group-hover/share:opacity-100 text-gray-400 hover:text-gray-600 p-0.5 transition-opacity"
                                      title={t('propertySynthesis.editAmount')}
                                    >
                                      <Pencil className="h-3 w-3" />
                                    </button>
                                  )}
                                </span>
                              )}
                            </td>
                            <td className="py-2 text-gray-500 pl-6 text-xs">{item.source}</td>
                            <td className="py-2 pl-4 text-right">
                              <div className="inline-flex items-center gap-1.5">
                                <span className={`text-xs px-2 py-0.5 rounded ${
                                  effectiveStatus === 'voted' ? 'bg-green-100 text-green-700' :
                                  effectiveStatus === 'estimated' ? 'bg-yellow-100 text-yellow-700' :
                                  'bg-blue-100 text-blue-700'
                                }`}>
                                  {t(`propertySynthesis.costStatus.${effectiveStatus}`)}
                                </span>
                                {isOverridden && (
                                  <span className="text-xs px-1.5 py-0.5 rounded bg-blue-100 text-blue-600">{t('propertySynthesis.userAdjusted')}</span>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Key findings */}
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

              {/* Risk factors */}
              {sd?.risk_factors && sd.risk_factors.length > 0 && (
                <div className="mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">{t('propertySynthesis.riskFactors')}</h3>
                  <ul className="space-y-2">
                    {sd.risk_factors.map((factor, idx) => (
                      <li key={idx} className="flex items-start text-gray-700">
                        <AlertCircle className="w-5 h-5 text-red-400 mr-2 flex-shrink-0 mt-0.5" />
                        {factor}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Cross-document themes (expandable) */}
              {sd?.cross_document_themes && sd.cross_document_themes.length > 0 && (
                <div className="mb-4">
                  <button
                    onClick={() => setShowThemes(!showThemes)}
                    className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-3 hover:text-purple-700"
                  >
                    {showThemes ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
                    {t('propertySynthesis.crossDocThemes')} ({sd.cross_document_themes.length})
                  </button>
                  {showThemes && (
                    <div className="space-y-3">
                      {sd.cross_document_themes.map((theme, idx) => (
                        <div key={idx} className="bg-white rounded-lg p-4 shadow-sm border border-gray-100">
                          <h4 className="font-medium text-gray-900 mb-2">{theme.theme}</h4>
                          <div className="text-xs text-gray-500 mb-1">
                            <span className="font-medium">{t('propertySynthesis.documentsInvolved')}:</span> {theme.documents_involved.join(', ')}
                          </div>
                          <p className="text-sm text-gray-600 mb-1"><span className="font-medium text-xs text-gray-500">{t('propertySynthesis.evolution')}:</span> {theme.evolution}</p>
                          <p className="text-sm text-gray-600"><span className="font-medium text-xs text-gray-500">{t('propertySynthesis.currentStatus')}:</span> {theme.current_status}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Buyer action items (expandable) */}
              {sd?.buyer_action_items && sd.buyer_action_items.length > 0 && (
                <div className="mb-4">
                  <button
                    onClick={() => setShowActionItems(!showActionItems)}
                    className="flex items-center gap-2 text-lg font-semibold text-gray-900 mb-3 hover:text-purple-700"
                  >
                    {showActionItems ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
                    {t('propertySynthesis.actionItems')} ({sd.buyer_action_items.length})
                  </button>
                  {showActionItems && (
                    <div className="space-y-2">
                      {sd.buyer_action_items
                        .sort((a, b) => a.priority - b.priority)
                        .map((item, idx) => (
                        <div key={idx} className="flex items-start gap-3 bg-white rounded-lg p-3 shadow-sm border border-gray-100">
                          <span className="flex-shrink-0 w-7 h-7 rounded-full bg-purple-100 text-purple-700 flex items-center justify-center text-sm font-bold">
                            {item.priority}
                          </span>
                          <div className="flex-1">
                            <p className="text-sm text-gray-700">{item.action}</p>
                            <div className="flex items-center gap-3 mt-1">
                              <span className={`text-xs px-2 py-0.5 rounded ${
                                item.urgency === 'immediate' ? 'bg-red-100 text-red-700' :
                                item.urgency === 'short_term' ? 'bg-yellow-100 text-yellow-700' :
                                'bg-blue-100 text-blue-700'
                              }`}>
                                {t(`propertySynthesis.urgency.${item.urgency}`) || item.urgency}
                              </span>
                              {item.estimated_cost > 0 && (
                                <span className="text-xs text-gray-500">{t('propertySynthesis.estimatedCost')}: {fmt(item.estimated_cost)}</span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Recommendations */}
              {synthesis.recommendations && synthesis.recommendations.length > 0 && (
                <div className="mb-4">
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

              {/* Confidence footer */}
              {sd?.confidence_reasoning && (
                <div className="mt-4 pt-4 border-t border-purple-200">
                  <p className="text-xs text-gray-500">
                    <span className="font-medium">{t('propertySynthesis.confidenceNote')}:</span> {sd.confidence_reasoning}
                  </p>
                </div>
              )}
            </div>
            );
          })()}

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
