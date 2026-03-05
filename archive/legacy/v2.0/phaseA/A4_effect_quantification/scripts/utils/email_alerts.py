#!/usr/bin/env python3
"""
Email alert utility for AWS job monitoring.

Sends email notifications for job completion, errors, and progress milestones.

Setup:
    1. Create Gmail app password: https://myaccount.google.com/apppasswords
    2. Set environment variables:
       export EMAIL_USER="your-email@gmail.com"
       export EMAIL_PASSWORD="your-app-password"
       export EMAIL_RECIPIENT="your-email@gmail.com"

Usage:
    from utils.email_alerts import send_alert

    send_alert("Job Complete", "Backdoor adjustment finished in 32 hours")
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from typing import Optional
from datetime import datetime


def send_alert(
    subject: str,
    message: str,
    user: Optional[str] = None,
    password: Optional[str] = None,
    recipient: Optional[str] = None
) -> bool:
    """
    Send email alert via Gmail SMTP.

    Args:
        subject: Email subject line
        message: Email body (plaintext)
        user: Sender email (defaults to EMAIL_USER env var)
        password: Gmail app password (defaults to EMAIL_PASSWORD env var)
        recipient: Recipient email (defaults to EMAIL_RECIPIENT env var)

    Returns:
        True if email sent successfully, False otherwise
    """
    # Get credentials from environment if not provided
    user = user or os.environ.get('EMAIL_USER')
    password = password or os.environ.get('EMAIL_PASSWORD')
    recipient = recipient or os.environ.get('EMAIL_RECIPIENT')

    # Validate credentials
    if not all([user, password, recipient]):
        print("⚠️  Email credentials not configured - skipping alert")
        print("    Set EMAIL_USER, EMAIL_PASSWORD, EMAIL_RECIPIENT environment variables")
        return False

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = recipient
        msg['Subject'] = f"[A4 Backdoor] {subject}"

        # Add timestamp to message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = f"Timestamp: {timestamp}\n\n{message}"

        msg.attach(MIMEText(body, 'plain'))

        # Send via Gmail SMTP
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)

        print(f"✅ Email sent: {subject}")
        return True

    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


def send_job_started_alert(n_edges: int, cores: int):
    """Send alert when job starts."""
    subject = "Job Started"
    message = f"""
Backdoor adjustment job started.

Configuration:
- Total edges: {n_edges:,}
- CPU cores: {cores}
- Estimated runtime: 32-36 hours

You will receive alerts at 25%, 50%, 75% completion and when finished.
"""
    return send_alert(subject, message)


def send_progress_alert(completed: int, total: int, elapsed_hours: float):
    """Send progress milestone alert."""
    percent = 100 * completed / total
    subject = f"Progress: {percent:.0f}% Complete"
    message = f"""
Backdoor adjustment progress update:

Completed: {completed:,} / {total:,} edges ({percent:.1f}%)
Elapsed time: {elapsed_hours:.1f} hours
Estimated remaining: {elapsed_hours * (total - completed) / completed:.1f} hours
"""
    return send_alert(subject, message)


def send_job_complete_alert(n_edges: int, runtime_hours: float, mean_backdoor_size: float):
    """Send alert when job completes successfully."""
    subject = "✅ Job Complete"
    message = f"""
Backdoor adjustment completed successfully!

Results:
- Edges processed: {n_edges:,}
- Runtime: {runtime_hours:.1f} hours ({runtime_hours/24:.1f} days)
- Mean backdoor size: {mean_backdoor_size:.1f} variables

Next steps:
1. Download results from AWS
2. Verify locally
3. Terminate AWS instance

Output file: ~/outputs/full_backdoor_sets.pkl
"""
    return send_alert(subject, message)


def send_error_alert(error_message: str, edge_count: int):
    """Send alert when job encounters an error."""
    subject = "🚨 Job Error"
    message = f"""
Backdoor adjustment encountered an error!

Error: {error_message}

Progress at error:
- Edges completed: {edge_count:,}

Action required:
1. SSH into AWS instance
2. Check logs: ~/A4_effect_quantification/logs/
3. Resume from latest checkpoint if possible

Latest checkpoint: ~/A4_effect_quantification/checkpoints/
"""
    return send_alert(subject, message)


def send_spot_interruption_alert(edge_count: int):
    """Send alert when spot instance receives interruption warning."""
    subject = "⚠️ Spot Instance Interruption"
    message = f"""
AWS spot instance will be terminated in 2 minutes!

Auto-checkpoint saved at {edge_count:,} edges.

Action required:
1. Wait for instance termination
2. Launch new spot instance
3. Resume from checkpoint: ~/checkpoints/backdoor_checkpoint_{edge_count:08d}.pkl

Checkpoint will be automatically saved to S3 if configured.
"""
    return send_alert(subject, message)


def test_email_config():
    """Test email configuration by sending a test message."""
    subject = "Test Email"
    message = "This is a test email from the A4 backdoor adjustment monitoring system."
    return send_alert(subject, message)


if __name__ == "__main__":
    print("=" * 80)
    print("EMAIL ALERT CONFIGURATION TEST")
    print("=" * 80)
    print("")

    # Check environment variables
    user = os.environ.get('EMAIL_USER')
    password_set = 'EMAIL_PASSWORD' in os.environ
    recipient = os.environ.get('EMAIL_RECIPIENT')

    print(f"EMAIL_USER: {user or '(not set)'}")
    print(f"EMAIL_PASSWORD: {'*' * 16 if password_set else '(not set)'}")
    print(f"EMAIL_RECIPIENT: {recipient or '(not set)'}")
    print("")

    if not all([user, password_set, recipient]):
        print("❌ Email credentials not configured")
        print("")
        print("Setup instructions:")
        print("1. Create Gmail app password: https://myaccount.google.com/apppasswords")
        print("2. Set environment variables:")
        print("")
        print('   export EMAIL_USER="your-email@gmail.com"')
        print('   export EMAIL_PASSWORD="your-app-password"')
        print('   export EMAIL_RECIPIENT="your-email@gmail.com"')
        exit(1)

    # Send test email
    print("Sending test email...")
    success = test_email_config()

    if success:
        print("")
        print("✅ Email configuration successful!")
        print(f"Check {recipient} for test message")
        exit(0)
    else:
        print("")
        print("❌ Email test failed - check credentials and network connection")
        exit(1)
