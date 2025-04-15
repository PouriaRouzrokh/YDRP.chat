import { AuthResponse, ErrorResponse, User } from "@/types";

// Mock user data
const MOCK_USERS = [
  {
    id: 1,
    email: "admin@example.com",
    password: "password123",
    full_name: "Admin User",
    is_admin: true,
  },
  {
    id: 2,
    email: "user@example.com",
    password: "password123",
    full_name: "Regular User",
    is_admin: false,
  },
];

// Token storage key
const TOKEN_KEY = "ydrp_auth_token";
const USER_KEY = "ydrp_user";

// Helper function to simulate network delay
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Mock authentication service
 */
export const authService = {
  /**
   * Login user with email and password
   */
  async login(email: string, password: string): Promise<AuthResponse> {
    // Simulate network delay
    await delay(800);

    // Find user
    const user = MOCK_USERS.find(
      (u) => u.email === email && u.password === password
    );

    if (!user) {
      const error: ErrorResponse = {
        detail: "Incorrect email or password",
      };
      throw new Error(JSON.stringify(error));
    }

    // Create a mock token (in a real app, this would be a JWT)
    const token = `mock_token_${user.id}_${Date.now()}`;

    // Store user data and token
    localStorage.setItem(
      USER_KEY,
      JSON.stringify({
        id: user.id,
        email: user.email,
        full_name: user.full_name,
        is_admin: user.is_admin,
      })
    );
    localStorage.setItem(TOKEN_KEY, token);

    // Return mock auth response
    return {
      access_token: token,
      token_type: "bearer",
    };
  },

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return !!localStorage.getItem(TOKEN_KEY);
  },

  /**
   * Get current user
   */
  getCurrentUser(): User | null {
    const userData = localStorage.getItem(USER_KEY);
    if (!userData) return null;
    return JSON.parse(userData) as User;
  },

  /**
   * Logout user
   */
  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  /**
   * Get auth token
   */
  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },
};
