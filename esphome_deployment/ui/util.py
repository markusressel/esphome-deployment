import hashlib


def get_device_color(name: str) -> str:
    """Consistently maps a name to a vibrant Rich color string."""
    hash_val = int(hashlib.md5(name.encode()).hexdigest(), 16)

    # ANSI colors 17-231 contain the main color cube (vibrant colors)
    # We use modulo to pick one
    color_code = (hash_val % 214) + 17
    return f"color({color_code})"
