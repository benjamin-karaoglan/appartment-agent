# API Reference

## Base URL

- **Development**: `http://localhost:8000/api`
- **Production**: `https://your-domain.com/api`

## Authentication

Authentication is handled by [Better Auth](https://www.better-auth.com/). The frontend manages sign-in/sign-up via `/api/auth/[...all]` API routes, which set an HTTP-only session cookie (`better-auth.session_token`).

Backend endpoints validate requests by reading this session cookie:

```bash
curl -X GET http://localhost:8000/api/properties \
  -H "Cookie: better-auth.session_token=SESSION_TOKEN"
```

The backend also supports legacy JWT Bearer tokens during migration (via `get_current_user_hybrid`).

## Endpoints

### Authentication

#### Register User

```http
POST /api/users/register
```

**Request Body**:

```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "John Doe"
}
```

**Response** `201 Created`:

```json
{
  "id": 1,
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2025-01-30T10:00:00Z"
}
```

#### Login

Authentication is handled client-side via the Better Auth SDK. The frontend calls `authClient.signIn.email()` which hits the Next.js `/api/auth/sign-in/email` route, setting a session cookie on success.

For the legacy endpoint (kept for backward compatibility):

```http
POST /api/users/login
```

**Request Body**:

```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response** `200 OK`: Sets `better-auth.session_token` cookie.

---

### Properties

#### List Properties

```http
GET /api/properties
```

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `skip` | int | Pagination offset (default: 0) |
| `limit` | int | Results per page (default: 100) |

**Response** `200 OK`:

```json
[
  {
    "id": 1,
    "address": "56 Rue Notre-Dame des Champs",
    "postal_code": "75006",
    "city": "Paris",
    "asking_price": 850000,
    "surface_area": 65.5,
    "created_at": "2025-01-30T10:00:00Z"
  }
]
```

#### Create Property

```http
POST /api/properties
```

**Request Body**:

```json
{
  "address": "56 Rue Notre-Dame des Champs",
  "postal_code": "75006",
  "city": "Paris",
  "asking_price": 850000,
  "surface_area": 65.5,
  "property_type": "apartment",
  "rooms": 3
}
```

#### Get Property

```http
GET /api/properties/{id}
```

#### Update Property

```http
PUT /api/properties/{id}
```

#### Delete Property

```http
DELETE /api/properties/{id}
```

---

### Documents

#### Upload Single Document

```http
POST /api/documents/upload
Content-Type: multipart/form-data
```

**Form Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | PDF or image file |
| `property_id` | int | Yes | Associated property |
| `document_type` | string | No | Type (auto-classified if omitted) |

**Response** `201 Created`:

```json
{
  "id": 1,
  "filename": "pv_ag_2024.pdf",
  "document_type": "pv_ag",
  "status": "processing",
  "property_id": 1,
  "created_at": "2025-01-30T10:00:00Z"
}
```

#### Bulk Upload Documents

```http
POST /api/documents/bulk-upload
Content-Type: multipart/form-data
```

**Form Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | file[] | Yes | Multiple PDF/image files |
| `property_id` | int | Yes | Associated property |

**Response** `202 Accepted`:

```json
{
  "status": "processing",
  "workflow_id": "bulk-processing-1-1706612400",
  "document_ids": [1, 2, 3],
  "total_files": 3,
  "message": "Successfully uploaded 3 documents. Processing..."
}
```

#### Get Bulk Processing Status

```http
GET /api/documents/bulk-status/{workflow_id}
```

**Response** `200 OK`:

```json
{
  "workflow_id": "bulk-processing-1-1706612400",
  "property_id": 1,
  "status": "completed",
  "progress": {
    "total": 3,
    "completed": 3,
    "failed": 0,
    "percentage": 100
  },
  "documents": [
    {
      "id": 1,
      "filename": "pv_ag_2024.pdf",
      "document_type": "pv_ag",
      "status": "analyzed"
    }
  ],
  "synthesis": {
    "summary": "Property analysis complete...",
    "total_annual_cost": 3500.0,
    "total_one_time_cost": 15000.0,
    "risk_level": "medium",
    "recommendations": ["..."]
  }
}
```

#### List Documents

```http
GET /api/documents
```

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `property_id` | int | Filter by property |
| `document_type` | string | Filter by type |

#### Get Document

```http
GET /api/documents/{id}
```

#### Delete Document

```http
DELETE /api/documents/{id}
```

---

### Analysis

#### Get Price Analysis

```http
GET /api/analysis/price
```

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `address` | string | Yes | Property address |
| `postal_code` | string | Yes | Postal code |
| `property_type` | string | No | apartment/house |

**Response** `200 OK`:

```json
{
  "address": "56 Rue Notre-Dame des Champs",
  "postal_code": "75006",
  "simple_analysis": {
    "sales_count": 3,
    "avg_price_per_sqm": 12500,
    "min_price": 600000,
    "max_price": 1350000,
    "sales": [...]
  },
  "trend_analysis": {
    "price_trend": 2.5,
    "projected_price_per_sqm": 12812,
    "confidence": "high",
    "data_points": 45
  },
  "recommendation": {
    "fair_price_range": [800000, 900000],
    "market_position": "slightly_above_market",
    "negotiation_suggestion": "Consider offering 5-8% below asking"
  }
}
```

#### Get Market Trends

```http
GET /api/analysis/trends
```

**Query Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `postal_code` | string | Yes | Area postal code |
| `years` | int | No | Years of history (default: 5) |

**Response** `200 OK`:

```json
{
  "postal_code": "75006",
  "trends": [
    {"year": 2021, "avg_price_per_sqm": 11200, "transactions": 245},
    {"year": 2022, "avg_price_per_sqm": 11800, "transactions": 231},
    {"year": 2023, "avg_price_per_sqm": 12100, "transactions": 198},
    {"year": 2024, "avg_price_per_sqm": 12400, "transactions": 167},
    {"year": 2025, "avg_price_per_sqm": 12650, "transactions": 89}
  ],
  "yoy_change": 2.0,
  "five_year_change": 12.9
}
```

---

### Photos

#### Upload Photo

```http
POST /api/photos/upload
Content-Type: multipart/form-data
```

**Form Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | JPG/PNG image |
| `property_id` | int | Yes | Associated property |
| `room_type` | string | No | living_room, bedroom, etc. |

#### Request Redesign

```http
POST /api/photos/{id}/redesign
```

**Request Body**:

```json
{
  "style": "modern",
  "preferences": {
    "color_scheme": "neutral",
    "furniture_style": "minimalist"
  }
}
```

**Response** `202 Accepted`:

```json
{
  "redesign_id": "redesign-123-456",
  "status": "generating",
  "estimated_time": 30
}
```

#### Get Redesign Status

```http
GET /api/photos/redesign/{redesign_id}
```

---

### Webhooks

#### MinIO Event Webhook

```http
POST /api/webhooks/minio
```

Internal endpoint for MinIO event notifications.

## Error Responses

All endpoints return consistent error format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

| Status Code | Description |
|-------------|-------------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing/invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Schema mismatch |
| 500 | Internal Server Error |

## Rate Limiting

API requests are rate-limited per user:

- **Standard**: 100 requests/minute
- **Bulk operations**: 10 requests/minute

Exceeded limits return `429 Too Many Requests`.
