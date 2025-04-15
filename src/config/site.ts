export const siteConfig = {
  name: "YDR Policy Chatbot",
  description: "A chatbot for Yale Radiology policies",

  // API URLs (placeholder values)
  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    endpoints: {
      chat: "/chat",
      chatStream: "/chat/stream",
      history: "/history",
      auth: "/auth",
    },
  },

  // Application settings
  settings: {
    // Control admin mode via environment variable: NEXT_PUBLIC_ADMIN_MODE="true"
    // When enabled, login will be bypassed entirely
    adminMode: process.env.NEXT_PUBLIC_ADMIN_MODE === "true",
    defaultTheme: "light",
  },

  // Navigation links
  navigation: [
    { name: "Chat", href: "/chat" },
    { name: "History", href: "/history" },
    { name: "About", href: "/about" },
  ],

  // Support info
  support: {
    email: "it-support@yale-rad.edu",
    phone: "+1 (203) 555-1234",
  },
};
