#!/usr/bin/env python3
"""
Code structure verification script.
Checks that all required components are in place before committing.
"""
import os
from pathlib import Path

print("="*60)
print("🔍 REWARDSSTRATEGIST SETUP VERIFICATION")
print("="*60)

errors = []
warnings = []

# Check required files
print("\n📁 Checking required files...")
required_files = [
    "main.py",
    "cards_widget.html",
    "deals_widget.html",
    "recommendations_widget.html",
    "seed_data.py",
    "system_prompt.txt",
    "README.md",
    "pyproject.toml"
]

for file in required_files:
    if Path(file).exists():
        print(f"  ✅ {file}")
    else:
        print(f"  ❌ {file} MISSING")
        errors.append(f"Missing file: {file}")

# Check main.py structure
print("\n🔧 Checking main.py structure...")
try:
    with open("main.py", "r") as f:
        content = f.read()
        
        # Check for required components
        checks = {
            "FastMCP import": "from fastmcp import FastMCP" in content,
            "Database initialization": "def init_db()" in content,
            "MCP instance": "mcp = FastMCP" in content,
            "OpenAI integration": "get_openai_client" in content,
            "Card management tools": "@mcp.tool()" in content and "add_card" in content,
            "Recommendation tools": "recommend_best_card" in content,
            "Deals tools": "get_deals" in content,
            "Recommendations tools": "recommend_new_cards" in content,
            "UI widgets": "@mcp.resource" in content,
            "Server startup": "mcp.run(" in content,
        }
        
        for check_name, result in checks.items():
            if result:
                print(f"  ✅ {check_name}")
            else:
                print(f"  ❌ {check_name} MISSING")
                errors.append(f"Missing component: {check_name}")
        
        # Count tools
        tool_count = content.count("@mcp.tool()")
        resource_count = content.count("@mcp.resource")
        print(f"\n  📊 Found {tool_count} MCP tools")
        print(f"  📊 Found {resource_count} MCP resources")
        
        if tool_count < 15:
            warnings.append(f"Expected more tools (found {tool_count})")
        
except Exception as e:
    errors.append(f"Error reading main.py: {e}")

# Check widget files
print("\n🎨 Checking widget files...")
widget_files = ["cards_widget.html", "deals_widget.html", "recommendations_widget.html"]
for widget in widget_files:
    try:
        with open(widget, "r") as f:
            widget_content = f.read()
            if "window.openai" in widget_content:
                print(f"  ✅ {widget} - Has OpenAI SDK integration")
            else:
                print(f"  ⚠️  {widget} - Missing OpenAI SDK integration")
                warnings.append(f"{widget} may be missing OpenAI SDK calls")
            
            if len(widget_content) < 100:
                print(f"  ⚠️  {widget} - File seems too small")
                warnings.append(f"{widget} may be incomplete")
            else:
                print(f"  ✅ {widget} - File size OK")
    except Exception as e:
        errors.append(f"Error reading {widget}: {e}")

# Check seed_data.py
print("\n🌱 Checking seed_data.py...")
try:
    with open("seed_data.py", "r") as f:
        seed_content = f.read()
        if "available_cards" in seed_content and "deals" in seed_content:
            print("  ✅ Contains seed data for cards and deals")
        else:
            warnings.append("seed_data.py may be incomplete")
except Exception as e:
    warnings.append(f"Could not verify seed_data.py: {e}")

# Check pyproject.toml
print("\n📦 Checking dependencies...")
try:
    with open("pyproject.toml", "r") as f:
        deps_content = f.read()
        required_deps = ["fastmcp", "aiosqlite", "openai"]
        for dep in required_deps:
            if dep in deps_content:
                print(f"  ✅ {dep} in dependencies")
            else:
                print(f"  ⚠️  {dep} not in dependencies")
                warnings.append(f"Missing dependency: {dep}")
except Exception as e:
    errors.append(f"Error reading pyproject.toml: {e}")

# Check for common issues
print("\n🔍 Checking for common issues...")
try:
    with open("main.py", "r") as f:
        content = f.read()
        
        # Check for hardcoded API keys
        if "sk-proj-" in content or "sk-" in content:
            print("  ⚠️  WARNING: Possible hardcoded API key found!")
            warnings.append("Hardcoded API key detected - should use environment variable")
        else:
            print("  ✅ No hardcoded API keys")
        
        # Check for proper error handling
        if "try:" in content and "except" in content:
            print("  ✅ Error handling present")
        else:
            warnings.append("Limited error handling")
        
        # Check for async/await
        if "async def" in content and "await" in content:
            print("  ✅ Async/await patterns used")
        else:
            warnings.append("May be missing async patterns")
            
except Exception as e:
    warnings.append(f"Could not perform common checks: {e}")

# Summary
print("\n" + "="*60)
print("📊 VERIFICATION SUMMARY")
print("="*60)

if errors:
    print(f"\n❌ ERRORS FOUND: {len(errors)}")
    for error in errors:
        print(f"   • {error}")
    print("\n⚠️  Please fix errors before committing!")
else:
    print("\n✅ No critical errors found!")

if warnings:
    print(f"\n⚠️  WARNINGS: {len(warnings)}")
    for warning in warnings:
        print(f"   • {warning}")
    print("\n💡 Consider addressing warnings for better code quality.")
else:
    print("\n✅ No warnings!")

print("\n" + "="*60)
if errors:
    print("❌ SETUP NOT READY - Fix errors before committing")
    exit(1)
elif warnings:
    print("⚠️  SETUP READY WITH WARNINGS - Review warnings")
    exit(0)
else:
    print("✅ SETUP VERIFIED - Ready to commit!")
    exit(0)
