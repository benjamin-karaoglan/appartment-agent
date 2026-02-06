import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Include credentials (cookies) in cross-origin requests
  withCredentials: true,
})

// Add locale to requests (no more token handling - Better Auth uses cookies)
api.interceptors.request.use((config) => {
  // Send current locale as Accept-Language header
  if (typeof document !== 'undefined') {
    const htmlLang = document.documentElement.lang
    if (htmlLang) {
      config.headers['Accept-Language'] = htmlLang
    }
  }

  return config
})

// Auth API (deprecated - use Better Auth client instead)
export const authAPI = {
  register: async (data: { email: string; password: string; full_name: string }) => {
    // This is now handled by Better Auth
    throw new Error('Use Better Auth signUp.email() instead')
  },

  login: async (data: { email: string; password: string }) => {
    // This is now handled by Better Auth
    throw new Error('Use Better Auth signIn.email() instead')
  },

  getCurrentUser: async () => {
    const response = await api.get('/api/users/me')
    return response.data
  },
}

// Properties API
export const propertiesAPI = {
  list: async () => {
    const response = await api.get('/api/properties/')
    return response.data
  },

  get: async (id: number) => {
    const response = await api.get(`/api/properties/${id}`)
    return response.data
  },

  create: async (data: any) => {
    const response = await api.post('/api/properties/', data)
    return response.data
  },

  update: async (id: number, data: any) => {
    const response = await api.put(`/api/properties/${id}`, data)
    return response.data
  },

  delete: async (id: number) => {
    await api.delete(`/api/properties/${id}`)
  },

  analyzePrice: async (id: number) => {
    const response = await api.post(`/api/properties/${id}/analyze-price`)
    return response.data
  },
}

// Documents API
export const documentsAPI = {
  list: async (propertyId?: number) => {
    const params = propertyId ? { property_id: propertyId } : {}
    const response = await api.get('/api/documents/', { params })
    return response.data
  },

  upload: async (file: File, propertyId: number | null, documentCategory: string) => {
    const formData = new FormData()
    formData.append('file', file)
    if (propertyId) {
      formData.append('property_id', propertyId.toString())
    }
    formData.append('document_category', documentCategory)

    const response = await api.post('/api/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  analyzePVAG: async (documentId: number) => {
    const response = await api.post(`/api/documents/${documentId}/analyze-pvag`)
    return response.data
  },

  analyzeDiagnostic: async (documentId: number) => {
    const response = await api.post(`/api/documents/${documentId}/analyze-diagnostic`)
    return response.data
  },

  analyzeTaxCharges: async (documentId: number) => {
    const response = await api.post(`/api/documents/${documentId}/analyze-tax-charges`)
    return response.data
  },

  delete: async (id: number) => {
    await api.delete(`/api/documents/${id}`)
  },
}

// Analysis API
export const analysisAPI = {
  generateComprehensive: async (propertyId: number) => {
    const response = await api.post(`/api/analysis/${propertyId}/comprehensive`)
    return response.data
  },

  getLatest: async (propertyId: number) => {
    const response = await api.get(`/api/analysis/${propertyId}/latest`)
    return response.data
  },
}

// Photos API
export const photosAPI = {
  analyze: async (file: File, transformationRequest: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('transformation_request', transformationRequest)

    const response = await api.post('/api/photos/analyze', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  uploadAndSave: async (file: File, propertyId: number) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('property_id', propertyId.toString())

    const response = await api.post('/api/photos/upload-and-save', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },
}

// Default export for convenience
export default api
