import re
import dateparser
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, List, Dict, Any
from .utils import logger, format_date_iso, escape_html

# TLScontact domain pattern
TLS_DOMAIN_REGEX = re.compile(r'@(tlscontact\.|tls-contact\.|tlsvisa\.)', re.IGNORECASE)

# Keyword patterns for appointment/visa emails
KEYWORD_REGEX = re.compile(
    r'\b(rendez-?vous|rdv|visa|appointment|confirmer|confirmé|confirmed|rendezvous|confirmation|tlscontact|tls-contact)\b', 
    re.IGNORECASE
)

# Numeric date pattern (DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, etc.)
DATE_NUMERIC_REGEX = re.compile(r'\b([0-3]?\d[\/\-\.\s][01]?\d[\/\-\.\s](?:\d{2}|\d{4}))\b')

def parse_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Parse an email message to detect TLScontact appointments"""
    result = {
        'isTls': False,
        'parsed': False,
        'date': None,
        'dateRaw': None,
        'link': None,
        'from': message.get('from', ''),
        'subject': message.get('subject', ''),
        'snippet': message.get('snippet', ''),
        'rawBody': message.get('body', '')
    }

    # Check if email meets criteria
    is_tls_domain = bool(TLS_DOMAIN_REGEX.search(result['from']))
    
    # Exact keywords logic from Node.js
    text_to_search = f"{result['subject']} {result['snippet']} {result['rawBody']}"
    has_keyword = bool(re.search(r'rendez-?vous|rdv|visa|tlscontact|tls-contact', text_to_search, re.IGNORECASE))

    result['isTls'] = is_tls_domain or has_keyword

    if not result['isTls']:
        logger.debug(f"Message not from TLScontact: {message.get('id')}")
        return result

    labels = message.get('labelIds', [])
    logger.info(f"TLScontact email detected: {{'id': {message.get('id')}, 'subject': {result['subject']}, 'from': {result['from']}, 'labels': {', '.join(labels)}}}")

    result['labels'] = labels

    # Extract date
    extracted = extract_date(result['rawBody'], result['subject'], result['snippet'])
    if extracted:
        result['parsed'] = True
        result['date'] = format_date_iso(extracted['date'])
        result['dateRaw'] = extracted['raw']
    else:
        logger.warning(f"Failed to extract date from message: {message.get('id')}")

    # Extract link
    result['link'] = extract_link(result['rawBody'])

    return result

def extract_date(body: str, subject: str = '', snippet: str = '') -> Optional[Dict[str, Any]]:
    """Extract appointment date from email body using numeric regex and dateparser"""
    combined_text = f"{subject}\n{snippet}\n{body}"

    # Try numeric date pattern first
    numeric_matches = DATE_NUMERIC_REGEX.findall(combined_text)
    for date_str in numeric_matches:
        # dateparser handles multiple locales including French and English
        parsed_dt = dateparser.parse(date_str, settings={'PREFER_DATES_FROM': 'future'})
        if parsed_dt:
            logger.debug(f"Extracted date (numeric): {date_str} -> {parsed_dt.isoformat()}")
            return {'date': parsed_dt, 'raw': date_str}

    # Fallback to dateparser for natural language
    # Iterate over lines to find potential date strings
    # This mirrors the behavior of finding a date within the text more reliably
    lines = combined_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Skip lines that are too short or just numbers
        if len(line) < 5 or line.isdigit():
            continue

        # Clean up bullet points or labels to help dateparser
        cleaned_line = line.lstrip('- ').replace('Date:', '').strip()
        
        # Try parsing the line
        parsed_dt = dateparser.parse(
            cleaned_line, 
            languages=['en', 'fr'],
            settings={
                'PREFER_DATES_FROM': 'future',
                'STRICT_PARSING': False, 
                'REQUIRE_PARTS': ['day', 'month']
            }
        )
        
        if parsed_dt:
            # Simple valid year check (e.g. current year or next)
            current_year = datetime.now().year
            if current_year - 1 <= parsed_dt.year <= current_year + 2:
                logger.debug(f"Extracted date (natural): {line} -> {parsed_dt.isoformat()}")
                return {'date': parsed_dt, 'raw': line}

    return None

def extract_link(body: str) -> Optional[str]:
    """Extract confirmation link from email body"""
    if not body:
        return None

    try:
        soup = BeautifulSoup(body, 'html.parser')
        links = []

        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('http'):
                links.append(href)

        # Prefer links containing "tlscontact" or "confirm"
        for link in links:
            if re.search(r'tlscontact|confirm', link, re.IGNORECASE):
                logger.debug(f"Extracted link (TLS/confirm): {link}")
                return link

        if links:
            logger.debug(f"Extracted link (first): {links[0]}")
            return links[0]

    except Exception:
        logger.debug("Failed to parse HTML, trying plain text link extraction")

    # Fallback: extract URLs from plain text
    url_regex = re.compile(r'https?://[^\s"<>|)]+', re.IGNORECASE)
    matches = url_regex.findall(body)
    
    if matches:
        # Remove trailing punctuation
        cleaned_matches = [re.sub(r'[.!?,;:]+$', '', url) for url in matches]
        
        for url in cleaned_matches:
            if re.search(r'tlscontact|confirm', url, re.IGNORECASE):
                logger.debug(f"Extracted link (plain text TLS/confirm): {url}")
                return url
        
        return cleaned_matches[0]

    return None

def format_for_telegram(parsed: Dict[str, Any], message_id: str) -> str:
    """Format parsed result for Telegram notification"""
    header = '🔔 <b>TLScontact Update</b>'

    # Check for keywords for Emergency alert
    is_appointment = bool(re.search(r'rendez-?vous|rdv|appointment', f"{parsed['subject']} {parsed['rawBody']}", re.IGNORECASE))

    if is_appointment and parsed['parsed']:
        header = '🚨 <b>EMERGENCY: APPOINTMENT FOUND</b>'

    # Add info if found in Spam or Trash
    labels = parsed.get('labels', [])
    if 'SPAM' in labels:
        header = f"⚠️ <b>Spam Detect:</b> {header}"
    elif 'TRASH' in labels:
        header = f"🗑️ <b>Trash Detect:</b> {header}"

    message = f"{header}\n\n"

    if parsed['parsed'] and parsed['date']:
        try:
            date_obj = datetime.fromisoformat(parsed['date'].replace('Z', '+00:00'))
            # Format: weekday, day month year, hour:minute (French-like)
            # Python's locale-dependent formatting can be tricky, using a manual format for "pretty"
            pretty_date = date_obj.strftime('%A %d %B %Y %H:%M') 
            # Note: This is English by default. For true French mirror:
            # import locale; locale.setlocale(locale.LC_TIME, 'fr_FR')
            # But let's keep it simple for now or use a constant map if needed.
            
            message += f"📅 <b>Date:</b> {pretty_date}\n"
            if parsed['dateRaw']:
                message += f"   (Source: \"{parsed['dateRaw']}\")\n"
        except Exception:
            message += f"📅 <b>Date:</b> {parsed['date']}\n"
    else:
        message += "❓ <b>Date:</b> Information non détectée\n"

    message += "\n"
    message += f"👤 <b>From:</b> {escape_html(parsed['from'])}\n"
    message += f"📧 <b>Subject:</b> {escape_html(parsed['subject'])}\n"

    if parsed['link']:
        message += f"\n🔗 <b>Link:</b> <a href=\"{parsed['link']}\">Ouvrir le portail</a>\n"

    if parsed['snippet']:
        short_snippet = parsed['snippet'][:150]
        suffix = '...' if len(parsed['snippet']) > 150 else ''
        message += f"\n📝 <b>Preview:</b>\n<i>{escape_html(short_snippet)}{suffix}</i>\n"

    message += f"\n<code>ID: {message_id}</code>"

    return message
