import { useState, useRef, KeyboardEvent, useEffect, useCallback } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { SendIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSubmit: (message: string) => void;
  isDisabled?: boolean;
  placeholder?: string;
  className?: string;
  initialValue?: string;
  autoSubmit?: boolean;
}

export function ChatInput({
  onSubmit,
  isDisabled = false,
  placeholder = "Type your message...",
  className,
  initialValue = "",
  autoSubmit = false,
}: ChatInputProps) {
  const [input, setInput] = useState(initialValue);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isInitialMount = useRef(true);

  // Auto-resize textarea when initialValue is provided
  useEffect(() => {
    if (initialValue && textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [initialValue]);

  const handleSubmit = useCallback(() => {
    const message = input.trim();
    if (message && !isDisabled) {
      onSubmit(message);
      setInput("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }
  }, [input, isDisabled, onSubmit]);

  // Auto-submit if enabled and initialValue is provided
  useEffect(() => {
    if (autoSubmit && initialValue && isInitialMount.current) {
      isInitialMount.current = false;

      // Use a short delay to ensure the UI is rendered first
      const timer = setTimeout(() => {
        handleSubmit();
      }, 300);

      return () => clearTimeout(timer);
    }
  }, [autoSubmit, initialValue, handleSubmit]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);

    // Auto-resize textarea
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  return (
    <div
      className={cn("flex items-center gap-1 sm:gap-2 pb-2 md:pb-0", className)}
    >
      <Textarea
        ref={textareaRef}
        value={input}
        onChange={handleTextareaChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isDisabled}
        className="resize-none min-h-[40px] md:min-h-[60px] max-h-[150px] sm:max-h-[200px] flex-1 py-2 px-2 sm:px-3 md:py-4 leading-relaxed text-sm sm:text-base"
        rows={1}
      />
      <Button
        onClick={handleSubmit}
        disabled={isDisabled || !input.trim()}
        size="icon"
        className="h-[40px] w-[40px] sm:h-[45px] sm:w-[45px] md:h-[60px] md:w-[60px] shrink-0"
      >
        <SendIcon className="h-3 w-3 sm:h-4 sm:w-4 md:h-5 md:w-5" />
      </Button>
    </div>
  );
}
