"""Optional: download a large public dataset to test GridLite at scale.

Our World in Data - CO2 and Greenhouse Gas Emissions (about 50,000 rows x 79
columns, ~14 MB). License: CC BY 4.0 - credit "Our World in Data".
Source: https://github.com/owid/co2-data

The file is saved as data/owid_co2.csv and is NOT committed to git.

Run:  python scripts/fetch_owid_data.py
"""

import os
import urllib.request

URL = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "owid_co2.csv")


def main():
    tmp = DEST + ".download"
    print(f"Downloading {URL} ...")
    urllib.request.urlretrieve(URL, tmp)
    os.replace(tmp, DEST)
    print(f"Saved {os.path.relpath(DEST)} ({os.path.getsize(DEST) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
