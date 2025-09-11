import azure.functions as func
import json
import logging
import httpx
import os
from datetime import datetime
from typing import Optional, Dict, Any
import uuid
from database import db
from dotenv import load_dotenv
import asyncio
from enum import Enum

class ErrorType(Enum):
    """Classification of errors for retry logic"""
    TRANSIENT = "transient"
    PERMANENT = "permanent"

class DebitError(Exception):
    """Custom exception for debit processing errors"""
    def __init__(self, message: str, error_type: ErrorType, status_code: int = None):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code

# Load environment variables from .env file
load_dotenv()

app = func.FunctionApp()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service Bus connection string should be configured in Azure settings
SERVICE_BUS_CONNECTION = "ServiceBusConnection"
SERVICE_BUS_QUEUE = os.environ.get("SERVICE_BUS_QUEUE")

def classify_error(exception: Exception, status_code: int = None) -> ErrorType:
    """
    Classify errors into transient or permanent types for retry logic.

    Transient Errors (should retry):
    - Network timeouts
    - Connection errors
    - Temporary server errors (5xx)
    - Service unavailable

    Permanent Errors (should not retry):
    - Authentication errors (401, 403)
    - Bad request/data validation errors (400)
    - Resource not found (404)
    - Method not allowed (405)
    - Conflict (409)
    - Unprocessable entity (422)
    """
    # Check for timeout exceptions - always transient
    if isinstance(exception, (httpx.TimeoutException, asyncio.TimeoutError)):
        return ErrorType.TRANSIENT

    # Check for connection/network errors - always transient
    if isinstance(exception, (httpx.ConnectError, httpx.NetworkError, httpx.ConnectTimeout)):
        return ErrorType.TRANSIENT

    # Check HTTP status codes
    if status_code:
        # Server errors (5xx) - transient
        if 500 <= status_code < 600:
            return ErrorType.TRANSIENT

        # Too Many Requests (429) - transient
        if status_code == 429:
            return ErrorType.TRANSIENT

        # Client errors that indicate permanent issues
        permanent_status_codes = {400, 401, 403, 404, 405, 409, 422}
        if status_code in permanent_status_codes:
            return ErrorType.PERMANENT

    # Check for specific error messages that indicate permanent issues
    error_message = str(exception).lower()
    permanent_keywords = [
        'unauthorized', 'forbidden', 'authentication', 'invalid token',
        'bad request', 'malformed', 'invalid data', 'validation failed',
        'not found', 'conflict', 'duplicate', 'already exists'
    ]

    for keyword in permanent_keywords:
        if keyword in error_message:
            return ErrorType.PERMANENT

    # Default to transient for unknown errors to allow retry
    return ErrorType.TRANSIENT

@app.function_name(name="health")
@app.route(route="health", auth_level=func.AuthLevel.FUNCTION, methods=["GET"])
async def health_check(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "healthy"}),
        status_code=200,
        mimetype="application/json"
    )

