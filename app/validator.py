import re
from pathlib import Path


class PathValidator:
    """Validates and constructs safe file paths with traversal protection."""

    def __init__(self, uploads_dir: Path):
        self.uploads_dir = uploads_dir

    def validate_job_id(self, job_id: str) -> str:
        """Validate job ID is a safe alphanumeric/dash/underscore string."""
        if not job_id or not isinstance(job_id, str):
            raise ValueError("Invalid jobId")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", job_id):
            raise ValueError("Invalid jobId format")
        return job_id

    def validate_job_path(self, job_id: str, sub_path: str = "") -> Path:
        """
        Construct and validate a job path, guarding against traversal and symlinks.

        Raises:
            ValueError: if the path escapes uploads_dir or is a symlink
        """
        job_id_safe = self.validate_job_id(job_id)
        full_path = self.uploads_dir / job_id_safe
        if sub_path:
            full_path = full_path / Path(sub_path).name
        # Check symlinks on the unresolved path; resolve() follows them, making is_symlink() always False
        if full_path.is_symlink():
            raise ValueError("Path is a symlink")
        resolved = full_path.resolve()
        uploads_dir_resolved = self.uploads_dir.resolve()
        try:
            resolved.relative_to(uploads_dir_resolved)
        except ValueError:
            raise ValueError("Path traversal attempt detected")
        return resolved
