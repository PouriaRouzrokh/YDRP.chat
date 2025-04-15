import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// List of paths that require authentication
const PROTECTED_PATHS = ["/chat", "/history", "/profile"];

// Check if the path is protected
function isProtectedPath(path: string): boolean {
  return PROTECTED_PATHS.some((protectedPath) =>
    path.startsWith(protectedPath)
  );
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check for authentication
  const token = request.cookies.get("ydrp_auth")?.value;

  // Check for admin mode
  const adminMode = process.env.NEXT_PUBLIC_ADMIN_MODE === "true";

  // Log debug info
  console.log("Middleware: ", {
    pathname,
    token: !!token,
    adminMode,
    isProtected: isProtectedPath(pathname),
  });

  // If admin mode is enabled, allow all access
  if (adminMode) {
    return NextResponse.next();
  }

  // If trying to access a protected path without being authenticated
  if (isProtectedPath(pathname) && !token) {
    console.log("Redirecting to login page");
    // Use absolute URL without parentheses
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Allow all other requests
  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.png$).*)",
  ],
};
