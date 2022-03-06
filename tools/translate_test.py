from os import path, sys

if __name__ == "__main__":
    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

    from windows.localization import TXT
    from windows.log import log, logger

    from tools.translate import TranslationHandler, TranslationService_Classes

    logger.print_only()
    logger.close()

    sentences = (
        "你好世界上所有的邮递员",
        "il pacco è definitivamente perso",
        "Your letter has been shredded by a dog",
        "Die Rakete, die Ihre Sendung transportiert, ist erneut auf dem Mond abgestürzt",
    )
    TO_LANG = TXT.locale_country_code
    for service_name in TranslationService_Classes:
        print(service_name.rjust(20, "-"))
        translation_handler = TranslationHandler(TO_LANG, service_name)
        for sentence in sentences:
            print(f"> '{sentence}'", end="")
            translation = translation_handler.get(sentence)
            print(f" --> '{translation}'")
        translation_handler.save()
