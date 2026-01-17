# OpenAI API Integration Guide

This document explains how the system prompt is integrated and how OpenAI API helps with tool selection and understanding.

## System Prompt Integration

### Problem
ChatGPT MCP apps don't automatically load system prompts. The system needs a way to ensure ChatGPT follows the correct behavior rules, onboarding flow, and response format.

### Solution

1. **System Prompt File** (`system_prompt.txt`)
   - Contains all behavior rules, onboarding logic, response format, and examples
   - Loaded at startup and available to all tools

2. **`get_system_instructions()` Tool**
   - ChatGPT can call this tool to get the complete system prompt
   - Returns all rules, flows, and examples
   - Use this when ChatGPT needs to understand expected behavior

3. **`suggest_tool_for_query()` Tool**
   - Uses OpenAI API to analyze user queries
   - Suggests which tool(s) to call and in what order
   - Ensures correct onboarding flow (create_user → manage_cards_ui → recommend_best_card)
   - Helps ChatGPT understand user intent and select appropriate tools

4. **Enhanced `enhanced_chat_response()` Tool**
   - Now uses the actual `system_prompt.txt` file instead of hardcoded instructions
   - Ensures consistent behavior across all AI-powered responses
   - Uses USD ($) instead of ₹ for US market

## How It Works

### 1. Startup
```python
SYSTEM_PROMPT = load_system_prompt()  # Loads system_prompt.txt
```

### 2. Tool Selection Helper
When ChatGPT receives a user query, it can call:
```python
suggest_tool_for_query(user_query="Which card for groceries?", user_id=1)
```

This returns:
```json
{
  "primary_tool": "recommend_best_card",
  "secondary_tools": ["list_cards", "get_reward_rules"],
  "reasoning": "User wants card recommendation for groceries",
  "required_params": {"category": "groceries", "spend_amount": 0},
  "onboarding_needed": false
}
```

### 3. System Instructions Access
ChatGPT can call:
```python
get_system_instructions()
```

This returns the complete system prompt with:
- Onboarding logic
- Response format rules
- Tool usage guidelines
- Category clarification rules
- Trade-off logic
- All examples

### 4. Enhanced Responses
The `enhanced_chat_response()` tool now:
- Loads system prompt from file
- Uses it as the system message for OpenAI API
- Ensures consistent behavior and formatting

## OpenAI API Key

The API key is configured in two ways:
1. **Environment Variable** (preferred): `OPENAI_API_KEY`
2. **Hardcoded Fallback** (for testing): Set in `get_openai_client()`

**Note**: For production, use environment variables only. Remove hardcoded keys.

## Usage Examples

### Example 1: First-time User
```
User: "Which card should I use for groceries?"

ChatGPT Flow:
1. Calls suggest_tool_for_query() → detects no cards exist
2. Returns: {"primary_tool": "manage_cards_ui", "onboarding_needed": true}
3. ChatGPT calls manage_cards_ui() to open card manager
4. Guides user to add cards first
```

### Example 2: Tool Selection
```
User: "Show me my wallet summary"

ChatGPT Flow:
1. Calls suggest_tool_for_query() → detects cards exist
2. Returns: {"primary_tool": "show_wallet_summary"}
3. ChatGPT calls show_wallet_summary()
4. Displays wallet summary widget
```

### Example 3: Complex Query
```
User: "I'm confused about which card to use"

ChatGPT Flow:
1. Calls suggest_tool_for_query() → suggests multiple tools
2. May call get_system_instructions() to understand response format
3. Calls recommend_best_card() or enhanced_chat_response()
4. Provides clear explanation following system prompt rules
```

## Benefits

1. **Consistent Behavior**: All AI responses follow the same system prompt
2. **Correct Tool Selection**: AI helps ChatGPT choose the right tools
3. **Onboarding Flow**: Ensures users go through proper setup
4. **Response Format**: All recommendations follow the same format
5. **Trade-off Logic**: When cards are close in value, explains trade-offs

## Testing

To test the integration:

1. **Test System Prompt Loading**:
   ```python
   # In ChatGPT, call:
   get_system_instructions()
   ```

2. **Test Tool Selection**:
   ```python
   # In ChatGPT, call:
   suggest_tool_for_query("Which card for $500 groceries?", user_id=1)
   ```

3. **Test Enhanced Response**:
   ```python
   # In ChatGPT, call:
   enhanced_chat_response("What's the best card for travel?", user_id=1)
   ```

## Troubleshooting

### Issue: System prompt not loading
- Check that `system_prompt.txt` exists in the project root
- Check file permissions
- Look for error messages in console

### Issue: OpenAI API not working
- Verify API key is set (environment variable or hardcoded)
- Check network connectivity
- Verify API key is valid and has credits

### Issue: Wrong tools being called
- Call `get_system_instructions()` to ensure ChatGPT understands rules
- Use `suggest_tool_for_query()` to get tool suggestions
- Check user state (user exists, cards exist)

## Next Steps

1. **Remove Hardcoded API Key**: Use environment variables only
2. **Add Logging**: Log tool selections and API calls
3. **Add Caching**: Cache system prompt to avoid repeated file reads
4. **Add Validation**: Validate tool suggestions before execution
