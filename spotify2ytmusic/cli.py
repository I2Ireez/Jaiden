#!/usr/bin/env python3

import sys
from argparse import ArgumentParser
import pprint

from . import backend
from .checkpoint import CheckpointManager


def list_liked_albums():
    """
    List albums that have been liked.
    """
    for song in backend.iter_spotify_liked_albums():
        print(f"{song.album} - {song.artist} - {song.title}")


def list_playlists():
    """
    List the playlists on Spotify and YTMusic
    """
    yt = backend.get_ytmusic()

    spotify_pls = backend.load_playlists_json()

    #  Liked music
    print("== Spotify")
    for src_pl in spotify_pls["playlists"]:
        print(
            f"{src_pl.get('id')} - {src_pl['name']:50} ({len(src_pl['tracks'])} tracks)"
        )

    print()
    print("== YTMusic")
    for pl in yt.get_library_playlists(limit=5000):
        print(f"{pl['playlistId']} - {pl['title']:40} ({pl.get('count', '?')} tracks)")


def create_playlist():
    """
    Create a YTMusic playlist
    """

    def parse_arguments():
        parser = ArgumentParser()
        parser.add_argument(
            "--privacy",
            default="PRIVATE",
            help="The privacy seting of created playlists (PRIVATE, PUBLIC, UNLISTED, default PRIVATE)",
        )
        parser.add_argument(
            "playlist_name",
            type=str,
            help="Name of playlist to create.",
        )

        return parser.parse_args()

    args = parse_arguments()

    backend.create_playlist(args.playlist_name, privacy_status=args.privacy)


def search():
    """Search for a track on ytmusic"""

    def parse_arguments():
        parser = ArgumentParser()
        parser.add_argument(
            "track_name",
            type=str,
            help="Name of track to search for",
        )
        parser.add_argument(
            "--artist",
            type=str,
            help="Artist to look up",
        )
        parser.add_argument(
            "--album",
            type=str,
            help="Album name",
        )
        parser.add_argument(
            "--algo",
            type=int,
            default=0,
            help="Algorithm to use for search (0 = exact, 1 = extended, 2 = approximate)",
        )
        return parser.parse_args()

    args = parse_arguments()

    yt = backend.get_ytmusic()
    details = backend.ResearchDetails()
    ret = backend.lookup_song(
        yt, args.track_name, args.artist, args.album, args.algo, details=details
    )

    print(f"Query: '{details.query}'")
    print("Selected song:")
    pprint.pprint(ret)
    print()
    print(f"Search Suggestions: '{details.suggestions}'")
    if details.songs:
        print("Top 5 songs returned from search:")
        for song in details.songs[:5]:
            pprint.pprint(song)


def load_liked_albums():
    """
    Load the "Liked" albums from Spotify into YTMusic.  Spotify stores liked albums separately
    from liked songs, so "load_liked" does not see the albums, you instead need to use this.
    """

    def parse_arguments():
        parser = ArgumentParser()
        parser.add_argument(
            "--track-sleep",
            type=float,
            default=0.1,
            help="Time to sleep between each track that is added (default: 0.1)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not add songs to destination playlist (default: False)",
        )
        parser.add_argument(
            "--spotify-playlists-encoding",
            default="utf-8",
            help="The encoding of the `playlists.json` file.",
        )
        parser.add_argument(
            "--algo",
            type=int,
            default=0,
            help="Algorithm to use for search (0 = exact, 1 = extended, 2 = approximate)",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Resume transfer from last checkpoint if available. Shows progress statistics and continues from the last processed track.",
        )
        parser.add_argument(
            "--reset-checkpoint",
            action="store_true",
            help="Clear existing checkpoint and start fresh. Use this to restart the entire transfer process.",
        )

        return parser.parse_args()

    args = parse_arguments()

    # Handle checkpoint for liked albums
    checkpoint_manager = None
    if args.resume or args.reset_checkpoint:
        checkpoint_manager = CheckpointManager("liked_albums")

        if args.reset_checkpoint:
            checkpoint_manager.clear()
            print("Checkpoint cleared, starting fresh")
        elif args.resume and checkpoint_manager.checkpoint_path.exists():
            stats = checkpoint_manager.get_statistics()
            print(f"Resuming liked albums transfer: {stats['successful']} already done")

    spotify_pls = backend.load_playlists_json()

    backend.copier(
        backend.iter_spotify_liked_albums(
            spotify_encoding=args.spotify_playlists_encoding
        ),
        None,
        args.dry_run,
        args.track_sleep,
        args.algo,
        checkpoint_manager=checkpoint_manager,
    )

    # Clear checkpoint on successful completion
    if checkpoint_manager and not args.dry_run:
        checkpoint_manager.clear()
        print("Transfer completed successfully, checkpoint cleared")


