"use client";

import { createContext, useContext, useState, useEffect } from "react";
import { siteConfig } from "@/config/site";
import { User } from "@/types";
import { authService } from "@/services/auth";

type AuthContextType = {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isAdminMode: boolean;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);

  // Check if admin mode is enabled
  const isAdminMode = siteConfig.settings.adminMode;

  // Check for saved auth on startup
  useEffect(() => {
    const checkAuth = () => {
      try {
        // Skip auth check if admin mode is enabled
        if (isAdminMode) {
          console.log("Admin mode enabled, setting mock user");
          // Create mock admin user that matches User type
          setUser({
            id: 0,
            email: "admin@example.com",
            full_name: "Admin User",
            is_admin: true,
          });
          setIsAuthenticated(true);
          return;
        }

        // Check if user is authenticated with authService
        if (authService.isAuthenticated()) {
          console.log("User authenticated via authService");
          const currentUser = authService.getCurrentUser();
          console.log("Current user:", currentUser);
          if (currentUser) {
            setUser(currentUser);
            setIsAuthenticated(true);
          }
        } else {
          console.log("No authenticated user found");
        }
      } catch (err) {
        console.error("Error restoring auth state:", err);
      }
    };

    checkAuth();
  }, [isAdminMode]);

  // Login function using authService
  const login = async (email: string, password: string) => {
    setIsLoading(true);
    setError(null);

    try {
      await authService.login(email, password);
      const currentUser = authService.getCurrentUser();
      if (currentUser) {
        setUser(currentUser);
        setIsAuthenticated(true);
      }
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unknown error occurred");
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Logout function using authService
  const logout = () => {
    authService.logout();
    setUser(null);
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        error,
        login,
        logout,
        isAuthenticated,
        isAdminMode,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
