# API Services

This directory contains all the services for interacting with the backend API.

## API Client

The `api-client.ts` file provides a wrapper around fetch that handles:

- Authentication token management
- Error response handling
- Session expiry detection
- Automatic redirection to login page when tokens expire

## Token Expiration Handling

When a user's authentication token expires, the following happens:

1. The API client detects a 401 Unauthorized response from any API call
2. It logs the user out (clearing all auth state)
3. It redirects the user to the login page
4. The login page will show a "Session expired" message to the user

This ensures users don't get stuck in a state where they appear logged in but can't access data.

## Services

- `auth.ts` - Authentication services (login, logout, token management)
- `chat.ts` - Chat functionality (messages, history, archiving)
- `stream.ts` - Server-sent events for streaming chat responses
- `profile.ts` - User profile information

All services use the common API client for request handling, ensuring consistent behavior when tokens expire.
