from __future__ import annotations

import os
import secrets
import stat
import tempfile
from pathlib import Path, PurePosixPath

from ..config import Settings


class SecretRefError(ValueError):
    pass


def generate_password() -> str:
    return secrets.token_urlsafe(48)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validated_ref_parts(ref: str) -> tuple[str, ...]:
    if not ref or not ref.strip():
        raise SecretRefError("Secret ref is required.")
    if "\\" in ref:
        raise SecretRefError("Secret ref must use forward slashes only.")
    if ref.startswith("/") or ref.endswith("/") or "//" in ref:
        raise SecretRefError("Secret ref cannot contain empty or absolute path segments.")
    path = PurePosixPath(ref)
    if path.is_absolute():
        raise SecretRefError("Secret ref must be relative.")
    parts = path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise SecretRefError("Secret ref cannot contain empty or traversal segments.")
    return tuple(parts)


def _ensure_secrets_dir(settings: Settings) -> Path:
    secrets_dir = settings.secrets_dir
    secrets_dir.mkdir(parents=True, exist_ok=True)
    try:
        secrets_dir.chmod(0o700)
    except OSError:
        pass
    return secrets_dir


def _ensure_parent_components(secrets_dir: Path, base: Path, parts: tuple[str, ...]) -> None:
    current = secrets_dir
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise SecretRefError("Secret ref escapes the secrets directory.")
        if current.exists():
            resolved = current.resolve(strict=True)
            if not _is_relative_to(resolved, base):
                raise SecretRefError("Secret ref escapes the secrets directory.")
            if not current.is_dir():
                raise SecretRefError("Secret ref parent is not a directory.")
        else:
            parent_resolved = current.parent.resolve(strict=True)
            if not _is_relative_to(parent_resolved, base):
                raise SecretRefError("Secret ref escapes the secrets directory.")
            current.mkdir()
            try:
                current.chmod(0o700)
            except OSError:
                pass
            resolved = current.resolve(strict=True)
            if not _is_relative_to(resolved, base) or current.is_symlink():
                raise SecretRefError("Secret ref escapes the secrets directory.")


def resolve_secret_path(settings: Settings, ref: str, *, create_parent: bool = False) -> Path:
    parts = _validated_ref_parts(ref)
    secrets_dir = _ensure_secrets_dir(settings)
    base = secrets_dir.resolve(strict=True)
    path = secrets_dir.joinpath(*parts)

    if create_parent:
        _ensure_parent_components(secrets_dir, base, parts[:-1])

    resolved = path.resolve(strict=False)
    if not _is_relative_to(resolved, base):
        raise SecretRefError("Secret ref escapes the secrets directory.")
    return path


def secret_exists(settings: Settings, ref: str) -> bool:
    path = resolve_secret_path(settings, ref)
    return path.is_file()


def read_secret(settings: Settings, ref: str) -> str:
    path = resolve_secret_path(settings, ref)
    resolved = path.resolve(strict=True)
    base = settings.secrets_dir.resolve(strict=True)
    if not _is_relative_to(resolved, base):
        raise SecretRefError("Secret ref escapes the secrets directory.")
    return path.read_text(encoding="utf-8")


def write_secret(settings: Settings, ref: str, value: str) -> None:
    path = resolve_secret_path(settings, ref, create_parent=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            temp_path.chmod(0o600)
        except OSError:
            pass
        os.replace(temp_path, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except Exception:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def delete_secret(settings: Settings, ref: str) -> None:
    path = resolve_secret_path(settings, ref)
    try:
        stat_result = path.lstat()
    except FileNotFoundError:
        return

    if stat.S_ISLNK(stat_result.st_mode):
        raise SecretRefError("Secret ref escapes the secrets directory.")
    if not stat.S_ISREG(stat_result.st_mode):
        raise SecretRefError("Secret ref is not a file.")

    resolved = path.resolve(strict=True)
    base = settings.secrets_dir.resolve(strict=True)
    if not _is_relative_to(resolved, base):
        raise SecretRefError("Secret ref escapes the secrets directory.")

    path.unlink()


def read_or_create_secret(settings: Settings, ref: str) -> str:
    if secret_exists(settings, ref):
        return read_secret(settings, ref)
    password = generate_password()
    write_secret(settings, ref, password)
    return password
