import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { PlusIcon } from "lucide-react";

export interface ChatHistoryItem {
  id: string;
  title: string;
  date: Date;
  active?: boolean;
}

interface ChatHistoryProps {
  items: ChatHistoryItem[];
  onSelect: (id: string) => void;
  onNewChat: () => void;
  className?: string;
}

export function ChatHistory({
  items,
  onSelect,
  onNewChat,
  className,
}: ChatHistoryProps) {
  return (
    <div className={cn("flex flex-col h-full", className)}>
      <div className="px-4 py-3">
        <Button
          onClick={onNewChat}
          variant="outline"
          className="w-full justify-start gap-2"
        >
          <PlusIcon className="h-4 w-4" />
          New Chat
        </Button>
      </div>

      <Separator />

      <ScrollArea className="flex-1">
        {items.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            No chat history
          </div>
        ) : (
          <div className="p-2">
            {items.map((item) => (
              <Button
                key={item.id}
                variant={item.active ? "secondary" : "ghost"}
                className={cn(
                  "w-full justify-start text-left font-normal px-2 py-2 mb-1",
                  item.active ? "bg-secondary" : "hover:bg-secondary/50"
                )}
                onClick={() => onSelect(item.id)}
              >
                <div className="flex flex-col items-start">
                  <span className="line-clamp-1">{item.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {item.date.toLocaleDateString()}
                  </span>
                </div>
              </Button>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
