"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/contexts/AuthContext";
import { LogOut, User as UserIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import Link from "next/link";
import { useEffect } from "react";

export function UserMenu() {
  const { user, logout, isAuthenticated } = useAuth();
  const router = useRouter();

  // Debug auth state
  useEffect(() => {
    console.log("UserMenu - Auth state:", { user, isAuthenticated });
  }, [user, isAuthenticated]);

  const handleLogout = () => {
    logout();
    toast.success("Logged out successfully");
    router.push("/login");
    router.refresh(); // Force router refresh after logout
  };

  // Get initials from username
  const getInitials = (name: string) => {
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase();
  };

  // Get initials from full name or email
  const getUserInitials = () => {
    if (user?.full_name) {
      return getInitials(user.full_name);
    }
    if (user?.email) {
      return user.email.substring(0, 2).toUpperCase();
    }
    return "?";
  };

  // If not authenticated, don't render the menu
  if (!isAuthenticated || !user) {
    console.log("UserMenu not rendering - not authenticated or no user");
    return null;
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="focus:outline-none">
        <Avatar className="h-8 w-8">
          <AvatarFallback>{getUserInitials()}</AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <div className="flex items-center justify-start gap-2 p-2">
          <div className="flex flex-col space-y-0.5">
            <p className="text-sm font-medium">
              {user?.full_name || user?.email}
            </p>
            <p className="text-xs text-muted-foreground">
              {user?.is_admin ? "Administrator" : "User"}
            </p>
          </div>
        </div>
        <DropdownMenuSeparator />
        <Link href="/profile" passHref>
          <DropdownMenuItem className="cursor-pointer">
            <UserIcon className="mr-2 h-4 w-4" />
            <span>Profile</span>
          </DropdownMenuItem>
        </Link>
        <DropdownMenuItem
          className="cursor-pointer text-destructive focus:text-destructive"
          onClick={handleLogout}
        >
          <LogOut className="mr-2 h-4 w-4" />
          <span>Log out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
