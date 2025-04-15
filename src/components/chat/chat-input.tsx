import { useState, useRef, KeyboardEvent } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { SendIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSubmit: (message: string) => void;
  isDisabled?: boolean;
  placeholder?: string;
  className?: string;
}

export function ChatInput({
  onSubmit,
  isDisabled = false,
  placeholder = "Type your message...",
  className,
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = () => {
    const message = input.trim();
    if (message && !isDisabled) {
      onSubmit(message);
      setInput("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }
  };

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
    <div className={cn("flex items-end gap-2", className)}>
      <Textarea
        ref={textareaRef}
        value={input}
        onChange={handleTextareaChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isDisabled}
        className="resize-none min-h-[60px] max-h-[200px] flex-1 pt-[18px] pb-[18px] leading-relaxed"
        rows={1}
      />
      <Button
        onClick={handleSubmit}
        disabled={isDisabled || !input.trim()}
        size="icon"
        className="h-[60px] w-[60px]"
      >
        <SendIcon className="h-5 w-5" />
      </Button>
    </div>
  );
}
