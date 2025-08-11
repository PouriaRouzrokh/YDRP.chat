import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { AuthProvider } from "@/contexts/AuthContext";
import { Navbar } from "@/components/layout/Navbar";
import { Toaster } from "@/components/ui/sonner";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Yale Department of Radiology Policy Chatbot",
  description: "A chatbot for Yale Department of Radiology policies",
  icons: {
    icon: "/Yale_logo.png",
    apple: "/Yale_logo.png",
    shortcut: "/Yale_logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <ThemeProvider>
          <AuthProvider>
            {/* Fixed Background Image */}
            <div className="fixed inset-0 z-[-1] bg-background-image bg-no-repeat bg-center bg-cover pointer-events-none"></div>

            <div className="flex min-h-screen flex-col">
              <Navbar />
              <main className="flex-1 w-full px-4 md:px-8 lg:px-12 mb-16">
                {children}
              </main>
              <footer className="fixed bottom-0 left-0 right-0 py-3 px-4 md:px-8 lg:px-12 border-t text-center text-sm text-muted-foreground bg-background/98 backdrop-blur supports-[backdrop-filter]:bg-background/90 z-10">
                Yale Department of Radiology. All rights reserved. ©{" "}
                {new Date().getFullYear()}
              </footer>
            </div>
            <Toaster />
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
