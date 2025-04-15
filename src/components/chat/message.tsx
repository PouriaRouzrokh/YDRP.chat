import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Bot, User } from "lucide-react";

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
    <div
      className={cn(
        "flex gap-3 w-full max-w-4xl mb-3",
        isUser ? "flex-row-reverse self-end" : "flex-row"
      )}
    >
      <Avatar className={cn(isUser ? "bg-primary" : "bg-secondary")}>
        <AvatarFallback>
          {isUser ? <User className="h-5 w-5" /> : <Bot className="h-5 w-5" />}
        </AvatarFallback>
      </Avatar>
      <div className="flex flex-col gap-2 w-full">
        <Card
          className={cn(isUser ? "bg-primary/10" : "bg-secondary/10", "w-full")}
        >
          <CardContent className="py-1.5 px-3 flex items-center">
            <div className="prose dark:prose-invert">{message.content}</div>
          </CardContent>
        </Card>
        {message.references && message.references.length > 0 && (
          <div className="flex flex-col gap-2">
            {message.references.map((reference) => (
              <PolicyReference key={reference.id} reference={reference} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function PolicyReference({ reference }: { reference: PolicyReference }) {
  return (
    <Card className="border-blue-200 bg-blue-50 dark:bg-blue-950 dark:border-blue-800">
      <CardHeader className="py-1 px-3 font-medium text-sm">
        {reference.title}
      </CardHeader>
      <CardContent className="py-1 px-3 text-sm">
        {reference.excerpt}
      </CardContent>
      <CardFooter className="pt-0 px-3 pb-1">
        <a
          href={reference.url}
          className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
        >
          View Source
        </a>
      </CardFooter>
    </Card>
  );
}

export function TypingIndicator() {
  return (
    <div className="flex gap-3 w-full max-w-4xl">
      <Avatar className="bg-secondary">
        <AvatarFallback>
          <Bot className="h-5 w-5" />
        </AvatarFallback>
      </Avatar>
      <Card className="bg-secondary/10 w-[80px]">
        <CardContent className="p-4 flex gap-1 items-center">
          <div className="animate-bounce h-1.5 w-1.5 bg-muted-foreground rounded-full" />
          <div
            className="animate-bounce h-1.5 w-1.5 bg-muted-foreground rounded-full"
            style={{ animationDelay: "0.2s" }}
          />
          <div
            className="animate-bounce h-1.5 w-1.5 bg-muted-foreground rounded-full"
            style={{ animationDelay: "0.4s" }}
          />
        </CardContent>
      </Card>
    </div>
  );
}
