# PYTHON_ARGCOMPLETE_OK
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
from nxc.helpers.logger import highlight
from nxc.helpers.misc import identify_target_file, display_modules
from nxc.parsers.ip import parse_targets
from nxc.parsers.nmap import parse_nmap_xml
from nxc.parsers.nessus import parse_nessus_file
from nxc.cli import gen_cli_args
from nxc.cli import ArgParseExit
from nxc.loaders.protocolloader import ProtocolLoader
from nxc.loaders.moduleloader import ModuleLoader
from nxc.first_run import first_run_setup
from nxc.paths import NXC_PATH, WORKSPACE_DIR
from nxc.logger import nxc_logger
from nxc.config import nxc_config, nxc_workspace, config_log
from nxc.database import create_db_engine
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
from nxc.helpers import powershell
import shutil
import os
from os.path import exists, join as path_join
from rich.progress import Progress
import platform
from nxc.console import make_console
from nxc import console
class ArgParseExit(Exception):
    pass

import argparse
argparse.ArgumentParser.exit = lambda self, *a, **k: (_ for _ in ()).throw(ArgParseExit())

if sys.stdout and sys.stdout.encoding == "cp1252":
    sys.stdout.reconfigure(encoding="utf-8")


# Increase file_limit to prevent error "Too many open files"
if platform.system() != "Windows":
    import resource
    file_limit = list(resource.getrlimit(resource.RLIMIT_NOFILE))
    file_limit[0] = min(file_limit[1], 10000)
    resource.setrlimit(resource.RLIMIT_NOFILE, tuple(file_limit))


async def start_run(protocol_obj, args, db, targets):
    futures = []

    if args.no_progress or len(targets) == 1:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            futures = [executor.submit(protocol_obj, args, db, t) for t in targets]
    else:
        with Progress(console=console.nxc_console) as progress, ThreadPoolExecutor(max_workers=args.threads) as executor:
            task = progress.add_task(
                f"[green]Running nxc against {len(targets)} target(s)",
                total=len(targets),
            )
            futures = [executor.submit(protocol_obj, args, db, t) for t in targets]
            for _ in as_completed(futures):
                progress.update(task, advance=1)

    for future in as_completed(futures):
        try:
            future.result()
        except Exception:
            nxc_logger.exception("Execution error")


def run_engine(argv, stdout, stderr):
    old_argv = sys.argv
    sys.argv = ["nxc"] + list(argv)

    try:
        console.nxc_console = make_console(stdout)

        with redirect_stdout(stdout), redirect_stderr(stderr):
            first_run_setup(nxc_logger)

            try:
                args, version_info = gen_cli_args(argv)
            except (SystemExit,ArgParseExit):
                return

            if config_log:
                nxc_logger.add_file_log()
            if getattr(args, "log", None):
                nxc_logger.add_file_log(args.log)

            if not args.protocol:
                return

            if args.protocol == "ssh" and args.key_file and not args.password:
                nxc_logger.fail("Password required with key file")
                return

            if getattr(args, "use_kcache", False) and not os.environ.get("KRB5CCNAME"):
                nxc_logger.error("KRB5CCNAME not set")
                return

            targets = []

            if getattr(args, "cred_id", None):
                for cid in list(args.cred_id):
                    if "-" in str(cid):
                        start, end = cid.split("-")
                        args.cred_id.remove(cid)
                        args.cred_id.extend(range(int(start), int(end) + 1))

            if getattr(args, "target", None):
                for target in args.target:
                    try:
                        if exists(target) and os.path.isfile(target):
                            ftype = identify_target_file(target)
                            if ftype == "nmap":
                                targets.extend(parse_nmap_xml(target, args.protocol))
                            elif ftype == "nessus":
                                targets.extend(parse_nessus_file(target, args.protocol))
                            else:
                                with open(target) as f:
                                    for line in f:
                                        targets.extend(parse_targets(line.strip()))
                        else:
                            targets.extend(parse_targets(target))
                    except Exception as e:
                        nxc_logger.fail(f"Failed to parse target {target}: {e}")

            if getattr(args, "clear_obfscripts", False):
                obf = os.path.join(NXC_PATH, "obfuscated_scripts")
                shutil.rmtree(obf, ignore_errors=True)
                os.mkdir(obf)
                nxc_logger.success("Cleared obfuscated scripts")

            if getattr(args, "obfs", False):
                powershell.obfuscate_ps_scripts = True

            loader = ProtocolLoader()
            proto_info = loader.get_protocols()[args.protocol]

            # protocol_module = loader.load_protocol(proto_info["path"])
            # protocol_object = None
            # for attr_name in dir(protocol_module):
            #     if attr_name.startswith("_"):
            #         continue

            #     attr = getattr(protocol_module, attr_name)
            #     if isinstance(attr, type):
            #         protocol_object = attr
            #         break

            # if protocol_object is None:
            #     raise RuntimeError(
            #         f"No protocol class found in {proto_info['path']}"
            #     )

            # Load protocol module (smb.py, ldap.py, etc)
            protocol_module = loader.load_protocol(proto_info["path"])
            protocol_object = protocol_module

            # Load protocol database module (database.py)
            protocol_db_module = None
            if "dbpath" in proto_info:
                protocol_db_module = loader.load_protocol(proto_info["dbpath"])

            db_path = path_join(WORKSPACE_DIR, nxc_workspace, f"{args.protocol}.db")
            db_engine = create_db_engine(db_path)

            # Initialize DB schema ONCE
            if hasattr(protocol_db_module, "db_schema"):
                protocol_db_module.db_schema(db_engine)

            # NetExec DOES NOT instantiate DB objects
            db = None
            if protocol_db_module and hasattr(protocol_db_module, "db_schema"):
                protocol_db_module.db_schema(db_engine)

            protocol_object.config = nxc_config

            if args.module or args.list_modules is not None:
                mod_loader = ModuleLoader(args, db, nxc_logger)
                modules = mod_loader.list_modules()

            if args.list_modules is not None:
                low = {m: p for m, p in modules.items() if not p["requires_admin"]}
                high = {m: p for m, p in modules.items() if p["requires_admin"]}
                nxc_logger.highlight("LOW PRIVILEGE MODULES")
                display_modules(args, low)
                nxc_logger.highlight("\nHIGH PRIVILEGE MODULES")
                display_modules(args, high)
                return

            try:
                asyncio.run(start_run(protocol_object, args, db, targets))
            finally:
                db_engine.dispose()

    finally:
        sys.argv = old_argv
