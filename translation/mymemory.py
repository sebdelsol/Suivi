import html

import langid
import requests
from tracking.secrets import VALID_EMAIL

from .translate import TranslationService


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