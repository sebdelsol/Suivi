import sys
from pathlib import Path

# import 2 levels up
sys.path.append(str(Path(__file__).parents[1]))


# pylint: disable=wrong-import-position
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
    "Votre colis a été remis en liberté",
)

TO_LANG = TXT.locale_country_code
DO_LOAD = False

for service_module in TranslationService_Modules:
    log(service_module.rjust(20, "-"))
    translation_handler = TranslationHandler(TO_LANG, service_module, do_load=DO_LOAD)

    for sentence in sentences:
        translation = translation_handler.get(sentence)
        log(f"> '{sentence}' --> '{translation}'")

    if DO_LOAD:
        translation_handler.save()
