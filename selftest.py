from io import StringIO
from nxc.netexec import run_engine

def test(name, args, expect):
    out = StringIO()
    err = StringIO()

    run_engine(args, out, err)

    stdout = out.getvalue()
    ok = expect in stdout

    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}")

    if not ok:
        print(stdout)
        print(err.getvalue())

    return ok


def run_selftest():
    print("=== NetExec Self Test ===")

    ok = True
    ok &= test("Version", ["--version"], "Yippie")
    ok &= test("Protocol List", ["--help"], "smb")
    ok &= test("SMB Module", ["smb", "--help"], "shares")

    if ok:
        print("\nALL TESTS PASSED")
    else:
        print("\nSOME TESTS FAILED")


if __name__ == "__main__":
    run_selftest()
