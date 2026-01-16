# Credit Card & Rewards Strategist

A ChatGPT-powered personal credit card and rewards strategist that tells users exactly which card to use, when to redeem points, and why — in plain conversation.

## What This App Does

This is a **conversational strategist** that runs inside ChatGPT via MCP (Model Context Protocol). It helps answer: "Which card should I use, when should I redeem, and why?"

The app provides MCP tools that return factual data about cards and rewards. ChatGPT uses this data to make recommendations and explain strategy in natural conversation.

**This is NOT:**
- A dashboard
- A finance tracker
- A bank app
- A transaction logger

**This IS:**
- A conversational strategist for credit card optimization
- A decision-making assistant that runs inside ChatGPT

## Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 2. Configure OpenAI API (Optional)

For enhanced chat responses, set your OpenAI API key:

```bash
export OPENAI_API_KEY="sk-proj-your-api-key-here"
```

Or create a `.env` file with:
```
OPENAI_API_KEY=sk-proj-your-api-key-here
```

### 3. Seed Initial Data (Optional)

Populate sample deals and available cards:

```bash
python3 seed_data.py
```

### 4. Start the Server

```bash
python3 main.py
```

The server will start on `http://0.0.0.0:8000`. The database is automatically created in your system's temp directory (check console output for exact path).

### 5. Connect to ChatGPT

1. Configure your MCP client to connect to the server at `http://0.0.0.0:8000`
2. Load the system prompt from `system_prompt.txt` into your ChatGPT configuration
3. The app is ready to use

## Operator Setup Guide

### Step 1: Create a User

The first time a user interacts, ChatGPT will automatically call `create_user()`:

```
User: "Which card should I use?"
ChatGPT: [Calls create_user(preference="balanced")]
         → Returns user_id (e.g., 1)
```

Or manually create a user:
- Tool: `create_user(preference="balanced")` (or "travel" or "cashback")
- Returns: `user_id`

### Step 2: Add Credit Cards

Users must add their cards before getting recommendations:

```
User: "I have HDFC Infinia"
ChatGPT: [Calls add_card(user_id=1, name="HDFC Infinia", bank="HDFC", reward_type="points")]
```

Available MCP tools:
- `create_user(preference="balanced")` - Create a new user
- `add_card(user_id, name, bank, reward_type)` - Add a credit card
- `list_cards(user_id)` - List all user's cards
- `activate_card(card_id)` / `deactivate_card(card_id)` - Manage card lifecycle

### Step 3: Seed Reward Rules

**Critical:** Cards need reward rules to work. Add rules for each card and category:

```
Tool: add_reward_rule(
    card_id=1,
    category="travel",
    earn_rate=5.0,  # 5% earn rate
    cap=50000.0,   # Optional: ₹50,000 cap per month
    notes="5x rewards on travel bookings"
)
```

Canonical categories: `travel`, `dining`, `shopping`, `online`, `fuel`, `general`, `other`

**Example setup for HDFC Infinia:**
```python
# Travel: 5% earn rate
add_reward_rule(card_id=1, category="travel", earn_rate=5.0, cap=50000.0)

# Dining: 3% earn rate
add_reward_rule(card_id=1, category="dining", earn_rate=3.0)

# General: 1% earn rate (fallback)
add_reward_rule(card_id=1, category="general", earn_rate=1.0)
```

### Step 4: Ask Strategy Questions

Once setup is complete, users can ask:

```
User: "Which card should I use for ₹10,000 travel booking?"
ChatGPT: [Calls recommend_best_card(user_id=1, spend_amount=10000, category="travel")]
         → Returns comparison data
         → Formats recommendation using response format contract
```

## Example ChatGPT Conversation

```
User: Which card should I use for ₹10,000 travel booking?

ChatGPT: [Calls recommend_best_card(user_id=1, spend_amount=10000, category="travel")]
         [Gets comparison data with estimated_value]

✅ Best card: HDFC Infinia
💰 Estimated value: ₹125

Why:
• 5% earn rate on travel (5x rewards)
• Earns 500 points worth ₹125 (points valued at 0.25x)
• Cap not breached this month

Watch out:
• Switch to another card after ₹50,000 travel spend this month (cap limit)
• Points expire after 3 years if not redeemed

---

User: What about ₹5,000 on Amazon?

ChatGPT: [Calls recommend_best_card(user_id=1, spend_amount=5000, category="shopping")]
         [Gets comparison data]

✅ Best card: HDFC Infinia
💰 Estimated value: ₹12.50

Why:
• 1% general earn rate applies (no shopping-specific rule)
• Earns 50 points worth ₹12.50

Watch out:
• Consider adding a shopping-specific card for better rewards on online purchases
```

## Available MCP Tools

### User Management
- `create_user(preference="balanced")` - Create a new user
- Returns: `user_id`

### Card Management
- `add_card(user_id, name, bank, reward_type)` - Add a credit card
- `list_cards(user_id)` - List all user's cards
- `activate_card(card_id)` - Activate a card
- `deactivate_card(card_id)` - Deactivate a card

