"""Explicitly confirmed Jira delivery with a durable, fail-closed outbox."""
import base64
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import store


class JiraError(RuntimeError):
    pass


def configuration(user_id):
    site = os.getenv('KATALYST_JIRA_SITE', '').rstrip('/')
    project = os.getenv('KATALYST_JIRA_PROJECT_KEY', '')
    email = os.getenv('KATALYST_JIRA_EMAIL', '')
    token = os.getenv('KATALYST_JIRA_API_TOKEN', '')
    issue_type = os.getenv('KATALYST_JIRA_ISSUE_TYPE_ID', '')
    allowed = [value.strip() for value in os.getenv('KATALYST_JIRA_ALLOWED_UIDS', '').split(',') if value.strip()]
    if not all((site, project, email, token, issue_type)):
        raise JiraError('Jira is not configured. Ask the administrator to configure the site, project key, account email, API token and issue type ID.')
    if not re.fullmatch(r'https://[a-z0-9][a-z0-9-]*\.atlassian\.net', site):
        raise JiraError('Jira site must be an HTTPS *.atlassian.net site without paths, ports or credentials.')
    if not re.fullmatch(r'[A-Z][A-Z0-9_]*', project) or not issue_type.isdigit():
        raise JiraError('Jira project key or issue type ID is invalid.')
    if user_id not in allowed:
        raise JiraError('Your account is not authorized for the shared Jira integration. Ask the administrator to add your UID to KATALYST_JIRA_ALLOWED_UIDS.')
    return {'site': site, 'project_key': project, 'email': email, 'token': token, 'issue_type_id': issue_type}


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def plan(project, config):
    tickets = []
    for story in project['stories']:
        summary = f"{story['id']}: {story['goal']}"[:255]
        description = (
            f"KATALYST project: {project['id']} - {project['title']}\n"
            f"Story: {story['id']}\n"
            f"As a {story['role']}, I want {story['goal']} so that {story['benefit']}.\n\n"
            f"Requirements: {', '.join(story['requirement_ids'])}\n\nAcceptance criteria:\n"
            + '\n\n'.join(story['acceptance_criteria'])
        )
        identity = {'project_id': project['id'], 'story_id': story['id'],
                    'site': config['site'], 'project_key': config['project_key']}
        # A story ID maps to one ticket per destination, even if the story changes later.
        key = _hash(identity)
        content_hash = _hash({'summary': summary, 'description': description, 'issue_type_id': config['issue_type_id']})
        entry = store.jira_delivery(key)
        tickets.append({
            'delivery_id': key, 'story_id': story['id'], 'summary': summary, 'description': description,
            'content_hash': content_hash, 'status': entry['status'] if entry else 'new',
            'issue_key': entry.get('issue_key') if entry else None,
            'url': entry.get('url') if entry else None,
            'changed': bool(entry and entry['content_hash'] != content_hash),
            'error': entry.get('error') if entry else None,
        })
    snapshot = {'destination': {'site': config['site'], 'project_key': config['project_key'],
                                'issue_type_id': config['issue_type_id']},
                'versions': {key: project[key] for key in ('requirements_version', 'stories_version', 'prototype_version')},
                'tickets': [{key: ticket[key] for key in ('story_id', 'summary', 'description', 'content_hash')} for ticket in tickets]}
    return {**snapshot, 'tickets': tickets, 'fingerprint': _hash(snapshot)}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def create_issue(config, ticket):
    paragraphs = [{'type': 'paragraph', 'content': [{'type': 'text', 'text': line}]}
                  for line in ticket['description'].split('\n') if line]
    payload = {'fields': {'project': {'key': config['project_key']},
                          'issuetype': {'id': config['issue_type_id']},
                          'summary': ticket['summary'],
                          'description': {'type': 'doc', 'version': 1, 'content': paragraphs},
                          'labels': ['katalyst', 'katalyst-' + ticket['delivery_id']]}}
    credentials = base64.b64encode(f"{config['email']}:{config['token']}".encode()).decode()
    request = Request(config['site'] + '/rest/api/3/issue', data=json.dumps(payload).encode(),
                      headers={'Authorization': 'Basic ' + credentials, 'Content-Type': 'application/json',
                               'Accept': 'application/json'}, method='POST')
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise JiraError(f'Jira returned HTTP {exc.code}. Check permissions, issue type and required fields. This delivery is blocked until an administrator reconciles it; no automatic retry was made.') from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise JiraError('Jira delivery outcome is uncertain after a connection failure. Do not recreate manually until checking Jira for its KATALYST label.') from exc
    except (ValueError, UnicodeError) as exc:
        raise JiraError('Jira returned an unreadable response. Delivery is blocked pending reconciliation.') from exc
    key = result.get('key') if isinstance(result, dict) else None
    if not isinstance(key, str) or not re.fullmatch(re.escape(config['project_key']) + r'-\d+', key):
        raise JiraError('Jira returned no valid issue key for the configured project. Delivery is blocked pending reconciliation.')
    return key


def deliver(project, config, preview, actor, read_current):
    if any(ticket['status'] not in ('new', 'created') for ticket in preview['tickets']):
        raise JiraError('An earlier Jira delivery is pending or blocked. An administrator must reconcile it before continuing.')
    for ticket in preview['tickets']:
        if ticket['status'] == 'created':
            continue
        if ticket['status'] != 'new':
            raise JiraError('An earlier Jira delivery is pending or blocked. An administrator must reconcile it before continuing.')
        current = read_current()
        if plan(current, config)['fingerprint'] != preview['fingerprint']:
            raise JiraError('Approved artifacts changed during delivery. Refresh the preview; already created tickets are preserved.')
        entry = {'project_id': project['id'], 'story_id': ticket['story_id'], 'status': 'pending',
                 'content_hash': ticket['content_hash'], 'actor': actor,
                 'at': datetime.now(timezone.utc).isoformat(), 'site': config['site'],
                 'project_key': config['project_key'], 'versions': preview['versions']}
        if not store.claim_jira_delivery(ticket['delivery_id'], entry):
            raise JiraError('Another request already claimed this Jira ticket. Refresh to see its delivery status; no duplicate was sent.')
        try:
            key = create_issue(config, ticket)
        except JiraError as exc:
            entry.update(status='blocked', error=str(exc))
            store.finish_jira_delivery(ticket['delivery_id'], entry)
            raise
        entry.update(status='created', issue_key=key, url=config['site'] + '/browse/' + key)
        store.finish_jira_delivery(ticket['delivery_id'], entry)
    return plan(read_current(), config)
