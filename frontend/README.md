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

Create a `.env.local` file:

```bash
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

For production, set this to your deployed backend URL.

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

```
src/
├── app/                    # Next.js App Router pages
│   ├── dashboard/          # Main dashboard
│   ├── properties/         # Property management
│   │   └── [id]/
│   │       ├── documents/  # Document upload & analysis
│   │       └── photos/     # Photo redesign studio
│   ├── login/              # Authentication
│   └── register/
├── components/             # Reusable components
│   ├── Header.tsx          # Navigation header
│   ├── ProtectedRoute.tsx  # Auth guard
│   └── MarketTrendChart.tsx
├── contexts/               # React contexts
│   └── AuthContext.tsx     # Authentication state
├── lib/                    # Utilities
│   └── api.ts              # Axios instance & interceptors
└── types/                  # TypeScript definitions
    └── index.ts
```

## Key Pages

| Route | Description |
|-------|-------------|
| `/dashboard` | Overview with stats and property list |
| `/properties/new` | Create new property |
| `/properties/[id]` | Property details |
| `/properties/[id]/documents` | Document management with AI analysis |
| `/properties/[id]/photos` | Photo redesign studio |

## Authentication

The app uses JWT tokens for authentication:

1. Tokens are stored in localStorage
2. `AuthContext` manages auth state globally
3. `ProtectedRoute` component guards authenticated pages
4. Axios interceptors automatically attach tokens to requests

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
