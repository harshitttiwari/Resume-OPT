"""GitHub data fetching and repo analysis tools."""
from __future__ import annotations
import json
import io
import os
import re
import zipfile
from pathlib import Path # Path means the location where the PDF or DOCX file should be saved.
from typing import Any
from urllib.parse import urlparse # used to break a URL into parts
import requests
from dotenv import load_dotenv
from log import get_logger

load_dotenv()
log = get_logger(__name__)

CACHE_DIR = Path("cache")
GITHUB_API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json"}
_token = os.getenv("GITHUB_TOKEN")
if _token:
    HEADERS["Authorization"] = f"Bearer {_token}"

def extract_github_username(github_url: str) -> str:
    """
    Extract username from:
    - https://github.com/username
    - github.com/username
    - username
    - https://github.com/username?tab=repositories

    Reject repository URLs like:
    - https://github.com/username/repo
    """
    value = str(github_url or "").strip().rstrip("/")

    if not value:
        raise ValueError("GitHub URL is required.")

    # If user enters only username
    if "/" not in value and "github.com" not in value:
        username = value.lstrip("@").split("?")[0].split("#")[0].strip()
        if not re.match(r"^[A-Za-z0-9-]{1,39}$", username):
            raise ValueError("Invalid GitHub username format.")
        return username

    # urlparse needs scheme to parse netloc correctly
    if not value.startswith(("http://", "https://")):
        value = "https://" + value

    parsed = urlparse(value)

    if "github.com" not in parsed.netloc.lower():
        raise ValueError("Please enter a valid GitHub profile URL.")

    parts = [p for p in parsed.path.split("/") if p]

    if not parts:
        raise ValueError("GitHub username not found in URL.")

    if len(parts) > 1:
        raise ValueError("Please enter a GitHub profile URL, not a repository URL.")

    username = parts[0].strip().lstrip("@")

    if not re.match(r"^[A-Za-z0-9-]{1,39}$", username):
        raise ValueError("Invalid GitHub username format.")

    return username

def _cache_path(key: str) -> Path:
    """creates a safe file path for storing cached data as a JSON file"""
    CACHE_DIR.mkdir(exist_ok=True)
    safe = re.sub(r"[^a-z0-9_-]", "_", key.lower())
    return CACHE_DIR / f"{safe}.json"

def _load_cache(key: str) -> dict | None:
    path = _cache_path(key)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return None
    return None

def _save_cache(key: str, data: Any) -> None:
    _cache_path(key).write_text(json.dumps(data, indent=2))

def fetch_github_profile(github_url: str) -> dict[str, Any]:
    username = extract_github_username(github_url)
    cache_key = f"profile_{username}"
    cached = _load_cache(cache_key)
    if cached:
        log.info(f"GitHub profile loaded from cache: {username}")
        return cached

    log.info(f"Fetching GitHub profile: {username}")
    resp = requests.get(f"{GITHUB_API}/users/{username}", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    profile = {
        "username":   data.get("login", ""),
        "name":       data.get("name", ""),
        "bio":        data.get("bio", ""),
        "location":   data.get("location", ""),
        "blog":       data.get("blog", ""),
        "public_repos": data.get("public_repos", 0),
        "followers":  data.get("followers", 0),
        "github_url": github_url,
    }
    _save_cache(cache_key, profile)
    return profile

def fetch_github_repos(github_url: str, max_repos: int = 30) -> list[dict[str, Any]]:
    username = extract_github_username(github_url)
    cache_key = f"repos_{username}"
    cached = _load_cache(cache_key)
    if cached:
        log.info(f"GitHub repos loaded from cache: {username} ({len(cached)} repos)")
        return cached

    log.info(f"Fetching GitHub repos: {username}")
    repos, page = [], 1
    while len(repos) < max_repos:
        resp = requests.get(
            f"{GITHUB_API}/users/{username}/repos",
            headers=HEADERS,
            params={"per_page": 30, "page": page, "sort": "updated"},
            timeout=10,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1

    result = [
        {
            "name":        r.get("name", ""),
            "description": r.get("description", "") or "",
            "language":    r.get("language", "") or "",
            "topics":      r.get("topics", []),
            "stars":       r.get("stargazers_count", 0),
            "forks":       r.get("forks_count", 0),
            "url":         r.get("html_url", ""),
            "updated_at":  r.get("updated_at", ""),
            "is_fork":     r.get("fork", False),
        }
        for r in repos[:max_repos]
        if not r.get("fork", False)  # skip forks
    ]
    _save_cache(cache_key, result)
    return result

def fetch_readme(github_url: str, repo_name: str) -> str:
    username = extract_github_username(github_url)
    cache_key = f"readme_{username}_{repo_name}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached.get("content", "")

    try:
        resp = requests.get(
            f"{GITHUB_API}/repos/{username}/{repo_name}/readme",
            headers={**HEADERS, "Accept": "application/vnd.github.raw"},
            timeout=10,
        )
        if resp.status_code == 404:
            _save_cache(cache_key, {"content": ""})
            return ""
        resp.raise_for_status()
        content = resp.text[:6000]  # cap at 6K chars
        _save_cache(cache_key, {"content": content})
        return content
    except Exception:
        return ""

def parse_linkedin_zip(zip_bytes: bytes) -> dict:
    """Extract profile data from LinkedIn data export ZIP."""
    result = {"experience": [], "education": [], "certifications": [], "skills": []}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            names = z.namelist()
            for fname in names:
                if fname.endswith("/"):
                    continue
                content = z.read(fname).decode("utf-8", errors="ignore")
                if "Experience" in fname:
                    result["experience_raw"] = content[:3000]
                elif "Education" in fname:
                    result["education_raw"] = content[:2000]
                elif "Certifications" in fname:
                    result["certifications_raw"] = content[:2000]
                elif "Skills" in fname:
                    result["skills_raw"] = content[:1000]
    except Exception as e:
        result["error"] = str(e)
    return result