import sys
import time
import requests # For the session object

def test_pytrends_functionality():
    print("--- Pytrends Independent Test ---")

    # 1. Check Python version (useful for context)
    print(f"Python version: {sys.version}")

    # 2. Attempt to import pytrends and check version
    try:
        import pytrends
        print(f"Successfully imported 'pytrends' module.")
        try:
            print(f"pytrends.__version__: {pytrends.__version__}")
        except AttributeError:
            print("ERROR: 'pytrends' module does not have a __version__ attribute.")
        except Exception as e:
            print(f"ERROR accessing pytrends.__version__: {e}")
    except ImportError:
        print("CRITICAL ERROR: Failed to import 'pytrends'. Is it installed in this environment?")
        print("--- End Pytrends Independent Test ---")
        return
    except Exception as e:
        print(f"CRITICAL ERROR during pytrends import: {e}")
        print("--- End Pytrends Independent Test ---")
        return

    # 3. Attempt to import TrendReq
    try:
        from pytrends.request import TrendReq
        print("Successfully imported 'TrendReq' from 'pytrends.request'.")
    except ImportError:
        print("CRITICAL ERROR: Failed to import 'TrendReq' from 'pytrends.request'.")
        print("--- End Pytrends Independent Test ---")
        return
    except Exception as e:
        print(f"CRITICAL ERROR during TrendReq import: {e}")
        print("--- End Pytrends Independent Test ---")
        return

    # 4. Initialize TrendReq (old way, without session)
    print("\nAttempting TrendReq initialization (old method, no session)...")
    try:
        pytrends_client_old = TrendReq(hl='en-US', tz=360, timeout=(10,25))
        print("  SUCCESS: TrendReq initialized (old method).")
    except Exception as e:
        print(f"  ERROR initializing TrendReq (old method): {e}")

    # 5. Initialize TrendReq (new way, with session)
    print("\nAttempting TrendReq initialization (new method, with requests_session)...")
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 Test Agent'}) # Basic user agent
    try:
        pytrends_client_new = TrendReq(hl='en-US', tz=360, timeout=(10,25), requests_session=session)
        print("  SUCCESS: TrendReq initialized (new method with requests_session).")

        # 6. Test a simple query if new initialization worked
        print("\nAttempting to fetch Google Trends data for 'Python'...")
        try:
            pytrends_client_new.build_payload(kw_list=['Python'], timeframe='today 1-m')
            interest_over_time_df = pytrends_client_new.interest_over_time()
            if not interest_over_time_df.empty:
                print("  SUCCESS: Fetched interest over time data.")
                print(interest_over_time_df.head())
            else:
                print("  INFO: Fetched data, but the DataFrame is empty (no results for 'Python' or API issue).")
        except Exception as e:
            print(f"  ERROR fetching Google Trends data: {e}")
            if "429" in str(e):
                print("  HINT: This might be a rate limit error (429).")

    except TypeError as te:
        if "unexpected keyword argument 'requests_session'" in str(te):
            print(f"  ERROR (TypeError): TrendReq does not support 'requests_session'. This strongly indicates an old pytrends version. {te}")
        else:
            print(f"  ERROR (TypeError) initializing TrendReq (new method): {te}")
    except Exception as e:
        print(f"  ERROR initializing TrendReq (new method): {e}")

    print("\n--- End Pytrends Independent Test ---")

if __name__ == "__main__":
    test_pytrends_functionality()