# Frontend

The AppArt Agent frontend is a Next.js 14 application using the App Router.

## Overview

| Technology | Purpose |
|------------|---------|
| Next.js 14 | React framework with App Router |
| React 18 | UI library with Server Components |
| TypeScript | Type safety |
| Tailwind CSS | Styling |
| Better Auth | Authentication (email/password + Google OAuth) |
| next-intl | Internationalization (FR/EN) |
| React Query | Data fetching and caching |
| pnpm | Package management |

## Project Structure

```text
frontend/
├── messages/                    # Translation files
│   ├── en.json
│   └── fr.json
├── src/
│   ├── app/
│   │   ├── [locale]/            # Locale-scoped pages (FR/EN)
│   │   │   ├── page.tsx         # Home page
│   │   │   ├── dashboard/       # Main dashboard
│   │   │   ├── properties/      # Property management
│   │   │   │   ├── [id]/
│   │   │   │   │   ├── documents/
│   │   │   │   │   └── photos/
│   │   │   │   └── new/
│   │   │   └── auth/
│   │   │       ├── login/
│   │   │       └── register/
│   │   ├── api/auth/[...all]/   # Better Auth API route
│   │   ├── globals.css          # Global styles
│   │   └── layout.tsx           # Root layout
│   ├── components/              # Shared components
│   │   ├── Header.tsx           # Navigation + locale switcher
│   │   ├── ProtectedRoute.tsx   # Auth guard
│   │   └── MarketTrendChart.tsx
│   ├── contexts/
│   │   └── AuthContext.tsx       # Auth state (Better Auth)
│   ├── i18n/                    # Internationalization
│   │   ├── config.ts
│   │   ├── navigation.ts
│   │   └── routing.ts
│   ├── lib/
│   │   ├── api.ts               # Axios API client
│   │   ├── auth.ts              # Better Auth server config
│   │   └── auth-client.ts       # Better Auth client
│   ├── middleware.ts            # next-intl locale middleware
│   └── types/
│       └── index.ts
├── tailwind.config.js
├── next.config.js
└── package.json
```

## Sections

| Guide | Description |
|-------|-------------|
| [Pages & Routes](pages.md) | Application pages and routing |
| [Components](components.md) | Reusable UI components |
| [Internationalization](internationalization.md) | FR/EN translations and locale routing |

## Quick Commands

```bash
# Development (Docker)
docker-compose up frontend

# Development (Local)
cd frontend
pnpm install
pnpm dev

# Build for production
pnpm build

# Type checking
pnpm type-check

# Linting
pnpm lint
```

## Key Features

### Server Components

Next.js 14 uses React Server Components by default:

- Reduced client-side JavaScript
- Better initial page load
- Direct database access (not used, API-based)

### Client Components

Interactive components are marked with `"use client"`:

```tsx
"use client";

import { useState } from 'react';

export function InteractiveComponent() {
  const [state, setState] = useState(false);
  // ...
}
```

### Data Fetching

Uses React Query for client-side data fetching:

```tsx
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

function PropertyList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['properties'],
    queryFn: () => api.get('/properties'),
  });
  // ...
}
```

## Development

### Environment Variables

Create `frontend/.env.local` (see `.env.local.example`):

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
DATABASE_URL=postgresql://appart:appart@localhost:5432/appart_agent
BETTER_AUTH_SECRET=your-secret-at-least-32-chars
```

### Hot Reload

Development server includes Fast Refresh:

- Component changes update instantly
- State is preserved when possible
- Errors show inline

### Styling

Using Tailwind CSS with custom configuration:

```tsx
<div className="flex items-center justify-between p-4 bg-white rounded-lg shadow">
  <h2 className="text-lg font-semibold text-gray-900">Title</h2>
  <button className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700">
    Action
  </button>
</div>
```
