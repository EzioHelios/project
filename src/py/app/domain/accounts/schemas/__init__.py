"""Account domain schemas for users, auth, OAuth, roles, and password reset."""

from app.domain.accounts.schemas._auth import (
    AccountLogin,
    AccountRegister,
    HumanVerification,
    PasswordUpdate,
    PasswordVerify,
)
from app.domain.accounts.schemas._email_verification import (
    EmailVerificationConfirm,
    EmailVerificationRequest,
    EmailVerificationSent,
    EmailVerificationStatus,
)
from app.domain.accounts.schemas._mfa import (
    LoginMfaChallenge,
    MfaBackupCodes,
    MfaChallenge,
    MfaConfirm,
    MfaDisable,
    MfaSetup,
    MfaStatus,
    MfaVerifyResult,
)
from app.domain.accounts.schemas._oauth import OAuthAccountInfo, OAuthAuthorization
from app.domain.accounts.schemas._password_reset import (
    ForgotPasswordRequest,
    PasswordResetComplete,
    PasswordResetSent,
    ResetPasswordRequest,
    ResetTokenValidation,
    ValidateResetTokenRequest,
)
from app.domain.accounts.schemas._permissions import Permission, RolePermissionsUpdate
from app.domain.accounts.schemas._roles import Role, RoleCreate, RoleUpdate, UserRoleAdd, UserRoleRevoke
from app.domain.accounts.schemas._sessions import ActiveSession, TokenRefresh
from app.domain.accounts.schemas._user import (
    OauthAccount,
    ProfileUpdate,
    User,
    UserCreate,
    UserRole,
    UserTeam,
    UserUpdate,
)
from app.lib.schema import Message

__all__ = (
    "AccountLogin",
    "AccountRegister",
    "ActiveSession",
    "EmailVerificationConfirm",
    "EmailVerificationRequest",
    "EmailVerificationSent",
    "EmailVerificationStatus",
    "ForgotPasswordRequest",
    "HumanVerification",
    "LoginMfaChallenge",
    "Message",
    "MfaBackupCodes",
    "MfaChallenge",
    "MfaConfirm",
    "MfaDisable",
    "MfaSetup",
    "MfaStatus",
    "MfaVerifyResult",
    "OAuthAccountInfo",
    "OAuthAuthorization",
    "OauthAccount",
    "PasswordResetComplete",
    "PasswordResetSent",
    "PasswordUpdate",
    "PasswordVerify",
    "Permission",
    "ProfileUpdate",
    "ResetPasswordRequest",
    "ResetTokenValidation",
    "Role",
    "RoleCreate",
    "RolePermissionsUpdate",
    "RoleUpdate",
    "TokenRefresh",
    "User",
    "UserCreate",
    "UserRole",
    "UserRoleAdd",
    "UserRoleRevoke",
    "UserTeam",
    "UserUpdate",
    "ValidateResetTokenRequest",
)
