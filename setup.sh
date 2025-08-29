#!/bin/bash

# Payliance Azure Function Setup Script

set -e

echo "🔧 Setting up Payliance Azure Function Development Environment"
echo "============================================================"

# Check Python version
echo "🐍 Checking Python version..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "   Python version: $python_version"

# Check if required Python version
required_version="3.8"
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "✅ Python version is compatible"
else
    echo "❌ Python 3.8 or higher is required"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📥 Installing Python packages..."
pip install -r requirements.txt

# Check if Azure Functions Core Tools is installed
echo "🔍 Checking Azure Functions Core Tools..."
if command -v func &> /dev/null; then
    func_version=$(func --version)
    echo "✅ Azure Functions Core Tools installed: $func_version"
else
    echo "⚠️ Azure Functions Core Tools not found"
    echo "💡 Install with: npm install -g azure-functions-core-tools@4 --unsafe-perm true"
    echo "   Or download from: https://github.com/Azure/azure-functions-core-tools"
fi

# Check if Azure CLI is installed
echo "🔍 Checking Azure CLI..."
if command -v az &> /dev/null; then
    az_version=$(az --version | head -n1)
    echo "✅ Azure CLI installed: $az_version"
else
    echo "⚠️ Azure CLI not found"
    echo "💡 Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
fi

# Create .env file from template if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.template .env
    echo "⚠️ Please update .env file with your actual Payliance credentials"
fi

echo ""
echo "✅ Setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Update .env file with your Payliance credentials"
echo "2. Update local.settings.json with your configuration"
echo "3. Run the function locally: func start"
echo "4. Test with: python test_function.py"
echo ""
echo "🔗 Useful commands:"
echo "   - Start function locally: func start"
echo "   - Run tests: python test_function.py"
echo "   - Deploy to Azure: ./deploy.sh"
echo ""

# Show current directory structure
echo "📁 Project structure:"
find . -maxdepth 2 -type f -not -path "./venv/*" -not -path "./.git/*" | sort
