import React from "react";
import { cn } from "@/lib/utils";
import { IconSpinner } from "../ui/icons";
import { Avatar, AvatarFallback, AvatarImage } from "../ui/avatar";
import { motion } from "framer-motion";
import { staggerContainer } from "@/lib/animation-variants";
// Markdown renderer no longer used; HTML is sanitized and rendered directly
import DOMPurify from "dompurify";

export type MessageRole = "user" | "assistant";

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
  const sanitizedHtml =
    typeof window !== "undefined"
      ? DOMPurify.sanitize(content, { USE_PROFILES: { html: true } })
      : content;
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={cn(
        "group relative mb-4 flex items-start md:mb-6",
        role === "user" ? "justify-end" : "justify-start",
        className
      )}
      role="listitem"
      aria-label={`${role} message`}
    >
      {role === "assistant" && (
        <div
          className="mr-3 flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-md border bg-background shadow-sm"
          aria-hidden="true"
        >
          <Avatar className="h-6 w-6">
            <AvatarImage src="/logo.png" alt="Assistant" />
            <AvatarFallback>AI</AvatarFallback>
          </Avatar>
        </div>
      )}
      <motion.div
        className={cn(
          "max-w-[80%] md:max-w-[65%] rounded-xl px-4 py-3 ring-1 ring-inset",
          role === "user"
            ? "bg-primary text-primary-foreground ring-primary"
            : "bg-muted ring-border",
          "transition-all duration-200 ease-in-out"
        )}
        tabIndex={0}
        aria-live={role === "assistant" ? "polite" : "off"}
        initial={{ scale: 0.95 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.2, delay: 0.1 }}
      >
        {isLoading ? (
          <div
            aria-label="Loading response"
            role="status"
            className="flex items-center justify-center h-6"
          >
            <IconSpinner className="h-4 w-4 animate-spin" />
            <span className="sr-only">Loading message...</span>
          </div>
        ) : (
          <div className="prose prose-sm md:prose-base break-words dark:prose-invert prose-p:leading-relaxed prose-pre:p-0 [&_a]:text-blue-600 dark:[&_a]:text-blue-400 [&_a]:underline">
            <div
              className="max-w-full"
              dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
            />
          </div>
        )}
      </motion.div>
      {role === "user" && (
        <div
          className="ml-3 flex h-8 w-8 shrink-0 select-none items-center justify-center rounded-md border bg-background shadow-sm"
          aria-hidden="true"
        >
          <Avatar className="h-6 w-6">
            <AvatarFallback>U</AvatarFallback>
          </Avatar>
        </div>
      )}
    </motion.div>
  );
}

export interface ChatMessagesProps {
  messages: ChatMessageProps[];
  isLoading?: boolean;
}

export function ChatMessages({ messages, isLoading }: ChatMessagesProps) {
  return (
    <motion.div
      className="flex flex-col space-y-5 py-4 px-4 md:px-6"
      role="list"
      aria-label="Chat messages"
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
    >
      {messages.map((message, index) => (
        <ChatMessage key={index} {...message} />
      ))}
      {isLoading && (
        <ChatMessage role="assistant" content="" isLoading={true} />
      )}
    </motion.div>
  );
}
