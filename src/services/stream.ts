import {
  ChatInfoChunk,
  ChatMessageRequest,
  ErrorChunk,
  StatusChunk,
  StreamChunk,
  TextDeltaChunk,
  ToolCallChunk,
  ToolOutputChunk,
} from "@/types";

// Helper function to simulate delay
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Generate an assistive answer one character at a time
 */
function* generateTextDeltas(text: string): Generator<string> {
  const words = text.split(" ");
  let currentWord = "";

  for (const word of words) {
    // Add space between words except for the first word
    if (currentWord.length > 0) {
      yield " ";
    }

    // Generate each character of the word
    for (const char of word) {
      yield char;
    }

    currentWord = word;
  }
}

/**
 * Mock policy search for tool calls
 */
const policySearch = async (query: string) => {
  await delay(1000); // Simulate policy search time

  const policies = [
    {
      id: "RAD-SAF-001",
      title: "Radiation Safety Protocol",
      excerpt:
        "Guidelines for radiation safety in the department, including exposure limits for staff.",
    },
    {
      id: "RAD-PRV-002",
      title: "Patient Data Privacy Policy",
      excerpt:
        "Procedures for handling patient information and imaging data privacy requirements.",
    },
    {
      id: "RAD-EQP-003",
      title: "Equipment Maintenance Guidelines",
      excerpt:
        "Required maintenance schedules for radiology equipment including MRI, CT, and X-ray machines.",
    },
  ];

  // Simple mock search logic
  const found = policies.filter((policy) =>
    query
      .toLowerCase()
      .includes(
        policy.title
          .toLowerCase()
          .replace(" Policy", "")
          .replace(" Protocol", "")
          .replace(" Guidelines", "")
      )
  );

  return found.length > 0
    ? found
    : [policies[Math.floor(Math.random() * policies.length)]];
};

/**
 * Generate a mock response based on the query
 */
const generateResponse = (query: string): string => {
  // Simple logic to determine response
  if (
    query.toLowerCase().includes("radiation") ||
    query.toLowerCase().includes("safety")
  ) {
    return "According to the Department of Radiology Policy on Radiation Safety (Policy ID: RAD-SAF-001), staff members should follow these guidelines:\n\n1. Always wear appropriate dosimeter badges\n2. Use lead shielding when within 6 feet of active radiation sources\n3. Maintain ALARA (As Low As Reasonably Achievable) principles\n4. Report any concerns to the Radiation Safety Officer immediately\n\nMonthly exposure limits are set at 4.2 mSv for most staff and 0.5 mSv for pregnant staff.";
  } else if (
    query.toLowerCase().includes("privacy") ||
    query.toLowerCase().includes("patient data")
  ) {
    return "According to the Department of Radiology Patient Data Privacy Policy (Policy ID: RAD-PRV-002), the following procedures must be followed:\n\n1. All patient data must be accessed only on a need-to-know basis\n2. Imaging studies cannot be shared outside the institution without proper authorization\n3. Workstations must be locked when unattended\n4. PHI should never be discussed in public areas\n\nViolations of this policy may result in disciplinary action up to and including termination.";
  } else if (
    query.toLowerCase().includes("maintenance") ||
    query.toLowerCase().includes("equipment")
  ) {
    return "According to the Department of Radiology Equipment Maintenance Guidelines (Policy ID: RAD-EQP-003), all equipment must undergo:\n\n1. Daily quality assurance checks\n2. Weekly performance monitoring\n3. Monthly calibration verification\n4. Quarterly preventative maintenance by certified engineers\n\nAny equipment malfunction must be reported immediately through the online incident reporting system and the equipment taken out of service.";
  } else {
    return "I've searched the Department of Radiology policies and couldn't find specific information that directly addresses your question. Would you like to rephrase your question or ask about a different policy area? I can provide information on radiation safety protocols, patient data privacy, or equipment maintenance guidelines.";
  }
};

/**
 * Mock streaming service to simulate SSE endpoint
 */
export const streamService = {
  /**
   * Simulate streaming a chat message response
   */
  async streamChatResponse(
    request: ChatMessageRequest,
    onChunk: (chunk: StreamChunk) => void
  ): Promise<void> {
    // Validate request
    if (!request.message.trim()) {
      const errorChunk: ErrorChunk = {
        type: "error",
        data: {
          message: "Message cannot be empty",
        },
      };
      onChunk(errorChunk);
      return;
    }

    try {
      // First chunk: chat info
      const chatId = request.chat_id || Date.now();
      const chatInfoChunk: ChatInfoChunk = {
        type: "chat_info",
        data: {
          chat_id: chatId,
          title: request.chat_id
            ? null
            : request.message.length > 30
            ? `${request.message.substring(0, 30)}...`
            : request.message,
        },
      };
      onChunk(chatInfoChunk);

      // Wait a bit
      await delay(300);

      // Tool call: search for relevant policies
      const toolCallId = `tool_${Date.now()}`;
      const toolCallChunk: ToolCallChunk = {
        type: "tool_call",
        data: {
          id: toolCallId,
          name: "find_similar_chunks",
          input: {
            query: request.message,
            limit: 3,
          },
        },
      };
      onChunk(toolCallChunk);

      // Wait a bit longer to simulate search
      await delay(1200);

      // Tool output: policy search results
      const policies = await policySearch(request.message);
      const toolOutputChunk: ToolOutputChunk = {
        type: "tool_output",
        data: {
          tool_call_id: toolCallId,
          output: policies,
        },
      };
      onChunk(toolOutputChunk);

      // Wait a bit
      await delay(500);

      // Generate assistant response
      const response = generateResponse(request.message);

      // Stream text deltas
      for (const delta of generateTextDeltas(response)) {
        // Simulate typing speed (randomized)
        await delay(Math.random() * 30 + 20);

        const textDeltaChunk: TextDeltaChunk = {
          type: "text_delta",
          data: {
            delta,
          },
        };
        onChunk(textDeltaChunk);
      }

      // Final status chunk
      await delay(300);
      const statusChunk: StatusChunk = {
        type: "status",
        data: {
          status: "complete",
          chat_id: chatId,
        },
      };
      onChunk(statusChunk);
    } catch (error) {
      // Handle any errors
      const errorChunk: ErrorChunk = {
        type: "error",
        data: {
          message:
            error instanceof Error
              ? error.message
              : "An unknown error occurred",
        },
      };
      onChunk(errorChunk);
    }
  },
};
