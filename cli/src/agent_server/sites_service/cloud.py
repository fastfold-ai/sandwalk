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

    def delete(self, site_id: str) -> None: ...


class FastFoldSitesClient:
    """Publish a ZIP through the FastFold Sites control-plane workflow."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        endpoint: str | None = None,
        timeout: float | None = None,
        request_timeout: float = 30,
        wait_timeout: float = 120,
        ready_timeout: float = 120,
    ) -> None:
        self.api_key = (api_key or os.environ.get("FASTFOLD_API_KEY") or "").strip()
        self.endpoint = (
            endpoint
            or os.environ.get("FASTFOLD_SITES_API_URL")
            or "https://api.fastfold.ai/v1"
        ).rstrip("/")
        # ``timeout`` remains as a legacy alias for the deployment wait budget.
        self.request_timeout = max(5.0, float(request_timeout))
        self.wait_timeout = max(
            1.0,
            float(wait_timeout if timeout is None else timeout),
        )
        # CloudFront KeyValueStore can lag a bit after deploy succeeds.
        self.ready_timeout = max(1.0, float(ready_timeout))

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
            with urllib.request.urlopen(
                request, timeout=self.request_timeout
            ) as response:
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
            with urllib.request.urlopen(
                request, timeout=self.request_timeout
            ) as response:
                if response.status not in {200, 201, 204}:
                    raise RuntimeError(f"Site upload failed with HTTP {response.status}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace").strip()
            raise RuntimeError(f"Site upload failed with HTTP {exc.code}: {detail[:300]}") from exc

    def _public_url_ready(self, url: str) -> bool:
        """Return True when the public site URL serves a successful HTML response."""
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "text/html,*/*",
                "User-Agent": "sandwalk-sites-ready-check/1.0",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urllib.request.urlopen(
                request, timeout=min(15.0, self.request_timeout)
            ) as response:
                return 200 <= int(response.status) < 400
        except urllib.error.HTTPError as exc:
            # 404 is the CloudFront Function "slug not in KVS yet" response.
            if exc.code in {404, 403, 502, 503, 504}:
                return False
            raise RuntimeError(
                f"Published site returned unexpected HTTP {exc.code} at {url}"
            ) from exc
        except urllib.error.URLError:
            return False

    def _wait_until_reachable(self, url: str) -> None:
        deadline = time.monotonic() + self.ready_timeout
        while time.monotonic() < deadline:
            if self._public_url_ready(url):
                return
            time.sleep(2)
        raise TimeoutError(
            f"Site deployed, but {url} was not reachable within "
            f"{int(self.ready_timeout)}s (CloudFront routing may still be propagating)."
        )

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

        deadline = time.monotonic() + self.wait_timeout
        last_state = "queued"
        while time.monotonic() < deadline:
            status = self._json(
                "GET",
                f"/sites/{site_id}/deployments/{deployment_id}",
            )
            last_state = str(status.get("status") or "").lower() or last_state
            if last_state == "succeeded":
                url = str(status.get("publicUrl") or site.get("url") or "").strip()
                if not url:
                    raise RuntimeError("Published site response did not include a URL.")
                self._wait_until_reachable(url)
                return PublishedSite(url=url, site_id=site_id)
            if last_state == "failed":
                detail = str(status.get("errorMessage") or "Site deployment failed")
                raise RuntimeError(detail)
            time.sleep(2)
        raise TimeoutError(
            f"Timed out after {int(self.wait_timeout)}s waiting for site deployment "
            f"{deployment_id} (last status: {last_state})."
        )

    def delete(self, site_id: str) -> None:
        if not self.api_key:
            raise ValueError("FASTFOLD_API_KEY is required to delete a published site.")
        self._json("DELETE", f"/sites/{site_id}")
