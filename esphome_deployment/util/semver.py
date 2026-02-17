import re


class SemVerVersion:
    def __init__(self, version_str: str):
        version_str = version_str.strip().lstrip('v')

        parts = version_str.split('.')
        if len(parts) != 3:
            raise ValueError("Version string must be in 'MAJOR.MINOR.PATCH' format")
        self.major = int(parts[0])
        self.minor = int(parts[1])

        last_part = parts[2]
        match = re.match(r'^(\d+)(.*)', last_part)
        if match:
            self.patch = int(match.group(1))
            self.suffix = match.group(2)  # This will be "b3", "-dev", or ""
        else:
            # Fallback if the patch doesn't start with a number
            raise ValueError(f"Invalid patch version format: '{last_part}'")

    def __lt__(self, other: 'SemVerVersion'):
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        return self.patch < other.patch

    def __eq__(self, other: 'SemVerVersion'):
        return (self.major == other.major and
                self.minor == other.minor and
                self.patch == other.patch and
                self.suffix == other.suffix)

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}{self.suffix}"
