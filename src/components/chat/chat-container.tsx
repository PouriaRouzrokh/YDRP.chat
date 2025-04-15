import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MenuIcon } from "lucide-react";
import { ChatSidebar, ChatSession } from "./chat-sidebar";
import { ChatInput } from "./chat-input";
import { ChatMessage, Message, TypingIndicator } from "./message";
import { cn } from "@/lib/utils";
import { chatService } from "@/services/chat";
import { streamService } from "@/services/stream";
import { toast } from "sonner";
import {
  ChatInfoChunk,
  ChatMessageRequest,
  ErrorChunk,
  StatusChunk,
  StreamChunk,
  TextDeltaChunk,
} from "@/types";

interface ChatContainerProps {
  initialSessions?: ChatSession[];
  initialMessages?: Message[];
  onSendMessage?: (message: string) => void;
}

export function ChatContainer({
  initialSessions = [],
  initialMessages = [],
  onSendMessage,
}: ChatContainerProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sessions, setSessions] = useState<ChatSession[]>(initialSessions);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(
    initialSessions.length > 0 ? initialSessions[0].id : null
  );
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [isTyping, setIsTyping] = useState(false);
  const [currentMessage, setCurrentMessage] = useState<Message | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch chat sessions on mount
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const chats = await chatService.getChats();
        const formattedChats = chatService.formatChatsForUI(chats);
        const formattedSessions: ChatSession[] = formattedChats.map((chat) => ({
          id: String(chat.id),
          title: chat.title,
          createdAt: new Date(),
          lastMessageTime: chat.lastMessageTime,
          messageCount: chat.messageCount,
        }));
        setSessions(formattedSessions);

        // Set active session if we have any and none is currently selected
        if (formattedSessions.length > 0 && !activeSessionId) {
          setActiveSessionId(formattedSessions[0].id);
          fetchMessagesForSession(Number(formattedSessions[0].id));
        }
      } catch (error) {
        console.error("Error fetching chat sessions:", error);
        toast.error("Failed to load chat history");
      }
    };

    fetchSessions();
  }, [activeSessionId]);

  // Fetch messages when active session changes
  useEffect(() => {
    if (activeSessionId) {
      fetchMessagesForSession(Number(activeSessionId));
    } else {
      setMessages([]);
    }
  }, [activeSessionId]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Fetch messages for a specific session
  const fetchMessagesForSession = async (sessionId: number) => {
    try {
      const messageData = await chatService.getChatMessages(sessionId);
      const formattedMessages = chatService.formatMessagesForUI(messageData);
      // Convert to Message type (should be compatible)
      const msgArray: Message[] = formattedMessages.map((msg) => ({
        id: String(msg.id),
        content: msg.content,
        role: msg.role,
        timestamp: msg.timestamp,
      }));
      setMessages(msgArray);
    } catch (error) {
      console.error(`Error fetching messages for session ${sessionId}:`, error);
      toast.error("Failed to load messages");
    }
  };

  // Handle streaming chunks
  const handleStreamChunk = (chunk: StreamChunk) => {
    if (chunk.type === "chat_info") {
      const infoChunk = chunk as ChatInfoChunk;
      // Update active session ID if this is a new chat
      if (!activeSessionId) {
        setActiveSessionId(String(infoChunk.data.chat_id));

        // Create new session in the sidebar
        const newSession: ChatSession = {
          id: String(infoChunk.data.chat_id),
          title: infoChunk.data.title || "New Chat",
          createdAt: new Date(),
          lastMessageTime: new Date(),
          messageCount: 1,
        };
        setSessions((prev) => [newSession, ...prev]);
      }
    } else if (chunk.type === "text_delta") {
      const textChunk = chunk as TextDeltaChunk;
      // Append text delta to current assistant message
      setCurrentMessage((prev) => {
        if (!prev) {
          // Create new assistant message if it doesn't exist
          return {
            id: `assistant-${Date.now()}`,
            content: textChunk.data.delta,
            role: "assistant",
            timestamp: new Date(),
          };
        }
        // Append delta to existing message
        return {
          ...prev,
          content: prev.content + textChunk.data.delta,
        };
      });
    } else if (chunk.type === "status") {
      const statusChunk = chunk as StatusChunk;
      if (statusChunk.data.status === "complete") {
        // Finalize the message and add to messages list
        if (currentMessage) {
          setMessages((prev) => [
            ...prev,
            {
              ...currentMessage,
              id: `${statusChunk.data.chat_id}-${Date.now()}`,
            },
          ]);
          setCurrentMessage(null);
        }
        setIsTyping(false);

        // Update session if active
        if (activeSessionId) {
          setSessions((prev) =>
            prev.map((session) =>
              session.id === String(statusChunk.data.chat_id)
                ? {
                    ...session,
                    lastMessageTime: new Date(),
                    messageCount: (session.messageCount ?? 0) + 1,
                  }
                : session
            )
          );
        }
      }
    } else if (chunk.type === "error") {
      const errorChunk = chunk as ErrorChunk;
      toast.error(errorChunk.data.message);
      setIsTyping(false);
    }
    // Handle other chunk types if needed (tool_call, tool_output)
  };

  const handleSendMessage = (content: string) => {
    if (!content.trim()) return;

    // Create user message
    const userMessage: Message = {
      id: Date.now().toString(),
      content,
      role: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);

    // Call the external handler if provided
    onSendMessage?.(content);

    // Create request object
    const request: ChatMessageRequest = {
      message: content,
      chat_id: activeSessionId ? Number(activeSessionId) : undefined,
    };

    // Stream response from backend
    streamService
      .streamChatResponse(request, handleStreamChunk)
      .catch((error) => {
        console.error("Stream error:", error);
        setIsTyping(false);
        toast.error("Failed to get response from server");
      });
  };

  const handleCreateNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
    setCurrentMessage(null);
  };

  const handleSelectSession = (sessionId: string) => {
    setActiveSessionId(sessionId);
    // Messages will be fetched by the useEffect that watches activeSessionId
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden bg-background">
      {/* Sidebar */}
      <div
        className={cn(
          "h-full border-r transition-all duration-300 ease-in-out",
          sidebarOpen ? "w-80" : "w-0"
        )}
      >
        {sidebarOpen && (
          <ChatSidebar
            sessions={sessions}
            activeSessionId={activeSessionId}
            onNewChat={handleCreateNewChat}
            onSessionSelect={handleSelectSession}
            isCollapsed={!sidebarOpen}
          />
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 h-full">
        {/* Chat Header */}
        <div className="flex items-center justify-between border-b px-4 py-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <MenuIcon className="h-5 w-5" />
          </Button>
          <h2 className="text-lg font-medium">
            {activeSessionId
              ? sessions.find((s) => s.id === activeSessionId)?.title || "Chat"
              : "New Chat"}
          </h2>
          <div className="w-10" />
        </div>

        {/* Messages Area */}
        <ScrollArea className="flex-1 p-4">
          <div className="flex flex-col gap-2 pb-10">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {currentMessage && (
              <ChatMessage key="current-message" message={currentMessage} />
            )}
            {isTyping && !currentMessage && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="p-4 border-t">
          <ChatInput
            onSubmit={handleSendMessage}
            isDisabled={isTyping}
            placeholder="Type your message..."
          />
        </div>
      </div>
    </div>
  );
}
