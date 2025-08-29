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

# Load environment variables from .env file
load_dotenv()

app = func.FunctionApp()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.function_name(name="health")
@app.route(route="health", auth_level=func.AuthLevel.FUNCTION, methods=["GET"])
async def health_check(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "healthy"}),
        status_code=200,
        mimetype="application/json"
    )

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
                if transaction_data:
                    logger.info(f"[{request_id}] Database lookup successful - found transaction data")
                else:
                    logger.warning(f"[{request_id}] Transaction not found in database")
            except Exception as e:
                logger.error(f"[{request_id}] Database lookup failed: {str(e)}")
        else:
            logger.warning(f"[{request_id}] Database connection not available")

        # Use database data if available, otherwise use fallback data
        if transaction_data:
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
                "checkNumber": "",
                "posCardTransactionTypeCode": "01",
                "posTerminalLocationAddress": transaction_data.get('merchant_address', ''),
                "posTerminalCity": transaction_data.get('merchant_city', ''),
                "posTerminalState": transaction_data.get('merchant_state', ''),
                "posReferenceInfo1": transaction_data.get('consumer_id', ''),
                "posReferenceInfo2": "00",
                "originalTranId": "",
                "accountType": "Personal Checking",
                "companyName": "",
                "address2": transaction_data.get('address2', ''),
                "opt1": "",
                "opt2": "",
                "opt3": "",
                "opt4": "",
                "opt5": "",
                "opt6": "",
                "micrData": "",
                "webType": "",
                "origSecCode": "",
                "imageF": "",
                "imageB": "",
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
                    logger.warning(f"[{request_id}] ValidationCode ({validation_code}) indicates {validation_message} ")
                elif authorization_id and db.connection_pool:
                    # Update the payliance auth code in database
                    update_success = await db.update_payliance_authcode(transaction_id, authorization_id)
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
                    "database_used": transaction_data is not None
                }),
                status_code=200,
                mimetype="application/json"
            )
        else:
            logger.warning(f"⚠️ [{request_id}] API ERROR: Transaction {transaction_id} failed with status {response.status_code}")
            return func.HttpResponse(
                json.dumps({
                    "success": False,
                    "status_code": response.status_code,
                    "error_message": response.text,
                    "transaction_id": transaction_id,
                    "request_id": request_id,
                    "processing_time_ms": processing_time
                }),
                status_code=response.status_code,
                mimetype="application/json"
            )

    except httpx.TimeoutException as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"❌ [{request_id}] TIMEOUT ERROR for transaction {transaction_id}: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "success": False,
                "error": "Request timeout - Payliance API did not respond within 30 seconds",
                "transaction_id": transaction_id,
                "request_id": request_id,
                "processing_time_ms": processing_time
            }),
            status_code=408,
            mimetype="application/json"
        )

    except httpx.HTTPStatusError as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"❌ [{request_id}] HTTP ERROR for transaction {transaction_id}: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "success": False,
                "error": f"HTTP error from Payliance API: {str(e)}",
                "transaction_id": transaction_id,
                "request_id": request_id,
                "processing_time_ms": processing_time
            }),
            status_code=500,
            mimetype="application/json"
        )

    except httpx.RequestError as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"❌ [{request_id}] REQUEST ERROR for transaction {transaction_id}: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "success": False,
                "error": f"Failed to call Payliance API: {str(e)}",
                "transaction_id": transaction_id,
                "request_id": request_id,
                "processing_time_ms": processing_time
            }),
            status_code=500,
            mimetype="application/json"
        )

    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(f"❌ [{request_id}] UNEXPECTED ERROR for transaction {transaction_id}: {str(e)}")
        return func.HttpResponse(
            json.dumps({
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "transaction_id": transaction_id,
                "request_id": request_id,
                "processing_time_ms": processing_time
            }),
            status_code=500,
            mimetype="application/json"
        )