@app.function_name(name="ServiceBusDebitProcessor")
@app.service_bus_queue_trigger(
    arg_name="msg",
    queue_name=SERVICE_BUS_QUEUE,
    connection=SERVICE_BUS_CONNECTION
)
async def service_bus_debit_processor(msg: func.ServiceBusMessage) -> None:
    """
    Azure Function triggered by Service Bus messages to process debit transactions.
    Each message from the Service Bus will trigger a call to the /debit endpoint.

    Error Handling:
    - Transient errors: Allow Service Bus retry (raise exception)
    - Permanent errors: Acknowledge message to prevent retry
    """
    message_id = str(uuid.uuid4())
    start_time = datetime.now()
    delivery_count = getattr(msg, 'delivery_count', 1)

    try:
        # Get message content
        message_body = msg.get_body().decode('utf-8')
        logger.info(f"[{message_id}] Received Service Bus message (delivery #{delivery_count}): {message_body}")

        # Parse the message body as JSON
        try:
            message_data = json.loads(message_body)
        except json.JSONDecodeError as e:
            logger.error(f"[{message_id}] Failed to parse message as JSON: {str(e)}")
            logger.error(f"[{message_id}] Raw message: {message_body}")
            # JSON parsing error is permanent - acknowledge message to prevent retry
            logger.error(f"[{message_id}] PERMANENT ERROR: Invalid JSON format - acknowledging message")
            return  # Return without raising to acknowledge message

        # Extract transaction_id from the message
        transaction_id = message_data.get('transaction_id')
        if not transaction_id:
            logger.error(f"[{message_id}] No transaction_id found in message")
            logger.error(f"[{message_id}] Message data: {message_data}")
            # Missing transaction_id is permanent - acknowledge message to prevent retry
            logger.error(f"[{message_id}] PERMANENT ERROR: Missing transaction_id - acknowledging message")
            return  # Return without raising to acknowledge message

        logger.info(f"[{message_id}] Processing Service Bus message for transaction: {transaction_id}")

        # Call the debit endpoint
        result = await call_debit_endpoint_with_error_handling(transaction_id, message_id)

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        if result['success']:
            logger.info(f"✅ [{message_id}] Service Bus message processed successfully for transaction {transaction_id} in {processing_time:.2f}ms")
        else:
            # Check error type from the result
            error_type = result.get('error_type', ErrorType.TRANSIENT)
            error_message = result.get('error_message', 'Unknown error')

            logger.error(f"❌ [{message_id}] Failed to process Service Bus message for transaction {transaction_id} in {processing_time:.2f}ms")
            logger.error(f"[{message_id}] Error type: {error_type.value}, Message: {error_message}")

            if error_type == ErrorType.PERMANENT:
                logger.error(f"[{message_id}] PERMANENT ERROR detected - acknowledging message to prevent retry")
                return  # Return without raising to acknowledge message
            else:
                logger.error(f"[{message_id}] TRANSIENT ERROR detected - allowing Service Bus retry")
                raise DebitError(f"Transient error processing debit transaction {transaction_id}: {error_message}", ErrorType.TRANSIENT)

    except DebitError as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"❌ [{message_id}] Debit error processing Service Bus message: {str(e)}")
        logger.error(f"[{message_id}] Processing time: {processing_time:.2f}ms")
        logger.error(f"[{message_id}] Error type: {e.error_type.value}")

        # Log message properties for debugging
        try:
            logger.error(f"[{message_id}] Message ID: {msg.message_id}")
            logger.error(f"[{message_id}] Delivery count: {delivery_count}")
            logger.error(f"[{message_id}] Enqueued time: {msg.enqueued_time_utc}")
        except Exception as prop_error:
            logger.error(f"[{message_id}] Error logging message properties: {str(prop_error)}")

        # Handle based on error type
        if e.error_type == ErrorType.PERMANENT:
            logger.error(f"[{message_id}] PERMANENT ERROR - acknowledging message to prevent retry")
            return  # Return without raising to acknowledge message
        else:
            logger.error(f"[{message_id}] TRANSIENT ERROR - allowing Service Bus retry")
            raise  # Re-raise to trigger Service Bus retry mechanism

    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"❌ [{message_id}] Unexpected error processing Service Bus message: {str(e)}")
        logger.error(f"[{message_id}] Processing time: {processing_time:.2f}ms")

        # Log message properties for debugging
        try:
            logger.error(f"[{message_id}] Message ID: {msg.message_id}")
            logger.error(f"[{message_id}] Delivery count: {delivery_count}")
            logger.error(f"[{message_id}] Enqueued time: {msg.enqueued_time_utc}")
        except Exception as prop_error:
            logger.error(f"[{message_id}] Error logging message properties: {str(prop_error)}")

        # Classify unknown errors and handle accordingly
        error_type = classify_error(e)
        logger.error(f"[{message_id}] Classified as: {error_type.value}")

        if error_type == ErrorType.PERMANENT:
            logger.error(f"[{message_id}] PERMANENT ERROR - acknowledging message to prevent retry")
            return  # Return without raising to acknowledge message
        else:
            logger.error(f"[{message_id}] TRANSIENT ERROR - allowing Service Bus retry")
            raise  # Re-raise to trigger Service Bus retry mechanism

