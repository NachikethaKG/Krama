"""Phase 3 research check: Fernet / DPAPI round trips, argon2 cost, token sizes, GitHub logged-out signals."""

import asyncio
import hashlib
import json
import secrets
import time

import win32crypt
from argon2 import PasswordHasher
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from playwright.async_api import async_playwright


async def github_logged_out():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto("https://github.com/", wait_until="domcontentloaded")
        meta = await page.locator('meta[name="user-login"]').get_attribute("content")
        resp = await page.goto("https://github.com/settings/profile", wait_until="domcontentloaded")
        final = page.url
        state = await ctx.storage_state()
        await browser.close()
    names = sorted({(c["name"], c["httpOnly"], c["secure"]) for c in state["cookies"]})
    logged_in = [c["value"] for c in state["cookies"] if c["name"] == "logged_in"]
    print("github / meta user-login:", repr(meta))
    print("/settings/profile ->", resp.status, final.split("?")[0])
    print("cookies (name, httpOnly, secure):", names)
    print("logged_in cookie:", logged_in, "| storage_state keys:", sorted(state), "| origins:", len(state["origins"]))
    return state


def main():
    state = asyncio.run(github_logged_out())
    blob = json.dumps(state).encode()
    print(f"storage_state JSON size: {len(blob)} bytes")

    # Fernet
    k1, k2 = Fernet.generate_key(), Fernet.generate_key()
    t0 = time.perf_counter()
    token = Fernet(k1).encrypt(blob)
    assert Fernet(k1).decrypt(token) == blob
    print(f"Fernet round trip ok ({(time.perf_counter() - t0) * 1000:.2f} ms), key len {len(k1)}, token {len(token)} bytes")
    rotated = MultiFernet([Fernet(k2), Fernet(k1)]).rotate(token)
    assert Fernet(k2).decrypt(rotated) == blob
    try:
        Fernet(k1).decrypt(rotated)
    except InvalidToken:
        print("MultiFernet.rotate: new key decrypts, old key alone no longer does")
    try:
        Fernet(k1).decrypt(token, ttl=0) if time.sleep(1.1) is None else None
    except InvalidToken:
        print("decrypt(ttl=0) after 1 s -> InvalidToken (age check works)")

    # DPAPI
    protected = win32crypt.CryptProtectData(k1, "krama-storage-key", None, None, None, 0)
    _desc, plain = win32crypt.CryptUnprotectData(protected, None, None, None, 0)
    assert plain == k1
    print(f"DPAPI round trip ok (current Windows user), {len(protected)} bytes")

    # argon2 defaults on this laptop
    ph = PasswordHasher()
    print(f"argon2 params: t={ph.time_cost} m={ph.memory_cost}KiB p={ph.parallelism}")
    h = ph.hash("correct horse battery staple")
    t0 = time.perf_counter()
    for _ in range(5):
        ph.verify(h, "correct horse battery staple")
    print(f"argon2 verify: {(time.perf_counter() - t0) / 5 * 1000:.1f} ms each; hash prefix {h[:30]}")
    print("needs rehash:", ph.check_needs_rehash(h))

    # tokens
    tok = secrets.token_urlsafe(32)
    print(f"token_urlsafe(32): {len(tok)} chars; sha256 hex {len(hashlib.sha256(tok.encode()).hexdigest())} chars")


if __name__ == "__main__":
    main()
