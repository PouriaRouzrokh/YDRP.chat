"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { motion } from "framer-motion";
import { fadeInUp, staggerContainer } from "@/lib/animation-variants";

export default function HomePage() {
  const { isAuthenticated, isAdminMode } = useAuth();

  return (
    <motion.div
      className="flex flex-col items-center justify-center min-h-[80vh] text-center p-4"
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
    >
      <motion.div className="max-w-3xl mx-auto" variants={fadeInUp}>
        <h1 className="text-4xl font-bold tracking-tight mb-6">
          Yale Department of Radiology Policy Chatbot
        </h1>
        <p className="text-xl text-muted-foreground mb-8">
          Access and search the Yale Department of Radiology Policies with
          natural language queries
        </p>
      </motion.div>

      <motion.div
        className="flex gap-4 flex-wrap justify-center"
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
  );
}
