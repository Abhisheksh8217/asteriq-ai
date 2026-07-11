"""
services/auth_service.py
------------------------
Handles secure user registration, password verification, and authentication token middleware.
Uses PBKDF2-HMAC-SHA256 for secure hashing to remain lightweight and dependency-free.
"""

import hashlib
import os
import re
import functools
import threading
from flask import request, jsonify
from typing import Optional, Tuple
from database import create_user, get_user, create_token, get_email_by_token, delete_token
from services.email_service import email_service
from logger import get_logger

logger = get_logger(__name__)

# PBKDF2 Config
ITERATIONS = 100000
KEY_LEN = 32
SALT_SIZE = 16

# Email Format Regex validation
EMAIL_REGEX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

class AuthService:
    """
    Service containing logic for secure password verification and token authentication.
    """

    def hash_password(self, password: str) -> str:
        """
        Hashes a plain-text password using PBKDF2 with a secure random salt.
        Returns format: salt_hex:hash_hex
        """
        salt = os.urandom(SALT_SIZE)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            ITERATIONS,
            dklen=KEY_LEN
        )
        return f"{salt.hex()}:{key.hex()}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        """
        Verifies a plain-text password against a stored hashed password.
        """
        try:
            salt_hex, hash_hex = stored_hash.split(":")
            salt = bytes.fromhex(salt_hex)
            target_hash = bytes.fromhex(hash_hex)
            
            key = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt,
                ITERATIONS,
                dklen=KEY_LEN
            )
            return key == target_hash
        except Exception as e:
            logger.error("Password verification error: %s", e)
            return False

    def register(self, email: str, password: str, name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Registers a new user after checking for email uniqueness and formatting.
        """
        email = email.strip().lower()
        if not email or not password:
            return False, "Email and password cannot be empty."

        if not EMAIL_REGEX.match(email):
            return False, "Please enter a valid email address (e.g. name@domain.com)."

        existing = get_user(email)
        if existing:
            return False, "An account with this email address already exists."

        try:
            password_hash = self.hash_password(password)
            create_user(email, password_hash, name=name)
            
            # Send welcome email asynchronously in the background to prevent response blocking
            logger.info("Scheduling welcome email dispatch for: %s", email)
            threading.Thread(
                target=email_service.send_welcome_email,
                args=(email,),
                daemon=True
            ).start()
            
            return True, "User registered successfully."
        except Exception as e:
            logger.error("User registration failed: %s", e)
            return False, f"Registration failed due to a database error: {e}"

    def login(self, email: str, password: str) -> Tuple[Optional[str], str]:
        """
        Logs in a user, returning a secure session token if successful.
        """
        email = email.strip().lower()
        user = get_user(email)
        if not user:
            return None, "Invalid email or password."

        if self.verify_password(password, user["password_hash"]):
            # Generate a new token
            token = create_token(email)
            return token, "Login successful."
        else:
            return None, "Invalid email or password."

    def logout(self, token: str) -> None:
        """
        Invalidates a session token.
        """
        delete_token(token)


# Singleton instance
auth_service = AuthService()


def token_required(f):
    """
    Decorator for Flask routes that requires a valid Authorization header.
    Injects the authenticated `current_user` email into the route.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Retrieve token from Authorization header
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Authorization token is missing."}), 401

        current_user = get_email_by_token(token)
        if not current_user:
            return jsonify({"error": "Authorization token is invalid or has expired."}), 401

        # Pass current_user email to the Flask route
        return f(current_user, *args, **kwargs)

    return decorated
