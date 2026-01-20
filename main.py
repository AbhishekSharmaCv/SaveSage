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

# Canonical category list (includes US categories: groceries, gas)
CANONICAL_CATEGORIES = ["travel", "dining", "shopping", "online", "fuel", "gas", "groceries", "general", "other"]

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

async def auto_seed_reward_rules(card_id: int, card_name: str):
    """
    Auto-seed reward rules from us_cards.json if card name matches.
    This removes admin burden by automatically creating reward rules.
    """
    try:
        us_cards_path = Path(__file__).parent / "data" / "us_cards.json"
        if not us_cards_path.exists():
            return 0  # No US cards data file, skip auto-seed
        
        with open(us_cards_path, "r", encoding="utf-8") as f:
            us_cards = json.load(f)
        
        # Find matching card by name (case-insensitive)
        matched_card = None
        for card in us_cards:
            if card["name"].lower() == card_name.lower():
                matched_card = card
                break
        
        if not matched_card:
            return 0  # Card not in US cards database, skip
        
        # Map categories: "gas" -> "fuel" for compatibility, "groceries" stays as is
        category_mapping = {
            "gas": "fuel",  # Map gas to fuel for compatibility
            "groceries": "groceries"  # Keep groceries as is (added to canonical list)
        }
        
        async with aiosqlite.connect(DB_PATH) as c:
            # Check if rules already exist for this card
            cur = await c.execute(
                "SELECT COUNT(*) FROM reward_rules WHERE card_id = ?",
                (card_id,)
            )
            existing_count = (await cur.fetchone())[0]
            if existing_count > 0:
                return 0  # Rules already exist, skip to allow manual override
            
            # Create reward rules from card data
            rules_created = 0
            notes_parts = []
            
            # Add signup bonus info to notes if available
            signup_bonus = matched_card.get("signup_bonus", {})
            if signup_bonus and signup_bonus.get("amount", 0) > 0:
                notes_parts.append(f"Signup bonus: {signup_bonus.get('amount')} {matched_card.get('reward_type', 'points')} after spending ${signup_bonus.get('spend', 0)} in {signup_bonus.get('days', 90)} days")
            
            # Add credits info from metadata if available
            metadata = matched_card.get("_metadata", {})
            if metadata:
                credits = metadata.get("credits", [])
                if credits:
                    credit_descriptions = [c.get("description", "") for c in credits[:3] if c.get("description")]
                    if credit_descriptions:
                        notes_parts.append(f"Credits: {', '.join(credit_descriptions)}")
            
            base_notes = ". ".join(notes_parts) if notes_parts else "Auto-seeded from us_cards.json"
            
            for category, earn_rate in matched_card.get("categories", {}).items():
                if earn_rate > 0:
                    # Map category if needed
                    db_category = category_mapping.get(category, category)
                    # Only add if category is in canonical list
                    if db_category in CANONICAL_CATEGORIES or category in CANONICAL_CATEGORIES:
                        final_category = db_category if db_category in CANONICAL_CATEGORIES else category
                        # Check if rule already exists
                        cur = await c.execute(
                            "SELECT id FROM reward_rules WHERE card_id = ? AND category = ?",
                            (card_id, final_category)
                        )
                        if not await cur.fetchone():
                            # Add category-specific note
                            category_note = f"{base_notes}. {earn_rate}x on {final_category}"
                            await c.execute(
                                "INSERT INTO reward_rules(card_id, category, earn_rate, notes) VALUES (?, ?, ?, ?)",
                                (card_id, final_category, earn_rate, category_note)
                            )
                            rules_created += 1
            
            await c.commit()
            if rules_created > 0:
                print(f"Auto-seeded {rules_created} reward rules for {card_name}")
                return rules_created
            return 0
    except Exception as e:
        print(f"Error auto-seeding reward rules for {card_name}: {e}")
        # Don't fail card addition if auto-seed fails
        return 0

# ============================================================================
# RESPONSE FORMAT CONTRACT
# ============================================================================
# Every recommendation response from ChatGPT MUST follow this format:
#
# ✅ Best card: <card_name>
# 💰 Estimated value: $<value>
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
# - Estimated value in $ (use estimated_value from tool results)
# - Clear explanation ("why") - explain earn rate, category match, etc.
# - Warnings ("watch out") - caps, limits, when to switch cards
# - If top 2 cards are within 10% value, explain trade-offs instead of forcing single choice
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
            
            # Auto-seed reward rules from us_cards.json if available
            await auto_seed_reward_rules(card_id, name)
            
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
            
            # Check if top 2 cards are within 10% - if so, mark for trade-off explanation
            if len(estimates) >= 2:
                top_value = estimates[0].get('estimated_value', 0)
                second_value = estimates[1].get('estimated_value', 0)
                if top_value > 0:
                    value_diff_pct = abs(top_value - second_value) / top_value
                    if value_diff_pct <= 0.10:  # Within 10%
                        # Mark top 2 cards as close for trade-off explanation
                        estimates[0]['close_tie'] = True
                        estimates[1]['close_tie'] = True
                        estimates[0]['trade_off_needed'] = True
            
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
Spend Amount: ${spend_amount}
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

