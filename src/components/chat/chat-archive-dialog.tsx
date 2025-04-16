import { FC, useState, useEffect } from "react";
import { toast } from "sonner";
import { Archive, RotateCcw, Undo2, AlertTriangle } from "lucide-react";
import { ChatSession } from "./chat-sidebar";
import { cn } from "@/lib/utils";
import { chatService } from "@/services/chat";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

interface ChatArchiveDialogProps {
  isOpen: boolean;
  onClose: () => void;
  activeSessions: ChatSession[];
  archivedSessions: ChatSession[];
  onSessionsUpdate: () => void;
}

export const ChatArchiveDialog: FC<ChatArchiveDialogProps> = ({
  isOpen,
  onClose,
  activeSessions,
  archivedSessions,
  onSessionsUpdate,
}) => {
  const [activeTab, setActiveTab] = useState<"active" | "archived">("active");
  const [selectedActiveSessions, setSelectedActiveSessions] = useState<
    string[]
  >([]);
  const [selectedArchivedSessions, setSelectedArchivedSessions] = useState<
    string[]
  >([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset selections when dialog opens
  useEffect(() => {
    if (isOpen) {
      setSelectedActiveSessions([]);
      setSelectedArchivedSessions([]);
      setIsSubmitting(false);
      console.log("Archive dialog opened, state reset");
    }
  }, [isOpen]);

  const handleSelectActiveSession = (sessionId: string) => {
    setSelectedActiveSessions((prev) =>
      prev.includes(sessionId)
        ? prev.filter((id) => id !== sessionId)
        : [...prev, sessionId]
    );
  };

  const handleSelectArchivedSession = (sessionId: string) => {
    setSelectedArchivedSessions((prev) =>
      prev.includes(sessionId)
        ? prev.filter((id) => id !== sessionId)
        : [...prev, sessionId]
    );
  };

  const handleSelectAllActiveSessions = () => {
    if (selectedActiveSessions.length === activeSessions.length) {
      setSelectedActiveSessions([]);
    } else {
      setSelectedActiveSessions(activeSessions.map((session) => session.id));
    }
  };

  const handleSelectAllArchivedSessions = () => {
    if (selectedArchivedSessions.length === archivedSessions.length) {
      setSelectedArchivedSessions([]);
    } else {
      setSelectedArchivedSessions(
        archivedSessions.map((session) => session.id)
      );
    }
  };

  const handleArchiveSelected = async () => {
    if (selectedActiveSessions.length === 0) {
      toast.error("No chats selected to archive");
      return;
    }

    setIsSubmitting(true);
    try {
      // Archive each selected chat one by one
      await Promise.all(
        selectedActiveSessions.map(async (sessionId) => {
          await chatService.archiveChat(Number(sessionId));
        })
      );

      toast.success(`Archived ${selectedActiveSessions.length} chat(s)`);
      setSelectedActiveSessions([]);
      onSessionsUpdate(); // Trigger refresh of chat lists
    } catch (error) {
      console.error("Error archiving chats:", error);
      toast.error("Failed to archive some chats");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUnarchiveSelected = async () => {
    if (selectedArchivedSessions.length === 0) {
      toast.error("No chats selected to unarchive");
      return;
    }

    setIsSubmitting(true);
    try {
      // Unarchive each selected chat one by one
      await Promise.all(
        selectedArchivedSessions.map(async (sessionId) => {
          await chatService.unarchiveChat(Number(sessionId));
        })
      );

      toast.success(`Unarchived ${selectedArchivedSessions.length} chat(s)`);
      setSelectedArchivedSessions([]);
      onSessionsUpdate(); // Trigger refresh of chat lists
    } catch (error) {
      console.error("Error unarchiving chats:", error);
      toast.error("Failed to unarchive some chats");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleArchiveAll = async () => {
    if (activeSessions.length === 0) {
      toast.error("No active chats to archive");
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await chatService.archiveAllChats();
      toast.success(result.message || `Archived ${result.count} chat(s)`);
      onSessionsUpdate(); // Trigger refresh of chat lists
    } catch (error) {
      console.error("Error archiving all chats:", error);
      toast.error("Failed to archive all chats");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open: boolean) => !open && onClose()}>
      <DialogContent className="sm:max-w-[500px] max-h-[80vh] flex flex-col overflow-hidden">
        <DialogHeader>
          <DialogTitle>Manage Chat Archive</DialogTitle>
          <DialogDescription>
            Archiving chats hides them from the sidebar but preserves them for
            future reference. You can unarchive them anytime to restore access.
          </DialogDescription>
        </DialogHeader>

        <Tabs
          value={activeTab}
          onValueChange={(value: string) =>
            setActiveTab(value as "active" | "archived")
          }
          className="flex-1 flex flex-col min-h-0 overflow-hidden"
        >
          <TabsList className="grid grid-cols-2">
            <TabsTrigger value="active" className="flex items-center gap-1">
              <Archive className="h-4 w-4" />
              <span>Active Chats</span>
            </TabsTrigger>
            <TabsTrigger value="archived" className="flex items-center gap-1">
              <RotateCcw className="h-4 w-4" />
              <span>Archived Chats</span>
            </TabsTrigger>
          </TabsList>

          {/* Active Chats Tab */}
          <TabsContent
            value="active"
            className="flex-1 flex flex-col min-h-0 max-h-[50vh] sm:max-h-[60vh] overflow-hidden data-[state=inactive]:hidden"
          >
            {activeSessions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <Archive className="h-8 w-8 mb-2" />
                <p>No active chats found</p>
              </div>
            ) : (
              <>
                <div className="py-2 flex items-center">
                  <Checkbox
                    id="select-all-active"
                    checked={
                      activeSessions.length > 0 &&
                      selectedActiveSessions.length === activeSessions.length
                    }
                    onCheckedChange={handleSelectAllActiveSessions}
                  />
                  <Label htmlFor="select-all-active" className="ml-2">
                    Select All ({activeSessions.length})
                  </Label>
                </div>

                <ScrollArea className="flex-1 border rounded-md overflow-y-auto">
                  <div className="p-2 space-y-2">
                    {activeSessions.map((session) => (
                      <div
                        key={session.id}
                        className={cn(
                          "flex items-center p-2 rounded-md",
                          selectedActiveSessions.includes(session.id)
                            ? "bg-muted"
                            : "hover:bg-accent hover:text-accent-foreground"
                        )}
                      >
                        <Checkbox
                          id={`active-${session.id}`}
                          checked={selectedActiveSessions.includes(session.id)}
                          onCheckedChange={() =>
                            handleSelectActiveSession(session.id)
                          }
                        />
                        <Label
                          htmlFor={`active-${session.id}`}
                          className="ml-2 cursor-pointer truncate flex-1"
                        >
                          {session.title}
                        </Label>
                      </div>
                    ))}
                  </div>
                </ScrollArea>

                <div className="flex justify-between mt-4 gap-2">
                  <Button
                    variant="outline"
                    className="flex gap-1 items-center"
                    onClick={handleArchiveSelected}
                    disabled={
                      selectedActiveSessions.length === 0 || isSubmitting
                    }
                  >
                    <Archive className="h-4 w-4" />
                    Archive Selected ({selectedActiveSessions.length})
                  </Button>
                  <Button
                    variant="destructive"
                    className="flex gap-1 items-center"
                    onClick={handleArchiveAll}
                    disabled={activeSessions.length === 0 || isSubmitting}
                  >
                    <AlertTriangle className="h-4 w-4" />
                    Archive All ({activeSessions.length})
                  </Button>
                </div>
              </>
            )}
          </TabsContent>

          {/* Archived Chats Tab */}
          <TabsContent
            value="archived"
            className="flex-1 flex flex-col min-h-0 max-h-[50vh] sm:max-h-[60vh] overflow-hidden data-[state=inactive]:hidden"
          >
            {archivedSessions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <RotateCcw className="h-8 w-8 mb-2" />
                <p>No archived chats found</p>
              </div>
            ) : (
              <>
                <div className="py-2 flex items-center">
                  <Checkbox
                    id="select-all-archived"
                    checked={
                      archivedSessions.length > 0 &&
                      selectedArchivedSessions.length ===
                        archivedSessions.length
                    }
                    onCheckedChange={handleSelectAllArchivedSessions}
                  />
                  <Label htmlFor="select-all-archived" className="ml-2">
                    Select All ({archivedSessions.length})
                  </Label>
                </div>

                <ScrollArea className="flex-1 border rounded-md overflow-y-auto">
                  <div className="p-2 space-y-2">
                    {archivedSessions.map((session) => (
                      <div
                        key={session.id}
                        className={cn(
                          "flex items-center p-2 rounded-md",
                          selectedArchivedSessions.includes(session.id)
                            ? "bg-muted"
                            : "hover:bg-accent hover:text-accent-foreground"
                        )}
                      >
                        <Checkbox
                          id={`archived-${session.id}`}
                          checked={selectedArchivedSessions.includes(
                            session.id
                          )}
                          onCheckedChange={() =>
                            handleSelectArchivedSession(session.id)
                          }
                        />
                        <Label
                          htmlFor={`archived-${session.id}`}
                          className="ml-2 cursor-pointer truncate flex-1"
                        >
                          {session.title}
                        </Label>
                      </div>
                    ))}
                  </div>
                </ScrollArea>

                <div className="mt-4">
                  <Button
                    variant="outline"
                    className="flex gap-1 items-center"
                    onClick={handleUnarchiveSelected}
                    disabled={
                      selectedArchivedSessions.length === 0 || isSubmitting
                    }
                  >
                    <Undo2 className="h-4 w-4" />
                    Unarchive Selected ({selectedArchivedSessions.length})
                  </Button>
                </div>
              </>
            )}
          </TabsContent>
        </Tabs>

        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
