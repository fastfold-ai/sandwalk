"""Patch Modal's deprecated filesystem sync methods with non-deprecated I/O."""

from __future__ import annotations

from typing import Any

from agent.sandbox_backend.runtime import _run_modal_blocking


def _patch_modal_filesystem_io(backend: Any, modal_sandbox: Any) -> None:
    """Prefer Modal's non-deprecated filesystem APIs for upload/download.

    ``langchain_modal.ModalSandbox`` still uses ``Sandbox.open`` / ``FileIO.write``,
    which raise ``DeprecationError`` and can flood the ASGI event loop when seeding
    many workspace files in the background.
    """
    try:
        from deepagents.backends.protocol import (
            FileDownloadResponse,
            FileUploadResponse,
        )
    except Exception:  # noqa: BLE001
        return

    filesystem = getattr(modal_sandbox, "filesystem", None)
    if filesystem is None:
        return

    def upload_files(files: list[tuple[str, bytes]]) -> list[Any]:
        def _upload() -> list[Any]:
            responses: list[Any] = []
            for path, content in files:
                if not str(path).startswith("/"):
                    responses.append(
                        FileUploadResponse(path=path, error="invalid_path")
                    )
                    continue
                try:
                    filesystem.write_bytes(content, path)
                    responses.append(FileUploadResponse(path=path, error=None))
                except PermissionError:
                    responses.append(
                        FileUploadResponse(path=path, error="permission_denied")
                    )
                except FileNotFoundError:
                    responses.append(
                        FileUploadResponse(path=path, error="file_not_found")
                    )
                except Exception as exc:  # noqa: BLE001
                    responses.append(FileUploadResponse(path=path, error=str(exc)))
            return responses

        return _run_modal_blocking(_upload)

    def download_files(paths: list[str]) -> list[Any]:
        def _download() -> list[Any]:
            responses: list[Any] = []
            read_bytes = getattr(filesystem, "read_bytes", None)
            for path in paths:
                if not str(path).startswith("/"):
                    responses.append(
                        FileDownloadResponse(
                            path=path, content=None, error="invalid_path"
                        )
                    )
                    continue
                if not callable(read_bytes):
                    responses.append(
                        FileDownloadResponse(
                            path=path, content=None, error="read_unsupported"
                        )
                    )
                    continue
                try:
                    content = read_bytes(path)
                    if isinstance(content, memoryview):
                        content = content.tobytes()
                    elif isinstance(content, str):
                        content = content.encode()
                    responses.append(
                        FileDownloadResponse(path=path, content=content, error=None)
                    )
                except FileNotFoundError:
                    responses.append(
                        FileDownloadResponse(
                            path=path, content=None, error="file_not_found"
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    responses.append(
                        FileDownloadResponse(path=path, content=None, error=str(exc))
                    )
            return responses

        return _run_modal_blocking(_download)

    backend.upload_files = upload_files  # type: ignore[method-assign]
    backend.download_files = download_files  # type: ignore[method-assign]
