from os import path, sys

sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

from translation.translate import TranslationHandler, TranslationService_Modules
from windows.localization import TXT
from windows.log import log, logger

logger.print_only()
logger.close()

sentences = (
    "你好世界上所有的邮递员",
    "il pacco è definitivamente perso",
    "Your letter has been shredded by a dog",
    "Die Rakete, die Ihre Sendung transportiert, ist erneut auf dem Mond abgestürzt",
)

TO_LANG = TXT.locale_country_code
LOAD_AND_SAVE = True

for service_module in TranslationService_Modules:
    log(service_module.rjust(20, "-"))
    translation_handler = TranslationHandler(
        TO_LANG, service_module, do_load=LOAD_AND_SAVE
    )

    for sentence in sentences:
        log(f"> '{sentence}'", end="")
        translation = translation_handler.get(sentence)
        log(f" --> '{translation}'")

    if LOAD_AND_SAVE:
        translation_handler.save()
