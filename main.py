from fastmcp import FastMCP
import os
import aiosqlite
import tempfile

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

def validate_category(category: str) -> bool:
    """Validate if category is in canonical list."""
    return category.lower() in CANONICAL_CATEGORIES

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

# Start the server
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
