from windows.log import log

from tools.save_handler import SaveHandler

TranslationService_Classes = {}


class TranslationService:
    def __init_subclass__(cls):
        """register subclasses"""
        TranslationService_Classes[cls.__name__] = cls

    def __init__(self, to_lang):
        self.to_lang = to_lang

    def translate(self, txt):
        raise NotImplementedError("translate method is missing")


class TranslationHandler:
    def __init__(self, to_lang, service_cls_name):
        log(f"Translation services: {' . '.join(sorted(TranslationService_Classes))}")
        if service_cls := TranslationService_Classes.get(service_cls_name):
            self.service = service_cls(to_lang)
            log(f"Use {service_cls_name} for translating into {to_lang}")

            filename = f"translation_{service_cls_name}_{to_lang}"
            self.save_handler = SaveHandler(filename, "translation", load_as_json=True)
            self.translated = self.save_handler.load() or {}

        else:
            raise ValueError(f"translation service {service_cls_name} doesn't exists")

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


import requests
from tracking.secrets import DEEPL_KEY


class DeepL(TranslationService):
    url = "https://api-free.deepl.com/v2/translate"

    def translate(self, txt):
        params = dict(
            text=txt, source_lang=None, target_lang=self.to_lang, auth_key=DEEPL_KEY
        )
        r = requests.get(self.url, params=params)
        if r.status_code == 200:
            if translations := r.json().get("translations"):
                if len(translations) > 0:
                    return translations[0]["text"]
        return None


import os

from google.cloud import translate as google_translate
from tracking.secrets import GOOGLE_CREDENTIAL_PATH, GOOGLE_PROJECT_ID


class GoogleCloud(TranslationService):
    def __init__(self, to_lang):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIAL_PATH
        self.google_client = google_translate.TranslationServiceClient()
        super().__init__(to_lang)

    def translate(self, txt):
        response = self.google_client.translate_text(
            contents=[txt],
            source_language_code=None,
            target_language_code=self.to_lang,
            mime_type="text/plain",
            parent=f"projects/{GOOGLE_PROJECT_ID}",
        )
        return response.translations[0].translated_text


from googletranslate import Translator


class GoogleAPI(TranslationService):
    def __init__(self, to_lang):
        self.translator = Translator(to_lang, "auto")
        super().__init__(to_lang)

    def translate(self, txt):
        return self.translator(txt)


import html

import langid
import requests
from tracking.secrets import VALID_EMAIL


class MyMemory(TranslationService):
    url = "https://api.mymemory.translated.net/get"

    def translate(self, txt):
        from_lang = langid.classify(txt)[0]
        params = dict(q=txt, langpair=f"{from_lang}|{self.to_lang}", de=VALID_EMAIL)
        r = requests.get(self.url, params=params)
        if r.status_code == 200:
            rjson = r.json()
            if rjson["responseStatus"] == 200:
                return html.unescape(rjson["responseData"].get("translatedText", txt))
        return None
