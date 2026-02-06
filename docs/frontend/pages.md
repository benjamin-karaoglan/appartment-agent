# Pages & Routes

AppArt Agent uses Next.js 14 App Router for file-based routing. All pages are under the `[locale]` dynamic segment (`/fr/...` or `/en/...`) for internationalization.

## Route Structure

```text
/[locale]                         # Landing page (/fr, /en)
├── /auth
│   ├── /login                    # Login form
│   └── /register                 # Registration form
├── /dashboard                    # Main dashboard (protected)
└── /properties
    ├── /new                      # Create property (protected)
    └── /[id]                     # Property detail (protected)
        ├── /documents            # Document management
        ├── /photos               # Photo management
        └── /redesign-studio      # Photo redesign
```

## Pages

### Landing Page (`/[locale]`)

**File**: `src/app/[locale]/page.tsx`

Public landing page with:

- Hero section
- Feature highlights
- Call-to-action buttons

### Authentication

#### Login (`/[locale]/auth/login`)

**File**: `src/app/[locale]/auth/login/page.tsx`

- Email/password form (via Better Auth)
- Optional Google OAuth sign-in
- Session cookie set on success
- Redirect to dashboard on success

#### Register (`/[locale]/auth/register`)

**File**: `src/app/[locale]/auth/register/page.tsx`

- Registration form (via Better Auth)
- Email validation
- Auto-login after registration

### Dashboard (`/[locale]/dashboard`)

**File**: `src/app/[locale]/dashboard/page.tsx`

Protected route showing:

- Property list
- Quick stats
- Recent activity
- Create property button

### Properties

#### New Property (`/[locale]/properties/new`)

**File**: `src/app/[locale]/properties/new/page.tsx`

Property creation form:

- Address input
- Price and surface area
- Property type selection

#### Property Detail (`/[locale]/properties/[id]`)

**File**: `src/app/[locale]/properties/[id]/page.tsx`

Property overview with:

- Property information
- Price analysis results
- Market trend chart
- Document summary
- Navigation to sub-pages

```tsx
// Dynamic route parameter
export default function PropertyPage({
  params
}: {
  params: { id: string }
}) {
  const propertyId = params.id;
  // ...
}
```

#### Documents (`/[locale]/properties/[id]/documents`)

**File**: `src/app/[locale]/properties/[id]/documents/page.tsx`

Document management:

- Bulk upload dropzone
- Document list with status
- Classification results
- Analysis viewer
- Synthesis summary

```tsx
// Document upload state
const [uploading, setUploading] = useState(false);
const [progress, setProgress] = useState<BulkUploadProgress | null>(null);

// Upload handler
const handleUpload = async (files: FileList) => {
  setUploading(true);
  const result = await api.bulkUpload(propertyId, files);
  pollStatus(result.workflow_id);
};
```

#### Photos (`/[locale]/properties/[id]/photos`)

**File**: `src/app/[locale]/properties/[id]/photos/page.tsx`

Photo management:

- Photo upload
- Gallery view
- Room type tagging
- Link to redesign studio

#### Redesign Studio (`/[locale]/properties/[id]/redesign-studio`)

**File**: `src/app/[locale]/properties/[id]/redesign-studio/page.tsx`

AI-powered photo redesign:

- Photo selection
- Style chooser
- Preference configuration
- Before/after comparison
- Redesign history

```tsx
// Redesign request
const requestRedesign = async (photoId: number, style: string) => {
  const result = await api.post(`/photos/${photoId}/redesign`, {
    style,
    preferences: selectedPreferences
  });
  setRedesignId(result.redesign_id);
  pollRedesignStatus(result.redesign_id);
};
```

## Protected Routes

Routes under `/[locale]/dashboard` and `/[locale]/properties` require authentication.

### ProtectedRoute Component

```tsx
// src/components/ProtectedRoute.tsx
"use client";

import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push('/auth/login');
    }
  }, [user, loading, router]);

  if (loading) {
    return <LoadingSpinner />;
  }

  if (!user) {
    return null;
  }

  return <>{children}</>;
}
```

### Usage in Layout

```tsx
// src/app/[locale]/dashboard/layout.tsx
import { ProtectedRoute } from '@/components/ProtectedRoute';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute>
      <Header />
      <main className="container mx-auto px-4 py-8">
        {children}
      </main>
    </ProtectedRoute>
  );
}
```

## Route Navigation

Use locale-aware navigation from `@/i18n/navigation` instead of standard Next.js imports. This automatically includes the current locale in URLs.

### Link Component

```tsx
import { Link } from '@/i18n/navigation';

<Link
  href={`/properties/${property.id}`}
  className="text-indigo-600 hover:text-indigo-800"
>
  View Property
</Link>
// Renders: /fr/properties/123 or /en/properties/123
```

### Programmatic Navigation

```tsx
import { useRouter } from '@/i18n/navigation';

const router = useRouter();

// Navigate (locale is automatically included)
router.push('/dashboard');

// Switch locale without losing current path
router.replace(pathname, { locale: 'en' });

// Back
router.back();
```

## Loading States

Each route can have a `loading.tsx` file:

```tsx
// src/app/[locale]/properties/[id]/loading.tsx
export default function Loading() {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-gray-200 rounded w-1/4 mb-4" />
      <div className="h-64 bg-gray-200 rounded" />
    </div>
  );
}
```

## Error Handling

Each route can have an `error.tsx` file:

```tsx
// src/app/[locale]/properties/[id]/error.tsx
"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div className="text-center py-8">
      <h2 className="text-xl font-semibold text-red-600">
        Something went wrong
      </h2>
      <p className="text-gray-600 mt-2">{error.message}</p>
      <button
        onClick={reset}
        className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded"
      >
        Try again
      </button>
    </div>
  );
}
```

## Metadata

Dynamic metadata for SEO:

```tsx
// src/app/[locale]/properties/[id]/page.tsx
import { Metadata } from 'next';

export async function generateMetadata({
  params
}: {
  params: { id: string }
}): Promise<Metadata> {
  const property = await fetchProperty(params.id);

  return {
    title: `${property.address} | AppArt Agent`,
    description: `Property analysis for ${property.address}, ${property.city}`,
  };
}
```
