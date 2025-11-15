"""
Main email automation script
Monitors Gmail inbox and responds to banking queries using AI
"""

import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import time
from groq import Groq
from email.header import decode_header

# Import configurations
from config import (
    GMAIL_ADDRESS, 
    SMTP_PASSWORD, 
    GROQ_API_KEY, 
    CHECK_INTERVAL,
    MODEL_NAME,
    TEMPERATURE,
    MAX_TOKENS
)
from banking_prompt import BANKING_SYSTEM_PROMPT

# Initialize Groq client
groq_client = Groq(api_key=GROQ_API_KEY)


def connect_to_gmail():
    """Connect to Gmail using IMAP"""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_ADDRESS, SMTP_PASSWORD)
        return mail
    except Exception as e:
        print(f"Error connecting to Gmail: {e}")
        return None


def decode_email_subject(subject):
    """Decode email subject"""
    if subject is None:
        return "No Subject"
    decoded = decode_header(subject)
    subject_parts = []
    for content, encoding in decoded:
        if isinstance(content, bytes):
            subject_parts.append(content.decode(encoding or 'utf-8', errors='ignore'))
        else:
            subject_parts.append(content)
    return ''.join(subject_parts)


def get_email_body(msg):
    """Extract email body from message"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
                except:
                    pass
    else:
        try:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            body = str(msg.get_payload())
    return body.strip()


def generate_response(user_query):
    """Generate response using Llama-3.3-70B via Groq"""
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": BANKING_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_query
                }
            ],
            model=MODEL_NAME,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Error generating response: {e}")
        return "We apologize for the inconvenience. We're experiencing technical difficulties. Please contact our customer care at 1800-XXX-XXXX or visit your nearest branch for assistance."


def send_email_response(to_address, subject, body):
    """Send email response via SMTP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_ADDRESS
        msg['To'] = to_address
        msg['Subject'] = f"Re: {subject}" if subject != "No Subject" else "Re: Your Query"
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_ADDRESS, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✓ Response sent to {to_address}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def process_unread_emails():
    """Main function to process unread emails"""
    mail = connect_to_gmail()
    if not mail:
        return
    
    try:
        mail.select('inbox')
        
        # Search for unread emails
        status, messages = mail.search(None, 'UNSEEN')
        
        if status != "OK":
            print("No unread messages found")
            return
        
        email_ids = messages[0].split()
        
        if not email_ids:
            print("No new emails to process")
            return
        
        print(f"Found {len(email_ids)} unread email(s)")
        
        for email_id in email_ids:
            try:
                # Fetch the email
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                
                if status != "OK":
                    continue
                
                # Parse email
                msg = email.message_from_bytes(msg_data[0][1])
                
                # Get sender
                sender = msg.get('From')
                sender_email = email.utils.parseaddr(sender)[1]
                
                # Get subject
                subject = decode_email_subject(msg.get('Subject'))
                
                # Get body
                body = get_email_body(msg)
                
                print(f"\n--- Processing email from {sender_email} ---")
                print(f"Subject: {subject}")
                print(f"Query: {body[:100]}...")
                
                # Generate AI response
                print("Generating AI response...")
                ai_response = generate_response(body)
                
                # Send response
                if send_email_response(sender_email, subject, ai_response):
                    # Mark as read only after successful response
                    mail.store(email_id, '+FLAGS', '\\Seen')
                    print("Email marked as read")
                
            except Exception as e:
                print(f"Error processing email: {e}")
                continue
        
    except Exception as e:
        print(f"Error in process_unread_emails: {e}")
    finally:
        try:
            mail.close()
            mail.logout()
        except:
            pass


def main():
    """Main loop - continuously monitor inbox"""
    print("=" * 60)
    print("Bank Email Automation System Started")
    print("=" * 60)
    print(f"Monitoring: {GMAIL_ADDRESS}")
    print(f"Check interval: {CHECK_INTERVAL} seconds")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    while True:
        try:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking for new emails...")
            process_unread_emails()
            print(f"Next check in {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\n\nStopping email automation system...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            print(f"Retrying in {CHECK_INTERVAL} seconds...")
            time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()