from importlib import import_module
from pkgutil import iter_modules

# import all modules in the package to auto-populate Couriers_classes
for _, module_name, _ in iter_modules(__path__):
    module = import_module(f"{__name__}.{module_name}")
