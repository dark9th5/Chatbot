from __future__ import annotations

import os
from urllib.parse import urlparse

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_admin.utils.auth import (
    ACCESS_TOKEN_EXPIRE_SECONDS,
    JWT_COOKIE_NAME,
    authenticate_admin,
    create_access_token,
    get_current_admin,
)


router = APIRouter()
templates = Jinja2Templates(directory="web_admin/templates")


def _safe_next_path(next_path: str | None) -> str:
    if not next_path:
        return "/"
    parsed = urlparse(next_path)
    if parsed.scheme or parsed.netloc:
        return "/"
    return next_path if next_path.startswith("/") else "/"


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/"):
    if get_current_admin(request):
        return RedirectResponse(url=_safe_next_path(next), status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "next": _safe_next_path(next),
            "error": None,
        },
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    user = authenticate_admin(username.strip(), password)
    safe_next = _safe_next_path(next)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "next": safe_next,
                "error": "Sai tài khoản hoặc mật khẩu.",
            },
            status_code=401,
        )

    token = create_access_token(user["username"])
    response = RedirectResponse(url=safe_next, status_code=303)
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_SECONDS,
        httponly=True,
        secure=os.getenv("ADMIN_COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(JWT_COOKIE_NAME)
    return response
