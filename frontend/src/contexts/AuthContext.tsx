"use client";

import React, { createContext, useContext, useCallback, useMemo, useEffect, useState, useRef } from 'react';
import { useRouter } from '@/i18n/navigation';
import { api } from '@/lib/api';
import type { User, LoginRequest, RegisterRequest } from '@/types';

interface BetterAuthSession {
  user: {
    id: string;
    email: string;
    name?: string;
  } | null;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  loginWithGoogle: () => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Dynamically import auth-client to avoid SSR issues
const getAuthClient = async () => {
  const { signIn, signUp, signOut, getSession } = await import('@/lib/auth-client');
  return { signIn, signUp, signOut, getSession };
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [session, setSession] = useState<BetterAuthSession | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [backendUser, setBackendUser] = useState<User | null>(null);
  const [backendLoading, setBackendLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  const authClientRef = useRef<Awaited<ReturnType<typeof getAuthClient>> | null>(null);

  // Initialize auth client on mount
  useEffect(() => {
    setMounted(true);

    const init = async () => {
      try {
        authClientRef.current = await getAuthClient();
        const result = await authClientRef.current.getSession();
        setSession(result.data);
      } catch (error) {
        console.error('Failed to initialize auth:', error);
        setSession(null);
      } finally {
        setSessionLoading(false);
      }
    };

    init();
  }, []);

  // Fetch backend user data when session changes
  useEffect(() => {
    const fetchBackendUser = async () => {
      if (session?.user) {
        setBackendLoading(true);
        try {
          const response = await api.get('/api/users/me');
          setBackendUser(response.data);
        } catch (error) {
          console.error('Failed to fetch backend user:', error);
          setBackendUser(null);
        } finally {
          setBackendLoading(false);
        }
      } else {
        setBackendUser(null);
      }
    };

    if (mounted && !sessionLoading) {
      fetchBackendUser();
    }
  }, [session?.user?.id, sessionLoading, mounted]);

  // Map Better Auth session to legacy User type for backward compatibility
  const user: User | null = useMemo(() => {
    if (!session?.user) return null;

    // Prefer backend user data if available (has more fields like documents_analyzed_count)
    if (backendUser) return backendUser;

    // Fallback to session data mapped to User type
    return {
      id: 0, // Will be fetched from backend
      email: session.user.email,
      full_name: session.user.name || '',
      is_active: true,
    };
  }, [session?.user, backendUser]);

  const refreshSession = useCallback(async () => {
    if (!authClientRef.current) return;
    try {
      const result = await authClientRef.current.getSession();
      setSession(result.data);
    } catch (error) {
      console.error('Failed to refresh session:', error);
      setSession(null);
    }
  }, []);

  const login = useCallback(async (credentials: LoginRequest) => {
    if (!authClientRef.current) {
      authClientRef.current = await getAuthClient();
    }

    const result = await authClientRef.current.signIn.email({
      email: credentials.email,
      password: credentials.password,
    });

    if (result.error) {
      throw new Error(result.error.message || 'Login failed');
    }

    await refreshSession();
    router.push('/dashboard');
  }, [router, refreshSession]);

  const loginWithGoogle = useCallback(async () => {
    if (!authClientRef.current) {
      authClientRef.current = await getAuthClient();
    }

    await authClientRef.current.signIn.social({
      provider: "google",
      callbackURL: "/dashboard",
    });
  }, []);

  const register = useCallback(async (data: RegisterRequest) => {
    if (!authClientRef.current) {
      authClientRef.current = await getAuthClient();
    }

    const result = await authClientRef.current.signUp.email({
      email: data.email,
      password: data.password,
      name: data.full_name,
    });

    if (result.error) {
      throw new Error(result.error.message || 'Registration failed');
    }

    await refreshSession();
    router.push('/dashboard');
  }, [router, refreshSession]);

  const logout = useCallback(async () => {
    if (!authClientRef.current) {
      authClientRef.current = await getAuthClient();
    }

    await authClientRef.current.signOut();
    setSession(null);
    setBackendUser(null);
    router.push('/');
  }, [router]);

  const loading = sessionLoading || backendLoading;

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        loginWithGoogle,
        register,
        logout,
        isAuthenticated: !!session?.user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
