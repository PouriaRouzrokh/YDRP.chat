import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { ChatSummary, MessageSummary } from "@/types";

/**
 * Combines class names with Tailwind's merge utility
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a date from ISO string to a human-readable format
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;

  // Check if the date is today
  const today = new Date();
  if (d.toDateString() === today.toDateString()) {
    return `Today at ${d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  }

  // Check if the date is yesterday
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) {
    return `Yesterday at ${d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    })}`;
  }

  // Otherwise, show the full date
  return d.toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: d.getFullYear() !== today.getFullYear() ? "numeric" : undefined,
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Transform API chat summaries to a UI-friendly format
 */
export function formatChatsForUI(chats: ChatSummary[]) {
  return chats.map((chat) => ({
    id: chat.id.toString(),
    title: chat.title || "New Chat",
    createdAt: formatDate(chat.created_at),
  }));
}

/**
 * Transform API messages to a UI-friendly format
 */
export function formatMessagesForUI(messages: MessageSummary[]) {
  return messages.map((message) => ({
    id: message.id.toString(),
    role: message.role,
    content: message.content,
    createdAt: formatDate(message.created_at),
  }));
}

/**
 * Create a truncated version of text with maximum length
 */
export function truncateText(text: string, maxLength: number = 50): string {
  if (text.length <= maxLength) return text;
  return `${text.substring(0, maxLength)}...`;
}

/**
 * Parse streaming chunks to rebuild a full message
 */
export function parseStreamContent(chunks: string[]): string {
  return chunks.join("");
}

/**
 * Generate a random ID (for mock data)
 */
export function generateId(): string {
  return Math.random().toString(36).substring(2, 12);
}
