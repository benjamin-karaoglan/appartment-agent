"use client";

import { useState, useEffect, useRef } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import Header from '@/components/Header';
import { ArrowLeft, Upload, Sparkles, Image as ImageIcon, Download, Trash2, X, Columns, Maximize2, Send, Plus, MessageSquare, Clock, Pencil, Check, LayoutGrid, Star } from 'lucide-react';
import { Link } from '@/i18n/navigation';
import { useParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import api from '@/lib/api';

interface PromotedRedesign {
  id: number;
  redesign_uuid: string;
  style_preset?: string;
  presigned_url?: string;
  created_at: string;
}

interface Photo {
  id: number;
  filename: string;
  room_type?: string;
  description?: string;
  uploaded_at: string;
  presigned_url: string;
  redesign_count: number;
  promoted_redesign?: PromotedRedesign | null;
}

interface Redesign {
  id: number;
  redesign_uuid: string;
  photo_id: number;
  style_preset?: string;
  prompt: string;
  aspect_ratio: string;
  created_at: string;
  generation_time_ms?: number;
  presigned_url: string;
  is_favorite: boolean;
  parent_redesign_id?: number | null;
  is_multi_turn: boolean;
}

interface Thread {
  id: number;
  messages: Redesign[];
  latestTimestamp: string;
}

interface StylePreset {
  id: string;
  name: string;
  description: string;
  prompt_template?: string;
}

function PhotosContent() {
  const t = useTranslations('photos');
  const tc = useTranslations('common');

  const params = useParams();
  const propertyId = params.id as string;

  const [photos, setPhotos] = useState<Photo[]>([]);
  const [selectedPhoto, setSelectedPhoto] = useState<Photo | null>(null);
  const [redesigns, setRedesigns] = useState<Redesign[]>([]);
  const [stylePresets, setStylePresets] = useState<StylePreset[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [deletingPhotoId, setDeletingPhotoId] = useState<number | null>(null);
  const [photoToDelete, setPhotoToDelete] = useState<Photo | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<string>('');
  const [customPrompt, setCustomPrompt] = useState('');
  const [roomType, setRoomType] = useState('living room');
  const [savingRoomType, setSavingRoomType] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [selectedRedesign, setSelectedRedesign] = useState<Redesign | null>(null);
  const [showOriginalFullscreen, setShowOriginalFullscreen] = useState(false);
  const [showComparison, setShowComparison] = useState(false);
  const [activeThreadId, setActiveThreadId] = useState<number | null>(null);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [optimisticPrompt, setOptimisticPrompt] = useState<string | null>(null);
  const [threadNames, setThreadNames] = useState<Record<number, string>>({});
  const [editingThreadId, setEditingThreadId] = useState<number | null>(null);
  const [editingThreadName, setEditingThreadName] = useState('');
  const [editingPhotoName, setEditingPhotoName] = useState(false);
  const [photoNameDraft, setPhotoNameDraft] = useState('');
  const [showGallery, setShowGallery] = useState(false);
  const [expandedBubbles, setExpandedBubbles] = useState<Set<number>>(new Set());
  const chatEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Load thread names from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem('threadNames');
      if (stored) setThreadNames(JSON.parse(stored));
    } catch { /* ignore */ }
  }, []);

  const saveThreadName = (threadId: number, name: string) => {
    const updated = { ...threadNames, [threadId]: name };
    setThreadNames(updated);
    try { localStorage.setItem('threadNames', JSON.stringify(updated)); } catch { /* ignore */ }
  };

  // Load style presets
  useEffect(() => {
    loadStylePresets();
  }, []);

  // Load photos
  useEffect(() => {
    loadPhotos();
  }, [propertyId]);

  // Load redesigns when photo is selected + reset thread state
  useEffect(() => {
    if (selectedPhoto) {
      loadRedesigns(selectedPhoto.id);
      setActiveThreadId(null);
      setShowGallery(false);
      setOptimisticPrompt(null);
      setSelectedPreset('');
      setCustomPrompt('');
    }
  }, [selectedPhoto]);

  useEffect(() => {
    if (!selectedPreset) return;
    const preset = stylePresets.find((item) => item.id === selectedPreset);
    if (!preset?.prompt_template) return;
    const translatedRoomType = t(`roomTypes.${roomType}`);
    setCustomPrompt(preset.prompt_template.replace(/\{room_type\}/g, translatedRoomType));
  }, [selectedPreset, roomType, stylePresets, t]);

  // Build threads from redesigns
  const buildThreads = (redesignsList: Redesign[]): Thread[] => {
    const byId = new Map<number, Redesign>();
    for (const r of redesignsList) byId.set(r.id, r);

    // Map parent_id → children
    const childrenOf = new Map<number, Redesign[]>();
    const roots: Redesign[] = [];
    for (const r of redesignsList) {
      if (!r.parent_redesign_id) {
        roots.push(r);
      } else {
        const siblings = childrenOf.get(r.parent_redesign_id) || [];
        siblings.push(r);
        childrenOf.set(r.parent_redesign_id, siblings);
      }
    }

    // Walk chain from a starting node to build one thread's messages
    const walkChain = (start: Redesign, childIdx: number): Redesign[] => {
      const chain: Redesign[] = [start];
      let current = start;
      while (true) {
        const kids = childrenOf.get(current.id);
        if (!kids || kids.length === 0) break;
        // If branching, each child after the first becomes a separate thread (handled by caller)
        const next = kids[childIdx !== undefined && current.id === start.id ? childIdx : 0];
        if (!next) break;
        chain.push(next);
        current = next;
        childIdx = 0; // after first step, always take first child
      }
      return chain;
    };

    const result: Thread[] = [];

    for (const root of roots) {
      const kids = childrenOf.get(root.id);
      if (!kids || kids.length <= 1) {
        // No branching: single thread from this root
        const msgs = walkChain(root, 0);
        result.push({
          id: root.id,
          messages: msgs,
          latestTimestamp: msgs[msgs.length - 1].created_at,
        });
      } else {
        // Branching: fork into separate threads
        // First thread includes root + first child's chain
        for (let i = 0; i < kids.length; i++) {
          const msgs = [root, ...walkChain(kids[i], 0)];
          result.push({
            id: i === 0 ? root.id : kids[i].id,
            messages: msgs,
            latestTimestamp: msgs[msgs.length - 1].created_at,
          });
        }
      }
    }

    // Sort by most recent activity (newest first)
    result.sort((a, b) => new Date(b.latestTimestamp).getTime() - new Date(a.latestTimestamp).getTime());
    return result;
  };

  useEffect(() => {
    setThreads(buildThreads(redesigns));
  }, [redesigns]);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [threads, optimisticPrompt, activeThreadId]);

  // Auto-resize textarea based on content
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
  }, [customPrompt]);

  const handlePhotoRename = async (newName: string) => {
    if (!selectedPhoto || !newName.trim()) return;
    try {
      const response = await api.patch(`/api/photos/${selectedPhoto.id}`, {
        filename: newName.trim(),
      });
      const updatedPhoto = response.data as Photo;
      setSelectedPhoto(updatedPhoto);
      setPhotos((prev) =>
        prev.map((p) => (p.id === updatedPhoto.id ? updatedPhoto : p))
      );
    } catch (error: any) {
      console.error('Error renaming photo:', error);
      alert(error.response?.data?.detail || t('renameFailed'));
    } finally {
      setEditingPhotoName(false);
    }
  };

  const loadStylePresets = async () => {
    try {
      const response = await api.get('/api/photos/presets');
      setStylePresets(response.data.presets);
    } catch (error) {
      console.error('Error loading presets:', error);
    }
  };

  const loadPhotos = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/api/photos/?property_id=${propertyId}`);
      setPhotos(response.data.photos);

      // Auto-select first photo if available
      if (response.data.photos.length > 0 && !selectedPhoto) {
        const initialPhoto = response.data.photos[0];
        setSelectedPhoto(initialPhoto);
        if (initialPhoto.room_type) {
          setRoomType(initialPhoto.room_type);
        }
      }
    } catch (error) {
      console.error('Error loading photos:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadRedesigns = async (photoId: number) => {
    try {
      const response = await api.get(`/api/photos/${photoId}/redesigns`);
      setRedesigns(response.data.redesigns);
    } catch (error) {
      console.error('Error loading redesigns:', error);
    }
  };

  const handleRoomTypeChange = async (value: string) => {
    setRoomType(value);
    if (!selectedPhoto) return;
    try {
      setSavingRoomType(true);
      const response = await api.patch(`/api/photos/${selectedPhoto.id}`, {
        room_type: value,
      });
      const updatedPhoto = response.data as Photo;
      setSelectedPhoto(updatedPhoto);
      setPhotos((prev) =>
        prev.map((photo) => (photo.id === updatedPhoto.id ? updatedPhoto : photo))
      );
    } catch (error: any) {
      console.error('Error updating room type:', error);
      alert(error.response?.data?.detail || t('roomTypeFailed'));
    } finally {
      setSavingRoomType(false);
    }
  };

  const handlePhotoUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('property_id', propertyId);
    formData.append('room_type', roomType);

    try {
      setUploading(true);
      const response = await api.post('/api/photos/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const newPhoto = response.data;
      setPhotos([newPhoto, ...photos]);
      setSelectedPhoto(newPhoto);

      // Clear file input
      event.target.value = '';
    } catch (error: any) {
      console.error('Error uploading photo:', error);
      alert(error.response?.data?.detail || t('uploadFailed'));
    } finally {
      setUploading(false);
    }
  };

  const handleGenerateRedesign = async () => {
    if (!selectedPhoto) {
      alert(t('selectPhotoFirst'));
      return;
    }

    if (!selectedPreset && !customPrompt) {
      alert(t('selectPresetOrPrompt'));
      return;
    }

    const activeThread = threads.find((th) => th.id === activeThreadId);
    const isFollowUp = activeThread && activeThread.messages.length > 0;
    const parentId = isFollowUp ? activeThread.messages[activeThread.messages.length - 1].id : undefined;

    // Set optimistic prompt for immediate visual feedback
    setOptimisticPrompt(customPrompt || selectedPreset);

    try {
      setGenerating(true);

      const body: Record<string, unknown> = {
        custom_prompt: customPrompt || undefined,
        room_type: selectedPhoto.room_type || roomType,
        aspect_ratio: '16:9',
      };

      if (isFollowUp) {
        body.parent_redesign_id = parentId;
      } else {
        body.style_preset = selectedPreset || undefined;
      }

      const response = await api.post(`/api/photos/${selectedPhoto.id}/redesign`, body);

      const newRedesign = response.data;
      setRedesigns([newRedesign, ...redesigns]);

      // For new threads, set active thread to the new redesign's id
      if (!isFollowUp) {
        setActiveThreadId(newRedesign.id);
      }

      // Clear inputs
      setSelectedPreset('');
      setCustomPrompt('');
      setOptimisticPrompt(null);
      setToastMessage(t('redesignGenerated'));
      setTimeout(() => setToastMessage(null), 3000);
    } catch (error: any) {
      console.error('Error generating redesign:', error);
      setOptimisticPrompt(null);
      alert(error.response?.data?.detail || t('generateFailed'));
    } finally {
      setGenerating(false);
    }
  };

  const handleDeletePhoto = async () => {
    if (!photoToDelete) return;
    try {
      setDeletingPhotoId(photoToDelete.id);
      await api.delete(`/api/photos/${photoToDelete.id}`);

      const remainingPhotos = photos.filter((item) => item.id !== photoToDelete.id);
      setPhotos(remainingPhotos);

      if (selectedPhoto?.id === photoToDelete.id) {
        setSelectedPhoto(remainingPhotos[0] || null);
        setRedesigns([]);
      }
    } catch (error: any) {
      console.error('Error deleting photo:', error);
      alert(error.response?.data?.detail || t('deleteFailed'));
    } finally {
      setDeletingPhotoId(null);
      setPhotoToDelete(null);
    }
  };

  const handlePromoteRedesign = async (photoId: number, redesignId: number) => {
    try {
      await api.patch(`/api/photos/${photoId}/promote/${redesignId}`);
      // Update local state
      setPhotos((prev) =>
        prev.map((p) => {
          if (p.id !== photoId) return p;
          const rd = redesigns.find((r) => r.id === redesignId);
          return {
            ...p,
            promoted_redesign: rd ? {
              id: rd.id,
              redesign_uuid: rd.redesign_uuid,
              style_preset: rd.style_preset,
              presigned_url: rd.presigned_url,
              created_at: rd.created_at,
            } : p.promoted_redesign,
          };
        })
      );
      if (selectedPhoto?.id === photoId) {
        const rd = redesigns.find((r) => r.id === redesignId);
        if (rd) {
          setSelectedPhoto((prev) => prev ? {
            ...prev,
            promoted_redesign: {
              id: rd.id,
              redesign_uuid: rd.redesign_uuid,
              style_preset: rd.style_preset,
              presigned_url: rd.presigned_url,
              created_at: rd.created_at,
            },
          } : prev);
        }
      }
      setToastMessage(t('redesignPromoted'));
      setTimeout(() => setToastMessage(null), 3000);
    } catch (error: any) {
      console.error('Error promoting redesign:', error);
      alert(error.response?.data?.detail || t('promoteFailed'));
    }
  };

  const handleDemoteRedesign = async (photoId: number) => {
    try {
      await api.delete(`/api/photos/${photoId}/promote`);
      // Update local state
      setPhotos((prev) =>
        prev.map((p) =>
          p.id === photoId ? { ...p, promoted_redesign: null } : p
        )
      );
      if (selectedPhoto?.id === photoId) {
        setSelectedPhoto((prev) => prev ? { ...prev, promoted_redesign: null } : prev);
      }
      setToastMessage(t('redesignDemoted'));
      setTimeout(() => setToastMessage(null), 3000);
    } catch (error: any) {
      console.error('Error demoting redesign:', error);
      alert(error.response?.data?.detail || t('promoteFailed'));
    }
  };

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

          <h1 className="text-3xl font-bold text-gray-900 mb-8">
            {t('title')}
          </h1>

          {/* Upload Section */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
              <Upload className="h-5 w-5 mr-2 text-indigo-600" />
              {t('uploadPhoto')}
            </h2>

            <div className="flex gap-4 items-end">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t('roomType')}
                </label>
                <select
                  value={roomType}
                  onChange={(e) => setRoomType(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="living room">{t('roomTypes.living room')}</option>
                  <option value="bedroom">{t('roomTypes.bedroom')}</option>
                  <option value="kitchen">{t('roomTypes.kitchen')}</option>
                  <option value="bathroom">{t('roomTypes.bathroom')}</option>
                  <option value="dining room">{t('roomTypes.dining room')}</option>
                  <option value="home office">{t('roomTypes.home office')}</option>
                </select>
              </div>

              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {t('choosePhoto')}
                </label>
                <label className="flex items-center justify-center px-6 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 cursor-pointer">
                  <Upload className="h-4 w-4 mr-2" />
                  {uploading ? t('uploading') : t('selectImage')}
                  <input
                    type="file"
                    accept="image/jpeg,image/jpg,image/png,image/webp"
                    onChange={handlePhotoUpload}
                    disabled={uploading}
                    className="hidden"
                  />
                </label>
              </div>
            </div>
          </div>

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Photo Gallery */}
            <div className="lg:col-span-1">
              <div className="bg-white shadow rounded-lg p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
                  <ImageIcon className="h-5 w-5 mr-2 text-indigo-600" />
                  {t('yourPhotos', { count: photos.length })}
                </h2>

                {loading ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
                  </div>
                ) : photos.length === 0 ? (
                  <p className="text-gray-500 text-center py-8">
                    {t('noPhotos')}
                  </p>
                ) : (
                  <div className="space-y-3">
                    {photos.map((photo) => (
                      <div
                        key={photo.id}
                        onClick={() => {
                          setSelectedPhoto(photo);
                          if (photo.room_type) {
                            setRoomType(photo.room_type);
                          }
                        }}
                        className={`cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
                          selectedPhoto?.id === photo.id
                            ? 'border-indigo-600 shadow-md'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}
                      >
                        <div className="relative">
                          <img
                            src={photo.presigned_url}
                            alt={photo.filename}
                            className="w-full h-32 object-cover"
                            onError={(e) => {
                              console.error('Failed to load image:', photo.presigned_url);
                              e.currentTarget.src = `data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect fill="%23ddd" width="200" height="200"/><text x="50%" y="50%" text-anchor="middle" fill="%23999">${encodeURIComponent(t('imageError'))}</text></svg>`;
                            }}
                          />
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              setPhotoToDelete(photo);
                            }}
                            disabled={deletingPhotoId === photo.id}
                            className="absolute right-2 top-2 rounded-full bg-white/90 p-1 text-gray-600 shadow hover:text-red-600 disabled:opacity-60"
                            aria-label={`${t('deletePhoto')} ${photo.filename}`}
                            title={t('deletePhoto')}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                        <div className="p-2 bg-gray-50">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {photo.filename}
                          </p>
                          <p className="text-xs text-gray-500">
                            {photo.room_type ? t(`roomTypes.${photo.room_type}`) : t('noRoomType')} • {t('redesignCount', { count: photo.redesign_count })}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Right Column: Conversation Studio */}
            <div className="lg:col-span-2">
              {!selectedPhoto ? (
                <div className="bg-white shadow rounded-lg p-12 text-center">
                  <ImageIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-500">{t('selectPhotoPrompt')}</p>
                </div>
              ) : (
                <div className="bg-white shadow rounded-lg flex flex-col" style={{ height: 'calc(100vh - 280px)', minHeight: '600px' }}>
                  {/* 7a: Original Photo Header */}
                  <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200">
                    <img
                      src={selectedPhoto.presigned_url}
                      alt={selectedPhoto.filename}
                      className="h-10 w-14 rounded object-cover cursor-pointer flex-shrink-0"
                      onClick={() => setShowOriginalFullscreen(true)}
                    />
                    <div className="min-w-0 flex-1">
                      {editingPhotoName ? (
                        <form
                          className="flex items-center gap-1"
                          onSubmit={(e) => { e.preventDefault(); handlePhotoRename(photoNameDraft); }}
                        >
                          <input
                            autoFocus
                            value={photoNameDraft}
                            onChange={(e) => setPhotoNameDraft(e.target.value)}
                            onBlur={() => handlePhotoRename(photoNameDraft)}
                            onKeyDown={(e) => { if (e.key === 'Escape') setEditingPhotoName(false); }}
                            className="text-sm font-medium text-gray-900 border border-gray-300 rounded px-1.5 py-0.5 w-full focus:outline-none focus:ring-1 focus:ring-indigo-500"
                          />
                          <button type="submit" className="text-green-600 hover:text-green-700 flex-shrink-0">
                            <Check className="h-3.5 w-3.5" />
                          </button>
                        </form>
                      ) : (
                        <button
                          onClick={() => { setEditingPhotoName(true); setPhotoNameDraft(selectedPhoto.filename); }}
                          className="flex items-center gap-1.5 group text-left w-full"
                          title={t('clickToRename')}
                        >
                          <p className="text-sm font-medium text-gray-900 truncate">{selectedPhoto.filename}</p>
                          <Pencil className="h-3 w-3 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                        </button>
                      )}
                    </div>
                    <select
                      value={roomType}
                      onChange={(e) => handleRoomTypeChange(e.target.value)}
                      disabled={savingRoomType}
                      className="w-36 px-2 py-1.5 text-sm border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100"
                    >
                      <option value="living room">{t('roomTypes.living room')}</option>
                      <option value="bedroom">{t('roomTypes.bedroom')}</option>
                      <option value="kitchen">{t('roomTypes.kitchen')}</option>
                      <option value="bathroom">{t('roomTypes.bathroom')}</option>
                      <option value="dining room">{t('roomTypes.dining room')}</option>
                      <option value="home office">{t('roomTypes.home office')}</option>
                    </select>
                  </div>

                  {/* 7b: Thread Tabs */}
                  <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100 overflow-x-auto">
                    <button
                      onClick={() => {
                        setActiveThreadId(null);
                        setShowGallery(false);
                        setSelectedPreset('');
                        setCustomPrompt('');
                      }}
                      className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-colors ${
                        activeThreadId === null && !showGallery
                          ? 'bg-purple-600 text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      <Plus className="h-3 w-3" />
                      {t('newThread')}
                    </button>
                    {threads.map((thread, idx) => {
                      const defaultLabel = thread.messages[0]?.style_preset?.replace(/_/g, ' ') || `${t('thread')} ${threads.length - idx}`;
                      const displayName = threadNames[thread.id] || defaultLabel;

                      if (editingThreadId === thread.id) {
                        return (
                          <form
                            key={thread.id}
                            className="flex items-center gap-1"
                            onSubmit={(e) => {
                              e.preventDefault();
                              saveThreadName(thread.id, editingThreadName || defaultLabel);
                              setEditingThreadId(null);
                            }}
                          >
                            <input
                              autoFocus
                              value={editingThreadName}
                              onChange={(e) => setEditingThreadName(e.target.value)}
                              onBlur={() => {
                                saveThreadName(thread.id, editingThreadName || defaultLabel);
                                setEditingThreadId(null);
                              }}
                              onKeyDown={(e) => { if (e.key === 'Escape') setEditingThreadId(null); }}
                              className="text-xs font-medium border border-purple-300 rounded-full px-2.5 py-1 w-32 focus:outline-none focus:ring-1 focus:ring-purple-500 text-gray-900"
                            />
                            <button type="submit" className="text-green-600 hover:text-green-700 flex-shrink-0">
                              <Check className="h-3 w-3" />
                            </button>
                          </form>
                        );
                      }

                      return (
                        <button
                          key={thread.id}
                          onClick={() => {
                            setActiveThreadId(thread.id);
                            setShowGallery(false);
                            setSelectedPreset('');
                            setCustomPrompt('');
                          }}
                          onDoubleClick={(e) => {
                            e.preventDefault();
                            setEditingThreadId(thread.id);
                            setEditingThreadName(displayName);
                          }}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                            activeThreadId === thread.id && !showGallery
                              ? 'bg-purple-100 text-purple-700 ring-1 ring-purple-300'
                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                          }`}
                          title={t('doubleClickToRename')}
                        >
                          <MessageSquare className="h-3 w-3" />
                          {displayName}
                          <span className="text-[10px] opacity-70">({thread.messages.length})</span>
                        </button>
                      );
                    })}

                    {/* Divider + All Redesigns gallery tab */}
                    {redesigns.length > 0 && (
                      <>
                        <div className="h-5 w-px bg-gray-300 flex-shrink-0" />
                        <button
                          onClick={() => setShowGallery(true)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                            showGallery
                              ? 'bg-indigo-100 text-indigo-700 ring-1 ring-indigo-300'
                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                          }`}
                        >
                          <LayoutGrid className="h-3 w-3" />
                          {t('allGallery')}
                          <span className="text-[10px] opacity-70">({redesigns.length})</span>
                        </button>
                      </>
                    )}
                  </div>

                  {showGallery ? (
                    /* Gallery Grid — browse-only view, no input area */
                    <div className="flex-1 overflow-y-auto p-4">
                      {redesigns.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full text-center py-12">
                          <ImageIcon className="h-12 w-12 text-gray-300 mb-4" />
                          <h3 className="text-lg font-semibold text-gray-700 mb-1">{t('noRedesigns')}</h3>
                          <p className="text-sm text-gray-500 max-w-sm">
                            {t('noRedesignsDesc')}
                          </p>
                        </div>
                      ) : (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                          {redesigns.map((redesign) => {
                            const parentThread = threads.find((th) =>
                              th.messages.some((m) => m.id === redesign.id)
                            );
                            const threadLabel = parentThread
                              ? threadNames[parentThread.id] || parentThread.messages[0]?.style_preset?.replace(/_/g, ' ') || t('thread')
                              : t('thread');

                            const timeAgo = (() => {
                              const diff = Date.now() - new Date(redesign.created_at).getTime();
                              const mins = Math.floor(diff / 60000);
                              if (mins < 1) return t('timeAgo.justNow');
                              if (mins < 60) return t('timeAgo.minutesAgo', { n: mins });
                              const hrs = Math.floor(mins / 60);
                              if (hrs < 24) return t('timeAgo.hoursAgo', { n: hrs });
                              const days = Math.floor(hrs / 24);
                              return t('timeAgo.daysAgo', { n: days });
                            })();

                            const isPromoted = selectedPhoto?.promoted_redesign?.id === redesign.id;

                            return (
                              <div key={redesign.id} className="group">
                                {/* Image with hover overlay */}
                                <div
                                  className="relative aspect-video rounded-lg overflow-hidden cursor-pointer"
                                  onClick={() => setSelectedRedesign(redesign)}
                                >
                                  <img
                                    src={redesign.presigned_url}
                                    alt={`Redesign ${redesign.id}`}
                                    className="w-full h-full object-cover"
                                  />
                                  {/* Promoted badge */}
                                  {isPromoted && (
                                    <div className="absolute top-2 left-2 z-10">
                                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-yellow-400 text-[10px] font-bold text-yellow-900 rounded">
                                        <Star className="h-2.5 w-2.5 fill-current" />
                                        {t('promoted')}
                                      </span>
                                    </div>
                                  )}
                                  {/* Hover overlay */}
                                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-start justify-between p-2 opacity-0 group-hover:opacity-100">
                                    <span className="px-1.5 py-0.5 bg-black/60 text-[10px] font-semibold text-white rounded uppercase">
                                      {redesign.style_preset?.replace(/_/g, ' ') || t('custom')}
                                    </span>
                                    <div className="flex items-center gap-1">
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          if (selectedPhoto) {
                                            if (isPromoted) {
                                              handleDemoteRedesign(selectedPhoto.id);
                                            } else {
                                              handlePromoteRedesign(selectedPhoto.id, redesign.id);
                                            }
                                          }
                                        }}
                                        className={`p-1 rounded transition-colors ${
                                          isPromoted
                                            ? 'bg-yellow-400 text-yellow-900 hover:bg-yellow-500'
                                            : 'bg-black/60 text-white hover:bg-black/80'
                                        }`}
                                        title={isPromoted ? t('demoteRedesign') : t('promoteRedesign')}
                                      >
                                        <Star className={`h-3.5 w-3.5 ${isPromoted ? 'fill-current' : ''}`} />
                                      </button>
                                      <a
                                        href={redesign.presigned_url}
                                        download
                                        onClick={(e) => e.stopPropagation()}
                                        className="p-1 bg-black/60 rounded text-white hover:bg-black/80 transition-colors"
                                        title={tc('download')}
                                      >
                                        <Download className="h-3.5 w-3.5" />
                                      </a>
                                    </div>
                                  </div>
                                </div>
                                {/* Metadata row */}
                                <div className="flex items-center gap-2 mt-1.5 px-0.5">
                                  <button
                                    onClick={() => {
                                      if (parentThread) {
                                        setShowGallery(false);
                                        setActiveThreadId(parentThread.id);
                                      }
                                    }}
                                    className="text-xs text-indigo-600 hover:text-indigo-800 font-medium truncate"
                                  >
                                    {threadLabel}
                                  </button>
                                  <span className="text-[10px] text-gray-400 flex-shrink-0">{timeAgo}</span>
                                  {redesign.generation_time_ms && (
                                    <span className="text-[10px] text-gray-400 flex-shrink-0">
                                      {(redesign.generation_time_ms / 1000).toFixed(1)}s
                                    </span>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ) : (
                    <>
                      {/* 7c: Conversation Timeline */}
                      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                        {(() => {
                          const activeThread = threads.find((th) => th.id === activeThreadId);
                          if (!activeThread || activeThread.messages.length === 0) {
                            // Welcome / empty state
                            return (
                              <div className="flex flex-col items-center justify-center h-full text-center py-12">
                                <Sparkles className="h-12 w-12 text-purple-300 mb-4" />
                                <h3 className="text-lg font-semibold text-gray-700 mb-1">{t('startConversation')}</h3>
                                <p className="text-sm text-gray-500 max-w-sm">
                                  {t('startConversationDesc')}
                                </p>
                              </div>
                            );
                          }

                          return activeThread.messages.map((redesign) => {
                            const isLong = redesign.prompt.length > 300;
                            const isExpanded = expandedBubbles.has(redesign.id);
                            return (
                            <div key={redesign.id} className="space-y-3">
                              {/* User bubble */}
                              <div className="flex justify-end">
                                <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-purple-600 text-white px-4 py-3">
                                  <p className="text-sm whitespace-pre-wrap">
                                    {isLong && !isExpanded ? redesign.prompt.substring(0, 300) + '...' : redesign.prompt}
                                  </p>
                                  {isLong && (
                                    <button
                                      onClick={() => {
                                        setExpandedBubbles((prev) => {
                                          const next = new Set(prev);
                                          if (next.has(redesign.id)) next.delete(redesign.id);
                                          else next.add(redesign.id);
                                          return next;
                                        });
                                      }}
                                      className="text-[11px] text-white/70 hover:text-white underline mt-1"
                                    >
                                      {isExpanded ? t('showLess') : t('showMore')}
                                    </button>
                                  )}
                                  <div className="flex items-center gap-2 mt-2">
                                    {redesign.style_preset && (
                                      <span className="px-1.5 py-0.5 bg-white/20 text-[10px] font-semibold rounded uppercase">
                                        {redesign.style_preset.replace(/_/g, ' ')}
                                      </span>
                                    )}
                                    <span className="text-[10px] opacity-70 flex items-center gap-1">
                                      <Clock className="h-2.5 w-2.5" />
                                      {new Date(redesign.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                    {redesign.generation_time_ms && (
                                      <span className="text-[10px] opacity-70">
                                        {(redesign.generation_time_ms / 1000).toFixed(1)}s
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                              {/* AI bubble */}
                              <div className="flex justify-start">
                                <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-gray-100 p-2">
                                  <div className="relative">
                                    <img
                                      src={redesign.presigned_url}
                                      alt={`Redesign ${redesign.id}`}
                                      className="w-full rounded-lg cursor-pointer hover:opacity-95 transition-opacity"
                                      onClick={() => setSelectedRedesign(redesign)}
                                    />
                                    {selectedPhoto?.promoted_redesign?.id === redesign.id && (
                                      <span className="absolute top-2 left-2 inline-flex items-center gap-1 px-1.5 py-0.5 bg-yellow-400 text-[10px] font-bold text-yellow-900 rounded">
                                        <Star className="h-2.5 w-2.5 fill-current" />
                                        {t('promoted')}
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex items-center justify-between mt-2 px-1">
                                    <span className="text-[10px] text-gray-500">
                                      {t('clickToView')}
                                    </span>
                                    <div className="flex items-center gap-2">
                                      <button
                                        onClick={() => {
                                          if (!selectedPhoto) return;
                                          if (selectedPhoto.promoted_redesign?.id === redesign.id) {
                                            handleDemoteRedesign(selectedPhoto.id);
                                          } else {
                                            handlePromoteRedesign(selectedPhoto.id, redesign.id);
                                          }
                                        }}
                                        className={`inline-flex items-center text-xs ${
                                          selectedPhoto?.promoted_redesign?.id === redesign.id
                                            ? 'text-yellow-600 hover:text-yellow-700'
                                            : 'text-gray-400 hover:text-yellow-600'
                                        }`}
                                        title={selectedPhoto?.promoted_redesign?.id === redesign.id ? t('demoteRedesign') : t('promoteRedesign')}
                                      >
                                        <Star className={`h-3.5 w-3.5 ${selectedPhoto?.promoted_redesign?.id === redesign.id ? 'fill-current' : ''}`} />
                                      </button>
                                      <a
                                        href={redesign.presigned_url}
                                        download
                                        className="inline-flex items-center text-xs text-indigo-600 hover:text-indigo-700"
                                      >
                                        <Download className="h-3 w-3 mr-1" />
                                        {tc('download')}
                                      </a>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            </div>
                          );
                          });
                        })()}

                        {/* Optimistic user bubble + typing indicator while generating */}
                        {generating && optimisticPrompt && (
                          <div className="space-y-3">
                            <div className="flex justify-end">
                              <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-purple-600 text-white px-4 py-3">
                                <p className="text-sm whitespace-pre-wrap">
                                  {optimisticPrompt.length > 300 ? optimisticPrompt.substring(0, 300) + '...' : optimisticPrompt}
                                </p>
                              </div>
                            </div>
                            <div className="flex justify-start">
                              <div className="rounded-2xl rounded-tl-sm bg-gray-100 px-4 py-3">
                                <div className="flex items-center gap-1.5">
                                  <div className="h-2 w-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                                  <div className="h-2 w-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                                  <div className="h-2 w-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                                </div>
                              </div>
                            </div>
                          </div>
                        )}

                        <div ref={chatEndRef} />
                      </div>

                      {/* 7d: Input Area */}
                      <div className="border-t border-gray-200 px-4 py-3">
                        {(() => {
                          const activeThread = threads.find((th) => th.id === activeThreadId);
                          const isFollowUp = activeThread && activeThread.messages.length > 0;

                          return (
                            <>
                              {/* Style presets for first message only */}
                              {!isFollowUp && (
                                <div className="mb-3">
                                  <div className="flex gap-2 overflow-x-auto pb-2">
                                    {stylePresets.map((preset) => (
                                      <button
                                        key={preset.id}
                                        onClick={() => {
                                          setSelectedPreset(preset.id);
                                          if (preset.prompt_template) {
                                            const translatedRoomType = t(`roomTypes.${roomType}`);
                                            setCustomPrompt(
                                              preset.prompt_template.replace(/\{room_type\}/g, translatedRoomType)
                                            );
                                          } else {
                                            setCustomPrompt('');
                                          }
                                        }}
                                        className={`flex-shrink-0 px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                                          selectedPreset === preset.id
                                            ? 'bg-purple-600 text-white'
                                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                        }`}
                                        title={preset.description}
                                      >
                                        {preset.name}
                                      </button>
                                    ))}
                                  </div>
                                </div>
                              )}

                              <div className="flex gap-2 items-end">
                                <textarea
                                  ref={textareaRef}
                                  value={customPrompt}
                                  onChange={(e) => {
                                    setCustomPrompt(e.target.value);
                                    if (e.target.value && !isFollowUp) setSelectedPreset('');
                                  }}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter' && !e.shiftKey) {
                                      e.preventDefault();
                                      if (!generating && (selectedPreset || customPrompt)) {
                                        handleGenerateRedesign();
                                      }
                                    }
                                  }}
                                  placeholder={isFollowUp ? t('refinePlaceholder') : t('promptPlaceholder')}
                                  rows={1}
                                  style={{ minHeight: '40px', maxHeight: '200px' }}
                                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none overflow-y-auto"
                                />
                                <button
                                  onClick={handleGenerateRedesign}
                                  disabled={generating || (!selectedPreset && !customPrompt)}
                                  className="flex-shrink-0 p-2.5 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                                >
                                  {generating ? (
                                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" />
                                  ) : isFollowUp ? (
                                    <Send className="h-5 w-5" />
                                  ) : (
                                    <Sparkles className="h-5 w-5" />
                                  )}
                                </button>
                              </div>

                              <p className="text-[11px] text-gray-400 mt-1.5">
                                {isFollowUp
                                  ? t('refineHint')
                                  : t('promptHint')}
                              </p>
                            </>
                          );
                        })()}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      {photoToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-gray-900">{t('deletePhotoTitle')}</h2>
            <p className="mt-2 text-sm text-gray-600">
              {t('deletePhotoMessage', { filename: photoToDelete.filename })}
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setPhotoToDelete(null)}
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                disabled={deletingPhotoId === photoToDelete.id}
              >
                {tc('cancel')}
              </button>
              <button
                type="button"
                onClick={handleDeletePhoto}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
                disabled={deletingPhotoId === photoToDelete.id}
              >
                {deletingPhotoId === photoToDelete.id ? tc('deleting') : t('deletePhoto')}
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedRedesign && selectedPhoto && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 px-4"
          onClick={() => { setSelectedRedesign(null); setShowComparison(false); }}
        >
          <div
            className={`relative max-h-[90vh] w-full overflow-auto ${showComparison ? 'max-w-6xl' : 'max-w-5xl'}`}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="absolute right-2 top-2 z-10 flex items-center gap-2">
              <button
                onClick={() => setShowComparison(!showComparison)}
                className="rounded-full bg-black/60 p-1.5 text-white hover:bg-black/80"
                title={showComparison ? t('fullscreenTooltip') : t('compareTooltip')}
              >
                {showComparison ? <Maximize2 className="h-5 w-5" /> : <Columns className="h-5 w-5" />}
              </button>
              <button
                onClick={() => { setSelectedRedesign(null); setShowComparison(false); }}
                className="rounded-full bg-black/60 p-1.5 text-white hover:bg-black/80"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            {showComparison ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="mb-2 text-center text-sm font-semibold text-white/80">{t('original')}</p>
                  <img
                    src={selectedPhoto.presigned_url}
                    alt={selectedPhoto.filename}
                    className="w-full rounded-lg object-contain max-h-[60vh]"
                  />
                </div>
                <div>
                  <p className="mb-2 text-center text-sm font-semibold text-white/80">{t('redesign')}</p>
                  <img
                    src={selectedRedesign.presigned_url}
                    alt={`Redesign ${selectedRedesign.id}`}
                    className="w-full rounded-lg object-contain max-h-[60vh]"
                  />
                </div>
              </div>
            ) : (
              <img
                src={selectedRedesign.presigned_url}
                alt={`Redesign ${selectedRedesign.id}`}
                className="h-full w-full rounded-lg object-contain"
              />
            )}
            <div className="mt-4 max-h-40 overflow-auto rounded-lg bg-white/95 p-4 text-sm text-gray-700">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                {t('prompt')}
              </p>
              <p className="mt-2 whitespace-pre-line">{selectedRedesign.prompt}</p>
            </div>
          </div>
        </div>
      )}

      {showOriginalFullscreen && selectedPhoto && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 px-4"
          onClick={() => setShowOriginalFullscreen(false)}
        >
          <div
            className="relative max-h-[90vh] w-full max-w-5xl"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              onClick={() => setShowOriginalFullscreen(false)}
              className="absolute right-2 top-2 z-10 rounded-full bg-black/60 p-1.5 text-white hover:bg-black/80"
            >
              <X className="h-5 w-5" />
            </button>
            <img
              src={selectedPhoto.presigned_url}
              alt={selectedPhoto.filename}
              className="h-full w-full rounded-lg object-contain"
            />
          </div>
        </div>
      )}

      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 rounded-lg bg-gray-900 px-4 py-3 text-sm font-semibold text-white shadow-lg">
          {toastMessage}
        </div>
      )}
    </div>
  );
}

export default function PhotosPage() {
  return (
    <ProtectedRoute>
      <PhotosContent />
    </ProtectedRoute>
  );
}
