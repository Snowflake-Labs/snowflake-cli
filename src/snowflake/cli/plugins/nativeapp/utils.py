import os
from pathlib import Path
from sys import stdin, stdout
from typing import List, Optional, Union


def needs_confirmation(needs_confirm: bool, auto_yes: bool) -> bool:
    return needs_confirm and not auto_yes


def is_tty_interactive():
    return stdin.isatty() and stdout.isatty()


def get_first_paragraph_from_markdown_file(file_path: Path) -> Optional[str]:
    """
    Reads a Markdown file at the given file path and finds the first paragraph

    Parameters:
        file_path (Path): Path to Markdown file

    Returns:
        Optional[str]: the first paragraph as a string, or None
        if no paragraph could be found

    Raises:
        FileNotFoundError: if file_path to Markdown file does not exist
    """
    if not file_path.exists():
        raise FileNotFoundError(file_path)

    with open(file_path, "r") as markdown_file:
        paragraph_text = None

        for line in markdown_file:
            stripped_line = line.strip()
            if not stripped_line.startswith("#") and stripped_line:
                paragraph_text = stripped_line
                break

        return paragraph_text


def shallow_git_clone(url: Union[str, os.PathLike], to_path: Union[str, os.PathLike]):
    """
    Performs a shallow clone of the repository at the provided url to the path specified

    Parameters:
        url (str | PathLike): Valid git url.
        to_path (str | PathLike): Path to which the repository should be cloned to.

    Returns:
        Repo: the repository that was cloned
    """
    from git import Repo

    # Clone the repository in the directory with options.
    repo = Repo.clone_from(
        url=url,
        to_path=to_path,
        filter=["tree:0"],
        depth=1,
    )
    # Close repo to avoid issues with permissions on Windows
    repo.close()

    return repo


def is_parent_directory(parent_dir: Path, file_path: Path) -> bool:
    abs_parent = str(parent_dir.resolve())
    abs_file = str(file_path.resolve())
    return abs_file.startswith(abs_parent)


def get_all_file_paths_under_dir(directory: Path) -> List[str]:
    abs_dir = str(directory.resolve())
    file_paths: List[str] = []
    for root, _, files in os.walk(abs_dir):
        for file in files:
            file_path = os.path.join(root, file)
            file_paths.append(file_path)
    return file_paths


def is_single_quoted(name: str) -> bool:
    return name.startswith("'") and name.endswith("'")
