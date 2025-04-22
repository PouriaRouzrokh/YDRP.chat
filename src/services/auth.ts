import { AuthResponse, ErrorResponse, User } from "@/types";
import { siteConfig } from "@/config/site";
import Cookies from "js-cookie";
import { apiClient } from "./api-client";

// Token storage key
const TOKEN_KEY = "ydrp_auth_token";
const USER_KEY = "ydrp_user";

/**
 * Authentication service for interacting with the backend auth API
 */
export const authService = {
  /**
   * Login user with email and password
   */
  async login(email: string, password: string): Promise<AuthResponse> {
    const url = `${siteConfig.api.baseUrl}${siteConfig.api.endpoints.auth}/token`;

    // Create form data for OAuth2 password flow
    const formData = new URLSearchParams();
    formData.append("username", email); // Backend expects email in the username field
    formData.append("password", password);

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData: ErrorResponse = await response.json();
        throw new Error(errorData.detail || "Authentication failed");
      }

      const data: AuthResponse = await response.json();

      // Store the token in localStorage
      localStorage.setItem(TOKEN_KEY, data.access_token);

      // Also store token in a cookie for middleware auth check
      Cookies.set(TOKEN_KEY, data.access_token, {
        expires: 7, // 7 days
        path: "/",
      });

      // Fetch user info after successful login
      await this.fetchUserInfo();

      return data;
    } catch (error) {
      console.error("Login error:", error);
      throw error;
    }
  },

  /**
   * Fetch current user information
   */
  async fetchUserInfo(): Promise<User> {
    if (!this.isAuthenticated()) {
      throw new Error("Not authenticated");
    }

    const url = `${siteConfig.api.baseUrl}${siteConfig.api.endpoints.auth}/users/me`;

    try {
      // Use apiClient to handle 401 errors automatically
      const userData = await apiClient.fetch<User>(url);

      // Save user data to localStorage
      localStorage.setItem(USER_KEY, JSON.stringify(userData));

      return userData;
    } catch (error) {
      console.error("Error fetching user info:", error);
      throw error;
    }
  },

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return !!this.getToken();
  },

  /**
   * Get current user
   */
  getCurrentUser(): User | null {
    const userData = localStorage.getItem(USER_KEY);
    if (!userData) return null;
    try {
      return JSON.parse(userData) as User;
    } catch (e) {
      console.error("Error parsing user data:", e);
      return null;
    }
  },

  /**
   * Logout user
   */
  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);

    // Also remove the cookie
    Cookies.remove(TOKEN_KEY, { path: "/" });
  },

  /**
   * Get auth token
   */
  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },
};
