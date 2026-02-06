"""
Git Service - Handles automated version control for SecureAssist.
"""
import subprocess
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

class GitService:
    """
    Manages Git operations for checkpoints and rollbacks.
    """
    
    def __init__(self, repo_path: str = None):
        self.repo_path = repo_path or os.getcwd()
    
    def _is_git_repo(self) -> bool:
        try:
            self._run_git(["rev-parse", "--is-inside-work-tree"])
            return True
        except Exception:
            return False
        
    def _run_git(self, args: list) -> str:
        """Run a git command and return output."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Git error ({args}): {e.stderr}")
            raise RuntimeError(f"Git operation failed: {e.stderr}")

    def checkpoint(self, message: str) -> Optional[str]:
        """Create a git commit of all current changes."""
        try:
            if not self._is_git_repo():
                logger.info("Skipping git checkpoint: not a git repository.")
                return None
            self._run_git(["add", "."])
            # Check if there are changes to commit
            status = self._run_git(["status", "--porcelain"])
            if not status:
                logger.info("No changes to checkpoint.")
                return None
            
            self._run_git(["commit", "-m", message])
            commit_hash = self._run_git(["rev-parse", "HEAD"])
            logger.info(f"Checkpoint created: {message} ({commit_hash})")
            return commit_hash
        except Exception as e:
            logger.error(f"Failed to create git checkpoint: {e}")
            return None

    def rollback(self, commit_hash: str = "HEAD~1") -> bool:
        """Rollback to a specific commit or the previous one."""
        try:
            logger.warning(f"Rolling back to {commit_hash}...")
            self._run_git(["reset", "--hard", commit_hash])
            return True
        except Exception as e:
            logger.error(f"Failed to rollback: {e}")
            return False

    def get_last_diff(self) -> str:
        """Return the diff of the most recent commit."""
        try:
            return self._run_git(["show", "HEAD", "--color=never"])
        except Exception as e:
            logger.error(f"Failed to get last diff: {e}")
            return ""

    def get_status(self) -> str:
        """Get summarized git status."""
        try:
            return self._run_git(["status", "--short"])
        except Exception as e:
            return str(e)

# Singleton instance
git_service = GitService()
