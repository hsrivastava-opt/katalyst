"""Optional, revisioned SRS documents; prototype gates remain independent."""
import io
import json
from html import escape

import fitz

from .models import SRSDocument

SECTIONS = [
    ('purpose', 'Purpose and stakeholders'),
    ('scope', 'Scope and boundaries'),
    ('functional', 'Functional requirements'),
    ('non_functional', 'Non-functional requirements'),
    ('interfaces', 'External interfaces'),
    ('data', 'Data requirements'),
    ('assumptions', 'Assumptions, conflicts and open questions'),
    ('acceptance', 'Acceptance and verification'),
]
MAX_REVISIONS = 10
MAX_HISTORY_BYTES = 400_000


def validate(document: SRSDocument, project: dict) -> None:
    if [section.id for section in document.sections] != [key for key, _ in SECTIONS]:
        raise ValueError('SRS must contain all eight sections in the documented order')
    if sum(len(section.content) for section in document.sections) > 24_000:
        raise ValueError('SRS section content exceeds the 24000-character document limit')
    requirements = {r['id'] for r in project['requirements']}
    sources = {s['id'] for s in project['sources']}
    covered = set()
    for section in document.sections:
        if not set(section.requirement_ids).issubset(requirements):
            raise ValueError(f'SRS section {section.id} references nonexistent requirements')
        if not set(section.source_ids).issubset(sources):
            raise ValueError(f'SRS section {section.id} references nonexistent sources')
        covered.update(section.requirement_ids)
    if covered != requirements:
        raise ValueError('SRS must link every approved requirement in at least one section')


def invalidate(project: dict) -> None:
    project['srs'] = None
    project['srs_approval'] = None


def check_capacity(project: dict, revision: dict | None = None) -> None:
    history = project.get('srs_revisions', [])
    if len(history) >= MAX_REVISIONS:
        raise ValueError('SRS revision limit reached (10 per project). Existing revisions are preserved; further saves/generation are blocked.')
    if revision and len(json.dumps([*history, revision], ensure_ascii=False).encode('utf-8')) > MAX_HISTORY_BYTES:
        raise ValueError('SRS history storage limit reached (400 KB). Existing revisions are preserved; no revision was saved.')


def append_revision(project: dict, document: SRSDocument, provider: str, actor: str, timestamp: str) -> None:
    revision = {
        'version': project.get('srs_version', 0) + 1,
        'requirements_version': project['requirements_version'],
        'document': document.model_dump(), 'provider': provider,
        'actor': actor, 'at': timestamp,
    }
    check_capacity(project, revision)
    project.setdefault('srs_revisions', []).append(revision)
    project['srs'] = revision
    project['srs_version'] = revision['version']
    project['srs_approval'] = None


def pdf(project: dict) -> bytes:
    revision = project['srs']
    document = revision['document']
    approval = project['srs_approval']
    paragraphs = [
        '<h1>' + escape(document['title']) + '</h1>',
        '<p>Software Requirements Specification</p>',
        f"<p>Project: {escape(project['id'])}<br>Revision: {revision['version']}<br>"
        f"Requirements version: {revision['requirements_version']}<br>"
        f"Authoring provider: {escape(revision['provider'])}<br>"
        f"Approved by: {escape(approval['reviewer'])}<br>Approved at: {escape(approval['at'])}</p>",
    ]
    for section in document['sections']:
        paragraphs.extend([
            '<h2>' + escape(section['title']) + '</h2>',
            '<p>' + escape(section['content']).replace('\n', '<br>') + '</p>',
            '<p class="references">Requirements: ' + escape(', '.join(section['requirement_ids']) or 'None linked')
            + '<br>Sources: ' + escape(', '.join(section['source_ids']) or 'Not specified') + '</p>',
        ])
    # Story paginates escaped text and embeds fallback fonts rather than executing document markup.
    story = fitz.Story(html=''.join(paragraphs), user_css='body {font-size:11pt;} h2 {font-size:15pt;} .references {font-size:9pt;color:#444;}')
    buffer = io.BytesIO()
    with fitz.DocumentWriter(buffer) as writer:
        story.write(writer, lambda number, filled: (fitz.Rect(0, 0, 595, 842), fitz.Rect(45, 45, 550, 790), None))
    with fitz.open(stream=buffer.getvalue(), filetype='pdf') as output:
        for index, page in enumerate(output):
            page.insert_text((45, 815), f'KATALYST | SRS revision {revision["version"]} | Page {index+1}/{len(output)}', fontsize=8)
        return output.tobytes()
