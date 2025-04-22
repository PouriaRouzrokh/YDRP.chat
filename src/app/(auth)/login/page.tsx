"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useForm } from "react-hook-form";
import { Alert, AlertDescription } from "@/components/ui/alert";

// Define form validation schema
const formSchema = z.object({
  email: z.string().email({
    message: "Please enter a valid email address.",
  }),
  password: z.string(),
});

// Create a separate client component for the form to handle searchParams
function LoginForm() {
  const { login, isLoading, error, isAdminMode, isAuthenticated } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [sessionExpired, setSessionExpired] = useState(false);

  // Initialize form with validation
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: "user@example.com", // Pre-filled for demo
      password: "password123", // Pre-filled for demo
    },
  });

  // Check for expired session parameter
  useEffect(() => {
    // Check if redirected from expired session
    const expired = searchParams.get("expired") === "true";

    if (expired) {
      setSessionExpired(true);
      toast.error("Session expired", {
        description: "Your session has expired. Please log in again.",
      });
    }
  }, [searchParams]);

  // Handle form submission
  async function onSubmit(values: z.infer<typeof formSchema>) {
    try {
      await login(values.email, values.password);
      toast.success("Login successful", {
        description: "Welcome to YDR Policy Chatbot",
      });

      // Reset expired session state
      setSessionExpired(false);

      // Force redirect after successful login
      router.push("/chat");
    } catch {
      // Error is handled by the auth context and displayed below
    }
  }

  // Redirect if already authenticated or in admin mode
  useEffect(() => {
    if (isAuthenticated || isAdminMode) {
      router.push("/chat");
    }
  }, [isAuthenticated, isAdminMode, router]);

  // If admin mode is enabled, show loading state while redirecting
  if (isAdminMode || isAuthenticated) {
    return (
      <div className="flex h-[calc(100vh-3.5rem)] items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="w-full flex justify-center items-center min-h-[calc(100vh-3.5rem)] py-8">
      <Card className="w-full max-w-md mx-4">
        <CardHeader>
          <CardTitle className="text-2xl">Login</CardTitle>
          <CardDescription>
            Sign in to access Yale Radiology Policies.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sessionExpired && (
            <Alert variant="destructive" className="mb-6">
              <AlertDescription>
                Your session has expired. Please log in again to continue.
              </AlertDescription>
            </Alert>
          )}

          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="space-y-6"
              noValidate
            >
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        placeholder="Enter your email"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input
                        type="password"
                        placeholder="Enter your password"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {error && (
                <div className="p-3 rounded-md bg-destructive/10 text-destructive text-sm">
                  {error}
                </div>
              )}

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? (
                  <span className="flex items-center justify-center">
                    <LoadingSpinner size="sm" className="mr-2" />
                    Signing in...
                  </span>
                ) : (
                  "Sign in"
                )}
              </Button>
            </form>
          </Form>
        </CardContent>
        <CardFooter className="flex flex-col space-y-2 items-start">
          <div className="text-sm text-muted-foreground">
            <span>Demo credentials pre-filled for you.</span>
          </div>
          <div className="text-sm text-muted-foreground">
            <span>For assistance, please contact </span>
            <a
              href="mailto:it-support@yale-rad.edu"
              className="text-primary hover:underline"
            >
              IT Support
            </a>
          </div>
        </CardFooter>
      </Card>
    </div>
  );
}

// Main page component with Suspense boundary
export default function LoginPage() {
  return (
    <Suspense fallback={<div className="flex h-[calc(100vh-3.5rem)] items-center justify-center"><LoadingSpinner size="lg" /></div>}>
      <LoginForm />
    </Suspense>
  );
}
