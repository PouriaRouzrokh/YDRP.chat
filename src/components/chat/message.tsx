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
          "w-[95%] sm:max-w-[85%] md:max-w-[80%]"
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
              "w-full shadow-sm"
            )}
          >
            <CardContent className="py-2 px-3 flex items-center">
              <div className="prose dark:prose-invert break-words">
                {message.content}
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
