"""Explicit, snapshot-bound SMTP handoff with a durable no-blind-retry ledger."""
import hashlib
import json
import logging
import os
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage

from fastapi import HTTPException

from . import auth, store

logger = logging.getLogger(__name__)


def address(value):
    if not isinstance(value, str) or len(value) > 254 or not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}", value
    ):
        raise HTTPException(422, 'Enter plain email addresses without display names or line breaks')
    return value


def configuration(user_id):
    allowed = os.getenv('KATALYST_EMAIL_ALLOWED_UIDS', '').split(',')
    if user_id not in {uid.strip() for uid in allowed if uid.strip()}:
        raise HTTPException(403, 'Your account is not authorized to use the shared email sender')
    values = {key: os.getenv('KATALYST_SMTP_' + key, '').strip()
              for key in ('HOST', 'PORT', 'USER', 'PASSWORD', 'FROM', 'SECURITY')}
    values['PASSWORD'] = os.getenv('KATALYST_SMTP_PASSWORD', '')
    if not all(values.values()):
        raise HTTPException(409, 'Email sender is not configured; ask the administrator to configure SMTP')
    if values['SECURITY'] not in ('ssl', 'starttls') or not values['PORT'].isdigit() or not 1 <= int(values['PORT']) <= 65535:
        raise HTTPException(409, 'SMTP requires a valid port and SECURITY ssl or starttls')
    if re.search(r'[\s/\\]', values['HOST']):
        raise HTTPException(409, 'SMTP host must be a hostname without a URL or path')
    try:
        address(values['FROM'])
    except HTTPException as exc:
        raise HTTPException(409, 'SMTP FROM must be a plain email address') from exc
    return values


def registered_recipient(email):
    if auth.mode() != 'firebase':
        raise HTTPException(409, 'Registered-recipient email requires Firebase authentication; demo mode cannot send')
    from firebase_admin import auth as firebase_auth
    from firebase_admin.exceptions import FirebaseError
    from google.auth.exceptions import GoogleAuthError
    try:
        user = firebase_auth.get_user_by_email(email, app=auth.firebase_app())
    except firebase_auth.UserNotFoundError as exc:
        raise HTTPException(422, 'Every recipient must have an active registered KATALYST account') from exc
    except (FirebaseError, GoogleAuthError, ValueError) as exc:
        logger.error('Registered email recipient verification unavailable')
        raise HTTPException(503, 'Recipient verification unavailable; check Firebase Admin configuration') from exc
    if user.disabled or not user.email:
        raise HTTPException(422, 'Every recipient must have an active registered KATALYST account')
    return {'uid': user.uid, 'email': address(user.email)}


def preview(project, draft, files, config):
    if '\r' in draft.subject or '\n' in draft.subject:
        raise HTTPException(422, 'Email subject must be a single line')
    recipients = [registered_recipient(address(email)) for email in draft.recipients]
    recipients = sorted({item['uid']: item for item in recipients}.values(), key=lambda item: item['uid'])
    attachment = f"KATALYST-{project['id']}-handoff.zip"
    payload = {'project_id': project['id'], 'owner': project['owner'], 'recipients': recipients,
               'subject': draft.subject, 'body': draft.body, 'from': config['FROM'],
               'smtp_host': config['HOST'], 'smtp_user': config['USER'], 'smtp_port': config['PORT'],
               'smtp_security': config['SECURITY'], 'files': files}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    entry = store.delivery('email', fingerprint)
    return {'fingerprint': fingerprint, 'from_email': config['FROM'],
            'recipients': [item['email'] for item in recipients], 'subject': draft.subject,
            'body': draft.body, 'attachment': attachment, 'attachment_entries': list(files),
            'status': entry['status'] if entry else 'new',
            'at': entry.get('at') if entry else None, 'error': entry.get('error') if entry else None}


def send_smtp(config, plan, archive):
    message = EmailMessage()
    message['From'] = config['FROM']
    message['To'] = 'undisclosed-recipients:;'
    message['Subject'] = plan['subject']
    message['Message-ID'] = f"<katalyst-{plan['fingerprint']}@{config['FROM'].split('@')[1]}>"
    message.set_content(plan['body'])
    message.add_attachment(archive, maintype='application', subtype='zip', filename=plan['attachment'])
    if len(message.as_bytes()) > 20_000_000:
        raise HTTPException(413, 'Email exceeds the 20 MB encoded message limit')
    context = ssl.create_default_context()
    try:
        connection = (smtplib.SMTP_SSL(config['HOST'], int(config['PORT']), timeout=30, context=context)
                      if config['SECURITY'] == 'ssl' else smtplib.SMTP(config['HOST'], int(config['PORT']), timeout=30))
        with connection as smtp:
            if config['SECURITY'] == 'starttls':
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
            smtp.login(config['USER'], config['PASSWORD'])
            refused = smtp.send_message(message, from_addr=config['FROM'], to_addrs=plan['recipients'])
            if refused:
                raise smtplib.SMTPException('Some recipients were refused')
    except (smtplib.SMTPException, OSError) as exc:
        logger.error('SMTP handoff failed or has an uncertain outcome; delivery requires reconciliation')
        raise HTTPException(502, 'Email outcome is uncertain or failed. Ask an administrator to check the SMTP provider before any resend.') from exc


def deliver(project, config, plan, archive, user_id, check_current):
    key = plan['fingerprint']
    entry = {'project_id': project['id'], 'actor': user_id, 'status': 'pending',
             'recipients': plan['recipients'], 'subject': plan['subject'], 'error': None,
             'at': datetime.now(timezone.utc).isoformat()}
    if not store.claim_delivery('email', key, entry):
        saved = store.delivery('email', key)
        if saved and saved['status'] == 'sent':
            return {**plan, 'status': 'sent', 'at': saved['at']}
        raise HTTPException(409, 'This email delivery is pending or blocked. An administrator must reconcile it; do not change the draft to bypass this safeguard.')
    try:
        check_current()
        send_smtp(config, plan, archive)
    except HTTPException as exc:
        entry.update(status='blocked', error=exc.detail)
        store.finish_delivery('email', key, entry)
        raise
    entry.update(status='sent', at=datetime.now(timezone.utc).isoformat())
    store.finish_delivery('email', key, entry)
    return {**plan, 'status': 'sent', 'at': entry['at']}
