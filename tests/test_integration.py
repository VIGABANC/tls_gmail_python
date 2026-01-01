import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.parser import parse_message

# Fixture loader for integration tests (duplicate logic, could be shared)
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')

def load_fixture(filename):
    file_path = os.path.join(FIXTURES_DIR, filename)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    message = {
        'id': filename.replace('.txt', ''),
        'from': '',
        'subject': '',
        'snippet': '',
        'body': ''
    }

    in_body = False
    body_lines = []

    for line in lines:
        line = line.replace('\r', '')
        if line.strip() == '---':
            in_body = True
            continue

        if not in_body:
            if line.startswith('From: '):
                message['from'] = line[6:].strip()
            elif line.startswith('Subject: '):
                message['subject'] = line[9:].strip()
        else:
            body_lines.append(line)

    message['body'] = '\n'.join(body_lines)
    message['snippet'] = ' '.join(body_lines[:3])[:200]
    return message

# Integration tests using mocked services
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.watcher import run_poll_cycle
from app.storage import close_storage, init_storage

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'test_token')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', 'test_chat_id')
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'test_id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'test_secret')
    monkeypatch.setenv('GOOGLE_REFRESH_TOKEN', 'test_refresh')
    monkeypatch.setenv('PYTHONPATH', '.')

@pytest.mark.asyncio
async def test_full_poll_cycle_with_appointment(mock_env):
    # Mock Gmail Service
    mock_gmail = MagicMock()
    mock_messages_list = MagicMock()
    mock_messages_list.execute.return_value = {
        'messages': [{'id': 'msg_123', 'threadId': 't_123'}]
    }
    mock_gmail.users().messages().list.return_value = mock_messages_list

    # Load a fixture as the message content
    fixture_msg = load_fixture('sample_tls_email_1.txt')
    
    # Mock message get response structure
    mock_message_get = MagicMock()
    mock_message_get.execute.return_value = {
        'id': 'msg_123',
        'threadId': 't_123',
        'labelIds': ['INBOX'],
        'snippet': fixture_msg['snippet'],
        'payload': {
            'headers': [
                {'name': 'From', 'value': fixture_msg['from']},
                {'name': 'Subject', 'value': fixture_msg['subject']},
                {'name': 'Date', 'value': 'Mon, 01 Jan 2026 10:00:00 +0000'}
            ],
            'body': {
                'data': None # Single part
            },
            'parts': [
                {
                    'mimeType': 'text/plain',
                    'body': {
                        'data': None # We rely on our parser consuming the 'body' string directly in tests, 
                                     # but in app/gmail_client.py it extracts from base64.
                                     # For this integration test, let's mock get_message directly to avoid mocking base64 decoding.
                    }
                }
            ]
        }
    }
    mock_gmail.users().messages().get.return_value = mock_message_get

    # Mock Telegram
    mock_httpx_post = AsyncMock()
    mock_httpx_post.return_value.status_code = 200
    mock_httpx_post.return_value.json.return_value = {'ok': True}

    # Patch everything
    with patch('app.gmail_client.build', return_value=mock_gmail), \
         patch('app.gmail_client.Credentials', MagicMock()), \
         patch('httpx.AsyncClient.post', mock_httpx_post), \
         patch('app.watcher.get_message', new_callable=AsyncMock) as mock_get_msg_func:
        
        # Override get_message to return our clean fixture object
        # The watcher calls get_message(id) which returns a parsed dict structure
        # In app/gmail_client.py get_message returns dict keys: id, threadId, labelIds, subject, from, to, date, snippet, body
        mock_get_msg_func.return_value = {
            'id': 'msg_123',
            'threadId': 't_123',
            'labelIds': ['INBOX'],
            'subject': fixture_msg['subject'],
            'from': fixture_msg['from'],
            'to': 'me',
            'date': 'Mon, 01 Jan 2026',
            'snippet': fixture_msg['snippet'],
            'body': fixture_msg['body']
        }
        
        # Run the cycle
        stats = await run_poll_cycle()
        
        # Verify results
        assert stats['checked'] == 1
        assert stats['new'] == 1
        assert stats['notified'] == 1
        assert len(stats['errors']) == 0
        
        # Verify Telegram send was called
        mock_httpx_post.assert_called_once()
        args, kwargs = mock_httpx_post.call_args
        assert 'api.telegram.org' in args[0]
        assert 'EMERGENCY' in kwargs['json']['text']

    close_storage()

@pytest.mark.asyncio
async def test_deduplication(mock_env):
    # Same setup but run twice
    
    # Mock clients as before
    mock_gmail = MagicMock()
    mock_messages_list = MagicMock()
    # Return same message both times
    mock_messages_list.execute.return_value = {'messages': [{'id': 'msg_dup', 'threadId': 't_dup'}]}
    mock_gmail.users().messages().list.return_value = mock_messages_list

    mock_httpx_post = AsyncMock()
    mock_httpx_post.return_value.status_code = 200

    fixture_msg = load_fixture('sample_tls_email_1.txt')
    
    with patch('app.gmail_client.build', return_value=mock_gmail), \
         patch('app.gmail_client.Credentials', MagicMock()), \
         patch('httpx.AsyncClient.post', mock_httpx_post), \
         patch('app.watcher.get_message', new_callable=AsyncMock) as mock_get_msg_func:
         
        mock_get_msg_func.return_value = {
            'id': 'msg_dup',
            'threadId': 't_dup',
            'labelIds': ['INBOX'],
            'subject': fixture_msg['subject'],
            'from': fixture_msg['from'],
            'to': 'me',
            'date': 'Mon, 01 Jan 2026',
            'snippet': fixture_msg['snippet'],
            'body': fixture_msg['body']
        }

        # First run
        stats1 = await run_poll_cycle()
        assert stats1['notified'] == 1

        # Second run
        stats2 = await run_poll_cycle()
        assert stats2['notified'] == 0
        assert stats2['processed'] == 1 # Skipped as processed

    close_storage()
