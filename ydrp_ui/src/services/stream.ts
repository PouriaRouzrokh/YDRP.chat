import {
  ChatMessageRequest,
  ErrorChunk,
  StatusChunk,
  StreamChunk,
} from "@/types";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import { authService } from "./auth";
import { siteConfig } from "@/config/site";

/**
 * Stream service for interacting with the backend SSE streaming endpoint
 */
export const streamService = {
  /**
   * Stream a chat message response from the backend
   */
  async streamChatResponse(
    request: ChatMessageRequest,
    onChunk: (chunk: StreamChunk) => void
  ): Promise<void> {
    // Validate request
    if (!request.message.trim()) {
      const errorChunk: ErrorChunk = {
        type: "error",
        data: {
          message: "Message cannot be empty",
        },
      };
      onChunk(errorChunk);
      return;
    }

    // Check authentication
    if (!authService.isAuthenticated() && !siteConfig.settings.adminMode) {
      const errorChunk: ErrorChunk = {
        type: "error",
        data: {
          message: "User not authenticated",
        },
      };
      onChunk(errorChunk);
      return;
    }

    const token = authService.getToken();
    const url = `${siteConfig.api.baseUrl}${siteConfig.api.endpoints.chatStream}`;

    // Get user ID from auth context or default to 0 in admin mode
    const user = authService.getCurrentUser();
    const userId = user?.id || 0;

    try {
      // Prepare the request body
      const requestBody = {
        user_id: userId,
        message: request.message,
        chat_id: request.chat_id || null,
      };

      let controller: AbortController | null = new AbortController();

      await fetchEventSource(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(requestBody),
        signal: controller.signal,

        async onopen(response) {
          if (response.ok) {
            return; // Connection established successfully
          } else if (response.status === 401) {
            // Unauthorized - token expired
            console.log("Token expired or invalid, redirecting to login");
            // Clear authentication state
            authService.logout();

            // Send error to UI
            const errorChunk: ErrorChunk = {
              type: "error",
              data: {
                message: "Your session has expired. Please log in again.",
              },
            };
            onChunk(errorChunk);

            // Abort the current request
            controller?.abort();

            // Redirect to login page
            window.location.href = "/login?expired=true";
          } else if (
            response.status >= 400 &&
            response.status < 500 &&
            response.status !== 429
          ) {
            // Client-side error
            const errorData = await response.json();
            const errorChunk: ErrorChunk = {
              type: "error",
              data: {
                message:
                  errorData.detail ||
                  `Error ${response.status}: ${response.statusText}`,
              },
            };
            onChunk(errorChunk);
            controller?.abort();
          } else {
            // Server-side error or rate limiting
            const errorChunk: ErrorChunk = {
              type: "error",
              data: {
                message: `Error ${response.status}: ${response.statusText}`,
              },
            };
            onChunk(errorChunk);
            controller?.abort();
          }
        },

        onmessage(event) {
          // Process each message event from the stream
          try {
            // Skip empty data events (heartbeats)
            if (!event.data || event.data === "{") {
              return; // Just a heartbeat, ignore
            }

            // Parse the data as a StreamChunk
            const chunk = JSON.parse(event.data) as StreamChunk;
            onChunk(chunk);
          } catch (e) {
            // Failed to parse JSON
            console.warn("Invalid SSE message format:", e);
            console.warn("Raw message:", event.data);
          }
        },

        onclose() {
          // Connection closed by the server
          if (controller) {
            // Only send if we didn't already complete
            const statusChunk: StatusChunk = {
              type: "status",
              data: {
                status: "complete",
                chat_id: request.chat_id || 0,
              },
            };
            onChunk(statusChunk);
            controller = null;
          }
        },

        onerror(error) {
          // Connection error
          console.error("SSE connection error:", error);
          const errorChunk: ErrorChunk = {
            type: "error",
            data: {
              message:
                error instanceof Error ? error.message : "Connection error",
            },
          };
          onChunk(errorChunk);

          // Abort the connection on error
          controller?.abort();
          controller = null;

          // Return undefined to not retry on error
          return undefined;
        },
        
        // Set a reasonable behavior for the SSE connection
        openWhenHidden: true,
      });
    } catch (error) {
      // Handle any errors
      console.error("Stream error:", error);
      const errorChunk: ErrorChunk = {
        type: "error",
        data: {
          message:
            error instanceof Error
              ? error.message
              : "An unknown error occurred",
        },
      };
      onChunk(errorChunk);
    }
  },
};
