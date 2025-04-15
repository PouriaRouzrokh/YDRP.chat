import { Chat, ChatMessage, ChatSummary, MessageSummary } from "@/types";
import { authService } from "./auth";
import { siteConfig } from "@/config/site";

// Mock chat data
const MOCK_CHATS: ChatSummary[] = [
  {
    id: 1,
    title: "Radiation Safety Protocols",
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), // 1 day ago
    updated_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 minutes ago
  },
  {
    id: 2,
    title: "Patient Privacy Guidelines",
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(), // 2 days ago
    updated_at: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(), // 3 hours ago
  },
  {
    id: 3,
    title: "Equipment Maintenance Procedures",
    created_at: new Date(Date.now() - 1000 * 60 * 60 * 72).toISOString(), // 3 days ago
    updated_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), // 1 day ago
  },
];

// Mock messages for each chat
const MOCK_MESSAGES: Record<number, MessageSummary[]> = {
  1: [
    {
      id: 1,
      role: "user",
      content: "What are the radiation safety protocols for pregnant staff?",
      created_at: new Date(Date.now() - 1000 * 60 * 35).toISOString(), // 35 minutes ago
    },
    {
      id: 2,
      role: "assistant",
      content:
        "According to the Yale Department of Radiology Policy on Radiation Safety (Policy ID: RAD-SAF-001), pregnant staff members should follow these guidelines:\n\n1. Report pregnancy to Radiation Safety Officer\n2. Wear dosimeter at waist level under lead apron\n3. Limit fluoroscopy procedures when possible\n4. Maintain distance from radiation sources when not directly involved\n\nThe maximum dose limit for pregnant staff is 5 mSv for the entire pregnancy or 0.5 mSv per month.",
      created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(), // 30 minutes ago
    },
  ],
  2: [
    {
      id: 3,
      role: "user",
      content:
        "What are the requirements for sharing patient imaging with outside institutions?",
      created_at: new Date(Date.now() - 1000 * 60 * 60 * 4).toISOString(), // 4 hours ago
    },
    {
      id: 4,
      role: "assistant",
      content:
        "According to the Yale Department of Radiology Policy on Patient Data Privacy (Policy ID: RAD-PRV-002), sharing imaging with outside institutions requires:\n\n1. Signed patient authorization form\n2. Verification of requesting institution's credentials\n3. Secure transfer method (approved DICOM exchange or encrypted media)\n4. Documentation of the transfer in the patient's record\n\nEmergency exceptions exist for urgent patient care situations, but still require documentation after the fact.",
      created_at: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(), // 3 hours ago
    },
  ],
  3: [
    {
      id: 5,
      role: "user",
      content: "What is the MRI maintenance schedule?",
      created_at: new Date(Date.now() - 1000 * 60 * 60 * 25).toISOString(), // 25 hours ago
    },
    {
      id: 6,
      role: "assistant",
      content:
        "According to the Yale Department of Radiology Equipment Maintenance Policy (Policy ID: RAD-EQP-003), MRI scanners must undergo:\n\n1. Daily: Quality assurance phantom scan before first patient\n2. Weekly: SNR and image quality tests by MRI technologists\n3. Monthly: Comprehensive performance evaluation by medical physics\n4. Quarterly: Preventative maintenance by vendor service engineers\n5. Annually: Full calibration and safety inspection\n\nAny issues identified must be documented and reported to the chief MRI technologist immediately.",
      created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(), // 24 hours ago
    },
  ],
};

// Export for use in other services
export { MOCK_CHATS };

// Helper function to simulate network delay
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Mock chat service
 */
export const chatService = {
  /**
   * Get chat history for the current user
   */
  async getChats(skip = 0, limit = 10): Promise<ChatSummary[]> {
    // Check if admin mode is enabled
    const isAdminMode = siteConfig.settings.adminMode;

    // Skip authentication check if admin mode is enabled
    if (!isAdminMode && !authService.isAuthenticated()) {
      throw new Error("User not authenticated");
    }

    // Simulate network delay
    await delay(500);

    // Return paginated chats
    return MOCK_CHATS.slice(skip, skip + limit);
  },

  /**
   * Get messages for a specific chat
   */
  async getChatMessages(
    chatId: number,
    skip = 0,
    limit = 100
  ): Promise<MessageSummary[]> {
    // Check if admin mode is enabled
    const isAdminMode = siteConfig.settings.adminMode;

    // Skip authentication check if admin mode is enabled
    if (!isAdminMode && !authService.isAuthenticated()) {
      throw new Error("User not authenticated");
    }

    // Simulate network delay
    await delay(700);

    // Check if chat exists
    const messages = MOCK_MESSAGES[chatId];
    if (!messages) {
      throw new Error("Chat not found");
    }

    // Return paginated messages
    return messages.slice(skip, skip + limit);
  },

  /**
   * Convert API chat summaries to UI chat format
   */
  formatChatsForUI(chats: ChatSummary[]): Chat[] {
    return chats.map((chat) => ({
      id: chat.id,
      title: chat.title ?? "Untitled Chat",
      lastMessageTime: new Date(chat.updated_at),
      messageCount: (MOCK_MESSAGES[chat.id] || []).length,
    }));
  },

  /**
   * Convert API messages to UI message format
   */
  formatMessagesForUI(messages: MessageSummary[]): ChatMessage[] {
    return messages.map((message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      timestamp: new Date(message.created_at),
    }));
  },
};
