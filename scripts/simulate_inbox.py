import os
import sys
import re

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.parser import parse_message, format_for_telegram

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests', 'fixtures')

def load_fixture(filename):
    file_path = os.path.join(FIXTURES_DIR, filename)

    if not os.path.exists(file_path):
        print(f"⚠️  Fixture not found: {filename}")
        return None

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

async def main():
    print('📧 TLScontact Email Parser - Fixture Simulator (Python)')
    print('=======================================================')
    print('')

    if not os.path.exists(FIXTURES_DIR):
        print(f"❌ Fixtures directory not found: {FIXTURES_DIR}")
        sys.exit(1)

    fixtures = [f for f in os.listdir(FIXTURES_DIR) if f.endswith('.txt')]

    if not fixtures:
        print(f"⚠️  No fixture files found in {FIXTURES_DIR}")
        sys.exit(0)

    print(f"Found {len(fixtures)} fixture(s)")
    print('')

    for filename in fixtures:
        print(f"\n{'='*60}")
        print(f"📄 Processing: {filename}")
        print('='*60)

        message = load_fixture(filename)
        if not message:
            continue

        print('\nInput:')
        print(f"  From: {message['from']}")
        print(f"  Subject: {message['subject']}")
        print(f"  Body length: {len(message['body'])} chars")
        print('')

        # Parse message
        parsed = parse_message(message)

        print('Parser Output:')
        print(f"  Is TLScontact: {'✅ Yes' if parsed['isTls'] else '❌ No'}")
        print(f"  Date Parsed: {'✅ Yes' if parsed['parsed'] else '❌ No'}")

        if parsed['date']:
            print(f"  Date (ISO): {parsed['date']}")
            print(f"  Date (raw): {parsed['dateRaw']}")

        if parsed['link']:
            print(f"  Link: {parsed['link']}")

        print('')

        # Format for Telegram
        if parsed['isTls']:
            print('Telegram Message Preview:')
            print('-'*60)
            telegram_msg = format_for_telegram(parsed, message['id'])
            # Strip HTML tags for console display
            plain_msg = re.sub(r'<b>(.*?)</b>', r'**\1**', telegram_msg)
            plain_msg = re.sub(r'<code>(.*?)</code>', r'`\1`', plain_msg)
            plain_msg = re.sub(r'<a href="(.*?)">(.*?)</a>', r'\2 (\1)', plain_msg)
            plain_msg = re.sub(r'<[^>]+>', '', plain_msg)
            print(plain_msg)
            print('-'*60)

    print('\n✅ Simulation complete!')

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
