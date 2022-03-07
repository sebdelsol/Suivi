import requests
from tracking.secrets import DEEPL_KEY

from .translate import TranslationService


class DeepL(TranslationService):
    url = "https://api-free.deepl.com/v2/translate"

    def __init__(self, to_lang):
        self.params = dict(target_lang=to_lang, auth_key=DEEPL_KEY)
        super().__init__(to_lang)

    def translate(self, txt):
        self.params["text"] = txt
        r = requests.get(self.url, params=self.params)
        if r.status_code == 200:
            if translations := r.json().get("translations"):
                if len(translations) > 0:
                    return translations[0]["text"]
        return None
