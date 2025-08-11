# Yale Radiology Policies Chatbot - Phased Implementation Plan

This document outlines a step-by-step implementation plan for the Yale Department of Radiology Policy Chatbot frontend. The plan is organized into distinct phases, each building upon the previous one, allowing for incremental development and testing.

## Overall Approach

The implementation follows these general principles:

1. Start with project setup and infrastructure
2. Develop the UI components without backend connectivity
3. Implement theme switching and visual styling
4. Add mock data for UI testing
5. Finally, connect to the backend APIs

Each phase ends with a specific checkpoint that can be tested to verify progress.

## Phase 1: Project Setup and Base Configuration

**Goal**: Create the basic Next.js project structure with essential configurations.

### Tasks:

1. Initialize a new Next.js project

   ```bash
   npx create-next-app@latest yale-radiology-chatbot
   cd yale-radiology-chatbot
   ```

2. Set up Tailwind CSS if not included in initialization

   ```bash
   npm install -D tailwindcss postcss autoprefixer
   npx tailwindcss init -p
   ```

3. Configure shadcn UI

   ```bash
   npx shadcn-ui@latest init
   ```

4. Create the basic project structure

   ```
   src/
   ├── app/
   │   ├── (auth)/
   │   │   └── login/
   │   │       └── page.tsx
   │   ├── chat/
   │   │   └── page.tsx
   │   ├── history/
   │   │   └── page.tsx
   │   ├── about/
   │   │   └── page.tsx
   │   ├── layout.tsx
   │   └── page.tsx
   ├── components/
   │   ├── ui/
   │   ├── auth/
   │   ├── chat/
   │   └── layout/
   ├── lib/
   │   └── utils.ts
   ├── config/
   │   └── site.ts
   └── types/
       └── index.ts
   ```

5. Create configuration file (`src/config/site.ts`) with placeholder values

   - API URLs
   - Application text
   - Admin mode toggle
   - Default theme settings

6. Install basic dependencies

   ```bash
   npm install @microsoft/fetch-event-source date-fns react-icons
   ```

7. Create a root layout with a simple placeholder page

**Checkpoint**: Application should start and display a placeholder page.

```bash
npm run dev
```

## Phase 2: Theme System & Navigation Structure

**Goal**: Implement the black and white theme system with light/dark mode toggle and create the basic navigation structure.

### Tasks:

1. Install necessary shadcn UI components

   ```bash
   npx shadcn-ui@latest add button switch navigation-menu avatar dropdown-menu separator
   ```

2. Create theme provider component with light/dark mode support

   - Implement theme context
   - Create theme toggle component
   - Add local storage persistence for theme preference

3. Create navigation bar component

   - Add placeholder for Yale logo
   - Include navigation links for Chat, History, and About
   - Implement theme toggle in the navbar
   - Add active state styling for current page
   - Add responsive mobile menu with burger icon toggle

4. Implement basic page layouts

   - Create placeholder pages for Chat, History, and About
   - Implement responsive layouts with mobile considerations
   - Ensure navigation works between all pages

5. Customize theme to implement black and white style
   - Configure light mode (white background, black text, gray accents)
   - Configure dark mode (dark background, white text, gray accents)
   - Verify theme toggle functionality

**Checkpoint**: Application should have working navigation between placeholder pages with a functioning theme toggle.

## Phase 3: Authentication UI

**Goal**: Create the login page and authentication UI components without actual backend connectivity.

### Tasks:

1. Install necessary shadcn UI components

   ```bash
   npx shadcn-ui@latest add form input card toast
   ```

2. Create login page with form

   - Design clean, professional login form
   - Include username and password fields
   - Add validation and error handling
   - Include admin contact information
   - Apply both light and dark theme styles

3. Implement mock authentication context

   - Create auth provider with mock login/logout functions
   - Implement secure token storage mechanism
   - Add protected route handling

4. Implement admin mode

   - Add configuration option for bypassing login in site config
   - Implement visual indicator for admin mode
   - Document how to toggle admin mode via environment variables (NEXT_PUBLIC_ADMIN_MODE="true")

