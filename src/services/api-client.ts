import { authService } from "./auth";

/**
 * API client that handles common API interaction patterns
 * including authentication error handling and redirects
 */
export const apiClient = {
  /**
   * Make an authenticated API request with token expiry handling
   */
  async fetch<T>(url: string, options: RequestInit = {}): Promise<T> {
    // Get the auth token
    const token = authService.getToken();

    // Create headers with authentication
    const headers = {
      ...options.headers,
      Authorization: token ? `Bearer ${token}` : "",
    };

    try {
      // Make the request
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Handle 401 Unauthorized errors (expired token)
      if (response.status === 401) {
        console.log("Token expired or invalid, redirecting to login");
        // Clear authentication state
        authService.logout();
        // Redirect to login page with expired parameter
        window.location.href = "/login?expired=true";
        throw new Error("Authentication failed. Please log in again.");
      }

      // Handle other error responses
      if (!response.ok) {
        // Try to parse error details
        let errorMessage = `Error ${response.status}: ${response.statusText}`;

        // Only try to parse JSON if there's a response body
        if (response.headers.get("content-length") !== "0") {
          try {
            const errorData = await response.json();
            if (errorData.detail) {
              errorMessage = errorData.detail;
            }
          } catch {
            // Ignore JSON parsing errors - no variable declared
          }
        }

        throw new Error(errorMessage);
      }

      // Return the JSON response
      return (await response.json()) as T;
    } catch (error) {
      // Re-throw the error for the caller to handle
      console.error("API request failed:", error);
      throw error;
    }
  },
};
