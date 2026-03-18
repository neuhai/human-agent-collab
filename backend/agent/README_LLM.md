# LLM Client Configuration

This system supports multiple LLM providers for agent actions. Configure your preferred provider using environment variables.

## Supported Providers

- **Azure OpenAI** (recommended)
- **OpenAI**
- **Anthropic Claude**
- **Mock** (for testing, no API calls)

## Configuration

### Azure OpenAI (Recommended)

Set the following environment variables:

```bash
export LLM_PROVIDER=azure
export AZURE_OPENAI_ENDPOINT=https://situated-agent-resource.cognitiveservices.azure.com/
export AZURE_OPENAI_API_KEY=your-api-key-here
export AZURE_OPENAI_DEPLOYMENT=gpt-4o
export AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

### OpenAI

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=your-openai-api-key-here
```

### Anthropic Claude

```bash
export LLM_PROVIDER=claude
export ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

### Mock (Testing)

```bash
export LLM_PROVIDER=mock
# No API key needed
```

## Programmatic Configuration

You can also configure the LLM client programmatically when creating an agent runner:

```python
from agent.agent_runner import register_agent_runner

# Azure OpenAI
llm_config = {
    'provider': 'azure',
    'endpoint': 'your azure endpoint',
    'api_key': 'your-api-key',
    'deployment': 'gpt-4o',
    'api_version': '2024-12-01-preview'
}

register_agent_runner(
    participant_id=participant_id,
    session_id=session_id,
    experiment_type=experiment_type,
    llm_config=llm_config
)
```

## Default Behavior

If no configuration is provided, the system will use the **Mock LLM client**, which returns empty actions for testing purposes.

