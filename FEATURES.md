# SaveSage-style Features Implementation

This document describes the new features added to replicate SaveSage's core functions in ChatGPT.

## ✅ Implemented Features

### 1. Deal Surfacing & Alerts

**MCP Tools:**
- `get_deals(user_id, category=None, card_id=None)` - Get active deals
- `show_deals_ui(user_id, category=None)` - Display deals widget
- `add_deal(...)` - Add new deal (admin function)

**UI Widget:** `deals_widget.html`
- Displays active deals in a carousel
- Shows discount percentages, merchants, categories
- Filters by category and card
- Auto-refreshes when deals update

**Usage:**
```
User: "Show me deals"
ChatGPT: [Calls show_deals_ui()]
         [Widget renders with active deals]
```

### 2. Personalized Card Recommendations

**MCP Tools:**
- `recommend_new_cards(user_id, preference=None)` - Get recommendations
- `show_recommendations_ui(user_id)` - Display recommendations widget
- `add_available_card(...)` - Add available card (admin function)

**UI Widget:** `recommendations_widget.html`
- Shows cards user doesn't have
- Matches based on user preference (travel/cashback/balanced)
- Displays key benefits, annual fees, target audience
- "Learn More" buttons for each card

**Usage:**
```
User: "What cards should I get?"
ChatGPT: [Calls show_recommendations_ui()]
         [Widget renders with personalized recommendations]
```

### 3. Enhanced Chat with OpenAI API

**MCP Tool:**
- `enhanced_chat_response(user_query, context="")` - Get OpenAI-powered responses

**Features:**
- Answers complex questions about cards
- Uses user's card data as context
- Handles questions like:
  - "Do I have lounge access on any card?"
  - "When do my points expire?"
  - "Which card is best for international travel?"

**Configuration:**
Set `OPENAI_API_KEY` environment variable:
```bash
export OPENAI_API_KEY="sk-proj-your-key-here"
```

### 4. Database Extensions

**New Tables:**
- `available_cards` - Cards available for recommendations
- `deals` - Active deals and offers

**Schema:**
```sql
available_cards:
  - id, name, bank, reward_type
  - annual_fee, key_benefits, target_audience, min_income

deals:
  - id, title, description, card_id, card_name
  - category, discount_percent, discount_amount
  - valid_from, valid_until, merchant, terms
```

## 🎨 UI Widgets

All widgets follow OpenAI Apps SDK patterns:
- Use `window.openai.toolOutput` to read data
- Use `window.openai.callTool()` for tool calls
- Use `window.openai.onToolOutput()` for lifecycle
- Render inline in ChatGPT interface

### Widgets Created:
1. `cards_widget.html` - Card management (existing, enhanced)
2. `deals_widget.html` - Deals carousel (new)
3. `recommendations_widget.html` - Recommendations carousel (new)

## 📊 Data Seeding

**Seed Script:** `seed_data.py`

Populates:
- 6 sample available cards (HDFC Infinia, Axis Magnus, SBI Cashback, etc.)
- 4 sample deals (Swiggy cashback, Amazon rewards, travel bonuses, etc.)

**Run:**
```bash
python3 seed_data.py
```

## 🔧 Setup Instructions

1. **Install dependencies:**
   ```bash
   uv sync
   # or
   pip install -e .
   ```

2. **Set OpenAI API key (optional):**
   ```bash
   export OPENAI_API_KEY="sk-proj-your-key-here"
   ```

3. **Seed initial data:**
   ```bash
   python3 seed_data.py
   ```

4. **Start server:**
   ```bash
   python3 main.py
   ```

## 💬 Example Conversations

### Deal Surfacing
```
User: "Show me deals for dining"
ChatGPT: [Calls show_deals_ui(user_id=1, category="dining")]
         [Widget shows dining deals]
```

### Card Recommendations
```
User: "What cards should I get?"
ChatGPT: [Calls show_recommendations_ui(user_id=1)]
         [Widget shows personalized recommendations]
```

### Enhanced Chat
```
User: "Do I have lounge access on any card?"
ChatGPT: [Calls enhanced_chat_response("Do I have lounge access on any card?")]
         [Returns detailed answer based on user's cards]
```

## 🎯 Architecture

- **Backend:** FastMCP server with SQLite
- **Frontend:** HTML widgets with vanilla JS
- **AI:** OpenAI API for enhanced responses (optional)
- **Data:** Static/seeded data (no external APIs required for MVP)

## 📝 Notes

- All existing functionality preserved
- No breaking changes to existing tools
- OpenAI API is optional (app works without it)
- Deals and recommendations use static data (can be extended with APIs later)
- UI widgets follow ChatGPT UI guidelines

## 🚀 Future Enhancements

- Real-time deal fetching from bank APIs
- Machine learning for better recommendations
- Travel redemption search integration
- Points balance tracking
- Merchant category lookup
