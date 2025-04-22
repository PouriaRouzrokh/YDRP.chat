"use client";

import { useState, useRef, useEffect, useCallback, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PanelLeftOpen, Edit } from "lucide-react";
import { ChatSidebar, ChatSession } from "@/components/chat/chat-sidebar";
import { ChatInput } from "@/components/chat/chat-input";
import { ChatFooterSpacer } from "@/components/chat/chat-footer-spacer";
import {
  ChatMessage,
  Message,
  TypingIndicator,
} from "@/components/chat/message";
import { motion, AnimatePresence } from "framer-motion";
import {
  fadeInUp,
  slideInLeft,
  slideInRight,
  staggerContainer,
} from "@/lib/animation-variants";
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
import { ChatRenameDialog } from "@/components/chat/chat-rename-dialog";
import { ChatArchiveDialog } from "@/components/chat/chat-archive-dialog";
import { LoadingSpinner } from "@/components/ui/loading-spinner";

// Client component that uses useSearchParams
function ChatPageContent() {
  const searchParams = useSearchParams();
  const initialMessage = searchParams.get("message");
  const chatId = searchParams.get("id");
  const router = useRouter();

  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [initialMessageSent, setInitialMessageSent] = useState(false);
  const [loading, setLoading] = useState(true);

  // State for rename dialog
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const [chatToRename, setChatToRename] = useState<ChatSession | null>(null);
  const [isArchiveDialogOpen, setIsArchiveDialogOpen] = useState(false);

  // Fetch available chat sessions from the server
  const fetchSessions = useCallback(async () => {
    try {
      setLoading(true);

      // Fetch active chats
      const activeChats = await chatService.getChatsWithMessageCounts(
        0,
        100,
        false
      );

      // Fetch archived chats
      const archivedChats = await chatService.getChatsWithMessageCounts(
        0,
        100,
        true
      );

      // Combine and format all chats
      const allChats = [...activeChats, ...archivedChats];
      const formattedSessions: ChatSession[] = allChats.map((chat) => ({
        id: String(chat.id),
        title: chat.title,
        createdAt: new Date(),
        lastMessageTime: chat.lastMessageTime,
        messageCount: chat.messageCount,
        isArchived: chat.isArchived,
      }));

      setChatSessions(formattedSessions);

      // If chat ID was specified in URL, select it explicitly.
      // We no longer automatically select the first session on load.
      if (chatId && !activeSessionId) {
        setActiveSessionId(chatId);
      }
    } catch (error) {
      console.error("Error fetching chat sessions:", error);
      toast.error("Failed to load chat history");
    } finally {
      setLoading(false);
    }
  }, [chatId, activeSessionId]);

  // Fetch sessions on mount and when dependencies change
  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // This effect now ONLY handles clearing messages when no session is active.
  // Fetching messages is now triggered ONLY by handleSelectChat.
  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
    }
  }, [activeSessionId]);

  // Add a new effect to load messages when a chat ID is provided in URL
  useEffect(() => {
    if (chatId && activeSessionId === chatId) {
      // Call directly without adding to dependency array
      (async () => {
        try {
          setLoading(true);
          const messageData = await chatService.getChatMessages(Number(chatId));
          const formattedMessages =
            chatService.formatMessagesForUI(messageData);
          // Convert to Message type (should be compatible)
          const msgArray: Message[] = formattedMessages.map((msg) => ({
            id: String(msg.id),
            content: msg.content,
            role: msg.role,
            timestamp: msg.timestamp,
          }));
          setMessages(msgArray);
        } catch (error) {
          console.error(`Error fetching messages for chat ${chatId}:`, error);
          toast.error("Failed to load messages");
        } finally {
          setLoading(false);
        }
      })();
    }
  }, [chatId, activeSessionId]);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Fetch messages for a specific session
  const fetchMessagesForSession = async (sessionId: number) => {
    try {
      setLoading(true);
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
      setLoading(false);
    } catch (error) {
      console.error(`Error fetching messages for session ${sessionId}:`, error);
      toast.error("Failed to load messages");
      setLoading(false);
    }
  };

  // Handle streaming chunks with useCallback
  const handleStreamChunk = useCallback(
    (chunk: StreamChunk) => {
      if (chunk.type === "chat_info") {
        const infoChunk = chunk as ChatInfoChunk;
        // Update active session ID ONLY if it was previously null (i.e., for a new chat)
        if (!activeSessionId) {
          const newChatId = String(infoChunk.data.chat_id);
          setActiveSessionId(newChatId);

          // Create new session in the sidebar
          const newSession: ChatSession = {
            id: newChatId,
            title: infoChunk.data.title || "New Chat",
            createdAt: new Date(),
            lastMessageTime: new Date(),
            messageCount: 1, // Initial user message counts as 1
          };
          setChatSessions((prev) => [newSession, ...prev]);
        }
      } else if (chunk.type === "text_delta") {
        const textChunk = chunk as TextDeltaChunk;
        setIsTyping(true);
        setMessages((prevMessages) => {
          const lastMessage = prevMessages[prevMessages.length - 1];

          // If the last message exists and is from the assistant, append the delta
          if (lastMessage && lastMessage.role === "assistant") {
            return [
              ...prevMessages.slice(0, -1),
              {
                ...lastMessage,
                content: lastMessage.content + textChunk.data.delta,
              },
            ];
          } else {
            // Otherwise, add a new assistant message
            return [
              ...prevMessages,
              {
                id: `assistant-${Date.now()}`,
                content: textChunk.data.delta,
                role: "assistant",
                timestamp: new Date(),
              },
            ];
          }
        });
      } else if (chunk.type === "status") {
        const statusChunk = chunk as StatusChunk;
        if (statusChunk.data.status === "complete") {
          // No need to finalize message separately, it's already in the messages array.
          setIsTyping(false);
          // Update session metadata if needed (e.g., last message time)
          if (activeSessionId) {
            const chatIdStr = String(statusChunk.data.chat_id);
            setChatSessions((prev) =>
              prev.map((session) =>
                session.id === chatIdStr
                  ? {
                      ...session,
                      lastMessageTime: new Date(),
                      // Optionally update message count if necessary, though it might be complex here
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
    },
    [activeSessionId]
  );

  const handleNewChat = useCallback(() => {
    setActiveSessionId(null);
    // Make sure URL params are updated without adding to history
    router.replace("/chat", { scroll: false });
  }, [router]);

  // Handle sending a message
  const handleSendMessage = useCallback((content: string) => {
    if (!content.trim()) return;

    // Mark initialMessage as sent if this message matches it
    if (initialMessage && content === initialMessage) {
      setInitialMessageSent(true);
    }

    // Create user message
    const userMessage: Message = {
      id: Date.now().toString(),
      content,
      role: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsTyping(true);

    // Create request object - for new chats, chat_id should be undefined
    // The server will create a new chat and return its ID in the chat_info chunk
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
  }, [activeSessionId, initialMessage, handleStreamChunk]);

  // Handle initial message from URL if present
  useEffect(() => {
    if (initialMessage && !initialMessageSent && !activeSessionId) {
      handleSendMessage(initialMessage);
      setInitialMessageSent(true);
    }
  }, [initialMessage, initialMessageSent, activeSessionId, handleSendMessage]);

  // Handle selecting a chat session
  const handleSelectChat = useCallback((chatId: string) => {
    setActiveSessionId(chatId);
    // Fetch messages for the selected chat ID
    fetchMessagesForSession(Number(chatId));
  }, []);

  const toggleSidebar = useCallback(() => {
    setIsSidebarOpen((prev) => !prev);
  }, []);

  // Handle opening the rename dialog for a chat
  const handleOpenRenameDialog = useCallback((chatId: string | null) => {
    if (!chatId) return;
    const chat = chatSessions.find((session) => session.id === chatId);
    if (chat) {
      setChatToRename(chat);
      setIsRenameDialogOpen(true);
    }
  }, [chatSessions]);

  // Handle closing the rename dialog
  const handleCloseRenameDialog = useCallback(() => {
    setIsRenameDialogOpen(false);
    setChatToRename(null);
  }, []);

  // Handle renaming a chat
  const handleRenameChat = useCallback(async (newTitle: string) => {
    if (!chatToRename) return;

    try {
      // Update in backend
      await chatService.renameChat(Number(chatToRename.id), newTitle);

      // Update in frontend
      setChatSessions((prev) =>
        prev.map((session) =>
          session.id === chatToRename.id
            ? { ...session, title: newTitle }
            : session
        )
      );

      toast.success("Chat renamed successfully");
    } catch (error) {
      console.error("Error renaming chat:", error);
      toast.error("Failed to rename chat");
    } finally {
      handleCloseRenameDialog();
    }
  }, [chatToRename, handleCloseRenameDialog]);

  // Handle opening the archive dialog
  const handleOpenArchiveDialog = useCallback(() => {
    setIsArchiveDialogOpen(true);
  }, []);

  // Handle closing the archive dialog
  const handleCloseArchiveDialog = useCallback(() => {
    setIsArchiveDialogOpen(false);
  }, []);

  return (
    <motion.div
      className="flex h-[calc(100vh-7rem)] overflow-hidden"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {/* Sidebar - only visible on medium screens and up */}
      <AnimatePresence>
        {isSidebarOpen && (
          <motion.div
            className="hidden md:block h-full overflow-hidden"
            variants={slideInLeft}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            <ChatSidebar
              sessions={chatSessions.filter((session) => !session.isArchived)}
              activeSessionId={activeSessionId}
              onSessionSelect={handleSelectChat}
              onNewChat={handleNewChat}
              isCollapsed={!isSidebarOpen}
              onOpenRenameDialog={handleOpenRenameDialog}
              onOpenArchiveDialog={handleOpenArchiveDialog}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main chat area */}
      <motion.div
        className="flex flex-col flex-1 h-full px-2 sm:px-4"
        variants={fadeInUp}
        initial="hidden"
        animate="visible"
      >
        {/* Chat header */}
        <motion.div
          className="flex items-center justify-between py-2 px-2 sm:p-4 border-b"
          variants={slideInRight}
          initial="hidden"
          animate="visible"
        >
          <div className="flex items-center">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleSidebar}
              className="hidden md:flex mr-2"
            >
              <PanelLeftOpen className="h-5 w-5" />
              <span className="sr-only">Toggle sidebar</span>
            </Button>
            <h2 className="text-lg font-medium">
              {chatSessions.find((chat) => chat.id === activeSessionId)
                ?.title || "New Conversation"}
            </h2>
            {activeSessionId && (
              <Button
                variant="ghost"
                size="icon"
                className="ml-1 sm:ml-2 h-6 w-6"
                onClick={() => handleOpenRenameDialog(activeSessionId)}
                aria-label="Rename Chat"
              >
                <Edit className="h-4 w-4" />
              </Button>
            )}
          </div>

          {/* Mobile-only New Chat button */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleNewChat}
            className="md:hidden"
          >
            New Chat
          </Button>
        </motion.div>

        {/* Fixed height container for messages and input */}
        <div className="flex flex-col h-[calc(100%-4rem)]">
          {/* Messages area with flex-1 to fill available space */}
          <div className="flex-1 overflow-hidden">
            <ScrollArea className="h-full p-2 sm:p-4">
              <motion.div
                className="flex flex-col pb-2"
                variants={fadeInUp}
                initial="hidden"
                animate="visible"
              >
                <AnimatePresence mode="wait">
                  {loading ? (
                    <motion.div
                      className="flex items-center justify-center h-full p-8 text-center text-muted-foreground"
                      variants={fadeInUp}
                      key="loading-state"
                    >
                      <div>Loading...</div>
                    </motion.div>
                  ) : messages.length === 0 ? (
                    <motion.div
                      className="flex items-center justify-center h-full p-8 text-center text-muted-foreground"
                      variants={fadeInUp}
                      key="empty-state"
                    >
                      <div className="text-center">
                        <h3 className="text-lg font-medium mb-2">
                          Welcome to Yale Department of Radiology Policy Chatbot
                        </h3>
                        <p className="max-w-md mx-auto">
                          Ask questions about department policies, safety
                          protocols, or procedural guidelines.
                        </p>
                        <br />
                        <p className="max-w-md mx-auto border-4">
                          Please note that this chat is not HIPPA safe, so
                          please avoid entering sensitive information.
                        </p>
                      </div>
                    </motion.div>
                  ) : (
                    <motion.div
                      key="message-list"
                      variants={staggerContainer}
                      initial="hidden"
                      animate="visible"
                    >
                      {messages.map((message) => (
                        <ChatMessage key={message.id} message={message} />
                      ))}
                      {/* Show typing indicator separately - after messages */}
                      {isTyping && <TypingIndicator />}
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Remove the old typing indicator position */}
                <div ref={messagesEndRef} />
              </motion.div>
            </ScrollArea>
          </div>

          {/* Input area with fixed height */}
          <motion.div
            className="pb-0.5 pt-0.5 sm:pb-2 sm:pt-2"
            variants={fadeInUp}
            initial="hidden"
            animate="visible"
            transition={{ delay: 0.2 }}
          >
            <ChatInput
              onSubmit={handleSendMessage}
              isDisabled={isTyping}
              placeholder="Type your message..."
              className="pb-0 text-sm sm:text-base"
              initialValue={
                initialMessage && !initialMessageSent ? initialMessage : ""
              }
              autoSubmit={true}
            />
          </motion.div>

          {/* Spacer to prevent overlap with fixed footer */}
          <ChatFooterSpacer />
        </div>
      </motion.div>

      {/* Render Rename Dialog */}
      {chatToRename && (
        <ChatRenameDialog
          isOpen={isRenameDialogOpen}
          onClose={handleCloseRenameDialog}
          onRename={handleRenameChat}
          currentTitle={chatToRename.title}
        />
      )}

      {/* Render Archive Dialog */}
      <ChatArchiveDialog
        isOpen={isArchiveDialogOpen}
        onClose={handleCloseArchiveDialog}
        activeSessions={chatSessions.filter((session) => !session.isArchived)}
        archivedSessions={chatSessions.filter((session) => session.isArchived)}
        onSessionsUpdate={fetchSessions}
      />
    </motion.div>
  );
}

// Main page component with Suspense boundary
export default function ChatPage() {
  return (
    <Suspense fallback={<div className="flex h-[calc(100vh-3.5rem)] items-center justify-center"><LoadingSpinner size="lg" /></div>}>
      <ChatPageContent />
    </Suspense>
  );
}
