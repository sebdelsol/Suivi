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


class SameLanguageError(Exception):
    pass


class TranslationHandler:
    def __init__(self, to_lang, service_module, do_load=True):
        available = " . ".join(TranslationService_Modules)
        log(f"Available translation services: {available}")

        if service_module in TranslationService_Modules:
            # import the relevant module
            service_module = f"{Package_Name}.{service_module}"
            __import__(service_module)

            # instantiate its TranslationService class
            service_cls = TranslationService_Classes[service_module]
            self.service_name = service_cls.__name__
            self.service = service_cls(to_lang)

            # load cache
            filename = f"translation_{self.service_name}_{to_lang}"
            self.load(filename, do_load)

            log(
                (
                    f"Import & use {service_module}.{self.service_name}"
                    f" for translating into {to_lang.upper()}"
                )
            )

        else:
            raise ValueError(
                (
                    f"translation service module '{service_module}'"
                    f" not in {TranslationService_Modules}"
                )
            )

    def load(self, filename, do_load):
        """load cache of translated sentences"""
        self.save_handler = SaveHandler(filename, load_as_json=True)
        if do_load and (cache := self.save_handler.load()):
            self.translated = cache["translated"]
            self.skip = set(cache["skip"])
        else:
            self.translated = {}
            self.skip = set()

    def save(self):
        """save cache translated sentences"""
        cache = dict(translated=self.translated, skip=list(self.skip))
        self.save_handler.save_as_json(cache)

    def get(self, txt):
        if txt:
            if txt in self.skip:
                return txt

            if translation := self.translated.get(txt):
                return translation

            try:
                if translation := self.service.translate(txt):
                    if txt != translation:
                        self.translated[txt] = translation
                        return translation

                    raise SameLanguageError

            except SameLanguageError:
                self.skip.add(txt)
                return txt

            log(
                f"Error translating '{txt}' with {self.service_name}",
                error=True,
            )

        return txt
