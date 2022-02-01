from localization import TXT
from log import logger

COURIERS_IDSHIP = (
    ("USPS", "LZ596462615US"),
    ("DHL", "JVGL084127362550620461415537"),
    # ('DHL', '1234567890'),
    # ('DHL', '6294166480'),
    ("Relais Colis", "VD3410033223"),
    ("4PX", "LZ074882152FR"),
    ("Asendia", "LZ074882152FR"),
    ("Cainiao", "LZ074882152FR"),
    ("Chronopost", "DT201253687FR"),
    # ("DPD", "250063801848433"),
    ("DPD", "250092101363956"),
    ("GLS", "676411719238"),
    ("La Poste", "LZ074882152FR"),
    ("Mondial Relay", "11150623-34920"),
    ("NL Post", "LT666174269NL"),
)

if __name__ == "__main__":
    # prevent drivers to be created in subprocess
    from couriers import Couriers

    logger.print_only()
    logger.close()

    couriers = Couriers(max_drivers=1)
    passed, failed = [], []

    for name, idship in sorted(COURIERS_IDSHIP, key=lambda t: t[0]):
        result = couriers.update(name, idship)
        if result and result["ok"]:
            passed.append(name)
            evt = result["events"][0]
            print(f"PASS test - {name}", end="")
            status = evt["status"] + ", " if evt["status"] else ""
            print(f" - {evt['date']:{TXT.long_date_format}} - {status}{evt['label']}")

        else:
            failed.append(name)
            print(f"FAIL test - {name} !!!!!!!!!!!!!!!!!!!!!!!")

    def get_list_of_names(names):
        if not names:
            return "NONE"

        txt = "ALL " if len(names) == len(COURIERS_IDSHIP) else ""
        return f"{txt}{len(names)} ({', '.join(names)})"

    print()
    print(f"Passed: {get_list_of_names(passed)}")
    print(f"Failed: {get_list_of_names(failed)}")
    print()
