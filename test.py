
import requests
from bs4 import BeautifulSoup


def find_mmr(url):
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/42.0.2311.135 Safari/537.36 Edge/12.246 "
    )
    resp = requests.get(url, headers={"User-Agent": f"{user_agent}"})
    soup = BeautifulSoup(resp.text, "html.parser")

    mmr_table = soup.find("div", attrs={"class": "gray-band-background table-section"})
    mmr_h3 = mmr_table.find("h3")
    try:
        text, mmr_str = mmr_h3.text.split(": ")
        mmr = int(mmr_str)
        return mmr if mmr > 2200 else 2200
    except ValueError:
        print("Error parsing MMR")
    raise ValueError("MMR not found")


if __name__ == "__main__":
    # print(read_mmr('chanterelle#21706'))
    print(find_mmr("https://www.heroesprofile.com/Player/Fenrir/8710344/2"))
