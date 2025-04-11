#!/usr/bin/env python3
"""
Interactive CLI to test the ChatAgent implementation.
Demonstrates basic chat, tools, and image processing functionality with support for
streaming intermediate results during iteration.
"""

import os
import argparse
import sys
import logging
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from rich.console import Console
from rich import print as rich_print
from back.chat.agent import ChatAgent

# Initialize Rich console for better formatting
console = Console()

# Sample tools that can be used with the agent
AVAILABLE_TOOLS = {
    "calculator": {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Perform basic arithmetic operations",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                        "description": "The arithmetic operation to perform"
                    },
                    "a": {
                        "type": "number",
                        "description": "The first number"
                    },
                    "b": {
                        "type": "number",
                        "description": "The second number"
                    }
                },
                "required": ["operation", "a", "b"]
            }
        }
    },
    "text_analyzer": {
        "type": "function",
        "function": {
            "name": "text_analyzer",
            "description": "Analyze text based on different criteria",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to analyze"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["count_char", "word_count", "find_occurrences"],
                        "description": "The type of analysis to perform"
                    },
                    "target": {
                        "type": "string",
                        "description": "The character or word to count/find (required for count_char and find_occurrences)"
                    }
                },
                "required": ["text", "analysis_type"]
            }
        }
    }
}

# Logging level mapping
LOGGING_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "none": None
}


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test the ChatAgent with an interactive CLI")
    parser.add_argument("--model", default="o3-mini", help="The OpenAI model to use (default: o3-mini)")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming of responses")
    parser.add_argument("--tools", nargs="*", choices=list(AVAILABLE_TOOLS.keys()), 
                        default=list(AVAILABLE_TOOLS.keys()),  # Default to all available tools
                        help="Tools to provide to the agent (default: all tools)")
    parser.add_argument("--no-tools", action="store_true", help="Disable all tools")
    parser.add_argument("--image", help="Path to an image file to process along with the first message")
    parser.add_argument("--logging", default="none", choices=list(LOGGING_LEVELS.keys()),
                        help="Set the logging level (default: none)")
    parser.add_argument("--max-iterations", type=int, default=10, 
                        help="Maximum number of iterations for the agent (default: 10)")
    
    return parser.parse_args()


def get_active_tools(tool_names: Optional[List[str]], disable_all: bool = False) -> List[Dict[str, Any]]:
    """
    Get the tool definitions for the specified tool names.
    
    Args:
        tool_names: List of tool names to enable
        disable_all: If True, ignore tool_names and return empty list
        
    Returns:
        List of tool definitions
    """
    if disable_all:
        return []
    
    if not tool_names:
        # Default to all tools if none specified
        tool_names = list(AVAILABLE_TOOLS.keys())
    
    return [AVAILABLE_TOOLS[name] for name in tool_names if name in AVAILABLE_TOOLS]


def print_tool_details(tools: List[Dict[str, Any]]):
    """Print detailed information about the available tools."""
    if not tools:
        console.print("No tools enabled.")
        return
    
    console.print("\n[bold blue]🔧 Available Tools:[/bold blue]")
    for tool in tools:
        function_info = tool.get("function", {})
        name = function_info.get("name", "Unknown")
        description = function_info.get("description", "No description")
        console.print(f"  • [bold cyan]{name}[/bold cyan]: {description}")
        
        # Print parameters if available
        params = function_info.get("parameters", {}).get("properties", {})
        if params:
            console.print("    [italic]Parameters:[/italic]")
            for param_name, param_info in params.items():
                param_type = param_info.get("type", "any")
                param_desc = param_info.get("description", "No description")
                console.print(f"      - [green]{param_name}[/green] ([yellow]{param_type}[/yellow]): {param_desc}")
    console.print()


def clear_screen():
    """Clear the terminal screen based on the OS."""
    # Check if the OS is Windows
    if os.name == 'nt':
        os.system('cls')
    else:  # For Unix/Linux/MacOS
        os.system('clear')


