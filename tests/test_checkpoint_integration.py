#!/usr/bin/env python

import unittest
import tempfile
import shutil
import subprocess
import sys
import inspect
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path for imports
sys.path.insert(0, '..')
from spotify2ytmusic.checkpoint import CheckpointManager


class TestCheckpointIntegration(unittest.TestCase):
    """Test CLI integration and end-to-end checkpoint functionality."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = Path(self.temp_dir) / "checkpoints"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # CLI Integration Tests
    def test_load_liked_albums_command_has_resume_flag(self):
        """Test that load_liked_albums command accepts --resume flag"""
        from spotify2ytmusic import cli

        # Get the load_liked_albums function
        load_liked_albums_func = getattr(cli, 'load_liked_albums', None)
        self.assertIsNotNone(load_liked_albums_func, "load_liked_albums function should exist")

        # Read the source to check if --resume flag is handled
        source = inspect.getsource(load_liked_albums_func)

        # These should now pass because the flags are implemented
        self.assertIn("--resume", source, "load_liked_albums should have --resume flag")
        self.assertIn("args.resume", source, "load_liked_albums should handle resume argument")

    def test_load_liked_albums_command_has_reset_checkpoint_flag(self):
        """Test that load_liked_albums command accepts --reset-checkpoint flag"""
        from spotify2ytmusic import cli

        load_liked_albums_func = getattr(cli, 'load_liked_albums', None)
        self.assertIsNotNone(load_liked_albums_func, "load_liked_albums function should exist")

        source = inspect.getsource(load_liked_albums_func)

        # These should now pass because the flags are implemented
        self.assertIn("--reset-checkpoint", source, "load_liked_albums should have --reset-checkpoint flag")
        self.assertIn("args.reset_checkpoint", source, "load_liked_albums should handle reset_checkpoint argument")

    def test_copy_all_playlists_command_has_resume_flag(self):
        """Test that copy_all_playlists command accepts --resume flag"""
        from spotify2ytmusic import cli

        # Get the copy_all_playlists function
        copy_all_playlists_func = getattr(cli, 'copy_all_playlists', None)
        self.assertIsNotNone(copy_all_playlists_func, "copy_all_playlists function should exist")

        # Read the source to check if --resume flag is handled
        source = inspect.getsource(copy_all_playlists_func)

        # These should now pass because the flags are implemented
        self.assertIn("--resume", source, "copy_all_playlists should have --resume flag")
        self.assertIn("args.resume", source, "copy_all_playlists should handle resume argument")

    def test_copy_all_playlists_command_has_reset_checkpoint_flag(self):
        """Test that copy_all_playlists command accepts --reset-checkpoint flag"""
        from spotify2ytmusic import cli

        copy_all_playlists_func = getattr(cli, 'copy_all_playlists', None)
        self.assertIsNotNone(copy_all_playlists_func, "copy_all_playlists function should exist")

        source = inspect.getsource(copy_all_playlists_func)

        # These should now pass because the flags are implemented
        self.assertIn("--reset-checkpoint", source, "copy_all_playlists should have --reset-checkpoint flag")
        self.assertIn("args.reset_checkpoint", source, "copy_all_playlists should handle reset_checkpoint argument")

    def test_copy_playlist_command_has_resume_flag(self):
        """Test that copy_playlist command accepts --resume flag"""
        # This will fail because copy_playlist doesn't have --resume flag yet
        from spotify2ytmusic import cli

        # Get the copy_playlist function
        copy_playlist_func = getattr(cli, 'copy_playlist', None)
        self.assertIsNotNone(copy_playlist_func, "copy_playlist function should exist")

        # Read the source to check if --resume flag is handled
        source = inspect.getsource(copy_playlist_func)

        # These should fail in RED phase because the flags aren't implemented
        self.assertIn("--resume", source, "copy_playlist should have --resume flag")
        self.assertIn("args.resume", source, "copy_playlist should handle resume argument")

    def test_copy_playlist_command_has_reset_checkpoint_flag(self):
        """Test that copy_playlist command accepts --reset-checkpoint flag"""
        # This will fail because copy_playlist doesn't have --reset-checkpoint flag yet
        from spotify2ytmusic import cli

        copy_playlist_func = getattr(cli, 'copy_playlist', None)
        self.assertIsNotNone(copy_playlist_func, "copy_playlist function should exist")

        source = inspect.getsource(copy_playlist_func)

        # These should fail in RED phase because the flags aren't implemented
        self.assertIn("--reset-checkpoint", source, "copy_playlist should have --reset-checkpoint flag")
        self.assertIn("args.reset_checkpoint", source, "copy_playlist should handle reset_checkpoint argument")

    @patch('sys.argv', ['test', 'spotify_123', 'youtube_456', '--resume'])
    @patch('spotify2ytmusic.cli.backend')
    @patch('spotify2ytmusic.cli.CheckpointManager')
    def test_copy_playlist_with_resume_creates_checkpoint_manager(self, mock_checkpoint_class, mock_backend):
        """Test that copy_playlist with --resume flag creates CheckpointManager"""
        from spotify2ytmusic import cli

        mock_checkpoint = Mock()
        mock_checkpoint_class.return_value = mock_checkpoint
        mock_checkpoint.checkpoint_path.exists.return_value = True
        mock_checkpoint.get_statistics.return_value = {
            "successful": 150,
            "failed": 3,
            "last_index": 152
        }

        # Mock backend.copy_playlist to avoid actual execution
        mock_backend.copy_playlist.return_value = None

        # Call copy_playlist (it will parse sys.argv internally)
        cli.copy_playlist()

        # Verify checkpoint was created
        mock_checkpoint_class.assert_called_once_with("spotify_123")

    @patch('sys.argv', ['test', 'spotify_123', 'youtube_456', '--reset-checkpoint'])
    @patch('spotify2ytmusic.cli.backend')
    @patch('spotify2ytmusic.cli.CheckpointManager')
    def test_copy_playlist_with_reset_clears_checkpoint(self, mock_checkpoint_class, mock_backend):
        """Test that copy_playlist with --reset-checkpoint clears existing checkpoint"""
        from spotify2ytmusic import cli

        mock_checkpoint = Mock()
        mock_checkpoint_class.return_value = mock_checkpoint

        # Mock backend.copy_playlist to avoid actual execution
        mock_backend.copy_playlist.return_value = None

        # Call copy_playlist (it will parse sys.argv internally)
        cli.copy_playlist()

        # Verify checkpoint was cleared (called twice: once for reset, once at completion)
        self.assertEqual(mock_checkpoint.clear.call_count, 2)

    @patch('sys.argv', ['test', '--resume'])
    @patch('spotify2ytmusic.cli.backend')
    @patch('spotify2ytmusic.cli.CheckpointManager')
    def test_load_liked_command_supports_checkpoint(self, mock_checkpoint_class, mock_backend):
        """Test that load_liked command supports checkpoint functionality"""
        from spotify2ytmusic import cli

        mock_checkpoint = Mock()
        mock_checkpoint_class.return_value = mock_checkpoint
        mock_checkpoint.checkpoint_path.exists.return_value = True
        mock_checkpoint.get_statistics.return_value = {"successful": 50, "failed": 0, "last_index": 49}

        # Mock backend.copier to avoid actual execution
        mock_backend.copier.return_value = None

        # Call load_liked (it will parse sys.argv internally)
        cli.load_liked()

        # Verify checkpoint was created for liked songs
        mock_checkpoint_class.assert_called_once_with("liked_songs")

    @patch('sys.argv', ['test', '--resume'])
    @patch('spotify2ytmusic.cli.backend')
    @patch('spotify2ytmusic.cli.CheckpointManager')
    def test_load_liked_albums_command_supports_checkpoint(self, mock_checkpoint_class, mock_backend):
        """Test that load_liked_albums command supports checkpoint functionality"""
        from spotify2ytmusic import cli

        mock_checkpoint = Mock()
        mock_checkpoint_class.return_value = mock_checkpoint
        mock_checkpoint.checkpoint_path.exists.return_value = True
        mock_checkpoint.get_statistics.return_value = {"successful": 25, "failed": 0, "last_index": 24}

        # Mock backend.copier to avoid actual execution
        mock_backend.copier.return_value = None
        mock_backend.load_playlists_json.return_value = {"playlists": []}
        mock_backend.iter_spotify_liked_albums.return_value = []

        # Call load_liked_albums (it will parse sys.argv internally)
        cli.load_liked_albums()

        # Verify checkpoint was created for liked albums
        mock_checkpoint_class.assert_called_once_with("liked_albums")

    @patch('sys.argv', ['test', '--resume'])
    @patch('spotify2ytmusic.cli.backend')
    def test_copy_all_playlists_command_supports_checkpoint(self, mock_backend):
        """Test that copy_all_playlists command supports checkpoint functionality"""
        from spotify2ytmusic import cli

        # Mock backend.copy_all_playlists to avoid actual execution
        mock_backend.copy_all_playlists.return_value = None

        # Call copy_all_playlists (it will parse sys.argv internally)
        cli.copy_all_playlists()

        # Verify that resume parameter was passed to backend
        mock_backend.copy_all_playlists.assert_called_once()
        call_args = mock_backend.copy_all_playlists.call_args
        self.assertTrue(call_args.kwargs['resume'], "resume should be True")
        self.assertFalse(call_args.kwargs['reset_checkpoint'], "reset_checkpoint should be False")

    def test_cli_imports_checkpoint_manager(self):
        """Test that CLI module imports CheckpointManager"""
        # This should fail because CLI doesn't import CheckpointManager yet
        from spotify2ytmusic import cli

        # This will fail in RED phase because CheckpointManager is not imported
        self.assertTrue(hasattr(cli, 'CheckpointManager'), "CLI should import CheckpointManager")

    @patch('sys.argv', ['copy_playlist', 'spotify_123', 'youtube_456', '--resume'])
    @patch('spotify2ytmusic.cli.CheckpointManager')
    def test_cli_resume_command_shows_progress_statistics(self, mock_checkpoint_class):
        """Test that CLI resume command shows detailed progress statistics"""
        # This test expects CLI to show detailed progress info that doesn't exist yet

        # Mock CheckpointManager to return expected statistics
        mock_checkpoint = Mock()
        mock_checkpoint_class.return_value = mock_checkpoint
        mock_checkpoint.checkpoint_path.exists.return_value = True
        mock_checkpoint.get_statistics.return_value = {
            "successful": 35,
            "failed": 1,
            "last_index": 35
        }

        with patch('spotify2ytmusic.cli.backend.copy_playlist') as mock_copy:
            from spotify2ytmusic import cli

            # Capture output
            with patch('builtins.print') as mock_print:
                cli.copy_playlist()

            # Verify expected progress display features
            output_calls = [call.args[0] for call in mock_print.call_args_list]
            output_text = '\n'.join(output_calls)

            # These features should be displayed
            self.assertIn("Progress: 41% complete", output_text, "Should show progress percentage")
            self.assertIn("Transfer speed: 12 tracks/min", output_text, "Should show transfer speed")
            self.assertIn("Estimated time remaining: 5 minutes", output_text, "Should show ETA")
            self.assertIn("Error summary: 1 failed (details below)", output_text, "Should show error summary")

    # Feature Integration Tests
    def test_checkpoint_automatically_removes_duplicates_from_source(self):
        """Test that checkpoint system automatically removes duplicate tracks from playlists.json"""
        # This test expects automatic duplicate removal that doesn't exist yet

        # Create a playlist with duplicate tracks
        test_playlist = {
            "playlists": [{
                "name": "Test Playlist",
                "id": "test_123",
                "tracks": [
                    {"track": {"name": "Song 1", "id": "track_1", "artists": [{"name": "Artist 1"}]}},
                    {"track": {"name": "Song 2", "id": "track_2", "artists": [{"name": "Artist 2"}]}},
                    {"track": {"name": "Song 1", "id": "track_1", "artists": [{"name": "Artist 1"}]}},  # Duplicate
                    {"track": {"name": "Song 3", "id": "track_3", "artists": [{"name": "Artist 3"}]}},
                ]
            }]
        }

        checkpoint = CheckpointManager("test_123", str(self.checkpoint_dir))

        # This feature doesn't exist yet - should automatically detect and remove duplicates
        unique_tracks = checkpoint.get_deduplicated_tracks(test_playlist["playlists"][0]["tracks"])

        # Should return only 3 unique tracks, removing the duplicate
        self.assertEqual(len(unique_tracks), 3, "Should remove duplicate tracks")
        track_ids = [track["track"]["id"] for track in unique_tracks]
        self.assertEqual(track_ids, ["track_1", "track_2", "track_3"], "Should preserve unique tracks in order")


    def test_checkpoint_supports_playlist_filtering_and_smart_resume(self):
        """Test that checkpoint system supports filtering tracks and smart resume based on criteria"""
        # This test expects advanced filtering that doesn't exist yet

        checkpoint = CheckpointManager("filter_test", str(self.checkpoint_dir))

        # This feature doesn't exist yet - filtering criteria
        filter_criteria = {
            "skip_explicit": True,
            "min_duration_seconds": 30,
            "max_duration_seconds": 600,
            "skip_genres": ["podcast", "audiobook"],
            "only_albums": False
        }

        checkpoint.set_filtering_criteria(filter_criteria)

        # Should filter tracks based on criteria
        test_tracks = [
            {"name": "Good Song", "explicit": False, "duration_ms": 180000},
            {"name": "Explicit Song", "explicit": True, "duration_ms": 200000},
            {"name": "Too Short", "explicit": False, "duration_ms": 15000},
        ]

        filtered_tracks = checkpoint.apply_filtering(test_tracks)

        # Should only include tracks that meet criteria
        self.assertEqual(len(filtered_tracks), 1, "Should filter tracks based on criteria")
        self.assertEqual(filtered_tracks[0]["name"], "Good Song", "Should keep track that meets criteria")

        # Should save filtering stats
        stats = checkpoint.get_filtering_statistics()
        self.assertEqual(stats["filtered_out"], 2, "Should track filtered tracks")
        self.assertEqual(stats["reasons"]["explicit"], 1, "Should track filter reasons")
        self.assertEqual(stats["reasons"]["duration"], 1, "Should track filter reasons")




if __name__ == "__main__":
    unittest.main()