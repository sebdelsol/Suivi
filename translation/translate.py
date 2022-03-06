import pkgutil

from tools.save_handler import SaveHandler
from windows.log import log

# list of translation module (exclude translate* modules)
PACKAGE_NAME = "translation"
this_module_name = __name__.split(".")[1]

TranslationService_Modules = [
    name
    for _, name, _ in pkgutil.iter_modules([PACKAGE_NAME])
    if name != this_module_name
]

# module to cls dict populated when a TranslationService is imported
TranslationService_Classes = {}


class TranslationService:
    def __init_subclass__(cls):
        """register the children class"""
        TranslationService_Classes[cls.__module__] = cls

    def __init__(self, to_lang):
        self.to_lang = to_lang

    def translate(self, txt):
        raise NotImplementedError("translate method is missing")


class TranslationHandler:
    def __init__(self, to_lang, service_module):
        log(f"Translation services: {' . '.join(sorted(TranslationService_Modules))}")
        if service_module in TranslationService_Modules:
            service_module = f"{PACKAGE_NAME}.{service_module}"
            __import__(service_module)

            service_cls = TranslationService_Classes[service_module]
            self.service = service_cls(to_lang)
            log(f"Use {service_cls.__name__} for translating into {to_lang}")

            filename = f"translation_{service_cls.__name__}_{to_lang}"
            self.save_handler = SaveHandler(filename, "translation", load_as_json=True)
            self.translated = self.save_handler.load() or {}

        else:
            raise ValueError(
                f"translation service module {service_module} doesn't exists"
            )

    def save(self):
        self.save_handler.save(self.translated, save_only_json=True)

    def get(self, txt):
        if txt:
            if translation := self.translated.get(txt):
                return translation

            if translation := self.service.translate(txt):
                self.translated[txt] = translation
                return translation

        return txt
