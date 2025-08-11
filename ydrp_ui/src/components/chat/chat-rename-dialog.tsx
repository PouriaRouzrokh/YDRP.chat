import { FC, useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface ChatRenameDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onRename: (newTitle: string) => void;
  currentTitle: string;
}

export const ChatRenameDialog: FC<ChatRenameDialogProps> = ({
  isOpen,
  onClose,
  onRename,
  currentTitle,
}) => {
  const [title, setTitle] = useState(currentTitle);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset the title when the dialog opens with a new current title
  useEffect(() => {
    if (isOpen) {
      setTitle(currentTitle);
      setIsSubmitting(false);
    }
  }, [isOpen, currentTitle]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (title.trim() && title.trim() !== currentTitle) {
      setIsSubmitting(true);

      try {
        // Immediately close the dialog for better UX
        onClose();

        // Call onRename with the new title
        await onRename(title.trim());
      } catch (error) {
        console.error("Error in rename dialog submit:", error);
      }
    } else if (title.trim() === currentTitle) {
      // No change, just close the dialog
      onClose();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open: boolean) => !open && onClose()}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Rename Chat</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-4 items-center gap-4">
              <Label htmlFor="chat-title" className="col-span-4">
                Chat Title
              </Label>
              <Input
                id="chat-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="col-span-4"
                autoFocus
                maxLength={255}
                placeholder="Enter a new title for this chat"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={
                !title.trim() || isSubmitting || title.trim() === currentTitle
              }
            >
              {isSubmitting ? "Saving..." : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
