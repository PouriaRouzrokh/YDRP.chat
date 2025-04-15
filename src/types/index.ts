// Authentication types
export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface ErrorResponse {
  detail: string;
}

// Chat types
export interface ChatSummary {
  id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
}

export interface MessageSummary {
  id: number;
  role: MessageRole;
  content: string;
  created_at: string;
}

export type MessageRole = "user" | "assistant";

// Request types
export interface ChatMessageRequest {
  chat_id?: number;
  message: string;
}

// Stream types
export type StreamChunkType =
  | "chat_info"
  | "text_delta"
  | "tool_call"
  | "tool_output"
  | "error"
  | "status";

export interface BaseChunk {
  type: StreamChunkType;
}

export interface StreamChunk<T = unknown> extends BaseChunk {
  data: T;
}

export interface ChatInfoChunk {
  type: "chat_info";
  data: {
    chat_id: number;
    title: string | null;
  };
}

export interface TextDeltaChunk {
  type: "text_delta";
  data: {
    delta: string;
  };
}

export interface ToolCallChunk {
  type: "tool_call";
  data: {
    id: string;
    name: string;
    input: Record<string, unknown>;
  };
}

export interface ToolOutputChunk {
  type: "tool_output";
  data: {
    tool_call_id: string;
    output: unknown;
  };
}

export interface ErrorChunk {
  type: "error";
  data: {
    message: string;
  };
}

export interface StatusChunk {
  type: "status";
  data: {
    status: "complete" | "error";
    chat_id: number;
  };
}

// Simplified types for UI
export interface User {
  id: number;
  email: string;
  full_name: string;
  is_admin: boolean;
}

export interface ChatMessage {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  isLoading?: boolean;
}

export interface Chat {
  id: number | string;
  title: string;
  lastMessageTime: Date;
  messageCount: number;
  isArchived?: boolean;
}

// Tool-related Types
export interface Policy {
  id: string;
  title: string;
  content: string;
}

export interface PolicySearchResult {
  query: string;
  results: Policy[];
}