def display_welcome_message():
    """Display the welcome message for the chat session."""
    console.print("\n" + "="*50, style="bold")
    console.print("🤖 [bold green]ChatAgent Interactive Session[/bold green]")
    console.print("Type [bold]'exit'[/bold] or [bold]'quit'[/bold] to end the conversation")
    console.print("Type [bold]'clear'[/bold] to reset the conversation history")
    console.print("Type [bold]'history'[/bold] to view the conversation history")
    console.print("Type [bold]'image <path>'[/bold] to add an image to your next message")
    console.print("Type [bold]'logging <level>'[/bold] to change logging level (debug, info, warning, error, critical, none)")
    console.print("Type [bold]'help'[/bold] to see all available commands")
    console.print("="*50 + "\n", style="bold")


def display_history(agent: ChatAgent):
    """Display the conversation history in a readable format."""
    history = agent.get_history()
    
    if not history:
        console.print("\n📝 No conversation history yet.", style="italic")
        return
    
    console.print("\n" + "="*50, style="bold")
    console.print("📝 [bold]Conversation History:[/bold]")
    console.print("="*50, style="bold")
    
    for i, message in enumerate(history):
        role = message.get("role", "unknown")
        content = message.get("content", "")
        
        # Format based on message role
        if role == "user":
            console.print(f"\n[bold blue]👤 User ({i+1}):[/bold blue]")
        elif role == "assistant":
            console.print(f"\n[bold green]🤖 Assistant ({i+1}):[/bold green]")
        elif role == "system":
            console.print(f"\n[bold yellow]⚙️ System ({i+1}):[/bold yellow]")
        elif role == "tool":
            console.print(f"\n[bold magenta]🧰 Tool ({i+1}):[/bold magenta]")
        else:
            console.print(f"\n[bold]{role.capitalize()} ({i+1}):[/bold]")
        
        # Handle different content formats
        if isinstance(content, str):
            # Try to parse as JSON for better display
            try:
                json_content = json.loads(content)
                console.print_json(json.dumps(json_content, indent=2))
            except:
                console.print(content)
        elif isinstance(content, list):
            # Handle multi-part content (like with images)
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        console.print(item.get("text", ""))
                    elif item.get("type") == "image_url":
                        console.print("[Image attached]", style="italic")
                else:
                    console.print(item)
        else:
            console.print_json(json.dumps(content, indent=2))
        
        # Display tool calls if present
        if "tool_calls" in message:
            console.print("\n[bold magenta]Tool Calls:[/bold magenta]")
            for tc in message["tool_calls"]:
                func_name = tc.get("function", {}).get("name", "unknown")
                func_args = tc.get("function", {}).get("arguments", "{}")
                try:
                    parsed_args = json.loads(func_args)
                    console.print(f"  • [bold cyan]{func_name}[/bold cyan]:")
                    console.print_json(json.dumps(parsed_args, indent=2))
                except:
                    console.print(f"  • [bold cyan]{func_name}[/bold cyan]: {func_args}")
    
    console.print("\n" + "="*50, style="bold")


