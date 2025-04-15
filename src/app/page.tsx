import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <div className="w-full flex flex-col items-center justify-center py-16 text-center">
      <h1 className="text-4xl font-bold mb-1">Yale Department of Radiology</h1>
      <h1 className="text-4xl font-bold mb-4">Policy Chatbot</h1>
      <p className="text-lg text-muted-foreground max-w-2xl mb-8">
        Welcome to the Yale Radiology Policies Chatbot. This application helps
        you find and understand radiology department policies through a simple
        chat interface.
      </p>
      <div className="flex gap-4">
        <Button asChild>
          <Link href="/chat">Start Chatting</Link>
        </Button>
        <Button variant="outline" asChild>
          <Link href="/about">Learn More</Link>
        </Button>
      </div>
    </div>
  );
}