### Reward Rules (Admin/Setup)
- `add_reward_rule(card_id, category, earn_rate, cap=None, notes="")` - Add reward rule
- `get_reward_rules(card_id)` - Get all rules for a card

### Strategy Tools
- `estimate_rewards(card_id, spend_amount, category)` - Estimate rewards for one card
- `recommend_best_card(user_id, spend_amount, category)` - Compare all cards

### Deals & Offers
- `get_deals(user_id, category=None, card_id=None)` - Get active deals
- `show_deals_ui(user_id, category=None)` - Show deals UI widget
- `add_deal(...)` - Add a new deal (admin)

### Card Recommendations
- `recommend_new_cards(user_id, preference=None)` - Get personalized card recommendations
- `show_recommendations_ui(user_id)` - Show recommendations UI widget
- `add_available_card(...)` - Add available card to database (admin)

### Enhanced Chat
- `enhanced_chat_response(user_query, context="")` - Get OpenAI-powered responses

**Note:** All tools return facts only. ChatGPT handles reasoning and recommendations.

## Response Format Contract

Every recommendation MUST follow this format (enforced by system prompt):

```
✅ Best card: <card_name>
💰 Estimated value: ₹<value>

Why:
• <reason 1>
• <reason 2>

Watch out:
• <cap / limit / trade-off>
```

## Category Clarification

If a user provides a non-canonical category (e.g., "Uber", "Amazon", "Swiggy"), ChatGPT will ask:

> "Should I treat this as travel, shopping, or something else?"

The backend does NOT silently guess categories. Users must clarify before proceeding.

Canonical categories: `travel`, `dining`, `shopping`, `online`, `fuel`, `general`, `other`

## Data Model

### Users
- `id` - Primary key
- `preference` - One of: `travel`, `cashback`, `balanced`

### Cards
- `id` - Primary key
- `user_id` - Foreign key to users
- `name` - Card name (e.g., "HDFC Infinia")
- `bank` - Bank name (e.g., "HDFC")
- `reward_type` - One of: `points`, `miles`, `cashback`
- `active` - Boolean flag (1 = active, 0 = inactive)

### Reward Rules
- `id` - Primary key
- `card_id` - Foreign key to cards
- `category` - Spending category (must be canonical)
- `earn_rate` - Reward rate as percentage (e.g., 5.0 for 5%)
- `cap` - Optional maximum reward cap
- `notes` - Optional notes about the rule

## Reward Value Normalization

The app normalizes different reward types for fair comparison:

- **Points**: 0.25x value (1 point = ₹0.25)
- **Miles**: 1.0x value (1 mile = ₹1.00)
- **Cashback**: 1.0x value (1% cashback = ₹1 per ₹100)

The `estimated_value` field in tool responses uses these conversion rates.

## Security Guarantees

**The app NEVER asks for:**
- Card numbers
- CVV codes
- OTPs
- Bank login credentials
- Expiry dates
- Any sensitive financial data

**Users only provide:**
- Card name (e.g., "HDFC Infinia")
- Bank name (e.g., "HDFC")
- Reward type (points/miles/cashback)

All data is stored locally in SQLite. No external services are called.

## Onboarding Flow

ChatGPT follows this automatic onboarding sequence:

1. **Check user exists** → If not, call `create_user()`
2. **Check cards exist** → If not, guide user to add cards
3. **Check reward rules exist** → If not, state setup is incomplete
4. **Proceed with strategy** → Only after all setup is complete

## Development

The app uses:
- **FastMCP** - MCP server framework
- **aiosqlite** - Async SQLite database
- **SQLite** - Local database storage

## Troubleshooting

**"No active cards found"**
→ User needs to add cards first using `add_card()`

**"No reward rule found for category"**
→ Card needs reward rules added using `add_reward_rule()`

**"Category must be one of: ..."**
→ Use canonical categories only, or ask user to clarify

**Database errors**
→ Check file permissions in temp directory (see console output for path)

## New Features (SaveSage-style)

### Deal Surfacing
Users can ask "Show me deals" or "What offers do I have?" to see active deals and promotions for their cards. The deals widget displays:
- Discount percentages and amounts
- Valid until dates
- Merchant information
- Category filters

### Card Recommendations
The app suggests new cards users don't have based on their spending profile. Ask "What cards should I get?" to see personalized recommendations with:
- Key benefits
- Annual fees
- Target audience matching

### Enhanced Chat
With OpenAI API configured, the app can answer complex questions like:
- "Do I have lounge access on any card?"
- "When do my points expire?"
- "Which card is best for international travel?"

## Notes

- Database is stored in system temp directory (check console output for exact path)
- All tools return facts only - ChatGPT handles reasoning and recommendations
- The system prompt enforces proper behavior and response format
- OpenAI API key is optional but enables enhanced chat responses
- Seed data script populates sample deals and available cards
- This is an MVP intended to run inside ChatGPT as a conversational product