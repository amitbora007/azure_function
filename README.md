#  Azure Function

An Azure Function that processes  debit transactions. This function takes a transaction ID and transaction data as input and calls the  E-check Debit API.

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
   chmod +x setup.sh
   ./setup.sh

   source venv/bin/activate
   ```

2. **Configure environment variables**:
   Copy `.env.template` to `.env` and update the values:
   ```bash
   cp .env.template .env
   ```

   Edit `.env` with your actual  API credentials:
   ```
   _BASE_URL=https://your-actual--url.com
   _AUTH_TOKEN=your-actual-auth-token
   ```

3. **Run locally**:
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
  "response_data": " API response data",
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

### Deploy to Azure from system

1. **Install Azure CLI**:
  - curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
  - chmod +x deployment.sh
  - ./deployment.sh
  - Create a Storage Account from the Portal
  - ./deployment.sh

2. Add environment variables:
  Portal > Function App > Settings > Environment Variables

3. Validate variables using this command:
   az functionapp config appsettings list     --name payliance-function-app-1756466897     --resource-group payliance-rg     --output table

4. func azure functionapp publish payliance-function-app-1756466897 --python

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

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure all dependencies are in `requirements.txt`
2. **Authentication errors**: Verify `_AUTH_TOKEN` is correct
3. **Connection errors**: Check `_BASE_URL` and network connectivity
4. **Timeout errors**: Adjust timeout values if needed

### Debug Logging

Enable verbose logging by setting log level in `host.json` or through environment variables.
