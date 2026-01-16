from run_netexec import run_netexec
from selftest import run_selftest
import sys

if __name__ == "__main__":
    if len(sys.argv) == 1:
        run_selftest()
    else:
        res = run_netexec(sys.argv[1:])
        print(res["stdout"], end="")
        if res["stderr"]:
            print(res["stderr"])
