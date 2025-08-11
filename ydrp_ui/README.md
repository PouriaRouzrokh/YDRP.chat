# Yale Department of Radiology Policy Chatbot

A modern, responsive web application that enables Yale Department of Radiology staff to search and access department policies through natural language queries. This chatbot provides instant, reliable answers from official policy documents.

## Project Overview

The Yale Department of Radiology Policy Chatbot is designed to make department policies more accessible through an intuitive chat interface. Users can:

- Ask questions about department policies using natural language
- View conversation history and manage past chats
- Access policy information 24/7 through a secure interface
- Search official documents with accurate citation capabilities

This repository contains the scripts for the UI functionalities – including the backend and data collection. These will be developed in a separate repository:

https://github.com/PouriaRouzrokh/YDRP_Engine

## Tech Stack

This application is built with a modern web development stack:

### Frontend

- **Framework**: Next.js 15.3 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS 4
- **UI Components**: shadcn/ui with Radix UI primitives
- **State Management**: React Context API
- **Form Handling**: React Hook Form with Zod validation
- **Animations**: Framer Motion
- **HTTP Client**: Native Fetch API
- **Streaming**: Server-Sent Events via Microsoft's fetch-event-source
- **Additional Libraries**:
  - date-fns - Date formatting and manipulation
  - react-markdown - Markdown rendering
  - sonner - Toast notifications
  - lucide-react - Icon system
  - next-themes - Theme management
  - js-cookie - Cookie management

### Backend Integration

The frontend connects to a Python-based backend API that provides:

- Authentication services
- Chat session management
- Real-time message streaming
- Policy document search and retrieval

## Project Structure

```
src/
├── app/ - Next.js App Router pages
│   ├── (auth)/ - Authentication-related routes
│   ├── chat/ - Chat interface
│   ├── profile/ - User profile
│   ├── history/ - Chat history
│   └── about/ - Information about the app
├── components/ - Reusable UI components
│   ├── ui/ - shadcn/ui components
│   ├── chat/ - Chat-specific components
│   ├── home/ - Homepage components
│   ├── layout/ - Layout components
│   └── auth/ - Authentication components
├── contexts/ - React Context providers
├── lib/ - Utility functions and helpers
├── services/ - API integration services
├── types/ - TypeScript type definitions
└── config/ - Application configuration
```

## Features

- **Secure Authentication**: Yale-specific login system
- **Real-time Chat**: Instant responses with SSE streaming
- **Chat Management**: Rename, archive, and organize chat sessions
- **Responsive Design**: Works seamlessly on desktop and mobile devices
- **Dark/Light Mode**: Customizable theme support
- **Policy References**: Citations linked directly to source documents

## Development Approach

This application was developed using a phased implementation approach:

1. Project setup and infrastructure
2. UI component development
3. Theme implementation and styling
4. Mock data integration for testing
5. Backend API integration
6. Testing and optimization
7. Documentation and deployment

## Getting Started

### Prerequisites

- Node.js 18+ (LTS recommended)
- npm or yarn package manager

### Installation

1. Clone the repository

```bash
git clone <repository-url>
cd ydrp_ui
```

2. Install dependencies

```bash
npm install
# or
yarn install
```

3. Set up environment variables (create a `.env.local` file)

```
NEXT_PUBLIC_API_URL=http://your-backend-url:8000
# Add other environment variables as needed
```

4. Start the development server

```bash
npm run dev
# or
yarn dev
```

5. Open [http://localhost:3000](http://localhost:3000) in your browser

### Building for Production

```bash
npm run build
npm run start
# or
yarn build
yarn start
```

## Support

For technical support, please contact Pouria Rouzrokh or Bardia Khosravi.
Emails: pouria.rouzrokh@yale.edu | bardia.khosravi@yale.edu
