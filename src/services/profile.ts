import { ChatSummary, User } from "@/types";
import { authService } from "./auth";
import { chatService } from "./chat";
import { siteConfig } from "@/config/site";

/**
 * Mock profile service for user profile data
 */
export const profileService = {
  /**
   * Get user profile information including conversation statistics
   */
  async getUserProfile(): Promise<{
    user: User;
    totalConversations: number;
    lastConversationDate: Date | null;
  }> {
    // Check for admin mode
    const isAdminMode = siteConfig.settings.adminMode;

    // If admin mode is enabled, return mock admin user
    if (isAdminMode) {
      const mockAdminUser: User = {
        id: 0,
        email: "admin@example.com",
        full_name: "Admin User",
        is_admin: true,
      };

      // Get conversation stats using the chat service
      const chats = await chatService.getChats(0, 100);
      const totalConversations = chats.length;

      // Find the most recent conversation date
      const dates = chats.map((chat: ChatSummary) => new Date(chat.updated_at));
      const lastConversationDate =
        dates.length > 0
          ? new Date(Math.max(...dates.map((date: Date) => date.getTime())))
          : null;

      return {
        user: mockAdminUser,
        totalConversations,
        lastConversationDate,
      };
    }

    // Regular auth flow for non-admin mode
    const user = authService.getCurrentUser();

    if (!user) {
      throw new Error("User not authenticated");
    }

    // Get conversation stats using the chat service
    const chats = await chatService.getChats(0, 100);
    const totalConversations = chats.length;

    // Find the most recent conversation date
    const dates = chats.map((chat: ChatSummary) => new Date(chat.updated_at));
    const lastConversationDate =
      dates.length > 0
        ? new Date(Math.max(...dates.map((date: Date) => date.getTime())))
        : null;

    return {
      user,
      totalConversations,
      lastConversationDate,
    };
  },
};
