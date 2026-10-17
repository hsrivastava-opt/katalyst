"""Persistence adapter: SQLite for local demos, Firestore for hosted Google Cloud runs.

Use KATALYST_STORE=firestore on Cloud Run. All project queries are owner-filtered.
Artifact subcollections and transactional editing remain future milestones.
"""
import hashlib, json, logging, os, sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from urllib.parse import quote

LOCK = RLock()
logger = logging.getLogger(__name__)

class PersistenceError(RuntimeError):
    pass

@contextmanager
def cloud_operation():
    from google.api_core.exceptions import GoogleAPICallError
    from google.auth.exceptions import GoogleAuthError
    try:
        yield
    except (GoogleAPICallError, GoogleAuthError) as exc:
        logger.error('Firestore operation failed; check credentials, IAM, service access and document limits')
        raise PersistenceError('Project storage unavailable; check Firestore configuration, permissions and document limits') from exc

def _is_firestore():
    default = 'sqlite' if os.getenv('KATALYST_AUTH_MODE', 'firebase').lower() == 'demo' else 'firestore'
    value = os.getenv('KATALYST_STORE', default).lower()
    if value not in ('firestore', 'sqlite'):
        raise RuntimeError('KATALYST_STORE must be firestore or sqlite')
    return value == 'firestore'

def _path():
    path = Path(os.getenv('KATALYST_DB', str(Path(__file__).resolve().parents[2] / 'data' / 'katalyst.sqlite')))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def firestore_client():
    try:
        from google.cloud import firestore
    except ImportError as exc:
        raise RuntimeError('Firestore adapter requires google-cloud-firestore') from exc
    return firestore.Client(project=os.getenv('GOOGLE_CLOUD_PROJECT') or None)

def _collection():
    return firestore_client().collection(os.getenv('KATALYST_FIRESTORE_COLLECTION','katalyst_projects'))

def initialize():
    if _is_firestore():return
    with LOCK, sqlite3.connect(_path()) as db:
        db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, body TEXT NOT NULL, owner TEXT)')
        columns = {row[1] for row in db.execute('PRAGMA table_info(projects)')}
        if 'owner' not in columns:
            db.execute('ALTER TABLE projects ADD COLUMN owner TEXT')
            for pid, body in db.execute('SELECT id, body FROM projects').fetchall():
                db.execute('UPDATE projects SET owner=? WHERE id=?', (json.loads(body).get('owner'), pid))
        db.execute('CREATE INDEX IF NOT EXISTS projects_owner_updated ON projects(owner, updated_at)')
        db.execute('CREATE TABLE IF NOT EXISTS users (uid TEXT PRIMARY KEY, body TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS jira_deliveries (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, body TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS email_deliveries (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, body TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS voice_sessions (uid TEXT PRIMARY KEY, last_started REAL NOT NULL)')

def save(project):
    if _is_firestore():
        with cloud_operation():
            _collection().document(project['id']).set(project)
        return
    with LOCK, sqlite3.connect(_path()) as db:
        db.execute('INSERT INTO projects(id, updated_at, body, owner) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,body=excluded.body,owner=excluded.owner', (project['id'], project['updated_at'], json.dumps(project), project['owner']))

def get(project_id):
    if _is_firestore():
        with cloud_operation():
            snapshot=_collection().document(project_id).get()
            return snapshot.to_dict() if snapshot.exists else None
    with LOCK, sqlite3.connect(_path()) as db:
        result = db.execute('SELECT body FROM projects WHERE id=?',(project_id,)).fetchone()
    return json.loads(result[0]) if result else None

def all_projects(owner):
    if _is_firestore():
        from google.cloud.firestore_v1.base_query import FieldFilter
        with cloud_operation():
            documents = _collection().where(filter=FieldFilter('owner', '==', owner)).stream()
            return sorted((doc.to_dict() for doc in documents), key=lambda p: p['updated_at'], reverse=True)
    with LOCK, sqlite3.connect(_path()) as db:
        rows = db.execute('SELECT body FROM projects WHERE owner=? ORDER BY updated_at DESC', (owner,)).fetchall()
    return [json.loads(row[0]) for row in rows]


