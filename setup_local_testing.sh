#!/bin/bash

# Local Service Bus Testing Setup Script
# This script helps you set up and test your Service Bus integration locally

set -e

echo "🚀 Azure Service Bus Local Testing Setup"
echo "======================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "function_app.py" ]; then
    print_error "Please run this script from the function app directory"
    exit 1
fi

print_status "Checking prerequisites..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed"
    exit 1
fi

# Check if Azure Functions Core Tools is installed
if ! command -v func &> /dev/null; then
    print_warning "Azure Functions Core Tools not found"
    echo "Install it from: https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local"
    echo "Or run: npm install -g azure-functions-core-tools@4 --unsafe-perm true"
    exit 1
fi

print_status "Installing Python dependencies..."

# Install required packages
pip3 install -r requirements.txt
pip3 install azure-servicebus httpx python-dotenv

print_status "Checking configuration..."

# Check if local.settings.json exists
if [ ! -f "local.settings.json" ]; then
    print_error "local.settings.json not found"
    echo "Please create it based on the template in the documentation"
    exit 1
fi

# Check if Service Bus connection is configured
if grep -q "your-servicebus-namespace" local.settings.json; then
    print_warning "Service Bus connection string needs to be updated in local.settings.json"
    echo "Replace the placeholder with your actual Service Bus connection string"
fi

print_status "Starting function app in background..."

# Kill any existing func processes
pkill -f "func start" || true

# Start the function app in background
nohup func start --port 7071 > func.log 2>&1 &
FUNC_PID=$!

echo "Function app PID: $FUNC_PID"
sleep 5

# Check if function app started successfully
if ! curl -s http://localhost:7071/api/health > /dev/null; then
    print_error "Function app failed to start"
    echo "Check func.log for details:"
    tail -n 20 func.log
    exit 1
fi

print_status "Function app started successfully!"

echo ""
echo "🧪 Now you can test your Service Bus integration:"
echo ""
echo "# Test the health endpoint"
echo "curl http://localhost:7071/api/health"
echo ""
echo "# Send a test message to Service Bus"
echo "python3 test_servicebus_local.py --send-message"
echo ""
echo "# Test the debit endpoint directly"
echo "python3 test_servicebus_local.py --test-direct"
echo ""
echo "# Run comprehensive tests"
echo "python3 test_servicebus_local.py"
echo ""
echo "# Monitor the Service Bus queue"
echo "python3 test_servicebus_local.py --monitor"
echo ""

echo "📋 Useful commands:"
echo "- View function logs: tail -f func.log"
echo "- Stop function app: kill $FUNC_PID"
echo "- View this help: python3 test_servicebus_local.py --setup"
echo ""

# Save PID for easy cleanup
echo $FUNC_PID > func.pid
print_status "Function app PID saved to func.pid"

echo "🎉 Setup complete! Your function app is running on http://localhost:7071"