def process_command(command: str, agent: ChatAgent) -> Any:
    """
    Process special commands in the chat interface.
    
    Args:
        command: The command string entered by the user
        agent: The ChatAgent instance
        
    Returns:
        True if a command was processed and should continue
        False if not a command
        "exit" if the program should exit
        Tuple with image path for image command
    """
    # Split command into parts
    parts = command.strip().split()
    
    if not parts:
        return False
        
    cmd = parts[0].lower()
    
    # Process command based on first word
    if cmd in ["exit", "quit"]:
        console.print("\nThank you for using ChatAgent. Goodbye! 👋", style="bold green")
        return "exit"  # Special return value for exit
    elif cmd == "clear":
        agent.clear_history()
        clear_screen()
        display_welcome_message()
        console.print("Conversation history cleared! Starting fresh...", style="bold green")
        return True
    elif cmd == "history":
        display_history(agent)
        return True
    elif cmd == "image" and len(parts) > 1:
        # Add image path for next message
        image_path = " ".join(parts[1:])
        if os.path.exists(image_path):
            console.print(f"\n[bold green]🖼️ Image added: {image_path}[/bold green]")
            console.print("Your next message will include this image.", style="italic")
            return True, image_path  # Return both status and image path
        else:
            console.print(f"\n[bold red]❌ Image not found: {image_path}[/bold red]")
            return True, None
    elif cmd == "logging" and len(parts) > 1:
        # Change logging level
        level = parts[1].lower()
        if level in LOGGING_LEVELS:
            log_level = LOGGING_LEVELS[level]
            # Update the ChatAgent's logger level
            if log_level is None:
                console.print("\nLogging disabled.", style="bold yellow")
            else:
                console.print(f"\nLogging level set to: [bold green]{level}[/bold green]")
                agent.logger.logger.setLevel(log_level)
            return True
        else:
            console.print(f"\n[bold red]❌ Invalid logging level. Options: {', '.join(LOGGING_LEVELS.keys())}[/bold red]")
            return True
    elif cmd == "help":
        console.print("\n" + "="*50, style="bold")
        console.print("🤖 [bold green]ChatAgent Commands:[/bold green]")
        console.print("  [bold]exit, quit[/bold] - End the conversation")
        console.print("  [bold]clear[/bold] - Reset the conversation history and screen")
        console.print("  [bold]history[/bold] - View the conversation history")
        console.print("  [bold]image <path>[/bold] - Add an image to your next message")
        console.print("  [bold]logging <level>[/bold] - Set logging level (debug, info, warning, error, critical, none)")
        console.print("  [bold]help[/bold] - Show this help message")
        console.print("="*50, style="bold")
        return True
        
    return False


def display_iteration_result(result: Dict[str, Any], iteration_num: int = None):
    """
    Display the result of an agent iteration to the user.
    
    Args:
        result: The iteration result dictionary
        iteration_num: Optional iteration number for display
    """
    iteration_str = f" (Iteration {iteration_num})" if iteration_num else ""
    
    # Only print the raw JSON when logging level is set to DEBUG or higher
    logger = logging.getLogger("ChatAgent")
    if logger.level >= logging.DEBUG:
        console.print_json(json.dumps(result, indent=2))
    
    console.print(f"\n[bold green]🤖 Assistant{iteration_str}:[/bold green]")
    console.print(result["response"])
    
    # Display tool records if present
    if result.get("tool_records"):
        console.print("\n[bold magenta]🧰 Tools Used:[/bold magenta]")
        for i, tool_record in enumerate(result["tool_records"]):
            tool_name = tool_record.get("tool_name", "Unknown Tool")
            tool_args = tool_record.get("tool_args", {})
            tool_result = tool_record.get("tool_result", {})
            
            console.print(f"  [bold cyan]{tool_name}[/bold cyan] called with:")
            console.print_json(json.dumps(tool_args, indent=2))
            console.print("  [italic]Result:[/italic]")
            
            # Format result for better readability
            if isinstance(tool_result, dict) and "description" in tool_result:
                console.print(f"  {tool_result['description']}")
            else:
                console.print_json(json.dumps(tool_result, indent=2))
            
            # Add separator between tools
            if i < len(result["tool_records"]) - 1:
                console.print("  ---")
    
    # Indicate if this is the final response
    if not result.get("handoff"):
        console.print("\n[italic](Continuing to process...)[/italic]")


def handle_iteration_result(result: Dict[str, Any], iteration_counter: List[int]):
    """
    Handle and display an iteration result, including tool usage.
    
    Args:
        result: The iteration result from the agent
        iteration_counter: A mutable list containing the current iteration count
    """
    # Increment the iteration counter
    iteration_counter[0] += 1
    
    # Display the result to the user without showing JSON structure
    display_iteration_result(result, iteration_counter[0])


