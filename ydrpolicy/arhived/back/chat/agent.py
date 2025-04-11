
import logging
import os
import json
from typing import List, Dict, Any, Optional, Union, Callable
import base64

from openai import OpenAI

# Import prompt and tool implementations
from .tools import TOOL_REGISTRY
from .prompt import SYSTEM_PROMPT_TEMPLATE
from .utils import ChatLogger, AgentResponse

class ChatAgent:
    """
    ChatAgent for conversing with users using OpenAI models,
    with support for tools, conversation memory, and image processing.
    Includes structured output for handoff decisions and iterative workflow.
    """
    
    def __init__(
        self,
        model: str = "o3-mini",
        api_key: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        streaming: bool = True,
        log_level: int = logging.INFO,
        max_iterations: int = 10,
        custom_instructions: str = ""
    ):
        """
        Initialize the ChatAgent.
        
        Args:
            model: OpenAI model to use (default is "o3-mini")
            api_key: OpenAI API key (will check env if not provided)
            tools: List of tools/functions the agent can use
            streaming: Whether to enable response streaming
            log_level: Logging level
            max_iterations: Maximum number of iterations for the agent loop
            custom_instructions: Additional custom instructions for the system prompt
        """
        # Set up API key
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided and not found in environment variables")
        
        # Initialize client (shoule be eventually replaced with the "Clarity" client)
        self.client = OpenAI(api_key=self.api_key)
        
        # Set up logger
        self.logger = ChatLogger(name="ChatAgent", level=log_level)
        self.logger.info(f"Initializing ChatAgent with model: {model}")
        
        # Chat settings
        self.model = model
        self.streaming = streaming
        self.tools = tools or []
        self.max_iterations = max_iterations
        self.custom_instructions = custom_instructions
        
        # Conversation memory
        self.conversation_history = []
        
        # Generate and set system prompt
        self._update_system_prompt()
        
    def _format_system_prompt(self) -> str:
        """
        Format the system prompt with the current tools information.
        
        Returns:
            Formatted system prompt
        """
        if not self.tools:
            tools_count = 0
            tools_list = "none"
        else:
            tools_count = len(self.tools)
            tool_names = [t.get('function', {}).get('name', 'unnamed') for t in self.tools]
            tools_list = ", ".join(tool_names)
            
        return SYSTEM_PROMPT_TEMPLATE.format(
            tools_count=tools_count,
            tools_list=tools_list,
            custom_instructions=self.custom_instructions
        )
    
    def _update_system_prompt(self):
        """Update the system prompt and refresh it in the conversation history"""
        system_prompt = self._format_system_prompt()
        
        # If conversation history exists and first message is system, update it
        if self.conversation_history and self.conversation_history[0]["role"] == "system":
            self.conversation_history[0]["content"] = system_prompt
            self.logger.info("Updated existing system prompt in conversation history")
        else:
            # Otherwise, initialize conversation with system message
            self.conversation_history = [
                {"role": "system", "content": system_prompt}
            ]
            self.logger.info("Initialized conversation history with system prompt")
    
    def _encode_image(self, image_path: str) -> str:
        """
        Encode an image file to base64 for API submission.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded image string
        """
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Error encoding image: {str(e)}")
            raise
            
    def _prepare_messages(self, 
                          text: str, 
                          image_paths: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Prepare message payload for the API, including any images.
        
        Args:
            text: User's text input
            image_paths: Optional list of paths to images
            
        Returns:
            List of message dictionaries for the API
        """
        messages = self.conversation_history.copy()
        
        # Note: We don't add the user message to conversation_history here
        # It will be added explicitly in iterate_chat to avoid duplication
        
        # Handle text-only messages
        if not image_paths:
            messages.append({"role": "user", "content": text})
            return messages
        
        # Handle messages with images
        content = []
        
        # Add text content
        if text:
            content.append({
                "type": "text",
                "text": text
            })
        
        # Add image content
        for image_path in image_paths:
            try:
                base64_image = self._encode_image(image_path)
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                })
                self.logger.info(f"Added image: {image_path}")
            except Exception as e:
                self.logger.error(f"Failed to add image {image_path}: {str(e)}")
        
        messages.append({"role": "user", "content": content})
        return messages
    
    def execute_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """
        Execute the requested tool calls and format results for the API.
        
        Args:
            tool_calls: List of tool calls from the API response
            
        Returns:
            List of tool result messages for the API
        """
        tool_results = []
        used_tools = []
        
        for tool_call in tool_calls:
            tool_id = tool_call.id
            function_name = tool_call.function.name
            used_tools.append(function_name)
            
            try:
                # Parse arguments as JSON
                arguments = json.loads(tool_call.function.arguments)
                
                # Check if the tool is in our registry
                if function_name in TOOL_REGISTRY:
                    self.logger.info(f"Executing tool: {function_name} with args: {arguments}")
                    
                    # Execute the tool function with the provided arguments
                    result = TOOL_REGISTRY[function_name](**arguments)
                    
                    # Format the result as JSON string
                    result_str = json.dumps(result)
                    
                    # Log the result
                    self.logger.info(f"Tool {function_name} result: {result_str[:100]}{'...' if len(result_str) > 100 else ''}")
                else:
                    error_msg = f"Tool {function_name} not found in registry"
                    self.logger.error(error_msg)
                    result_str = json.dumps({"error": error_msg})
            
            except Exception as e:
                error_msg = f"Error executing tool {function_name}: {str(e)}"
                self.logger.error(error_msg)
                result_str = json.dumps({"error": error_msg})
            
            # Add the tool result to the list
            tool_results.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": result_str
            })
        
        return tool_results
    
    def parse_response(self, content: str) -> Dict[str, Any]:
        """
        Parse the assistant's response to extract structured handoff and response fields.
        
        Args:
            content: The content of the assistant's response
            
        Returns:
            Dictionary with handoff and response fields
        """
        try:
            # First try to parse as JSON directly
            parsed = json.loads(content)
            if 'handoff' in parsed and 'response' in parsed:
                return {
                    "handoff": parsed["handoff"],
                    "response": parsed["response"]
                }
        except:
            # If JSON parsing fails, try to extract using a more relaxed approach
            self.logger.warning("Could not parse response as JSON, attempting alternate extraction")
            try:
                # Look for something that looks like JSON in the response
                import re
                # Find any JSON-like structure with handoff and response fields
                json_match = re.search(r'\{(?:[^{}]|"(?:\\.|[^"\\])*")*"handoff"\s*:\s*(true|false)(?:[^{}]|"(?:\\.|[^"\\])*")*"response"\s*:\s*"(?:\\.|[^"\\])*"(?:[^{}]|"(?:\\.|[^"\\])*")*\}', 
                                      content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    try:
                        parsed = json.loads(json_str)
                        if 'handoff' in parsed and 'response' in parsed:
                            return {
                                "handoff": parsed["handoff"],
                                "response": parsed["response"]
                            }
                    except:
                        pass
                        
                # Try an even more relaxed approach - find code blocks with JSON
                code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if code_block_match:
                    try:
                        json_str = code_block_match.group(1)
                        parsed = json.loads(json_str)
                        if 'handoff' in parsed and 'response' in parsed:
                            return {
                                "handoff": parsed["handoff"],
                                "response": parsed["response"]
                            }
                    except:
                        pass
            except:
                pass
        
        # If all parsing attempts fail, return a default structure
        self.logger.warning("Could not extract structured fields, using defaults")
        return {
            "handoff": True,  # Default to handoff
            "response": content  # Use the entire content as the response
        }
    
    def process_non_streaming_response(self, response: Any) -> Dict[str, Any]:
        """
        Process a non-streaming response from the API and update conversation history.
        
        Args:
            response: Response from the OpenAI API
            
        Returns:
            Dictionary with handoff, response, and tool_records fields
        """
        # Extract message from the choices
        message = response.choices[0].message
        
        # Check if there are tool calls
        if hasattr(message, 'tool_calls') and message.tool_calls:
            # If there are tool calls, handoff should be False
            result = {
                "handoff": False,
                "response": message.content or "I need to use a tool to help with this.",
                "tool_records": []  # We'll populate this after executing the tools
            }
            
            # Add the assistant's message with tool calls to history
            self.conversation_history.append({
                "role": "assistant",
                "content": json.dumps({"handoff": False, "response": result["response"]}),
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in message.tool_calls
                ]
            })
            
            # Execute the tool calls and collect tool records
            tool_results = self.execute_tool_calls(message.tool_calls)
            
            # Build tool_records list
            for i, (tool_call, tool_result) in enumerate(zip(message.tool_calls, tool_results)):
                try:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    tool_result_content = json.loads(tool_result["content"])
                    
                    result["tool_records"].append({
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "tool_result": tool_result_content
                    })
                except Exception as e:
                    self.logger.error(f"Error building tool record for tool {i}: {str(e)}")
                    result["tool_records"].append({
                        "tool_name": tool_call.function.name if hasattr(tool_call, 'function') else f"unknown_tool_{i}",
                        "tool_args": "Error parsing arguments",
                        "tool_result": f"Error parsing result: {str(e)}"
                    })
            
            # Add tool results to history
            for tool_result in tool_results:
                self.conversation_history.append(tool_result)
                
            return result
        else:
            # No tool calls, parse the response
            parsed_response = self.parse_response(message.content)
            
            # Add the final response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": json.dumps(parsed_response)
            })
            
            # Add the tool_records field (None since no tools were used)
            parsed_response["tool_records"] = None
            
            return parsed_response
    
    def process_streaming_response(self, stream_response) -> Dict[str, Any]:
        """
        Process a streaming response from the API and handle tool calls.
        
        Args:
            stream_response: Stream from the OpenAI API
            
        Returns:
            Dictionary with handoff, response, and tool_records fields
        """
        # Initialize variables to collect response content and tool calls
        collected_content = []
        final_tool_calls = {}
        has_tool_calls = False
        
        # Process each chunk in the stream
        for chunk in stream_response:
            delta = chunk.choices[0].delta
            
            # Process content if present
            if delta.content is not None:
                collected_content.append(delta.content)
                # print(delta.content, end="", flush=True)
            
            # Process tool calls if present
            if delta.tool_calls:
                has_tool_calls = True
                for tool_call in delta.tool_calls:
                    # Skip if None
                    if tool_call is None:
                        continue
                        
                    # Initialize tool call entry if new
                    if tool_call.index is not None:
                        index = tool_call.index
                        if index not in final_tool_calls:
                            final_tool_calls[index] = {
                                "index": index,
                                "id": tool_call.id,
                                "type": tool_call.type,
                                "function": {
                                    "name": tool_call.function.name if tool_call.function and tool_call.function.name else "",
                                    "arguments": ""
                                }
                            }
                    
                        # Accumulate arguments
                        if tool_call.function and tool_call.function.arguments is not None:
                            final_tool_calls[index]["function"]["arguments"] += tool_call.function.arguments
        
        # Format the accumulated content
        full_response = "".join(collected_content)
        
        # If there are tool calls, handle them
        if has_tool_calls and final_tool_calls:
            # For tool calls, set handoff to False and include tool_records
            result = {
                "handoff": False,
                "response": full_response,
                "tool_records": []  # We'll populate this after executing the tools
            }
            
            # Prepare tool calls for history and execution
            tool_calls_for_history = [
                {
                    "id": tc["id"],
                    "type": tc["type"] or "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"]
                    }
                } for tc in final_tool_calls.values()
            ]
            
            # Add the assistant's message with tool calls to history
            self.conversation_history.append({
                "role": "assistant",
                "content": json.dumps({"handoff": False, "response": result["response"]}),
                "tool_calls": tool_calls_for_history
            })
            
            # Convert the dictionary to a list of tool calls for execution
            tool_calls_list = []
            
            for tc in final_tool_calls.values():
                # Create a tool call object
                tool_call_obj = type('ToolCall', (), {
                    'id': tc["id"],
                    'type': tc["type"] or "function",
                    'function': type('Function', (), {
                        'name': tc["function"]["name"],
                        'arguments': tc["function"]["arguments"]
                    })
                })
                tool_calls_list.append(tool_call_obj)
            
            # Execute the tool calls
            tool_results = self.execute_tool_calls(tool_calls_list)
            
            # Build tool_records list
            for i, (tc, tool_result) in enumerate(zip(final_tool_calls.values(), tool_results)):
                try:
                    tool_name = tc["function"]["name"]
                    tool_args = json.loads(tc["function"]["arguments"])
                    tool_result_content = json.loads(tool_result["content"])
                    
                    result["tool_records"].append({
                        "tool_name": tool_name,
                        "tool_args": tool_args,
                        "tool_result": tool_result_content
                    })
                except Exception as e:
                    self.logger.error(f"Error building tool record for tool {i}: {str(e)}")
                    result["tool_records"].append({
                        "tool_name": tc["function"]["name"] if "function" in tc and "name" in tc["function"] else f"unknown_tool_{i}",
                        "tool_args": "Error parsing arguments",
                        "tool_result": f"Error parsing result: {str(e)}"
                    })
            
            # Add tool results to history
            for tool_result in tool_results:
                self.conversation_history.append(tool_result)
                
            return result
        else:
            # No tool calls, parse the response
            parsed_response = self.parse_response(full_response)
            
            # Add the final response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": json.dumps(parsed_response)
            })
            
            # Add the tool_records field (None since no tools were used)
            parsed_response["tool_records"] = None
            
            print()  # Add a newline after streaming completes
            return parsed_response
    
    def iterate_chat(self, 
                     text: Optional[str] = None, 
                     image_paths: Optional[List[str]] = None,
                     tool_choice: Union[str, Dict[str, Any], None] = "auto") -> Dict[str, Any]:
        """
        Perform a single iteration of the chat process.
        
        Args:
            text: User's text input (optional if continuing from a tool call)
            image_paths: Optional list of paths to images to include
            tool_choice: Control over function calling behavior
            
        Returns:
            Dictionary with handoff and response fields
        """
        try:
            # Prepare messages if text input is provided
            if text is not None:
                messages = self._prepare_messages(text, image_paths)
            else:
                messages = self.conversation_history
                
            # Request structured output format - using json_object type which works across more models
            response_format = {"type": "json_object"}
            
            # Make API call with or without streaming
            if self.streaming:
                # Set up streaming parameters
                stream_args = {
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "response_format": response_format
                }
                
                if self.tools:
                    stream_args["tools"] = self.tools
                    stream_args["tool_choice"] = tool_choice
                    
                stream_response = self.client.chat.completions.create(**stream_args)
                return self.process_streaming_response(stream_response)
            else:
                # Set up non-streaming parameters
                api_args = {
                    "model": self.model,
                    "messages": messages,
                    "response_format": response_format
                }
                
                if self.tools:
                    api_args["tools"] = self.tools
                    api_args["tool_choice"] = tool_choice
                
                response = self.client.chat.completions.create(**api_args)
                return self.process_non_streaming_response(response)
                
        except Exception as e:
            error_msg = f"Error during chat iteration: {str(e)}"
            self.logger.error(error_msg)
            return {
                "handoff": True,
                "response": f"An error occurred: {error_msg}"
            }
    
    def chat(self, 
             text: str, 
             image_paths: Optional[List[str]] = None,
             tool_choice: Union[str, Dict[str, Any], None] = "auto",
             callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> str:
        """
        Main chat loop that iterates until a handoff or max iterations.
        
        Args:
            text: User's text input
            image_paths: Optional list of paths to images to include
            tool_choice: Control over function calling behavior
            callback: Optional callback function to receive each iteration's result
            
        Returns:
            The assistant's final response
        """
        self.logger.info(f"Starting chat loop with max {self.max_iterations} iterations")
        
        # Start with the user's input
        iteration_text = text
        iteration_images = image_paths
        iterations = 0
        final_response = None
        
        while iterations < self.max_iterations:
            iterations += 1
            self.logger.info(f"Iteration {iterations}/{self.max_iterations}")
            
            # Perform one iteration
            result = self.iterate_chat(iteration_text, iteration_images, tool_choice)
            
            # If a callback is provided, send the iteration result
            if callback:
                callback(result)
            
            # Store the response
            final_response = result["response"]
            
            # Clear the inputs for subsequent iterations - only use text input in first iteration
            iteration_text = None
            iteration_images = None
            
            # Check if we should hand off
            if result["handoff"]:
                self.logger.info(f"Handoff requested after {iterations} iterations")
                return final_response
            
            # Check if we've reached the maximum iterations
            if iterations >= self.max_iterations:
                self.logger.warning(f"Reached maximum iterations ({self.max_iterations})")
                self.conversation_history.append({
                    "role": "assistant",
                    "content": json.dumps({
                        "handoff": True,
                        "response": final_response + "\n\n(Note: Maximum iterations reached)"
                    })
                })
                return final_response + "\n\n(Note: Maximum iterations reached)"
        
        # This should not be reached due to the check inside the loop
        return "Maximum iterations reached without a conclusive answer."
    
    def clear_history(self) -> None:
        """Clear the conversation history and reinitialize with system prompt"""
        self.logger.info("Clearing conversation history")
        self._update_system_prompt()
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Return the conversation history"""
        return self.conversation_history
    
    def add_tool(self, tool: Dict[str, Any]) -> None:
        """
        Add a new tool to the agent's toolkit and update the system prompt.
        
        Args:
            tool: Tool/function definition following OpenAI's format
        """
        self.tools.append(tool)
        tool_name = tool.get('function', {}).get('name', 'unnamed')
        self.logger.info(f"Added new tool: {tool_name}")
        
        # Update the system prompt to reflect the new tool
        self._update_system_prompt()
    
    def set_tools(self, tools: List[Dict[str, Any]]) -> None:
        """
        Set the complete list of tools for the agent and update the system prompt.
        
        Args:
            tools: List of tool/function definitions
        """
        self.tools = tools
        tool_names = [t.get('function', {}).get('name', 'unnamed') for t in tools]
        self.logger.info(f"Updated tools list with {len(tools)} tools: {', '.join(tool_names)}")
        
        # Update the system prompt to reflect the new tools
        self._update_system_prompt()
        
    def set_custom_instructions(self, instructions: str) -> None:
        """
        Set custom instructions for the system prompt and update it.
        
        Args:
            instructions: Custom instructions text
        """
        self.custom_instructions = instructions
        self.logger.info("Updated custom instructions")
        
        # Update the system prompt with the new instructions
        self._update_system_prompt()