import html
from os import environ

import requests
from windows.localization import TXT

from .secrets import GOOGLE_CREDENTIAL_PATH, GOOGLE_PROJECT_ID, VALID_EMAIL

USE_GOOGLE = True


if USE_GOOGLE:
    from google.cloud import translate as google_translate

    environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIAL_PATH
    google_client = google_translate.TranslationServiceClient()

else:
    import langid


def translate(txt, from_lang=None, to_lang=TXT.locale_country_code):
    if txt:
        if USE_GOOGLE:
            if from_lang != to_lang:
                response = google_client.translate_text(
                    contents=[txt],
                    source_language_code=from_lang,
                    target_language_code=to_lang,
                    mime_type="text/plain",
                    parent=f"projects/{GOOGLE_PROJECT_ID}",
                )

                return response.translations[0].translated_text

        if not from_lang:
            from_lang = langid.classify(txt)[0]

        if from_lang != to_lang:
            url = "https://api.mymemory.translated.net/get?"
            params = dict(q=txt, langpair=f"{from_lang}|{to_lang}", de=VALID_EMAIL)
            r = requests.get(url, params=params)
            if r.status_code == 200:
                rjson = r.json()
                if rjson["responseStatus"] == 200:
                    return html.unescape(
                        rjson["responseData"].get("translatedText", txt)
                    )
    return txt
