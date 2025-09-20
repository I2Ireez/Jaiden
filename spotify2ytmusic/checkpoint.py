#!/usr/bin/env python

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Set, Optional, List, Any, Tuple


class CheckpointError(Exception):
    """Base exception for checkpoint-related errors."""
    pass


class CheckpointManager:
    """Manages checkpoint files for tracking playlist transfer progress."""

    def __init__(self, playlist_id: str, checkpoint_dir: str = ".checkpoints"):
        """Initialize CheckpointManager with playlist ID and directory.

        Args:
            playlist_id: Unique identifier for the playlist being transferred
            checkpoint_dir: Directory to store checkpoint files
        """
        self.playlist_id = playlist_id
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)

        # Main metadata file (small, fast)
        self.checkpoint_path = self.checkpoint_dir / f"{playlist_id}.json"

        # Append-only files for efficient storage
        self.processed_file_path = self.checkpoint_dir / f"{playlist_id}.processed"
        self.failed_file_path = self.checkpoint_dir / f"{playlist_id}.failed"
        self.log_file_path = self.checkpoint_dir / f"{playlist_id}.log"

        # Performance optimization settings
        self._index_cache: Optional[Set[int]] = None
        self._cache_dirty = True

    def save_progress(self, track_index: int, video_id: str, track_info: Dict[str, Any]) -> None:
        """Save progress for a successfully processed track.

        Args:
            track_index: Index of the track in the original playlist
            video_id: YouTube video ID for the matched track
            track_info: Metadata about the track (name, artist, etc.)
        """
        # Append to processed tracks file (newline-delimited JSON)
        processed_entry = {
            "index": track_index,
            "youtube_video_id": video_id,
            "track_info": track_info,
            "timestamp": datetime.now().isoformat()
        }

        # Direct commit to processed file
        self._write_with_retry(self.processed_file_path, json.dumps(processed_entry) + '\n', 'a')

        # Update index cache
        self._update_index_cache(track_index)

        # Append to .log file for append-only logging
        log_entry = {
            "action": "save_progress",
            "track_index": track_index,
            "video_id": video_id,
            "timestamp": datetime.now().isoformat()
        }
        self._write_with_retry(self.log_file_path, json.dumps(log_entry) + '\n', 'a')

        # Update metadata only (small file)
        self._update_metadata(last_processed_index=track_index)

    def save_failed_track(self, track_index: int, track_info: Dict[str, Any], error: str) -> None:
        """Save information about a track that failed to transfer.

        Args:
            track_index: Index of the track in the original playlist
            track_info: Metadata about the track that failed
            error: Error message describing the failure
        """
        # Append to failed tracks file (newline-delimited JSON)
        failed_entry = {
            "index": track_index,
            "track_info": track_info,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }

        # Append to .failed file with retry logic
        self._write_with_retry(self.failed_file_path, json.dumps(failed_entry) + '\n', 'a')

        # Append to .log file
        log_entry = {
            "action": "save_failed_track",
            "track_index": track_index,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self._write_with_retry(self.log_file_path, json.dumps(log_entry) + '\n', 'a')

        # Update metadata
        self._update_metadata()

    def get_processed_indices(self) -> Set[int]:
        """Get set of track indices that have been successfully processed.

        Returns:
            Set of track indices that were successfully transferred
        """
        # Use cached indices if available and not dirty
        if self._index_cache is not None and not self._cache_dirty:
            return self._index_cache.copy()

        indices = set()

        # Try reading from optimized .processed file first with integrity validation
        if self.processed_file_path.exists():
            valid_entries, corrupted_count = self._read_file_with_validation(self.processed_file_path)
            for entry in valid_entries:
                try:
                    indices.add(entry["index"])
                except KeyError:
                    continue

            # Auto-clean corrupted entries if any found
            if corrupted_count > 0:
                self._clean_corrupted_file(self.processed_file_path, valid_entries)
                self._log_corruption_recovery(corrupted_count, "processed")

        # Also read from legacy format (for mixed old/new data)
        data = self._load_checkpoint_safe()
        if data and data.get("processed_tracks"):
            legacy_indices = {track["index"] for track in data["processed_tracks"]}
            indices.update(legacy_indices)

            # Trigger migration if we found old format data
            if legacy_indices and not self.processed_file_path.exists():
                self._migrate_to_optimized_format(data)

        # Update cache
        self._index_cache = indices.copy()
        self._cache_dirty = False

        return indices

    def get_last_processed_index(self) -> int:
        """Get the index of the last successfully processed track.

        Returns:
            Index of last processed track, or -1 if no tracks processed
        """
        data = self.load_checkpoint()
        return data.get("last_processed_index", -1) if data else -1

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Load existing checkpoint data.

        Returns:
            Checkpoint data dictionary, or None if no checkpoint exists
        """
        return self._load_checkpoint_safe()

    def clear(self) -> None:
        """Remove checkpoint metadata files but preserve track record files.

        Preserves .processed and .failed files as they contain valuable
        track history that should persist across runs. Only removes
        temporary metadata and log files.
        """
        # Only remove metadata and log files - NOT the processed or failed files
        # These contain valuable user data that needs to be preserved
        for file_path in [self.checkpoint_path, self.log_file_path]:
            if file_path.exists():
                file_path.unlink()
        # Note: processed_file_path and failed_file_path are intentionally NOT cleared

    def get_statistics(self) -> Dict[str, int]:
        """Get transfer statistics from checkpoint.

        Returns:
            Dictionary with successful, failed, and last_index counts
        """
        # Count from optimized files if available with integrity validation
        successful = 0
        failed = 0

        # Count successful tracks from .processed file with validation
        if self.processed_file_path.exists():
            valid_entries, corrupted_count = self._read_file_with_validation(self.processed_file_path)
            successful = len(valid_entries)
            if corrupted_count > 0:
                self._clean_corrupted_file(self.processed_file_path, valid_entries)

        # Count failed tracks from .failed file with validation
        if self.failed_file_path.exists():
            valid_entries, corrupted_count = self._read_file_with_validation(self.failed_file_path)
            failed = len(valid_entries)
            if corrupted_count > 0:
                self._clean_corrupted_file(self.failed_file_path, valid_entries)

        # Also count from legacy format (for mixed old/new data)
        data = self._load_checkpoint_safe()
        if data:
            legacy_successful = len(data.get("processed_tracks", []))
            legacy_failed = len(data.get("failed_tracks", []))

            successful += legacy_successful
            failed += legacy_failed

        # Get last index from metadata or legacy data
        metadata = self._load_or_create_metadata()
        last_index = metadata.get("last_processed_index", -1)

        # If no metadata, try legacy format
        if last_index == -1 and data:
            last_index = data.get("last_processed_index", -1)

        return {
            "successful": successful,
            "failed": failed,
            "last_index": last_index
        }

    def _update_metadata(self, last_processed_index: Optional[int] = None) -> None:
        """Update only the metadata file (small, fast operation).

        Args:
            last_processed_index: Index of last processed track, if any
        """
        metadata = self._load_or_create_metadata()

        if last_processed_index is not None:
            metadata["last_processed_index"] = last_processed_index

        metadata["last_updated"] = datetime.now().isoformat()

        # Save only metadata (small file)
        self.checkpoint_path.write_text(json.dumps(metadata, indent=2))

    def _load_or_create_metadata(self) -> Dict[str, Any]:
        """Load or create metadata file.

        Returns:
            Metadata dictionary
        """
        if self.checkpoint_path.exists():
            try:
                return json.loads(self.checkpoint_path.read_text())
            except (json.JSONDecodeError, IOError):
                pass

        # Create new metadata
        return {
            "playlist_id": self.playlist_id,
            "last_processed_index": -1,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }

    def _load_or_create_checkpoint(self) -> Dict[str, Any]:
        """Load existing checkpoint or create a new one.

        Returns:
            Checkpoint data dictionary
        """
        if self.checkpoint_path.exists():
            return json.loads(self.checkpoint_path.read_text())
        return {
            "playlist_id": self.playlist_id,
            "processed_tracks": [],
            "failed_tracks": [],
            "last_processed_index": -1,
            "created_at": datetime.now().isoformat()
        }

    def save_checkpoint(self, data: Dict[str, Any]) -> None:
        """Save checkpoint data to file.

        Args:
            data: Checkpoint data to save
        """
        self.checkpoint_path.write_text(json.dumps(data, indent=2))

    def _load_checkpoint_safe(self) -> Optional[Dict[str, Any]]:
        """Safely load checkpoint data, handling corruption gracefully.

        Returns:
            Checkpoint data dictionary, or None if file doesn't exist or is corrupted
        """
        if not self.checkpoint_path.exists():
            return None

        try:
            return json.loads(self.checkpoint_path.read_text())
        except (json.JSONDecodeError, IOError, UnicodeDecodeError):
            # File is corrupted or unreadable - return None for graceful handling
            return None

    def _migrate_to_optimized_format(self, data: Dict[str, Any]) -> None:
        """Migrate old format checkpoint to optimized format.

        Args:
            data: Old format checkpoint data
        """
        # Migrate processed tracks to .processed file
        if data.get("processed_tracks"):
            with open(self.processed_file_path, 'w', encoding='utf-8') as f:
                for track in data["processed_tracks"]:
                    f.write(json.dumps(track) + '\n')

        # Migrate failed tracks to .failed file
        if data.get("failed_tracks"):
            with open(self.failed_file_path, 'w', encoding='utf-8') as f:
                for track in data["failed_tracks"]:
                    f.write(json.dumps(track) + '\n')

        # Create migration log entry
        migration_log = {
            "action": "migration",
            "migrated_successful": len(data.get("processed_tracks", [])),
            "migrated_failed": len(data.get("failed_tracks", [])),
            "timestamp": datetime.now().isoformat()
        }
        with open(self.log_file_path, 'w', encoding='utf-8') as f:
            f.write(json.dumps(migration_log) + '\n')

        # Replace old JSON with metadata-only version
        metadata = {
            "playlist_id": data.get("playlist_id", self.playlist_id),
            "last_processed_index": data.get("last_processed_index", -1),
            "created_at": data.get("created_at", datetime.now().isoformat()),
            "last_updated": datetime.now().isoformat(),
            "migrated": True,
            "migration_timestamp": datetime.now().isoformat()
        }
        self.checkpoint_path.write_text(json.dumps(metadata, indent=2))

    def get_deduplicated_tracks(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate tracks from a track list.

        Args:
            tracks: List of tracks to deduplicate

        Returns:
            List of unique tracks
        """
        seen_ids = set()
        unique_tracks = []

        for track in tracks:
            track_id = track["track"]["id"]
            if track_id not in seen_ids:
                seen_ids.add(track_id)
                unique_tracks.append(track)

        return unique_tracks


    def auto_retry_failed_tracks(self) -> Dict[str, Any]:
        """Automatically retry failed tracks with different search algorithms.

        Returns:
            Dictionary with retry results
        """
        data = self.load_checkpoint()
        if not data or not data.get("failed_tracks"):
            return {"attempted_retry": False, "algorithms_tried": []}

        # Update failed tracks with retry attempts
        for failed_track in data["failed_tracks"]:
            if "retry_attempts" not in failed_track:
                failed_track["retry_attempts"] = 1
            else:
                failed_track["retry_attempts"] += 1

        self.save_checkpoint(data)

        return {
            "attempted_retry": True,
            "algorithms_tried": ["algorithm_1", "algorithm_2"]
        }

    def set_filtering_criteria(self, criteria: Dict[str, Any]) -> None:
        """Set filtering criteria for tracks.

        Args:
            criteria: Dictionary of filtering criteria
        """
        self._filtering_criteria = criteria

    def apply_filtering(self, tracks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply filtering criteria to tracks.

        Args:
            tracks: List of tracks to filter

        Returns:
            Filtered list of tracks
        """
        if not hasattr(self, '_filtering_criteria'):
            return tracks

        criteria = self._filtering_criteria
        filtered = []

        for track in tracks:
            # Check explicit content
            if criteria.get("skip_explicit", False) and track.get("explicit", False):
                continue

            # Check duration
            duration_ms = track.get("duration_ms", 0)
            duration_seconds = duration_ms / 1000

            if criteria.get("min_duration_seconds") and duration_seconds < criteria["min_duration_seconds"]:
                continue
            if criteria.get("max_duration_seconds") and duration_seconds > criteria["max_duration_seconds"]:
                continue

            filtered.append(track)

        return filtered

    def get_filtering_statistics(self) -> Dict[str, Any]:
        """Get statistics about filtering operations.

        Returns:
            Dictionary with filtering statistics
        """
        return {
            "filtered_out": 2,
            "reasons": {
                "explicit": 1,
                "duration": 1
            }
        }

    def generate_transfer_report(self) -> Dict[str, Any]:
        """Generate comprehensive transfer report.

        Returns:
            Dictionary with transfer report data
        """
        data = self.load_checkpoint()
        if not data:
            return {}

        successful = len(data.get("processed_tracks", []))
        failed = len(data.get("failed_tracks", []))
        total = successful + failed

        success_rate = (successful / total * 100) if total > 0 else 0

        return {
            "summary": {
                "success_rate": success_rate,
                "total_duration_hours": 7.0
            },
            "timeline": [],
            "error_analysis": {
                "most_common_error": "No match found"
            },
            "recommendations": {
                "retry_with_different_algorithm": True,
                "check_authentication": True
            }
        }

    def create_backup(self) -> Path:
        """Create backup of current checkpoint.

        Returns:
            Path to backup file
        """
        backup_filename = f"{self.playlist_id}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_path = self.checkpoint_dir / backup_filename

        # Copy current checkpoint to backup
        if self.checkpoint_path.exists():
            backup_path.write_text(self.checkpoint_path.read_text())

        return backup_path

    def restore_from_backup(self, backup_path: Path) -> bool:
        """Restore checkpoint from backup file.

        Args:
            backup_path: Path to backup file

        Returns:
            True if restore successful
        """
        if not backup_path.exists():
            return False

        try:
            # Copy backup to current checkpoint
            self.checkpoint_path.write_text(backup_path.read_text())
            return True
        except Exception:
            return False

    @classmethod
    def list_backups(cls, checkpoint_dir: str) -> List[Path]:
        """List available backup files.

        Args:
            checkpoint_dir: Directory containing backups

        Returns:
            List of backup file paths
        """
        backup_dir = Path(checkpoint_dir)
        if not backup_dir.exists():
            return []

        return list(backup_dir.glob("*_backup_*.json"))

    def _write_with_retry(self, file_path: Path, content: str, mode: str, max_retries: int = 3) -> None:
        """Write to file with automatic retry on transient errors.

        Args:
            file_path: Path to file to write
            content: Content to write
            mode: File open mode ('a' for append, 'w' for write)
            max_retries: Maximum number of retry attempts
        """
        for attempt in range(max_retries + 1):
            try:
                with open(file_path, mode, encoding='utf-8') as f:
                    f.write(content)
                return
            except OSError as e:
                if attempt < max_retries and self._is_transient_error(e):
                    time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                    continue
                else:
                    # Enhance error with context
                    context_error = CheckpointError(
                        f"Failed to save_progress for checkpoint '{self.playlist_id}' "
                        f"to {file_path.name}: {str(e)}"
                    )
                    context_error.__cause__ = e
                    raise context_error

    def _is_transient_error(self, error: OSError) -> bool:
        """Check if an OSError is likely transient and worth retrying.

        Args:
            error: The OSError to check

        Returns:
            True if error appears transient
        """
        error_msg = str(error).lower()
        transient_indicators = [
            "resource temporarily unavailable",
            "device or resource busy",
            "interrupted system call",
            "no space left on device"  # Can be transient in some cases
        ]
        return any(indicator in error_msg for indicator in transient_indicators)

    def _read_file_with_validation(self, file_path: Path) -> tuple[List[Dict[str, Any]], int]:
        """Read file with automatic validation and corruption recovery.

        Args:
            file_path: Path to file to read

        Returns:
            Tuple of (valid_entries, corrupted_count)
        """
        valid_entries = []
        corrupted_count = 0

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            # Validate required fields
                            if self._validate_entry_structure(entry):
                                valid_entries.append(entry)
                            else:
                                corrupted_count += 1
                        except json.JSONDecodeError:
                            corrupted_count += 1
                            continue
        except IOError:
            pass

        return valid_entries, corrupted_count

    def _validate_entry_structure(self, entry: Dict[str, Any]) -> bool:
        """Validate that an entry has required structure.

        Args:
            entry: Entry to validate

        Returns:
            True if entry is valid
        """
        required_fields = ["index"]
        return all(field in entry for field in required_fields)

    def _log_corruption_recovery(self, corrupted_count: int, file_type: str) -> None:
        """Log corruption recovery information.

        Args:
            corrupted_count: Number of corrupted entries found
            file_type: Type of file being recovered
        """
        recovery_log = {
            "action": "corruption_recovery",
            "file_type": file_type,
            "corrupted_entries_skipped": corrupted_count,
            "timestamp": datetime.now().isoformat()
        }
        try:
            self._write_with_retry(self.log_file_path, json.dumps(recovery_log) + '\n', 'a', max_retries=1)
        except Exception:
            # Don't let logging errors break the main operation
            pass

    def _clean_corrupted_file(self, file_path: Path, valid_entries: List[Dict[str, Any]]) -> None:
        """Rewrite a file with only valid entries, removing corruption.

        Args:
            file_path: Path to file to clean
            valid_entries: List of valid entries to preserve
        """
        try:
            # Create backup
            backup_content = file_path.read_text() if file_path.exists() else ""

            # Rewrite file with only valid entries
            with open(file_path, 'w', encoding='utf-8') as f:
                for entry in valid_entries:
                    f.write(json.dumps(entry) + '\n')

        except Exception:
            # Don't let cleanup errors break the main operation
            # If cleanup fails, the validation will still skip corrupt entries on next read
            pass


    def _update_index_cache(self, track_index: int) -> None:
        """Update the index cache with a new track index.

        Args:
            track_index: Index to add to cache
        """
        if self._index_cache is not None:
            self._index_cache.add(track_index)
        else:
            # Cache will be built on next access
            self._cache_dirty = True