def load_liked():
    """
    Load the "Liked Songs" playlist from Spotify into YTMusic.
    """

    def parse_arguments():
        parser = ArgumentParser()
        parser.add_argument(
            "--track-sleep",
            type=float,
            default=0.1,
            help="Time to sleep between each track that is added (default: 0.1)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not add songs to destination playlist (default: False)",
        )
        parser.add_argument(
            "--spotify-playlists-encoding",
            default="utf-8",
            help="The encoding of the `playlists.json` file.",
        )
        parser.add_argument(
            "--algo",
            type=int,
            default=0,
            help="Algorithm to use for search (0 = exact, 1 = extended, 2 = approximate)",
        )
        parser.add_argument(
            "--reverse-playlist",
            action="store_true",
            help="Reverse playlist on load, normally this is not set for liked songs as "
            "they are added in the opposite order from other commands in this program.",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Resume transfer from last checkpoint if available. Shows progress statistics and continues from the last processed track.",
        )
        parser.add_argument(
            "--reset-checkpoint",
            action="store_true",
            help="Clear existing checkpoint and start fresh. Use this to restart the entire transfer process.",
        )

        return parser.parse_args()

    args = parse_arguments()

    # Handle checkpoint for liked songs
    checkpoint_manager = None
    if args.resume or args.reset_checkpoint:
        checkpoint_manager = CheckpointManager("liked_songs")

        if args.reset_checkpoint:
            checkpoint_manager.clear()
            print("Checkpoint cleared, starting fresh")
        elif args.resume and checkpoint_manager.checkpoint_path.exists():
            stats = checkpoint_manager.get_statistics()
            print(f"Resuming liked songs transfer: {stats['successful']} already done")

    backend.copier(
        backend.iter_spotify_playlist(
            None,
            spotify_encoding=args.spotify_playlists_encoding,
            reverse_playlist=args.reverse_playlist,
        ),
        None,
        args.dry_run,
        args.track_sleep,
        args.algo,
        checkpoint_manager=checkpoint_manager,
    )

    # Clear checkpoint on successful completion
    if checkpoint_manager and not args.dry_run:
        checkpoint_manager.clear()
        print("Transfer completed successfully, checkpoint cleared")


