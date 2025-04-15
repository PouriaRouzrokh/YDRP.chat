"use client";

import React from "react";
import { motion } from "framer-motion";
import {
  fadeInUp,
  scaleIn,
  slideInLeft,
  slideInRight,
} from "@/lib/animation-variants";

interface PageTransitionProps {
  children: React.ReactNode;
  className?: string;
  variant?: "fadeUp" | "scale" | "slideLeft" | "slideRight";
}

export function PageTransition({
  children,
  className = "",
  variant = "fadeUp",
}: PageTransitionProps) {
  // Select the appropriate animation variant based on the prop
  const getVariant = () => {
    switch (variant) {
      case "scale":
        return scaleIn;
      case "slideLeft":
        return slideInLeft;
      case "slideRight":
        return slideInRight;
      case "fadeUp":
      default:
        return fadeInUp;
    }
  };

  return (
    <motion.div
      variants={getVariant()}
      initial="hidden"
      animate="visible"
      exit="exit"
      className={className}
    >
      {children}
    </motion.div>
  );
}
