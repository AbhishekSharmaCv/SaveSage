"""
Seed script to populate initial data for deals and available cards.
Run this after setting up the database to add sample data.
"""
import asyncio
import aiosqlite
import tempfile
import os

DB_PATH = os.path.join(tempfile.gettempdir(), "rewards_strategist.db")

async def seed_data():
    """Seed initial deals and available cards."""
    async with aiosqlite.connect(DB_PATH) as c:
        # Seed available cards
        available_cards = [
            ("HDFC Infinia", "HDFC", "points", 12500, "5x rewards on travel, 3x on dining, airport lounge access", "travel", None),
            ("Axis Magnus", "Axis Bank", "points", 10000, "5x rewards on travel, 4x on dining, premium benefits", "travel", None),
            ("SBI Cashback", "SBI", "cashback", 999, "5% cashback on online, 1% on all other spends", "cashback", None),
            ("ICICI Amazon Pay", "ICICI", "cashback", 0, "5% cashback on Amazon, 1% on other spends", "cashback", None),
            ("Amex Platinum", "American Express", "points", 60000, "Premium travel card with lounge access, concierge", "travel", 2000000),
            ("HDFC Regalia", "HDFC", "points", 2500, "4x rewards on travel, 2x on dining, lounge access", "balanced", None),
        ]
        
        for card in available_cards:
            try:
                await c.execute(
                    """INSERT OR IGNORE INTO available_cards(name, bank, reward_type, annual_fee, key_benefits, target_audience, min_income)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    card
                )
            except Exception as e:
                print(f"Error adding card {card[0]}: {e}")
        
        # Seed deals
        deals = [
            ("10% Cashback on Swiggy", "Get 10% cashback on all Swiggy orders using HDFC cards", "HDFC Infinia", "dining", 10, None, "2025-12-31", "Swiggy", "Valid on orders above ₹500"),
            ("5% Extra on Amazon", "Earn 5% extra rewards on Amazon purchases", "ICICI Amazon Pay", "shopping", 5, None, "2025-12-31", "Amazon", "Valid on Prime members"),
            ("Travel Bonus Miles", "Get 2x miles on all travel bookings", "Axis Magnus", "travel", None, None, "2025-12-31", "All Travel", "Valid till Dec 2025"),
            ("Dining Delight", "15% off at select restaurants", None, "dining", 15, None, "2025-12-31", "Partner Restaurants", "Valid on weekends"),
        ]
        
        for deal in deals:
            try:
                await c.execute(
                    """INSERT OR IGNORE INTO deals(title, description, card_name, category, discount_percent, discount_amount, valid_until, merchant, terms)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    deal
                )
            except Exception as e:
                print(f"Error adding deal {deal[0]}: {e}")
        
        await c.commit()
        print("✅ Data seeded successfully!")
        print(f"   - Added {len(available_cards)} available cards")
        print(f"   - Added {len(deals)} deals")

if __name__ == "__main__":
    asyncio.run(seed_data())
