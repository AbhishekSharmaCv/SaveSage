# Card Data System Update

## Overview
The system has been updated to use comprehensive US credit card data from `Uscards_data.md`. This update includes 167 credit cards with detailed information including credits, offers, signup bonuses, and transfer partners.

## Changes Made

### 1. Data Transformation
- **Script**: `transform_card_data.py`
- **Input**: `Uscards_data.md` (comprehensive card data in escaped JSON format)
- **Output**: `data/us_cards.json` (167 cards in system-compatible format)
- **Process**:
  - Parsed escaped JSON from markdown file
  - Transformed card data to match system schema
  - Mapped issuers to bank names
  - Determined reward types (points/miles/cashback)
  - Extracted categories, signup bonuses, transfer partners
  - Preserved metadata (credits, offers, URLs, etc.)

### 2. Enhanced Card Data Structure
Each card now includes:
- **Basic Info**: name, bank, annual_fee, reward_type
- **Categories**: dining, travel, groceries, gas, general (with earn rates)
- **Signup Bonus**: amount, spend requirement, time window
- **Point Value**: redemption value for points/miles
- **Transfer Partners**: airline and hotel partners
- **Metadata** (`_metadata` field):
  - Credits (lounge access, hotel credits, etc.)
  - Current offers
  - Historical offers
  - URLs and image URLs
  - Business card flags

### 3. System Enhancements

#### Auto-Seed Function (`auto_seed_reward_rules`)
- Enhanced to include signup bonus information in notes
- Adds credit descriptions from metadata
- Provides more detailed reward rule notes

#### Travel Card Recommendations (`recommend_travel_cards`)
- Now includes credits information
- Shows current signup offers
- Includes card URLs for easy access
- Better prioritization based on transfer partners and credits

### 4. Card Statistics
- **Total Cards**: 167 (5 discontinued cards skipped)
- **Banks Represented**: 17 different issuers
  - American Express: 32 cards
  - Chase: 35 cards
  - Barclays: 21 cards
  - Bank of America: 14 cards
  - Capital One: 10 cards
  - Citi: 11 cards
  - US Bank: 12 cards
  - Wells Fargo: 9 cards
  - And 9 more banks

## Usage

### Adding Cards
When users add cards that match names in `us_cards.json`, the system automatically:
1. Creates reward rules for all categories
2. Includes signup bonus information
3. Adds credit descriptions
4. Provides detailed notes

### Recommendations
The `recommend_travel_cards` function now returns:
- Card details with credits
- Current signup offers
- Transfer partner information
- URLs for application

## Files Modified
1. `data/us_cards.json` - Updated with 167 comprehensive cards
2. `main.py` - Enhanced auto-seed and recommendation functions
3. `transform_card_data.py` - New transformation script

## Future Enhancements
- Use credits information in value calculations
- Display offers in card recommendations UI
- Track historical offers for better recommendations
- Use business card flags for filtering

## Notes
- The transformation script handles escaped JSON and various edge cases
- Discontinued cards are automatically filtered out
- Categories are inferred from currency, credits, and other indicators
- Point values are estimated based on program type
