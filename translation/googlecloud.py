import os

from google.cloud import translate as google_translate
from tracking.secrets import GOOGLE_CREDENTIAL_PATH, GOOGLE_PROJECT_ID

from .translate import TranslationService


class GoogleCloud(TranslationService):
    def __init__(self, to_lang):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIAL_PATH
        self.google_client = google_translate.TranslationServiceClient()
        self.kwargs = dict(
            source_language_code=None,
            target_language_code=to_lang,
            mime_type="text/plain",
            parent=f"projects/{GOOGLE_PROJECT_ID}",
        )
        super().__init__(to_lang)

    def translate(self, txt):
        self.kwargs['contents'] = [txt]
        response = self.google_client.translate_text(**self.kwargs)
        return response.translations[0].translated_text
