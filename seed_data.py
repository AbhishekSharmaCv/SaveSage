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
    """Seed initial deals, available cards, and merchant mappings."""
    async with aiosqlite.connect(DB_PATH) as c:
        # Seed available cards (more comprehensive list)
        available_cards = [
            ("HDFC Infinia", "HDFC", "points", 12500, "5x rewards on travel, 3x on dining, unlimited airport lounge access, concierge service", "travel", None),
            ("Axis Magnus", "Axis Bank", "points", 10000, "5x rewards on travel, 4x on dining, premium benefits, golf access", "travel", None),
            ("SBI Cashback", "SBI", "cashback", 999, "5% cashback on online shopping, 1% on all other spends, no cap", "cashback", None),
            ("ICICI Amazon Pay", "ICICI", "cashback", 0, "5% cashback on Amazon, 2% on bill payments, 1% on other spends", "cashback", None),
            ("Amex Platinum", "American Express", "points", 60000, "Premium travel card with unlimited lounge access, concierge, hotel benefits", "travel", 2000000),
            ("HDFC Regalia", "HDFC", "points", 2500, "4x rewards on travel, 2x on dining, lounge access, travel vouchers", "balanced", None),
            ("Axis Ace", "Axis Bank", "cashback", 499, "2% cashback on all spends, 5% on bill payments via Google Pay", "cashback", None),
            ("HDFC Diners Black", "HDFC", "points", 10000, "4x rewards on travel, 3x on dining, lounge access, golf benefits", "travel", None),
            ("SBI SimplyClick", "SBI", "points", 499, "5x rewards on online shopping, 1x on other spends, movie benefits", "balanced", None),
            ("ICICI Coral", "ICICI", "points", 500, "2x rewards on dining, 1x on other spends, movie benefits", "balanced", None),
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
        
        # Seed deals (more comprehensive)
        deals = [
            ("10% Cashback on Swiggy", "Get 10% cashback on all Swiggy orders using HDFC cards", "HDFC Infinia", "dining", 10, None, "2025-12-31", "Swiggy", "Valid on orders above ₹500"),
            ("15% Cashback on Zomato", "Earn 15% cashback on Zomato orders with Axis cards", "Axis Magnus", "dining", 15, None, "2025-12-31", "Zomato", "Valid on orders above ₹300"),
            ("5% Extra on Amazon", "Earn 5% extra rewards on Amazon purchases", "ICICI Amazon Pay", "shopping", 5, None, "2025-12-31", "Amazon", "Valid on Prime members"),
            ("10% Off on Flipkart", "Get 10% instant discount on Flipkart with SBI cards", "SBI Cashback", "shopping", 10, None, "2025-12-31", "Flipkart", "Max discount ₹500"),
            ("Travel Bonus Miles", "Get 2x miles on all travel bookings", "Axis Magnus", "travel", None, None, "2025-12-31", "All Travel", "Valid till Dec 2025"),
            ("Dining Delight", "15% off at select restaurants", None, "dining", 15, None, "2025-12-31", "Partner Restaurants", "Valid on weekends"),
            ("Uber 20% Cashback", "Get 20% cashback on Uber rides with HDFC cards", "HDFC Regalia", "travel", 20, None, "2025-12-31", "Uber", "Max ₹200 per ride"),
            ("Fuel Savings", "5% cashback on fuel purchases", None, "fuel", 5, None, "2025-12-31", "All Fuel Stations", "Valid on weekends"),
            ("Movie Magic", "Buy 1 Get 1 on movie tickets", "SBI SimplyClick", "entertainment", 50, None, "2025-12-31", "BookMyShow", "Valid on weekends"),
            ("Hotel Rewards", "Get 2x points on hotel bookings", "HDFC Infinia", "travel", None, None, "2025-12-31", "Partner Hotels", "Valid on bookings above ₹5000"),
        ]
        
        # Seed merchant category mappings
        merchant_mappings = [
            ("swiggy", "dining", 1.0),
            ("zomato", "dining", 1.0),
            ("uber", "travel", 1.0),
            ("ola", "travel", 1.0),
            ("amazon", "shopping", 1.0),
            ("flipkart", "shopping", 1.0),
            ("myntra", "shopping", 1.0),
            ("make my trip", "travel", 1.0),
            ("goibibo", "travel", 1.0),
            ("bookmyshow", "entertainment", 0.9),
            ("netflix", "entertainment", 1.0),
            ("spotify", "entertainment", 1.0),
            ("irctc", "travel", 1.0),
            ("indigo", "travel", 1.0),
            ("spicejet", "travel", 1.0),
            ("air india", "travel", 1.0),
            ("oyo", "travel", 1.0),
            ("starbucks", "dining", 1.0),
            ("dominos", "dining", 1.0),
            ("pizza hut", "dining", 1.0),
            ("mcdonalds", "dining", 1.0),
        ]
        
        for mapping in merchant_mappings:
            try:
                await c.execute(
                    """INSERT OR IGNORE INTO merchant_categories(merchant_name, category, confidence)
                       VALUES (?, ?, ?)""",
                    mapping
                )
            except Exception as e:
                print(f"Error adding merchant mapping {mapping[0]}: {e}")
        
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
        print(f"   - Added {len(merchant_mappings)} merchant category mappings")

if __name__ == "__main__":
    asyncio.run(seed_data())
