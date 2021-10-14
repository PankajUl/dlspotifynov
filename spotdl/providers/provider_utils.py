from pathlib import Path
from typing import List
from urllib.parse import quote

from bs4 import BeautifulSoup
from requests import get
from thefuzz import fuzz


def _match_percentage(str1: str, str2: str, score_cutoff: float = 0) -> float:
    """
    A wrapper around `thefuzz.fuzz.partial_ratio` to handle UTF-8 encoded
    emojis that usually cause errors

    `str` `str1` : a random sentence
    `str` `str2` : another random sentence
    `float` `score_cutoff` : minimum score required to consider it a match
        returns 0 when similarity < score_cutoff

    RETURNS `float`
    """

    # ! this will throw an error if either string contains a UTF-8 encoded emoji
    try:
        partial_ratio = fuzz.partial_ratio(str1, str2)

        if partial_ratio < score_cutoff:
            return 0

        return partial_ratio

    # ! we build new strings that contain only alphanumerical characters and spaces
    # ! and return the partial_ratio of that
    except:  # noqa:E722
        new_str1 = "".join(
            each_letter
            for each_letter in str1
            if each_letter.isalnum() or each_letter.isspace()
        )

        new_str2 = "".join(
            each_letter
            for each_letter in str2
            if each_letter.isalnum() or each_letter.isspace()
        )

        partial_ratio = fuzz.partial_ratio(new_str1, new_str2)

        if partial_ratio < score_cutoff:
            return 0

        return partial_ratio


def _parse_duration(duration: str) -> float:
    """
    Convert string value of time (duration: "25:36:59") to a float value of seconds (92219.0)
    """
    try:
        # {(1, "s"), (60, "m"), (3600, "h")}
        mapped_increments = zip([1, 60, 3600], reversed(duration.split(":")))
        seconds = sum(multiplier * int(time) for multiplier, time in mapped_increments)
        return float(seconds)

    # ! This usually occurs when the wrong string is mistaken for the duration
    except (ValueError, TypeError, AttributeError):
        return 0.0


def _create_song_title(song_name: str, song_artists: List[str]) -> str:
    joined_artists = ", ".join(song_artists)
    return f"{joined_artists} - {song_name}"


def _get_song_lyrics(
    song_name: str, song_artists: List[str], track_search=False
) -> str:
    """
    `str` `song_name` : Name of song

    `list<str>` `song_artists` : list containing name of contributing artists

    `bool` `track_search` : if `True`, search the musixmatch tracks page.

    RETURNS `str`: Lyrics of the song.

    Gets the lyrics of the song.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36"
    }

    # remove artist names that are already in the song_name
    # we do not use SongObject.create_file_name beacause it
    # removes '/' etc from the artist and song names.
    artists_str = ", ".join(
        artist for artist in song_artists if artist.lower() not in song_name.lower()
    )

    # quote the query so that it's safe to use in a url
    # e.g "Au/Ra" -> "Au%2FRa"
    query = quote(f"{song_name} - {artists_str}", safe="")
    
    # search the `tracks page` if track_search is True
    if track_search:
        query += "/tracks"

    search_url = f"https://www.musixmatch.com/search/{query}"
    search_resp = get(search_url, headers=headers)
    if not search_resp.ok:
        return ""

    search_soup = BeautifulSoup(search_resp.text, "html.parser")
    song_url_tag = search_soup.select_one("a[href^='/lyrics/']")

    # song_url_tag being None means no results were found on the
    # All Results page, therefore, we use `track_search` to
    # search the tracks page.
    if song_url_tag is None:
        # track_serach being True means we are already searching the tracks page.
        if track_search:
            return ""

        lyrics = _get_song_lyrics(song_name, song_artists, track_search=True)
        return lyrics

    song_url = "https://www.musixmatch.com" + song_url_tag.get("href")
    lyrics_resp = get(song_url, headers=headers)
    if not lyrics_resp.ok:
        return ""

    lyrics_soup = BeautifulSoup(lyrics_resp.text, "html.parser")
    lyrics_paragraphs = lyrics_soup.select("p.mxm-lyrics__content")
    lyrics = "\n".join(i.get_text() for i in lyrics_paragraphs)

    return lyrics


def _sanitize_filename(input_str: str) -> str:
    output = input_str

    # ! this is windows specific (disallowed chars)
    output = "".join(char for char in output if char not in "/?\\*|<>")

    # ! double quotes (") and semi-colons (:) are also disallowed characters but we would
    # ! like to retain their equivalents, so they aren't removed in the prior loop
    output = output.replace('"', "'").replace(":", "-")

    return output


def _get_smaller_file_path(input_song, output_format: str) -> Path:
    # Only use the first artist if the song path turns out to be too long
    smaller_name = f"{input_song.contributing_artists[0]} - {input_song.song_name}"

    smaller_name = _sanitize_filename(smaller_name)

    try:
        return Path(f"{smaller_name}.{output_format}").resolve()
    except OSError:
        # Expected to happen in the rare case when the saved path is too long,
        # even with the short filename
        raise OSError("Cannot save song due to path issues.")


def _get_converted_file_path(song_obj, output_format: str = None) -> Path:

    # ! we eliminate contributing artist names that are also in the song name, else we
    # ! would end up with things like 'Jetta, Mastubs - I'd love to change the world
    # ! (Mastubs REMIX).mp3' which is kinda an odd file name.

    # also make sure that main artist is included in artistStr even if they
    # are in the song name, for example
    # Lil Baby - Never Recover (Lil Baby & Gunna, Drake).mp3

    artists_filtered = []

    if output_format is None:
        output_format = "mp3"

    for artist in song_obj.contributing_artists:
        if artist.lower() not in song_obj.song_name:
            artists_filtered.append(artist)
        elif artist.lower() is song_obj.contributing_artists[0].lower():
            artists_filtered.append(artist)

    artist_str = ", ".join(artists_filtered)

    converted_file_name = _sanitize_filename(
        f"{artist_str} - {song_obj.song_name}.{output_format}"
    )

    converted_file_path = Path(converted_file_name)

    # ! Checks if a file name is too long (256 max on both linux and windows)
    try:
        if len(str(converted_file_path.resolve().name)) > 256:
            print("Path was too long. Using Small Path.")
            return _get_smaller_file_path(song_obj, output_format)
    except OSError:
        return _get_smaller_file_path(song_obj, output_format)

    return converted_file_path