5. Implement route protection with middleware

   - Create Next.js middleware to protect authenticated routes
   - Define protected paths (chat, history, profile)
   - Redirect unauthenticated users to login
   - Properly handle route groups with Next.js app router

6. Implement loading states and error messages
   - Create loading spinner component
   - Design error message components
   - Test form validation

**Checkpoint**: Login page should be visually complete with form validation. Admin mode should bypass the login screen. Route protection should correctly redirect users.

## Phase 4: Chat Interface Layout

**Goal**: Develop the main chat interface layout with properly aligned components.

### Tasks:

1. Install necessary shadcn UI components

   ```bash
   npx shadcn-ui@latest add scroll-area separator avatar textarea tooltip
   ```

2. Create the chat page layout

   - Implement sidebar for chat history
   - Create main chat window
   - Add message input area
   - Ensure proper spacing and alignment
   - Add application footer with copyright information

3. Build chat message components

   - Design user message component
   - Design assistant message component
   - Create typing indicator
   - Add policy reference display component
   - Ensure vertical center alignment of text in message boxes

4. Implement sidebar components

   - Create chat history item component
   - Add "New Chat" button
   - Implement sidebar collapse for mobile

5. Design input area

   - Create message input field
   - Add send button
   - Implement basic keyboard shortcuts (Enter to send)
   - Add vertical centering for input text

6. Test responsive layout
   - Verify alignment across different screen sizes
   - Test mobile view with optimized layout (hide sidebar on mobile)
   - Add "New Chat" button to header on mobile screens
   - Check spacing consistency
   - Ensure the input box stays fixed at the bottom without overlapping with footer

**Checkpoint**: Chat interface should be visually complete with properly aligned components that adapt to different screen sizes.

## Phase 5: Chat History & About Pages

**Goal**: Complete the Chat History and About pages with proper styling and navigation.

### Tasks:

1. Install additional shadcn UI components if needed

   ```bash
   npx shadcn-ui@latest add table tabs badge
   ```

2. Develop Chat History page

   - Create list/grid view of conversation history
   - Implement sorting and filtering UI
   - Add pagination controls
   - Ensure consistent styling with sidebar
   - Create proper linking between history and chat pages

3. Implement About page

   - Create sections for application information
   - Add content explaining the application purpose and functionality
   - Describe how the system works in non-technical terms
   - Include step-by-step usage instructions
   - Include support contact information
   - Design version information display
   - Use consistent naming ("Yale Department of Radiology Policy Chatbot")

4. Connect navigation between pages

   - Ensure history items in sidebar navigate to chat
   - Link chat history page items to specific conversations
   - Verify all navigation paths work correctly
   - Use Next.js Link components for proper client-side navigation

5. Add consistent empty states
   - Design empty chat history view
   - Create first-time user welcome message

**Checkpoint**: All pages should be visually complete with working navigation between them.

## Phase 6: Mock Data Integration

**Goal**: Implement mock data services to simulate backend functionality.

### Tasks:

1. Create mock data structures

   - Define interfaces for Chat, Message, and User types
   - Create mock data factory functions

2. Implement mock data services

   - Create service for chat history
   - Add service for message history
   - Implement service for mock authentication
   - Create profile service for user data

3. Connect UI to mock data

   - Update chat history components to use mock data
   - Connect chat window to mock conversation data
   - Implement chat input with mock responses

4. Add simulated loading states

   - Implement loading indicators
   - Add artificial delays to simulate network requests
   - Test error states with mock errors

5. Simulate message streaming

   - Create mock streaming implementation
   - Implement typing indicator during streaming
   - Test policy reference display

6. Implement user profile page
   - Create profile page layout with cards
   - Display user information (name, email, account type)
   - Show conversation statistics (total count, last conversation)
   - Connect to profile service for data
   - Add profile link to user menu dropdown
   - Ensure proper authentication before displaying

**Checkpoint**: Application should function with mock data, showing realistic conversations and interactions. User profile should display correct information.

## Phase 7: Finishing UI Polish

**Goal**: Refine visual design, animations, and ensure perfect component alignment.

### Tasks:

1. Audit visual design

   - Check spacing consistency
   - Verify component alignment using grid overlay
   - Ensure proper visual hierarchy

