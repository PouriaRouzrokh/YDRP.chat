"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { siteConfig } from "@/config/site";
import { useTheme } from "@/contexts/ThemeContext";
import { useAuth } from "@/contexts/AuthContext";
import { UserMenu } from "@/components/auth/user-menu";
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
} from "@/components/ui/navigation-menu";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Moon, Sun } from "lucide-react";

export function Navbar() {
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated } = useAuth();
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="w-full px-4 md:px-8 lg:px-12 flex h-14 items-center justify-between">
        <div className="flex items-center">
          <Link href="/" className="flex items-center space-x-2 mr-4">
            <Image
              src="/Yale_logo.png"
              alt="Yale Logo"
              width={30}
              height={30}
              className="object-contain"
            />
            <span className="font-bold">{siteConfig.name}</span>
          </Link>
          <NavigationMenu className="hidden md:flex">
            <NavigationMenuList>
              {siteConfig.navigation.map((item) => (
                <NavigationMenuItem key={item.href}>
                  <NavigationMenuLink asChild>
                    <Link
                      href={item.href}
                      className={`block px-4 py-2 text-sm font-medium ${
                        pathname === item.href
                          ? "text-foreground"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {item.name}
                    </Link>
                  </NavigationMenuLink>
                </NavigationMenuItem>
              ))}
            </NavigationMenuList>
          </NavigationMenu>
        </div>

        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1">
            <Sun
              className={`h-4 w-4 ${
                theme === "dark" ? "text-muted-foreground" : "text-foreground"
              }`}
            />
            <Switch
              checked={theme === "dark"}
              onCheckedChange={toggleTheme}
              aria-label="Toggle theme"
            />
            <Moon
              className={`h-4 w-4 ${
                theme === "light" ? "text-muted-foreground" : "text-foreground"
              }`}
            />
          </div>

          {isAuthenticated && (
            <div className="ml-4">
              <UserMenu />
            </div>
          )}

          {/* Mobile menu button (to be implemented in Phase 4) */}
          <Button variant="outline" size="icon" className="md:hidden ml-2">
            <span className="sr-only">Toggle menu</span>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-6 w-6"
            >
              <line x1="4" x2="20" y1="12" y2="12" />
              <line x1="4" x2="20" y1="6" y2="6" />
              <line x1="4" x2="20" y1="18" y2="18" />
            </svg>
          </Button>
        </div>
      </div>
    </header>
  );
}
