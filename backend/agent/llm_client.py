"""
LLM Client Manager: Supports multiple LLM providers (OpenAI, Azure OpenAI, Claude, etc.)

This module provides a unified interface for different LLM providers.
"""

import os
from typing import Optional, Any, Dict
from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Abstract base class for LLM clients"""

    def supports_multimodal_images(self) -> bool:
        """True if chat.completions accepts OpenAI-style image_url parts in message content."""
        return False
    
    @abstractmethod
    def chat_completions_create(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Create a chat completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (optional, may use default)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
        
        Returns:
            Response content as string
        """
        pass


class OpenAIClient(LLMClient):
    """OpenAI API client"""

    def supports_multimodal_images(self) -> bool:
        return True
    
    def __init__(self, api_key: str):
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")
    
    def chat_completions_create(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        model = model or "gpt-4o-mini"
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        return response.choices[0].message.content


class AzureOpenAIClient(LLMClient):
    """Azure OpenAI API client"""

    def supports_multimodal_images(self) -> bool:
        return True
    
    def __init__(
        self,
        api_key: str,
        endpoint: str,
        api_version: str = "2024-12-01-preview",
        deployment: Optional[str] = None
    ):
        try:
            from openai import AzureOpenAI
            self.client = AzureOpenAI(
                api_version=api_version,
                azure_endpoint=endpoint,
                api_key=api_key,
            )
            self.deployment = deployment
        except ImportError:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")
    
    def chat_completions_create(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        # For Azure, use deployment name as model
        deployment = model or self.deployment
        if not deployment:
            raise ValueError("Azure OpenAI requires deployment name (model parameter)")
        
        # Build call arguments
        call_kwargs = {
            'model': deployment,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens or 4096,
        }
        
        # Merge with additional kwargs (including response_format if provided)
        call_kwargs.update(kwargs)
        
        response = self.client.chat.completions.create(**call_kwargs)
        
        return response.choices[0].message.content


class ClaudeClient(LLMClient):
    """Anthropic Claude API client"""
    
    def __init__(self, api_key: str):
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("Anthropic package not installed. Install with: pip install anthropic")
    
    def chat_completions_create(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        model = model or "claude-3-5-sonnet-20241022"
        max_tokens = max_tokens or 4096
        
        # Convert messages format for Claude (Claude uses different format)
        # Claude expects system message separately and messages without system role
        system_message = None
        claude_messages = []
        
        for msg in messages:
            if msg.get('role') == 'system':
                system_message = msg.get('content')
            else:
                claude_messages.append({
                    'role': msg.get('role'),
                    'content': msg.get('content')
                })
        
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_message,
            messages=claude_messages,
            **kwargs
        )
        
        # Claude returns content as a list of text blocks
        if response.content and len(response.content) > 0:
            return response.content[0].text
        return ""


class MockLLMClient(LLMClient):
    """Mock LLM client for testing (returns empty actions)"""
    
    def chat_completions_create(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        import json
        return json.dumps({
            "planning": "Mock planning: I will wait and observe.",
            "actions": []
        })


def create_llm_client(config: Optional[Dict[str, Any]] = None) -> Optional[LLMClient]:
    """
    Create an LLM client based on configuration.
    
    Configuration can be provided via:
    1. config dict parameter
    2. Environment variables
    
    Environment variables (for Azure OpenAI):
    - LLM_PROVIDER: "azure", "openai", "claude", or "mock"
    - AZURE_OPENAI_ENDPOINT: Azure endpoint URL
    - AZURE_OPENAI_API_KEY: Azure API key
    - AZURE_OPENAI_DEPLOYMENT: Deployment name (e.g., "gpt-4o")
    - AZURE_OPENAI_API_VERSION: API version (default: "2024-12-01-preview")
    - OPENAI_API_KEY: OpenAI API key
    - ANTHROPIC_API_KEY: Anthropic API key
    
    Args:
        config: Optional configuration dict with provider settings
    
    Returns:
        LLMClient instance or None if no valid configuration found
    """
    # Use config if provided, otherwise read from environment
    if config:
        provider = config.get('provider', 'mock').lower()
    else:
        provider = os.getenv('LLM_PROVIDER', 'mock').lower()
    
    try:
        if provider == 'azure':
            # Azure OpenAI configuration
            if config:
                endpoint = config.get('endpoint')
                api_key = config.get('api_key')
                deployment = config.get('deployment')
                api_version = config.get('api_version', '2024-12-01-preview')
            else:
                endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
                api_key = os.getenv('AZURE_OPENAI_API_KEY')
                deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')
                api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')
            
            if not endpoint or not api_key:
                print('[LLMClient] Warning: Azure OpenAI endpoint or API key not set. Using mock LLM.')
                return MockLLMClient()
            
            if not deployment:
                print('[LLMClient] Warning: Azure OpenAI deployment not set. Using mock LLM.')
                return MockLLMClient()
            
            return AzureOpenAIClient(
                api_key=api_key,
                endpoint=endpoint,
                api_version=api_version,
                deployment=deployment
            )
        
        elif provider == 'openai':
            # OpenAI configuration
            if config:
                api_key = config.get('api_key')
            else:
                api_key = os.getenv('OPENAI_API_KEY')
            
            if not api_key:
                print('[LLMClient] Warning: OPENAI_API_KEY not set. Using mock LLM.')
                return MockLLMClient()
            
            return OpenAIClient(api_key=api_key)
        
        elif provider == 'claude':
            # Anthropic Claude configuration
            if config:
                api_key = config.get('api_key')
            else:
                api_key = os.getenv('ANTHROPIC_API_KEY')
            
            if not api_key:
                print('[LLMClient] Warning: ANTHROPIC_API_KEY not set. Using mock LLM.')
                return MockLLMClient()
            
            return ClaudeClient(api_key=api_key)
        
        else:
            # Default to mock
            print(f'[LLMClient] Unknown provider "{provider}". Using mock LLM.')
            return MockLLMClient()
    
    except Exception as e:
        print(f'[LLMClient] Error creating LLM client: {e}. Using mock LLM.')
        return MockLLMClient()

