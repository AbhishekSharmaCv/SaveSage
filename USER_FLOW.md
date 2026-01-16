# Expected User Flow in ChatGPT

This document explains the expected flow when users interact with the RewardsStrategist MCP app inside ChatGPT.

## Flow 1: First-Time User Asking Strategy Question

**User:** "Which card should I use for ₹10,000 travel booking?"

**ChatGPT's Actions (Automatic Onboarding):**

1. **Check if user exists**
   - Calls `list_cards(user_id=1)` (default user_id for MVP)
   - If error or empty → Proceeds to step 2
   - If success → Proceeds to step 3

2. **Create user (if needed)**
   - Calls `create_user(preference="balanced")`
   - Gets `user_id` (e.g., 1)
   - **ChatGPT Response:** "I've set up your account. Now let's add your credit cards."

3. **Check if user has cards**
   - Calls `list_cards(user_id=1)`
   - If empty → **ChatGPT Response:** "I need to know about your cards first. Let's add your credit cards. You can say 'I want to add my cards' or tell me about them."
   - If cards exist → Proceeds to step 4

4. **Check if cards have reward rules**
   - Calls `get_reward_rules(card_id=X)` for first card
   - If no rules → **ChatGPT Response:** "Your cards are added, but I need reward rules configured. This setup is incomplete. Reward rules need to be added."
   - If rules exist → Proceeds to step 5

5. **Answer strategy question**
   - Calls `recommend_best_card(user_id=1, spend_amount=10000, category="travel")`
   - Gets comparison data with `estimated_value` for all cards
   - **ChatGPT Response (Formatted):**
     ```
     ✅ Best card: HDFC Infinia
     💰 Estimated value: ₹125
     
     Why:
     • 5% earn rate on travel (5x rewards)
     • Earns 500 points worth ₹125 (points valued at 0.25x)
     • Cap not breached this month
     
     Watch out:
     • Switch to another card after ₹50,000 travel spend this month (cap limit)
     ```

---

## Flow 2: User Wants to Add Cards (UI Flow)

**User:** "I want to add my cards" or "Show me the card manager"

**ChatGPT's Actions:**

1. **Call UI tool**
   - Calls `manage_cards_ui(user_id=1)`
   - Tool returns:
     ```json
     {
       "structuredContent": {
         "cards": [...],
         "user_id": 1
       },
       "content": [{"type": "text", "text": "Card manager opened. You have 2 card(s)."}]
     }
     ```

2. **ChatGPT renders widget**
   - ChatGPT loads `ui://widget/cards.html` resource
   - Widget renders inline in chat interface
   - Widget displays:
     - Add Card Form (name, bank, reward type)
     - Current Cards List (if any)

3. **User interacts with widget**
   - User fills form: "HDFC Infinia", "HDFC", "points"
   - Clicks "Add Card" button
   - Widget calls `window.openai.callTool('add_card', {...})`
   - MCP tool `add_card()` executes → saves to SQLite
   - Widget refreshes card list automatically

4. **ChatGPT sees result**
   - Tool returns success/error
   - Widget updates UI
   - **ChatGPT Response:** "Card added successfully! You can now ask me which card to use for your purchases."

---

## Flow 3: User Asks Strategy Question (After Setup)

**User:** "Which card should I use for ₹5,000 on Amazon?"

**ChatGPT's Actions:**

1. **Category clarification (if needed)**
   - "Amazon" is not a canonical category
   - **ChatGPT Response:** "Should I treat this as travel, shopping, or something else?"
   - User: "shopping"

2. **Get recommendation**
   - Calls `recommend_best_card(user_id=1, spend_amount=5000, category="shopping")`
   - Tool returns comparison data for all active cards

3. **Format response**
   - **ChatGPT Response:**
     ```
     ✅ Best card: HDFC Infinia
     💰 Estimated value: ₹12.50
     
     Why:
     • 1% general earn rate applies (no shopping-specific rule)
     • Earns 50 points worth ₹12.50
     
     Watch out:
     • Consider adding a shopping-specific card for better rewards on online purchases
     ```

---

## Flow 4: User Asks About Specific Card

**User:** "How much will I earn on HDFC Infinia for ₹20,000 travel?"

**ChatGPT's Actions:**

1. **Get card ID**
   - Calls `list_cards(user_id=1)` to find card ID
   - Finds card with name "HDFC Infinia" → `card_id=1`

2. **Estimate rewards**
   - Calls `estimate_rewards(card_id=1, spend_amount=20000, category="travel")`
   - Tool returns:
     ```json
     {
       "card_name": "HDFC Infinia",
       "rewards_earned": 1000,
       "estimated_value": 250,
       "earn_rate": 5.0,
       "cap_applied": false
     }
     ```

3. **Explain result**
   - **ChatGPT Response:** "For ₹20,000 travel spend on HDFC Infinia, you'll earn 1,000 points worth ₹250 (5% earn rate). The cap hasn't been reached, so you'll get the full reward."

