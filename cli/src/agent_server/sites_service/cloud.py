"""FastFold Sites publishing boundary and HTTP adapter."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class PublishedSite:
    url: str
    site_id: str | None = None


class SitesPublisher(Protocol):
    def publish(
        self,
        *,
        artifact: Path,
        name: str,
        local_site_id: str,
        content_sha256: str,
        expanded_size_bytes: int,
        file_count: int,
        slug: str | None = None,
        cloud_site_id: str | None = None,
    ) -> PublishedSite: ...


class FastFoldSitesClient:
    """Publish a ZIP through the FastFold Sites control-plane workflow."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        endpoint: str | None = None,
        timeout: float = 300,
    ) -> None:
        self.api_key = (api_key or os.environ.get("FASTFOLD_API_KEY") or "").strip()
        self.endpoint = (
            endpoint
            or os.environ.get("FASTFOLD_SITES_API_URL")
            or "https://api.fastfold.ai/v1"
        ).rstrip("/")
        self.timeout = timeout

    def _json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.endpoint}{path}",
            data=data,
            method=method,
        )
        request.add_header("Authorization", f"Bearer {self.api_key}")
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace").strip()
            raise RuntimeError(
                f"FastFold Sites API returned HTTP {exc.code}: {detail[:300]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach FastFold Sites API: {exc.reason}") from exc
        if not isinstance(result, dict):
            raise RuntimeError("FastFold Sites API returned an invalid response.")
        return result

    def _upload(self, artifact: Path, upload: dict[str, Any]) -> None:
        url = str(upload.get("url") or "").strip()
        fields = upload.get("fields")
        if not url or not isinstance(fields, dict):
            raise RuntimeError("FastFold Sites API returned an invalid upload form.")
        boundary = f"----sandwalk-sites-{os.urandom(12).hex()}"
        body = bytearray()
        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
            )
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            b'Content-Disposition: form-data; name="file"; filename="site.zip"\r\n'
            b"Content-Type: application/zip\r\n\r\n"
        )
        body.extend(artifact.read_bytes())
        body.extend(f"\r\n--{boundary}--\r\n".encode())
        request = urllib.request.Request(url, data=bytes(body), method="POST")
        request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status not in {200, 201, 204}:
                    raise RuntimeError(f"Site upload failed with HTTP {response.status}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace").strip()
            raise RuntimeError(f"Site upload failed with HTTP {exc.code}: {detail[:300]}") from exc

    def publish(
        self,
        *,
        artifact: Path,
        name: str,
        local_site_id: str,
        content_sha256: str,
        expanded_size_bytes: int,
        file_count: int,
        slug: str | None = None,
        cloud_site_id: str | None = None,
    ) -> PublishedSite:
        del local_site_id
        if not self.api_key:
            raise ValueError("FASTFOLD_API_KEY is required to publish a site.")
        if cloud_site_id:
            site = self._json(
                "PATCH",
                f"/sites/{cloud_site_id}",
                {"name": name, "slug": slug} if slug else {"name": name},
            )
        else:
            site = self._json("POST", "/sites", {"name": name, "slug": slug})
        site_id = str(site.get("id") or "").strip()
        if not site_id:
            raise RuntimeError("FastFold Sites API did not return a site id.")

        created = self._json("POST", f"/sites/{site_id}/deployments")
        deployment = created.get("deployment")
        upload = created.get("upload")
        if not isinstance(deployment, dict) or not isinstance(upload, dict):
            raise RuntimeError("FastFold Sites API did not return deployment upload details.")
        deployment_id = str(deployment.get("id") or "").strip()
        if not deployment_id:
            raise RuntimeError("FastFold Sites API did not return a deployment id.")
        self._upload(artifact, upload)
        self._json(
            "POST",
            f"/sites/{site_id}/deployments/{deployment_id}/finalize",
            {
                "expandedSizeBytes": expanded_size_bytes,
                "fileCount": file_count,
                "archiveSha256": content_sha256,
            },
        )

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            status = self._json(
                "GET",
                f"/sites/{site_id}/deployments/{deployment_id}",
            )
            state = str(status.get("status") or "").lower()
            if state == "succeeded":
                url = str(status.get("publicUrl") or site.get("url") or "").strip()
                if not url:
                    raise RuntimeError("Published site response did not include a URL.")
                return PublishedSite(url=url, site_id=site_id)
            if state == "failed":
                detail = str(status.get("errorMessage") or "Site deployment failed")
                raise RuntimeError(detail)
            time.sleep(2)
        raise TimeoutError("Timed out waiting for the site deployment to finish.")
