#!/usr/bin/env python

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from ytmusicapi.exceptions import YTMusicServerError
import json

# Add project root to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spotify2ytmusic.backend import copier, SongInfo
from spotify2ytmusic.checkpoint import CheckpointManager


class TestBackendSizeLimit(unittest.TestCase):
    """Test backend size limit functionality - isolated from CLI"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.checkpoint_dir = Path(self.temp_dir) / ".checkpoint"
        self.checkpoint_dir.mkdir(exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_copier_accepts_max_tracks_parameter(self):
        """Test copier() accepts max_tracks parameter"""
        mock_yt = MagicMock()
        checkpoint = CheckpointManager("test", checkpoint_dir=str(self.checkpoint_dir))
        tracks = [SongInfo("Song 1", "Artist 1", "Album 1")]

        with patch('spotify2ytmusic.backend.lookup_song') as mock_lookup:
            mock_lookup.return_value = {"videoId": "vid", "title": "Test", "artists": []}

            copier(
                iter(tracks),
                dst_pl_id="test_id",
                checkpoint_manager=checkpoint,
                yt=mock_yt,
                max_tracks=5000,
                track_sleep=0  # Remove sleep for fast testing
            )

    def test_skip_tracks_beyond_limit(self):
        """Test tracks 5000+ are skipped without API calls"""
        mock_yt = MagicMock()
        checkpoint = CheckpointManager("test", checkpoint_dir=str(self.checkpoint_dir))

        # Create only 10 tracks for fast testing (simulate indices 4995-5004)
        tracks = [SongInfo(f"Song {i}", f"Artist {i}", f"Album {i}")
                 for i in range(4995, 5005)]

        with patch('spotify2ytmusic.backend.lookup_song') as mock_lookup:
            mock_lookup.return_value = {"videoId": "vid", "title": "Test", "artists": []}

            # Mock enumerate to simulate we're at track 4995+
            original_enumerate = enumerate
            def mock_enumerate(iterable, start=0):
                return original_enumerate(iterable, start=4995)

            with patch('builtins.enumerate', side_effect=mock_enumerate):
                copier(
                    iter(tracks),
                    dst_pl_id="test_id",
                    checkpoint_manager=checkpoint,
                    yt=mock_yt,
                    max_tracks=5000,
                    track_sleep=0  # Remove sleep for fast testing
                )

        # Should only add first 5 tracks (indices 4995-4999), skip 5 tracks (5000-5004)
        self.assertEqual(mock_yt.add_playlist_items.call_count, 5)

        # Verify failed file is created for skipped tracks
        failed_file = self.checkpoint_dir / "test.failed"
        self.assertTrue(failed_file.exists())

    def test_handle_server_error_gracefully(self):
        """Test YTMusicServerError is handled gracefully"""
        mock_yt = MagicMock()

        # Simulate server error
        mock_yt.add_playlist_items.side_effect = YTMusicServerError("Maximum playlist size exceeded.")
        checkpoint = CheckpointManager("test", checkpoint_dir=str(self.checkpoint_dir))

        tracks = [SongInfo("Song 1", "Artist 1", "Album 1")]

        with patch('spotify2ytmusic.backend.lookup_song') as mock_lookup:
            mock_lookup.return_value = {"videoId": "vid", "title": "Test", "artists": []}

            # Should handle the error gracefully and exit cleanly
            copier(iter(tracks), dst_pl_id="test_id", checkpoint_manager=checkpoint, yt=mock_yt, track_sleep=0)


class TestCLISizeLimit(unittest.TestCase):
    """Test CLI size limit functionality - isolated from backend"""

    def test_check_playlist_sizes_function_exists(self):
        """Test CLI check_playlist_sizes function exists and works correctly"""
        from spotify2ytmusic.cli import check_playlist_sizes

        playlists = [
            {"id": "1", "name": "Small", "tracks": [{"track": {}}] * 100},
            {"id": "2", "name": "Large", "tracks": [{"track": {}}] * 6000},
        ]

        oversized = check_playlist_sizes(playlists)
        self.assertEqual(len(oversized), 1)
        self.assertEqual(oversized[0]["name"], "Large")

    def test_display_size_warning_function_exists(self):
        """Test CLI display_size_warning function exists and works correctly"""
        from spotify2ytmusic.cli import display_size_warning

        oversized = [{"name": "Large", "track_count": 6000, "over_limit": 1000}]

        # Mock input to return 'n' (no)
        with patch('builtins.input', return_value='n'):
            result = display_size_warning(oversized)
            self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()