@mcp.tool()
async def simulate_monthly_spend(user_id: int, dining: float = 0, groceries: float = 0, 
                                 travel: float = 0, gas: float = 0, general: float = 0):
    """
    Simulate monthly spending and calculate annual rewards per card.
    Returns total annual rewards per card, best overall card, and missed value.
    
    Args:
        user_id: The user's ID
        dining: Monthly dining spend
        groceries: Monthly groceries spend
        travel: Monthly travel spend
        gas: Monthly gas spend
        general: Monthly general spend
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Get all active cards for user
            cur = await c.execute(
                "SELECT id, name, bank, reward_type FROM cards WHERE user_id = ? AND active = 1",
                (user_id,)
            )
            cards = await cur.fetchall()
            
            if not cards:
                return {"status": "error", "message": f"No active cards found for user {user_id}"}
            
            monthly_spend = {
                "dining": dining,
                "groceries": groceries,
                "travel": travel,
                "gas": gas,
                "general": general
            }
            
            results = []
            total_monthly = sum(monthly_spend.values())
            
            for card_id, card_name, bank, reward_type in cards:
                # Get reward rules for this card
                cur = await c.execute(
                    "SELECT category, earn_rate, cap FROM reward_rules WHERE card_id = ?",
                    (card_id,)
                )
                rules = await cur.fetchall()
                
                # Calculate monthly rewards by category
                monthly_rewards = 0
                category_details = {}
                
                for category, spend_amount in monthly_spend.items():
                    if spend_amount > 0:
                        # Find matching rule (exact match or fallback to general/other)
                        rule = None
                        for rule_category, earn_rate, cap in rules:
                            if rule_category == category:
                                rule = (rule_category, earn_rate, cap)
                                break
                        
                        if not rule:
                            # Try general fallback
                            for rule_category, earn_rate, cap in rules:
                                if rule_category == "general":
                                    rule = (rule_category, earn_rate, cap)
                                    break
                        
                        if not rule:
                            # Try other fallback
                            for rule_category, earn_rate, cap in rules:
                                if rule_category == "other":
                                    rule = (rule_category, earn_rate, cap)
                                    break
                        
                        if rule:
                            rule_category, earn_rate, cap = rule
                            category_rewards = spend_amount * (earn_rate / 100)
                            
                            # Apply cap if exists (monthly cap, so divide by 12 for annual)
                            if cap is not None:
                                annual_cap = cap * 12  # Convert to annual
                                annual_category_rewards = min(category_rewards * 12, annual_cap)
                                category_rewards = annual_category_rewards / 12
                            
                            monthly_rewards += category_rewards
                            category_details[category] = {
                                "earn_rate": earn_rate,
                                "rewards": round(category_rewards, 2)
                            }
                
                # Calculate annual rewards
                annual_rewards = monthly_rewards * 12
                
                # Calculate estimated value
                value_multiplier = REWARD_VALUE_MAP.get(reward_type, 1.0)
                estimated_annual_value = round(annual_rewards * value_multiplier, 2)
                
                results.append({
                    "card_id": card_id,
                    "card_name": card_name,
                    "bank": bank,
                    "reward_type": reward_type,
                    "monthly_rewards": round(monthly_rewards, 2),
                    "annual_rewards": round(annual_rewards, 2),
                    "estimated_annual_value": estimated_annual_value,
                    "category_details": category_details
                })
            
            # Sort by estimated annual value
            results.sort(key=lambda x: x['estimated_annual_value'], reverse=True)
            best_card = results[0] if results else None
            
            # Calculate missed value (categories with no good card coverage)
            missed_opportunities = []
            for category, spend_amount in monthly_spend.items():
                if spend_amount > 0:
                    # Find best earn rate for this category across all cards
                    best_rate = 0
                    for result in results:
                        if category in result['category_details']:
                            rate = result['category_details'][category]['earn_rate']
                            best_rate = max(best_rate, rate)
                    
                    # If best rate is low (<= 1.5%), suggest improvement
                    if best_rate <= 1.5:
                        annual_spend = spend_amount * 12
                        potential_improvement = annual_spend * 0.03  # Assume 3% could be achieved
                        missed_opportunities.append({
                            "category": category,
                            "current_best_rate": best_rate,
                            "annual_spend": round(annual_spend, 2),
                            "potential_improvement": round(potential_improvement, 2)
                        })
            
            return {
                "monthly_spend": monthly_spend,
                "total_monthly_spend": round(total_monthly, 2),
                "results": results,
                "best_card": best_card,
                "missed_opportunities": missed_opportunities
            }
    except Exception as e:
        return {"status": "error", "message": f"Error simulating spend: {str(e)}"}

@mcp.tool()
async def analyze_wallet_gaps(user_id: int):
    """
    Analyze user's wallet for missing cards, overlapping cards, and redundant cards.
    Returns recommendations for cards to add and estimated value increase.
    
    Args:
        user_id: The user's ID
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Get user's active cards with reward rules
            cur = await c.execute(
                """
                SELECT c.id, c.name, c.bank, c.reward_type, r.category, r.earn_rate
                FROM cards c
                LEFT JOIN reward_rules r ON c.id = r.card_id
                WHERE c.user_id = ? AND c.active = 1
                ORDER BY c.name, r.category
                """,
                (user_id,)
            )
            card_data = await cur.fetchall()
            
            if not card_data:
                return {
                    "status": "error",
                    "message": f"No active cards found for user {user_id}"
                }
            
            # Organize by category
            category_coverage = {}
            card_categories = {}
            
            for card_id, card_name, bank, reward_type, category, earn_rate in card_data:
                if category:
                    if category not in category_coverage:
                        category_coverage[category] = []
                    category_coverage[category].append({
                        "card_id": card_id,
                        "card_name": card_name,
                        "bank": bank,
                        "earn_rate": earn_rate
                    })
                    
                    if card_id not in card_categories:
                        card_categories[card_id] = {
                            "name": card_name,
                            "bank": bank,
                            "categories": {}
                        }
                    card_categories[card_id]["categories"][category] = earn_rate
            
            # Identify gaps (categories with no card or low earn rates)
            gaps = []
            important_categories = ["groceries", "dining", "travel", "gas"]
            
            for category in important_categories:
                if category not in category_coverage:
                    gaps.append({
                        "category": category,
                        "issue": "no_coverage",
                        "message": f"No card covers {category} category"
                    })
                else:
                    max_rate = max([c["earn_rate"] for c in category_coverage[category]])
                    if max_rate <= 1.5:  # Low earn rate
                        gaps.append({
                            "category": category,
                            "issue": "low_rate",
                            "current_best_rate": max_rate,
                            "message": f"Best {category} rate is only {max_rate}%"
                        })
            
            # Identify overlapping cards (multiple cards with similar high rates for same category)
            overlaps = []
            for category, cards in category_coverage.items():
                if len(cards) > 1:
                    high_rate_cards = [c for c in cards if c["earn_rate"] >= 3.0]
                    if len(high_rate_cards) > 1:
                        overlaps.append({
                            "category": category,
                            "cards": high_rate_cards,
                            "message": f"Multiple cards with high {category} rates: {', '.join([c['card_name'] for c in high_rate_cards])}"
                        })
            
            # Load US cards data to suggest additions
            recommendations = []
            us_cards_path = Path(__file__).parent / "data" / "us_cards.json"
            if us_cards_path.exists():
                with open(us_cards_path, "r", encoding="utf-8") as f:
                    us_cards = json.load(f)
                
                # Get user's existing card names
                cur = await c.execute(
                    "SELECT name FROM cards WHERE user_id = ?",
                    (user_id,)
                )
                existing_card_names = {row[0].lower() for row in await cur.fetchall()}
                
                # Suggest cards that fill gaps
                for gap in gaps:
                    category = gap["category"]
                    for us_card in us_cards:
                        if us_card["name"].lower() not in existing_card_names:
                            card_rate = us_card.get("categories", {}).get(category, 0)
                            if card_rate >= 3.0:  # Good rate for this category
                                # Estimate annual value (assuming $500/month in category)
                                monthly_spend = 500
                                annual_spend = monthly_spend * 12
                                current_best = gap.get("current_best_rate", 0)
                                improvement = (card_rate - current_best) / 100 * annual_spend
                                
                                recommendations.append({
                                    "card_name": us_card["name"],
                                    "bank": us_card["bank"],
                                    "annual_fee": us_card.get("annual_fee", 0),
                                    "fills_gap": category,
                                    "earn_rate": card_rate,
                                    "estimated_annual_improvement": round(improvement, 2),
                                    "net_value": round(improvement - us_card.get("annual_fee", 0), 2)
                                })
                                break  # One recommendation per gap
            
            # Sort recommendations by net value
            recommendations.sort(key=lambda x: x.get("net_value", 0), reverse=True)
            
            return {
                "gaps": gaps,
                "overlaps": overlaps,
                "recommendations": recommendations[:5],  # Top 5 recommendations
                "summary": f"Found {len(gaps)} gap(s), {len(overlaps)} overlap(s), {len(recommendations)} recommendation(s)"
            }
    except Exception as e:
        return {"status": "error", "message": f"Error analyzing wallet gaps: {str(e)}"}

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

