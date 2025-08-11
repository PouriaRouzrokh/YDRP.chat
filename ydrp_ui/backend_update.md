# Backend API Update Guide for Frontend Developers (Chat Management - v0.2.0+)

**Date:** [Insert Date Here]

This document outlines the changes made to the backend API to support new chat management features: **Chat Renaming** and **Chat Archiving**. Please update your frontend implementation to leverage these new capabilities.

## Summary of Changes

1.  **`GET /chat` Endpoint:**
    - Now accepts an `?archived=true` query parameter to fetch archived chats instead of active ones.
    - The `ChatSummary` object in the response now includes an `is_archived` boolean field.
2.  **New Endpoints Added:**
    - `PATCH /chat/{chat_id}/rename`: Renames a specific chat.
    - `PATCH /chat/{chat_id}/archive`: Archives a specific chat.
    - `PATCH /chat/{chat_id}/unarchive`: Unarchives a specific chat.
    - `POST /chat/archive-all`: Archives all active chats for the user.

## Detailed Changes

### 1. Changes to Existing Endpoints

#### `GET /chat` (List User's Chats)

- **New Query Parameter:**
  - `archived` (boolean, optional):
    - If set to `true` (`/chat?archived=true`), the endpoint returns only **archived** chats belonging to the user.
    - If `false` or **omitted** (e.g., `/chat` or `/chat?archived=false`), the endpoint returns only **active** (non-archived) chats, maintaining the previous default behavior.
- **Updated Response Body (`ChatSummary` Object):**
  - Each chat summary object in the response array now includes the `is_archived` field.
  - **Example Updated `ChatSummary`:**
    ```json
    {
      "id": 123,
      "title": "MRI Contrast Policy Discussion",
      "created_at": "2023-10-27T10:00:00Z",
      "updated_at": "2023-10-27T10:05:30Z",
      "is_archived": false // <-- NEW FIELD
    }
    ```
- **Frontend Action:**
  - Update your chat list fetching logic to optionally include the `?archived=true` parameter when displaying archived chats.
  - Use the `is_archived` field in the response if needed (though filtering is now handled by the query parameter).

### 2. New Endpoints for Chat Management

**Authentication:** All the following new endpoints require the `Authorization: Bearer <token>` header.

#### 2.1 Rename Chat

- **Path:** `/chat/{chat_id}/rename`
- **Method:** `PATCH`
- **Request Body (JSON):**
  ```json
  {
    "new_title": "Your Concise New Chat Title" // String, required, max 255 chars
  }
  ```
- **Success Response (200 OK):** Returns the updated `ChatSummary` object, reflecting the new title and `updated_at` time.
  ```json
  {
    "id": 123,
    "title": "Your Concise New Chat Title", // <-- Updated
    "created_at": "2023-10-27T10:00:00Z",
    "updated_at": "2023-10-27T11:15:00Z", // <-- Updated
    "is_archived": false
  }
  ```
- **Errors:** `401` (Unauthorized), `404` (Not Found/Not Owner), `422` (Invalid Title).
- **Purpose:** Allows users to modify the title of their chat sessions.
- **Frontend Action:** Implement UI controls (e.g., an edit button/modal) to allow users to input a new title and call this endpoint. Refresh the relevant chat list upon success.

#### 2.2 Archive Chat

- **Path:** `/chat/{chat_id}/archive`
- **Method:** `PATCH`
- **Request Body:** None
- **Success Response (200 OK):** Returns the updated `ChatSummary` object with `is_archived` set to `true`.
  ```json
  {
    "id": 123,
    "title": "Original Chat Title",
    "created_at": "2023-10-27T10:00:00Z",
    "updated_at": "2023-10-27T11:20:00Z", // <-- Updated
    "is_archived": true // <-- Updated
  }
  ```
- **Errors:** `401` (Unauthorized), `404` (Not Found/Not Owner).
- **Purpose:** Marks a chat as archived, effectively removing it from the default active chat list.
- **Frontend Action:** Provide a button/option to archive a chat. Upon success, remove the chat from the _active_ list view and potentially refresh the _archived_ list view in the background or upon user navigation.

#### 2.3 Unarchive Chat

- **Path:** `/chat/{chat_id}/unarchive`
- **Method:** `PATCH`
- **Request Body:** None
- **Success Response (200 OK):** Returns the updated `ChatSummary` object with `is_archived` set to `false`.
  ```json
  {
    "id": 123,
    "title": "Original Chat Title",
    "created_at": "2023-10-27T10:00:00Z",
    "updated_at": "2023-10-27T11:25:00Z", // <-- Updated
    "is_archived": false // <-- Updated
  }
  ```
- **Errors:** `401` (Unauthorized), `404` (Not Found/Not Owner).
- **Purpose:** Restores an archived chat back to the active state.
- **Frontend Action:** Provide a button/option within the archived chat list to unarchive a chat. Upon success, remove the chat from the _archived_ list view and refresh the _active_ list view.

#### 2.4 Archive All Active Chats

- **Path:** `/chat/archive-all`
- **Method:** `POST`
- **Request Body:** None
- **Success Response (200 OK):** Returns a confirmation message and the count of chats that were archived.
  ```json
  {
    "message": "Successfully archived 5 active chat session(s).",
    "count": 5 // Number of chats actually moved to archived state
  }
  ```
- **Errors:** `401` (Unauthorized), `500` (Internal Server Error).
- **Purpose:** Allows users to quickly archive all their currently active chats.
- **Frontend Action:** Implement a button (likely with a confirmation dialog) for this bulk action. Upon success, refresh the _active_ chat list (it should become empty) and potentially refresh the _archived_ list.

## Frontend Implementation Notes

- **State Management:** You will need to manage the display of both active and archived chats. This could be through separate API calls using the `archived` parameter or by fetching all chats and filtering client-side (less efficient for large numbers of chats).
- **UI Elements:** Add UI elements (buttons, menu items) for Rename, Archive, Unarchive, and potentially Archive All actions.
- **List Refreshing:** Ensure your chat lists (both active and archived views) are refreshed appropriately after any management action (Rename, Archive, Unarchive, Archive All) to reflect the changes accurately.
- **Error Handling:** Handle potential `401`, `404`, and `422` errors from the new endpoints gracefully in the UI.

Please review these changes and update your frontend implementation accordingly. Contact the backend team if you have any questions.
