export interface User {
  id: string;
  name: string;
  email: string;
}

export interface Message {
  id: string;
  content: string;
  role: "user" | "assistant";
  timestamp: string;
  policyReferences?: PolicyReference[];
}

export interface PolicyReference {
  id: string;
  title: string;
  content: string;
  url?: string;
}

export interface Chat {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: Message[];
}