async def call_debit_endpoint_with_error_handling(transaction_id: str, correlation_id: str = None) -> Dict[str, Any]:
    """
    Helper function to call the debit endpoint internally with proper error classification.

    Args:
        transaction_id: The transaction ID to process
        correlation_id: Optional correlation ID for logging

    Returns:
        Dict containing success status, error_type, and error_message
    """
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    try:
        # Get environment variables for internal call
        function_app_url = os.environ.get('FUNCTION_APP_URL', 'http://localhost:7071')
        function_key = os.environ.get('FUNCTION_KEY', '')

        # Prepare the request payload
        payload = {"transaction_id": transaction_id}

        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'X-Correlation-ID': correlation_id
        }

        # Add function key if available (for production)
        if function_key:
            headers['x-functions-key'] = function_key

        # Construct the URL
        debit_url = f"{function_app_url}/api/debit"

        logger.info(f"[{correlation_id}] Calling debit endpoint: {debit_url}")

        # Make the HTTP call with timeout and retry logic
        timeout = httpx.Timeout(timeout=60.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            response = await client.post(debit_url, headers=headers, json=payload)

        if response.status_code == 200:
            logger.info(f"✅ [{correlation_id}] Debit endpoint call successful for transaction {transaction_id}")
            try:
                response_data = response.json()
                if response_data.get('success'):
                    return {"success": True}
                else:
                    error_msg = f"Debit endpoint returned success=false: {response_data}"
                    logger.warning(f"[{correlation_id}] {error_msg}")
                    # Classify based on response content
                    error_type = classify_error(Exception(error_msg), response.status_code)
                    return {
                        "success": False,
                        "error_type": error_type,
                        "error_message": error_msg
                    }
            except json.JSONDecodeError:
                logger.warning(f"[{correlation_id}] Could not parse debit endpoint response as JSON")
                return {"success": True}  # Assume success if we got 200 but couldn't parse
        else:
            error_msg = f"Debit endpoint call failed with status {response.status_code}: {response.text}"
            logger.error(f"❌ [{correlation_id}] {error_msg}")
            error_type = classify_error(Exception(error_msg), response.status_code)
            return {
                "success": False,
                "error_type": error_type,
                "error_message": error_msg
            }

    except (httpx.TimeoutException, asyncio.TimeoutError) as e:
        error_msg = f"Timeout calling debit endpoint for transaction {transaction_id}: {str(e)}"
        logger.error(f"❌ [{correlation_id}] {error_msg}")
        return {
            "success": False,
            "error_type": ErrorType.TRANSIENT,
            "error_message": error_msg
        }
    except (httpx.ConnectError, httpx.NetworkError, httpx.ConnectTimeout) as e:
        error_msg = f"Network error calling debit endpoint for transaction {transaction_id}: {str(e)}"
        logger.error(f"❌ [{correlation_id}] {error_msg}")
        return {
            "success": False,
            "error_type": ErrorType.TRANSIENT,
            "error_message": error_msg
        }
    except httpx.RequestError as e:
        error_msg = f"Request error calling debit endpoint for transaction {transaction_id}: {str(e)}"
        logger.error(f"❌ [{correlation_id}] {error_msg}")
        error_type = classify_error(e)
        return {
            "success": False,
            "error_type": error_type,
            "error_message": error_msg
        }
    except Exception as e:
        error_msg = f"Unexpected error calling debit endpoint for transaction {transaction_id}: {str(e)}"
        logger.error(f"❌ [{correlation_id}] {error_msg}")
        error_type = classify_error(e)
        return {
            "success": False,
            "error_type": error_type,
            "error_message": error_msg
        }

async def call_debit_endpoint(transaction_id: str, correlation_id: str = None) -> bool:
    """
    Helper function to call the debit endpoint internally (backward compatibility).

    Args:
        transaction_id: The transaction ID to process
        correlation_id: Optional correlation ID for logging

    Returns:
        bool: True if successful, False otherwise
    """
    result = await call_debit_endpoint_with_error_handling(transaction_id, correlation_id)
    return result['success']

@app.function_name(name="PaylianceDebitFunction")
@app.route(route="debit", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
async def payliance_debit_function(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function to process Payliance debit transactions

    Expects JSON body with:
    {
        "transaction_id": "string"
    }
    """

    request_id = str(uuid.uuid4())
    start_time = datetime.now()

    try:
        # Initialize database connection if not already done
        if not db.connection_pool:
            logger.info(f"[{request_id}] Initializing database connection...")
            db_initialized = await db.initialize_pool(min_size=1, max_size=3)
            if not db_initialized:
                logger.warning(f"[{request_id}] Database initialization failed")

        # Get request body
        req_body = req.get_json()

        if not req_body:
            logger.error(f"[{request_id}] No JSON body provided")
            return func.HttpResponse(
                json.dumps({
                    "success": False,
                    "error": "No JSON body provided",
                    "request_id": request_id
                }),
                status_code=400,
                mimetype="application/json"
            )

        # Extract transaction_id
        transaction_id = req_body.get('transaction_id')

        if not transaction_id:
            logger.error(f"[{request_id}] transaction_id is required")
            return func.HttpResponse(
                json.dumps({
                    "success": False,
                    "error": "transaction_id is required",
                    "request_id": request_id
                }),
                status_code=400,
                mimetype="application/json"
            )

        logger.info(f"[{request_id}] Processing debit transaction for ID: {transaction_id}")

        # Get environment variables
        payliance_base_url = os.environ.get('PAYLIANCE_BASE_URL')
        auth_token = os.environ.get('PAYLIANCE_AUTH_TOKEN')

        # Debug logging for environment variables
        logger.info(f"[{request_id}] PAYLIANCE_BASE_URL: {payliance_base_url}")
        logger.info(f"[{request_id}] PAYLIANCE_AUTH_TOKEN configured: {bool(auth_token)}")

        if not auth_token:
            logger.error(f"[{request_id}] PAYLIANCE_AUTH_TOKEN not configured")
            return func.HttpResponse(
                json.dumps({
                    "success": False,
                    "error": "PAYLIANCE_AUTH_TOKEN not configured",
                    "request_id": request_id
                }),
                status_code=500,
                mimetype="application/json"
            )

        if not payliance_base_url:
            logger.error(f"[{request_id}] PAYLIANCE_BASE_URL not configured")
            return func.HttpResponse(
                json.dumps({
                    "success": False,
                    "error": "PAYLIANCE_BASE_URL not configured",
                    "request_id": request_id
                }),
                status_code=500,
                mimetype="application/json"
            )

        # Fetch transaction details from database
        transaction_data = None
        if db.connection_pool:
            try:
                logger.info(f"[{request_id}] Fetching transaction details from database for ID: {transaction_id}")
                transaction_data = await db.get_transaction_by_id(transaction_id)
                if transaction_data.get('transaction_id'):
                    logger.warning(f"[{request_id}] Transaction already sent to Payliance")
                    return func.HttpResponse(
                        json.dumps({
                            "success": False,
                            "error": "Transaction already sent to Payliance",
                            "request_id": request_id
                        }),
                        status_code=200,
                        mimetype="application/json"
                    )
                elif not transaction_data.get('transaction_id'):
                    logger.info(f"[{request_id}] Database lookup successful - found transaction data")
                else:
                    logger.warning(f"[{request_id}] Transaction not found in database")
            except Exception as e:
                logger.error(f"[{request_id}] Database lookup failed: {str(e)}")
        else:
            logger.warning(f"[{request_id}] Database connection not available")

        # Use database data if available
        if not transaction_data.get('transaction_id'):
            # Parse datetime from database
            stamp = transaction_data.get('stamp')
            if isinstance(stamp, str):
                try:
                    stamp = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
                except ValueError:
                    logger.warning(f"[{request_id}] Invalid datetime format for stamp, using current time")
                    stamp = datetime.now()
            elif not stamp:
                stamp = datetime.now()

            # Build transaction payload with database data
            transaction_payload = {
                "uniqueTranId": transaction_id,
                "routing": "121000358",
                "accountNumber": "5428610017522",
                "checkAmount": float(transaction_data.get('total_amount', 0)),
                "secCode": transaction_data.get('ach_trans_type', 'POS'),
                "posTransactionDate": stamp.isoformat() + "Z",
                "posTerminalId": str(transaction_data.get('terminal_id', '')),
                "posTransactionSerialNumber": transaction_data.get('serial_number', ''),
                "posAuthorizationCode": str(transaction_data.get('approval_code', '')),
                "lastName": transaction_data.get('lname', ''),
                "firstName": transaction_data.get('fname', ''),
                "address1": transaction_data.get('address1', ''),
                "city": transaction_data.get('city', ''),
                "state": transaction_data.get('state', ''),
                "zip": transaction_data.get('zip', ''),
                "phone": transaction_data.get('home_phone') or transaction_data.get('mobile_phone', ''),
                "checkDate": stamp.isoformat() + "Z",
                "customDescriptor": transaction_data.get('ach_statement_id', ''),
                # Additional fields that may be required by Payliance API
                "posCardTransactionTypeCode": "01",
                "posTerminalLocationAddress": transaction_data.get('merchant_address', ''),
                "posTerminalCity": transaction_data.get('merchant_city', ''),
                "posTerminalState": transaction_data.get('merchant_state', ''),
                "posReferenceInfo1": transaction_data.get('consumer_id', ''),
                "posReferenceInfo2": "00",
                "accountType": "Personal Checking",
                "address2": transaction_data.get('address2', ''),
                "isSameDay": False,
                "futureDate": "",
                "microEntry": False,
                "convenienceFee": False,
                "convenienceFeeAmount": 0
            }

        # Prepare headers
        url = f"{payliance_base_url}/api/v1/echeck/debit"
        headers = {
            'accept': 'text/plain',
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json',
            'X-Request-ID': request_id
        }

        logger.info(f"[{request_id}] Calling Payliance API: {url}")

        # Make HTTP call to Payliance API
        timeout = httpx.Timeout(timeout=30.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout, verify=True) as client:
            response = await client.post(url, headers=headers, json=transaction_payload)

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        # Process response
        if response.status_code == 200:
            logger.info(f"✅ [{request_id}] SUCCESS: Transaction {transaction_id} processed in {processing_time:.2f}ms")

            # Extract AuthorizationId from response and update database
            try:
                response_data = json.loads(response.text)
                authorization_id = response_data.get('AuthorizationId')
                validation_code = response_data.get('ValidationCode')
                validation_message = response_data.get('message')

                if validation_code != 1:
                    logger.warning(f"[{request_id}] Received ValidationCode ({validation_code}) with message {validation_message} ")
                elif authorization_id and db.connection_pool:
                    # Update the payliance auth code in database
                    update_success = await db.insert_transaction_event(
                        transaction_id=transaction_id,
                        settled_log_id=datetime.now().strftime('%y%m%d%H'),
                        created_by=9998,
                        payliance_auth_id=authorization_id
                    )

                    if update_success:
                        logger.info(f"[{request_id}] Database updated with AuthorizationId: {authorization_id}")
                    else:
                        logger.warning(f"[{request_id}] Failed to update database with AuthorizationId: {authorization_id}")
                elif not authorization_id:
                    logger.warning(f"[{request_id}] No AuthorizationId found in response")
                elif not db.connection_pool:
                    logger.warning(f"[{request_id}] Database connection not available for AuthorizationId update")

            except json.JSONDecodeError:
                logger.warning(f"[{request_id}] Response is not valid JSON, cannot extract AuthorizationId")
            except Exception as e:
                logger.error(f"[{request_id}] Error updating AuthorizationId in database: {str(e)}")

            return func.HttpResponse(
                json.dumps({
                    "success": True,
                    "status_code": response.status_code,
                    "response_data": response.text,
                    "transaction_id": transaction_id,
                    "request_id": request_id,
                    "processing_time_ms": processing_time,
                }),
                status_code=200,
                mimetype="application/json"
            )
        else:
            # Classify error based on status code and response
            error_type = classify_error(Exception(f"HTTP {response.status_code}"), response.status_code)
            error_msg = f"API ERROR: Transaction {transaction_id} failed with status {response.status_code}"

            logger.warning(f"⚠️ [{request_id}] {error_msg}")
            logger.warning(f"[{request_id}] Error classified as: {error_type.value}")
            logger.warning(f"[{request_id}] Response: {response.text}")

            # For non-200 responses, raise appropriate exception to trigger retry logic
            if error_type == ErrorType.TRANSIENT:
                raise DebitError(f"{error_msg}: {response.text}", ErrorType.TRANSIENT, response.status_code)
            else:
                raise DebitError(f"{error_msg}: {response.text}", ErrorType.PERMANENT, response.status_code)

    except DebitError as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"❌ [{request_id}] DEBIT ERROR for transaction {transaction_id}: {str(e)}")
        logger.error(f"[{request_id}] Error type: {e.error_type.value}")

        # Return appropriate status code based on error type
        if e.error_type == ErrorType.PERMANENT:
            status_code = e.status_code or 400
        else:
            status_code = e.status_code or 500

        return func.HttpResponse(
            json.dumps({
                "success": False,
                "error": str(e),
                "error_type": e.error_type.value,
                "transaction_id": transaction_id,
                "request_id": request_id,
                "processing_time_ms": processing_time
            }),
            status_code=status_code,
            mimetype="application/json"
        )

    except (httpx.TimeoutException, asyncio.TimeoutError) as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"❌ [{request_id}] TIMEOUT ERROR for transaction {transaction_id}: {str(e)}")
        logger.error(f"[{request_id}] Error classified as: {ErrorType.TRANSIENT.value}")
        return func.HttpResponse(
            json.dumps({
                "success": False,
                "error": "Request timeout - Payliance API did not respond within 30 seconds",
                "error_type": ErrorType.TRANSIENT.value,
                "transaction_id": transaction_id,
                "request_id": request_id,
                "processing_time_ms": processing_time
            }),
            status_code=408,
            mimetype="application/json"
        )

    except httpx.HTTPStatusError as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        error_type = classify_error(e, getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None)
        logger.error(f"❌ [{request_id}] HTTP ERROR for transaction {transaction_id}: {str(e)}")
        logger.error(f"[{request_id}] Error classified as: {error_type.value}")

        status_code = getattr(e.response, 'status_code', 500) if hasattr(e, 'response') else 500
        return func.HttpResponse(
            json.dumps({
                "success": False,
                "error": f"HTTP error from Payliance API: {str(e)}",
                "error_type": error_type.value,
                "transaction_id": transaction_id,
                "request_id": request_id,
                "processing_time_ms": processing_time
            }),
            status_code=status_code,
            mimetype="application/json"
        )

    except (httpx.ConnectError, httpx.NetworkError, httpx.ConnectTimeout) as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"❌ [{request_id}] NETWORK ERROR for transaction {transaction_id}: {str(e)}")
        logger.error(f"[{request_id}] Error classified as: {ErrorType.TRANSIENT.value}")
        return func.HttpResponse(
            json.dumps({
                "success": False,
                "error": f"Network error connecting to Payliance API: {str(e)}",
                "error_type": ErrorType.TRANSIENT.value,
                "transaction_id": transaction_id,
                "request_id": request_id,
                "processing_time_ms": processing_time
            }),
            status_code=503,
            mimetype="application/json"
        )

    except httpx.RequestError as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        error_type = classify_error(e)
        logger.error(f"❌ [{request_id}] REQUEST ERROR for transaction {transaction_id}: {str(e)}")
        logger.error(f"[{request_id}] Error classified as: {error_type.value}")

        status_code = 500 if error_type == ErrorType.TRANSIENT else 400
        return func.HttpResponse(
            json.dumps({
                "success": False,
                "error": f"Failed to call Payliance API: {str(e)}",
                "error_type": error_type.value,
                "transaction_id": transaction_id,
                "request_id": request_id,
                "processing_time_ms": processing_time
            }),
            status_code=status_code,
            mimetype="application/json"
        )

    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        error_type = classify_error(e)
        logger.error(f"❌ [{request_id}] UNEXPECTED ERROR for transaction {transaction_id}: {str(e)}")
        logger.error(f"[{request_id}] Error classified as: {error_type.value}")

        status_code = 500 if error_type == ErrorType.TRANSIENT else 400
        return func.HttpResponse(
            json.dumps({
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_type": error_type.value,
                "transaction_id": transaction_id,
                "request_id": request_id,
                "processing_time_ms": processing_time
            }),
            status_code=status_code,
            mimetype="application/json"
        )