---

## Flow 5: Multiple Cards Close in Value

**User:** "Which card for ₹15,000 dining?"

**ChatGPT's Actions:**

1. **Get comparison**
   - Calls `recommend_best_card(user_id=1, spend_amount=15000, category="dining")`
   - Tool returns estimates sorted by `estimated_value`

2. **Detect close values**
   - Card A: ₹225 (HDFC Infinia)
   - Card B: ₹220 (Axis Magnus)
   - Difference < 5%

3. **Explain trade-offs**
   - **ChatGPT Response:**
     ```
     Both cards are very close in value:
     
     ✅ HDFC Infinia: ₹225
     • 3% earn rate on dining
     • Points valued at 0.25x
     
     ✅ Axis Magnus: ₹220
     • 4% earn rate on dining
     • Points valued at 0.22x
     
     The difference is minimal (₹5). Choose based on:
     - Which card you prefer for other categories
     - Which bank's redemption options you like better
     ```

---

## Flow 6: User Has No Cards Yet

**User:** "Which card should I use?"

**ChatGPT's Actions:**

1. **Check cards**
   - Calls `list_cards(user_id=1)`
   - Returns empty array `[]`

2. **Guide to add cards**
   - **ChatGPT Response:** "I need to know about your cards first. Let's add your credit cards. You can say 'I want to add my cards' to open the card manager, or tell me about your cards directly."

3. **If user says "I want to add my cards"**
   - Proceeds to Flow 2 (UI Flow)

4. **If user says "I have HDFC Infinia"**
   - Calls `add_card(user_id=1, name="HDFC Infinia", bank="HDFC", reward_type="points")`
   - **ChatGPT Response:** "Great! I've added HDFC Infinia. To give you recommendations, I'll also need reward rules configured for this card. For now, you can ask me questions and I'll help once the setup is complete."

---

## Flow 7: User Wants to Manage Cards

**User:** "Show me my cards" or "List my cards"

**ChatGPT's Actions:**

1. **Option A: Text response**
   - Calls `list_cards(user_id=1)`
   - **ChatGPT Response:**
     ```
     You have 2 cards:
     1. HDFC Infinia (HDFC) - Points - Active
     2. Axis Magnus (Axis) - Points - Active
     ```

2. **Option B: UI widget**
   - Calls `manage_cards_ui(user_id=1)`
   - Widget renders with visual card list
   - User can activate/deactivate cards via buttons

---

## Key Points

### Onboarding Sequence (Automatic)
1. User exists? → `create_user()` if not
2. Cards exist? → Guide to add cards if not
3. Rules exist? → State setup incomplete if not
4. All ready? → Answer strategy questions

### Tool Call Pattern
- **Never invent data** - Always call MCP tools
- **Always call `recommend_best_card()`** before recommending
- **Always verify rules** with `get_reward_rules()` when needed

### Response Format (Mandatory)
Every recommendation MUST include:
- ✅ Best card name
- 💰 Estimated value in ₹
- Why (explanation)
- Watch out (warnings/limits)

### Category Handling
- Canonical: `travel`, `dining`, `shopping`, `online`, `fuel`, `general`, `other`
- Non-canonical (e.g., "Uber", "Amazon") → Ask clarification
- Never silently guess categories

### UI Widget Flow
- User requests card manager → `manage_cards_ui()` called
- Widget renders inline
- User actions → Widget calls MCP tools via `window.openai.callTool()`
- Results update widget automatically

---

## Example Complete Conversation

```
User: Which card should I use for ₹10,000 travel?

ChatGPT: [Calls list_cards(user_id=1)]
         I need to know about your cards first. Let's add your credit cards.
         You can say "I want to add my cards" to open the card manager.

User: I want to add my cards

ChatGPT: [Calls manage_cards_ui(user_id=1)]
         [Widget renders inline]
         Card manager opened. You have 0 card(s).

User: [Fills form: HDFC Infinia, HDFC, points, clicks Add Card]
      [Widget calls add_card() → Success]

ChatGPT: Card added successfully!

User: Which card should I use for ₹10,000 travel?

ChatGPT: [Calls get_reward_rules(card_id=1)]
         Your cards are added, but I need reward rules configured.
         This setup is incomplete.

[Admin adds reward rules via add_reward_rule()]

User: Which card should I use for ₹10,000 travel?

ChatGPT: [Calls recommend_best_card(user_id=1, spend_amount=10000, category="travel")]
         
         ✅ Best card: HDFC Infinia
         💰 Estimated value: ₹125
         
         Why:
         • 5% earn rate on travel
         • Earns 500 points worth ₹125
         
         Watch out:
         • Cap limit: ₹50,000 per month
```

---

This flow ensures users are properly onboarded, data is always accurate (from MCP tools), and the UI provides a smooth experience for card management.
