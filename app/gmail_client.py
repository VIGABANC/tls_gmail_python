import os
import base64
from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from .utils import logger

# Global clients
gmail_service = None

def init_gmail_client():
    """Initialize Gmail client with OAuth2 credentials from environment variables"""
    global gmail_service
    
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
    refresh_token = os.getenv('GOOGLE_REFRESH_TOKEN')

    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError(
            'Missing required Google OAuth credentials. '
            'Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN env vars.'
        )

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    gmail_service = build('gmail', 'v1', credentials=creds)
    logger.info('Gmail client initialized')

async def list_messages(query: str, max_results: int = 10, include_spam_trash: bool = True) -> List[Dict[str, str]]:
    """List messages matching query"""
    if not gmail_service:
        raise RuntimeError('Gmail client not initialized. Call init_gmail_client() first.')

    user_email = os.getenv('GOOGLE_USER_EMAIL', 'me')

    try:
        logger.debug(f"Listing messages with query: {query} include_spam_trash: {include_spam_trash}")

        response = gmail_service.users().messages().list(
            userId=user_email,
            q=query,
            maxResults=max_results,
            includeSpamTrash=include_spam_trash
        ).execute()

        messages = response.get('messages', [])
        logger.info(f"Found {len(messages)} messages matching query")

        return messages
    except Exception as e:
        logger.error(f"Failed to list messages: {str(e)}")
        raise e

async def get_message(message_id: str) -> Dict[str, Any]:
    """Get full message details"""
    if not gmail_service:
        raise RuntimeError('Gmail client not initialized. Call init_gmail_client() first.')

    user_email = os.getenv('GOOGLE_USER_EMAIL', 'me')

    try:
        logger.debug(f"Fetching message: {message_id}")

        message = gmail_service.users().messages().get(
            userId=user_email,
            id=message_id,
            format='full'
        ).execute()

        # Parse headers
        headers = {}
        payload = message.get('payload', {})
        for header in payload.get('headers', []):
            headers[header['name'].lower()] = header['value']

        # Extract body
        body = extract_body(payload)

        # Build parsed message object
        parsed = {
            'id': message['id'],
            'threadId': message['threadId'],
            'labelIds': message.get('labelIds', []),
            'subject': headers.get('subject', ''),
            'from': headers.get('from', ''),
            'to': headers.get('to', ''),
            'date': headers.get('date', ''),
            'snippet': message.get('snippet', ''),
            'body': body
        }

        logger.debug(f"Message fetched and basic-parsed: {{'id': {parsed['id']}, 'subject': {parsed['subject']}, 'from': {parsed['from']}, 'labels': {', '.join(parsed['labelIds'])}}}")

        return parsed
    except Exception as e:
        logger.error(f"Failed to get message: {str(e)}")
        raise e

def extract_body(payload: Dict[str, Any]) -> str:
    """Extract body from message payload"""
    if not payload:
        return ''

    # Single part message
    body_data = payload.get('body', {}).get('data')
    if body_data:
        return decode_base64url(body_data)

    # Multi-part message
    parts = payload.get('parts', [])
    if parts:
        html_parts = []
        text_parts = []

        def traverse_parts(inner_parts):
            for part in inner_parts:
                mime_type = part.get('mimeType')
                data = part.get('body', {}).get('data')
                
                if mime_type == 'text/html' and data:
                    html_parts.append(decode_base64url(data))
                elif mime_type == 'text/plain' and data:
                    text_parts.append(decode_base64url(data))

                # Handle attachments that are text/html
                filename = part.get('filename')
                if filename and data:
                    if mime_type in ['text/plain', 'text/html']:
                        logger.debug(f"Extracting content from attachment: {filename}")
                        content = decode_base64url(data)
                        if mime_type == 'text/html':
                            html_parts.append(content)
                        else:
                            text_parts.append(content)

                if 'parts' in part:
                    traverse_parts(part['parts'])

        traverse_parts(parts)

        if html_parts:
            return '\n<hr>\n'.join(html_parts)
        if text_parts:
            return '\n---\n'.join(text_parts)

    return ''

def decode_base64url(data: str) -> str:
    """Decode base64url-encoded string used by Gmail API"""
    if not data:
        return ''
    try:
        decoded_bytes = base64.urlsafe_b64decode(data + '=' * (4 - len(data) % 4))
        return decoded_bytes.decode('utf-8', errors='replace')
    except Exception as e:
        logger.warning(f"Failed to decode base64url: {str(e)}")
        return ''
