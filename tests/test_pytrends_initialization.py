import sys
import os

# Add src directory to path to allow importing ExternalDataCollector
# This assumes the test script is in the 'tests' directory, and 'src' is a sibling of 'tests'
module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if module_path not in sys.path:
    sys.path.append(module_path)

from src.connectors.external_data_collector import ExternalDataCollector

def run_pytrends_init_test():
    print("--- Testing ExternalDataCollector Pytrends Initialization ---")
    
    # The ExternalDataCollector's __init__ method loads .env by default.
    # Ensure your .env file is in the project root: c:\\Users\\lucav\\Github\\Game-Popularity-Prediction-Modelv2\\.env

    print("\nAttempting to instantiate ExternalDataCollector...")
    try:
        collector = ExternalDataCollector() # This will call _init_pytrends
        
        if collector.pytrends_client:
            print("\nSUCCESS: collector.pytrends_client is initialized.")
            print("         Review console output for specific initialization path (shared session or fallback).")
        else:
            print("\nFAILURE: collector.pytrends_client is None after instantiation.")
            print("         Check the console output above for error messages from _init_pytrends.")

    except Exception as e:
        print(f"\nCRITICAL ERROR during ExternalDataCollector instantiation: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- End of Pytrends Initialization Test ---")

if __name__ == "__main__":
    run_pytrends_init_test()
