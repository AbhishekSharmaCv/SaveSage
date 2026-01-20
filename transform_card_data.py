"""
Transform comprehensive US card data from Uscards_data.md to the system's expected format.
This script parses the comprehensive card data and converts it to match us_cards.json structure.
"""
import json
import re
from pathlib import Path

def parse_escaped_json(file_path):
    """Parse the escaped JSON from the markdown file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    # The file contains escaped JSON, so we need to unescape it
    # Remove the leading backslash if present
    if content.startswith('\\'):
        content = content[1:]
    
    # Fix escaped underscores (most common issue)
    content = content.replace('\\_', '_')
    
    # Handle escaped brackets
    content = content.replace('\\[', '[')
    content = content.replace('\\]', ']')
    
    # Use json.JSONDecoder with a custom error handler to fix invalid escapes
    import re
    
    # More careful approach: only fix known problematic patterns
    # Fix \& in URLs (common issue)
    content = content.replace('\\&', '&')
    # Fix \<= (less than or equal)
    content = content.replace('\\<=', '<=')
    # Fix \>= (greater than or equal)
    content = content.replace('\\>=', '>=')
    # Fix \# in URLs
    content = content.replace('\\#', '#')
    # Fix double-escaped quotes: \\" should be \"
    content = content.replace('\\\\"', '\\"')
    
    # Try to parse, and if it fails, try to fix the specific error
    try:
        data = json.loads(content)
        return data
    except json.JSONDecodeError as e:
        error_pos = e.pos if hasattr(e, 'pos') else None
        if error_pos:
            # Try to see what's around the error
            start = max(0, error_pos - 50)
            end = min(len(content), error_pos + 50)
            error_context = content[start:end]
            print(f"Error at position {error_pos}")
            print(f"Context: ...{error_context}...")
        
        # Try using json.decoder with more lenient parsing
        # Actually, let's try using ijson or just manually fix common issues
        # Replace \ followed by non-standard chars, but preserve valid JSON escapes
        # Valid JSON escapes: \" \\ \/ \b \f \n \r \t \uXXXX
        def fix_invalid_escapes(text):
            """Fix invalid escape sequences while preserving valid ones."""
            result = []
            i = 0
            while i < len(text):
                if text[i] == '\\' and i + 1 < len(text):
                    next_char = text[i + 1]
                    # Valid JSON escape sequences
                    if next_char in ['"', '\\', '/', 'b', 'f', 'n', 'r', 't']:
                        result.append(text[i])
                        result.append(next_char)
                        i += 2
                    # Unicode escape sequence \uXXXX
                    elif next_char == 'u' and i + 5 < len(text):
                        # Check if it's a valid unicode escape
                        try:
                            int(text[i+2:i+6], 16)
                            result.append(text[i:i+6])
                            i += 6
                        except:
                            # Invalid unicode escape, remove backslash
                            result.append(next_char)
                            i += 2
                    # Invalid escape - remove the backslash
                    else:
                        result.append(next_char)
                        i += 2
                else:
                    result.append(text[i])
                    i += 1
            return ''.join(result)
        
        try:
            content_fixed = fix_invalid_escapes(content)
            data = json.loads(content_fixed)
            return data
        except Exception as e2:
            print(f"Fixed parsing also failed: {e2}")
            raise

def map_issuer_to_bank(issuer):
    """Map issuer field to bank name."""
    issuer_map = {
        "AMERICAN_EXPRESS": "American Express",
        "CHASE": "Chase",
        "CAPITAL_ONE": "Capital One",
        "CITI": "Citi",
        "BILT": "Bilt",
        "DISCOVER": "Discover",
        "WELLS_FARGO": "Wells Fargo",
        "BANK_OF_AMERICA": "Bank of America",
        "US_BANK": "US Bank"
    }
    return issuer_map.get(issuer, issuer.replace("_", " ").title())

def determine_reward_type(currency, universal_cashback_percent):
    """Determine reward type from currency and cashback percent."""
    if currency in ["USD", "CASH"]:
        return "cashback"
    elif currency in ["AMERICAN_EXPRESS", "CHASE", "CITI", "CAPITAL_ONE", "BILT"]:
        return "points"
    elif currency in ["DELTA", "UNITED", "AMERICAN_AIRLINES", "SOUTHWEST", "JETBLUE", 
                      "ALASKA", "HAWAIIAN", "FRONTIER", "SPIRIT", "VIRGIN_ATLANTIC",
                      "AIR_CANADA", "AVIANCA", "EMIRATES", "QANTAS", "SINGAPORE_AIRLINES",
                      "BRITISH_AIRWAYS", "AIR_FRANCE_KLM"]:
        return "miles"
    elif currency in ["HILTON", "MARRIOTT", "HYATT", "IHG", "CHOICE", "WYNDHAM"]:
        return "points"
    else:
        # Default based on cashback percent
        if universal_cashback_percent and universal_cashback_percent > 0:
            return "cashback"
        return "points"

def extract_categories_from_card(card_data):
    """Extract category rewards from card data. 
    Since the comprehensive data doesn't have explicit categories, 
    we'll infer from currency, credits, and other fields."""
    categories = {
        "dining": 1,
        "travel": 1,
        "groceries": 1,
        "gas": 1,
        "general": 1
    }
    
    # Check for travel-related indicators
    currency = card_data.get("currency", "")
    if currency in ["DELTA", "UNITED", "AMERICAN_AIRLINES", "SOUTHWEST", "JETBLUE"]:
        categories["travel"] = 5
    
    # Check credits for travel benefits
    credits = card_data.get("credits", [])
    travel_credits = [c for c in credits if any(keyword in c.get("description", "").lower() 
                                                 for keyword in ["lounge", "airline", "hotel", "travel", "precheck"])]
    if travel_credits:
        categories["travel"] = max(categories["travel"], 3)
    
    # Universal cashback percent can indicate general spending
    universal_cb = card_data.get("universalCashbackPercent", 0)
    if universal_cb >= 2:
        categories["general"] = universal_cb
    
    return categories

