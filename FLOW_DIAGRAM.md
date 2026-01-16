# Complete Flow Diagram & OpenAI API Usage

## 🔄 Current Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ChatGPT Interface                            │
│  (User types messages, ChatGPT orchestrates via system prompt) │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastMCP Server (main.py)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  MCP Tools (Return Facts Only)                           │  │
│  │  • add_card, list_cards, recommend_best_card           │  │
│  │  • get_deals, show_deals_ui                              │  │
│  │  • recommend_new_cards, show_recommendations_ui          │  │
│  │  • enhanced_chat_response ← Uses OpenAI API             │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  UI Widget Resources                                      │  │
│  │  • cards_widget.html                                      │  │
│  │  • deals_widget.html                                      │  │
│  │  • recommendations_widget.html                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SQLite Database                                         │  │
│  │  • users, cards, reward_rules                            │  │
│  │  • available_cards, deals                                │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              OpenAI API (OPTIONAL - Only for enhanced_chat)     │
│  Used ONLY when enhanced_chat_response() tool is called         │
└─────────────────────────────────────────────────────────────────┘
```

## 📍 Where OpenAI API is Used

### ✅ **ONLY ONE PLACE:** `enhanced_chat_response()` tool

**Location:** `main.py` lines 950-1001

**When it's called:**
- User asks complex questions that need deeper analysis
- Examples:
  - "Do I have lounge access on any card?"
  - "When do my points expire?"
  - "Which card is best for international travel?"

**How it works:**
1. Tool fetches user's card data from SQLite
2. Builds context JSON with card details
3. Calls OpenAI API (gpt-4o-mini) with:
   - System prompt: "You are a credit card rewards strategist..."
   - User query + card context
4. Returns OpenAI's response

**Code:**
```python
@mcp.tool()
async def enhanced_chat_response(user_query: str, context: str = ""):
    client = get_openai_client()  # Gets OpenAI client
    if not client:
        return {"status": "error", "message": "OpenAI API not configured"}
    
    # Build context from user's cards
    # ... fetch from SQLite ...
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[...],
        max_tokens=500
    )
    
    return {"status": "success", "response": response.choices[0].message.content}
```

### ❌ **NOT Used In:**

- ✅ `add_card()` - Direct SQLite insert
- ✅ `list_cards()` - Direct SQLite query
- ✅ `recommend_best_card()` - SQLite queries + calculation logic
- ✅ `get_deals()` - Direct SQLite query
- ✅ `recommend_new_cards()` - SQLite queries + matching logic
- ✅ All UI widgets - Pure HTML/JS, no API calls
- ✅ All other tools - Pure database operations

## 🔀 Complete User Flow Examples

### Flow 1: Basic Card Recommendation (NO OpenAI API)

```
User: "Which card should I use for ₹10,000 travel?"

ChatGPT (via system prompt):
  1. Calls list_cards(user_id=1) → SQLite query
  2. Calls recommend_best_card(user_id=1, spend_amount=10000, category="travel")
     → SQLite queries + calculation logic
     → Returns: [{card_name, estimated_value, earn_rate, ...}]
  3. Formats response using system prompt rules
  4. Returns: "✅ Best card: HDFC Infinia, 💰 ₹125..."

NO OpenAI API called - All logic in MCP tools
```

### Flow 2: Show Deals (NO OpenAI API)

```
User: "Show me deals"

ChatGPT:
  1. Calls show_deals_ui(user_id=1)
     → Calls get_deals(user_id=1) internally
     → SQLite query: SELECT * FROM deals WHERE is_active=1
  2. Returns structuredContent with deals array
  3. ChatGPT renders deals_widget.html
  4. Widget displays deals carousel

NO OpenAI API called - Pure database + UI
```

### Flow 3: Card Recommendations (NO OpenAI API)

```
User: "What cards should I get?"

ChatGPT:
  1. Calls show_recommendations_ui(user_id=1)
     → Calls recommend_new_cards(user_id=1) internally
     → SQLite queries:
        - Get user's existing cards
        - Get all available_cards
        - Filter out duplicates
        - Match by preference (travel/cashback/balanced)
  2. Returns recommendations array
  3. ChatGPT renders recommendations_widget.html
  4. Widget displays recommendations

