"use client";

import { useState, useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/ProtectedRoute';
import Header from '@/components/Header';
import { api } from '@/lib/api';
import { ArrowLeft, Search } from 'lucide-react';
import Link from 'next/link';

interface PropertyFormData {
  address: string;
  postal_code?: string;
  city?: string;
  department?: string;
  asking_price?: number;
  surface_area?: number;
  rooms?: number;
  property_type?: string;
  floor?: number;
  building_year?: number;
}

interface AddressSuggestion {
  address: string;
  postal_code: string;
  city: string;
  property_type: string;
  count: number;
}

function NewPropertyContent() {
  const router = useRouter();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [addressQuery, setAddressQuery] = useState('');
  const [suggestions, setSuggestions] = useState<AddressSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const suggestionsRef = useRef<HTMLDivElement>(null);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors },
  } = useForm<PropertyFormData>();

  // Close suggestions when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (suggestionsRef.current && !suggestionsRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Search addresses as user types
  useEffect(() => {
    const searchAddresses = async () => {
      if (addressQuery.length < 2) {
        setSuggestions([]);
        return;
      }

      setLoadingSuggestions(true);
      try {
        const response = await api.get(`/api/properties/search-addresses?q=${encodeURIComponent(addressQuery)}&limit=15`);
        setSuggestions(response.data);
        setShowSuggestions(true);
      } catch (err) {
        console.error('Failed to search addresses:', err);
        setSuggestions([]);
      } finally {
        setLoadingSuggestions(false);
      }
    };

    const timeoutId = setTimeout(searchAddresses, 400);
    return () => clearTimeout(timeoutId);
  }, [addressQuery]);

  const selectAddress = (suggestion: AddressSuggestion) => {
    setValue('address', suggestion.address);
    setValue('postal_code', suggestion.postal_code);
    setValue('city', suggestion.city);
    setValue('property_type', suggestion.property_type);
    setValue('department', suggestion.postal_code.substring(0, 2));
    setAddressQuery(suggestion.address);
    setShowSuggestions(false);
  };

  const onSubmit = async (data: PropertyFormData) => {
    setError('');
    setLoading(true);

    try {
      const response = await api.post('/api/properties/', data);
      const property = response.data;

      // Redirect to the property detail page
      router.push(`/properties/${property.id}`);
    } catch (err: any) {
      console.error('Property creation error:', err);
      setError(err.response?.data?.detail || 'Failed to create property. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <main className="max-w-3xl mx-auto py-6 sm:px-6 lg:px-8">
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
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">Add New Property</h1>
            <p className="mt-2 text-sm text-gray-600">
              Enter the property details to start your analysis
            </p>
          </div>

          {/* Form */}
          <div className="bg-white shadow rounded-lg">
            <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-6">
              {error && (
                <div className="rounded-md bg-red-50 p-4">
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}

              {/* Address Section */}
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Property Location
                </h3>
                <div className="space-y-4">
                  <div className="relative" ref={suggestionsRef}>
                    <label htmlFor="address" className="block text-sm font-medium text-gray-700">
                      Address <span className="text-red-500">*</span>
                    </label>
                    <div className="relative mt-1">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Search className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        id="address"
                        type="text"
                        value={addressQuery}
                        onChange={(e) => {
                          const value = e.target.value;
                          setAddressQuery(value);
                          setValue('address', value);
                        }}
                        onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                        className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        placeholder="Start typing address... (e.g., 56 notre dame)"
                        autoComplete="off"
                      />
                      <input type="hidden" {...register('address', { required: 'Address is required' })} />
                      {loadingSuggestions && (
                        <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
                          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                        </div>
                      )}
                    </div>
                    {errors.address && (
                      <p className="mt-1 text-sm text-red-600">{errors.address.message}</p>
                    )}

                    {/* Suggestions dropdown */}
                    {showSuggestions && suggestions.length > 0 && (
                      <div className="absolute z-10 mt-1 w-full bg-white shadow-lg max-h-60 rounded-md py-1 text-base ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none sm:text-sm">
                        {suggestions.map((suggestion, index) => (
                          <div
                            key={index}
                            onClick={() => selectAddress(suggestion)}
                            className="cursor-pointer select-none relative py-2 pl-3 pr-9 hover:bg-blue-50"
                          >
                            <div className="flex flex-col">
                              <span className="font-medium text-gray-900">{suggestion.address}</span>
                              <span className="text-sm text-gray-500">
                                {suggestion.city} {suggestion.postal_code} - {suggestion.property_type}
                                <span className="ml-2 text-xs text-gray-400">({suggestion.count} sales)</span>
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {showSuggestions && addressQuery.length >= 2 && suggestions.length === 0 && !loadingSuggestions && (
                      <div className="absolute z-10 mt-1 w-full bg-white shadow-lg rounded-md py-3 px-4 text-sm text-gray-500">
                        No addresses found in Paris. Try typing the street name (e.g., "notre dame des champs")
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    <div>
                      <label htmlFor="postal_code" className="block text-sm font-medium text-gray-700">
                        Postal Code
                      </label>
                      <input
                        id="postal_code"
                        type="text"
                        {...register('postal_code')}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        placeholder="75001"
                      />
                    </div>

                    <div>
                      <label htmlFor="city" className="block text-sm font-medium text-gray-700">
                        City
                      </label>
                      <input
                        id="city"
                        type="text"
                        {...register('city')}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        placeholder="Paris"
                      />
                    </div>

                    <div>
                      <label htmlFor="department" className="block text-sm font-medium text-gray-700">
                        Department
                      </label>
                      <input
                        id="department"
                        type="text"
                        {...register('department')}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                        placeholder="75"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Property Details Section */}
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Property Details
                </h3>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div>
                    <label htmlFor="property_type" className="block text-sm font-medium text-gray-700">
                      Property Type
                    </label>
                    <select
                      id="property_type"
                      {...register('property_type')}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    >
                      <option value="">Select type</option>
                      <option value="Appartement">Appartement</option>
                      <option value="Maison">Maison</option>
                    </select>
                  </div>

                  <div>
                    <label htmlFor="asking_price" className="block text-sm font-medium text-gray-700">
                      Asking Price (€)
                    </label>
                    <input
                      id="asking_price"
                      type="number"
                      {...register('asking_price', {
                        valueAsNumber: true,
                      })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      placeholder="250000"
                    />
                  </div>

                  <div>
                    <label htmlFor="surface_area" className="block text-sm font-medium text-gray-700">
                      Surface Area (m²)
                    </label>
                    <input
                      id="surface_area"
                      type="number"
                      step="0.01"
                      {...register('surface_area', {
                        valueAsNumber: true,
                      })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      placeholder="65"
                    />
                  </div>

                  <div>
                    <label htmlFor="rooms" className="block text-sm font-medium text-gray-700">
                      Number of Rooms
                    </label>
                    <input
                      id="rooms"
                      type="number"
                      {...register('rooms', {
                        valueAsNumber: true,
                      })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      placeholder="3"
                    />
                  </div>

                  <div>
                    <label htmlFor="floor" className="block text-sm font-medium text-gray-700">
                      Floor
                    </label>
                    <input
                      id="floor"
                      type="number"
                      {...register('floor', {
                        valueAsNumber: true,
                      })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      placeholder="2"
                    />
                  </div>

                  <div>
                    <label htmlFor="building_year" className="block text-sm font-medium text-gray-700">
                      Building Year
                    </label>
                    <input
                      id="building_year"
                      type="number"
                      {...register('building_year', {
                        valueAsNumber: true,
                      })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 text-gray-900 bg-white focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      placeholder="1990"
                    />
                  </div>
                </div>
              </div>

              {/* Submit Button */}
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => router.push('/dashboard')}
                  className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? 'Creating...' : 'Create Property'}
                </button>
              </div>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function NewPropertyPage() {
  return (
    <ProtectedRoute>
      <NewPropertyContent />
    </ProtectedRoute>
  );
}