def extract_signup_bonus(offers):
    """Extract signup bonus from offers."""
    if not offers or len(offers) == 0:
        return {"amount": 0, "spend": 0, "days": 0}
    
    # Get the first (current) offer
    offer = offers[0]
    spend = offer.get("spend", 0)
    days = offer.get("days", 90)
    
    # Extract amount - could be in different formats
    amount = 0
    amount_data = offer.get("amount", [])
    if amount_data and len(amount_data) > 0:
        if isinstance(amount_data[0], dict):
            amount = amount_data[0].get("amount", 0)
        elif isinstance(amount_data[0], (int, float)):
            amount = amount_data[0]
    
    return {
        "amount": int(amount),
        "spend": int(spend),
        "days": int(days)
    }

def get_transfer_partners(currency, issuer):
    """Get transfer partners based on currency and issuer."""
    transfer_partners_map = {
        "AMERICAN_EXPRESS": ["Delta", "Air France-KLM", "Emirates", "Hilton", "Marriott", "British Airways"],
        "CHASE": ["United", "Hyatt", "British Airways", "Singapore Airlines", "JetBlue", "Southwest"],
        "CAPITAL_ONE": ["Air Canada Aeroplan", "Avianca LifeMiles", "Emirates Skywards", "Qantas", "Marriott Bonvoy"],
        "CITI": ["American Airlines", "JetBlue", "Choice Hotels", "Wyndham"],
        "BILT": ["American Airlines", "United", "Hyatt", "Marriott", "Air France-KLM"]
    }
    
    if currency in ["AMERICAN_EXPRESS", "CHASE", "CAPITAL_ONE", "CITI", "BILT"]:
        return transfer_partners_map.get(issuer, [])
    
    return []