@mcp.resource("ui://widget/wallet_summary.html", mime_type="text/html+skybridge")
def wallet_summary_widget():
    """
    HTML widget for wallet summary UI.
    Shows active cards, best categories per card, and weak spots.
    """
    widget_path = Path(__file__).parent / "wallet_summary_widget.html"
    try:
        with open(widget_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<html><body><p>Wallet summary widget file not found</p></body></html>"
    except Exception as e:
        return f"<html><body><p>Error loading wallet summary widget: {str(e)}</p></body></html>"

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

@mcp.tool()
async def show_wallet_summary(user_id: int = 1):
    """
    Show wallet summary UI widget.
    Displays active cards, best categories per card, and weak spots (missing coverage).
    
    Args:
        user_id: The user's ID (default: 1 for MVP)
    
    Returns:
        Structured content with wallet analysis and widget reference.
    """
    try:
        # Get active cards
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute(
                """
                SELECT id, name, bank, reward_type, active
                FROM cards
                WHERE user_id = ? AND active = 1
                ORDER BY name ASC
                """,
                (user_id,)
            )
            cols = [d[0] for d in cur.description]
            cards = [dict(zip(cols, r)) for r in await cur.fetchall()]
            
            # Get reward rules for each card to analyze strengths
            strengths = []
            weak_spots = []
            category_coverage = {}
            
            for card in cards:
                cur = await c.execute(
                    "SELECT category, earn_rate FROM reward_rules WHERE card_id = ? ORDER BY earn_rate DESC",
                    (card['id'],)
                )
                rules = await cur.fetchall()
                
                # Find best categories (rate >= 3%)
                best_categories = []
                for category, earn_rate in rules:
                    if earn_rate >= 3.0:
                        best_categories.append(f"{category} ({earn_rate}x)")
                    
                    # Track category coverage
                    if category not in category_coverage:
                        category_coverage[category] = []
                    category_coverage[category].append(earn_rate)
                
                if best_categories:
                    strengths.append(f"{card['name']}: {', '.join(best_categories)}")
            
            # Identify weak spots (important categories with no or low coverage)
            important_categories = ['groceries', 'dining', 'travel', 'gas']
            for category in important_categories:
                if category not in category_coverage:
                    weak_spots.append(f"No card covers {category}")
                else:
                    max_rate = max(category_coverage[category])
                    if max_rate < 2.0:
                        weak_spots.append(f"{category}: best rate is only {max_rate}%")
        
        return {
            "structuredContent": {
                "cards": cards,
                "strengths": strengths,
                "weakSpots": weak_spots,
                "user_id": user_id
            },
            "content": [
                {
                    "type": "text",
                    "text": f"Wallet summary: {len(cards)} active card(s), {len(strengths)} strength(s), {len(weak_spots)} weak spot(s)"
                }
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error loading wallet summary: {str(e)}",
            "structuredContent": {
                "cards": [],
                "strengths": [],
                "weakSpots": [],
                "user_id": user_id
            }
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
            
            # Load US cards data for better recommendations
            us_cards_path = Path(__file__).parent / "data" / "us_cards.json"
            us_cards_available = []
            if us_cards_path.exists():
                with open(us_cards_path, "r", encoding="utf-8") as f:
                    us_cards_data = json.load(f)
                    # Map US cards to available_cards format
                    for us_card in us_cards_data:
                        if (us_card["name"], us_card["bank"]) not in existing_cards:
                            us_cards_available.append({
                                "name": us_card["name"],
                                "bank": us_card["bank"],
                                "reward_type": us_card["reward_type"],
                                "annual_fee": us_card.get("annual_fee", 0),
                                "key_benefits": us_card.get("notes", ""),
                                "target_audience": "travel" if us_card.get("categories", {}).get("travel", 0) >= 3 else "balanced",
                                "categories": us_card.get("categories", {}),
                                "signup_bonus": us_card.get("signup_bonus", {}),
                                "from_us_cards": True
                            })
            
            # Combine available_cards and us_cards
            all_candidate_cards = candidate_cards + us_cards_available
            
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
{json.dumps(all_candidate_cards[:20], indent=2, default=str)}

Task: Rank and select the top 5 cards that would best complement the user's existing portfolio. Consider:
1. Gaps in reward categories (e.g., if user has no travel card, recommend one)
2. Reward type diversity (points, miles, cashback)
3. Annual fee value proposition
4. User's stated preference ({user_pref})
5. Benefits that user doesn't currently have

Return ONLY a JSON array of card names in order of recommendation, e.g., ["Chase Sapphire Reserve", "Amex Platinum", "Capital One Venture X"]
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
                    if ai_response.startswith("```"):
                        ai_response = ai_response.split("```")[1]
                        if ai_response.startswith("json"):
                            ai_response = ai_response[4:]
                    ai_response = ai_response.strip()
                    
                    recommended_names = json.loads(ai_response)
                    
                    # Map names back to cards
                    recommendations = []
                    for name in recommended_names:
                        for card in all_candidate_cards:
                            if card.get('name', '') == name or name in card.get('name', ''):
                                if card not in recommendations:
                                    recommendations.append(card)
                                    break
                    
                    # Fill remaining slots if AI didn't recommend 5
                    remaining = [c for c in all_candidate_cards if c not in recommendations]
                    recommendations.extend(remaining[:5 - len(recommendations)])
                    
                    return recommendations[:5]
                except Exception as e:
                    # Fallback to rule-based if AI fails
                    print(f"AI recommendation failed, using fallback: {e}")
            
            # Fallback: Rule-based matching with US cards data
            recommendations = []
            
            # For travel preference, prioritize travel cards
            if user_pref == 'travel':
                # Sort by travel category rate
                travel_cards = [c for c in all_candidate_cards if c.get('categories', {}).get('travel', 0) >= 3]
                travel_cards.sort(key=lambda x: x.get('categories', {}).get('travel', 0), reverse=True)
                recommendations.extend(travel_cards[:3])
                
                # Add premium travel cards
                premium_travel = [c for c in all_candidate_cards if 'Sapphire Reserve' in c.get('name', '') or 'Platinum' in c.get('name', '') or 'Venture X' in c.get('name', '')]
                for card in premium_travel:
                    if card not in recommendations:
                        recommendations.append(card)
            elif user_pref == 'cashback':
                cashback_cards = [c for c in all_candidate_cards if c.get('reward_type') == 'cashback']
                recommendations.extend(cashback_cards[:5])
            else:
                # Balanced: mix of categories
                # Get best cards for different categories
                best_travel = max([c for c in all_candidate_cards if c.get('categories', {}).get('travel', 0) > 0], 
                                 key=lambda x: x.get('categories', {}).get('travel', 0), default=None)
                best_dining = max([c for c in all_candidate_cards if c.get('categories', {}).get('dining', 0) > 0],
                                 key=lambda x: x.get('categories', {}).get('dining', 0), default=None)
                best_groceries = max([c for c in all_candidate_cards if c.get('categories', {}).get('groceries', 0) > 0],
                                    key=lambda x: x.get('categories', {}).get('groceries', 0), default=None)
                
                for card in [best_travel, best_dining, best_groceries]:
                    if card and card not in recommendations:
                        recommendations.append(card)
            
            # Fill remaining slots
            remaining = [c for c in all_candidate_cards if c not in recommendations]
            recommendations.extend(remaining[:5 - len(recommendations)])
            
            return recommendations[:5]
    except Exception as e:
        return {"status": "error", "message": f"Error getting recommendations: {str(e)}"}

@mcp.tool()
async def recommend_travel_cards(user_id: int = 1, international: bool = True):
    """
    Recommend the best travel credit cards, especially for international flights from the US.
    Works without OpenAI API - uses US card data directly.
    
    Args:
        user_id: The user's ID
        international: Whether user travels internationally (default: True)
    
    Returns:
        List of recommended travel cards with details
    """
    try:
        async with aiosqlite.connect(DB_PATH) as c:
            # Get user's existing cards
            cur = await c.execute(
                "SELECT name, bank FROM cards WHERE user_id = ?",
                (user_id,)
            )
            existing_cards = {(row[0], row[1]) for row in await cur.fetchall()}
        
        # Load US cards data
        us_cards_path = Path(__file__).parent / "data" / "us_cards.json"
        if not us_cards_path.exists():
            return {"status": "error", "message": "US cards data not found"}
        
        with open(us_cards_path, "r", encoding="utf-8") as f:
            us_cards = json.load(f)
        
        # Filter travel cards (travel category >= 3)
        travel_cards = []
        for card in us_cards:
            if (card["name"], card["bank"]) not in existing_cards:
                travel_rate = card.get("categories", {}).get("travel", 0)
                if travel_rate >= 3:
                    card_info = {
                        "name": card["name"],
                        "bank": card["bank"],
                        "reward_type": card["reward_type"],
                        "annual_fee": card.get("annual_fee", 0),
                        "travel_rate": travel_rate,
                        "point_value": card.get("point_value", 0.01),
                        "signup_bonus": card.get("signup_bonus", {}),
                        "transfer_partners": card.get("transfer_partners", []),
                        "notes": card.get("notes", ""),
                        "categories": card.get("categories", {})
                    }
                    
                    # Add credits and offers from metadata if available
                    metadata = card.get("_metadata", {})
                    if metadata:
                        credits = metadata.get("credits", [])
                        if credits:
                            card_info["credits"] = [
                                {
                                    "description": c.get("description", ""),
                                    "value": c.get("value", 0),
                                    "weight": c.get("weight", 0)
                                }
                                for c in credits[:5]  # Limit to top 5 credits
                            ]
                        
                        offers = metadata.get("offers", [])
                        if offers:
                            # Get current offer
                            current_offer = offers[0] if offers else {}
                            card_info["current_offer"] = {
                                "spend": current_offer.get("spend", 0),
                                "amount": current_offer.get("amount", []),
                                "days": current_offer.get("days", 90),
                                "details": current_offer.get("details", "")
                            }
                        
                        # Add URL if available
                        if metadata.get("url"):
                            card_info["url"] = metadata.get("url")
                    
                    travel_cards.append(card_info)
        
        # Sort by travel rate and point value
        travel_cards.sort(key=lambda x: (x["travel_rate"], x["point_value"]), reverse=True)
        
        # For international travel, prioritize cards with good transfer partners
        if international:
            premium_travel = [c for c in travel_cards if len(c.get("transfer_partners", [])) > 3]
            other_travel = [c for c in travel_cards if len(c.get("transfer_partners", [])) <= 3]
            travel_cards = premium_travel + other_travel
        
        return {
            "status": "success",
            "recommendations": travel_cards[:5],
            "message": f"Found {len(travel_cards)} travel cards. Top recommendations for international travel from the US."
        }
    except Exception as e:
        return {"status": "error", "message": f"Error getting travel recommendations: {str(e)}"}

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
    """Get OpenAI client (API key from environment variable or hardcoded for testing)."""
    try:
        from openai import OpenAI
        # Try environment variable first, then fallback to hardcoded (for testing)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)
    except ImportError:
        return None
    except Exception:
        return None

def load_system_prompt():
    """Load system prompt from file."""
    try:
        prompt_path = Path(__file__).parent / "system_prompt.txt"
        if prompt_path.exists():
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        return None
    except Exception as e:
        print(f"Error loading system prompt: {e}")
        return None

@mcp.tool()
async def get_system_instructions():
    """
    Get the system instructions and behavior rules for this credit card strategist.
    Call this tool if you need to understand how to use other tools or what the expected behavior is.
    
    Returns:
        Complete system prompt with all rules, flows, and examples.
    """
    prompt = load_system_prompt()
    if prompt:
        return {
            "status": "success",
            "instructions": prompt,
            "message": "System instructions loaded successfully. Use these rules for all interactions."
        }
    else:
        return {
            "status": "error",
            "message": "System prompt file not found"
        }

@mcp.tool()
async def suggest_tool_for_query(user_query: str, user_id: int = 1):
    """
    Use AI to suggest which tool(s) to call based on user's query.
    This helps ensure the right tools are called for each user request.
    
    Args:
        user_query: The user's question or request
        user_id: The user's ID (default: 1)
    
    Returns:
        Suggested tool name(s) and reasoning
    """
    try:
        # Get user's current state
        async with aiosqlite.connect(DB_PATH) as c:
            cur = await c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            user_exists = await cur.fetchone()
            
            cur = await c.execute("SELECT COUNT(*) FROM cards WHERE user_id = ?", (user_id,))
            card_count = (await cur.fetchone())[0]
        
        # Rule-based tool selection (works without API)
        query_lower = user_query.lower()
        
        # Onboarding queries
        if not user_exists:
            suggestion = {
                "primary_tool": "create_user",
                "secondary_tools": [],
                "reasoning": "User does not exist, need to create user first",
                "required_params": {"preference": "balanced"},
                "onboarding_needed": True
            }
        elif card_count == 0:
            if any(word in query_lower for word in ["add", "card", "wallet", "have"]):
                suggestion = {
                    "primary_tool": "manage_cards_ui",
                    "secondary_tools": [],
                    "reasoning": "User has no cards, need to add cards first",
                    "required_params": {"user_id": user_id},
                    "onboarding_needed": True
                }
            else:
                suggestion = {
                    "primary_tool": "manage_cards_ui",
                    "secondary_tools": [],
                    "reasoning": "User has no cards, guide to add cards",
                    "required_params": {"user_id": user_id},
                    "onboarding_needed": True
                }
        # Travel/recommendation queries
        elif any(word in query_lower for word in ["travel", "flight", "international", "airline", "recommend", "suggest", "which card", "what card", "best card"]):
            # For travel-specific queries, use recommend_travel_cards (works without API)
            if any(word in query_lower for word in ["travel", "flight", "international", "airline"]):
                suggestion = {
                    "primary_tool": "recommend_travel_cards",
                    "secondary_tools": ["recommend_new_cards", "show_recommendations_ui"],
                    "reasoning": "User asking for travel card recommendations - use recommend_travel_cards first (works without API)",
                    "required_params": {"user_id": user_id, "international": "international" in query_lower or "flight" in query_lower},
                    "onboarding_needed": False
                }
            elif "recommend" in query_lower or "suggest" in query_lower or "best" in query_lower:
                suggestion = {
                    "primary_tool": "recommend_new_cards",
                    "secondary_tools": ["show_recommendations_ui"],
                    "reasoning": "User asking for card recommendations",
                    "required_params": {"user_id": user_id, "preference": "travel" if "travel" in query_lower else None},
                    "onboarding_needed": False
                }
            else:
                suggestion = {
                    "primary_tool": "recommend_best_card",
                    "secondary_tools": ["list_cards"],
                    "reasoning": "User asking which card to use",
                    "required_params": {"user_id": user_id, "category": "travel" if "travel" in query_lower else "general", "spend_amount": 0},
                    "onboarding_needed": False
                }
        # Card management queries
        elif any(word in query_lower for word in ["add card", "my cards", "show cards", "list cards"]):
            suggestion = {
                "primary_tool": "manage_cards_ui",
                "secondary_tools": ["list_cards"],
                "reasoning": "User wants to manage or view their cards",
                "required_params": {"user_id": user_id},
                "onboarding_needed": False
            }
        # Wallet summary queries
        elif any(word in query_lower for word in ["wallet", "summary", "overview", "portfolio"]):
            suggestion = {
                "primary_tool": "show_wallet_summary",
                "secondary_tools": ["list_cards"],
                "reasoning": "User wants to see wallet summary",
                "required_params": {"user_id": user_id},
                "onboarding_needed": False
            }
        # Deals queries
        elif any(word in query_lower for word in ["deal", "offer", "promotion"]):
            suggestion = {
                "primary_tool": "show_deals_ui",
                "secondary_tools": ["get_deals"],
                "reasoning": "User asking about deals or offers",
                "required_params": {"user_id": user_id},
                "onboarding_needed": False
            }
        # General queries - use enhanced_chat_response if API available, otherwise recommend_new_cards
        else:
            client = get_openai_client()
            if client:
                suggestion = {
                    "primary_tool": "enhanced_chat_response",
                    "secondary_tools": ["list_cards"],
                    "reasoning": "General query, use enhanced chat response",
                    "required_params": {"user_id": user_id, "user_query": user_query},
                    "onboarding_needed": False
                }
            else:
                # Fallback: suggest recommendations
                suggestion = {
                    "primary_tool": "recommend_new_cards",
                    "secondary_tools": ["show_recommendations_ui"],
                    "reasoning": "General query, show card recommendations as fallback",
                    "required_params": {"user_id": user_id},
                    "onboarding_needed": False
                }
        
        # Try AI enhancement if available
        client = get_openai_client()
        if client:
            try:
                available_tools = [
                    "create_user", "add_card", "list_cards", "get_reward_rules",
                    "recommend_best_card", "estimate_rewards", "simulate_monthly_spend",
                    "analyze_wallet_gaps", "show_wallet_summary", "manage_cards_ui",
                    "show_deals_ui", "show_recommendations_ui", "recommend_new_cards",
                    "recommend_travel_cards", "lookup_merchant", "get_system_instructions", 
                    "enhanced_chat_response"
                ]
                
                system_prompt = load_system_prompt() or "You are a credit card rewards strategist."
                
                prompt = f"""You are a tool selection assistant. The rule-based system suggested:
{json.dumps(suggestion, indent=2)}

User Query: "{user_query}"
User State: exists={bool(user_exists)}, cards={card_count}

Available Tools: {', '.join(available_tools)}

Refine the suggestion if needed, or confirm the rule-based suggestion is correct.
Return ONLY a JSON object with the same structure as above."""

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a tool selection assistant. Always return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.2
                )
                
                ai_response = response.choices[0].message.content.strip()
                if ai_response.startswith("```"):
                    ai_response = ai_response.split("```")[1]
                    if ai_response.startswith("json"):
                        ai_response = ai_response[4:]
                ai_response = ai_response.strip()
                
                ai_suggestion = json.loads(ai_response)
                # Use AI suggestion if it's better
                if ai_suggestion.get("primary_tool"):
                    suggestion = ai_suggestion
            except Exception as e:
                # Use rule-based suggestion if AI fails
                print(f"AI tool suggestion failed, using rule-based: {e}")
        
        return {
            "status": "success",
            "suggestion": suggestion,
            "user_state": {
                "user_exists": bool(user_exists),
                "card_count": card_count
            }
        }
    except Exception as e:
            return {
                "status": "error",
            "message": f"Error suggesting tool: {str(e)}"
        }

@mcp.tool()
async def enhanced_chat_response(user_query: str, context: str = "", user_id: int = 1):
    """
    Get enhanced chat response using OpenAI API for complex queries.
    Uses the user's card data as context and follows system prompt rules.
    Falls back to rule-based responses if OpenAI API is not configured.
    
    Args:
        user_query: User's question
        context: Optional context about user's cards
        user_id: The user's ID (default: 1)
    """
    try:
        # Build context from user's cards if not provided
        if not context:
            async with aiosqlite.connect(DB_PATH) as c:
                cur = await c.execute(
                    """SELECT c.name, c.bank, c.reward_type, r.category, r.earn_rate
                       FROM cards c
                       LEFT JOIN reward_rules r ON c.id = r.card_id
                       WHERE c.user_id = ? AND c.active = 1""",
                    (user_id,)
                )
                cards_data = await cur.fetchall()
                if cards_data:
                    context = "User's cards: " + json.dumps([{
                        "name": row[0], "bank": row[1], "reward_type": row[2],
                        "category": row[3], "earn_rate": row[4]
                    } for row in cards_data], indent=2)
        
        client = get_openai_client()
        if not client:
            # Fallback: Provide rule-based response without API
            query_lower = user_query.lower()
            
            # Travel-related queries
            if any(word in query_lower for word in ["travel", "flight", "international", "airline", "hotel"]):
                async with aiosqlite.connect(DB_PATH) as c:
                    cur = await c.execute(
                        """SELECT c.name, c.bank, r.category, r.earn_rate
                           FROM cards c
                           LEFT JOIN reward_rules r ON c.id = r.card_id
                           WHERE c.user_id = ? AND c.active = 1 AND r.category = 'travel'
                           ORDER BY r.earn_rate DESC""",
                        (user_id,)
                    )
                    travel_cards = await cur.fetchall()
                    
                    if travel_cards:
                        best_card = travel_cards[0]
                        response_text = f"""Based on your cards, **{best_card[0]}** ({best_card[1]}) is your best option for travel with {best_card[3]}% earn rate on travel.

For international flights from the US, consider these cards from our database:
- **Chase Sapphire Reserve**: 5x on travel, 1.5cpp value, $550 annual fee
- **Amex Platinum**: 5x on flights/hotels, premium travel benefits, $695 annual fee  
- **Capital One Venture X**: 10x on travel bookings, 2x everything else, $395 annual fee

Would you like me to recommend specific cards to add to your wallet?"""
                    else:
                        response_text = """For international travel from the US, I recommend these travel-focused cards:

**Premium Options:**
- **Chase Sapphire Reserve**: 5x on travel, 1.5cpp value, excellent transfer partners
- **Amex Platinum**: 5x on flights/hotels, premium lounge access, $695 annual fee

**Value Options:**
- **Capital One Venture X**: 10x on travel bookings, 2x everything else, $395 annual fee
- **Chase Sapphire Preferred**: 5x on travel, 1.25cpp value, $95 annual fee

Would you like me to show you personalized recommendations based on your current cards?"""
            
            # Card recommendation queries
            elif any(word in query_lower for word in ["recommend", "suggest", "which card", "what card", "best card"]):
                response_text = """I can help you find the best cards! Let me analyze your current wallet and suggest cards that would complement it.

Would you like me to:
1. Show personalized card recommendations?
2. Analyze gaps in your current wallet?
3. Recommend cards for specific categories (travel, dining, groceries)?

Just ask and I'll help you optimize your credit card portfolio!"""
            
            # General queries - provide helpful response
            else:
                response_text = f"""I can help you with credit card optimization! Based on your query: "{user_query}"

Here's what I can do:
- Recommend which card to use for specific purchases
- Suggest new cards to add to your wallet
- Analyze your current cards and find gaps
- Show deals and offers for your cards
- Help optimize your rewards strategy

Your current cards: {context if context else "No cards added yet"}

What would you like to know?"""
            
            return {
                "status": "success",
                "response": response_text,
                "note": "Response generated without OpenAI API. For enhanced responses, set OPENAI_API_KEY environment variable."
            }
        
        # Load system prompt
        system_prompt = load_system_prompt() or """You are an expert credit card rewards strategist. 
        Your role is to help users optimize their credit card usage and maximize rewards.
        Always base answers on provided card data context. Use USD ($) for all monetary values."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"""Context about user's credit cards and reward rules:
{context}

User Question: {user_query}

Provide a clear, helpful answer based on the context above. Follow the system instructions for response format and behavior. If the context doesn't contain enough information to answer fully, acknowledge what you can answer and what's missing."""}
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
                "summary": f"You have {totals['points']:,.0f} points, {totals['miles']:,.0f} miles, and ${totals['cashback']:,.2f} cashback"
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
                    "text": f"Comparing top {len(top_cards)} cards for ${spend_amount:,.0f} {category} spend"
                }
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error showing comparison: {str(e)}",
            "structuredContent": {"comparison": [], "spend_amount": spend_amount, "category": category}
        }

# Load system prompt at startup and make it available
SYSTEM_PROMPT = load_system_prompt()
if SYSTEM_PROMPT:
    print("System prompt loaded successfully")
else:
    print("Warning: System prompt not found")

# Start the server
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
