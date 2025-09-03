# Local Service Bus Testing Guide

This guide explains how to test your Azure Service Bus integration locally during development.

## Prerequisites

1. **Azure Service Bus Namespace**: You need an actual Azure Service Bus namespace (the emulator doesn't support all features)
2. **Queue Created**: Create a queue named `transactions` in your Service Bus namespace
3. **Connection String**: Get the connection string from Azure Portal

## Setup Instructions

### 1. Configure Your Service Bus Connection

Update your `local.settings.json` file with your actual Service Bus connection string:

```json
{
  "Values": {
    "ServiceBusConnection": "Endpoint=sb://YOUR-NAMESPACE.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=YOUR-KEY"
  }
}
```

### 2. Create the Service Bus Queue

In Azure Portal:
1. Go to your Service Bus namespace
2. Click "Queues" in the left menu
3. Click "+ Queue"
4. Name it `transactions`
5. Use default settings and create

### 3. Install Required Packages

Make sure you have all required packages:

```bash
pip install azure-servicebus httpx python-dotenv
```

## Testing Methods

### Method 1: Using the Test Script

We've created a comprehensive test script (`test_servicebus_local.py`) that provides multiple testing options:

#### Basic Usage

```bash
# Show setup instructions
python test_servicebus_local.py --setup

# Check if your function app is running
python test_servicebus_local.py --health-check

# Send a single test message
python test_servicebus_local.py --send-message

# Send multiple test messages
python test_servicebus_local.py --send-batch 5

# Test the debit endpoint directly (bypass Service Bus)
python test_servicebus_local.py --test-direct

# Monitor the Service Bus queue
python test_servicebus_local.py --monitor

# Run comprehensive test (combines multiple tests)
python test_servicebus_local.py
```

#### Advanced Usage

```bash
# Send message with specific transaction ID
python test_servicebus_local.py --send-message --transaction-id "10524551425999953608"

```

### Method 2: Manual Testing Steps

#### Step 1: Start Your Function App

```bash
# Navigate to your function directory
cd /home/amit.bora/Downloads/ai/payliance-azure-function

# Start the function app locally
func start --port 7071
```

You should see output like:
```
Azure Functions Core Tools
Core Tools Version: 4.x.x
Function Runtime Version: 4.x.x

Functions:
  health: [GET] http://localhost:7071/api/health
  PaylianceDebitFunction: [POST] http://localhost:7071/api/debit
  ServiceBusDebitProcessor: serviceBusTrigger
```

#### Step 2: Test the Health Endpoint

```bash
curl http://localhost:7071/api/health
```

Expected response:
```json
{"status": "healthy"}
```

#### Step 3: Test the Debit Endpoint Directly

```bash
curl -X POST http://localhost:7071/api/debit \
  -H "Content-Type: application/json" \
  -d '{"transaction_id": "test-123"}'
```

#### Step 4: Send Messages to Service Bus

Use the test script or Azure Portal:

**Using Test Script:**
```bash
python test_servicebus_local.py --send-message
```

**Using Azure Portal:**
1. Go to your Service Bus namespace
2. Click on "Queues" → "transactions"
3. Click "Service Bus Explorer"
4. Click "Send messages"
5. Set message body to:
```json
{
  "transaction_id": "portal-test-123",
  "amount": 50.00,
  "currency": "USD"
}
```

### Method 3: Using Azure Service Bus Explorer (GUI)

Install the Service Bus Explorer desktop application:
1. Download from: https://github.com/paolosalvatori/ServiceBusExplorer
2. Connect using your connection string
3. Navigate to your queue
4. Send test messages

## Expected Behavior

When everything is working correctly:

1. **Message Sent**: You send a message to the `transactions` queue
2. **Function Triggered**: The `ServiceBusDebitProcessor` function is automatically triggered
3. **Processing**: The function extracts the `transaction_id` and calls the `/debit` endpoint
4. **Logging**: You'll see detailed logs in the function app console

### Sample Log Output

```
[2025-09-03T10:30:15.123Z] Executing 'Functions.ServiceBusDebitProcessor' (Reason='', Id=abc-123)
[2025-09-03T10:30:15.124Z] [msg-456] Received Service Bus message: {"transaction_id":"test-123","amount":100.50}
[2025-09-03T10:30:15.125Z] [msg-456] Processing Service Bus message for transaction: test-123
[2025-09-03T10:30:15.126Z] [corr-789] Calling debit endpoint: http://localhost:7071/api/debit
[2025-09-03T10:30:15.250Z] ✅ [corr-789] Debit endpoint call successful for transaction test-123
[2025-09-03T10:30:15.251Z] ✅ [msg-456] Service Bus message processed successfully for transaction test-123 in 127.45ms
[2025-09-03T10:30:15.252Z] Executed 'Functions.ServiceBusDebitProcessor' (Succeeded, Id=abc-123, Duration=129ms)
```

## Troubleshooting

### Common Issues

#### 1. "ServiceBusConnection not properly configured"
- Check your `local.settings.json` has the correct connection string
- Ensure the connection string doesn't contain placeholder values

#### 2. "Cannot connect to Azure Function"
- Make sure `func start` is running
- Check the port (default: 7071)
- Verify firewall isn't blocking the port

#### 3. "Queue 'transactions' does not exist"
- Create the queue in Azure Portal
- Ensure the queue name matches exactly (case-sensitive)

#### 4. "Authentication failed"
- Verify your Service Bus connection string is correct
- Check that the access key has the required permissions

#### 5. Service Bus function not triggering
- Check that the queue name in the function matches your actual queue
- Verify the connection string name matches the one in your function (`ServiceBusConnection`)
- Ensure the function app has the Service Bus extension installed

### Debug Steps

1. **Check Function Logs**: Look at the function app console for detailed error messages
2. **Verify Queue Messages**: Use Azure Portal to see if messages are in the queue
3. **Test Direct Endpoint**: Verify the `/debit` endpoint works independently
4. **Check Network**: Ensure you can reach Azure Service Bus from your machine

### Useful Commands

```bash
# Check if your queue has messages
python test_servicebus_local.py --monitor

# Test just the HTTP endpoint
python test_servicebus_local.py --test-direct

# Send a batch of test messages
python test_servicebus_local.py --send-batch 3

# Full system test
python test_servicebus_local.py
```

## Environment Variables Reference

Make sure these are configured in your `local.settings.json`:

```json
{
  "Values": {
    "ServiceBusConnection": "Endpoint=sb://YOUR-NAMESPACE.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=YOUR-KEY",
    "FUNCTION_APP_URL": "http://localhost:7071",
    "PAYLIANCE_BASE_URL": "https://your-payliance-api-url.com",
    "PAYLIANCE_AUTH_TOKEN": "your-payliance-auth-token"
  }
}
```

## Next Steps

Once local testing is working:
1. Deploy to Azure using the provided deployment scripts
2. Update environment variables in Azure Function App settings
3. Monitor production logs and metrics
4. Set up alerts for failed message processing
