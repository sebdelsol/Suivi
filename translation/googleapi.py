from googletrans import Translator

from .translate import SameLanguageError, TranslationService


class GoogleAPI(TranslationService):
    def __init__(self, to_lang):
        self.translator = Translator()
        super().__init__(to_lang)

    def translate(self, txt):
        translation = self.translator.translate(txt, dest=self.to_lang)
        if translation.src == self.to_lang:
            raise SameLanguageError

        return translation.text
