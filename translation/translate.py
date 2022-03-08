import pkgutil
from abc import ABC, abstractmethod

from tools.save_handler import SaveHandler
from windows.log import log

# list of translation modules that should implement TranslationService
Package_Name, This_Module_Name = __name__.split(".")

TranslationService_Modules = sorted(
    name
    for _, name, _ in pkgutil.iter_modules([Package_Name])
    if name != This_Module_Name
)

# lookup TranslationService classes by module names, automatically populated
TranslationService_Classes = {}


class TranslationService(ABC):
    def __init_subclass__(cls):
        """
        populate TranslationService_Classes
        when a module with a derived TranslationService is imported
        """
        TranslationService_Classes[cls.__module__] = cls

    def __init__(self, to_lang):
        self.to_lang = to_lang

    @abstractmethod
    def translate(self, txt):
        pass


class TranslationHandler:
    def __init__(self, to_lang, service_module, do_load=True):
        log(f"Available translation services: {' . '.join(TranslationService_Modules)}")

        if service_module in TranslationService_Modules:
            # import the relevant module
            service_module = f"{Package_Name}.{service_module}"
            __import__(service_module)

            # instantiate its TranslationService class
            service_cls = TranslationService_Classes[service_module]
            service_name = service_cls.__name__
            self.service = service_cls(to_lang)

            # load dict of all translated sentences
            filename = f"translation_{service_name}_{to_lang}"
            self.save_handler = SaveHandler(filename, load_as_json=True)

            if do_load:
                self.translated = self.save_handler.load() or {}

            else:
                self.translated = {}

            log(
                (
                    f"Import & use {service_module}.{service_name} "
                    f"for translating into {to_lang.upper()}"
                )
            )

        else:
            raise ValueError(
                (
                    f"translation service module '{service_module}' "
                    f"not found in {TranslationService_Modules}"
                )
            )

    def save(self):
        # save dict of all translated sentences
        self.save_handler.save_as_json(self.translated)

    def get(self, txt):
        if txt:
            if translation := self.translated.get(txt):
                return translation

            if translation := self.service.translate(txt):
                self.translated[txt] = translation
                return translation
        if txt:
            log(
                f"Error translating '{txt}' with {type(self.service).__name__}",
                error=True,
            )
        return txt
