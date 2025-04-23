import { useEffect, useRef, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { MenuIcon, Edit } from "lucide-react";
import { ChatSidebar, ChatSession } from "./chat-sidebar";
import { ChatInput } from "./chat-input";
import { ChatMessage, Message, TypingIndicator } from "./message";
import { cn } from "@/lib/utils";
import { chatService } from "@/services/chat";
import { streamService } from "@/services/stream";
import { toast } from "sonner";
import {
  ChatInfoChunk,
  ChatMessageRequest,
  ErrorChunk,
  StatusChunk,
  StreamChunk,
  TextDeltaChunk,
} from "@/types";
import { ChatRenameDialog } from "./chat-rename-dialog";
import { ChatArchiveDialog } from "./chat-archive-dialog";

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
  const [archivedSessions, setArchivedSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(
    initialSessions.length > 0 ? initialSessions[0].id : null
  );
  // Direct state for active chat title
  const [activeChatTitle, setActiveChatTitle] = useState<string>(
    initialSessions.length > 0
      ? initialSessions[0]?.title || "Chat"
      : "New Chat"
  );
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [isTyping, setIsTyping] = useState(false);
  const [currentMessage, setCurrentMessage] = useState<Message | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // State for rename dialog
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const [chatToRename, setChatToRename] = useState<ChatSession | null>(null);

  // State for archive dialog
  const [isArchiveDialogOpen, setIsArchiveDialogOpen] = useState(false);

  // Fetch messages for a specific session
  const fetchMessagesForSession = useCallback(async (sessionId: number) => {
    try {
      const messageData = await chatService.getChatMessages(sessionId);
      const formattedMessages = chatService.formatMessagesForUI(messageData);
      // Convert to Message type (should be compatible)
      const msgArray: Message[] = formattedMessages.map((msg) => ({
        id: String(msg.id),
        content: msg.content,
        role: msg.role,
        timestamp: msg.timestamp,
      }));
      setMessages(msgArray);
    } catch (error) {
      console.error(`Error fetching messages for session ${sessionId}:`, error);
      toast.error("Failed to load messages");
    }
  }, []);

  // Separate function to fetch both active and archived sessions
  const fetchSessions = useCallback(async () => {
    try {
      // Fetch active chats
      const activeChats = await chatService.getChatsWithMessageCounts(
        0,
        100,
        false
      );
      const formattedActiveSessions: ChatSession[] = activeChats.map(
        (chat) => ({
          id: String(chat.id),
          title: chat.title,
          createdAt: new Date(),
          lastMessageTime: chat.lastMessageTime,
          messageCount: chat.messageCount,
          isArchived: false,
        })
      );
      setSessions(formattedActiveSessions);

      // Fetch archived chats
      const archivedChats = await chatService.getChatsWithMessageCounts(
        0,
        100,
        true
      );
      const formattedArchivedSessions: ChatSession[] = archivedChats.map(
        (chat) => ({
          id: String(chat.id),
          title: chat.title,
          createdAt: new Date(),
          lastMessageTime: chat.lastMessageTime,
          messageCount: chat.messageCount,
          isArchived: true,
        })
      );
      setArchivedSessions(formattedArchivedSessions);

      // Set active session if we have any and none is currently selected
      if (formattedActiveSessions.length > 0 && !activeSessionId) {
        const firstSession = formattedActiveSessions[0];
        setActiveSessionId(firstSession.id);
        setActiveChatTitle(firstSession.title);
        fetchMessagesForSession(Number(firstSession.id));
      }
    } catch (error) {
      console.error("Error fetching chat sessions:", error);
      toast.error("Failed to load chat history");
    }
  }, [activeSessionId, fetchMessagesForSession]);

  // Update active chat title whenever active session changes
  useEffect(() => {
    if (!activeSessionId) {
      setActiveChatTitle("New Chat");
      return;
    }

    const chat = sessions.find((s) => s.id === activeSessionId);
    if (chat) {
      setActiveChatTitle(chat.title);
    } else {
      // If the active chat isn't found (e.g., deleted/archived?), reset
      setActiveChatTitle("Select Chat");
      // Optionally, clear the active session ID
      // setActiveSessionId(null);
    }
  }, [activeSessionId, sessions]);

  // Fetch chat sessions on mount
  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // Fetch messages when active session changes
  useEffect(() => {
    if (activeSessionId) {
      fetchMessagesForSession(Number(activeSessionId));
    } else {
      setMessages([]);
    }
  }, [activeSessionId, fetchMessagesForSession]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Handle streaming chunks
  const handleStreamChunk = (chunk: StreamChunk) => {
    if (chunk.type === "chat_info") {
      const infoChunk = chunk as ChatInfoChunk;
      // Update active session ID if this is a new chat
      if (!activeSessionId) {
        const newChatId = String(infoChunk.data.chat_id);
        const newChatTitle = infoChunk.data.title || "New Chat";

        setActiveSessionId(newChatId);
        setActiveChatTitle(newChatTitle);

        // Create new session in the sidebar
        const newSession: ChatSession = {
          id: newChatId,
          title: newChatTitle,
          createdAt: new Date(),
          lastMessageTime: new Date(),
          messageCount: 0, // Start with 0, will be updated when message is complete
          isArchived: false, // New chats are not archived by default
        };
        setSessions((prev) => [newSession, ...prev]);
      }
    } else if (chunk.type === "text_delta") {
      const textChunk = chunk as TextDeltaChunk;
      // Append text delta to current assistant message
      setCurrentMessage((prev) => {
        if (!prev) {
          // Create new assistant message if it doesn't exist
          return {
            id: `assistant-${Date.now()}`,
            content: textChunk.data.delta,
            role: "assistant",
            timestamp: new Date(),
          };
        }
        // Append delta to existing message
        return {
          ...prev,
          content: prev.content + textChunk.data.delta,
        };
      });
    } else if (chunk.type === "status") {
      const statusChunk = chunk as StatusChunk;
      if (statusChunk.data.status === "complete") {
        // Finalize the message and add to messages list
        if (currentMessage) {
          setMessages((prev) => [
            ...prev,
            {
              ...currentMessage,
              id: `${statusChunk.data.chat_id}-${Date.now()}`,
            },
          ]);
          setCurrentMessage(null);
        }
        setIsTyping(false);

        // Update session if active
        if (activeSessionId) {
          setSessions((prev) =>
            prev.map((session) =>
              session.id === String(statusChunk.data.chat_id)
                ? {
                    ...session,
                    lastMessageTime: new Date(),
                    messageCount: session.messageCount
                      ? session.messageCount + 1
                      : 1,
                  }
                : session
            )
          );
        }
      }
    } else if (chunk.type === "error") {
      const errorChunk = chunk as ErrorChunk;
      toast.error(errorChunk.data.message);
      setIsTyping(false);
    }
    // Handle other chunk types if needed (tool_call, tool_output)
  };

  const handleSendMessage = (content: string) => {
    if (!content.trim()) return;

    // Create user message
    const userMessage: Message = {
      id: Date.now().toString(),
      content,
      role: "user",
      timestamp: new Date(),
    };

    // Add user message and immediately show typing indicator
    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);

    // Call the external handler if provided
    onSendMessage?.(content);

    // Create request object
    const request: ChatMessageRequest = {
      message: content,
      chat_id: activeSessionId ? Number(activeSessionId) : undefined,
    };

    // Stream response from backend
    streamService
      .streamChatResponse(request, handleStreamChunk)
      .catch((error) => {
        console.error("Stream error:", error);
        setIsTyping(false);
        toast.error("Failed to get response from server");
      });
  };

  const handleCreateNewChat = () => {
    setActiveSessionId(null);
    setActiveChatTitle("New Chat");
    setMessages([]);
    setCurrentMessage(null);
  };

  const handleSelectSession = (sessionId: string) => {
    setActiveSessionId(sessionId);
    // Update title immediately
    const selectedChat = sessions.find((s) => s.id === sessionId);
    if (selectedChat) {
      setActiveChatTitle(selectedChat.title);
    }
    // Messages will be fetched by the useEffect that watches activeSessionId
  };

  const handleOpenRenameDialog = (chatId: string | null) => {
    if (!chatId) return;
    const chat = sessions.find((s) => s.id === chatId);
    if (chat) {
      setChatToRename(chat);
      setIsRenameDialogOpen(true);
    } else {
      console.warn(`Chat with ID ${chatId} not found for renaming.`);
    }
  };

  const handleCloseRenameDialog = () => {
    setIsRenameDialogOpen(false);
    setChatToRename(null); // Clear the chat being renamed
  };

  // Archive dialog handlers
  const handleOpenArchiveDialog = () => {
    console.log("Opening archive dialog", { current: isArchiveDialogOpen });
    setIsArchiveDialogOpen(true);
    // Force a re-render to ensure state is updated
    setTimeout(() => {
      console.log("Archive dialog should now be open:", isArchiveDialogOpen);
    }, 0);
  };

  const handleCloseArchiveDialog = () => {
    console.log("Closing archive dialog");
    setIsArchiveDialogOpen(false);
  };

  // Merged rename handler (API call + state update)
  const handleRenameChat = async (newTitle: string) => {
    if (!chatToRename) return;

    const chatId = chatToRename.id;
    const originalTitle = chatToRename.title; // Store original title for potential rollback

    // Optimistic UI update
    setSessions((prevSessions) =>
      prevSessions.map((session) =>
        session.id === chatId ? { ...session, title: newTitle } : session
      )
    );
    // Update header title immediately if it's the active chat
    if (activeSessionId === chatId) {
      setActiveChatTitle(newTitle);
    }

    handleCloseRenameDialog(); // Close dialog immediately

    try {
      console.log(`ChatContainer: Renaming chat ${chatId} to "${newTitle}"`);
      await chatService.renameChat(Number(chatId), newTitle);
      toast.success("Chat renamed successfully");
    } catch (error) {
      console.error("Error renaming chat:", error);
      toast.error("Failed to rename chat");
      // Rollback optimistic update on error
      setSessions((prevSessions) =>
        prevSessions.map((session) =>
          session.id === chatId ? { ...session, title: originalTitle } : session
        )
      );
      if (activeSessionId === chatId) {
        setActiveChatTitle(originalTitle);
      }
    }
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden bg-background">
      {/* Sidebar */}
      <div
        className={cn(
          "h-full border-r transition-all duration-300 ease-in-out overflow-hidden",
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
            onOpenRenameDialog={handleOpenRenameDialog}
            onOpenArchiveDialog={handleOpenArchiveDialog}
          />
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 h-full">
        {/* Chat Header */}
        <div className="flex items-center justify-between border-b px-2 sm:px-4 py-1 sm:py-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <MenuIcon className="h-5 w-5" />
          </Button>
          <h2
            className="text-base sm:text-lg font-medium truncate max-w-[150px] sm:max-w-[200px] md:max-w-full"
            key={`header-title-${activeSessionId}-${activeChatTitle}`} // Force re-render on title changes
          >
            {activeChatTitle}
          </h2>
          {activeSessionId && (
            <Button
              variant="ghost"
              size="icon"
              className="ml-1 sm:ml-2 h-5 w-5 sm:h-6 sm:w-6" // Smaller on mobile
              onClick={() => handleOpenRenameDialog(activeSessionId)}
              aria-label="Rename Chat"
            >
              <Edit className="h-3 w-3 sm:h-4 sm:w-4" />
            </Button>
          )}
          <div className="w-6 sm:w-10" />
        </div>

        {/* Messages Area */}
        <ScrollArea className="flex-1 p-2 sm:p-4">
          <div className="flex flex-col gap-2 pb-10">
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {currentMessage && (
              <ChatMessage key="current-message" message={currentMessage} />
            )}
            {isTyping && !currentMessage && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="p-1 sm:p-4 border-t">
          <ChatInput
            onSubmit={handleSendMessage}
            isDisabled={isTyping}
            placeholder="Type your message..."
            className="text-sm sm:text-base pb-0.5"
          />
        </div>
      </div>

      {/* Render Rename Dialog */}
      {chatToRename && (
        <ChatRenameDialog
          isOpen={isRenameDialogOpen}
          onClose={handleCloseRenameDialog}
          onRename={handleRenameChat} // Use the consolidated handler
          currentTitle={chatToRename.title}
        />
      )}

      {/* Render Archive Dialog */}
      <ChatArchiveDialog
        isOpen={isArchiveDialogOpen}
        onClose={handleCloseArchiveDialog}
        activeSessions={sessions}
        archivedSessions={archivedSessions}
        onSessionsUpdate={fetchSessions}
      />
    </div>
  );
}
