#!/usr/bin/env python3
"""
Test script for Azure Service Bus integration in local development environment.

This script allows you to:
1. Send test messages to Azure Service Bus queue
2. Test the Service Bus triggered function locally
3. Monitor message processing and errors

Usage:
    python test_servicebus_local.py --send-message
    python test_servicebus_local.py --send-batch 5
    python test_servicebus_local.py --monitor
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Optional
import argparse

try:
    from azure.servicebus import ServiceBusClient, ServiceBusMessage
    from azure.servicebus.exceptions import ServiceBusError
except ImportError:
    print("❌ azure-servicebus package not installed. Run: pip install azure-servicebus")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("❌ httpx package not installed. Run: pip install httpx")
    sys.exit(1)

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ServiceBusLocalTester:
    def __init__(self):
        self.connection_string = os.environ.get('ServiceBusConnection')
        self.queue_name = os.environ.get('SERVICE_BUS_QUEUE')
        self.function_url = os.environ.get('FUNCTION_APP_URL', 'http://localhost:7071')

        if not self.connection_string or 'your-servicebus-namespace' in self.connection_string:
            logger.error("❌ ServiceBusConnection not properly configured in environment variables")
            logger.info("Please update your local.settings.json or .env file with a valid Service Bus connection string")
            sys.exit(1)

    def send_test_message(self, transaction_id: Optional[str] = None) -> bool:
        """Send a test message to the Service Bus queue"""
        if not transaction_id:

            message_data = {
                "transaction_id": "1234567",
                "timestamp": datetime.now().isoformat(),
                "test": True
            }
        else:
            message_data = {
                "transaction_id": transaction_id,
                "timestamp": datetime.now().isoformat(),
                "test": True
            }

        try:
            with ServiceBusClient.from_connection_string(self.connection_string) as client:
                sender = client.get_queue_sender(queue_name=self.queue_name)
                with sender:
                    message = ServiceBusMessage(json.dumps(message_data))
                    sender.send_messages(message)
                    logger.info(f"✅ Sent test message for transaction: {transaction_id}")
                    logger.info(f"   Message data: {json.dumps(message_data, indent=2)}")
                    return True
        except ServiceBusError as e:
            logger.error(f"❌ Service Bus error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error: {str(e)}")
            return False

    async def check_function_health(self) -> bool:
        """Check if the Azure Function is running"""
        url = f"{self.function_url}/api/health"

        try:
            timeout = httpx.Timeout(timeout=10.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    logger.info(f"✅ Azure Function is healthy")
                    return True
                else:
                    logger.warning(f"⚠️ Health check returned: {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"❌ Cannot connect to Azure Function: {str(e)}")
            logger.info(f"   Make sure your function app is running on {self.function_url}")
            return False

    def monitor_queue(self, duration: int = 30) -> None:
        """Monitor the Service Bus queue for messages"""
        logger.info(f"👀 Monitoring Service Bus queue '{self.queue_name}' for {duration} seconds...")

        try:
            with ServiceBusClient.from_connection_string(self.connection_string) as client:
                receiver = client.get_queue_receiver(queue_name=self.queue_name)
                with receiver:
                    start_time = time.time()
                    message_count = 0

                    while time.time() - start_time < duration:
                        try:
                            # Peek messages without consuming them
                            messages = receiver.peek_messages(max_message_count=10)
                            current_count = len(messages)

                            if current_count != message_count:
                                logger.info(f"📊 Queue has {current_count} pending messages")
                                message_count = current_count

                            time.sleep(2)
                        except KeyboardInterrupt:
                            logger.info("⏹️ Monitoring stopped by user")
                            break
                        except Exception as e:
                            logger.error(f"❌ Error monitoring queue: {str(e)}")
                            time.sleep(5)

                    logger.info(f"✅ Monitoring complete. Final queue count: {message_count}")
        except Exception as e:
            logger.error(f"❌ Failed to monitor queue: {str(e)}")

    def print_setup_instructions(self):
        """Print setup instructions for local testing"""
        print("""
🔧 SETUP INSTRUCTIONS FOR LOCAL SERVICE BUS TESTING

1. Configure your local.settings.json:
   Update the ServiceBusConnection with your actual Azure Service Bus connection string:

   "ServiceBusConnection": "Endpoint=sb://YOUR-NAMESPACE.servicebus.windows.net/;SharedAccessKeyName=YOUR-KEY-NAME;SharedAccessKey=YOUR-KEY"

2. Ensure your Service Bus queue exists:
   - Queue name: "transactions"
   - You can create this in the Azure portal

3. Start your Azure Function locally:
   func start --port 7071

4. Run tests:
   python test_servicebus_local.py --send-message
   python test_servicebus_local.py --monitor

🔍 TROUBLESHOOTING:
- Check that your function app is running on http://localhost:7071
- Verify Service Bus connection string is correct
- Ensure the 'transactions' queue exists in your Service Bus namespace
- Check function app logs for any errors
        """)

def main():
    parser = argparse.ArgumentParser(description='Test Azure Service Bus integration locally')
    parser.add_argument('--send-message', action='store_true', help='Send a single test message')
    parser.add_argument('--monitor', action='store_true', help='Monitor the Service Bus queue')
    parser.add_argument('--health-check', action='store_true', help='Check function app health')
    parser.add_argument('--setup', action='store_true', help='Show setup instructions')
    parser.add_argument('--transaction-id', type=str, help='Specific transaction ID to use')

    args = parser.parse_args()

    tester = ServiceBusLocalTester()

    if args.setup:
        tester.print_setup_instructions()
        return

    # Check function health first (keep this async)
    async def run_health_check():
        return await tester.check_function_health()

    health_ok = asyncio.run(run_health_check())
    if not health_ok:
        logger.warning("⚠️ Function app doesn't seem to be running. Some tests may fail.")
        print("Run: func start --port 7071")
        if not args.health_check:
            return

    if args.health_check:
        asyncio.run(run_health_check())
    elif args.send_message:
        tester.send_test_message(args.transaction_id)
    elif args.monitor:
        tester.monitor_queue()
    else:
        # Default: run a comprehensive test
        logger.info("🧪 Running comprehensive Service Bus test...")

        # 1. Health check
        asyncio.run(run_health_check())

        # 2. Send test message
        logger.info("\n" + "="*50)
        tester.send_test_message()

        # 3. Wait a bit for processing
        logger.info("\n⏳ Waiting 5 seconds for message processing...")
        time.sleep(5)

        logger.info("\n✅ Test complete! Check your function app logs for processing details.")

if __name__ == "__main__":
    main()
