from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules

from windows.log import log

from tracking.courier import Courier, Couriers_classes

# import all modules in the couriers package so that Couriers_classes is populated
COURIERS_PACKAGE = "couriers"
package_dir = Path(__file__).parent.parent.joinpath(COURIERS_PACKAGE)
for (_, module_name, _) in iter_modules([package_dir]):
    module = import_module(f"{COURIERS_PACKAGE}.{module_name}")


class CouriersHandler:
    def __init__(self, max_drivers=2):
        self.couriers = {cls.name: cls() for cls in Couriers_classes}
        log(f"CREATE Couriers: {', '.join(sorted(self.couriers))}")

        Courier.set_max_scrape_drivers(max_drivers)

    def exists(self, name):
        return bool(self.couriers.get(name))

    def open_in_browser(self, name, idship):
        if courier := self.couriers.get(name):
            courier.open_in_browser(idship)

    def validate_idship(self, name, idship):
        if courier := self.couriers.get(name):
            return bool(courier.idship_validation(idship))
        return False

    def get_url_for_browser(self, name, idship):
        if courier := self.couriers.get(name):
            return bool(courier.get_url_for_browser(idship))
        return False

    def get_idship_validation_msg(self, name):
        if courier := self.couriers.get(name):
            return courier.idship_validation_msg
        return ""

    def update(self, name, idship):
        if courier := self.couriers.get(name):
            return courier.update(idship)
        return None

    def get_names(self):
        return list(self.couriers)
