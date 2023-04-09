import subprocess
from bs4 import BeautifulSoup
from enum import Enum
import json
import re

class Data(Enum):
    ACCOUNT = "Account" 
    BUILDING = "Building"
    LAND = "Land"
    DEEDS = "Deeds"
    NOTES = "Notes"
    SALES = "ImpSales"
    PHOTOS = "Photo"

def makeId(num):
    width = 7
    return f"{num:0>{width}}"

def makeURL(tab, id): return f"https://services.wake.gov/realestate/{tab.value}.asp?id={makeId(id)}"

def cleanString(string, strip=True):
    if strip:
        string = string.strip()

    return re.sub(r'[\s\u200b]+', ' ', string)

def makeCurlFor(tab, id):
    url = makeURL(tab, id)
    return subprocess.check_output(f"curl {url}")

def attachAccountData(data, id):
    print("Getting account data from:")
    print(makeURL(Data.ACCOUNT, id))

    html = makeCurlFor(Data.ACCOUNT, id)
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")

    #does re writing temp cause page misses in cashe?
    temp = rows[3].find_all("b")
    data["Real Estate ID"] = cleanString(temp[0].text)
    data["PIN #"] = cleanString(temp[1].text)

    temp = rows[7].find_all("b")
    data["Location Address"] = cleanString(temp[0].text)
    data["Property Description"] = cleanString(temp[1].text)

    temp = rows[11].find("b")
    data["Property Owner"] = cleanString(temp.text)

    temp = rows[9].find_all("b")
    # i think using clean string once and then three strips is faster then clean string twice with one strip. not sure though
    data["Owner's Mailing Address"] = cleanString(f"{temp[2].text.strip()} {temp[3].text.strip()}", strip=False)
    data["Property Location Address"] = cleanString(f"{temp[5].text.strip()} {temp[6].text.strip()}", strip=False)

    temp = rows[22].find_all("tr")

    for tag in temp:
        tds = tag.find_all("td")
        field = None
        value = None

        for tag in tds:
            if tag.find("b"):
                value = cleanString(tag.text)
            elif tag.text:
                field = cleanString(tag.text)

        if field and value:
            data[field] = value

    print(f"Done getting {Data.ACCOUNT.value} data")
    return data
        
def getData(id):
    data = {}
    attachAccountData(data, id)
    return data

def saveData(data):
    id = data["Real Estate ID"]
    file = open(f"data/{id}.json", "w")
    file.write(json.dumps(data))
    file.close()

def handleId(id):
    print(f"Starting to collect data for ID#{id}")
    saveData(getData(id))
    print(f"Done collecting data for ID#{id}")

handleId(1)