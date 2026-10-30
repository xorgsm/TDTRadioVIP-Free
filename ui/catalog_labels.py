"""Etiquetas legibles en español para los metadatos del catálogo IPTV."""

import re


_GROUP_LABELS = {
    "undefined": "Sin categoría",
    "general": "General",
    "public": "Público",
    "news": "Noticias",
    "entertainment": "Entretenimiento",
    "series": "Series",
    "movies": "Cine",
    "music": "Música",
    "religious": "Religión",
    "documentary": "Documentales",
    "legislative": "Parlamento",
    "kids": "Infantil",
    "sports": "Deportes",
    "weather": "Tiempo",
    "culture": "Cultura",
    "education": "Educación",
    "lifestyle": "Estilo de vida",
    "comedy": "Comedia",
    "classic": "Clásicos",
    "business": "Economía",
    "cooking": "Cocina",
    "travel": "Viajes",
    "science": "Ciencia",
    "shop": "Compras",
    "outdoor": "Aire libre",
    "family": "Familia",
    "animation": "Animación",
    "auto": "Motor",
    "relax": "Relax",
    "local": "Local",
    "interactive": "Interactivo",
    "other": "Otros",
    "xxx": "Adultos",
}

_TAG_LABELS = {
    "geo-blocked": "Bloqueo geográfico",
    "not 24/7": "No emite 24/7",
    "offline": "Sin señal",
}
_TRAILING_TAG = re.compile(r"\[([^\[\]]+)\]\s*$")


def humanize_group(name: str) -> str:
    """Traduce las categorías separadas por punto y coma, sin repetirlas."""
    labels = []
    seen = set()
    for part in (name or "").split(";"):
        part = part.strip()
        if not part:
            continue
        label = _GROUP_LABELS.get(part.casefold(), part)
        key = label.casefold()
        if key not in seen:
            seen.add(key)
            labels.append(label)
    return " · ".join(labels) or "Sin categoría"


def split_name_tags(name: str) -> tuple[str, list[str]]:
    """Extrae y traduce solo las etiquetas al final, conservando su orden."""
    remaining = name
    tags = []
    while match := _TRAILING_TAG.search(remaining):
        tag = match.group(1).strip()
        tags.append(_TAG_LABELS.get(tag.casefold(), tag))
        remaining = remaining[:match.start()].rstrip()

    # Un nombre compuesto solo por etiquetas sigue siendo un nombre válido.
    if not tags or not remaining.strip():
        return name, []
    return remaining, list(reversed(tags))
