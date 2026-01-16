class ArgParseExit(Exception):
    pass


import sys
import argparse
import argcomplete
import importlib.metadata
from argparse import RawTextHelpFormatter

from nxc.loaders.protocolloader import ProtocolLoader
from nxc.helpers.logger import highlight
from nxc.helpers.args import DisplayDefaultsNotNone
from nxc.logger import nxc_logger, setup_debug_logging


# hard override argparse exits (as original netexec behaviour)
argparse.ArgumentParser.error = (
    lambda self, message: (_ for _ in ()).throw(ArgParseExit(message))
)
argparse.ArgumentParser.exit = (
    lambda self, status=0, message=None: (_ for _ in ()).throw(ArgParseExit(message))
)


def gen_cli_args(argv=None):
    setup_debug_logging()

    # ---------------- VERSION INFO ----------------
    try:
        meta = importlib.metadata.version("netexec")
    except Exception:
        meta = "0.0.0+local"

    try:
        VERSION, COMMIT = meta.split("+")
        DISTANCE = ""
        if "." in COMMIT:
            DISTANCE, COMMIT = COMMIT.split(".", 1)
    except Exception:
        VERSION = meta
        COMMIT = ""
        DISTANCE = ""

    CODENAME = "Yippie-Ki-Yay"

    # ---------------- BASE PARSERS ----------------
    generic_parser = argparse.ArgumentParser(
        add_help=False, formatter_class=DisplayDefaultsNotNone
    )
    generic_group = generic_parser.add_argument_group("Generic Options")
    generic_group.add_argument("--version", action="store_true", help="Display nxc version")
    generic_group.add_argument("-t", "--threads", type=int, default=256)
    generic_group.add_argument("--timeout", type=int)
    generic_group.add_argument("--jitter", metavar="INTERVAL")

    output_parser = argparse.ArgumentParser(
        add_help=False, formatter_class=DisplayDefaultsNotNone
    )
    output_group = output_parser.add_argument_group("Output Options")
    output_group.add_argument("--no-progress", action="store_true")
    output_group.add_argument("--log", metavar="LOG")
    log_level = output_group.add_mutually_exclusive_group()
    log_level.add_argument("--verbose", action="store_true")
    log_level.add_argument("--debug", action="store_true")

    dns_parser = argparse.ArgumentParser(
        add_help=False, formatter_class=DisplayDefaultsNotNone
    )
    dns_group = dns_parser.add_argument_group("DNS")
    dns_group.add_argument("-6", dest="force_ipv6", action="store_true")
    dns_group.add_argument("--dns-server")
    dns_group.add_argument("--dns-tcp", action="store_true")
    dns_group.add_argument("--dns-timeout", type=int, default=3)

    # ---------------- MAIN PARSER ----------------
    parser = argparse.ArgumentParser(
        exit_on_error=False,
        description=rf"""
     .   .
    .|   |.     _   _          _     _____
    ||   ||    | \ | |   ___  | |_  | ____| __  __   ___    ___
    \\( )//    |  \| |  / _ \ | __| |  _|   \ \/ /  / _ \  / __|
    .=[ ]=.    | |\  | |  __/ | |_  | |___   >  <  |  __/ | (__
   / /˙-˙\ \   |_| \_|  \___|  \__| |_____| /_/\_\  \___|  \___|
   ˙ \   / ˙
     ˙   ˙

    The network execution tool

    {highlight('Version', 'red')} : {highlight(VERSION)}
    {highlight('Codename', 'red')}: {highlight(CODENAME)}
    {highlight('Commit', 'red')}  : {highlight(COMMIT)}
    """,
        formatter_class=RawTextHelpFormatter,
        parents=[generic_parser, output_parser, dns_parser],
    )

    # ---------------- MODULE PARSER (NO FS ACCESS) ----------------
    module_parser = argparse.ArgumentParser(
        add_help=False, formatter_class=DisplayDefaultsNotNone
    )
    mgroup = module_parser.add_argument_group("Modules")
    mgroup.add_argument("-M", "--module", action="append",default=[])
    mgroup.add_argument("-o", nargs="+", default=[], dest="module_options")
    mgroup.add_argument("-L", "--list-modules", action="store_true")
    mgroup.add_argument("--options", dest="show_module_options", action="store_true")

    # ---------------- PROTOCOL SUBPARSERS ----------------
    subparsers = parser.add_subparsers(
        title="Available Protocols", dest="protocol" , required=False,
    )

    std_parser = argparse.ArgumentParser(
    add_help=False,
    parents=[generic_parser, output_parser, dns_parser, module_parser],
    formatter_class=DisplayDefaultsNotNone,
)

    std_parser.add_argument("target", nargs="*", help="target(s)")

    # ---------------- KERBEROS AUTH ----------------
    kerberos_group = std_parser.add_argument_group("Kerberos Authentication")
    kerberos_group.add_argument(
        "-k", "--kerberos",
        action="store_true",
        help="Use Kerberos authentication"
    )
    kerberos_group.add_argument(
        "--use-kcache",
        dest="use_kcache",
        action="store_true",
        help="Use Kerberos authentication from ccache file (KRB5CCNAME)"
    )
    kerberos_group.add_argument(
        "--aesKey",
        metavar="AESKEY",
        nargs="+",
        help="AES key to use for Kerberos Authentication"
    )
    kerberos_group.add_argument(
        "--kdcHost",
        metavar="KDCHOST",
        help="FQDN of the domain controller"
    )


    # ---------------- LOAD PROTOCOL ARGS SAFELY ----------------
    p_loader = ProtocolLoader()
    protocols = p_loader.get_protocols()
    for proto_name in protocols.keys():
        # empty placeholder so argparse accepts "smb", "ldap", etc
        subparsers.add_parser(
            proto_name,
            add_help=False
    )
    for proto_name, proto in protocols.items():
        try:
            # load protocol module itself (smb.py, ldap.py, etc)
            proto_mod = p_loader.load_protocol(proto["path"])
        except Exception as e:
            nxc_logger.debug(f"Failed loading protocol {proto_name}: {e}")
            continue

        # proto_args is OPTIONAL and lives INSIDE protocol module
        if hasattr(proto_mod, "proto_args"):
            try:
                subparsers = proto_mod.proto_args(
                    subparsers,
                    [std_parser, module_parser]
                )
            except Exception as e:
                nxc_logger.exception(
                    f"Error registering CLI args for protocol {proto_name}: {e}"
                )


    # ---------------- FINAL PARSE ----------------
    # argcomplete.autocomplete(parser, always_complete_options=False)

    # if len(sys.argv) == 1:
    #     parser.print_help()
    #     sys.exit(0)

    # # ✅ THIS IS THE MOST IMPORTANT FIX
    # # ❌ DO NOT use parse_known_args
    # args = parser.parse_args()

    # if args.version:
    #     print(f"{VERSION} - {CODENAME} - {COMMIT} - {DISTANCE}")
    #     sys.exit(0)

    # return args, [CODENAME, VERSION, COMMIT, DISTANCE]
    if argv is None:
            argv = sys.argv[1:]

    if not argv:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_known_args(argv)[0]
    if not hasattr(args, "module"):
        args.module = []

    if not hasattr(args, "list_modules"):
        args.list_modules = False


    if args.version:
        print(f"{VERSION} - {CODENAME} - {COMMIT} - {DISTANCE}")
        sys.exit(0)

    return args, [CODENAME, VERSION, COMMIT, DISTANCE]