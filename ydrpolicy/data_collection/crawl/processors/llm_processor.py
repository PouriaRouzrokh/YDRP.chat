"""
Module for handling LLM interactions for content analysis and OCR.
"""
import os
import json
from types import SimpleNamespace
from typing import Dict, Optional, Union, List
from openai import OpenAI
from pydantic import BaseModel, Field
import logging

# Third-party imports
from mistralai import Mistral

# Local imports
from ydrpolicy.data_collection.crawl.processors import llm_prompts
    
# Initialize logger
logger = logging.getLogger(__name__)

class PolicyContent(BaseModel):
    """Pydantic model for structured policy content extraction."""
    include: bool = Field(description="Whether the content contains policy information")
    content: str = Field(description="The extracted policy content")
    definite_links: List[str] = Field(default_factory=list, description="Links that definitely contain policy information")
    probable_links: List[str] = Field(default_factory=list, description="Links that might contain policy information")

def process_document_with_ocr(document_url: str, config: SimpleNamespace) -> str:
    """
    Process a document using Mistral's OCR capabilities.
    
    Args:
        document_url: URL of the document to process
        
    Returns:
        Extracted text in markdown format
    """
    try:
        if not config.LLM.MISTRAL_API_KEY:
            raise ValueError("MISTRAL_API_KEY is not set in the environment variables")
        
        client = Mistral(api_key=config.LLM.MISTRAL_API_KEY)
        
        logger.info(f"Processing document with OCR: {document_url}")
        ocr_response = client.ocr.process(
            model=config.LLM.OCR_MODEL,
            document={
                "type": "document_url",
                "document_url": document_url
            },
            include_image_base64=False
        )
        
        # Extract text from OCR response
        if hasattr(ocr_response, 'text'):
            return ocr_response.text
        
        # If the response structure is different, attempt to extract text
        if isinstance(ocr_response, dict) and 'text' in ocr_response:
            return ocr_response['text']
            
        logger.warning(f"Unexpected OCR response structure: {type(ocr_response)}")
        return str(ocr_response)
        
    except Exception as e:
        logger.error(f"Error processing document with OCR: {str(e)}")
        return f"Error processing document: {str(e)}"

def analyze_content_for_policies(content: str, url: str, links: list = None, config: SimpleNamespace = None) -> Dict[str, Union[bool, str, list]]:
    """
    Analyze content using LLM to detect policy information and relevant links.
    
    Args:
        content: The content to analyze
        url: The source URL of the content
        links: List of links from the page (optional)
        
    Returns:
        Dictionary with 'include', 'content', 'definite_links', and 'probable_links' keys
    """
    try:
        if not config.LLM.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in the environment variables")
        
        os.environ["OPENAI_API_KEY"] = config.LLM.OPENAI_API_KEY
        
        # Add links information to the prompt if available
        links_info = ""
        if links and len(links) > 0:
            links_info = "\n\nLinks found on the page:\n"
            for i, (link_url, link_text) in enumerate(links[:50]):  # Limit to 50 links to avoid token limits
                links_info += f"{i+1}. [{link_text}]({link_url})\n"
        
        # Prepare messages
        messages = [
            {"role": "system", "content": llm_prompts.POLICY_DETECTION_SYSTEM_PROMPT},
            {"role": "user", "content": llm_prompts.POLICY_DETECTION_USER_PROMPT.format(
                url=url,
                content=content[:15000] + links_info  # Add links info
            )}
        ]
        
        logger.info(f"Analyzing content for policies from: {url}")
        
        try:
            # Get completion from LLM with proper Pydantic model
            openai_client = OpenAI(api_key=config.LLM.OPENAI_API_KEY)
            response = openai_client.chat.completions.create(
                model=config.LLM.CRAWLER_LLM_MODEL,
                messages=messages,
                response_format={"type": "json_object"}
            )
            
            # Process the response
            if hasattr(response, 'choices') and len(response.choices) > 0:
                result_text = response.choices[0].message.content
                # Parse the JSON manually first
                result_dict = json.loads(result_text)
                
                # Then create a PolicyContent object from it
                policy_content = PolicyContent(
                    include=result_dict.get('include', False),
                    content=result_dict.get('content', ""),
                    definite_links=result_dict.get('definite_links', []),
                    probable_links=result_dict.get('probable_links', [])
                )
                
                # Convert to dictionary
                result = policy_content.model_dump()
                logger.info(f"LLM analysis complete for {url}. Policy detected: {result['include']}")
                return result
                
        except Exception as parsing_error:
            logger.warning(f"Error parsing LLM response: {str(parsing_error)}")
            # Try direct JSON approach as fallback
            try:
                openai_client = OpenAI(api_key=config.LLM.OPENAI_API_KEY)
                response = openai_client.chat.completions.create(
                    model=config.LLM.CRAWLER_LLM_MODEL,
                    messages=messages,
                    response_format={"type": "json_object"}
                )
                
                if hasattr(response, 'choices') and len(response.choices) > 0:
                    result_text = response.choices[0].message.content
                    result = json.loads(result_text)
                    
                    # Ensure all expected keys are present
                    result.setdefault('include', False)
                    result.setdefault('content', "")
                    result.setdefault('definite_links', [])
                    result.setdefault('probable_links', [])
                    
                    logger.info(f"LLM analysis complete for {url} (fallback method). Policy detected: {result['include']}")
                    return result
            except Exception as fallback_error:
                logger.error(f"Error in fallback parsing: {str(fallback_error)}")
                
        # Default return if all else fails
        return {
            "include": False, 
            "content": "", 
            "definite_links": [], 
            "probable_links": []
        }
        
    except Exception as e:
        logger.error(f"Error analyzing content: {str(e)}")
        return {
            "include": False, 
            "content": "", 
            "definite_links": [], 
            "probable_links": []
        }