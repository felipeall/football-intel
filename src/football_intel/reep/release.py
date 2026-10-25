"""Reep's published releases: which is current, what changed, and downloading one.

Releases live at `data.reep.football/releases/<stamp>/`, each with a manifest holding the
files' SHA-256 checksums, the release's quality gates and a diff from its predecessor.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "https://data.reep.football/releases"
TIMEOUT = httpx.Timeout(60.0, connect=10.0)
FILES = ("bridges.parquet", "redirects.parquet")
MANIFEST = "manifest.json"
# The chain from the current release back to the pinned one is followed at most this far.
MAX_CHAIN = 100


class ChecksumMismatchError(Exception):
    """A downloaded file does not match the release manifest's checksum."""


@dataclass(frozen=True)
class Manifest:
    release: str
    data: dict[str, Any]

    @property
    def checksums(self) -> dict[str, str]:
        return self.data["checksums_sha256"]

    @property
    def gate_passed(self) -> bool | None:
        return self.data.get("gates", {}).get("gate_passed")

    @property
    def previous(self) -> str | None:
        return self.data.get("diff", {}).get("previous_label")

    @property
    def new_bridges(self) -> dict[str, int]:
        return self.data.get("diff", {}).get("new_bridges_by_provider", {})


def client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE_URL, transport=transport, timeout=TIMEOUT)


async def latest_release(api: httpx.AsyncClient) -> str:
    """The stamp of the release Reep currently publishes."""
    response = await api.get("/latest.json")
    response.raise_for_status()
    return response.json()["stamp"]


async def fetch_manifest(api: httpx.AsyncClient, release: str) -> Manifest:
    response = await api.get(f"/{release}/{MANIFEST}")
    response.raise_for_status()
    return Manifest(release, response.json())


async def releases_since(api: httpx.AsyncClient, pinned: str) -> list[Manifest]:
    """The manifests of the releases after `pinned`, newest first, up to the current one.

    Each manifest names its predecessor, so the chain is followed back from the current
    release until `pinned`, a gap, or `MAX_CHAIN` releases.
    """
    manifests: list[Manifest] = []
    release: str | None = await latest_release(api)
    while release is not None and release != pinned and len(manifests) < MAX_CHAIN:
        manifest = await fetch_manifest(api, release)
        manifests.append(manifest)
        release = manifest.previous
    return manifests


async def download(api: httpx.AsyncClient, release: str, directory: Path) -> Manifest:
    """Download a release's manifest and files into `directory`, verifying each file.

    A file already there with the right checksum is not downloaded again. A download goes to
    a temporary file, renamed into place only once its checksum matches, so an interrupted
    or corrupt download never looks like a valid file.
    """
    directory.mkdir(parents=True, exist_ok=True)
    manifest = await fetch_manifest(api, release)
    (directory / MANIFEST).write_text(_json(manifest.data))
    for name in FILES:
        target = directory / name
        expected = manifest.checksums[name]
        if target.exists() and sha256(target) == expected:
            continue
        partial = directory / f"{name}.partial"
        async with api.stream("GET", f"/{release}/{name}") as response:
            response.raise_for_status()
            with partial.open("wb") as file:
                async for chunk in response.aiter_bytes():
                    file.write(chunk)
        actual = sha256(partial)
        if actual != expected:
            partial.unlink()
            raise ChecksumMismatchError(
                f"{name} of {release}: sha256 {actual}, manifest says {expected}"
            )
        partial.replace(target)
    return manifest


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)
