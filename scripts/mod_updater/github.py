"""GitHub release discovery and downloads with bounded retries."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import urllib.request
from pathlib import Path


class GitHub:
    def fetch(self, url: str, destination: Path | None = None):
        headers = {
            "User-Agent": "cs2-mod-updater",
            "Accept": "application/vnd.github+json",
        }
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=30) as response:
                    if destination is None:
                        return json.load(response)
                    with destination.open("wb") as output:
                        shutil.copyfileobj(response, output)
                    return
            except (OSError, ValueError) as error:
                if attempt == 2:
                    # Avoid logging potentially sensitive response bodies.
                    raise RuntimeError(
                        f"request failed ({type(error).__name__})"
                    ) from None
                time.sleep(attempt + 1)

    def download(self, asset: dict, destination: Path) -> None:
        """Download an asset and verify its size and optional SHA-256 digest."""
        self.fetch(asset["browser_download_url"], destination)
        name = asset["name"]
        if destination.stat().st_size != asset["size"]:
            raise ValueError(f"{name}: asset size mismatch")
        digest = asset.get("digest")
        if not digest:
            return
        if not digest.startswith("sha256:"):
            raise ValueError(f"{name}: unsupported asset digest")
        hasher = hashlib.sha256()
        with destination.open("rb") as data:
            for chunk in iter(lambda: data.read(1024 * 1024), b""):
                hasher.update(chunk)
        if digest != f"sha256:{hasher.hexdigest()}":
            raise ValueError(f"{name}: asset checksum mismatch")

    def latest(self, repository: str, tag_prefix: str = "") -> dict:
        """Select by publication date, including prereleases and excluding drafts."""
        releases = []
        page = 1
        while True:
            batch = self.fetch(
                f"https://api.github.com/repos/{repository}/releases?per_page=100&page={page}"
            )
            if not isinstance(batch, list):
                raise TypeError("invalid releases response")
            releases.extend(
                release
                for release in batch
                if not release.get("draft")
                and release.get("published_at")
                and release["tag_name"].startswith(tag_prefix)
            )
            if len(batch) < 100:
                break
            page += 1
        if not releases:
            raise ValueError("no published releases")
        return max(releases, key=lambda r: (r["published_at"], r["id"]))
