import os
import asyncio
from typing import Dict, Any, List
from .utils import logger
from .gmail_client import init_gmail_client, list_messages, get_message
from .parser import parse_message
from .notifier import init_telegram_client, send_appointment_notification
from .storage import init_storage, has_processed, mark_processed

async def run_poll_cycle() -> Dict[str, Any]:
    """Run one polling cycle"""
    stats = {
        'checked': 0,
        'new': 0,
        'processed': 0,
        'notified': 0,
        'errors': []
    }

    try:
        logger.info('=== Starting poll cycle (Python) ===')

        # Initialize clients
        init_storage()
        init_gmail_client()
        init_telegram_client()

        # Build query
        query = os.getenv('POLL_QUERY', 'from:(tlscontact.com)')

        # Add "in:anywhere" if enabled
        search_anywhere = os.getenv('SEARCH_IN_ANYWHERE', 'true').lower() != 'false'
        if search_anywhere and 'in:anywhere' not in query:
            query = f"in:anywhere ({query})"

        # Add "newer_than:1d"
        if 'newer_than:' not in query:
            query = f"{query} newer_than:1d"

        # Add extra query terms
        extra_query = os.getenv('SEARCH_QUERY_EXTRA')
        if extra_query:
            query = f"{query} {extra_query}"

        limit = int(os.getenv('POLL_LIMIT', '10'))
        max_sends = int(os.getenv('POLL_MAX_SENDS_PER_RUN', '3'))

        logger.info(f"Poll config: {{'query': {query}, 'limit': {limit}, 'maxSends': {max_sends}, 'searchAnywhere': {search_anywhere}}}")

        # List messages
        messages = await list_messages(query, limit, search_anywhere)
        stats['checked'] = len(messages)

        if not messages:
            logger.info('No messages found matching query')
            return stats

        logger.info(f"Found {len(messages)} messages, processing...")

        sent_count = 0

        # Process each message
        for msg in messages:
            message_id = msg['id']
            try:
                # Check if already processed
                if has_processed(message_id):
                    logger.debug(f"Message already processed, skipping: {message_id}")
                    stats['processed'] += 1
                    continue

                stats['new'] += 1

                # Fetch full message
                full_message = await get_message(message_id)

                # Log labels
                labels = full_message.get('labelIds', [])
                logger.info(f"Processing message {message_id} found in: {', '.join(labels)}")

                # Parse message
                parsed = parse_message(full_message)

                # Check if this is a TLScontact email
                if not parsed.get('isTls'):
                    logger.debug(f"Message not TLScontact, marking processed: {message_id}")
                    mark_processed(message_id)
                    continue

                # Check send limit
                if sent_count >= max_sends:
                    logger.warning(f"Reached max sends limit ({max_sends}), skipping notification for: {message_id}")
                    mark_processed(message_id)
                    continue

                # Send notification
                logger.info(f"Sending notification for message: {message_id}")
                await send_appointment_notification(parsed, message_id)

                sent_count += 1
                stats['notified'] += 1

                # Mark as processed AFTER successful notification
                mark_processed(message_id)

                logger.info(f"Message processed successfully: {message_id}")

            except Exception as e:
                logger.error(f"Failed to process message {message_id}: {str(e)}")
                stats['errors'].append({
                    'messageId': message_id,
                    'error': str(e)
                })

        logger.info(f"=== Poll cycle complete === {stats}")
        return stats

    except Exception as e:
        logger.error(f"Poll cycle failed: {str(e)}")
        stats['errors'].append({
            'phase': 'initialization',
            'error': str(e)
        })
        raise e

async def start_continuous_polling():
    """Continuous polling mode"""
    interval_minutes = int(os.getenv('POLL_INTERVAL_MINUTES', '5'))
    interval_seconds = interval_minutes * 60

    logger.info(f"Starting continuous polling (interval: {interval_minutes} minutes)")

    # Run immediately on start
    try:
        await run_poll_cycle()
    except Exception as e:
        logger.error(f"Initial poll cycle failed: {str(e)}")

    # Schedule recurring polls
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await run_poll_cycle()
        except Exception as e:
            logger.error(f"Poll cycle failed: {str(e)}")
            # Continue polling even if one cycle fails
