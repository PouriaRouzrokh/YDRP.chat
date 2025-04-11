"""
Tool implementations for the ChatAgent.
Contains actual Python functions that implement the tools available to the agent.
"""

from typing import Dict, Any, List, Optional


def calculator(operation: str, a: float, b: float) -> Dict[str, Any]:
    """
    Perform a basic arithmetic operation.
    
    Args:
        operation: The arithmetic operation to perform (add, subtract, multiply, divide)
        a: The first number
        b: The second number
        
    Returns:
        Dictionary containing the result and a description
    """
    result = None
    
    if operation == "add":
        result = a + b
        description = f"The sum of {a} and {b} is {result}"
    elif operation == "subtract":
        result = a - b
        description = f"The difference of {a} and {b} is {result}"
    elif operation == "multiply":
        result = a * b
        description = f"The product of {a} and {b} is {result}"
    elif operation == "divide":
        if b == 0:
            return {
                "error": "Division by zero is not allowed",
                "result": None
            }
        result = a / b
        description = f"The division of {a} by {b} is {result}"
    else:
        return {
            "error": f"Unsupported operation: {operation}",
            "result": None
        }
    
    return {
        "result": result,
        "description": description
    }


def text_analyzer(text: str, analysis_type: str, target: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze text according to the specified analysis type.
    
    Args:
        text: The text to analyze
        analysis_type: The type of analysis to perform 
                      (count_char, word_count, find_occurrences)
        target: The target character or word to find/count (optional)
        
    Returns:
        Dictionary containing the analysis results
    """
    if not text:
        return {
            "error": "No text provided for analysis",
            "result": None
        }
    
    if analysis_type == "count_char":
        if not target or len(target) != 1:
            return {
                "error": "For character counting, please provide a single character as target",
                "result": None
            }
        
        count = text.lower().count(target.lower())
        return {
            "count": count,
            "description": f"The character '{target}' appears {count} times in the text"
        }
        
    elif analysis_type == "word_count":
        words = text.split()
        count = len(words)
        return {
            "count": count,
            "description": f"The text contains {count} words"
        }
        
    elif analysis_type == "find_occurrences":
        if not target:
            return {
                "error": "For finding occurrences, please provide a target word",
                "result": None
            }
        
        # Convert to lowercase for case-insensitive matching
        text_lower = text.lower()
        target_lower = target.lower()
        
        # Find all occurrences (starting positions)
        occurrences = []
        start = 0
        
        while True:
            start = text_lower.find(target_lower, start)
            if start == -1:
                break
            occurrences.append(start)
            start += 1
        
        count = len(occurrences)
        return {
            "count": count,
            "positions": occurrences,
            "description": f"The word '{target}' appears {count} times in the text"
        }
    
    else:
        return {
            "error": f"Unsupported analysis type: {analysis_type}",
            "result": None
        }


# Map tool names to their implementation functions
TOOL_REGISTRY = {
    "calculator": calculator,
    "text_analyzer": text_analyzer
} 