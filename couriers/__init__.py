from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules

# import all modules in the couriers package so that Couriers_classes is populated
package_dir = Path(__file__).parent
for (_, module_name, _) in iter_modules([package_dir]):
    module = import_module(f"{__name__}.{module_name}")
