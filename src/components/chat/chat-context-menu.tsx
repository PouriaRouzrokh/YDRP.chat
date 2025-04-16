import { FC, useState, useEffect, useRef } from "react";
import { Edit } from "lucide-react";
import { ChatSession } from "./chat-sidebar";

interface ChatContextMenuProps {
  chat: ChatSession;
  onOpenRenameDialog: (chatId: string) => void;
  children: React.ReactNode;
}

export const ChatContextMenu: FC<ChatContextMenuProps> = ({
  chat,
  onOpenRenameDialog,
  children,
}) => {
  const [showMenu, setShowMenu] = useState(false);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const menuRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleContextMenu = (e: React.MouseEvent) => {
    // Prevent default browser context menu
    e.preventDefault();

    // Calculate position for the menu
    setPosition({
      x: e.clientX,
      y: e.clientY,
    });

    // Show the custom context menu
    setShowMenu(true);
  };

  // Handle clicks outside the menu to close it
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false);
      }
    };

    if (showMenu) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showMenu]);

  // Close menu on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setShowMenu(false);
      }
    };

    if (showMenu) {
      document.addEventListener("keydown", handleKeyDown);
    }

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [showMenu]);

  return (
    <div
      ref={containerRef}
      className="relative w-full"
      onContextMenu={handleContextMenu}
    >
      {/* The child component (button) */}
      {children}

      {/* Custom context menu */}
      {showMenu && (
        <div
          ref={menuRef}
          className="absolute z-50 min-w-[160px] overflow-hidden rounded-md border bg-popover p-1 shadow-md animate-in fade-in-0 zoom-in-95"
          style={{
            position: "fixed",
            left: `${position.x}px`,
            top: `${position.y}px`,
          }}
        >
          <button
            className="relative flex w-full cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
            onClick={() => {
              onOpenRenameDialog(chat.id);
              setShowMenu(false);
            }}
          >
            <Edit className="mr-2 h-4 w-4" />
            <span>Rename</span>
          </button>
        </div>
      )}
    </div>
  );
};
