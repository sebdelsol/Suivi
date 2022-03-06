import requests
from tracking.secrets import DEEPL_KEY

from .translate import TranslationService


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
