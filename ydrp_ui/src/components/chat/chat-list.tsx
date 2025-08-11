import { useRef, useEffect } from "react";
import { ChatMessage, ChatMessageProps } from "./chat-message";
import { cn } from "@/lib/utils";

interface ChatListProps {
  messages: ChatMessageProps[];
  isLoading?: boolean;
  className?: string;
}

export function ChatList({ messages, isLoading, className }: ChatListProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div
      ref={containerRef}
      className={cn("flex flex-col gap-4 overflow-y-auto", className)}
    >
      {messages.map((message, index) => (
        <ChatMessage
          key={index}
          role={message.role}
          content={message.content}
          isLoading={index === messages.length - 1 && isLoading}
        />
      ))}

      {/* Empty loading message when there are no messages yet */}
      {messages.length === 0 && isLoading && (
        <ChatMessage role="assistant" content="" isLoading={true} />
      )}
    </div>
  );
}
