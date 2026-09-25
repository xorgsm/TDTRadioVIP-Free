"""
Proceso ffmpeg simulado para los tests de core/audio_converter.py,
core/audio_editor.py y core/mp3_info.py -- ningún test lanza el ffmpeg
real. El último argumento del comando es siempre el archivo de salida:
FakeFfmpegProcess lo escribe al terminar si el código de salida es 0,
igual que haría ffmpeg.
"""
import io


class FakeFfmpegProcess:
    def __init__(self, cmd, returncode=0, stdout_lines=(), stderr_text="",
                 output_bytes=b"MP3DATA"):
        self.cmd = list(cmd)
        self.returncode = None
        self._final_returncode = returncode
        self.stdout = io.StringIO("".join(stdout_lines))
        self._stderr_text = stderr_text
        self._output_bytes = output_bytes
        self.terminated = False

    def terminate(self):
        self.terminated = True

    def _finish(self):
        if self.returncode is None:
            self.returncode = 1 if self.terminated else self._final_returncode
            if self.returncode == 0:
                with open(self.cmd[-1], "wb") as fh:
                    fh.write(self._output_bytes)
        return self.returncode

    def wait(self, timeout=None):
        return self._finish()

    def communicate(self, timeout=None):
        self._finish()
        return "", self._stderr_text


class FakePopenFactory:
    """Sustituto de subprocess.Popen que devuelve FakeFfmpegProcess y guarda cada uno."""

    def __init__(self, **process_kwargs):
        self.process_kwargs = process_kwargs
        self.processes = []
        self.on_create = None  # callback(proceso) justo tras crearlo

    def __call__(self, cmd, **kwargs):
        proceso = FakeFfmpegProcess(cmd, **self.process_kwargs)
        self.processes.append(proceso)
        if self.on_create is not None:
            self.on_create(proceso)
        return proceso
