import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Bot, User } from "lucide-react";
import { motion } from "framer-motion";
import { fadeInUp } from "@/lib/animation-variants";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";

export interface PolicyReference {
  id: string;
  title: string;
  excerpt: string;
  url: string;
}

export interface Message {
  id: string;
  content: string;
  role: "user" | "assistant";
  timestamp: Date;
  references?: PolicyReference[];
}

interface MessageProps {
  message: Message;
}

export function ChatMessage({ message }: MessageProps) {
  const isUser = message.role === "user";

  // Helper function to make URLs more mobile-friendly by truncating if needed
  const formatUrl = (url: string) => {
    // For display purposes, we'll truncate very long URLs
    if (url.length > 30) {
      return `${url.substring(0, 15)}...${url.substring(url.length - 10)}`;
    }
    return url;
  };

  return (
    <motion.div
      variants={fadeInUp}
      className={cn(
        "flex w-full mb-4",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      <div
        className={cn(
          "flex gap-3",
          isUser ? "flex-row-reverse" : "flex-row",
          isUser ? "ml-auto" : "mr-auto",
          "w-full max-w-[95%] sm:max-w-[85%] md:max-w-[80%]"
        )}
      >
        <Avatar className={cn(isUser ? "bg-primary" : "bg-secondary")}>
          <AvatarFallback>
            {isUser ? (
              <User className="h-5 w-5" />
            ) : (
              <Bot className="h-5 w-5" />
            )}
          </AvatarFallback>
        </Avatar>
        <motion.div
          className="flex flex-col gap-2 w-full"
          initial={{ scale: 0.95 }}
          animate={{ scale: 1 }}
          transition={{ duration: 0.2 }}
        >
          <Card
            className={cn(
              isUser
                ? "bg-green-100 dark:bg-emerald-700 text-gray-800 dark:text-gray-50 border-green-200 dark:border-emerald-600"
                : "bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700",
              "w-full shadow-sm overflow-hidden break-words"
            )}
          >
            <CardContent className="py-2 px-2 sm:px-3 flex items-center overflow-hidden">
              <div className="prose-sm sm:prose dark:prose-invert break-words w-full overflow-hidden">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={{
                    a: ({ href, children, ...props }) => (
                      <a
                        {...props}
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 dark:text-blue-400 hover:underline break-all hyphens-auto overflow-wrap-anywhere text-xs sm:text-sm"
                        title={href}
                      >
                        {typeof children === "string" && children === href
                          ? formatUrl(href)
                          : children}
                      </a>
                    ),
                    ul: ({ ...props }) => (
                      <ul {...props} className="list-disc pl-3 sm:pl-5 mb-2" />
                    ),
                    ol: ({ ...props }) => (
                      <ol
                        {...props}
                        className="list-decimal pl-3 sm:pl-5 mb-2"
                      />
                    ),
                    li: ({ ...props }) => <li {...props} className="mb-1" />,
                    p: ({ ...props }) => (
                      <p
                        {...props}
                        className="mb-2 max-w-full text-sm sm:text-base break-words whitespace-pre-wrap overflow-wrap-anywhere hyphens-auto"
                      />
                    ),
                    code: ({ ...props }) => (
                      <code
                        {...props}
                        className="break-all text-xs sm:text-sm p-0.5 overflow-wrap-anywhere"
                      />
                    ),
                    pre: ({ ...props }) => (
                      <pre
                        {...props}
                        className="whitespace-pre-wrap break-all text-xs sm:text-sm overflow-x-auto max-w-full"
                      />
                    ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            </CardContent>
          </Card>
          {message.references && message.references.length > 0 && (
            <div className="flex flex-col gap-2">
              {message.references.map((reference) => (
                <PolicyReference key={reference.id} reference={reference} />
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </motion.div>
  );
}

export function PolicyReference({ reference }: { reference: PolicyReference }) {
  return (
    <Card className="border-blue-300 bg-blue-50 dark:bg-blue-900 dark:border-blue-800 dark:text-blue-100">
      <CardHeader className="py-1 px-3 font-medium text-sm text-blue-800 dark:text-blue-100">
        {reference.title}
      </CardHeader>
      <CardContent className="py-1 px-3 text-sm text-blue-900 dark:text-blue-200">
        {reference.excerpt}
      </CardContent>
      <CardFooter className="pt-0 px-3 pb-1">
        <a
          href={reference.url}
          className="text-xs text-blue-600 dark:text-blue-300 hover:underline"
        >
          View Source
        </a>
      </CardFooter>
    </Card>
  );
}

export function TypingIndicator() {
  return (
    <motion.div
      variants={fadeInUp}
      className="flex w-full mb-4 justify-start"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex gap-3 w-[95%] sm:max-w-[85%] md:max-w-[80%]">
        <Avatar className="bg-secondary">
          <AvatarFallback>
            <Bot className="h-5 w-5" />
          </AvatarFallback>
        </Avatar>
        <motion.div
          initial={{ scale: 0.95 }}
          animate={{ scale: 1 }}
          transition={{ duration: 0.2 }}
          className="w-full"
        >
          <Card className="bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700 w-[120px] shadow-sm">
            <CardContent className="p-3 flex gap-2 items-center">
              <div className="animate-bounce h-2 w-2 bg-muted-foreground rounded-full" />
              <div
                className="animate-bounce h-2 w-2 bg-muted-foreground rounded-full"
                style={{ animationDelay: "0.2s" }}
              />
              <div
                className="animate-bounce h-2 w-2 bg-muted-foreground rounded-full"
                style={{ animationDelay: "0.4s" }}
              />
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </motion.div>
  );
}
