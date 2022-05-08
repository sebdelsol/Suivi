from concurrent.futures import Future, ThreadPoolExecutor, as_completed

MUTI_THREADED = True

if not MUTI_THREADED:

    class MockThreadPoolExecutor(ThreadPoolExecutor):
        def submit(self, *args, **kwargs):
            function, *args = args
            future_ = Future()
            future_.set_result(function(*args, **kwargs))
            return future_

        def shutdown(self, wait=True):
            pass

    ThreadPoolExecutor = MockThreadPoolExecutor
    N_DRIVERS = 1

else:
    N_DRIVERS = 3


if __name__ == "__main__":
    import locale
    import sys
    from pathlib import Path

    # import 2 levels up
    sys.path.append(str(Path(__file__).parents[1]))

    # list of tuples (courier_name, idship)
    from config import Couriers_to_test
    from tracking.couriers_handler import CouriersHandler
    from windows.localization import TXT
    from windows.log import log, logger

    locale.setlocale(locale.LC_TIME, TXT.locale_setting)  # date in correct language
    logger.print_only()
    logger.close()

    passed, failed = [], []
    couriers_handler = CouriersHandler(max_drivers=N_DRIVERS)
    couriers_to_test = sorted(Couriers_to_test, key=lambda c: c[0])

    with ThreadPoolExecutor(max_workers=len(couriers_to_test)) as executor:
        futures = {
            executor.submit(couriers_handler.update, courier_name, idship): courier_name
            for courier_name, idship in couriers_to_test
        }

        for future in as_completed(futures):
            result = future.result()
            courier_name = futures[future]

            msg = f". {courier_name}"
            if result and result["ok"]:
                passed.append(courier_name)
                events = result["events"]
                event = events[0]
                status = f"{event['status']}, " if event["status"] else ""
                msg += f" - PASS - {len(events)} event(s)\n"
                msg += f". {event['date']:{TXT.long_date_format}} - {status}{event['label']}"

            else:
                failed.append(courier_name)
                msg += " - FAIL\n"
                msg += ". !!!!!!!!!!!!!!!!!!!!!!!"
            log(f"\n{msg}\n")

        def get_couriers_names(a_list):
            if a_list:
                txt = "ALL " if len(a_list) == len(couriers_to_test) else ""
                names = (f"\n . {name}" for name in sorted(a_list))
                return f"{txt}{len(a_list)}{''.join(names)}"
            return "NONE"

        log(f"\nPassed: {get_couriers_names(passed)}")
        log(f"\nFailed: {get_couriers_names(failed)}")
        log()
