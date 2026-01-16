from fastmcp import FastMCP
import os
import aiosqlite
import tempfile
from pathlib import Path
import json
from datetime import datetime, timedelta

# Use temporary directory which should be writable
TEMP_DIR = tempfile.gettempdir()
DB_PATH = os.path.join(TEMP_DIR, "rewards_strategist.db")

print(f"Database path: {DB_PATH}")

mcp = FastMCP("RewardsStrategist")

def init_db():
    """Initialize database with users, cards, and reward_rules tables."""
    try:
        import sqlite3
        with sqlite3.connect(DB_PATH) as c:
            c.execute("PRAGMA journal_mode=WAL")
            
            # Users table
            c.execute("""
                CREATE TABLE IF NOT EXISTS users(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    preference TEXT CHECK(preference IN ('travel', 'cashback', 'balanced')) DEFAULT 'balanced'
                )
            """)
            
            # Cards table
            c.execute("""
                CREATE TABLE IF NOT EXISTS cards(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    bank TEXT NOT NULL,
                    reward_type TEXT CHECK(reward_type IN ('points', 'miles', 'cashback')) NOT NULL,
                    active INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Reward rules table
            c.execute("""
                CREATE TABLE IF NOT EXISTS reward_rules(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    earn_rate REAL NOT NULL,
                    cap REAL,
                    notes TEXT DEFAULT '',
                    FOREIGN KEY (card_id) REFERENCES cards(id)
                )
            """)
            
            # Available cards table (for recommendations)
            c.execute("""
                CREATE TABLE IF NOT EXISTS available_cards(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    bank TEXT NOT NULL,
                    reward_type TEXT CHECK(reward_type IN ('points', 'miles', 'cashback')) NOT NULL,
                    annual_fee REAL DEFAULT 0,
                    key_benefits TEXT,
                    target_audience TEXT,
                    min_income REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Deals table
            c.execute("""
                CREATE TABLE IF NOT EXISTS deals(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    card_id INTEGER,
                    card_name TEXT,
                    category TEXT,
                    discount_percent REAL,
                    discount_amount REAL,
                    valid_from TEXT,
                    valid_until TEXT,
                    merchant TEXT,
                    terms TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (card_id) REFERENCES cards(id)
                )
            """)
            
            # Points/rewards tracking table
            c.execute("""
                CREATE TABLE IF NOT EXISTS rewards_balance(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id INTEGER NOT NULL UNIQUE,
                    balance REAL NOT NULL DEFAULT 0,
                    expiry_date TEXT,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (card_id) REFERENCES cards(id)
                )
            """)
            
            # Merchant category mapping table
            c.execute("""
                CREATE TABLE IF NOT EXISTS merchant_categories(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    merchant_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(merchant_name, category)
                )
            """)
            
            # Test write access
            c.execute("INSERT OR IGNORE INTO users(id, preference) VALUES (1, 'balanced')")
            c.execute("DELETE FROM users WHERE id = 1")
            print("Database initialized successfully with write access")
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise

# Initialize database synchronously at module load
init_db()

# Reward value normalization map (conversion rates)
REWARD_VALUE_MAP = {
    "points": 0.25,
    "miles": 1.0,
    "cashback": 1.0
}

# Canonical category list
CANONICAL_CATEGORIES = ["travel", "dining", "shopping", "online", "fuel", "general", "other"]

# Merchant to category mappings (common merchants)
MERCHANT_CATEGORY_MAP = {
    "swiggy": "dining",
    "zomato": "dining",
    "uber": "travel",
    "ola": "travel",
    "amazon": "shopping",
    "flipkart": "shopping",
    "myntra": "shopping",
    "make my trip": "travel",
    "goibibo": "travel",
    "bookmyshow": "entertainment",
    "netflix": "entertainment",
    "spotify": "entertainment",
    "irctc": "travel",
    "indigo": "travel",
    "spicejet": "travel",
    "air india": "travel",
    "oyo": "travel",
    "taj": "travel",
    "marriott": "travel",
    "starbucks": "dining",
    "dominos": "dining",
    "pizza hut": "dining",
    "mcdonalds": "dining",
    "big bazaar": "shopping",
    "dmart": "shopping",
    "reliance": "shopping",
    "hp": "fuel",
    "bharat petroleum": "fuel",
    "indian oil": "fuel",
}

def validate_category(category: str) -> bool:
    """Validate if category is in canonical list."""
    return category.lower() in CANONICAL_CATEGORIES

def lookup_merchant_category(merchant_name: str) -> str:
    """Look up category for a merchant name."""
    merchant_lower = merchant_name.lower().strip()
    
    # Check exact match
    if merchant_lower in MERCHANT_CATEGORY_MAP:
        return MERCHANT_CATEGORY_MAP[merchant_lower]
    
    # Check partial match
    for merchant, category in MERCHANT_CATEGORY_MAP.items():
        if merchant in merchant_lower or merchant_lower in merchant:
            return category
    
    # Default to "other" if no match
    return "other"

# ============================================================================
# RESPONSE FORMAT CONTRACT
# ============================================================================
# Every recommendation response from ChatGPT MUST follow this format:
#
# ✅ Best card: <card_name>
# 💰 Estimated value: ₹<value>
#
# Why:
# • <reason 1>
# • <reason 2>
#
# Watch out:
# • <cap / limit / trade-off>
#
# Required elements:
# - Best card name (from recommend_best_card tool results)
# - Estimated value in ₹ (use estimated_value from tool results)
# - Clear explanation ("why") - explain earn rate, category match, etc.
# - Warnings ("watch out") - caps, limits, when to switch cards
#
# This format is enforced by the system prompt. MCP tools return facts only;
# ChatGPT formats the recommendation using this structure.
# ============================================================================

# ============================================================================
# CATEGORY CLARIFICATION RULES
# ============================================================================
# If a user provides a non-canonical category (e.g., "Uber", "Amazon", "Swiggy"),
# ChatGPT should ask a clarification question:
#
# "Should I treat this as travel, shopping, or something else?"
#
# DO NOT silently guess or map categories in the backend.
# The backend will return "unsupported" status if category doesn't match.
# ChatGPT must ask for clarification before retrying with a canonical category.
#
# Canonical categories: travel, dining, shopping, online, fuel, general, other
# ============================================================================

@mcp.tool()
async def create_user(preference: str = "balanced"):
    """
    Create a new user.
    
    Args:
        preference: User preference - one of: travel, cashback, balanced (default: balanced)
    """
    try:
        # Validate preference
        if preference not in ['travel', 'cashback', 'balanced']:
            return {"status": "error", "message": "preference must be one of: travel, cashback, balanced"}
        
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                "INSERT INTO users(preference) VALUES (?)",
                (preference,)
            )
            user_id = cur.lastrowid
            await c.commit()
            return {
                "status": "success",
                "user_id": user_id,
                "message": f"User created successfully with preference: {preference}"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error creating user: {str(e)}"}

@mcp.tool()
async def add_card(user_id: int, name: str, bank: str, reward_type: str):
    """
    Add a new credit card for a user.
    
    Args:
        user_id: The user's ID
        name: Card name (e.g., "HDFC Infinia")
        bank: Bank name (e.g., "HDFC")
        reward_type: Type of reward - one of: points, miles, cashback
    """
    try:
        # Validate reward_type
        if reward_type not in ['points', 'miles', 'cashback']:
            return {"status": "error", "message": "reward_type must be one of: points, miles, cashback"}
        
        async with aiosqlite.connect(DB_PATH) as c:
            # Check for duplicate card (same name, bank, and user)
            cur = await c.execute(
                "SELECT id FROM cards WHERE user_id = ? AND name = ? AND bank = ?",
                (user_id, name, bank)
            )
            existing = await cur.fetchone()
            if existing:
                return {
                    "status": "error",
                    "message": f"Card '{name}' from {bank} already exists for this user"
                }
            
            cur = await c.execute(
                "INSERT INTO cards(user_id, name, bank, reward_type) VALUES (?, ?, ?, ?)",
                (user_id, name, bank, reward_type)
            )
            card_id = cur.lastrowid
            await c.commit()
            return {
                "status": "success",
                "id": card_id,
                "message": f"Card '{name}' added successfully"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error adding card: {str(e)}"}

@mcp.tool()
async def list_cards(user_id: int):
    """
    List all cards for a user.
    
    Args:
        user_id: The user's ID
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """
                SELECT id, name, bank, reward_type, active
                FROM cards
                WHERE user_id = ?
                ORDER BY active DESC, name ASC
                """,
                (user_id,)
            )
            cols = [d[0] for d in cur.description]
            rows = await cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]
    except Exception as e:
        return {"status": "error", "message": f"Error listing cards: {str(e)}"}

@mcp.tool()
async def add_reward_rule(card_id: int, category: str, earn_rate: float, cap: float = None, notes: str = ""):
    """
    Add a reward rule for a card.
    Used for seeding card intelligence (admin/setup).
    
    Args:
        card_id: The card's ID
        category: Spending category (must be in canonical list)
        earn_rate: Reward rate as percentage (e.g., 5.0 for 5%)
        cap: Optional maximum reward cap
        notes: Optional notes about the rule
    """
    try:
        # Validate category
        if not validate_category(category):
            return {
                "status": "error",
                "message": f"Category must be one of: {', '.join(CANONICAL_CATEGORIES)}"
            }
        
        async with aiosqlite.connect(DB_PATH) as c:
            # Verify card exists
            cur = await c.execute("SELECT id FROM cards WHERE id = ?", (card_id,))
            if not await cur.fetchone():
                return {"status": "error", "message": f"Card with id {card_id} not found"}
            
            cur = await c.execute(
                "INSERT INTO reward_rules(card_id, category, earn_rate, cap, notes) VALUES (?, ?, ?, ?, ?)",
                (card_id, category.lower(), earn_rate, cap, notes)
            )
            rule_id = cur.lastrowid
            await c.commit()
            return {
                "status": "success",
                "id": rule_id,
                "message": f"Reward rule added successfully for category '{category}'"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error adding reward rule: {str(e)}"}

@mcp.tool()
async def get_reward_rules(card_id: int):
    """
    Get all reward rules for a specific card.
    
    Args:
        card_id: The card's ID
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Get card info
            cur = await c.execute(
                "SELECT id, name, bank, reward_type FROM cards WHERE id = ?",
                (card_id,)
            )
            card_row = await cur.fetchone()
            if not card_row:
                return {"status": "error", "message": f"Card with id {card_id} not found"}
            
            card_info = {
                "id": card_row[0],
                "name": card_row[1],
                "bank": card_row[2],
                "reward_type": card_row[3]
            }
            
            # Get reward rules
            cur = await c.execute(
                """
                SELECT id, category, earn_rate, cap, notes
                FROM reward_rules
                WHERE card_id = ?
                ORDER BY earn_rate DESC
                """,
                (card_id,)
            )
            cols = [d[0] for d in cur.description]
            rules = [dict(zip(cols, r)) for r in await cur.fetchall()]
            
            return {
                "card": card_info,
                "rules": rules
            }
    except Exception as e:
        return {"status": "error", "message": f"Error getting reward rules: {str(e)}"}

@mcp.tool()
async def estimate_rewards(card_id: int, spend_amount: float, category: str):
    """
    Estimate rewards for a specific card, spend amount, and category.
    Returns facts only - no recommendations.
    
    Args:
        card_id: The card's ID
        spend_amount: Amount to spend
        category: Spending category (e.g., "travel", "dining", "shopping")
    """
    try:
        # Normalize category
        category = category.lower()
        
        async with aiosqlite.connect(DB_PATH) as c:
            # Get card info
            cur = await c.execute(
                "SELECT id, name, reward_type FROM cards WHERE id = ? AND active = 1",
                (card_id,)
            )
            card_row = await cur.fetchone()
            if not card_row:
                return {"status": "error", "message": f"Active card with id {card_id} not found"}
            
            card_name = card_row[1]
            reward_type = card_row[2]
            
            # Improved fallback logic: exact -> general -> other
            rule_row = None
            fallback_used = None
            
            # Try exact category match
            cur = await c.execute(
                """
                SELECT category, earn_rate, cap, notes
                FROM reward_rules
                WHERE card_id = ? AND category = ?
                """,
                (card_id, category)
            )
            rule_row = await cur.fetchone()
            if rule_row:
                fallback_used = None
            else:
                # Try general category
                cur = await c.execute(
                    """
                    SELECT category, earn_rate, cap, notes
                    FROM reward_rules
                    WHERE card_id = ? AND category = 'general'
                    LIMIT 1
                    """,
                    (card_id,)
                )
                rule_row = await cur.fetchone()
                if rule_row:
                    fallback_used = "general"
                else:
                    # Try other category
                    cur = await c.execute(
                        """
                        SELECT category, earn_rate, cap, notes
                        FROM reward_rules
                        WHERE card_id = ? AND category = 'other'
                        LIMIT 1
                        """,
                        (card_id,)
                    )
                    rule_row = await cur.fetchone()
                    if rule_row:
                        fallback_used = "other"
            
            if not rule_row:
                return {
                    "status": "unsupported",
                    "card_id": card_id,
                    "card_name": card_name,
                    "category": category,
                    "message": f"No reward rule found for category '{category}' on card '{card_name}' (checked: exact, general, other)"
                }
            
            rule_category, earn_rate, cap, notes = rule_row
            
            # Calculate rewards
            base_rewards = spend_amount * (earn_rate / 100)
            
            # Apply cap if exists
            if cap is not None and base_rewards > cap:
                rewards_earned = cap
                cap_applied = True
            else:
                rewards_earned = base_rewards
                cap_applied = False
            
            # Calculate estimated value using normalization map
            value_multiplier = REWARD_VALUE_MAP.get(reward_type, 1.0)
            estimated_value = round(rewards_earned * value_multiplier, 2)
            
            result = {
                "card_id": card_id,
                "card_name": card_name,
                "reward_type": reward_type,
                "spend_amount": spend_amount,
                "category": rule_category,
                "earn_rate": earn_rate,
                "rewards_earned": round(rewards_earned, 2),
                "estimated_value": estimated_value,
                "cap": cap,
                "cap_applied": cap_applied,
                "notes": notes or ""
            }
            
            if fallback_used:
                result["fallback_used"] = fallback_used
            
            return result
    except Exception as e:
        return {"status": "error", "message": f"Error estimating rewards: {str(e)}"}

@mcp.tool()
async def recommend_best_card(user_id: int, spend_amount: float, category: str):
    """
    Get reward estimates for all user's active cards for comparison.
    Returns facts only - ChatGPT will determine the best card.
    
    Args:
        user_id: The user's ID
        spend_amount: Amount to spend
        category: Spending category (e.g., "travel", "dining", "shopping")
    """
    try:
        # Normalize category
        category = category.lower()
        
        async with aiosqlite.connect(DB_PATH) as c:
            # Get user preference
            cur = await c.execute(
                "SELECT preference FROM users WHERE id = ?",
                (user_id,)
            )
            user_row = await cur.fetchone()
            user_preference = user_row[0] if user_row else 'balanced'
            
            # Get all active cards for user
            cur = await c.execute(
                "SELECT id, name, bank, reward_type FROM cards WHERE user_id = ? AND active = 1",
                (user_id,)
            )
            cards = await cur.fetchall()
            
            if not cards:
                return {"status": "error", "message": f"No active cards found for user {user_id}"}
            
            # Get estimates for each card
            estimates = []
            for card_id, card_name, bank, reward_type in cards:
                # Improved fallback logic: exact -> general -> other
                rule_row = None
                fallback_used = None
                
                # Try exact category match
                cur = await c.execute(
                    """
                    SELECT category, earn_rate, cap, notes
                    FROM reward_rules
                    WHERE card_id = ? AND category = ?
                    """,
                    (card_id, category)
                )
                rule_row = await cur.fetchone()
                if rule_row:
                    fallback_used = None
                else:
                    # Try general category
                    cur = await c.execute(
                        """
                        SELECT category, earn_rate, cap, notes
                        FROM reward_rules
                        WHERE card_id = ? AND category = 'general'
                        LIMIT 1
                        """,
                        (card_id,)
                    )
                    rule_row = await cur.fetchone()
                    if rule_row:
                        fallback_used = "general"
                    else:
                        # Try other category
                        cur = await c.execute(
                            """
                            SELECT category, earn_rate, cap, notes
                            FROM reward_rules
                            WHERE card_id = ? AND category = 'other'
                            LIMIT 1
                            """,
                            (card_id,)
                        )
                        rule_row = await cur.fetchone()
                        if rule_row:
                            fallback_used = "other"
                
                if rule_row:
                    rule_category, earn_rate, cap, notes = rule_row
                    base_rewards = spend_amount * (earn_rate / 100)
                    
                    if cap is not None and base_rewards > cap:
                        rewards_earned = cap
                        cap_applied = True
                    else:
                        rewards_earned = base_rewards
                        cap_applied = False
                    
                    # Calculate estimated value using normalization map
                    value_multiplier = REWARD_VALUE_MAP.get(reward_type, 1.0)
                    estimated_value = round(rewards_earned * value_multiplier, 2)
                    
                    estimate = {
                        "card_id": card_id,
                        "card_name": card_name,
                        "bank": bank,
                        "reward_type": reward_type,
                        "category": rule_category,
                        "earn_rate": earn_rate,
                        "rewards_earned": round(rewards_earned, 2),
                        "estimated_value": estimated_value,
                        "cap": cap,
                        "cap_applied": cap_applied,
                        "notes": notes or ""
                    }
                    
                    if fallback_used:
                        estimate["fallback_used"] = fallback_used
                    
                    estimates.append(estimate)
                else:
                    estimates.append({
                        "card_id": card_id,
                        "card_name": card_name,
                        "bank": bank,
                        "reward_type": reward_type,
                        "status": "unsupported",
                        "message": f"No reward rule found for category '{category}' (checked: exact, general, other)"
                    })
            
            # Sort by estimated_value descending (fallback to rewards_earned)
            estimates.sort(key=lambda x: x.get('estimated_value', x.get('rewards_earned', 0)), reverse=True)
            
            # Use AI for tie-breaking and nuanced recommendations when cards are close
            client = get_openai_client()
            if client and len(estimates) > 1:
                try:
                    # Check if top cards are very close (within 5% of each other)
                    top_value = estimates[0].get('estimated_value', 0)
                    if top_value > 0:
                        close_cards = [e for e in estimates if abs(e.get('estimated_value', 0) - top_value) / top_value <= 0.05]
                        
                        if len(close_cards) > 1:
                            # Use AI to break ties considering user preference and card features
                            prompt = f"""You are a credit card rewards strategist. Break a tie between cards with very similar reward values.

User Preference: {user_preference}
Spend Amount: ₹{spend_amount}
Category: {category}

Cards (already sorted by estimated value):
{json.dumps(close_cards, indent=2)}

Task: Re-rank these cards considering:
1. User's stated preference ({user_preference})
2. Long-term value (annual fees, other benefits)
3. Reward type diversity (points vs cashback vs miles)
4. Cap status (cards with caps applied may be less flexible)
5. Overall card benefits beyond just this transaction

Return ONLY a JSON array of card_id values in your recommended order, e.g., [2, 1, 3]
Do not include any explanation, only the JSON array."""

                            response = client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[
                                    {"role": "system", "content": "You are a credit card rewards strategist. Always return only valid JSON arrays of card IDs."},
                                    {"role": "user", "content": prompt}
                                ],
                                max_tokens=150,
                                temperature=0.2
                            )
                            
                            ai_response = response.choices[0].message.content.strip()
                            if ai_response.startswith("```"):
                                ai_response = ai_response.split("```")[1]
                                if ai_response.startswith("json"):
                                    ai_response = ai_response[4:]
                            ai_response = ai_response.strip()
                            
                            ai_ranked_ids = json.loads(ai_response)
                            
                            # Reorder close cards based on AI ranking
                            card_map = {e['card_id']: e for e in close_cards}
                            ai_ranked = [card_map[id] for id in ai_ranked_ids if id in card_map]
                            other_cards = [e for e in estimates if e['card_id'] not in [c['card_id'] for c in close_cards]]
                            
                            estimates = ai_ranked + other_cards
                            
                            # Add AI reasoning note
                            for estimate in estimates:
                                if estimate.get('card_id') in ai_ranked_ids[:3]:
                                    estimate['ai_recommended'] = True
                except Exception as e:
                    # Silently fallback to value-based sorting if AI fails
                    print(f"AI tie-breaking failed, using value-based sort: {e}")
            
            return {
                "user_preference": user_preference,
                "spend_amount": spend_amount,
                "category": category,
                "estimates": estimates
            }
    except Exception as e:
        return {"status": "error", "message": f"Error getting recommendations: {str(e)}"}

@mcp.tool()
async def deactivate_card(card_id: int):
    """
    Deactivate a credit card.
    
    Args:
        card_id: The card's ID
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Verify card exists
            cur = await c.execute("SELECT id, name FROM cards WHERE id = ?", (card_id,))
            card_row = await cur.fetchone()
            if not card_row:
                return {"status": "error", "message": f"Card with id {card_id} not found"}
            
            card_name = card_row[1]
            
            cur = await c.execute(
                "UPDATE cards SET active = 0 WHERE id = ?",
                (card_id,)
            )
            await c.commit()
            return {
                "status": "success",
                "message": f"Card '{card_name}' deactivated successfully"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error deactivating card: {str(e)}"}

@mcp.tool()
async def activate_card(card_id: int):
    """
    Activate a credit card.
    
    Args:
        card_id: The card's ID
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Verify card exists
            cur = await c.execute("SELECT id, name FROM cards WHERE id = ?", (card_id,))
            card_row = await cur.fetchone()
            if not card_row:
                return {"status": "error", "message": f"Card with id {card_id} not found"}
            
            card_name = card_row[1]
            
            cur = await c.execute(
                "UPDATE cards SET active = 1 WHERE id = ?",
                (card_id,)
            )
            await c.commit()
            return {
                "status": "success",
                "message": f"Card '{card_name}' activated successfully"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error activating card: {str(e)}"}

# ============================================================================
# UI WIDGET RESOURCE
# ============================================================================

@mcp.resource("ui://widget/cards.html", mime_type="text/html+skybridge")
def cards_widget():
    """
    HTML widget for card management UI.
    Renders inline inside ChatGPT chat interface.
    """
    widget_path = Path(__file__).parent / "cards_widget.html"
    try:
        with open(widget_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<html><body><p>Widget file not found</p></body></html>"
    except Exception as e:
        return f"<html><body><p>Error loading widget: {str(e)}</p></body></html>"

# ============================================================================
# UI MANAGEMENT TOOL
# ============================================================================

@mcp.tool()
async def manage_cards_ui(user_id: int = 1):
    """
    Open the card management UI widget.
    This tool renders an inline UI inside ChatGPT for adding and managing credit cards.
    
    Args:
        user_id: The user's ID (default: 1 for MVP)
    
    Returns:
        Structured content with current cards list and widget reference.
        
    Tool metadata (for OpenAI Apps SDK):
    - outputTemplate: ui://widget/cards.html
    - widgetAccessible: true
    - invoking: "Opening card manager..."
    - invoked: "Here are your cards."
    """
    try:
        # Fetch current cards for the widget
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """
                SELECT id, name, bank, reward_type, active
                FROM cards
                WHERE user_id = ?
                ORDER BY active DESC, name ASC
                """,
                (user_id,)
            )
            cols = [d[0] for d in cur.description]
            rows = await cur.fetchall()
            cards = [dict(zip(cols, r)) for r in rows]
        
        # Deduplicate cards by id (safety check)
        seen_ids = set()
        unique_cards = []
        for card in cards:
            if card['id'] not in seen_ids:
                seen_ids.add(card['id'])
                unique_cards.append(card)
        
        # Return structured content for widget
        # The widget will access this via window.openai.toolOutput
        # Note: For OpenAI Apps SDK, the return format should match their expected structure
        return {
            "structuredContent": {
                "cards": unique_cards,
                "user_id": user_id
            },
            "content": [
                {
                    "type": "text",
                    "text": f"Card manager opened. You have {len(unique_cards)} card(s)."
                }
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error loading card manager: {str(e)}",
            "structuredContent": {
                "cards": [],
                "user_id": user_id
            },
            "content": [
                {
                    "type": "text",
                    "text": "Error loading card manager. Please try again."
                }
            ]
        }

# ============================================================================
# DEALS & OFFERS MANAGEMENT
# ============================================================================

@mcp.tool()
async def get_deals(user_id: int = 1, category: str = None, card_id: int = None):
    """
    Get active deals and offers for user's cards.
    
    Args:
        user_id: The user's ID
        category: Optional category filter (travel, dining, shopping, etc.)
        card_id: Optional card ID filter
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            query = """
                SELECT d.id, d.title, d.description, d.card_id, d.card_name, 
                       d.category, d.discount_percent, d.discount_amount,
                       d.valid_from, d.valid_until, d.merchant, d.terms
                FROM deals d
                WHERE d.is_active = 1
                AND (d.valid_until IS NULL OR d.valid_until >= date('now'))
            """
            params = []
            
            if card_id:
                query += " AND d.card_id = ?"
                params.append(card_id)
            elif user_id:
                # Get deals for user's cards
                query += " AND (d.card_id IN (SELECT id FROM cards WHERE user_id = ?) OR d.card_id IS NULL)"
                params.append(user_id)
            
            if category:
                query += " AND d.category = ?"
                params.append(category)
            
            query += " ORDER BY d.created_at DESC LIMIT 20"
            
            cur = await c.execute(query, params)
            cols = [d[0] for d in cur.description]
            rows = await cur.fetchall()
            deals = [dict(zip(cols, r)) for r in rows]
            
            # Use AI to prioritize deals based on user's spending patterns
            client = get_openai_client()
            if client and len(deals) > 1:
                try:
                    # Get user's spending patterns from reward rules
                    cur = await c.execute(
                        """SELECT r.category, r.earn_rate, COUNT(*) as usage_count
                           FROM reward_rules r
                           JOIN cards c ON r.card_id = c.id
                           WHERE c.user_id = ? AND c.active = 1
                           GROUP BY r.category
                           ORDER BY usage_count DESC, r.earn_rate DESC"""
                    )
                    spending_patterns = await cur.fetchall()
                    
                    # Get user preference
                    cur = await c.execute("SELECT preference FROM users WHERE id = ?", (user_id,))
                    user_row = await cur.fetchone()
                    user_pref = user_row[0] if user_row else 'balanced'
                    
                    if spending_patterns:
                        prompt = f"""You are a deals prioritization expert. Rank deals based on user's spending patterns and preferences.

User Profile:
- Preference: {user_pref}
- Spending Patterns: {json.dumps([{"category": row[0], "earn_rate": row[1], "usage": row[2]} for row in spending_patterns], indent=2)}

Available Deals:
{json.dumps(deals, indent=2, default=str)}

Task: Rank these deals by relevance to the user. Consider:
1. Match with user's frequent spending categories
2. Discount value (percentage and amount)
3. User's card ownership (prioritize deals for cards user has)
4. Validity period (sooner expiring deals get priority if similar value)
5. User's stated preference ({user_pref})

Return ONLY a JSON array of deal IDs in order of priority, e.g., [3, 1, 5, 2, 4]
Do not include any explanation, only the JSON array."""

                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {"role": "system", "content": "You are a deals prioritization expert. Always return only valid JSON arrays of deal IDs."},
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=200,
                            temperature=0.3
                        )
                        
                        ai_response = response.choices[0].message.content.strip()
                        if ai_response.startswith("```"):
                            ai_response = ai_response.split("```")[1]
                            if ai_response.startswith("json"):
                                ai_response = ai_response[4:]
                        ai_response = ai_response.strip()
                        
                        ai_ranked_ids = json.loads(ai_response)
                        
                        # Reorder deals based on AI ranking
                        deal_map = {d['id']: d for d in deals}
                        ai_ranked = [deal_map[id] for id in ai_ranked_ids if id in deal_map]
                        other_deals = [d for d in deals if d['id'] not in ai_ranked_ids]
                        
                        deals = ai_ranked + other_deals
                except Exception as e:
                    # Silently fallback to date-based sorting if AI fails
                    print(f"AI deal prioritization failed, using date-based sort: {e}")
            
            return deals
    except Exception as e:
        return {"status": "error", "message": f"Error getting deals: {str(e)}"}

@mcp.tool()
async def add_deal(title: str, description: str = "", card_name: str = None, 
                   category: str = None, discount_percent: float = None,
                   discount_amount: float = None, valid_until: str = None,
                   merchant: str = None, terms: str = ""):
    """
    Add a new deal/offer (admin function for seeding data).
    
    Args:
        title: Deal title
        description: Deal description
        card_name: Card name (optional)
        category: Category (travel, dining, shopping, etc.)
        discount_percent: Discount percentage
        discount_amount: Discount amount
        valid_until: Valid until date (YYYY-MM-DD)
        merchant: Merchant name
        terms: Terms and conditions
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """INSERT INTO deals(title, description, card_name, category, 
                    discount_percent, discount_amount, valid_until, merchant, terms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, description, card_name, category, discount_percent,
                 discount_amount, valid_until, merchant, terms)
            )
            deal_id = cur.lastrowid
            await c.commit()
            return {
                "status": "success",
                "id": deal_id,
                "message": f"Deal '{title}' added successfully"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error adding deal: {str(e)}"}

# ============================================================================
# CARD RECOMMENDATIONS
# ============================================================================

@mcp.tool()
async def recommend_new_cards(user_id: int = 1, preference: str = None):
    """
    Recommend new credit cards that user doesn't have based on their profile.
    Uses AI to intelligently match cards to user's existing portfolio and preferences.
    
    Args:
        user_id: The user's ID
        preference: Optional preference override (travel, cashback, balanced)
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Get user preference
            cur = await c.execute("SELECT preference FROM users WHERE id = ?", (user_id,))
            user_row = await cur.fetchone()
            user_pref = preference or (user_row[0] if user_row else 'balanced')
            
            # Get user's existing cards with details
            cur = await c.execute(
                """SELECT c.name, c.bank, c.reward_type, r.category, r.earn_rate
                   FROM cards c
                   LEFT JOIN reward_rules r ON c.id = r.card_id
                   WHERE c.user_id = ? AND c.active = 1"""
            )
            existing_cards_data = await cur.fetchall()
            existing_cards = {(row[0], row[1]) for row in existing_cards_data}
            
            # Get available cards user doesn't have
            cur = await c.execute(
                """SELECT id, name, bank, reward_type, annual_fee, key_benefits, target_audience, min_income
                   FROM available_cards
                   ORDER BY annual_fee ASC, name ASC"""
            )
            cols = [d[0] for d in cur.description]
            all_cards = [dict(zip(cols, r)) for r in await cur.fetchall()]
            
            # Filter out cards user already has
            candidate_cards = []
            for card in all_cards:
                if (card['name'], card['bank']) not in existing_cards:
                    candidate_cards.append(card)
            
            if not candidate_cards:
                return []
            
            # Use AI to intelligently rank and recommend cards
            client = get_openai_client()
            if client:
                try:
                    # Build context about user's existing cards
                    existing_context = []
                    for row in existing_cards_data:
                        existing_context.append({
                            "name": row[0],
                            "bank": row[1],
                            "reward_type": row[2],
                            "category": row[3],
                            "earn_rate": row[4]
                        })
                    
                    prompt = f"""You are a credit card recommendation expert. Analyze the user's existing cards and recommend the best new cards from the candidate list.

User Profile:
- Preference: {user_pref}
- Existing Cards: {json.dumps(existing_context, indent=2)}

Candidate Cards:
{json.dumps(candidate_cards, indent=2)}

Task: Rank and select the top 5 cards that would best complement the user's existing portfolio. Consider:
1. Gaps in reward categories (e.g., if user has no travel card, recommend one)
2. Reward type diversity (points, miles, cashback)
3. Annual fee value proposition
4. User's stated preference ({user_pref})
5. Benefits that user doesn't currently have

Return ONLY a JSON array of card IDs (as integers) in order of recommendation, e.g., [3, 1, 5, 2, 4]
Do not include any explanation, only the JSON array."""

                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a credit card recommendation expert. Always return only valid JSON arrays."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=200,
                        temperature=0.3
                    )
                    
                    # Parse AI response
                    ai_response = response.choices[0].message.content.strip()
                    # Remove markdown code blocks if present
                    if ai_response.startswith("```"):
                        ai_response = ai_response.split("```")[1]
                        if ai_response.startswith("json"):
                            ai_response = ai_response[4:]
                    ai_response = ai_response.strip()
                    
                    recommended_ids = json.loads(ai_response)
                    
                    # Map IDs back to cards and maintain order
                    card_map = {card['id']: card for card in candidate_cards}
                    recommendations = [card_map[id] for id in recommended_ids if id in card_map]
                    
                    # Fill remaining slots if AI didn't recommend 5
                    remaining = [c for c in candidate_cards if c['id'] not in recommended_ids]
                    recommendations.extend(remaining[:5 - len(recommendations)])
                    
                    return recommendations[:5]
                except Exception as e:
                    # Fallback to rule-based if AI fails
                    print(f"AI recommendation failed, using fallback: {e}")
            
            # Fallback: Rule-based matching
            recommendations = []
            for card in candidate_cards:
                if user_pref == 'travel' and 'travel' in (card.get('target_audience') or '').lower():
                    recommendations.append(card)
                elif user_pref == 'cashback' and card['reward_type'] == 'cashback':
                    recommendations.append(card)
                elif user_pref == 'balanced':
                    recommendations.append(card)
            
            return recommendations[:5]
    except Exception as e:
        return {"status": "error", "message": f"Error getting recommendations: {str(e)}"}

@mcp.tool()
async def add_available_card(name: str, bank: str, reward_type: str,
                            annual_fee: float = 0, key_benefits: str = "",
                            target_audience: str = "", min_income: float = None):
    """
    Add an available card to the database (admin function for seeding data).
    
    Args:
        name: Card name
        bank: Bank name
        reward_type: points, miles, or cashback
        annual_fee: Annual fee
        key_benefits: Key benefits description
        target_audience: Target audience (travel, cashback, etc.)
        min_income: Minimum income requirement
    """
    try:
        if reward_type not in ['points', 'miles', 'cashback']:
            return {"status": "error", "message": "reward_type must be one of: points, miles, cashback"}
        
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """INSERT INTO available_cards(name, bank, reward_type, annual_fee, 
                    key_benefits, target_audience, min_income)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (name, bank, reward_type, annual_fee, key_benefits, target_audience, min_income)
            )
            card_id = cur.lastrowid
            await c.commit()
            return {
                "status": "success",
                "id": card_id,
                "message": f"Available card '{name}' added successfully"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error adding available card: {str(e)}"}

# ============================================================================
# OPENAI API INTEGRATION
# ============================================================================

def get_openai_client():
    """Get OpenAI client (API key from environment variable)."""
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)
    except ImportError:
        return None
    except Exception:
        return None

@mcp.tool()
async def enhanced_chat_response(user_query: str, context: str = ""):
    """
    Get enhanced chat response using OpenAI API for complex queries.
    Uses the user's card data as context.
    
    Args:
        user_query: User's question
        context: Optional context about user's cards
    """
    try:
        client = get_openai_client()
        if not client:
            return {
                "status": "error",
                "message": "OpenAI API not configured. Set OPENAI_API_KEY environment variable."
            }
        
        # Build context from user's cards if not provided
        if not context:
            async with aiosqlite.connect(DB_PATH) as c:
                cur = await c.execute(
                    """SELECT c.name, c.bank, c.reward_type, r.category, r.earn_rate
                       FROM cards c
                       LEFT JOIN reward_rules r ON c.id = r.card_id
                       WHERE c.user_id = 1 AND c.active = 1"""
                )
                cards_data = await cur.fetchall()
                if cards_data:
                    context = "User's cards: " + json.dumps([{
                        "name": row[0], "bank": row[1], "reward_type": row[2],
                        "category": row[3], "earn_rate": row[4]
                    } for row in cards_data], indent=2)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are an expert credit card rewards strategist. Your role is to help users optimize their credit card usage and maximize rewards.

Guidelines:
- Always base answers on the provided card data context
- Be specific about reward rates, caps, and limitations
- Explain trade-offs clearly
- If information is missing, say so rather than guessing
- Use Indian Rupees (₹) for all monetary values
- Be concise but thorough
- Prioritize actionable advice"""},
                {"role": "user", "content": f"""Context about user's credit cards and reward rules:
{context}

User Question: {user_query}

Provide a clear, helpful answer based on the context above. If the context doesn't contain enough information to answer fully, acknowledge what you can answer and what's missing."""}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return {
            "status": "success",
            "response": response.choices[0].message.content
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error getting enhanced response: {str(e)}"
        }

# ============================================================================
# DEALS UI WIDGET
# ============================================================================

@mcp.resource("ui://widget/deals.html", mime_type="text/html+skybridge")
def deals_widget():
    """HTML widget for displaying deals and offers."""
    widget_path = Path(__file__).parent / "deals_widget.html"
    try:
        with open(widget_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<html><body><p>Deals widget file not found</p></body></html>"
    except Exception as e:
        return f"<html><body><p>Error loading deals widget: {str(e)}</p></body></html>"

@mcp.tool()
async def show_deals_ui(user_id: int = 1, category: str = None):
    """
    Show deals and offers UI widget.
    
    Args:
        user_id: The user's ID
        category: Optional category filter
    """
    try:
        deals = await get_deals(user_id, category)
        if isinstance(deals, dict) and deals.get("status") == "error":
            deals = []
        
        return {
            "structuredContent": {
                "deals": deals if isinstance(deals, list) else [],
                "user_id": user_id,
                "category": category
            },
            "content": [
                {
                    "type": "text",
                    "text": f"Found {len(deals) if isinstance(deals, list) else 0} active deal(s) for you."
                }
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error loading deals: {str(e)}",
            "structuredContent": {"deals": [], "user_id": user_id}
        }

# ============================================================================
# RECOMMENDATIONS UI WIDGET
# ============================================================================

@mcp.resource("ui://widget/recommendations.html", mime_type="text/html+skybridge")
def recommendations_widget():
    """HTML widget for displaying card recommendations."""
    widget_path = Path(__file__).parent / "recommendations_widget.html"
    try:
        with open(widget_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<html><body><p>Recommendations widget file not found</p></body></html>"
    except Exception as e:
        return f"<html><body><p>Error loading recommendations widget: {str(e)}</p></body></html>"

@mcp.tool()
async def show_recommendations_ui(user_id: int = 1):
    """
    Show personalized card recommendations UI widget.
    
    Args:
        user_id: The user's ID
    """
    try:
        recommendations = await recommend_new_cards(user_id)
        if isinstance(recommendations, dict) and recommendations.get("status") == "error":
            recommendations = []
        
        return {
            "structuredContent": {
                "recommendations": recommendations if isinstance(recommendations, list) else [],
                "user_id": user_id
            },
            "content": [
                {
                    "type": "text",
                    "text": f"Found {len(recommendations) if isinstance(recommendations, list) else 0} card recommendation(s) for you."
                }
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error loading recommendations: {str(e)}",
            "structuredContent": {"recommendations": [], "user_id": user_id}
        }

# ============================================================================
# POINTS/REWARDS TRACKING
# ============================================================================

@mcp.tool()
async def get_rewards_balance(user_id: int = 1):
    """
    Get rewards balance summary for all user's cards.
    
    Args:
        user_id: The user's ID
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """SELECT c.id, c.name, c.bank, c.reward_type, 
                          COALESCE(rb.balance, 0) as balance,
                          rb.expiry_date, rb.last_updated, rb.notes
                   FROM cards c
                   LEFT JOIN rewards_balance rb ON c.id = rb.card_id
                   WHERE c.user_id = ? AND c.active = 1
                   ORDER BY c.name ASC""",
                (user_id,)
            )
            cols = [d[0] for d in cur.description]
            rows = await cur.fetchall()
            balances = [dict(zip(cols, r)) for r in rows]
            
            # Calculate totals by reward type
            totals = {"points": 0, "miles": 0, "cashback": 0}
            for balance in balances:
                reward_type = balance.get("reward_type", "")
                if reward_type in totals:
                    totals[reward_type] += balance.get("balance", 0)
            
            return {
                "balances": balances,
                "totals": totals,
                "summary": f"You have {totals['points']:,.0f} points, {totals['miles']:,.0f} miles, and ₹{totals['cashback']:,.2f} cashback"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error getting rewards balance: {str(e)}"}

@mcp.tool()
async def update_rewards_balance(card_id: int, balance: float, expiry_date: str = None, notes: str = ""):
    """
    Update or set rewards balance for a card.
    
    Args:
        card_id: The card's ID
        balance: Current balance (points, miles, or cashback amount)
        expiry_date: Optional expiry date (YYYY-MM-DD)
        notes: Optional notes
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Verify card exists
            cur = await c.execute("SELECT id, name FROM cards WHERE id = ?", (card_id,))
            card_row = await cur.fetchone()
            if not card_row:
                return {"status": "error", "message": f"Card with id {card_id} not found"}
            
            # Insert or update balance
            cur = await c.execute(
                """INSERT INTO rewards_balance(card_id, balance, expiry_date, notes, last_updated)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(card_id) DO UPDATE SET
                       balance = excluded.balance,
                       expiry_date = excluded.expiry_date,
                       notes = excluded.notes,
                       last_updated = CURRENT_TIMESTAMP""",
                (card_id, balance, expiry_date, notes)
            )
            await c.commit()
            return {
                "status": "success",
                "message": f"Balance updated for card {card_row[1]}"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error updating balance: {str(e)}"}

@mcp.tool()
async def add_rewards(card_id: int, amount: float, notes: str = ""):
    """
    Add rewards to a card's balance (increment existing balance).
    
    Args:
        card_id: The card's ID
        amount: Amount to add
        notes: Optional notes about the addition
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Get current balance
            cur = await c.execute(
                "SELECT balance FROM rewards_balance WHERE card_id = ?",
                (card_id,)
            )
            row = await cur.fetchone()
            current_balance = row[0] if row else 0.0
            
            new_balance = current_balance + amount
            
            # Update balance
            return await update_rewards_balance(card_id, new_balance, notes=notes)
    except Exception as e:
        return {"status": "error", "message": f"Error adding rewards: {str(e)}"}

# ============================================================================
# MERCHANT CATEGORY LOOKUP
# ============================================================================

@mcp.tool()
async def lookup_merchant(merchant_name: str):
    """
    Look up the spending category for a merchant name.
    Returns the most likely category based on merchant name.
    
    Args:
        merchant_name: Name of the merchant (e.g., "Swiggy", "Amazon", "Uber")
    
    Returns:
        Suggested category and confidence level
    """
    try:
        category = lookup_merchant_category(merchant_name)
        
        # Check database for custom mappings
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                "SELECT category, confidence FROM merchant_categories WHERE merchant_name = ?",
                (merchant_name.lower(),)
            )
            row = await cur.fetchone()
            if row:
                category = row[0]
                confidence = row[1]
            else:
                confidence = 0.8 if category != "other" else 0.5
        
        return {
            "merchant": merchant_name,
            "suggested_category": category,
            "confidence": confidence,
            "message": f"'{merchant_name}' is likely '{category}' category"
        }
    except Exception as e:
        return {"status": "error", "message": f"Error looking up merchant: {str(e)}"}

@mcp.tool()
async def add_merchant_mapping(merchant_name: str, category: str, confidence: float = 1.0):
    """
    Add a custom merchant to category mapping (admin function).
    
    Args:
        merchant_name: Name of the merchant
        category: Spending category (must be canonical)
        confidence: Confidence level (0.0 to 1.0)
    """
    try:
        if not validate_category(category):
            return {
                "status": "error",
                "message": f"Category must be one of: {', '.join(CANONICAL_CATEGORIES)}"
            }
        
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """INSERT OR REPLACE INTO merchant_categories(merchant_name, category, confidence)
                   VALUES (?, ?, ?)""",
                (merchant_name.lower(), category.lower(), confidence)
            )
            await c.commit()
            return {
                "status": "success",
                "message": f"Merchant mapping added: {merchant_name} -> {category}"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error adding merchant mapping: {str(e)}"}

# ============================================================================
# CARD COMPARISON WIDGET
# ============================================================================

@mcp.resource("ui://widget/comparison.html", mime_type="text/html+skybridge")
def comparison_widget():
    """HTML widget for comparing multiple cards side-by-side."""
    widget_path = Path(__file__).parent / "comparison_widget.html"
    try:
        with open(widget_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<html><body><p>Comparison widget file not found</p></body></html>"
    except Exception as e:
        return f"<html><body><p>Error loading comparison widget: {str(e)}</p></body></html>"

@mcp.resource("ui://widget/rewards.html", mime_type="text/html+skybridge")
def rewards_widget():
    """HTML widget for displaying rewards balance."""
    widget_path = Path(__file__).parent / "rewards_widget.html"
    try:
        with open(widget_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<html><body><p>Rewards widget file not found</p></body></html>"
    except Exception as e:
        return f"<html><body><p>Error loading rewards widget: {str(e)}</p></body></html>"

@mcp.tool()
async def show_rewards_balance_ui(user_id: int = 1):
    """
    Show rewards balance UI widget.
    
    Args:
        user_id: The user's ID
    """
    try:
        result = await get_rewards_balance(user_id)
        if isinstance(result, dict) and result.get("status") == "error":
            return result
        
        balances = result.get("balances", [])
        totals = result.get("totals", {})
        summary = result.get("summary", "")
        
        return {
            "structuredContent": {
                "balances": balances,
                "totals": totals,
                "summary": summary,
                "user_id": user_id
            },
            "content": [
                {
                    "type": "text",
                    "text": summary or f"You have {len(balances)} card(s) with tracked balances"
                }
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error loading rewards balance: {str(e)}",
            "structuredContent": {"balances": [], "totals": {}, "user_id": user_id}
        }

@mcp.tool()
async def show_card_comparison(user_id: int, spend_amount: float, category: str):
    """
    Show card comparison UI widget when multiple cards are close in value.
    
    Args:
        user_id: The user's ID
        spend_amount: Amount to spend
        category: Spending category
    """
    try:
        result = await recommend_best_card(user_id, spend_amount, category)
        if isinstance(result, dict) and result.get("status") == "error":
            return result
        
        estimates = result.get("estimates", [])
        
        # Filter to top 3 cards for comparison
        top_cards = estimates[:3] if len(estimates) >= 3 else estimates
        
        return {
            "structuredContent": {
                "comparison": top_cards,
                "spend_amount": spend_amount,
                "category": category,
                "user_id": user_id
            },
            "content": [
                {
                    "type": "text",
                    "text": f"Comparing top {len(top_cards)} cards for ₹{spend_amount:,.0f} {category} spend"
                }
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error showing comparison: {str(e)}",
            "structuredContent": {"comparison": [], "spend_amount": spend_amount, "category": category}
        }

# Start the server
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
