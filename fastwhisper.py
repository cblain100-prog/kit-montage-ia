"""Whisper on the Apple GPU (mlx-whisper), same call as openai-whisper: load_model(name).transcribe(audio, **kw).
openai-whisper runs FP32 on the CPU here: the full-video retake check and `takes` took over 30 min each and were cut
(2026-10-01). Falls back to openai-whisper when mlx is missing."""


class _Mlx:
    def __init__(self, name):
        self.repo = f"mlx-community/whisper-{name}-mlx"

    def transcribe(self, audio, **kw):
        import mlx_whisper
        return mlx_whisper.transcribe(audio, path_or_hf_repo=self.repo, **kw)


def load_model(name="medium"):
    try:
        import mlx_whisper  # noqa: F401
        return _Mlx(name)
    except ImportError:
        import whisper
        return whisper.load_model(name)
