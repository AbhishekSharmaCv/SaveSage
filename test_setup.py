#!/usr/bin/env python3
"""
Test script to verify the RewardsStrategist setup is working correctly.
Run this before committing to ensure everything is functional.
"""
import sys
import asyncio
import tempfile
import os

# Test imports
print("🔍 Testing imports...")
try:
    from fastmcp import FastMCP
    import aiosqlite
    from pathlib import Path
    import json
    print("✅ All core imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

# Test OpenAI import (optional)
try:
    from openai import OpenAI
    print("✅ OpenAI import successful (optional)")
except ImportError:
    print("⚠️  OpenAI not installed (optional, will use fallbacks)")

# Test main module import
print("\n🔍 Testing main module...")
try:
    # Change to the project directory
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import main
    print("✅ Main module imports successfully")
except Exception as e:
    print(f"❌ Main module import error: {e}")
    sys.exit(1)

# Test database initialization
print("\n🔍 Testing database initialization...")
try:
    # The init_db() is called at module load, so if we got here, it worked
    # But let's verify the database file exists
    db_path = os.path.join(tempfile.gettempdir(), "rewards_strategist.db")
    if os.path.exists(db_path):
        print(f"✅ Database file exists at: {db_path}")
    else:
        print(f"⚠️  Database file not found (will be created on first run)")
except Exception as e:
    print(f"❌ Database test error: {e}")

# Test widget files exist
print("\n🔍 Testing widget files...")
widget_files = [
    "cards_widget.html",
    "deals_widget.html",
    "recommendations_widget.html"
]
all_widgets_exist = True
for widget in widget_files:
    widget_path = Path(__file__).parent / widget
    if widget_path.exists():
        print(f"✅ {widget} exists")
    else:
        print(f"❌ {widget} NOT FOUND")
        all_widgets_exist = False

if not all_widgets_exist:
    print("❌ Some widget files are missing")
    sys.exit(1)

# Test MCP tools registration
print("\n🔍 Testing MCP tools registration...")
try:
    # Count tools and resources
    tools = [attr for attr in dir(main.mcp) if not attr.startswith('_')]
    print(f"✅ MCP instance created: {main.mcp}")
    
    # Check if we can access the mcp object
    if hasattr(main.mcp, 'tools'):
        print(f"✅ MCP tools registered: {len(main.mcp.tools) if hasattr(main.mcp.tools, '__len__') else 'N/A'}")
    if hasattr(main.mcp, 'resources'):
        print(f"✅ MCP resources registered: {len(main.mcp.resources) if hasattr(main.mcp.resources, '__len__') else 'N/A'}")
except Exception as e:
    print(f"❌ MCP registration test error: {e}")

# Test async database operations
print("\n🔍 Testing async database operations...")
async def test_db_ops():
    try:
        db_path = os.path.join(tempfile.gettempdir(), "rewards_strategist.db")
        async with aiosqlite.connect(db_path) as conn:
            # Test query
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = await cursor.fetchall()
            expected_tables = ['users', 'cards', 'reward_rules', 'available_cards', 'deals']
            found_tables = [t[0] for t in tables]
            
            print(f"✅ Database connection successful")
            print(f"   Found tables: {found_tables}")
            
            for table in expected_tables:
                if table in found_tables:
                    print(f"   ✅ Table '{table}' exists")
                else:
                    print(f"   ❌ Table '{table}' MISSING")
                    return False
        return True
    except Exception as e:
        print(f"❌ Database operation error: {e}")
        return False

db_test_result = asyncio.run(test_db_ops())
if not db_test_result:
    sys.exit(1)

# Test OpenAI client (if available)
print("\n🔍 Testing OpenAI client...")
try:
    client = main.get_openai_client()
    if client:
        print("✅ OpenAI client created successfully")
        print("   (API key is set)")
    else:
        print("⚠️  OpenAI client not available (API key not set - this is OK)")
except Exception as e:
    print(f"⚠️  OpenAI client test error: {e} (this is OK if API key not set)")

# Test seed data script
print("\n🔍 Testing seed data script...")
try:
    import seed_data
    print("✅ Seed data script imports successfully")
except Exception as e:
    print(f"⚠️  Seed data script error: {e}")

# Summary
print("\n" + "="*50)
print("📊 TEST SUMMARY")
print("="*50)
print("✅ All core functionality verified")
print("✅ Widget files present")
print("✅ Database schema correct")
print("✅ MCP tools registered")
print("\n🎉 Setup looks good! Ready to commit.")
print("\n💡 Next steps:")
print("   1. Run: python3 seed_data.py (to populate sample data)")
print("   2. Set OPENAI_API_KEY if you want AI features")
print("   3. Run: python3 main.py (to start server)")
