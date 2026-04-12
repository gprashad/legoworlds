import jwt
from fastapi import Request, HTTPException
from src.config import SUPABASE_JWT_SECRET

# Dev bypass user — remove when Google SSO is wired up
DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


async def get_current_user(request: Request) -> dict:
    """Extract and verify Supabase JWT from Authorization header.
    Falls back to dev user if no token provided (temporary)."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        # TODO: remove dev bypass when auth is live
        return {"sub": DEV_USER_ID}

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
