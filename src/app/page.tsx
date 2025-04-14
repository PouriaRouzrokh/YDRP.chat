export default function HomePage() {
  return (
    <div className="container flex items-center justify-center min-h-screen">
      <div className="text-center">
        <h1 className="text-4xl font-bold">Yale Radiology Policies Chatbot</h1>
        <p className="mt-4 text-xl">A chatbot for Yale Radiology policies</p>
        <div className="mt-8">
          <a
            href="/chat"
            className="px-4 py-2 text-white bg-blue-600 rounded hover:bg-blue-700"
          >
            Start Chatting
          </a>
        </div>
      </div>
    </div>
  );
}