def interactive_session(agent: ChatAgent, image_path: Optional[str] = None, tool_names: Optional[List[str]] = None, 
                        model: str = "o3-mini", streaming: bool = True, logging_level: str = "none"):
    """
    Run an interactive chat session with the agent.
    
    Args:
        agent: The initialized ChatAgent instance
        image_path: Optional path to an image for the first message
        tool_names: Names of tools enabled for this session
        model: The model being used
        streaming: Whether streaming is enabled
        logging_level: Current logging level
    """
    # Display welcome message
    clear_screen()
    display_welcome_message()
    
    # Display configuration information
    console.print("[bold]📋 Session Configuration:[/bold]")
    console.print(f"  • Model: [cyan]{model}[/cyan]")
    console.print(f"  • Streaming: [cyan]{'Enabled' if streaming else 'Disabled'}[/cyan]")
    console.print(f"  • Max iterations: [cyan]{agent.max_iterations}[/cyan]")
    console.print(f"  • Logging level: [cyan]{logging_level}[/cyan]")
    if image_path:
        console.print(f"  • Starting with image: [cyan]{image_path}[/cyan]")
    console.print()
    
    # Display tool information
    if agent.tools:
        tool_names = [t.get('function', {}).get('name', 'unnamed') for t in agent.tools]
        console.print(f"[bold]🧰 Tools enabled:[/bold] {', '.join(tool_names)}")
        print_tool_details(agent.tools)
    else:
        console.print("[bold yellow]⚠️ No tools enabled for this session.[/bold yellow]")
    
    # If there's an image, use it for the first message
    if image_path and os.path.exists(image_path):
        console.print(f"Enter your first message to analyze this image:", style="bold")
    
    # Track pending image path for next message
    pending_image = image_path if image_path and os.path.exists(image_path) else None
    
    try:
        # Main interaction loop
        while True:
            # Get user input
            user_message = console.input("\n[bold blue]👤 You:[/bold blue]\n")
            
            # Check if it's a special command
            command_result = process_command(user_message, agent)
            
            # Handle command results
            if command_result == "exit":
                # Exit command was processed, break the loop
                break
            elif isinstance(command_result, tuple):
                # This is a special case for the image command which returns (True, image_path)
                _, pending_image = command_result
                continue
            elif command_result is True:
                # Command was processed, continue to next iteration
                continue
            elif command_result is False:
                # Not a command, process as a regular message
                pass
            
            # Process the message with image if available
            image_paths = [pending_image] if pending_image else None
            
            if image_paths:
                console.print(f"\n🖼️ Processing image: {pending_image}...\n", style="italic")
            
            # Set up iteration tracking
            iteration_counter = [0]  # Use a list for mutable counter
            
            # Call the chat method with the callback for intermediate results
            response = agent.chat(
                user_message, 
                image_paths=image_paths,
                callback=lambda result: handle_iteration_result(result, iteration_counter)
            )
            
            # Reset pending image after it's been used
            pending_image = None
            
    except KeyboardInterrupt:
        console.print("\n\nSession terminated by user. Goodbye! 👋", style="bold green")
    except Exception as e:
        console.print(f"\n\n[bold red]❌ Error: {str(e)}[/bold red]")
        # Print traceback for debugging
        import traceback
        traceback.print_exc()


def main():
    """Main entry point for the script."""
    # Load environment variables (including OPENAI_API_KEY)
    load_dotenv()
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Get tools based on user selection, respecting the --no-tools flag
    tools = get_active_tools(args.tools, disable_all=args.no_tools)
    
    # Get logging level
    log_level = LOGGING_LEVELS.get(args.logging.lower(), None)
    
    # Initialize the agent
    agent = ChatAgent(
        model=args.model,
        streaming=not args.no_stream,
        tools=tools,
        log_level=log_level,
        max_iterations=args.max_iterations
    )
    
    # Start interactive session
    interactive_session(
        agent, 
        args.image,
        tool_names=args.tools if not args.no_tools else [],
        model=args.model,
        streaming=not args.no_stream,
        logging_level=args.logging
    )


if __name__ == "__main__":
    main()