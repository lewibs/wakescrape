import subprocess
from bs4 import BeautifulSoup
from enum import Enum
import json
import re
import urllib.parse

FAIL_COUNT = 0
MAX_FAIL = 50
STORAGE_DIR = "houses"

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

def makeURL(tab, params): return f"https://services.wake.gov/realestate/{tab.value}.asp?{urllib.parse.urlencode(params)}"

def cleanString(string, strip=True):
    if strip:
        string = string.strip()

    return re.sub(r'[\s\u200b]+', ' ', string)

def makeCurlFor(tab, params):
    url = makeURL(tab, params)
    return subprocess.check_output(f"curl -s {url}")

def printSoup(soup):
    i = 0
    for tag in soup:
        print(f"\n\ntag #{i}")
        print(tag)
        i += 1

def goldilocks(soup):
    head = soup.find("h1")

    if head and head.text == "Object Moved":
        raise Exception("Failed getting this data. The house moved")
    
    return soup

#this is used for when you have a tr and want to parse three things and get the bold value and the unbold field
def boldStrategy(data, soupArr):
    for tag in soupArr:
        field = None
        value = None

        cols = tag.find_all("td")

        for col in cols:
            if col.find("b"):
                value = cleanString(col.text)
            elif not field:
                field = cleanString(col.text)

        if field and value:
            data[field] = value

#this is for when you have a perfect every other array of field then value
def everyOtherStrategy(data, soupArr):
    for tag in soupArr[::2]:
        value = tag.find_next_sibling()
        if value:
            value = cleanString(value.text)
            if value and tag.text:
                data[tag.text] = value

#takes a long string from a table with headers and rows and then makes a nested object and returns it
def tabularStrategy(tables, orderedFields):
    tabular = {}

    for table in tables:
        cols = table.find_all("td")
        i = 0
        max = len(orderedFields)
        ticker = None

        if len(table) < len(orderedFields):
            continue

        for colidx in range(len(orderedFields) + 1):
            col = cols[colidx]
            if i == 0:
                ticker = cleanString(col.text)
                tabular[ticker] = {}
            else:
                value = cleanString(col.text)
                field = orderedFields[i - 1]

                if value and field:
                    tabular[ticker][field] = value

            if i >= max:
                i = 0
            else:
                i += 1

    return tabular
    
#this takes the account data and attaches it to the data object passed in
def attachAccountData(data, id):
    params = {"id":makeId(id)}
    print(f"url: {makeURL(Data.ACCOUNT, params)}")
    html = makeCurlFor(Data.ACCOUNT, params)
    soup = goldilocks(BeautifulSoup(html, "html.parser"))

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
    boldStrategy(data, temp)

    return data


def attachBuildingData(data, id):
    params = {
        "id": makeId(id),
        "cd": "01"
    }
    print(f"url: {makeURL(Data.BUILDING, params)}")
    html = makeCurlFor(Data.BUILDING, params)
    soup = goldilocks(BeautifulSoup(html, "html.parser"))

    rows = soup.find_all("tr")

    temp = rows[7].find_all("td")
    data["Building Location Address"] = cleanString(temp[3].text)
    data["Building Description"] = cleanString(temp[8].text)

    #first mega col
    temp = rows[15].find("td").find_all("tr")
    boldStrategy(data, temp)

    #second mega col
    temp = rows[27].find_all("td")[1:]
    everyOtherStrategy(data, temp)

    temp = rows[30].find_all("td")[1:]
    everyOtherStrategy(data, temp)

    #third mega col
    temp = rows[15].find_all("td")[67].find_all("tr")
    boldStrategy(data, temp)

    #table row with 2 col
    temp = rows[50].find("td").find_all("tr")[1:]
    data["Main and Addition Summary"] = tabularStrategy(temp, ["Story", None, "Type", "Code", "Area", "Inc"])

    print(data)
    return data

#this gets all the data associated with the id and returns it
def getData(id):
    data = {}
    attachAccountData(data, id)
    attachBuildingData(data, id)
    return data

#this takes the data and saves it
def saveData(data):
    id = data["Real Estate ID"]
    file = open(f"{STORAGE_DIR}/{id}.json", "w")
    file.write(json.dumps(data))
    file.close()

getData(198345)

# def main():
#     global FAIL_COUNT
#     for id in range(1, 9999999):
#         if FAIL_COUNT >= MAX_FAIL:
#             print("Finished collecting data from wake county houses")
#             return

#         try:
#             print(f"#{makeId(id)}")
#             data = getData(id)
#             print(data)
#             saveData(data)
#             FAIL_COUNT = 0
#         except Exception as e:
#             print(e)
#             FAIL_COUNT += 1

#         print("\n")

# if __name__ == "__main__":
#     main()
