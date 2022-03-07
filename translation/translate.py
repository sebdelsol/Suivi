import pkgutil

from tools.save_handler import SaveHandler
from windows.log import log

# list of translation module that implement TranslationService
Package_Name, This_Module_Name = __name__.split(".")

TranslationService_Modules = sorted(
    name
    for _, name, _ in pkgutil.iter_modules([Package_Name])
    if name != This_Module_Name
)

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
    def __init__(self, to_lang, service_module, do_load=True):
        log(f"Translation services: {' . '.join(TranslationService_Modules)}")
        if service_module in TranslationService_Modules:
            service_module = f"{Package_Name}.{service_module}"
            __import__(service_module)

            service_cls = TranslationService_Classes[service_module]
            self.service = service_cls(to_lang)
            log(
                f"Use {service_module}.{service_cls.__name__} for translating into {to_lang}"
            )

            filename = f"translation_{service_cls.__name__}_{to_lang}"
            self.save_handler = SaveHandler(filename, "translation", load_as_json=True)
            self.translated = {}
            if do_load:
                self.translated = self.save_handler.load() or {}

        else:
            raise ValueError(
                f"translation service module '{service_module}' should be in {TranslationService_Modules}"
            )

    def save(self):
        self.save_handler.save_as_json(self.translated)

    def get(self, txt):
        if txt:
            if translation := self.translated.get(txt):
                return translation

            if translation := self.service.translate(txt):
                self.translated[txt] = translation
                return translation

        return txt
