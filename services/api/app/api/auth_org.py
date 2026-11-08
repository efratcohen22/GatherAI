import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import CurrentUser, create_user_with_org, hash_password, issue_local_token, verify_password
from app.core.config import Settings, get_settings
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.models import LocalCredential, Organization, OrganizationMember, User
from app.schemas.schemas import AddOrgMemberIn, LoginIn, MemberOut, MeOut, OrganizationOut, SignupIn, TokenOut

router = APIRouter(prefix="/api", tags=["auth"])
Db = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]


def _local_only(settings: Config) -> None:
    if settings.auth_mode != "local":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")


@router.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok"}


@router.get("/config", tags=["system"])
def public_config(settings: Config) -> dict:
    return {"auth_mode": settings.auth_mode, "ai_live": settings.ai_live, "environment": settings.app_env}


@router.post(
    "/auth/local/signup", response_model=TokenOut, status_code=201,
    dependencies=[Depends(_local_only), Depends(rate_limit("signup", 20))],
)
def local_signup(body: SignupIn, db: Db, settings: Config) -> TokenOut:
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = create_user_with_org(db, body.email, body.display_name)
    db.add(LocalCredential(user_id=user.id, password_hash=hash_password(body.password)))
    db.commit()
    return TokenOut(access_token=issue_local_token(user, settings))


@router.post(
    "/auth/local/login", response_model=TokenOut,
    dependencies=[Depends(_local_only), Depends(rate_limit("login", 30))],
)
def local_login(body: LoginIn, db: Db, settings: Config) -> TokenOut:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    credential = db.get(LocalCredential, user.id) if user else None
    if credential is None or not verify_password(body.password, credential.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return TokenOut(access_token=issue_local_token(user, settings))


def _organizations(db: Session, user: User) -> list[OrganizationOut]:
    rows = db.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == user.id, OrganizationMember.status == "active")
    ).all()
    return [OrganizationOut(id=o.id, name=o.name, role=role) for o, role in rows]


@router.get("/auth/me", response_model=MeOut)
def me(user: CurrentUser, db: Db) -> MeOut:
    return MeOut(id=user.id, email=user.email, display_name=user.display_name, organizations=_organizations(db, user))


@router.get("/organizations", response_model=list[OrganizationOut])
def organizations(user: CurrentUser, db: Db) -> list[OrganizationOut]:
    return _organizations(db, user)


def _membership(db: Session, user: User, organization_id: uuid.UUID) -> OrganizationMember:
    member = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id, OrganizationMember.user_id == user.id,
            OrganizationMember.status == "active",
        )
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    return member


@router.get("/organizations/{organization_id}", response_model=OrganizationOut)
def organization(organization_id: uuid.UUID, user: CurrentUser, db: Db) -> OrganizationOut:
    member = _membership(db, user, organization_id)
    org = db.get(Organization, organization_id)
    return OrganizationOut(id=org.id, name=org.name, role=member.role)


@router.get("/organizations/{organization_id}/members", response_model=list[MemberOut])
def organization_members(organization_id: uuid.UUID, user: CurrentUser, db: Db) -> list[MemberOut]:
    _membership(db, user, organization_id)
    rows = db.execute(
        select(User, OrganizationMember.role)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.organization_id == organization_id)
    ).all()
    return [MemberOut(user_id=u.id, email=u.email, display_name=u.display_name, role=role) for u, role in rows]


@router.post("/organizations/{organization_id}/members", response_model=MemberOut, status_code=201)
def add_organization_member(organization_id: uuid.UUID, body: AddOrgMemberIn, user: CurrentUser, db: Db) -> MemberOut:
    if _membership(db, user, organization_id).role != "organization_owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can add members")
    target = db.scalar(select(User).where(User.email == body.email.lower()))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No GatherAI account uses this email yet")
    if db.get(OrganizationMember, (organization_id, target.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Already a member")
    db.add(OrganizationMember(organization_id=organization_id, user_id=target.id, role=body.role))
    db.commit()
    return MemberOut(user_id=target.id, email=target.email, display_name=target.display_name, role=body.role)
