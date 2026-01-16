# ChatGPT UI Test Queries

Use these exact queries (or variations) in ChatGPT to trigger the UI widgets.

## 🎯 Card Management UI

**To see the card management widget:**

### Query Options:
```
"I want to add my cards"
"Show me the card manager"
"Open card manager"
"Let me add my credit cards"
"I need to add cards"
"Manage my cards"
```

**What happens:**
- ChatGPT calls `manage_cards_ui(user_id=1)`
- Widget `cards_widget.html` renders inline
- You'll see:
  - Add Card Form (name, bank, reward type)
  - Your existing cards list
  - Activate/Deactivate buttons

**Example conversation:**
```
You: "I want to add my cards"

ChatGPT: [Calls manage_cards_ui]
         [Widget renders]
         "Card manager opened. You have 0 card(s)."
```

---

## 🎁 Deals & Offers UI

**To see the deals widget:**

### Query Options:
```
"Show me deals"
"What offers do I have?"
"Show me active deals"
"Are there any deals for my cards?"
"Show deals for dining"
"Show me travel deals"
```

**What happens:**
- ChatGPT calls `show_deals_ui(user_id=1)` or `show_deals_ui(user_id=1, category="dining")`
- Widget `deals_widget.html` renders inline
- You'll see:
  - Active deals carousel
  - Discount percentages
  - Merchant information
  - Validity dates

**Example conversation:**
```
You: "Show me deals"

ChatGPT: [Calls show_deals_ui]
         [Widget renders]
         "Found 4 active deal(s) for you."
```

---

## 💡 Card Recommendations UI

**To see the recommendations widget:**

### Query Options:
```
"What cards should I get?"
"Recommend cards for me"
"Show me card recommendations"
"What new cards would be good for me?"
"Suggest cards based on my profile"
```

**What happens:**
- ChatGPT calls `show_recommendations_ui(user_id=1)`
- Widget `recommendations_widget.html` renders inline
- You'll see:
  - Personalized card recommendations
  - Key benefits
  - Annual fees
  - "Learn More" buttons

**Example conversation:**
```
You: "What cards should I get?"

ChatGPT: [Calls show_recommendations_ui]
         [Widget renders]
         "Found 5 card recommendation(s) for you."
```

---

## 🔄 Complete Test Flow

### Step 1: Add Cards (First Time)
```
You: "I want to add my cards"
→ Card management UI appears
→ Fill form: "HDFC Infinia", "HDFC", "points"
→ Click "Add Card"
→ Card appears in list
```

### Step 2: View Deals
```
You: "Show me deals"
→ Deals widget appears
→ See active deals for your cards
```

### Step 3: Get Recommendations
```
You: "What cards should I get?"
→ Recommendations widget appears
→ See personalized card suggestions
```

### Step 4: Ask Strategy Question
```
You: "Which card should I use for ₹10,000 travel?"
→ ChatGPT calls recommend_best_card()
→ Returns formatted recommendation (no UI widget)
```

---

## 💬 Natural Language Variations

ChatGPT understands variations, so you can also say:

**For Card Manager:**
- "I need to set up my cards"
- "Can I add a credit card?"
- "Let's add my cards"
- "Card setup"

**For Deals:**
- "Any deals available?"
- "What promotions are there?"
- "Show me offers"
- "Deals and discounts"

**For Recommendations:**
- "What credit cards do you recommend?"
- "Suggest some cards"
- "Which cards should I apply for?"
- "Card suggestions"

---

## ⚠️ Important Notes

1. **First Time Setup:**
   - If you haven't added cards yet, ChatGPT might guide you to add cards first
   - The card manager UI is the primary onboarding tool

2. **Widget Rendering:**
   - Widgets render inline in ChatGPT's chat interface
   - They appear as interactive cards/forms
   - You can interact directly with the UI

3. **If Widget Doesn't Render:**
   - Check that MCP server is running
   - Verify MCP connection in ChatGPT settings
   - Check browser console for errors (if accessible)

4. **Data Requirements:**
   - For deals: Run `python3 seed_data.py` first to populate sample deals
   - For recommendations: Run `python3 seed_data.py` to populate available cards
   - For card manager: Works immediately (empty state if no cards)

---

## 🧪 Quick Test Sequence

Copy and paste these in order:

```
1. "I want to add my cards"
   → Should see card management UI

2. "Show me deals"
   → Should see deals widget (if data seeded)

3. "What cards should I get?"
   → Should see recommendations widget (if data seeded)

4. "Which card for ₹5000 dining?"
   → Should see text recommendation (no widget)
```

---

## 🎯 Expected Results

### ✅ Success Indicators:

**Card Manager:**
- Form with 3 fields (Card Name, Bank, Reward Type)
- "Add Card" button
- Card list (empty initially)

**Deals Widget:**
- Header: "🎁 Active Deals & Offers"
- Deal cards with discount badges
- Merchant and category info

**Recommendations Widget:**
- Header: "💡 Recommended Cards"
- Card cards with benefits
- Annual fee information
- "Learn More" buttons

### ❌ If You See Errors:

- "Tool not found" → MCP server not connected
- "Error loading widget" → Widget file missing or server issue
- Empty widget → No data (run seed_data.py)
- Text only (no UI) → Widget not rendering (check MCP configuration)

---

## 🔧 Troubleshooting

**Widget not showing?**
1. Check MCP server is running: `python3 main.py`
2. Verify MCP connection in ChatGPT
3. Check system prompt is loaded
4. Try explicit tool call: "Call manage_cards_ui tool"

**No data in widgets?**
1. Run: `python3 seed_data.py`
2. Add cards manually via card manager
3. Add deals via `add_deal` tool (admin)

**Widget shows but doesn't work?**
1. Check browser console (if accessible)
2. Verify `window.openai` API is available
3. Check network tab for tool calls

---

## 📝 Example Full Conversation

```
You: "I want to add my cards"

ChatGPT: [Calls manage_cards_ui(user_id=1)]
         [Widget renders]
         "Card manager opened. You have 0 card(s)."

You: [Fills form: HDFC Infinia, HDFC, points]
     [Clicks "Add Card"]

ChatGPT: "Card 'HDFC Infinia' added successfully!"

You: "Show me deals"

ChatGPT: [Calls show_deals_ui(user_id=1)]
         [Widget renders]
         "Found 4 active deal(s) for you."

You: "What cards should I get?"

ChatGPT: [Calls show_recommendations_ui(user_id=1)]
         [Widget renders]
         "Found 5 card recommendation(s) for you."
```

---

**Ready to test!** Start with "I want to add my cards" to see the card management UI.