2. Implement animations and transitions

   - Add smooth page transitions
   - Implement message appear animations
   - Add theme transition effects

3. Enhance homepage with featured chats carousel

   - Create responsive featured chats carousel with framer-motion animations
   - Implement auto-advancing slides with pause on hover
   - Add slide indicators for direct navigation
   - Design card layout with user/assistant message previews and imagery
   - Implement "Start Similar Chat" feature that pre-populates chat input
   - Add category badges and visual separation between sections
   - Ensure proper vertical spacing and full-height hero section
   - Implement smooth scroll indicator for content below the fold
   - Add subtle gradients and visual enhancements to content areas

4. Enhance accessibility

   - Add proper ARIA attributes
   - Test keyboard navigation
   - Verify screen reader compatibility
   - Check color contrast in both themes

5. Optimize responsive behavior

   - Test on various device sizes
   - Fine-tune breakpoints
   - Verify touch interactions

6. Perform visual QA
   - Check for any overlapping components
   - Verify consistent spacing
   - Test both light and dark themes

**Checkpoint**: Application should have polished visual design with smooth animations and perfect component alignment.

## Phase 8: Backend API Integration

**Goal**: Connect the application to the actual backend API.

### Tasks:

1. Create API service layer

   - Implement authentication service
   - Create chat service
   - Add message service
   - Implement streaming service

2. Connect authentication

   - Replace mock auth with actual API calls
   - Implement token management
   - Add token refresh logic if needed
   - Test error handling

3. Implement chat history

   - Connect to `/chat` endpoint
   - Implement pagination
   - Add error handling and retries

4. Connect chat messaging

   - Implement `/chat/{chat_id}/messages` endpoint integration
   - Add new chat creation
   - Implement message history loading

5. Implement SSE streaming
   - Connect to `/chat/stream` endpoint
   - Parse and handle different event types
   - Implement message updating
   - Add policy reference display
   - Handle connection management and errors

**Checkpoint**: Application should be fully functional with backend connectivity.

## Phase 9: Testing & Optimization

**Goal**: Ensure the application works correctly and performs well.

### Tasks:

1. Perform functional testing

   - Test all user flows
   - Verify API interactions
   - Check error handling
   - Test offline behavior

2. Optimize performance

   - Implement code splitting
   - Add component lazy loading
   - Optimize asset loading
   - Check bundle size

3. Implement logging and monitoring

   - Add error logging
   - Implement performance monitoring
   - Create user action tracking (if required)

4. Perform security review

   - Audit authentication implementation
   - Check for exposed sensitive information
   - Review input validation

5. Final cross-browser testing
   - Test on all required browsers
   - Verify mobile functionality
   - Check printing functionality if needed

**Checkpoint**: Application should be fully tested, optimized, and ready for deployment.

## Phase 10: Documentation & Deployment

**Goal**: Prepare the application for production use.

### Tasks:

1. Create documentation

   - Write README with setup instructions
   - Document configuration options
   - Create user guide if required

2. Prepare deployment configuration

   - Create production build
   - Configure for intranet deployment
   - Set up proper environment variables

3. Implement admin tools if needed

   - Add configuration panel
   - Create admin-only features
   - Document admin functionality

4. Create deployment packages

   - Generate production build
   - Package with dependencies
   - Create deployment scripts

5. Final verification
   - Test in an environment similar to production
   - Verify all functionality works as expected
   - Check for any network-specific issues

**Checkpoint**: Application should be documented and ready for deployment to the intranet environment.

## Appendix: Checkpoints Summary

For quick reference, here are all the development checkpoints:

1. **Phase 1**: Basic Next.js application with project structure
2. **Phase 2**: Working navigation and theme toggle
3. **Phase 3**: Complete login page with mock authentication
4. **Phase 4**: Chat interface layout with proper component alignment
5. **Phase 5**: Fully navigable application with all pages
6. **Phase 6**: Functional application with mock data
7. **Phase 7**: Polished UI with animations and perfect alignment
8. **Phase 8**: Backend integration with real data
9. **Phase 9**: Fully tested and optimized application
10. **Phase 10**: Documented and deployment-ready application
