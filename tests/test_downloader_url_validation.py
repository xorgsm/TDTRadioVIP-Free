import pytest

from core.downloader import DownloadWorker, url_valida_para_descarga


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=abc123",
    "http://example.com/video",
])
def test_valid_http_urls_are_accepted(url):
    assert url_valida_para_descarga(url) is True


@pytest.mark.parametrize("url", [
    "",
    "not a url",
    "ftp://example.com/video",
    "--exec=calc.exe",
    "-o pwned.txt https://example.com",
    "file:///etc/passwd",
])
def test_non_http_or_flag_like_values_are_rejected(url):
    assert url_valida_para_descarga(url) is False


def test_construir_comando_uses_double_dash_separator_before_url():
    worker = DownloadWorker("https://example.com/video", ".", as_mp3=False)
    cmd = worker._construir_comando("yt-dlp.exe", "salida.txt")

    assert cmd[-2:] == ["--", "https://example.com/video"]
