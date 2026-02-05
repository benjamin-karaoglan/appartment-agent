"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/ProtectedRoute';
import Header from '@/components/Header';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';
import { Plus, Home, FileText, TrendingUp, Trash2, Palette } from 'lucide-react';
import type { Property } from '@/types';

interface UserStats {
  documents_analyzed_count: number;
  redesigns_generated_count: number;
  total_properties: number;
}

interface DVFStats {
  total_records: number;
  formatted_count: string;
  total_imports: number;
  last_updated: string | null;
}

function DashboardContent() {
  const { user } = useAuth();
  const router = useRouter();
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletePropertyId, setDeletePropertyId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [userStats, setUserStats] = useState<UserStats | null>(null);
  const [dvfStats, setDvfStats] = useState<DVFStats | null>(null);

  useEffect(() => {
    loadProperties();
    loadUserStats();
    loadDvfStats();
  }, []);

  const loadProperties = async () => {
    try {
      const response = await api.get('/api/properties/');
      setProperties(response.data);
    } catch (error) {
      console.error('Failed to load properties:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadUserStats = async () => {
    try {
      const response = await api.get('/api/users/stats');
      setUserStats(response.data);
    } catch (error) {
      console.error('Failed to load user stats:', error);
    }
  };

  const loadDvfStats = async () => {
    try {
      const response = await api.get('/api/properties/dvf-stats');
      setDvfStats(response.data);
    } catch (error) {
      console.error('Failed to load DVF stats:', error);
    }
  };

  const handleDeleteClick = (e: React.MouseEvent, propertyId: number) => {
    e.stopPropagation(); // Prevent navigation to property detail
    setDeletePropertyId(propertyId);
  };

  const confirmDelete = async () => {
    if (!deletePropertyId) return;

    setDeleting(true);
    try {
      await api.delete(`/api/properties/${deletePropertyId}`);
      // Reload properties list
      await loadProperties();
      setDeletePropertyId(null);
    } catch (error) {
      console.error('Failed to delete property:', error);
      alert('Failed to delete property. Please try again.');
    } finally {
      setDeleting(false);
    }
  };

  const cancelDelete = () => {
    if (!deleting) {
      setDeletePropertyId(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {/* Welcome Section */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">
              Welcome back, {user?.full_name}!
            </h1>
            <p className="mt-2 text-sm text-gray-600">
              Manage your properties and analyze potential investments
            </p>
          </div>

          {/* Stats Overview */}
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-3 mb-8">
            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <Home className="h-6 w-6 text-gray-400" />
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">
                        Total Properties
                      </dt>
                      <dd className="text-3xl font-semibold text-gray-900">
                        {properties.length}
                      </dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <FileText className="h-6 w-6 text-gray-400" />
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">
                        Documents Analyzed
                      </dt>
                      <dd className="text-3xl font-semibold text-gray-900">
                        {userStats?.documents_analyzed_count ?? 0}
                      </dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <Palette className="h-6 w-6 text-gray-400" />
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">
                        Redesigns Generated
                      </dt>
                      <dd className="text-3xl font-semibold text-gray-900">
                        {userStats?.redesigns_generated_count ?? 0}
                      </dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <TrendingUp className="h-6 w-6 text-gray-400" />
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">
                        DVF Records Available
                      </dt>
                      <dd className="text-3xl font-semibold text-gray-900">
                        {dvfStats?.formatted_count ?? '0'}
                      </dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Properties Section */}
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 border-b border-gray-200 sm:px-6">
              <div className="flex items-center justify-between">
                <h3 className="text-lg leading-6 font-medium text-gray-900">
                  Your Properties
                </h3>
                <button
                  onClick={() => router.push('/properties/new')}
                  className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <Plus className="h-5 w-5 mr-2" />
                  Add Property
                </button>
              </div>
            </div>

            <div className="px-4 py-5 sm:p-6">
              {loading ? (
                <div className="text-center py-12">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <p className="mt-2 text-sm text-gray-500">Loading properties...</p>
                </div>
              ) : properties.length === 0 ? (
                <div className="text-center py-12">
                  <Home className="mx-auto h-12 w-12 text-gray-400" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900">No properties</h3>
                  <p className="mt-1 text-sm text-gray-500">
                    Get started by adding your first property.
                  </p>
                  <div className="mt-6">
                    <button
                      onClick={() => router.push('/properties/new')}
                      className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                    >
                      <Plus className="h-5 w-5 mr-2" />
                      Add Property
                    </button>
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {properties.map((property) => (
                    <div
                      key={property.id}
                      onClick={() => router.push(`/properties/${property.id}`)}
                      className="relative border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow cursor-pointer"
                    >
                      <button
                        onClick={(e) => handleDeleteClick(e, property.id)}
                        className="absolute top-2 right-2 p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                        title="Delete property"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                      <h4 className="text-lg font-medium text-gray-900 mb-2 pr-8">
                        {property.address}
                      </h4>
                      <p className="text-sm text-gray-500 mb-2">
                        {property.city} {property.postal_code}
                      </p>
                      {property.asking_price && (
                        <p className="text-lg font-semibold text-blue-600">
                          {new Intl.NumberFormat('fr-FR', {
                            style: 'currency',
                            currency: 'EUR',
                          }).format(property.asking_price)}
                        </p>
                      )}
                      <div className="mt-3 flex items-center text-sm text-gray-500">
                        {property.surface_area && (
                          <span>{property.surface_area}m²</span>
                        )}
                        {property.rooms && (
                          <span className="ml-3">{property.rooms} pièces</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Delete Confirmation Modal */}
          {deletePropertyId && (
            <div className="fixed z-10 inset-0 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
              <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
                {/* Background overlay */}
                <div
                  className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
                  aria-hidden="true"
                  onClick={cancelDelete}
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
                      onClick={confirmDelete}
                      className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {deleting ? 'Deleting...' : 'Delete'}
                    </button>
                    <button
                      type="button"
                      disabled={deleting}
                      onClick={cancelDelete}
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

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
