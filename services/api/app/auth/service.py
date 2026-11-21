"""Token verification and identity. Both auth modes end in the same `User` row."""
import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.models import Organization, OrganizationMember, User, utcnow

bearer = HTTPBearer(auto_error=False)
_jwks_client: jwt.PyJWKClient | None = None
LOCAL_ISSUER = "gatherai-local"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    salt_b64, digest_b64 = stored.split("$", 1)
    digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=2**14, r=8, p=1)
    return hmac.compare_digest(digest, base64.b64decode(digest_b64))


def issue_local_token(user: User, settings: Settings) -> str:
    now = utcnow()
    return jwt.encode(
        {"sub": str(user.id), "email": user.email, "iss": LOCAL_ISSUER, "iat": now, "exp": now + timedelta(hours=12)},
        settings.local_jwt_secret,
        algorithm="HS256",
    )


def _decode(token: str, settings: Settings) -> dict:
    if settings.auth_mode == "local":
        return jwt.decode(
            token, settings.local_jwt_secret, algorithms=["HS256"], issuer=LOCAL_ISSUER, options={"require": ["exp", "sub"]}
        )
    if settings.supabase_jwt_secret:
        return jwt.decode(
            token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated",
            issuer=f"{settings.supabase_url}/auth/v1", options={"require": ["exp", "sub"]},
        )
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", cache_keys=True)
    key = _jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token, key.key, algorithms=["ES256", "RS256"], audience="authenticated",
        issuer=f"{settings.supabase_url}/auth/v1", options={"require": ["exp", "sub"]},
    )


def create_user_with_org(db: Session, email: str, display_name: str, user_id: uuid.UUID | None = None) -> User:
    user = User(id=user_id or uuid.uuid4(), email=email.lower(), display_name=display_name)
    db.add(user)
    db.flush()
    org = Organization(name=f"{display_name}'s organization", owner_user_id=user.id)
    db.add(org)
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="organization_owner"))
    return user


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    if credentials is None:
        raise unauthorized
    try:
        claims = _decode(credentials.credentials, settings)
        user_id = uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise unauthorized from exc
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        if settings.auth_mode != "supabase" or not claims.get("email"):
            raise unauthorized
        email = claims["email"].lower()
        if db.scalar(select(User.id).where(User.email == email)):
            # Another account already owns this email. Never merge identities silently.
            raise HTTPException(status.HTTP_409_CONFLICT, "This email is linked to a different account. Contact support.")
        name = (claims.get("user_metadata") or {}).get("display_name") or email.split("@")[0]
        user = create_user_with_org(db, email, name, user_id)
        db.commit()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
