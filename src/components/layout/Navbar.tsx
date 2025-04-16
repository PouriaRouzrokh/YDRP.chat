"use client";

import { useState, useEffect } from "react";
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
import { Moon, Sun, Menu, X, LogIn } from "lucide-react";

export function Navbar() {
  const { theme, toggleTheme } = useTheme();
  const { isAuthenticated, isAdminMode, user } = useAuth();
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Debug navbar auth state
  useEffect(() => {
    console.log("Navbar - Auth state:", { isAuthenticated, isAdminMode, user });
  }, [isAuthenticated, isAdminMode, user]);

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  // Only show certain menu items when authenticated
  const filteredNavigation = siteConfig.navigation.filter((item) => {
    // Always show About
    if (item.href === "/about") return true;

    // Only show authenticated routes when logged in
    return isAuthenticated || isAdminMode;
  });

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/98 backdrop-blur supports-[backdrop-filter]:bg-background/90">
      <div className="w-full px-4 md:px-8 lg:px-12 flex h-14 items-center justify-between">
        <div className="flex items-center">
          <Link href="/" className="flex items-center space-x-2 mr-4">
            <Image
              src="/Yale_logo.png"
              alt="Yale Logo"
              width={0}
              height={0}
              sizes="100vw"
              priority
              className="w-[30px] h-auto object-contain"
            />
            <span className="font-bold">{siteConfig.name}</span>
          </Link>
          <NavigationMenu className="hidden md:flex">
            <NavigationMenuList>
              {filteredNavigation.map((item) => (
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

          {/* Show user menu when authenticated, login button when not */}
          {isAuthenticated || isAdminMode ? (
            <div className="ml-4">
              <UserMenu />
            </div>
          ) : (
            <Button variant="outline" size="sm" className="ml-4" asChild>
              <Link href="/login">
                <LogIn className="h-4 w-4 mr-2" />
                <span>Login</span>
              </Link>
            </Button>
          )}

          {/* Mobile menu button */}
          <Button
            variant="outline"
            size="icon"
            className="md:hidden ml-2"
            onClick={toggleMobileMenu}
          >
            <span className="sr-only">Toggle menu</span>
            {isMobileMenuOpen ? (
              <X className="h-6 w-6" />
            ) : (
              <Menu className="h-6 w-6" />
            )}
          </Button>
        </div>
      </div>

      {/* Mobile menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden bg-background/98 border-b shadow-lg">
          <nav className="flex flex-col p-4 space-y-3">
            {filteredNavigation.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setIsMobileMenuOpen(false)}
                className={`block px-4 py-2 text-sm font-medium rounded-md ${
                  pathname === item.href
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                {item.name}
              </Link>
            ))}
            {/* Always show login in mobile menu when not authenticated */}
            {!isAuthenticated && !isAdminMode && (
              <Link
                href="/login"
                onClick={() => setIsMobileMenuOpen(false)}
                className="block px-4 py-2 text-sm font-medium rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50"
              >
                <span className="flex items-center">
                  <LogIn className="h-4 w-4 mr-2" />
                  Login
                </span>
              </Link>
            )}
          </nav>
        </div>
      )}
    </header>
  );
}
