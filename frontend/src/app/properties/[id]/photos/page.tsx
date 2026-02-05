"use client";

import { useState, useEffect } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import Header from '@/components/Header';
import { ArrowLeft, Upload, Sparkles, Image as ImageIcon, Download, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import api from '@/lib/api';

interface Photo {
  id: number;
  filename: string;
  room_type?: string;
  description?: string;
  uploaded_at: string;
  presigned_url: string;
  redesign_count: number;
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
}

interface StylePreset {
  id: string;
  name: string;
  description: string;
  prompt_template?: string;
}

function PhotosContent() {
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

  // Load style presets
  useEffect(() => {
    loadStylePresets();
  }, []);

  // Load photos
  useEffect(() => {
    loadPhotos();
  }, [propertyId]);

  // Load redesigns when photo is selected
  useEffect(() => {
    if (selectedPhoto) {
      loadRedesigns(selectedPhoto.id);
    }
  }, [selectedPhoto]);

  useEffect(() => {
    if (!selectedPreset) return;
    const preset = stylePresets.find((item) => item.id === selectedPreset);
    if (!preset?.prompt_template) return;
    setCustomPrompt(preset.prompt_template.replace(/\{room_type\}/g, roomType));
  }, [selectedPreset, roomType, stylePresets]);

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
      alert(error.response?.data?.detail || 'Failed to update room type');
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
      alert(error.response?.data?.detail || 'Failed to upload photo');
    } finally {
      setUploading(false);
    }
  };

  const handleGenerateRedesign = async () => {
    if (!selectedPhoto) {
      alert('Please select a photo first');
      return;
    }

    if (!selectedPreset && !customPrompt) {
      alert('Please select a preset or enter a custom prompt');
      return;
    }

    try {
      setGenerating(true);
      const response = await api.post(`/api/photos/${selectedPhoto.id}/redesign`, {
        style_preset: selectedPreset || undefined,
        custom_prompt: customPrompt || undefined,
        room_type: selectedPhoto.room_type || roomType,
        aspect_ratio: '16:9'
      });

      const newRedesign = response.data;
      setRedesigns([newRedesign, ...redesigns]);

      // Clear inputs
      setSelectedPreset('');
      setCustomPrompt('');
      setToastMessage('Redesign generated');
      setTimeout(() => setToastMessage(null), 3000);
    } catch (error: any) {
      console.error('Error generating redesign:', error);
      alert(error.response?.data?.detail || 'Failed to generate redesign');
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
      alert(error.response?.data?.detail || 'Failed to delete photo');
    } finally {
      setDeletingPhotoId(null);
      setPhotoToDelete(null);
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
            Back to Property
          </Link>

          <h1 className="text-3xl font-bold text-gray-900 mb-8">
            Apartment Redesign Studio
          </h1>

          {/* Upload Section */}
          <div className="bg-white shadow rounded-lg p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center">
              <Upload className="h-5 w-5 mr-2 text-indigo-600" />
              Upload Photo
            </h2>

            <div className="flex gap-4 items-end">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Room Type
                </label>
                <select
                  value={roomType}
                  onChange={(e) => setRoomType(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="living room">Living Room</option>
                  <option value="bedroom">Bedroom</option>
                  <option value="kitchen">Kitchen</option>
                  <option value="bathroom">Bathroom</option>
                  <option value="dining room">Dining Room</option>
                  <option value="home office">Home Office</option>
                </select>
              </div>

              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Choose Photo
                </label>
                <label className="flex items-center justify-center px-6 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 cursor-pointer">
                  <Upload className="h-4 w-4 mr-2" />
                  {uploading ? 'Uploading...' : 'Select Image'}
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
                  Your Photos ({photos.length})
                </h2>

                {loading ? (
                  <div className="text-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
                  </div>
                ) : photos.length === 0 ? (
                  <p className="text-gray-500 text-center py-8">
                    No photos uploaded yet
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
                              e.currentTarget.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect fill="%23ddd" width="200" height="200"/><text x="50%" y="50%" text-anchor="middle" fill="%23999">Image Error</text></svg>';
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
                            aria-label={`Delete ${photo.filename}`}
                            title="Delete photo"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                        <div className="p-2 bg-gray-50">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {photo.filename}
                          </p>
                          <p className="text-xs text-gray-500">
                            {photo.room_type || 'No room type'} • {photo.redesign_count} redesigns
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Right Column: Redesign Studio */}
            <div className="lg:col-span-2">
              {!selectedPhoto ? (
                <div className="bg-white shadow rounded-lg p-12 text-center">
                  <ImageIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-500">Upload or select a photo to get started</p>
                </div>
              ) : (
                <>
                  {/* Original Photo */}
                  <div className="bg-white shadow rounded-lg p-6 mb-6">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
                      <h3 className="text-lg font-semibold text-gray-900">
                        Original Photo
                      </h3>
                      <div className="flex items-center gap-3">
                        <label className="text-sm font-medium text-gray-700">
                          Room Type
                        </label>
                        <select
                          value={roomType}
                          onChange={(e) => handleRoomTypeChange(e.target.value)}
                          disabled={savingRoomType}
                          className="w-44 px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100"
                        >
                          <option value="living room">Living Room</option>
                          <option value="bedroom">Bedroom</option>
                          <option value="kitchen">Kitchen</option>
                          <option value="bathroom">Bathroom</option>
                          <option value="dining room">Dining Room</option>
                          <option value="home office">Home Office</option>
                        </select>
                      </div>
                    </div>
                    <img
                      src={selectedPhoto.presigned_url}
                      alt={selectedPhoto.filename}
                      className="w-full rounded-lg"
                    />
                  </div>

                  {/* Redesign Controls */}
                  <div className="bg-white shadow rounded-lg p-6 mb-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                      <Sparkles className="h-5 w-5 mr-2 text-purple-600" />
                      Generate Redesign
                    </h3>

                    {/* Style Presets */}
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Choose a Design Style
                      </label>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        {stylePresets.map((preset) => (
                          <button
                            key={preset.id}
                            onClick={() => {
                              setSelectedPreset(preset.id);
                              if (preset.prompt_template) {
                                setCustomPrompt(
                                  preset.prompt_template.replace(/\{room_type\}/g, roomType)
                                );
                              } else {
                                setCustomPrompt('');
                              }
                            }}
                            className={`p-4 border-2 rounded-lg text-left transition-all ${
                              selectedPreset === preset.id
                                ? 'border-purple-600 bg-purple-50'
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                          >
                            <p className="font-semibold text-gray-900 mb-1">{preset.name}</p>
                            <p className="text-xs text-gray-600">{preset.description}</p>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Custom Prompt */}
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Or Enter Custom Prompt
                      </label>
                      <textarea
                        value={customPrompt}
                        onChange={(e) => {
                          setCustomPrompt(e.target.value);
                          if (e.target.value) setSelectedPreset('');
                        }}
                        placeholder="Describe your desired redesign in detail..."
                        rows={6}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Tip: Describe the scene, don&apos;t just list keywords
                      </p>
                    </div>

                    <button
                      onClick={handleGenerateRedesign}
                      disabled={generating || (!selectedPreset && !customPrompt)}
                      className="w-full px-6 py-3 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed flex items-center justify-center gap-2 font-semibold"
                    >
                      {generating ? (
                        <>
                          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                          Generating... (this may take 10-30s)
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-5 w-5" />
                          Generate Redesign
                        </>
                      )}
                    </button>
                  </div>

                  {/* Redesign Gallery */}
                  <div className="bg-white shadow rounded-lg p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">
                      Redesigns ({redesigns.length})
                    </h3>

                    {redesigns.length === 0 ? (
                      <p className="text-gray-500 text-center py-8">
                        No redesigns yet. Generate your first one above!
                      </p>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {redesigns.map((redesign) => (
                      <div
                        key={redesign.id}
                        className="border border-gray-200 rounded-lg overflow-hidden hover:shadow-lg transition-shadow"
                      >
                        <img
                          src={redesign.presigned_url}
                          alt={`Redesign ${redesign.id}`}
                          className="w-full h-64 object-cover cursor-pointer"
                          onClick={() => setSelectedRedesign(redesign)}
                        />
                            <div className="p-4 bg-gray-50">
                              <div className="flex items-center justify-between mb-2">
                                <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs font-semibold rounded">
                                  {redesign.style_preset?.replace(/_/g, ' ').toUpperCase() || 'CUSTOM'}
                                </span>
                                {redesign.generation_time_ms && (
                                  <span className="text-xs text-gray-500">
                                    {(redesign.generation_time_ms / 1000).toFixed(1)}s
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-gray-600 line-clamp-2 mb-2">
                                {redesign.prompt.substring(0, 100)}...
                              </p>
                              <a
                                href={redesign.presigned_url}
                                download
                                className="inline-flex items-center text-sm text-indigo-600 hover:text-indigo-700"
                              >
                                <Download className="h-4 w-4 mr-1" />
                                Download
                              </a>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </main>

      {photoToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-gray-900">Delete photo</h2>
            <p className="mt-2 text-sm text-gray-600">
              Delete &quot;{photoToDelete.filename}&quot; and all its redesigns? This cannot be undone.
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setPhotoToDelete(null)}
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                disabled={deletingPhotoId === photoToDelete.id}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeletePhoto}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
                disabled={deletingPhotoId === photoToDelete.id}
              >
                {deletingPhotoId === photoToDelete.id ? 'Deleting...' : 'Delete photo'}
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedRedesign && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 px-4"
          onClick={() => setSelectedRedesign(null)}
        >
          <div
            className="relative max-h-[90vh] w-full max-w-5xl"
            onClick={(event) => event.stopPropagation()}
          >
            <img
              src={selectedRedesign.presigned_url}
              alt={`Redesign ${selectedRedesign.id}`}
              className="h-full w-full rounded-lg object-contain"
            />
            <div className="mt-4 max-h-40 overflow-auto rounded-lg bg-white/95 p-4 text-sm text-gray-700">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Prompt
              </p>
              <p className="mt-2 whitespace-pre-line">{selectedRedesign.prompt}</p>
            </div>
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
