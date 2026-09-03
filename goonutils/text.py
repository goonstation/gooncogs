def ckeyify(text: str) -> str:
    """Normalize text to the lowercase alphanumeric format used by BYOND ckeys."""
    return "".join(character.lower() for character in text if character.isalnum())
