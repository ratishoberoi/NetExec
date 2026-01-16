import io
from nxc.netexec import run_engine

def run_netexec(args: list[str]) -> dict:
    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        run_engine(args, stdout, stderr)
        return {
            "returncode": 0,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        }
    except Exception as e:
        return {
            "returncode": 1,
            "stdout": stdout.getvalue(),
            "stderr": str(e),
        }