def calculate_point_value(currency, reward_type):
    """Calculate point value based on currency and reward type."""
    if reward_type == "cashback":
        return 0.01
    
    # Point values for different programs
    point_values = {
        "AMERICAN_EXPRESS": 0.0125,
        "CHASE": 0.0125,
        "CAPITAL_ONE": 0.01,
        "CITI": 0.01,
        "BILT": 0.0125,
        "DELTA": 0.012,
        "UNITED": 0.012,
        "HILTON": 0.005,
        "MARRIOTT": 0.008,
        "HYATT": 0.02
    }
    
    return point_values.get(currency, 0.01)

def transform_card(card_data):
    """Transform a single card from comprehensive format to system format."""
    issuer = card_data.get("issuer", "")
    bank = map_issuer_to_bank(issuer)
    name = card_data.get("name", "")
    currency = card_data.get("currency", "")
    universal_cb = card_data.get("universalCashbackPercent", 0)
    
    reward_type = determine_reward_type(currency, universal_cb)
    categories = extract_categories_from_card(card_data)
    signup_bonus = extract_signup_bonus(card_data.get("offers", []))
    point_value = calculate_point_value(currency, reward_type)
    transfer_partners = get_transfer_partners(currency, issuer)
    
    # Build notes from credits and other info
    notes_parts = []
    credits = card_data.get("credits", [])
    if credits:
        credit_descriptions = [c.get("description", "") for c in credits if c.get("description")]
        if credit_descriptions:
            notes_parts.append(f"Credits: {', '.join(credit_descriptions[:3])}")
    
    # Add offer details if available
    offers = card_data.get("offers", [])
    if offers:
        offer = offers[0]
        details = offer.get("details", "")
        if details:
            notes_parts.append(details)
    
    notes = ". ".join(notes_parts) if notes_parts else ""
    
    transformed = {
        "name": name,
        "bank": bank,
        "annual_fee": card_data.get("annualFee", 0),
        "reward_type": reward_type,
        "categories": categories,
        "signup_bonus": signup_bonus,
        "point_value": point_value,
        "transfer_partners": transfer_partners,
        "approximate": True,  # Since we're inferring categories
    }
    
    if notes:
        transformed["notes"] = notes
    
    # Add additional fields for future use
    transformed["_metadata"] = {
        "cardId": card_data.get("cardId"),
        "currency": currency,
        "isBusiness": card_data.get("isBusiness", False),
        "url": card_data.get("url", ""),
        "imageUrl": card_data.get("imageUrl", ""),
        "credits": credits,
        "offers": offers,
        "historicalOffers": card_data.get("historicalOffers", []),
        "discontinued": card_data.get("discontinued", False)
    }
    
    return transformed

def main():
    """Main transformation function."""
    project_dir = Path(__file__).parent
    input_file = project_dir / "Uscards_data.md"
    output_file = project_dir / "data" / "us_cards.json"
    
    print(f"Reading card data from {input_file}...")
    try:
        cards_data = parse_escaped_json(input_file)
        print(f"Found {len(cards_data)} cards")
    except Exception as e:
        print(f"Error reading input file: {e}")
        return
    
    print("Transforming cards...")
    transformed_cards = []
    skipped = 0
    
    for card in cards_data:
        # Skip discontinued cards
        if card.get("discontinued", False):
            skipped += 1
            continue
        
        try:
            transformed = transform_card(card)
            transformed_cards.append(transformed)
        except Exception as e:
            print(f"Error transforming card {card.get('name', 'Unknown')}: {e}")
            skipped += 1
    
    print(f"Transformed {len(transformed_cards)} cards (skipped {skipped} discontinued)")
    
    # Sort by bank and name
    transformed_cards.sort(key=lambda x: (x["bank"], x["name"]))
    
    # Write to output file
    print(f"Writing to {output_file}...")
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(transformed_cards, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Successfully transformed {len(transformed_cards)} cards!")
    print(f"   Output: {output_file}")
    
    # Print summary by bank
    banks = {}
    for card in transformed_cards:
        bank = card["bank"]
        banks[bank] = banks.get(bank, 0) + 1
    
    print("\nCards by bank:")
    for bank, count in sorted(banks.items()):
        print(f"   {bank}: {count} cards")

if __name__ == "__main__":
    main()
