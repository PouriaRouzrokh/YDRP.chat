import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { PlusCircle } from "lucide-react";

export interface ChatSession {
  id: string;
  title: string;
  createdAt: Date;
  lastMessageTime?: Date;
  messageCount?: number;
}

export interface ChatSidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSessionSelect: (sessionId: string) => void;
  onNewChat: () => void;
  isCollapsed: boolean;
}

export function ChatSidebar({
  sessions,
  activeSessionId,
  onSessionSelect,
  onNewChat,
  isCollapsed,
}: ChatSidebarProps) {
  if (isCollapsed) {
    return (
      <div className="flex h-full w-[60px] flex-col items-center border-r p-2">
        <Button
          variant="ghost"
          size="icon"
          className="mb-4"
          onClick={onNewChat}
          aria-label="New Chat"
        >
          <PlusCircle className="h-6 w-6" />
        </Button>
      </div>
    );
  }

  return (
    <div className="flex h-full w-[260px] flex-col border-r overflow-hidden">
      <div className="p-4 flex-shrink-0">
        <Button onClick={onNewChat} className="w-full justify-start gap-2">
          <PlusCircle className="h-4 w-4" />
          New Chat
        </Button>
      </div>
      <div className="flex-1 overflow-auto">
        <ScrollArea className="h-full px-2">
          <div className="space-y-1 pb-4">
            {sessions?.map((session) => (
              <Button
                key={session.id}
                variant={activeSessionId === session.id ? "secondary" : "ghost"}
                className={cn(
                  "w-full justify-start truncate overflow-hidden text-sm",
                  activeSessionId === session.id ? "bg-secondary/50" : ""
                )}
                onClick={() => onSessionSelect(session.id)}
              >
                {session.title}
              </Button>
            ))}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
