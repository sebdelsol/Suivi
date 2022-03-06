from googletranslate import Translator

from .translate import TranslationService


class GoogleAPI(TranslationService):
    def __init__(self, to_lang):
        self.translator = Translator(to_lang, "auto")
        super().__init__(to_lang)

    def translate(self, txt):
        return self.translator(txt)
