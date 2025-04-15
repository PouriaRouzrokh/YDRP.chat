"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ChevronLeft, ChevronRight, User, Bot } from "lucide-react";
import { cn } from "@/lib/utils";
import Link from "next/link";

// Define the type for featured chat items
interface FeaturedChat {
  id: number;
  title: string;
  userMessage: string;
  assistantMessage: string;
  imageUrl: string;
  category: string;
  path: string;
}

export function FeaturedChats() {
  const [featuredChats, setFeaturedChats] = useState<FeaturedChat[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [direction, setDirection] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch featured chats data from the JSON file
  useEffect(() => {
    async function fetchFeaturedChats() {
      try {
        const response = await fetch("/data/featured-chats.json");

        if (!response.ok) {
          throw new Error(`Failed to fetch featured chats: ${response.status}`);
        }

        const data = await response.json();
        setFeaturedChats(data);
        setIsLoading(false);
      } catch (error) {
        console.error("Error fetching featured chats:", error);
        setIsLoading(false);
      }
    }

    fetchFeaturedChats();
  }, []);

  const handleNext = useCallback(() => {
    if (featuredChats.length === 0) return;

    setDirection(1);
    setCurrentIndex((prevIndex) => (prevIndex + 1) % featuredChats.length);
  }, [featuredChats.length]);

  const handlePrevious = useCallback(() => {
    if (featuredChats.length === 0) return;

    setDirection(-1);
    setCurrentIndex(
      (prevIndex) =>
        (prevIndex - 1 + featuredChats.length) % featuredChats.length
    );
  }, [featuredChats.length]);

  // Auto-advance the slider every 5 seconds
  useEffect(() => {
    if (!isPaused && featuredChats.length > 0) {
      const interval = setInterval(() => {
        handleNext();
      }, 5000);

      return () => clearInterval(interval);
    }
  }, [isPaused, featuredChats.length, handleNext]);

  const variants = {
    enter: (direction: number) => ({
      x: direction > 0 ? 500 : -500,
      opacity: 0,
    }),
    center: {
      x: 0,
      opacity: 1,
    },
    exit: (direction: number) => ({
      x: direction < 0 ? 500 : -500,
      opacity: 0,
    }),
  };

  // Show loading state or empty state if no data
  if (isLoading) {
    return (
      <div className="w-full max-w-5xl mx-auto px-4 py-8">
        <h2 className="text-2xl md:text-3xl font-medium text-center mb-8 text-muted-foreground">
          Featured Conversations
        </h2>
        <div className="h-[400px] flex items-center justify-center">
          <div className="animate-pulse text-muted-foreground">
            Loading featured chats...
          </div>
        </div>
      </div>
    );
  }

  if (featuredChats.length === 0) {
    return (
      <div className="w-full max-w-5xl mx-auto px-4 py-8">
        <h2 className="text-2xl md:text-3xl font-medium text-center mb-8 text-muted-foreground">
          Featured Conversations
        </h2>
        <div className="h-[400px] flex items-center justify-center">
          <div className="text-muted-foreground">
            No featured chats available at this time.
          </div>
        </div>
      </div>
    );
  }

  const current = featuredChats[currentIndex];

  return (
    <div className="w-full max-w-5xl mx-auto px-4 py-8">
      <h2 className="text-2xl md:text-3xl font-medium text-center mb-8 text-muted-foreground">
        Featured Conversations
      </h2>

      <div
        className="relative overflow-hidden rounded-xl bg-card shadow-lg border"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        <div className="absolute top-4 right-4 z-10">
          <span className="inline-block px-3 py-1 text-xs font-medium rounded-full bg-primary/10 text-primary backdrop-blur-sm">
            {current.category}
          </span>
        </div>

        <AnimatePresence mode="wait" custom={direction} initial={false}>
          <motion.div
            key={current.id}
            custom={direction}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{
              type: "spring",
              stiffness: 300,
              damping: 30,
              duration: 0.5,
            }}
            className="w-full"
          >
            <div className="grid md:grid-cols-2 gap-0">
              <div className="p-6 md:p-8 flex flex-col justify-between">
                <div>
                  <h3 className="text-xl md:text-2xl font-bold mb-4">
                    {current.title}
                  </h3>
                  <div className="space-y-4">
                    <Card className="bg-green-100 dark:bg-emerald-700 text-gray-800 dark:text-gray-50 border-green-200 dark:border-emerald-600 shadow-sm transition-all">
                      <CardContent className="p-3 md:p-4 text-sm md:text-base">
                        <div className="flex items-start">
                          <div className="shrink-0 mr-3 mt-0.5 bg-green-200 dark:bg-emerald-600 h-6 w-6 rounded-full flex items-center justify-center border border-green-300 dark:border-emerald-500">
                            <User className="h-3.5 w-3.5 text-green-800 dark:text-white" />
                          </div>
                          <div className="flex-1 break-words">
                            {current.userMessage}
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="bg-gray-100 dark:bg-gray-800 border-gray-200 dark:border-gray-700 shadow-sm transition-all">
                      <CardContent className="p-3 md:p-4 text-sm md:text-base">
                        <div className="flex items-start">
                          <div className="shrink-0 mr-3 mt-0.5 bg-blue-200 dark:bg-blue-600 h-6 w-6 rounded-full flex items-center justify-center border border-blue-300 dark:border-blue-500">
                            <Bot className="h-3.5 w-3.5 text-blue-800 dark:text-white" />
                          </div>
                          <div className="flex-1 whitespace-pre-line break-words">
                            {current.assistantMessage}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                </div>

                <Button asChild className="mt-6 w-full sm:w-auto">
                  <Link
                    href={`/chat?message=${encodeURIComponent(
                      current.userMessage
                    )}`}
                  >
                    Start Similar Chat
                  </Link>
                </Button>
              </div>

              <div className="aspect-video md:aspect-auto bg-muted relative h-[200px] md:h-full overflow-hidden">
                <div
                  className="absolute inset-0 bg-cover bg-center transition-transform duration-10000 hover:scale-110"
                  style={{
                    backgroundImage: `url(${current.imageUrl})`,
                    backgroundSize: "cover",
                  }}
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent" />
              </div>
            </div>
          </motion.div>
        </AnimatePresence>

        <Button
          variant="ghost"
          size="icon"
          className="absolute left-2 top-1/2 -translate-y-1/2 bg-background/80 hover:bg-background/90 rounded-full z-10 shadow-md"
          onClick={handlePrevious}
        >
          <ChevronLeft className="h-6 w-6" />
          <span className="sr-only">Previous</span>
        </Button>

        <Button
          variant="ghost"
          size="icon"
          className="absolute right-2 top-1/2 -translate-y-1/2 bg-background/80 hover:bg-background/90 rounded-full z-10 shadow-md"
          onClick={handleNext}
        >
          <ChevronRight className="h-6 w-6" />
          <span className="sr-only">Next</span>
        </Button>

        {/* Slide indicators */}
        <div className="absolute bottom-4 left-0 right-0 flex justify-center gap-2 z-10">
          {featuredChats.map((_, index) => (
            <button
              key={index}
              className={cn(
                "w-2.5 h-2.5 rounded-full transition-all",
                index === currentIndex
                  ? "bg-primary w-5"
                  : "bg-primary/30 hover:bg-primary/50"
              )}
              onClick={() => {
                setDirection(index > currentIndex ? 1 : -1);
                setCurrentIndex(index);
              }}
              aria-label={`Go to slide ${index + 1}`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