NO OpenAI API called - Pure matching logic
```

### Flow 4: Enhanced Chat (WITH OpenAI API) ⚡

```
User: "Do I have lounge access on any card?"

ChatGPT:
  1. Calls enhanced_chat_response("Do I have lounge access on any card?")
  2. Tool internally:
     a. Fetches user's cards from SQLite
     b. Builds context: {"cards": [...], "reward_rules": [...]}
     c. Calls OpenAI API:
        POST https://api.openai.com/v1/chat/completions
        {
          "model": "gpt-4o-mini",
          "messages": [
            {"role": "system", "content": "You are a credit card strategist..."},
            {"role": "user", "content": "Context: {...}\n\nQuestion: Do I have lounge access?"}
          ]
        }
     d. Gets response from OpenAI
  3. Returns: {"status": "success", "response": "Based on your cards..."}
  4. ChatGPT displays OpenAI's response

OpenAI API IS called here - Only tool that uses it
```

### Flow 5: Complex Question Without Enhanced Chat (NO OpenAI API)

```
User: "Which card for groceries?"

ChatGPT (via system prompt logic):
  1. Calls recommend_best_card(user_id=1, spend_amount=?, category="shopping")
  2. Gets data from SQLite
  3. ChatGPT's own reasoning (via system prompt) formats response
  4. Returns formatted recommendation

NO OpenAI API - ChatGPT's built-in reasoning handles it
```

## 🎯 Key Points

### OpenAI API Usage:
- **Only 1 tool uses it:** `enhanced_chat_response()`
- **Optional:** App works perfectly without it
- **When to use:** Complex questions that need deeper analysis
- **What it does:** Provides detailed answers using user's card data as context

### All Other Tools:
- **Pure SQLite operations** - No external APIs
- **Deterministic logic** - Same input = same output
- **Fast** - No network latency
- **No API costs** - Free to run

### ChatGPT's Role:
- **Orchestrates** - Decides which tools to call
- **Formats responses** - Uses system prompt rules
- **Renders widgets** - Displays UI components
- **Reasoning** - Uses its own knowledge for most queries

## 🔧 Configuration

### With OpenAI API:
```bash
export OPENAI_API_KEY="sk-proj-..."
python3 main.py
```
- All features work
- Enhanced chat available
- More detailed answers for complex questions

### Without OpenAI API:
```bash
python3 main.py
# (No OPENAI_API_KEY set)
```
- All features work except `enhanced_chat_response()`
- Other tools return error if enhanced_chat is called
- All other functionality unaffected

## 📊 Tool Dependency Map

```
┌─────────────────────────────────────────┐
│         ChatGPT (Orchestrator)         │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                 │
       ▼                 ▼
┌─────────────┐   ┌──────────────┐
│ MCP Tools   │   │ UI Widgets   │
│ (Facts)     │   │ (Display)   │
└──────┬──────┘   └──────┬───────┘
       │                 │
       └─────────┬───────┘
                 │
                 ▼
         ┌───────────────┐
         │  SQLite DB    │
         │  (Data)      │
         └───────────────┘
                 │
                 ▼ (Only for enhanced_chat_response)
         ┌───────────────┐
         │  OpenAI API   │
         │  (Optional)   │
         └───────────────┘
```

## 💡 Summary

**OpenAI API is used:**
- ✅ **ONLY** in `enhanced_chat_response()` tool
- ✅ **ONLY** when ChatGPT decides to call that tool
- ✅ **ONLY** for complex questions needing deeper analysis
- ✅ **OPTIONAL** - App works without it

**Everything else:**
- ❌ Uses pure SQLite queries
- ❌ Uses deterministic calculation logic
- ❌ No external API dependencies
- ❌ Fast and free to run

**ChatGPT's role:**
- Decides which tools to call (via system prompt)
- Formats responses (via system prompt rules)
- Renders UI widgets
- Uses its own reasoning for most queries
