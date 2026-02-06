# AppArt Agent - Frontend

Modern Next.js frontend for the AppArt Agent real estate management platform.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **HTTP Client**: Axios
- **Charts**: Recharts

## Features

- **Property Management**: Create, view, and manage real estate properties
- **Document Analysis**: Upload and AI-analyze property documents (PV d'AG, diagnostics, tax documents)
- **Photo Redesign Studio**: AI-powered apartment redesign using Gemini 2.5 Flash
- **Market Analysis**: DVF (property sales) data visualization and trends
- **Dashboard**: Overview of properties, documents analyzed, and redesigns generated

## Getting Started

### Prerequisites

- Node.js 18+
- pnpm (recommended) or npm

### Installation

```bash
# Install dependencies
pnpm install

# Copy environment template
cp .env.example .env.local
```

### Environment Variables

Create a `.env.local` file (see `.env.local.example`):

```bash
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# App URL (for Better Auth callbacks)
NEXT_PUBLIC_APP_URL=http://localhost:3000

# Database (for Better Auth server-side session management)
DATABASE_URL=postgresql://appart:appart@localhost:5432/appart_agent

# Better Auth secret (generate with: openssl rand -hex 32)
BETTER_AUTH_SECRET=your-better-auth-secret-at-least-32-characters

# Google OAuth (optional - from Google Cloud Console)
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
```

For production, set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_APP_URL` to your deployed URLs.

### Development

```bash
# Start development server
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build

```bash
# Create production build
pnpm build

# Start production server
pnpm start
```

## Project Structure

```text
src/
├── app/
│   ├── [locale]/               # Locale-scoped pages (FR/EN)
│   │   ├── page.tsx            # Home page
│   │   ├── dashboard/          # Main dashboard
│   │   ├── properties/         # Property management
│   │   │   ├── new/            # Create property
│   │   │   └── [id]/
│   │   │       ├── documents/  # Document upload & analysis
│   │   │       └── photos/     # Photo redesign studio
│   │   └── auth/
│   │       ├── login/          # Login page
│   │       └── register/       # Registration page
│   ├── api/auth/[...all]/      # Better Auth API route handler
│   ├── layout.tsx              # Root layout
│   └── globals.css             # Global styles
├── components/                 # Reusable components
│   ├── Header.tsx              # Navigation header + locale switcher
│   ├── ProtectedRoute.tsx      # Auth guard
│   └── MarketTrendChart.tsx
├── contexts/
│   └── AuthContext.tsx          # Auth state (Better Auth sessions)
├── i18n/                        # Internationalization
│   ├── config.ts               # Locale definitions
│   ├── navigation.ts           # Locale-aware Link, useRouter
│   └── routing.ts              # Locale routing config
├── lib/
│   ├── api.ts                  # Axios instance & interceptors
│   ├── auth.ts                 # Better Auth server configuration
│   └── auth-client.ts          # Better Auth client (signIn, signUp, etc.)
├── middleware.ts                # next-intl locale middleware
└── types/
    └── index.ts
messages/                        # Translation files (at frontend root)
├── en.json
└── fr.json
```

## Key Pages

All pages are under the `[locale]` segment (e.g., `/fr/dashboard`, `/en/dashboard`).

| Route | Description |
|-------|-------------|
| `/[locale]/` | Home page |
| `/[locale]/dashboard` | Overview with stats and property list |
| `/[locale]/properties/new` | Create new property |
| `/[locale]/properties/[id]` | Property details with price analysis |
| `/[locale]/properties/[id]/documents` | Document management with AI analysis |
| `/[locale]/properties/[id]/photos` | Photo redesign studio |
| `/[locale]/auth/login` | Login (email/password + Google OAuth) |
| `/[locale]/auth/register` | Registration |

## Authentication

The app uses [Better Auth](https://www.better-auth.com/) for authentication:

1. **Email/Password**: Users can register and login with email/password
2. **Google OAuth**: One-click sign-in with Google accounts
3. **Session Management**: HTTP-only cookies (no localStorage tokens)
4. **API Route Handler**: `/api/auth/[...all]` handles all auth endpoints
5. `AuthContext` manages auth state globally via `getSession()`
6. `ProtectedRoute` component guards authenticated pages
7. The backend validates sessions by checking cookies against `ba_session` table

### Auth Architecture

```text
Frontend -> Next.js API Routes (/api/auth/*) -> PostgreSQL (ba_* tables)
         -> FastAPI (validates session cookie against ba_session table)
```

### Key Files

- `src/lib/auth.ts` - Better Auth server configuration
- `src/lib/auth-client.ts` - Better Auth client (signIn, signUp, signOut)
- `src/app/api/auth/[...all]/route.ts` - API route handler
- `src/contexts/AuthContext.tsx` - Auth state management

## Styling

- Tailwind CSS for utility-first styling
- Consistent color scheme: blue primary, purple for AI features
- Responsive design for mobile and desktop
- Dark mode compatible form inputs

## API Integration

All API calls go through the configured `NEXT_PUBLIC_API_URL`:

```typescript
import { api } from '@/lib/api';

// Example: Fetch properties
const response = await api.get('/api/properties/');

// Example: Upload document
const formData = new FormData();
formData.append('file', file);
await api.post('/api/documents/upload', formData);
```

## Docker

The frontend can be built as a Docker image:

```bash
docker build -t appart-frontend -f Dockerfile .
```

The Dockerfile uses a multi-stage build for optimal image size.

## Contributing

1. Follow the existing code style
2. Use TypeScript strictly (no `any` where avoidable)
3. Keep components small and focused
4. Use meaningful commit messages
