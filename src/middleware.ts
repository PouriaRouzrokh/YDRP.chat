import { NextResponse, type NextRequest } from "next/server";
import { siteConfig } from "./config/site";

export function middleware(request: NextRequest) {
  // Get the pathname of the request
  const path = request.nextUrl.pathname;

  // Define public paths that don't require authentication
  const isPublicPath = path === "/login";

  // Check if user is authenticated or admin mode is enabled
  // Look for any cookie that starts with 'ydrp_auth' since we'll be setting
  // our auth cookie client-side with js-cookie
  const hasAuthCookie = request.cookies
    .getAll()
    .some((cookie) => cookie.name === "ydrp_auth");
  const isAuthenticated = hasAuthCookie || siteConfig.settings.adminMode;

  // If the path is public and user is authenticated, redirect to home
  if (isPublicPath && isAuthenticated) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  // If the path is protected and user is not authenticated, redirect to login
  if (!isPublicPath && !isAuthenticated) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Otherwise, continue
  return NextResponse.next();
}

// Configure the middleware to run on specific paths
export const config = {
  matcher: [
    // Match all paths except for static files, api routes, and _next
    "/((?!api|_next/static|_next/image|favicon.ico).*)",
  ],
};
