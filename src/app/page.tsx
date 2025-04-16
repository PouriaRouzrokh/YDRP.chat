"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { motion } from "framer-motion";
import { fadeInUp, staggerContainer } from "@/lib/animation-variants";
import { FeaturedChats } from "@/components/home/featured-chats";
import { ChevronDown, Zap, Clock, Search } from "lucide-react";

export default function HomePage() {
  const { isAuthenticated, isAdminMode } = useAuth();

  return (
    <motion.div
      className="flex flex-col items-center"
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
    >
      {/* Hero Section - Full viewport height on desktop */}
      <section className="w-full min-h-[calc(100vh-5rem)] flex flex-col justify-center items-center py-8 md:py-12 px-4">
        <motion.div
          className="max-w-3xl mx-auto text-center flex-1 flex flex-col justify-center py-8 md:py-12"
          variants={fadeInUp}
        >
          {/* Content area with transparent background */}
          <div className="relative rounded-2xl overflow-hidden p-8 pb-4 md:p-10 md:pb-6 border border-primary/10 flex items-center justify-center mb-8">
            {/* Content with relative positioning */}
            <div className="relative z-10 flex flex-col items-center justify-center w-full">
              <div className="text-center mb-8 md:mb-12">
                <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
                  Yale Department of Radiology
                </h1>
                <h1 className="text-4xl md:text-3xl font-bold tracking-tight">
                  Policy Chatbot
                </h1>
              </div>

              <p className="text-xl text-center text-muted-foreground mb-12 md:mb-14 max-w-2xl mx-auto leading-relaxed">
                Access and search the Yale Department of Radiology Policies with
                natural language queries
              </p>

              {/* Key benefits */}
              <div className="flex flex-col md:flex-row justify-center items-center gap-6 md:gap-12 mb-0 w-full max-w-2xl mx-auto">
                <motion.div
                  className="flex items-center gap-3 justify-center"
                  variants={fadeInUp}
                  transition={{ delay: 0.1 }}
                >
                  <div className="p-2.5 rounded-full bg-primary/10 flex-shrink-0">
                    <Zap className="h-5 w-5 text-primary" />
                  </div>
                  <span className="text-base font-medium">
                    Instant Policy Answers
                  </span>
                </motion.div>

                <motion.div
                  className="flex items-center gap-3 justify-center"
                  variants={fadeInUp}
                  transition={{ delay: 0.2 }}
                >
                  <div className="p-2.5 rounded-full bg-primary/10 flex-shrink-0">
                    <Clock className="h-5 w-5 text-primary" />
                  </div>
                  <span className="text-base font-medium">Available 24/7</span>
                </motion.div>

                <motion.div
                  className="flex items-center gap-3 justify-center"
                  variants={fadeInUp}
                  transition={{ delay: 0.3 }}
                >
                  <div className="p-2.5 rounded-full bg-primary/10 flex-shrink-0">
                    <Search className="h-5 w-5 text-primary" />
                  </div>
                  <span className="text-base font-medium">
                    Search Official Documents
                  </span>
                </motion.div>
              </div>
            </div>
          </div>

          <motion.div
            className="flex gap-4 flex-wrap justify-center pt-4 mt-4"
            variants={fadeInUp}
          >
            {isAuthenticated || isAdminMode ? (
              <Button asChild size="lg">
                <Link href="/chat">Start a Chat</Link>
              </Button>
            ) : (
              <Button asChild size="lg">
                <Link href="/login">Sign In</Link>
              </Button>
            )}
            <Button asChild variant="outline" size="lg">
              <Link href="/about">Learn More</Link>
            </Button>
          </motion.div>
        </motion.div>

        {/* Scroll indicator */}
        <div className="mt-10 md:mt-auto mb-8 text-center animate-pulse">
          <p className="text-muted-foreground mb-4">
            Scroll down to explore how others are using the chatbot...
          </p>
          <motion.div
            animate={{ y: [0, 10, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
          >
            <ChevronDown className="h-6 w-6 mx-auto text-muted-foreground" />
          </motion.div>
        </div>
      </section>

      {/* Compact separator with more emphasis */}
      <div className="w-full max-w-2xl mx-auto px-4 py-4 bg-background">
        <div className="flex items-center justify-center space-x-3">
          <div className="w-2/5 h-[2px] bg-gradient-to-r from-transparent to-border/80"></div>
          <div className="w-3 h-3 rounded-full bg-border"></div>
          <div className="w-2/5 h-[2px] bg-gradient-to-l from-transparent to-border/80"></div>
        </div>
      </div>

      {/* Featured Chats Section with transparent background */}
      <section className="w-full py-16">
        <motion.div className="relative z-10" variants={fadeInUp}>
          <FeaturedChats />
        </motion.div>
      </section>
    </motion.div>
  );
}
