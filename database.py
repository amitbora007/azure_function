#!/usr/bin/env python3
"""
Database module for MSSQL Server operations in Azure Functions
Handles async connections and queries to bim_transaction table
"""
import aioodbc
import asyncio
import os
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class MSSQLDatabase:
    """Async MSSQL Database connection handler for Azure Functions"""

    def __init__(self):
        self.connection_pool: Optional[aioodbc.Pool] = None
        self.connection_string = self._build_connection_string()

    def _build_connection_string(self) -> str:
        """Build MSSQL connection string from environment variables"""
        server = os.environ.get('MSSQL_SERVER')
        database = os.environ.get('MSSQL_DATABASE')
        username = os.environ.get('MSSQL_USERNAME')
        password = os.environ.get('MSSQL_PASSWORD')
        port = os.environ.get('MSSQL_PORT')
        driver = os.environ.get('MSSQL_DRIVER')

        if not all([server, database, username, password]):
            logger.warning("Database configuration incomplete - some environment variables are missing")
            return ""

        # Build connection string
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server},{port};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            "Encrypt=no;"
            "TrustServerCertificate=no;"
            "Connection Timeout=30;"
        )

        logger.info(f"MSSQL connection string built for server: {server}, database: {database}")
        return conn_str

    async def initialize_pool(self, min_size: int = 1, max_size: int = 5):
        """Initialize connection pool"""
        if not self.connection_string:
            logger.error("Cannot initialize pool - connection string is empty")
            return False

        try:
            self.connection_pool = await aioodbc.create_pool(
                dsn=self.connection_string,
                minsize=min_size,
                maxsize=max_size,
                autocommit=True
            )
            logger.info(f"MSSQL connection pool initialized (min: {min_size}, max: {max_size})")

            # Test connection
            test_result = await self.test_connection()
            return test_result

        except Exception as e:
            logger.error(f"Failed to initialize MSSQL connection pool: {str(e)}")
            return False

    async def close_pool(self):
        """Close connection pool"""
        if self.connection_pool:
            try:
                self.connection_pool.close()
                await self.connection_pool.wait_closed()
                logger.info("MSSQL connection pool closed")
            except Exception as e:
                logger.error(f"Error closing connection pool: {str(e)}")

    async def test_connection(self) -> bool:
        """Test database connection"""
        if not self.connection_pool:
            return False

        try:
            async with self.connection_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1 as test")
                    result = await cursor.fetchone()
                    logger.info("MSSQL connection test successful")
                    return result[0] == 1
        except Exception as e:
            logger.error(f"MSSQL connection test failed: {str(e)}")
            return False

    async def get_transaction_by_id(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Get transaction from bim_transaction table by ID"""
        if not self.connection_pool:
            logger.warning("Database connection pool not available")
            return None

        query = """
        SELECT
            te.transaction_id,
            right(bt.transaction_id, 6) as serial_number,
            bt.stamp,
            bt.total_amount,
            bt.consumer_id,
            bt.merchant_id,
            bt.terminal_id,
            bt.approval_code,
            bt.cdf1,
            bt.cdf2,
            c.fname,
            c.lname,
            c.address1,
            c.address2,
            c.city,
            c.state,
            c.zip,
            c.home_phone,
            c.mobile_phone,
            m.address1 as merchant_address,
            m.city as merchant_city,
            m.state as merchant_state,
            m.ach_trans_type,
            m.ach_statement_id,
            te.settled_log_id
        FROM bim_transaction bt
        INNER JOIN bim_consumer c ON bt.consumer_id = c.consumer_id
        INNER JOIN bim_merchant m ON bt.merchant_id = m.merchant_id
        LEFT JOIN bim_transaction_events te ON bt.transaction_id = te.transaction_id
        WHERE bt.transaction_id = ?
        """

        try:
            async with self.connection_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, (transaction_id,))
                    row = await cursor.fetchone()

                    if row:
                        # Convert row to dictionary
                        columns = [column[0] for column in cursor.description]
                        transaction_data = dict(zip(columns, row))

                        logger.info(f"Found transaction data for ID: {transaction_id}")
                        return transaction_data
                    else:
                        logger.warning(f"No transaction found for ID: {transaction_id}")
                        return None

        except Exception as e:
            logger.error(f"Database query failed for transaction {transaction_id}: {str(e)}")
            return None


    async def insert_transaction_event(self,
        transaction_id: str,
        settled_log_id: str,
        created_by: int,
        payliance_auth_id: str
    ) -> bool:
        """Insert a record into bim_transaction_events table"""
        if not self.connection_pool:
            logger.warning("Database connection pool not available")
            return False

        query = """
        INSERT INTO bim_transaction_events
        (transaction_id, settled_stamp, settled_log_id, created_by, payliance_auth_id, created_on)
        VALUES (?, GETUTCDATE(), ?, ?, ?, GETUTCDATE())
        """

        try:
            async with self.connection_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(query, (
                        transaction_id,
                        settled_log_id,
                        created_by,
                        payliance_auth_id
                    ))
                    if cursor.rowcount > 0:
                        logger.info(f"Inserted transaction event for transaction_id {transaction_id}")
                        return True
                    else:
                        logger.warning(f"No rows inserted for transaction_id {transaction_id}")
                        return False
        except Exception as e:
            logger.error(f"Failed to insert transaction event for transaction_id {transaction_id}: {str(e)}")
            return False

# Global database instance
db = MSSQLDatabase()
