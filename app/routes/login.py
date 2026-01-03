from fastapi import Cookie, Response

@app.post("/login")
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    access_token: str | None = Cookie(None),
    refresh_token: str | None = Cookie(None),
):
    # 1️⃣ If already logged in
    if access_token:
        try:
            jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
            return {"msg": "Already logged in"}
        except JWTError:
            pass

    # 2️⃣ Refresh token flow
    if refresh_token:
        try:
            payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload["sub"]

            new_access = create_access_token(
                email, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            )

            response.set_cookie(
                "access_token", new_access,
                httponly=True, samesite="lax"
            )

            return {"msg": "Token refreshed"}
        except JWTError:
            pass

    # 3️⃣ Normal login
    email = form_data.username
    password = form_data.password

    user = users_collection.find_one({"email": email})
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access = create_access_token(email, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh = create_refresh_token(email)

    response.set_cookie("access_token", access, httponly=True, samesite="lax")
    response.set_cookie("refresh_token", refresh, httponly=True, samesite="lax")

    return {"msg": "Login successful"}
