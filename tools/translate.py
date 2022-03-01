from tools.save_handler import SaveHandler


class TranslateServices:
    deepl = "deepl"
    google = "google"
    mymemory = "mymerory"


TRANSLATE_SERVICE = TranslateServices.deepl

if TRANSLATE_SERVICE == TranslateServices.google:
    import os

    from google.cloud import translate as google_translate
    from tracking.secrets import GOOGLE_CREDENTIAL_PATH, GOOGLE_PROJECT_ID

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIAL_PATH
    google_client = google_translate.TranslationServiceClient()

    def translate(txt, from_lang, to_lang):
        if from_lang != to_lang:
            response = google_client.translate_text(
                contents=[txt],
                source_language_code=from_lang,
                target_language_code=to_lang,
                mime_type="text/plain",
                parent=f"projects/{GOOGLE_PROJECT_ID}",
            )
            return response.translations[0].translated_text
        return None

elif TRANSLATE_SERVICE == TranslateServices.mymemory:
    import html

    import langid
    import requests
    from tracking.secrets import VALID_EMAIL

    def translate(txt, from_lang, to_lang):
        from_lang = from_lang or langid.classify(txt)[0]
        if from_lang != to_lang:
            url = "https://api.mymemory.translated.net/get"
            params = dict(q=txt, langpair=f"{from_lang}|{to_lang}", de=VALID_EMAIL)
            r = requests.get(url, params=params)
            if r.status_code == 200:
                rjson = r.json()
                if rjson["responseStatus"] == 200:
                    return html.unescape(
                        rjson["responseData"].get("translatedText", txt)
                    )
        return None

elif TRANSLATE_SERVICE == TranslateServices.deepl:
    import requests
    from tracking.secrets import DEEPL_KEY

    def translate(txt, from_lang, to_lang):
        if from_lang != to_lang:
            url = "https://api-free.deepl.com/v2/translate"
            params = dict(
                text=txt, source_lang=from_lang, target_lang=to_lang, auth_key=DEEPL_KEY
            )
            r = requests.get(url, params=params)
            if r.status_code == 200:
                if translations := r.json().get("translations"):
                    if len(translations) > 0:
                        return translations[0]["text"]
        return None


class TranslationHandler:
    def __init__(self, to_lang):
        self.to_lang = to_lang
        filename = f"translation_{to_lang}"
        self.save_handler = SaveHandler(filename, load_as_json=True)
        self.translated = self.save_handler.load() or {}

    def save(self):
        self.save_handler.save(self.translated, save_only_json=True)

    def get(self, txt, from_lang=None):
        if txt:
            if translation := self.translated.get(txt):
                return translation

            if translation := translate(txt, from_lang, self.to_lang):
                self.translated[txt] = translation
                return translation

        return txt
