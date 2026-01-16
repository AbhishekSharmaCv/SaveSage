# OpenAI API Integration Guide

## 🎯 Overview

OpenAI API is now integrated into **4 key tools** to provide intelligent, context-aware recommendations and responses. All integrations include graceful fallbacks if the API is unavailable.

## 📍 Tools Using OpenAI API

### 1. `recommend_new_cards()` - AI-Powered Card Recommendations

**Location:** `main.py` lines ~850-950

**What it does:**
- Analyzes user's existing card portfolio
- Identifies gaps in reward categories
- Recommends cards that complement existing cards
- Considers annual fees, benefits, and user preference

**AI Prompt Strategy:**
```
System: "You are a credit card recommendation expert. Always return only valid JSON arrays."

User: "Analyze user's existing cards and recommend top 5 cards that best complement 
their portfolio. Consider gaps in reward categories, reward type diversity, annual 
fee value, user preference, and benefits user doesn't currently have.

Return ONLY a JSON array of card IDs in order of recommendation."
```

**Fallback:** Rule-based matching by preference if AI fails

**When it's called:**
- User asks "What cards should I get?"
- `show_recommendations_ui()` tool calls it

---

### 2. `recommend_best_card()` - AI Tie-Breaking for Close Cards

**Location:** `main.py` lines ~587-595

**What it does:**
- When multiple cards have very similar reward values (within 5%)
- Uses AI to break ties considering:
  - User preference
  - Long-term value (annual fees, other benefits)
  - Reward type diversity
  - Cap status
  - Overall card benefits

**AI Prompt Strategy:**
```
System: "You are a credit card rewards strategist. Always return only valid JSON arrays of card IDs."

User: "Break a tie between cards with very similar reward values. Consider user preference, 
long-term value, reward type diversity, cap status, and overall benefits beyond just this transaction.

Return ONLY a JSON array of card_id values in recommended order."
```

**Fallback:** Value-based sorting if AI fails

**When it's called:**
- User asks "Which card should I use for ₹X on [category]?"
- Cards have similar estimated values

---

### 3. `get_deals()` - AI-Powered Deal Prioritization

**Location:** `main.py` lines ~860-920

