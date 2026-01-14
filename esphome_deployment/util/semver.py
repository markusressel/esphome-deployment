class SemVerVersion:
    def __init__(self, version_str: str):
        parts = version_str.split('.')
        if len(parts) != 3:
            raise ValueError("Version string must be in 'MAJOR.MINOR.PATCH' format")
        self.major = int(parts[0])
        self.minor = int(parts[1])
        self.patch = int(parts[2])

    def __lt__(self, other: 'SemVerVersion'):
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        return self.patch < other.patch

    def __eq__(self, other: 'SemVerVersion'):
        return (self.major == other.major and
                self.minor == other.minor and
                self.patch == other.patch)

    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"
