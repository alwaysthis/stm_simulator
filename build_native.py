"""Build the optional native backend with MinGW g++ (no Python headers needed)."""
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parent
compiler = shutil.which("g++")
if compiler is None:
    raise SystemExit("Install MinGW-w64 and add g++ to PATH, then run this script again.")
target = root / "stm_simulator" / ("_stm_native_v2.dll" if sys.platform == "win32" else "_stm_native_v2.so")
subprocess.run([compiler, "-O3", "-std=c++17", "-shared", "-static", "-static-libgcc", "-static-libstdc++",
                str(root / "native" / "stm_native.cpp"), "-o", str(target)], check=True)
print(target)
