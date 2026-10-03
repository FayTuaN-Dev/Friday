"""Rend visibles les DLL CUDA installées par pip (nvidia-cublas-cu12, nvidia-cudnn-cu12)."""

import os
import sys
from pathlib import Path


def register_cuda_dlls() -> None:
    if sys.platform != "win32":
        return
    try:
        import nvidia
    except ImportError:
        return
    for base in nvidia.__path__:
        for bin_dir in Path(base).glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            # ctranslate2 charge certaines DLL via le PATH classique
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
