#!/bin/bash
# Setup script for Saga Backend API

echo "🚀 Setting up Saga Backend API..."

# Check Python version
echo ""
echo "Checking Python version..."
python3 --version

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  .env file not found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "✅ .env created - please update API_KEY before running!"
fi

# Check directory structure
echo ""
echo "Checking directory structure..."

if [ ! -d "data/raw_news" ]; then
    echo "Creating data/raw_news directory..."
    mkdir -p data/raw_news
fi

if [ ! -d "users" ]; then
    echo "⚠️  users/ directory not found!"
    echo "Please copy your users directory from saga-graph:"
    echo "  cp -r ../saga-graph/API/users ./users"
else
    echo "✅ users/ directory exists"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Update API_KEY in .env file"
echo "  2. Ensure users/ directory has your data"
echo "  3. Start the server: python main.py"
echo "  4. Run tests: python test.py"
echo ""
