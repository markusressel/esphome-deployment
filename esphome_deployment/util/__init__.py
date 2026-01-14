import json
from os import PathLike
from pathlib import Path
from typing import Optional, Any, Dict, List

from ruamel.yaml import YAML
from ruamel.yaml.comments import TaggedScalar, CommentedMap


def calculate_md5_file(file_path: PathLike | str) -> Optional[str]:
    """
    Calculate the MD5 checksum of a file.

    :param file_path: Path to the file.
    :return: MD5 checksum as a hexadecimal string, or None if the file does not exist, is not a file, or if file_path is None.
    """
    if file_path is None:
        return None
    if isinstance(file_path, str):
        file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    import hashlib
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def calculate_md5_string(content: Any) -> str:
    """
    Calculate the MD5 checksum of a string.

    :param content: The input string.
    :return: MD5 checksum as a hexadecimal string.
    """
    import hashlib
    hash_md5 = hashlib.md5()
    if isinstance(content, dict):
        content = json.dumps(content)
    if not isinstance(content, str):
        content = str(content)
    hash_md5.update(content.encode('utf-8'))
    return hash_md5.hexdigest()


def find_included_header_file_paths(data: Any) -> List[Path]:
    """
    Function to find included header file paths in the data structure.
    Currently not implemented.

    :param data: The input data.
    :return: A list of included header file paths.
    """
    include_list = data.get('esphome', {}).get('includes', [])
    included_file_paths = list(map(lambda x: Path(x), include_list))
    return included_file_paths


def calculate_md5_yaml_recursive(root_path: Path, file_path: Path) -> str:
    """
    Calculate the MD5 checksum of a YAML-like data structure recursively,
    where the "recursive" refers to handling !include tags.

    :param root_path: The root path for resolving header file includes.
    :param file_path: The path to the YAML file.
    :return: MD5 checksum as a hexadecimal string.
    """
    data = load_yaml_file(file_path)
    header_files = find_included_header_file_paths(data)
    included_paths = find_included_paths(data)

    result = calculate_md5_file(file_path)
    for included_file_path in included_paths:
        absolute_included_path = (file_path.parent / included_file_path).resolve()
        included_md5 = calculate_md5_yaml_recursive(root_path, absolute_included_path)
        result += included_md5

    for header_file in header_files:
        absolute_header_path = (root_path / header_file).resolve()
        header_md5 = calculate_md5_file(absolute_header_path)
        result += header_md5

    return calculate_md5_string(result)


def find_included_paths(data: Any) -> List[Path]:
    """
    Recursively find all file paths included via !include tags in the given data structure.

    :param data: The input data (can be dict, list, or primitive types).
    :return: A list of included file paths.
    """
    included_paths = []
    include_tag_trval = '!include'

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, TaggedScalar) and value.tag.trval == include_tag_trval:
                included_paths.append(Path(value.value))
            elif isinstance(value, CommentedMap) and value.tag.trval == include_tag_trval:
                included_paths.append(Path(value.get("file")))
            else:
                included_paths.extend(find_included_paths(value))
    elif isinstance(data, list):
        for item in data:
            included_paths.extend(find_included_paths(item))

    return included_paths


def load_yaml_file(file_path: Path) -> Optional[Dict]:
    """
    Load a YAML file and return its content as a dictionary.

    :param file_path: Path to the YAML file.
    :return: Content of the YAML file as a dictionary, or None if loading fails.
    """
    with file_path.open('r') as f:
        yaml = YAML(typ='rt', pure=True)
        return yaml.load(f)
