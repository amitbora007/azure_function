#!/usr/bin/env python3
"""
Test script for Payliance Azure Function
"""
import json
import httpx
import asyncio
from datetime import datetime

async def test_payliance_function():
    """Test the Payliance Azure Function locally"""

    # Test data - now only needs transaction_id since data comes from database
    test_payload = {
        "transaction_id": "10521553374999953559"
    }

    # Local function URL (when running func start)
    url = "http://localhost:7071/api/debit"

    print("🧪 Testing Payliance Azure Function with Database Integration")
    print(f"📋 Transaction ID: {test_payload['transaction_id']}")
    print(f"🔗 URL: {url}")
    print("� Function will attempt to fetch transaction data from MSSQL database")
    print("-" * 50)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                json=test_payload,
                headers={"Content-Type": "application/json"}
            )

        print(f"📊 Status Code: {response.status_code}")
        print(f"📄 Response Headers: {dict(response.headers)}")
        print("-" * 50)

        try:
            response_data = response.json()
            print("📋 Response Body:")
            print(json.dumps(response_data, indent=2))
        except json.JSONDecodeError:
            print("📄 Response Body (raw):")
            print(response.text)

        if response.status_code == 200:
            print("\n✅ Test completed successfully!")
        else:
            print(f"\n⚠️ Test completed with status {response.status_code}")

    except httpx.ConnectError:
        print("❌ Connection failed!")
        print("💡 Make sure the Azure Function is running locally with 'func start'")
    except httpx.TimeoutException:
        print("⏰ Request timed out!")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

def test_payload_validation():
    """Test payload validation scenarios"""

    print("\n🔍 Testing payload validation...")

    test_cases = [
        {
            "name": "Missing transaction_id",
            "payload": {}
        },
        {
            "name": "Empty payload",
            "payload": {}
        },
        {
            "name": "Valid transaction_id",
            "payload": {
                "transaction_id": "TEST123"
            }
        }
    ]

    for test_case in test_cases:
        print(f"\n📝 Test case: {test_case['name']}")
        print(f"📋 Payload: {json.dumps(test_case['payload'], indent=2)}")

async def test_with_real_transaction():
    """Test with a real transaction ID if available"""

    print("\n🔍 Testing with real transaction ID...")

    # You can replace this with an actual transaction ID from your database
    real_transaction_id = "TXN_REAL_123456"  # Replace with actual ID

    test_payload = {
        "transaction_id": real_transaction_id
    }

    url = "http://localhost:7071/api/debit"

    print(f"📋 Real Transaction ID: {real_transaction_id}")
    print("💾 This should fetch actual data from the database")
    print("-" * 50)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                json=test_payload,
                headers={"Content-Type": "application/json"}
            )

        print(f"📊 Status Code: {response.status_code}")
        print("-" * 30)

        try:
            response_data = response.json()
            print("📋 Response Body:")
            print(json.dumps(response_data, indent=2))

            # Check if database was used
            if response_data.get('database_used'):
                print("\n✅ Database data was successfully used!")
            else:
                print("\n⚠️ database lookup failed")

        except json.JSONDecodeError:
            print("📄 Response Body (raw):")
            print(response.text)

    except httpx.ConnectError:
        print("❌ Connection failed!")
        print("💡 Make sure the Azure Function is running locally with 'func start'")
    except httpx.TimeoutException:
        print("⏰ Request timed out!")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    print("🚀 Payliance Azure Function Test Suite with Database Integration")
    print("=" * 60)

    # Test payload validation
    test_payload_validation()

    # Test actual function call
    print("\n" + "=" * 60)
    asyncio.run(test_payliance_function())

    # Test with real transaction (optional)
    print("\n" + "=" * 60)
    asyncio.run(test_with_real_transaction())