def save_user(profile):
    if _is_firestore():
        with cloud_operation():
            firestore_client().collection('users').document(quote(profile['uid'], safe='')).set(profile, merge=True)
        return
    with LOCK, sqlite3.connect(_path()) as db:
        db.execute('INSERT INTO users(uid, body) VALUES(?,?) ON CONFLICT(uid) DO UPDATE SET body=excluded.body',
                   (profile['uid'], json.dumps(profile)))


def jira_delivery(key):
    return delivery('jira', key)


def delivery(kind, key):
    if kind not in ('jira', 'email'):
        raise ValueError('Unknown delivery kind')
    if _is_firestore():
        with cloud_operation():
            snapshot = _collection().document(f'_{kind}_deliveries').collection('entries').document(key).get()
            return snapshot.to_dict() if snapshot.exists else None
    with LOCK, sqlite3.connect(_path()) as db:
        row = db.execute(f'SELECT body FROM {kind}_deliveries WHERE id=?', (key,)).fetchone()
    return json.loads(row[0]) if row else None


def claim_jira_delivery(key, entry):
    return claim_delivery('jira', key, entry)


def claim_delivery(kind, key, entry):
    """Reserve before external writes, across workers; ambiguous claims are never retried."""
    if kind not in ('jira', 'email'):
        raise ValueError('Unknown delivery kind')
    if _is_firestore():
        from google.api_core.exceptions import AlreadyExists
        with cloud_operation():
            try:
                _collection().document(f'_{kind}_deliveries').collection('entries').document(key).create(entry)
            except AlreadyExists:
                return False
        return True
    with LOCK, sqlite3.connect(_path()) as db:
        cursor = db.execute(f'INSERT OR IGNORE INTO {kind}_deliveries(id,project_id,body) VALUES(?,?,?)',
                            (key, entry['project_id'], json.dumps(entry)))
        return cursor.rowcount == 1


def finish_jira_delivery(key, entry):
    return finish_delivery('jira', key, entry)


def finish_delivery(kind, key, entry):
    if kind not in ('jira', 'email'):
        raise ValueError('Unknown delivery kind')
    if _is_firestore():
        with cloud_operation():
            _collection().document(f'_{kind}_deliveries').collection('entries').document(key).set(entry)
        return
    with LOCK, sqlite3.connect(_path()) as db:
        db.execute(f'UPDATE {kind}_deliveries SET body=? WHERE id=?', (json.dumps(entry), key))


def claim_voice_slot(uid, timestamp, cooldown):
    """One bounded cooldown record per identity, independent of project edits."""
    if _is_firestore():
        from google.cloud import firestore
        key = hashlib.sha256(uid.encode()).hexdigest()
        with cloud_operation():
            client = firestore_client()
            reference = client.collection(os.getenv('KATALYST_FIRESTORE_COLLECTION', 'katalyst_projects')).document(
                '_voice_sessions').collection('entries').document(key)

            @firestore.transactional
            def claim(transaction):
                snapshot = reference.get(transaction=transaction)
                if snapshot.exists and snapshot.to_dict()['last_started'] > timestamp - cooldown:
                    return False
                transaction.set(reference, {'last_started': timestamp})
                return True

            return claim(client.transaction())
    with LOCK, sqlite3.connect(_path()) as db:
        cursor = db.execute(
            'INSERT INTO voice_sessions(uid,last_started) VALUES(?,?) '
            'ON CONFLICT(uid) DO UPDATE SET last_started=excluded.last_started '
            'WHERE voice_sessions.last_started<=?',
            (uid, timestamp, timestamp - cooldown),
        )
        return cursor.rowcount == 1
