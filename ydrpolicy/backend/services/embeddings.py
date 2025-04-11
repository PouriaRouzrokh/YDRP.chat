import asyncio
from typing import List, Dict, Any, Optional
import logging

from openai import AsyncOpenAI

from ydrpolicy.backend.config import config
from ydrpolicy.backend.logger import logger

# Cache for the OpenAI client
_client = None


def get_openai_client() -> AsyncOpenAI:
    """
    Get an AsyncOpenAI client instance.
    
    Returns:
        AsyncOpenAI client
    """
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=config.OPENAI.API_KEY,
        )
    return _client


async def embed_text(text: str, model: Optional[str] = None) -> List[float]:
    """
    Generate embeddings for a text using OpenAI's API.
    
    Args:
        text: Text to embed
        model: Embedding model to use (defaults to config value)
        
    Returns:
        List of floats representing the embedding vector
    """
    if not text or not text.strip():
        logger.warning("Attempted to embed empty text")
        # Return a zero vector of the appropriate size
        return [0.0] * config.RAG.EMBEDDING_DIMENSIONS
    
    client = get_openai_client()
    
    if model is None:
        model = config.RAG.EMBEDDING_MODEL
    
    try:
        logger.debug(f"Generating embedding for text: {text[:50]}...")
        response = await client.embeddings.create(
            model=model,
            input=text
        )
        logger.debug(f"Successfully generated embedding with dimensions: {len(response.data[0].embedding)}")
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        raise


async def embed_texts(texts: List[str], model: Optional[str] = None) -> List[List[float]]:
    """
    Generate embeddings for multiple texts using OpenAI's API.
    
    This batches the requests to improve efficiency.
    
    Args:
        texts: List of texts to embed
        model: Embedding model to use (defaults to config value)
        
    Returns:
        List of embedding vectors
    """
    if not texts:
        return []
    
    client = get_openai_client()
    
    if model is None:
        model = config.RAG.EMBEDDING_MODEL
    
    # Remove empty strings and track their positions
    valid_texts = []
    empty_indices = []
    
    for i, text in enumerate(texts):
        if text and text.strip():
            valid_texts.append(text)
        else:
            empty_indices.append(i)
            logger.warning(f"Empty text at index {i} will receive a zero vector")
    
    try:
        if valid_texts:
            logger.info(f"Generating embeddings for {len(valid_texts)} texts")
            response = await client.embeddings.create(
                model=model,
                input=valid_texts
            )
            embeddings = [item.embedding for item in response.data]
            logger.info(f"Successfully generated {len(embeddings)} embeddings")
        else:
            embeddings = []
        
        # Reinsert zero vectors for empty texts
        zero_vector = [0.0] * config.RAG.EMBEDDING_DIMENSIONS
        result = []
        valid_idx = 0
        
        for i in range(len(texts)):
            if i in empty_indices:
                result.append(zero_vector)
            else:
                result.append(embeddings[valid_idx])
                valid_idx += 1
                
        return result
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        raise


class DummyEmbedding:
    """
    Dummy embedding class for testing without OpenAI API access.
    
    This generates deterministic vectors based on the hash of the text
    so that similar texts get similar vectors.
    """
    
    @staticmethod
    async def embed(text: str) -> List[float]:
        """
        Generate a dummy embedding vector for testing.
        
        Args:
            text: Text to embed
            
        Returns:
            Dummy embedding vector
        """
        import hashlib
        
        # Get the hash of the text
        hash_obj = hashlib.md5(text.encode())
        hash_bytes = hash_obj.digest()
        
        # Create a vector from the hash
        dimensions = config.RAG.EMBEDDING_DIMENSIONS
        
        # Expand the hash to fill the required dimensions
        expanded_bytes = hash_bytes * (dimensions // len(hash_bytes) + 1)
        
        # Convert to vector of floats between -1 and 1
        vector = []
        for i in range(dimensions):
            val = (expanded_bytes[i] / 255.0) * 2 - 1
            vector.append(val)
        
        # Normalize the vector
        norm = sum(x*x for x in vector) ** 0.5
        if norm > 0:
            vector = [x/norm for x in vector]
        
        logger.debug(f"Generated dummy embedding for text: {text[:50]}...")
        return vector


# For testing without API access
async def dummy_embed_text(text: str) -> List[float]:
    """
    Generate a dummy embedding for testing without OpenAI API.
    
    Args:
        text: Text to embed
        
    Returns:
        Dummy embedding vector
    """
    return await DummyEmbedding.embed(text)


async def dummy_embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate dummy embeddings for multiple texts.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of dummy embedding vectors
    """
    results = []
    for text in texts:
        if text and text.strip():
            results.append(await dummy_embed_text(text))
        else:
            results.append([0.0] * config.RAG.EMBEDDING_DIMENSIONS)
    return results