import * as React from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { IconSpinner } from "@/components/ui/icons";

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessageProps {
  role: MessageRole;
  content: string;
  isLoading?: boolean;
  className?: string;
}

export function ChatMessage({
  role,
  content,
  isLoading,
  className,
}: ChatMessageProps) {
  return (
    <div
      className={cn(
        "flex gap-3 px-3 py-2",
        role === "user" ? "bg-background" : "bg-muted/50",
        className
      )}
    >
      <Avatar className="h-8 w-8">
        {role === "user" ? (
          <>
            <AvatarImage src="/user-avatar.png" alt="User" />
            <AvatarFallback>U</AvatarFallback>
          </>
        ) : (
          <>
            <AvatarImage src="/bot-avatar.png" alt="Assistant" />
            <AvatarFallback>A</AvatarFallback>
          </>
        )}
      </Avatar>
      <div className="flex-1 flex flex-col justify-center">
        <div className="font-semibold text-sm">
          {role === "user" ? "You" : "Assistant"}
        </div>
        <div className="prose prose-sm max-w-none">
          {isLoading ? (
            <div className="flex items-center">
              <IconSpinner className="mr-2" />
              <span>Thinking...</span>
            </div>
          ) : (
            content
          )}
        </div>
      </div>
    </div>
  );
}

export function ChatMessages({
  messages,
  isLoading,
  className,
}: {
  messages: Omit<ChatMessageProps, "className">[];
  isLoading?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {messages.map((message, index) => (
        <ChatMessage key={index} {...message} />
      ))}
      {isLoading && (
        <ChatMessage role="assistant" content="" isLoading={true} />
      )}
    </div>
  );
}
