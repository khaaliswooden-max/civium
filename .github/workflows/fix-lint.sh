#!/bin/bash
# fix-lint.sh - Automatically fix common linting issues in Civium

set -e

echo "🔧 Civium Lint Fixer"
echo "===================="
echo ""

# Check if ruff is installed
if ! command -v ruff &> /dev/null; then
    echo "❌ Ruff not found. Installing..."
    pip install ruff
fi

# Check if running in correct directory
if [ ! -d "services" ] && [ ! -d "shared" ]; then
    echo "⚠️  Warning: Expected to find 'services' or 'shared' directories."
    echo "   Make sure you're running this from the project root."
    echo ""
fi

echo "📝 Step 1: Auto-fixing with Ruff..."
echo "-----------------------------------"
ruff check . --fix --select=I,F401,UP || true
echo "✅ Basic fixes applied"
echo ""

echo "📝 Step 2: Formatting with Ruff..."
echo "-----------------------------------"
ruff format . || true
echo "✅ Code formatted"
echo ""

echo "📝 Step 3: Checking for remaining issues..."
echo "-------------------------------------------"
ruff check . --output-format=github || true
echo ""

echo "📝 Step 4: Type checking with mypy (informational)..."
echo "-----------------------------------------------------"
if command -v mypy &> /dev/null; then
    mypy services/ shared/ --ignore-missing-imports --no-strict-optional || true
else
    echo "⚠️  mypy not installed. Skipping type check."
    echo "   Install with: pip install mypy"
fi
echo ""

echo "✅ Lint fixing complete!"
echo ""
echo "💡 Next steps:"
echo "   1. Review the changes: git diff"
echo "   2. Fix any remaining issues manually"
echo "   3. Run tests: pytest tests/"
echo "   4. Commit: git add . && git commit -m 'fix: resolve linting issues'"
echo "   5. Push: git push"
