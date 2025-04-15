import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MenuIcon } from "lucide-react";
import { ChatSidebar, ChatSession } from "./chat-sidebar";
import { ChatInput } from "./chat-input";
import { ChatMessage, Message, TypingIndicator } from "./message";
import { cn } from "@/lib/utils";

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
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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

    // Simulate typing indicator
    setIsTyping(true);

    // Call the external handler if provided
    onSendMessage?.(content);

    // Simulate assistant response after delay
    setTimeout(() => {
      setIsTyping(false);

      // Mock assistant response
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content:
          "This is a simulated response to your message. In the actual application, this would be replaced with the response from the backend.",
        role: "assistant",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Update session if active
      if (activeSessionId) {
        setSessions((prev) =>
          prev.map((session) =>
            session.id === activeSessionId
              ? {
                  ...session,
                  lastMessageTime: new Date(),
                  messageCount: (session.messageCount ?? 0) + 2,
                }
              : session
          )
        );
      }
    }, 2000);
  };

  const handleCreateNewChat = () => {
    const newSession: ChatSession = {
      id: Date.now().toString(),
      title: "New Chat",
      createdAt: new Date(),
      lastMessageTime: new Date(),
      messageCount: 0,
    };

    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    setMessages([]);
  };

  const handleSelectSession = (sessionId: string) => {
    setActiveSessionId(sessionId);
    // In a real app, we would fetch messages for this session
    // For now, we'll just clear messages when switching sessions
    setMessages([]);
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
            {isTyping && <TypingIndicator />}
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
