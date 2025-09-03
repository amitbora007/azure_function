# Azure Service Bus Integration Setup

This document explains how to set up and use the Azure Service Bus integration for processing debit transactions.

## Overview

The application now includes a Service Bus triggered Azure Function that:
1. Listens for messages on the `transactions` Service Bus queue
2. Processes each message to extract the `transaction_id`
3. Calls the internal `/debit` endpoint for each transaction
4. Handles errors gracefully with proper logging and retry mechanisms

## Architecture

```
Service Bus Queue (transactions) → ServiceBusDebitProcessor Function → /debit endpoint → Payliance API
```

## Configuration

### Required Environment Variables

Update your `local.settings.json` (for local development) or Azure Function App settings (for production):

```json
{
  "ServiceBusConnection": "Endpoint=sb://your-namespace.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=your-key",
  "FUNCTION_APP_URL": "https://your-function-app.azurewebsites.net",
  "FUNCTION_KEY": "your-function-host-key",
  "PAYLIANCE_BASE_URL": "https://your-payliance-api.com",
  "PAYLIANCE_AUTH_TOKEN": "your-payliance-token"
}
```

### Service Bus Setup

1. **Create Service Bus Namespace**: In Azure Portal, create a Service Bus namespace
2. **Create Queue**: Create a queue named `transactions`
3. **Get Connection String**: Copy the connection string from the namespace's "Shared access policies"
4. **Configure Dead Letter Queue**: The queue should have dead letter queue enabled for failed messages

## Message Format

Messages sent to the Service Bus queue should be in JSON format:

```json
{
  "transaction_id": "your-transaction-id-here",
  "timestamp": "2023-09-03T10:30:00Z",
  "additional_data": "optional"
}
```

**Required Fields:**
- `transaction_id`: The transaction ID that exists in your database

## Error Handling

### Retry Mechanism
- Failed messages are automatically retried by Service Bus
- Maximum delivery count should be configured on the queue (recommended: 5-10)
- Failed messages after max retries go to the dead letter queue

### Logging
All operations are logged with correlation IDs for traceability:
- ✅ Success: Transaction processed successfully
- ⚠️ Warning: Non-fatal issues (e.g., validation errors)
- ❌ Error: Fatal errors that cause message failure

### Error Scenarios Handled
1. **Invalid JSON**: Message cannot be parsed as JSON
2. **Missing transaction_id**: Required field not present
3. **Database errors**: Connection or query failures
4. **API timeouts**: Payliance API not responding
5. **HTTP errors**: Network or service errors

## Monitoring

### Key Metrics to Monitor
- Message processing rate
- Error rate
- Dead letter queue length
- Processing time per message
- Database connection health

### Log Queries (Application Insights)
```kusto
// Failed Service Bus processing
traces
| where message contains "ServiceBusDebitProcessor"
| where severityLevel >= 3
| order by timestamp desc

// Processing times
traces
| where message contains "Service Bus message processed successfully"
| extend processingTime = extract(@"(\d+\.\d+)ms", 1, message)
| summarize avg(todouble(processingTime)) by bin(timestamp, 5m)
```

## Testing

### Local Testing
1. Start the Azure Functions Core Tools: `func start`
2. Send a test message to your Service Bus queue
3. Monitor the console logs for processing

### Sample Test Message
```bash
# Using Azure CLI to send test message
az servicebus message send \
  --resource-group your-rg \
  --namespace-name your-namespace \
  --queue-name transactions \
  --body '{"transaction_id": "test-123", "timestamp": "2023-09-03T10:30:00Z"}'
```

## Production Deployment

### Azure Function App Settings
Ensure these settings are configured in your Azure Function App:
- `ServiceBusConnection`: Service Bus connection string
- `FUNCTION_APP_URL`: Your function app URL
- `FUNCTION_KEY`: Function host key for internal calls
- `PAYLIANCE_BASE_URL`: Payliance API endpoint
- `PAYLIANCE_AUTH_TOKEN`: Payliance authentication token

### Security Considerations
1. Use Managed Identity when possible instead of connection strings
2. Store sensitive settings in Azure Key Vault
3. Configure proper RBAC permissions
4. Enable Application Insights for monitoring

### Scaling
- The function will automatically scale based on queue length
- Consider configuring `maxConcurrentCalls` in host.json for high throughput
- Monitor and adjust Service Bus queue settings as needed

## Troubleshooting

### Common Issues

1. **Messages not processing**
   - Check Service Bus connection string
   - Verify queue name matches configuration
   - Check function app logs

2. **High error rate**
   - Check database connectivity
   - Verify Payliance API credentials
   - Review dead letter queue messages

3. **Slow processing**
   - Monitor database performance
   - Check Payliance API response times
   - Consider adjusting timeout values

### Debug Commands
```bash
# Check function logs
func logs

# Test database connection
# (Add your database test script here)

# Test Payliance API
curl -X POST "https://your-function-app.azurewebsites.net/api/debit" \
  -H "Content-Type: application/json" \
  -d '{"transaction_id": "test-123"}'
```
