"""Pruebas de las etiquetas del catálogo sin dependencias de Qt."""

import pytest

from ui.catalog_labels import humanize_group, split_name_tags


@pytest.mark.parametrize("name, expected", [
    ("Undefined", "Sin categoría"),
    ("General", "General"),
    ("Public", "Público"),
    ("News", "Noticias"),
    ("Entertainment", "Entretenimiento"),
    ("Series", "Series"),
    ("Movies", "Cine"),
    ("Music", "Música"),
    ("Religious", "Religión"),
    ("Documentary", "Documentales"),
    ("Legislative", "Parlamento"),
    ("Kids", "Infantil"),
    ("Sports", "Deportes"),
    ("Weather", "Tiempo"),
    ("Culture", "Cultura"),
    ("Education", "Educación"),
    ("Lifestyle", "Estilo de vida"),
    ("Comedy", "Comedia"),
    ("Classic", "Clásicos"),
    ("Business", "Economía"),
    ("Cooking", "Cocina"),
    ("Travel", "Viajes"),
    ("Science", "Ciencia"),
    ("Shop", "Compras"),
    ("Outdoor", "Aire libre"),
    ("Family", "Familia"),
    ("Animation", "Animación"),
    ("Auto", "Motor"),
    ("Relax", "Relax"),
    ("Local", "Local"),
    ("Interactive", "Interactivo"),
    ("Other", "Otros"),
    ("XXX", "Adultos"),
])
def test_humanize_known_groups(name, expected):
    """Todas las categorías conocidas se traducen sin distinguir mayúsculas."""
    assert humanize_group(name) == expected
    assert humanize_group(name.swapcase()) == expected


@pytest.mark.parametrize("name, expected", [
    ("", "Sin categoría"),
    (" ; ; \t; \n", "Sin categoría"),
    (" News ; Music ;; News; NEWS ; Sports ", "Noticias · Música · Deportes"),
    (" Categoría propia ", "Categoría propia"),
    ("News; Mi categoría;Music;Mi categoría", "Noticias · Mi categoría · Música"),
    ("News;Noticias", "Noticias"),
])
def test_humanize_group_lists(name, expected):
    """Recorta espacios, omite vacíos y conserva el orden sin duplicados."""
    assert humanize_group(name) == expected


@pytest.mark.parametrize("name, expected", [
    ("3Cat Exclusiu 1 (1080p) [Geo-blocked]",
     ("3Cat Exclusiu 1 (1080p)", ["Bloqueo geográfico"])),
    ("Canal [Not 24/7]", ("Canal", ["No emite 24/7"])),
    ("Canal [Offline]", ("Canal", ["Sin señal"])),
    ("Canal [Geo-blocked][Not 24/7] [Offline]",
     ("Canal", ["Bloqueo geográfico", "No emite 24/7", "Sin señal"])),
    ("Canal [Experimental]", ("Canal", ["Experimental"])),
    ("Canal [ Offline ] [GEO-BLOCKED]  ",
     ("Canal", ["Sin señal", "Bloqueo geográfico"])),
    ("Canal [Offline] [Offline]", ("Canal", ["Sin señal", "Sin señal"])),
    ("[Offline]", ("[Offline]", [])),
    ("  [Geo-blocked] [Offline]  ", ("  [Geo-blocked] [Offline]  ", [])),
    ("Canal [Regional] HD", ("Canal [Regional] HD", [])),
    ("Canal [Regional] HD [Offline]", ("Canal [Regional] HD", ["Sin señal"])),
    ("Canal (1080p)", ("Canal (1080p)", [])),
    (" Canal sin etiquetas  ", (" Canal sin etiquetas  ", [])),
    ("", ("", [])),
    ("Canal [Offline", ("Canal [Offline", [])),
])
def test_split_name_tags(name, expected):
    """Solo extrae etiquetas finales y nunca deja el nombre vacío."""
    assert split_name_tags(name) == expected
