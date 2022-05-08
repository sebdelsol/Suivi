import os

from config import GOOGLE_CREDENTIAL_PATH
from google.cloud import translate_v2 as translate

from .translate import SameLanguageError, TranslationService


class GoogleCloud(TranslationService):
    def __init__(self, to_lang):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIAL_PATH
        self.client = translate.Client()
        self.kwargs = dict(
            target_language=to_lang,
            format_="text",
        )
        super().__init__(to_lang)

    def translate(self, txt):
        result = self.client.translate(txt, **self.kwargs)

        if result["detectedSourceLanguage"] == self.to_lang:
            raise SameLanguageError

        return result["translatedText"]