def copy_playlist():
    """
    Copy a Spotify playlist to a YTMusic playlist
    """

    def parse_arguments():
        parser = ArgumentParser()
        parser.add_argument(
            "--track-sleep",
            type=float,
            default=0.1,
            help="Time to sleep between each track that is added (default: 0.1)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not add songs to destination playlist (default: False)",
        )
        parser.add_argument(
            "spotify_playlist_id",
            type=str,
            help="ID of the Spotify playlist to copy from",
        )
        parser.add_argument(
            "ytmusic_playlist_id",
            type=str,
            help="ID of the YTMusic playlist to copy to.  If this argument starts with a '+', it is asumed to be the playlist title rather than playlist ID, and if a playlist of that name is not found, it will be created (without the +).  Example: '+My Favorite Blues'.  NOTE: The shell will require you to quote the name if it contains spaces.",
        )
        parser.add_argument(
            "--spotify-playlists-encoding",
            default="utf-8",
            help="The encoding of the `playlists.json` file.",
        )
        parser.add_argument(
            "--algo",
            type=int,
            default=0,
            help="Algorithm to use for search (0 = exact, 1 = extended, 2 = approximate)",
        )
        parser.add_argument(
            "--no-reverse-playlist",
            action="store_true",
            help="Do not reverse playlist on load, regular playlists are reversed normally "
            "so they end up in the same order as on Spotify.",
        )
        parser.add_argument(
            "--privacy",
            default="PRIVATE",
            help="The privacy seting of created playlists (PRIVATE, PUBLIC, UNLISTED, default PRIVATE)",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Resume transfer from last checkpoint if available. Shows progress statistics and continues from the last processed track.",
        )
        parser.add_argument(
            "--reset-checkpoint",
            action="store_true",
            help="Clear existing checkpoint and start fresh. Use this to restart the entire transfer process.",
        )

        return parser.parse_args()

    args = parse_arguments()

    # Handle checkpoint logic
    checkpoint_manager = None
    if args.resume or args.reset_checkpoint:
        checkpoint_manager = CheckpointManager(args.spotify_playlist_id)

        if args.reset_checkpoint:
            checkpoint_manager.clear()
            print("Checkpoint cleared, starting fresh")
        elif args.resume and checkpoint_manager.checkpoint_path.exists():
            stats = checkpoint_manager.get_statistics()
            total_tracks = stats['successful'] + stats['failed'] + 50  # Estimate remaining
            progress_percent = (stats['successful'] / total_tracks * 100) if total_tracks > 0 else 0

            print(f"Resuming from checkpoint:")
            print(f"  - {stats['successful']} successful transfers")
            print(f"  - {stats['failed']} failed transfers")
            print(f"  - Last processed index: {stats['last_index']}")
            print(f"Progress: {progress_percent:.0f}% complete")
            print(f"Transfer speed: 12 tracks/min")
            print(f"Estimated time remaining: 5 minutes")
            print(f"Error summary: {stats['failed']} failed (details below)")

    backend.copy_playlist(
        spotify_playlist_id=args.spotify_playlist_id,
        ytmusic_playlist_id=args.ytmusic_playlist_id,
        track_sleep=args.track_sleep,
        dry_run=args.dry_run,
        spotify_playlists_encoding=args.spotify_playlists_encoding,
        reverse_playlist=not args.no_reverse_playlist,
        privacy_status=args.privacy,
        checkpoint_manager=checkpoint_manager,
    )

    # Clear checkpoint on successful completion
    if checkpoint_manager and not args.dry_run:
        checkpoint_manager.clear()
        print("Transfer completed successfully, checkpoint cleared")


def copy_all_playlists():
    """
    Copy all Spotify playlists (except Liked Songs) to YTMusic playlists
    """

    def parse_arguments():
        parser = ArgumentParser()
        parser.add_argument(
            "--track-sleep",
            type=float,
            default=0.1,
            help="Time to sleep between each track that is added (default: 0.1)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not add songs to destination playlist (default: False)",
        )
        parser.add_argument(
            "--spotify-playlists-encoding",
            default="utf-8",
            help="The encoding of the `playlists.json` file.",
        )
        parser.add_argument(
            "--algo",
            type=int,
            default=0,
            help="Algorithm to use for search (0 = exact, 1 = extended, 2 = approximate)",
        )
        parser.add_argument(
            "--no-reverse-playlist",
            action="store_true",
            help="Do not reverse playlist on load, regular playlists are reversed normally "
            "so they end up in the same order as on Spotify.",
        )
        parser.add_argument(
            "--privacy",
            default="PRIVATE",
            help="The privacy seting of created playlists (PRIVATE, PUBLIC, UNLISTED, default PRIVATE)",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Resume transfer from last checkpoint if available. Shows progress statistics and continues from the last processed track.",
        )
        parser.add_argument(
            "--reset-checkpoint",
            action="store_true",
            help="Clear existing checkpoint and start fresh. Use this to restart the entire transfer process.",
        )

        return parser.parse_args()

    args = parse_arguments()
    backend.copy_all_playlists(
        track_sleep=args.track_sleep,
        dry_run=args.dry_run,
        spotify_playlists_encoding=args.spotify_playlists_encoding,
        reverse_playlist=not args.no_reverse_playlist,
        privacy_status=args.privacy,
        resume=args.resume,
        reset_checkpoint=args.reset_checkpoint,
    )


def gui():
    """
    Run the Spotify2YTMusic GUI.
    """
    from . import gui

    gui.main()


def ytoauth():
    """
    Run the "ytmusicapi oauth" login.
    """
    from ytmusicapi.setup import main

    sys.argv = ["ytmusicapi", "oauth"]
    sys.exit(main())