**What it does:**
- Analyzes user's spending patterns from reward rules
- Prioritizes deals based on:
  - Match with frequent spending categories
  - Discount value
  - Card ownership (prioritizes user's cards)
  - Validity period
  - User preference

**AI Prompt Strategy:**
```
System: "You are a deals prioritization expert. Always return only valid JSON arrays of deal IDs."

User: "Rank deals by relevance to user. Consider match with spending patterns, 
discount value, card ownership, validity period, and user preference.

Return ONLY a JSON array of deal IDs in order of priority."
```

**Fallback:** Date-based sorting if AI fails

**When it's called:**
- User asks "Show me deals"
- `show_deals_ui()` tool calls it

---

### 4. `enhanced_chat_response()` - AI-Powered Q&A

**Location:** `main.py` lines ~950-1010

**What it does:**
- Answers complex questions about cards
- Uses user's card data as context
- Provides detailed, nuanced answers

**AI Prompt Strategy:**
```
System: "You are an expert credit card rewards strategist. Your role is to help users 
optimize their credit card usage and maximize rewards.

Guidelines:
- Always base answers on provided card data context
- Be specific about reward rates, caps, and limitations
- Explain trade-offs clearly
- If information is missing, say so rather than guessing
- Use Indian Rupees (₹) for all monetary values
- Be concise but thorough
- Prioritize actionable advice"

User: "Context about user's credit cards: {...}
User Question: {user_query}

Provide a clear, helpful answer based on the context above."
```

**Fallback:** Returns error message if API not configured

**When it's called:**
- User asks complex questions like:
  - "Do I have lounge access on any card?"
  - "When do my points expire?"
  - "Which card is best for international travel?"

---

## 🔄 Complete Flow with AI

### Flow 1: Card Recommendations (WITH AI)

```
User: "What cards should I get?"

ChatGPT:
  1. Calls recommend_new_cards(user_id=1)
  2. Tool:
     a. Fetches user's existing cards from SQLite
     b. Fetches all available cards
     c. Filters out cards user already has
     d. Calls OpenAI API with:
        - User's existing cards as context
        - All candidate cards
        - User preference
        - Prompt: "Recommend top 5 cards that complement portfolio"
     e. Gets ranked card IDs from AI
     f. Maps IDs back to card objects
     g. Returns ranked recommendations
  3. ChatGPT displays recommendations widget

✅ Uses OpenAI API for intelligent matching
```

### Flow 2: Card Selection with Tie-Breaking (WITH AI)

```
User: "Which card for ₹5,000 dining?"

ChatGPT:
  1. Calls recommend_best_card(user_id=1, spend_amount=5000, category="dining")
  2. Tool:
     a. Calculates rewards for all cards
     b. Sorts by estimated_value
     c. Detects top 3 cards are within 5% of each other
     d. Calls OpenAI API with:
        - Close cards data
        - User preference
        - Prompt: "Break tie considering long-term value"
     e. Gets AI-ranked card IDs
     f. Reorders cards based on AI ranking
  3. ChatGPT formats response with AI-recommended card first

✅ Uses OpenAI API for tie-breaking
```

### Flow 3: Deal Prioritization (WITH AI)

```
User: "Show me deals"

ChatGPT:
  1. Calls get_deals(user_id=1)
  2. Tool:
     a. Fetches all active deals from SQLite
     b. Fetches user's spending patterns from reward rules
     c. Calls OpenAI API with:
        - User's spending patterns
        - All deals
        - User preference
        - Prompt: "Rank deals by relevance to user"
     d. Gets AI-ranked deal IDs
     e. Reorders deals based on AI ranking
  3. Returns prioritized deals
  4. ChatGPT displays deals widget

✅ Uses OpenAI API for prioritization
```

### Flow 4: Complex Q&A (WITH AI)

```
User: "Do I have lounge access on any card?"

ChatGPT:
  1. Calls enhanced_chat_response("Do I have lounge access on any card?")
  2. Tool:
     a. Fetches user's cards and reward rules from SQLite
     b. Builds context JSON
     c. Calls OpenAI API with:
        - System prompt: "Expert credit card strategist..."
        - User query + card context
     d. Gets detailed answer from OpenAI
  3. Returns AI response
  4. ChatGPT displays answer

✅ Uses OpenAI API for detailed answers
```

## 🛡️ Error Handling & Fallbacks

All AI integrations include **graceful fallbacks**:

1. **If OpenAI API not configured:**
   - `recommend_new_cards()` → Rule-based matching
   - `recommend_best_card()` → Value-based sorting
   - `get_deals()` → Date-based sorting
   - `enhanced_chat_response()` → Returns error message

2. **If API call fails:**
   - All tools catch exceptions
   - Fall back to deterministic logic
   - Log error but don't break user experience
   - User gets results (maybe less optimal, but functional)

3. **If API returns invalid data:**
   - JSON parsing errors are caught
   - Falls back to deterministic logic
   - No crashes, seamless experience

## ⚙️ Configuration

### Required:
```bash
export OPENAI_API_KEY="sk-proj-your-key-here"
```

### Model Used:
- **gpt-4o-mini** (cost-effective, fast, good quality)

### Temperature Settings:
- **Recommendations:** 0.3 (more deterministic)
- **Tie-breaking:** 0.2 (very deterministic)
- **Deal prioritization:** 0.3 (balanced)
- **Q&A:** 0.7 (more creative, natural)

### Token Limits:
- **Recommendations:** 200 tokens
- **Tie-breaking:** 150 tokens
- **Deal prioritization:** 200 tokens
- **Q&A:** 500 tokens

## 📊 Performance Impact

### With OpenAI API:
- **Recommendations:** More personalized, better matching
- **Tie-breaking:** Smarter decisions considering long-term value
- **Deal prioritization:** Deals matched to spending patterns
- **Q&A:** Detailed, context-aware answers

### Without OpenAI API:
- **All features still work**
- Uses rule-based fallbacks
- Slightly less optimal but functional
- No additional latency

## 💡 Best Practices

1. **Always provide context** - AI gets user's card data
2. **Clear prompts** - Specific instructions for AI
3. **Structured outputs** - AI returns JSON arrays for parsing
4. **Error handling** - Graceful fallbacks everywhere
5. **Cost optimization** - Use gpt-4o-mini, limit tokens
6. **User experience** - Never block user if AI fails

## 🎯 Summary

**4 tools use OpenAI API:**
1. ✅ `recommend_new_cards()` - Smart card matching
2. ✅ `recommend_best_card()` - Tie-breaking
3. ✅ `get_deals()` - Deal prioritization
4. ✅ `enhanced_chat_response()` - Complex Q&A

**All have fallbacks** - App works without API

**All are optional** - Graceful degradation

**All use proper prompts** - Context-aware, structured outputs
