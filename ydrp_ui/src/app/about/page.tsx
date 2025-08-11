import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export default function AboutPage() {
  return (
    <div className="container mx-auto py-8 max-w-4xl">
      <h1 className="text-3xl font-bold mb-6">
        About Yale Department of Radiology Policy Chatbot
      </h1>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>What is this application?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p>
            The Yale Department of Radiology Policy Chatbot is a user-friendly
            tool designed to make the Department of Radiology&apos;s policies
            and guidelines easily accessible. Instead of searching through
            documents or websites, you can simply ask questions in everyday
            language and receive accurate information based on official
            department policies.
          </p>
          <p>
            Think of it as a helpful assistant who has read all the
            department&apos;s policy documents and can quickly find and explain
            the information you need.
          </p>
        </CardContent>
      </Card>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>How does it work?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p>Behind the scenes, this application works in several steps:</p>
          <ol className="list-decimal pl-6 space-y-3">
            <li>
              <strong>Data Collection:</strong> The system automatically gathers
              Yale Department of Radiology policy documents from authorized
              sources.
            </li>
            <li>
              <strong>Information Processing:</strong> These policies are
              carefully organized and stored in a secure database.
            </li>
            <li>
              <strong>Intelligent Search:</strong> When you ask a question, the
              system searches through all policies to find the most relevant
              information.
            </li>
            <li>
              <strong>Conversational Response:</strong> A specialized AI
              assistant presents the information in a clear, conversational way,
              with references to the source policies.
            </li>
          </ol>
          <p className="mt-4">
            Importantly, all answers are based directly on actual department
            policies - the system doesn&apos;t make up information or provide
            opinions.
          </p>
        </CardContent>
      </Card>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>How to use this tool?</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p>
            Using the Yale Department of Radiology Policy Chatbot is
            straightforward:
          </p>
          <ol className="list-decimal pl-6 space-y-3">
            <li>
              <strong>Login:</strong> Access the application using your provided
              credentials. This ensures only authorized personnel can access
              department policies.
            </li>
            <li>
              <strong>Ask a question:</strong> Type your question in everyday
              language. For example: &quot;What are the safety protocols for
              pregnant staff working with radiation?&quot; or &quot;What is the
              procedure for scheduling an emergency MRI?&quot;
            </li>
            <li>
              <strong>Review the answer:</strong> The system will provide a
              clear response based on department policies, often with references
              to specific documents.
            </li>
            <li>
              <strong>Ask follow-up questions:</strong> You can continue the
              conversation to get more details or clarification.
            </li>
            <li>
              <strong>Start a new chat:</strong> Begin a new conversation any
              time you have a different topic to discuss.
            </li>
          </ol>
          <p className="mt-4">
            Your chat history is saved, so you can always refer back to previous
            conversations.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Support & Contact Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p>
            If you encounter any issues or have questions about the application,
            please contact:
          </p>
          <div className="bg-muted/50 p-4 rounded-lg">
            <p>
              <strong>Pouria Ruzrokh, MD, MPH, MHPE</strong>
            </p>
            <p>Email: pouria.rouzrokh@yale.edu</p>
          </div>
          <div className="bg-muted/50 p-4 rounded-lg">
            <p>
              <strong>Bardia Khosravi, MD, MPH, MHPE</strong>
            </p>
            <p>Email: bardia.khosravi@yale.edu</p>
          </div>
          <Separator className="my-4" />
          <div className="text-sm text-muted-foreground">
            <p>Version 0.2.0</p>
            <p>© {new Date().getFullYear()} Yale Department of Radiology</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
