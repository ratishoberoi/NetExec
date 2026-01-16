import sys
import traceback
import importlib
from types import ModuleType

from importlib import import_module
from importlib.resources import files

from nxc.context import Context
from nxc.helpers.misc import CATEGORY
from nxc.logger import NXCAdapter


class ModuleLoader:
    def __init__(self, args, db, logger):
        self.args = args
        self.db = db
        self.logger = logger

    # ---------------------------------------------------------
    # Sanity checks
    # ---------------------------------------------------------
    def module_is_sane(self, module, module_name):
        error = False

        if not hasattr(module, "name"):
            self.logger.fail(f"{module_name} missing 'name'")
            error = True

        elif module.name != module_name:
            self.logger.fail(f"{module_name} filename must match module.name")
            error = True

        elif not hasattr(module, "description"):
            self.logger.fail(f"{module_name} missing 'description'")
            error = True

        elif not hasattr(module, "category") or module.category not in (
            CATEGORY.ENUMERATION,
            CATEGORY.CREDENTIAL_DUMPING,
            CATEGORY.PRIVILEGE_ESCALATION,
        ):
            self.logger.fail(f"{module_name} invalid or missing 'category'")
            error = True

        elif not hasattr(module, "supported_protocols"):
            self.logger.fail(f"{module_name} missing 'supported_protocols'")
            error = True

        elif not hasattr(module, "options"):
            self.logger.fail(f"{module_name} missing 'options'")
            error = True

        elif not (
            hasattr(module, "on_login")
            or hasattr(module, "on_admin_login")
        ):
            self.logger.fail(
                f"{module_name} missing on_login/on_admin_login"
            )
            error = True

        return not error

    # ---------------------------------------------------------
    # Load module safely (IMPORT-BASED)
    # ---------------------------------------------------------
    def load_module(self, module_import_path: str):
        try:
            mod = import_module(module_import_path)
            module = mod.NXCModule()

            name = module_import_path.split(".")[-1]
            if self.module_is_sane(module, name):
                return module

        except Exception as e:
            self.logger.fail(
                f"Failed loading module {module_import_path}: {e}"
            )
            self.logger.debug(traceback.format_exc())

        return None

    # ---------------------------------------------------------
    # Initialize module for execution
    # ---------------------------------------------------------
    def init_module(self, module_import_path: str):
        module = self.load_module(module_import_path)
        if not module:
            return None

        self.logger.debug(f"Supported protocols: {module.supported_protocols}")
        self.logger.debug(f"Selected protocol: {self.args.protocol}")

        if self.args.protocol not in module.supported_protocols:
            self.logger.fail(
                f"Module {module.name.upper()} not supported for protocol {self.args.protocol}"
            )
            sys.exit(1)

        try:
            module_logger = NXCAdapter(
                extra={"module_name": module.name.upper()}
            )
            context = Context(self.db, module_logger, self.args)

            module_options = {}
            for opt in self.args.module_options:
                k, v = opt.split("=", 1)
                module_options[k.upper()] = v

            module.options(context, module_options)
            return module

        except Exception as e:
            self.logger.fail(
                f"Error initializing module {module.name}: {e}"
            )
            self.logger.debug(traceback.format_exc())

        return None

    # ---------------------------------------------------------
    # Get module metadata (NO INIT)
    # ---------------------------------------------------------
    def get_module_info(self, module_import_path: str):
        try:
            mod = import_module(module_import_path)
            cls = mod.NXCModule

            name = module_import_path.split(".")[-1]
            if not self.module_is_sane(cls, name):
                return None

            return {
                name: {
                    "path": module_import_path,
                    "description": cls.description,
                    "options": cls.options.__doc__,
                    "supported_protocols": cls.supported_protocols,
                    "category": cls.category,
                    "requires_admin": bool(
                        hasattr(cls, "on_admin_login")
                        and callable(cls.on_admin_login)
                    ),
                }
            }

        except Exception as e:
            self.logger.debug(
                f"Failed reading module info {module_import_path}: {e}"
            )
            self.logger.debug(traceback.format_exc())

        return None

    # ---------------------------------------------------------
    # List modules (EMBEDDED SAFE)
    # ---------------------------------------------------------
    def list_modules(self):
        modules = {}

        try:
            pkg = files("nxc.modules")

            for file in pkg.iterdir():
                if not file.name.endswith(".py"):
                    continue
                if file.name == "example_module.py":
                    continue

                name = file.name[:-3]
                import_path = f"nxc.modules.{name}"

                info = self.get_module_info(import_path)
                if info:
                    modules.update(info)

        except Exception as e:
            self.logger.debug(f"Module discovery failed: {e}")
            self.logger.debug(traceback.format_exc())

        return modules
