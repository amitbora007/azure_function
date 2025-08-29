# Payliance Azure Function

An Azure Function that processes Payliance debit transactions. This function takes a transaction ID and transaction data as input and calls the Payliance E-check Debit API.

## Features

- **Async Processing**: Built with async/await for optimal performance
- **Error Handling**: Comprehensive error handling with detailed logging
- **Request Tracking**: Each request gets a unique request ID for tracking
- **Timeout Management**: Configurable timeouts for external API calls
- **Environment Configuration**: Uses environment variables for configuration

## Setup

### Prerequisites

- Python 3.8 or higher
- Azure Functions Core Tools
    - ubuntu
        1. curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg

        2. sudo mv microsoft.gpg /etc/apt/trusted.gpg.d/microsoft.gpg

        3. sudo sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/microsoft-ubuntu-$(lsb_release -cs)-prod $(lsb_release -cs) main" > /etc/apt/sources.list.d/dotnetdev.list'

        4. apt-get update

        5. apt-get install azure-functions-core-tools-4

        6. curl http://localhost:7071/api/health

- Azure subscription (for deployment)

### Local Development

1. **Install dependencies**:
   ```bash
   pip3 install -r requirements.txt
   source venv/bin/activate
   ```

2. **Configure environment variables**:
   Copy `.env.template` to `.env` and update the values:
   ```bash
   cp .env.template .env
   ```

   Edit `.env` with your actual Payliance API credentials:
   ```
   PAYLIANCE_BASE_URL=https://your-actual-payliance-url.com
   PAYLIANCE_AUTH_TOKEN=your-actual-auth-token
   ```

3. **Update local.settings.json**:
   Update the `local.settings.json` file with your configuration:
   ```json
   {
     "IsEncrypted": false,
     "Values": {
       "AzureWebJobsStorage": "UseDevelopmentStorage=true",
       "FUNCTIONS_WORKER_RUNTIME": "python",
       "PAYLIANCE_BASE_URL": "https://your-payliance-base-url.com",
       "PAYLIANCE_AUTH_TOKEN": "your-payliance-auth-token-here"
     }
   }
   ```

4. **Run locally**:
   ```bash
   func start
   ```

## API Usage

### Endpoint
- **Method**: POST
- **Path**: `/api/debit`
- **Authentication**: Function key required

### Request Body

```json
{
  "transaction_id": "TXN123456"
}
```

### Response

#### Success Response (200)
```json
{
  "success": true,
  "status_code": 200,
  "response_data": "Payliance API response data",
  "transaction_id": "TXN123456",
  "request_id": "uuid-here",
  "processing_time_ms": 1250.5
}
```

#### Error Response (4xx/5xx)
```json
{
  "success": false,
  "status_code": 400,
  "error_message": "Error description",
  "transaction_id": "TXN123456",
  "request_id": "uuid-here",
  "processing_time_ms": 150.2
}
```

## Deployment

### Deploy to Azure

1. **Create Azure Function App**:
   ```bash
   az functionapp create --resource-group myResourceGroup \
     --consumption-plan-location westus2 \
     --runtime python \
     --runtime-version 3.9 \
     --functions-version 4 \
     --name myFunctionApp \
     --storage-account mystorageaccount
   ```

2. **Deploy the function**:
   ```bash
   func azure functionapp publish myFunctionApp
   ```

3. **Configure environment variables** in Azure Portal:
   - Go to your Function App in Azure Portal
   - Navigate to Configuration > Application settings
   - Add the following settings:
     - `PAYLIANCE_BASE_URL`
     - `PAYLIANCE_AUTH_TOKEN`

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PAYLIANCE_BASE_URL` | Base URL for Payliance API | Yes |
| `PAYLIANCE_AUTH_TOKEN` | Bearer token for Payliance API authentication | Yes |
| `AzureWebJobsStorage` | Azure Storage connection string | Yes |
| `FUNCTIONS_WORKER_RUNTIME` | Function runtime (should be "python") | Yes |

### Default Values

The function uses the following default values:
- **Routing Number**: `121000358`
- **Account Number**: `5428610017522`
- **SEC Code**: `POS` (if not provided)
- **Account Type**: `Personal Checking`
- **Request Timeout**: 30 seconds
- **Connection Timeout**: 10 seconds

## Logging

The function provides comprehensive logging including:
- Request processing start/end
- API call details
- Error conditions
- Processing time metrics
- Request IDs for correlation

Logs are available in:
- Local development: Console output
- Azure: Application Insights and Function App logs

## Error Handling

The function handles various error scenarios:
- **Missing required fields**: Returns 400 with descriptive error
- **API timeouts**: Returns 408 with timeout message
- **HTTP errors**: Returns appropriate status code with error details
- **Network errors**: Returns 500 with connection error details
- **Unexpected errors**: Returns 500 with generic error message

## Testing

### Local Testing with curl

```bash
curl -X POST "http://localhost:7071/api/debit" \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "TEST123"
  }'
```

## Security Considerations

- Store sensitive configuration (API tokens) in Azure Key Vault for production
- Use managed identity for Azure resource access
- Enable authentication/authorization on the Function App
- Implement IP restrictions if needed
- Monitor and alert on function executions

## Performance

- Function uses async HTTP client for optimal performance
- Includes connection pooling and timeout configuration
- Tracks processing time for monitoring
- Designed for horizontal scaling in Azure

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure all dependencies are in `requirements.txt`
2. **Authentication errors**: Verify `PAYLIANCE_AUTH_TOKEN` is correct
3. **Connection errors**: Check `PAYLIANCE_BASE_URL` and network connectivity
4. **Timeout errors**: Adjust timeout values if needed

### Debug Logging

Enable verbose logging by setting log level in `host.json` or through environment variables.
