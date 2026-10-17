"""Firebase ID-token verification. Demo identity is explicit and never user-selectable."""
import logging
import os
from functools import lru_cache

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


def mode():
    value = os.getenv('KATALYST_AUTH_MODE', 'firebase').lower()
    if value not in ('firebase', 'demo'):
        raise RuntimeError('KATALYST_AUTH_MODE must be firebase or demo')
    return value


def public_config():
    return {
        'apiKey': os.getenv('KATALYST_FIREBASE_WEB_API_KEY', ''),
        'authDomain': os.getenv('KATALYST_FIREBASE_AUTH_DOMAIN', ''),
        'projectId': os.getenv('GOOGLE_CLOUD_PROJECT', ''),
        'appId': os.getenv('KATALYST_FIREBASE_WEB_APP_ID', ''),
    }


@lru_cache(maxsize=1)
def firebase_app():
    import firebase_admin
    project = os.getenv('GOOGLE_CLOUD_PROJECT')
    if not project:
        raise RuntimeError('Firebase authentication requires GOOGLE_CLOUD_PROJECT')
    return firebase_admin.initialize_app(options={'projectId': project}, name='katalyst-auth')


def initialize():
    if mode() == 'firebase':
        if os.getenv('FIREBASE_AUTH_EMULATOR_HOST'):
            raise RuntimeError('Firebase Auth emulator tokens are not accepted by this deployment')
        firebase_app()
    else:
        logger.warning('DEMO authentication enabled: one shared local identity, not real authentication')


def verify_token(token):
    from firebase_admin import auth
    return auth.verify_id_token(token, app=firebase_app(), check_revoked=True)


def authenticated_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if mode() == 'demo':
        return {'uid': 'demo-user', 'email': None, 'name': 'Local demo reviewer'}
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Sign in to access KATALYST', headers={'WWW-Authenticate': 'Bearer'})
    from firebase_admin import auth
    from firebase_admin.exceptions import FirebaseError
    from google.auth.exceptions import GoogleAuthError
    try:
        claims = verify_token(credentials.credentials)
    except auth.CertificateFetchError as exc:
        logger.error('Firebase signing certificate retrieval failed')
        raise HTTPException(503, 'Authentication service unavailable; try again later') from exc
    except (auth.InvalidIdTokenError, auth.RevokedIdTokenError, auth.UserDisabledError,
            auth.UserNotFoundError, ValueError) as exc:
        raise HTTPException(401, 'Session is invalid or expired; sign in again',
                            headers={'WWW-Authenticate': 'Bearer'}) from exc
    except (GoogleAuthError, FirebaseError) as exc:
        logger.error('Firebase authentication service or server credentials unavailable')
        raise HTTPException(503, 'Authentication service unavailable; check server credentials') from exc
    uid = claims.get('uid')
    if not isinstance(uid, str) or not uid or len(uid) > 128:
        raise HTTPException(401, 'Invalid authenticated identity')
    return {'uid': uid, 'email': claims.get('email'), 'name': claims.get('name', '')}


def current_user(user=Depends(authenticated_user)):
    return user['uid']
