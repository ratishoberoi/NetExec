from os.path import join
import os

try:
    from importlib.resources import files
except ImportError:
    from importlib_resources import files


# This is the embedded nxc package root (works inside Nuitka EXE)
NXC_PKG = files("nxc")

# Internal immutable data shipped with the exe
DATA_PATH = str(NXC_PKG.joinpath("data"))

# Runtime workspace (allowed to be on disk)
NXC_PATH = os.path.join(os.path.expanduser("~"), ".nxc")

TMP_PATH = join(NXC_PATH, "tmp")
CONFIG_PATH = join(NXC_PATH, "nxc.conf")
WORKSPACE_DIR = join(NXC_PATH, "workspaces")
