#!/usr/bin/env python

import unittest
from unittest.mock import patch, MagicMock
import spotify2ytmusic
import os
import sys
from io import StringIO

# Get the absolute path to the test data file
TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), "playliststest.json")


class TestCopier(unittest.TestCase):
    @patch("spotify2ytmusic.backend.get_ytmusic")
    @patch('sys.stdout', new_callable=StringIO)
    @patch('time.sleep')
    def test_copier_success(self, mock_sleep, mock_stdout, mock_get_ytmusic):
        # Setup mock responses
        mock_ytmusic_instance = MagicMock()
        mock_get_ytmusic.return_value = mock_ytmusic_instance
        mock_ytmusic_instance.get_playlist.return_value = {"title": "Test Playlist"}
        mock_ytmusic_instance.add_playlist_items.return_value = None

        spotify2ytmusic.backend.copier(
            spotify2ytmusic.backend.iter_spotify_playlist(
                "68QlHDwCiXfhodLpS72iOx",
                spotify_playlist_file=TEST_DATA_PATH,
            ),
            dst_pl_id="dst_test",
        )

        mock_ytmusic_instance.get_playlist.assert_called_once_with(
            playlistId="dst_test"
        )
        # time.sleep is mocked to speed up tests

    @patch("spotify2ytmusic.backend.get_ytmusic")
    @patch('sys.stdout', new_callable=StringIO)
    @patch('time.sleep')
    def test_copier_albums(self, mock_sleep, mock_stdout, mock_get_ytmusic):
        # Setup mock responses
        mock_ytmusic_instance = MagicMock()
        mock_get_ytmusic.return_value = mock_ytmusic_instance
        mock_ytmusic_instance.get_playlist.return_value = {"title": "Test Playlist"}
        mock_ytmusic_instance.add_playlist_items.return_value = None

        spotify2ytmusic.backend.copier(
            spotify2ytmusic.backend.iter_spotify_liked_albums(
                spotify_playlist_file=TEST_DATA_PATH
            ),
            dst_pl_id="dst_test",
        )

        mock_ytmusic_instance.get_playlist.assert_called_once_with(
            playlistId="dst_test"
        )
        # time.sleep is mocked to speed up tests

    @patch("spotify2ytmusic.backend.get_ytmusic")
    @patch('sys.stdout', new_callable=StringIO)
    @patch('time.sleep')
    def test_copier_liked_playlists(self, mock_sleep, mock_stdout, mock_get_ytmusic):
        # Setup mock responses
        mock_ytmusic_instance = MagicMock()
        mock_get_ytmusic.return_value = mock_ytmusic_instance
        mock_ytmusic_instance.get_playlist.return_value = {"title": "Test Playlist"}
        mock_ytmusic_instance.add_playlist_items.return_value = None

        spotify2ytmusic.backend.copier(
            spotify2ytmusic.backend.iter_spotify_playlist(
                "68QlHDwCiXfhodLpS72iOx", spotify_playlist_file=TEST_DATA_PATH
            ),
            dst_pl_id="dst_test",
            track_sleep=0,
        )

        mock_ytmusic_instance.get_playlist.assert_called_once_with(
            playlistId="dst_test"
        )
        # time.sleep is mocked to speed up tests


if __name__ == "__main__":
    unittest.main()
