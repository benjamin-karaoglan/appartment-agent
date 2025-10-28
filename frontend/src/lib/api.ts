import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auth API
export const authAPI = {
  register: async (data: { email: string; password: string; full_name: string }) => {
    const response = await api.post('/api/users/register', data)
    return response.data
  },

  login: async (data: { email: string; password: string }) => {
    const response = await api.post('/api/users/login', data)
    return response.data
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
