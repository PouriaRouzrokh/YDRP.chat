"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { format } from "date-fns";

// Mock data for chat history
const MOCK_CHAT_HISTORY = [
  {
    id: "1",
    title: "Radiation Safety Protocols",
    lastMessageTime: new Date(Date.now() - 1000 * 60 * 30), // 30 minutes ago
    messageCount: 8,
  },
  {
    id: "2",
    title: "Patient Privacy Guidelines",
    lastMessageTime: new Date(Date.now() - 1000 * 60 * 60 * 3), // 3 hours ago
    messageCount: 5,
  },
  {
    id: "3",
    title: "Equipment Maintenance Procedures",
    lastMessageTime: new Date(Date.now() - 1000 * 60 * 60 * 24), // 1 day ago
    messageCount: 12,
  },
  {
    id: "4",
    title: "MRI Safety Requirements",
    lastMessageTime: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2), // 2 days ago
    messageCount: 7,
  },
  {
    id: "5",
    title: "COVID-19 Department Policies",
    lastMessageTime: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3), // 3 days ago
    messageCount: 15,
  },
  {
    id: "6",
    title: "Training Requirements for Residents",
    lastMessageTime: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5), // 5 days ago
    messageCount: 9,
  },
];

export default function HistoryPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [sortBy, setSortBy] = useState<"date" | "title">("date");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  // Filter chats based on search term
  const filteredChats = MOCK_CHAT_HISTORY.filter((chat) =>
    chat.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Sort chats
  const sortedChats = [...filteredChats].sort((a, b) => {
    if (sortBy === "date") {
      return b.lastMessageTime.getTime() - a.lastMessageTime.getTime();
    } else {
      return a.title.localeCompare(b.title);
    }
  });

  // Paginate
  const totalPages = Math.ceil(sortedChats.length / itemsPerPage);
  const paginatedChats = sortedChats.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  return (
    <div className="container mx-auto py-8 max-w-4xl">
      <h1 className="text-3xl font-bold mb-6">Chat History</h1>

      {/* Search and filters */}
      <div className="flex flex-col md:flex-row gap-4 mb-6">
        <Input
          placeholder="Search conversations..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="max-w-md"
        />
        <div className="flex gap-2">
          <Button
            variant={sortBy === "date" ? "default" : "outline"}
            onClick={() => setSortBy("date")}
            size="sm"
          >
            Sort by Date
          </Button>
          <Button
            variant={sortBy === "title" ? "default" : "outline"}
            onClick={() => setSortBy("title")}
            size="sm"
          >
            Sort by Title
          </Button>
        </div>
      </div>

      {/* Chat list */}
      <div className="space-y-4">
        {paginatedChats.length > 0 ? (
          paginatedChats.map((chat) => (
            <Card key={chat.id} className="hover:bg-muted/50 transition-colors">
              <CardHeader className="p-4">
                <div className="flex justify-between items-start">
                  <CardTitle className="text-lg font-medium">
                    {chat.title}
                  </CardTitle>
                  <div className="text-sm text-muted-foreground">
                    {format(chat.lastMessageTime, "MMM d, yyyy 'at' h:mm a")}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">
                    {chat.messageCount} message{chat.messageCount !== 1 && "s"}
                  </span>
                  <Button variant="outline" size="sm" asChild>
                    <Link href={`/chat?id=${chat.id}`}>View Conversation</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))
        ) : (
          <div className="text-center p-8 bg-muted/30 rounded-lg">
            <h3 className="text-lg font-medium mb-2">No conversations found</h3>
            <p className="text-muted-foreground mb-4">
              Try adjusting your search or start a new chat
            </p>
            <Button asChild>
              <Link href="/chat">Start New Chat</Link>
            </Button>
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-between items-center mt-6">
          <Button
            variant="outline"
            onClick={handlePreviousPage}
            disabled={currentPage === 1}
          >
            Previous
          </Button>
          <div className="text-sm text-muted-foreground">
            Page {currentPage} of {totalPages}
          </div>
          <Button
            variant="outline"
            onClick={handleNextPage}
            disabled={currentPage === totalPages}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
