import pkgutil
import importlib
import nxc.protocols


class ProtocolLoader:
    def get_protocols(self):
        protocols = {}
        pkg_path = nxc.protocols.__path__

        for module_info in pkgutil.iter_modules(pkg_path):
            # 🔴 CRITICAL FIX: only protocol PACKAGES (smb/, ldap/, etc)
            if not module_info.ispkg:
                continue

            name = module_info.name
            base = f"nxc.protocols.{name}"

            try:
                importlib.import_module(base)
            except Exception:
                continue

            proto = {"path": base}

            try:
                importlib.import_module(f"{base}.database")
                proto["dbpath"] = f"{base}.database"
            except Exception:
                pass

            try:
                importlib.import_module(f"{base}.db_navigator")
                proto["nvpath"] = f"{base}.db_navigator"
            except Exception:
                pass

            try:
                importlib.import_module(f"{base}.proto_args")
                proto["argspath"] = f"{base}.proto_args"
            except Exception:
                pass

            protocols[name] = proto

        return protocols

    def load_protocol(self, module_path):
        return importlib.import_module(module_path)
