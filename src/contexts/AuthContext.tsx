"use client";

import { createContext, useContext, useState, useEffect } from "react";
import { siteConfig } from "@/config/site";
import Cookies from "js-cookie";

type User = {
  username: string;
  role: "user" | "admin";
};

type AuthContextType = {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isAdminMode: boolean;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Set cookie for 7 days
const COOKIE_EXPIRY = 7;

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
          setUser({ username: "admin", role: "admin" });
          setIsAuthenticated(true);
          return;
        }

        // Try to get auth from cookies first
        const cookieAuth = Cookies.get("ydrp_auth");
        if (cookieAuth) {
          try {
            const parsedAuth = JSON.parse(cookieAuth);
            setUser(parsedAuth.user);
            setIsAuthenticated(true);
            return;
          } catch (e) {
            console.error("Error parsing auth cookie:", e);
            // If cookie parse fails, try localStorage as fallback
          }
        }

        // Fallback to localStorage
        const savedAuth = localStorage.getItem("ydrp_auth");
        if (savedAuth) {
          const parsedAuth = JSON.parse(savedAuth);
          setUser(parsedAuth.user);
          setIsAuthenticated(true);

          // Sync cookie with localStorage if cookie wasn't found
          if (!cookieAuth) {
            Cookies.set("ydrp_auth", savedAuth, { expires: COOKIE_EXPIRY });
          }
        }
      } catch (err) {
        console.error("Error restoring auth state:", err);
        // Clear all auth data
        localStorage.removeItem("ydrp_auth");
        Cookies.remove("ydrp_auth");
      }
    };

    checkAuth();
  }, [isAdminMode]);

  // Mock login function
  const login = async (username: string, password: string) => {
    setIsLoading(true);
    setError(null);

    try {
      // Simulate API call delay
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // In a real app, this would validate against a backend
      if (password.length < 6) {
        throw new Error("Invalid credentials. Please try again.");
      }

      // Mock successful login
      const userData: User = {
        username,
        role: username === "admin" ? "admin" : "user",
      };

      // Create auth data object
      const authData = JSON.stringify({
        user: userData,
        token: "mock-jwt-token",
      });

      // Save to both localStorage and cookies
      localStorage.setItem("ydrp_auth", authData);
      Cookies.set("ydrp_auth", authData, { expires: COOKIE_EXPIRY });

      setUser(userData);
      setIsAuthenticated(true);
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

  // Logout function
  const logout = () => {
    localStorage.removeItem("ydrp_auth");
    Cookies.remove("ydrp_auth");
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
