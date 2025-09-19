#!/usr/bin/env python

import unittest
import tempfile
import shutil
import json
import sys
import os
from pathlib import Path
from unittest.mock import patch, mock_open

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from spotify2ytmusic.checkpoint import CheckpointManager


class TestCheckpointErrorResilience(unittest.TestCase):
    """Test error resilience and recovery capabilities of checkpoint system."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = Path(self.temp_dir) / "checkpoints"
        self.checkpoint_dir.mkdir(exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_checkpoint_handles_disk_full_without_corruption(self):
        """Test that running out of disk space doesn't corrupt existing checkpoint data."""
        checkpoint = CheckpointManager("disk_full_test", str(self.checkpoint_dir))

        # Save some initial data successfully
        checkpoint.save_progress(0, "vid_0", {"name": "Song 0"})
        checkpoint.save_progress(1, "vid_1", {"name": "Song 1"})

        # Verify initial state
        initial_stats = checkpoint.get_statistics()
        self.assertEqual(initial_stats["successful"], 2)

        # Simulate disk full during save operation
        with patch('builtins.open', side_effect=OSError("No space left on device")):
            try:
                checkpoint.save_progress(2, "vid_2", {"name": "Song 2"})
            except:
                pass  # Expected to fail

        # Existing data should remain intact and uncorrupted
        new_checkpoint = CheckpointManager("disk_full_test", str(self.checkpoint_dir))

        preserved_indices = new_checkpoint.get_processed_indices()
        preserved_stats = new_checkpoint.get_statistics()

        # This should pass in an error-resilient system, but will likely fail in current system
        self.assertEqual(preserved_indices, {0, 1}, "Existing data should be preserved after disk full error")
        self.assertEqual(preserved_stats["successful"], 2, "Statistics should reflect preserved data only")

        # Should be able to continue operations once disk space is available
        new_checkpoint.save_progress(3, "vid_3", {"name": "Recovery Song"})
        final_stats = new_checkpoint.get_statistics()
        self.assertEqual(final_stats["successful"], 3, "Should resume normal operation after disk space recovered")

    def test_checkpoint_recovers_from_partial_corruption_automatically(self):
        """Test that partially corrupted files are automatically recovered without data loss."""
        checkpoint = CheckpointManager("corruption_recovery_test", str(self.checkpoint_dir))

        # Save several tracks successfully
        for i in range(5):
            checkpoint.save_progress(i, f"vid_{i}", {"name": f"Song {i}"})

        # Verify all data saved correctly
        initial_indices = checkpoint.get_processed_indices()
        self.assertEqual(initial_indices, {0, 1, 2, 3, 4})

        # Simulate partial corruption (like power loss during write)
        # Corrupt only part of the file, leaving some valid data
        processed_content = checkpoint.processed_file_path.read_text()
        lines = processed_content.strip().split('\n')

        # Keep first 3 valid lines, corrupt the rest
        corrupted_content = '\n'.join(lines[:3]) + '\n{"corrupted": invalid json}\n{"also": broken'
        checkpoint.processed_file_path.write_text(corrupted_content)

        # An error-resilient system should automatically recover valid data
        new_checkpoint = CheckpointManager("corruption_recovery_test", str(self.checkpoint_dir))

        # Should automatically detect corruption and recover what it can
        recovered_indices = new_checkpoint.get_processed_indices()
        recovered_stats = new_checkpoint.get_statistics()

        # Should recover at least the valid entries (first 3 tracks)
        self.assertGreaterEqual(len(recovered_indices), 3, "Should recover valid data from corrupted file")
        self.assertGreaterEqual(recovered_stats["successful"], 3, "Should count recovered valid entries")

        # Should be able to continue normal operation after recovery
        new_checkpoint.save_progress(5, "vid_5", {"name": "Post-recovery Song"})

        final_stats = new_checkpoint.get_statistics()
        self.assertEqual(final_stats["successful"], recovered_stats["successful"] + 1,
                        "Should continue working normally after automatic recovery")

    def test_checkpoint_handles_transient_errors_with_automatic_retry(self):
        """Test that transient I/O errors are automatically retried without failing."""
        checkpoint = CheckpointManager("retry_test", str(self.checkpoint_dir))

        # Save initial data successfully
        checkpoint.save_progress(0, "vid_0", {"name": "Song 0"})

        # Create a counter to simulate transient failure that succeeds on retry
        call_count = 0
        original_open = open

        def mock_open_with_transient_failure(*args, **kwargs):
            nonlocal call_count
            if 'retry_test.processed' in str(args[0]) and 'a' in args[1]:
                call_count += 1
                if call_count == 1:
                    # First call fails with transient error
                    raise OSError("Resource temporarily unavailable")
            # All other calls or retry attempts succeed
            return original_open(*args, **kwargs)

        # An error-resilient system should automatically retry transient failures
        with patch('builtins.open', side_effect=mock_open_with_transient_failure):
            # This should succeed after automatic retry (current system will fail)
            checkpoint.save_progress(1, "vid_1", {"name": "Song 1"})

        # Verify the save eventually succeeded despite initial failure
        final_stats = checkpoint.get_statistics()
        self.assertEqual(final_stats["successful"], 2, "Should retry and succeed on transient errors")

        indices = checkpoint.get_processed_indices()
        self.assertEqual(indices, {0, 1}, "Should have both tracks saved after retry")

    def test_checkpoint_handles_concurrent_access_conflicts(self):
        """Test handling of concurrent access to checkpoint files."""
        checkpoint1 = CheckpointManager("concurrent_test", str(self.checkpoint_dir))
        checkpoint2 = CheckpointManager("concurrent_test", str(self.checkpoint_dir))

        # Both try to save simultaneously (simulate race condition)
        checkpoint1.save_progress(0, "vid_0", {"name": "Song 0 from process 1"})

        # Simulate file being locked by another process during second save
        def mock_open_with_lock_conflict(*args, **kwargs):
            if 'concurrent_test.processed' in str(args[0]) and 'a' in args[1]:
                raise OSError("Resource temporarily unavailable")
            return open(*args, **kwargs)

        # Should handle concurrent access gracefully
        with patch('builtins.open', side_effect=mock_open_with_lock_conflict):
            with self.assertRaisesRegex(Exception, r".*concurrent_test.*(resource|lock|busy|unavailable)"):
                checkpoint2.save_progress(1, "vid_1", {"name": "Song 1 from process 2"})

        # First checkpoint should still work normally regardless
        indices = checkpoint1.get_processed_indices()
        self.assertEqual(indices, {0}, "First checkpoint should continue working normally")

    def test_checkpoint_validates_file_integrity_automatically(self):
        """Test that checkpoint system automatically validates file integrity."""
        checkpoint = CheckpointManager("integrity_test", str(self.checkpoint_dir))

        # Save some data
        checkpoint.save_progress(0, "vid_0", {"name": "Song 0"})
        checkpoint.save_progress(1, "vid_1", {"name": "Song 1"})

        # Corrupt the processed file with invalid JSON
        checkpoint.processed_file_path.write_text('{"index": 0, "invalid": json}\n{"index": 1, "youtube_video_id": "vid_1", "track_info": {"name": "Song 1"}}')

        # System should detect invalid entries and skip them gracefully
        new_checkpoint = CheckpointManager("integrity_test", str(self.checkpoint_dir))

        # Should automatically validate and recover from corrupt entries
        indices = new_checkpoint.get_processed_indices()
        stats = new_checkpoint.get_statistics()

        # Should skip invalid entries and preserve valid ones
        self.assertEqual(indices, {1}, "Should skip corrupt entry and preserve valid one")
        self.assertEqual(stats["successful"], 1, "Should count only valid entries after integrity check")

        # Should be able to continue operations normally after integrity recovery
        new_checkpoint.save_progress(2, "vid_2", {"name": "Post-corruption Song"})

        final_stats = new_checkpoint.get_statistics()
        self.assertEqual(final_stats["successful"], stats["successful"] + 1, "Should continue working normally after integrity recovery")

    def test_checkpoint_provides_detailed_error_context(self):
        """Test that checkpoint errors provide detailed context for debugging."""
        checkpoint = CheckpointManager("context_test", str(self.checkpoint_dir))

        # Test I/O error context
        with patch('builtins.open', side_effect=IOError("Input/output error")):
            with self.assertRaisesRegex(Exception, r".*save_progress.*context_test.*Input/output error"):
                checkpoint.save_progress(0, "vid_0", {"name": "Song 0"})

        # Test filesystem permission error context
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with self.assertRaisesRegex(Exception, r".*context_test.*processed.*Permission denied"):
                checkpoint.save_progress(0, "vid_0", {"name": "Song 0"})

    def test_checkpoint_automatic_cleanup_of_temporary_files(self):
        """Test that temporary files are cleaned up even when operations fail."""
        checkpoint = CheckpointManager("cleanup_test", str(self.checkpoint_dir))

        # Save initial data successfully
        checkpoint.save_progress(0, "vid_0", {"name": "Song 0"})

        # Simulate write failure
        with patch('builtins.open', side_effect=OSError("Disk full")):
            try:
                checkpoint.save_progress(1, "vid_1", {"name": "Song 1"})
            except:
                pass  # Expected to fail

        # File should remain valid and readable after failure
        new_checkpoint = CheckpointManager("cleanup_test", str(self.checkpoint_dir))
        final_indices = new_checkpoint.get_processed_indices()

        # Should preserve original data
        self.assertIn(0, final_indices, "Original data should be preserved")
        self.assertLessEqual(len(final_indices), 2, "Should not have partial or corrupt entries")


if __name__ == "__main__":
    unittest.main()